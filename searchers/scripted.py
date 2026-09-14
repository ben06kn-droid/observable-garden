"""Four scripted searchers with a known, exact trial count (spec §3.1).
Deliberate choice: validate the estimator against searchers whose behavior
is fully specified before introducing agent messiness. If the estimator
fails here it fails everywhere, and the fault can't be pinned on the agent.

Every searcher submits a naive, undiscounted predictive distribution
(Distribution.degenerate at its own in-sample Sharpe) — none of these know
to discount for their own search. That's the point: calibration is scored
against the estimator's transcript-implied deflation, not against anything
the scripted searcher itself believes.
"""
from __future__ import annotations

import itertools

import numpy as np

from environments.sandbox import Sandbox, Specification, Distribution, EvalResult
from searchers.base import Searcher


def _one_hot_sum(K: int, indices) -> np.ndarray:
    w = np.zeros(K)
    w[list(indices)] = 1.0
    return w


class Honest(Searcher):
    """Control: fits one pre-registered specification, no selection. N=1.
    Deflation should be ~0 and the p-value ~ uniform."""
    name = "honest"

    def __init__(self, feature_index: int = 0, seed: int = 0):
        super().__init__(seed=seed)
        self.feature_index = feature_index

    def run(self, sandbox: Sandbox) -> None:
        spec = Specification(weights=_one_hot_sum(sandbox.num_features, [self.feature_index]), name="honest")
        result = sandbox.evaluate(spec)
        sandbox.submit(spec, Distribution.degenerate(result.sharpe))


class Greedy(Searcher):
    """Evaluates all K single-feature strategies, takes the best. Minimal
    selection, exactly N = K."""
    name = "greedy"

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        best: tuple[Specification, EvalResult] | None = None
        for k in range(K):
            spec = Specification(weights=_one_hot_sum(K, [k]), name=f"greedy_f{k}")
            result = sandbox.evaluate(spec)
            if best is None or result.sharpe > best[1].sharpe:
                best = (spec, result)
        sandbox.submit(best[0], Distribution.degenerate(best[1].sharpe))


class GridSearch(Searcher):
    """Feature subsets up to size `max(subset_sizes)`, equal-weighted. Large
    N, heavily correlated trials by construction: overlapping subsets share
    components (e.g. {1,2} and {1,3} both carry feature 1's contribution).

    The proposal's grid also sweeps a lookback and a threshold axis. Those
    presuppose a strategy that trades on rolling-window smoothing and a
    signal-gating rule; this DGP's features are drawn iid across time with
    no autocorrelation for a lookback to exploit, and this Specification is
    a pure linear rule with no gating mechanism. Rather than bolt on
    machinery the environment doesn't otherwise use, the large-N,
    heavily-correlated-trials property this searcher is meant to exercise
    is produced by combinatorial subset overlap instead. Noted here rather
    than left implicit.
    """
    name = "gridsearch"

    def __init__(self, subset_sizes=(1, 2, 3), max_trials: int | None = 1500, seed: int = 0):
        super().__init__(seed=seed)
        self.subset_sizes = subset_sizes
        self.max_trials = max_trials

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        combos = list(itertools.chain.from_iterable(
            itertools.combinations(range(K), size) for size in self.subset_sizes
        ))
        if self.max_trials is not None and len(combos) > self.max_trials:
            rng = np.random.default_rng(self.seed)
            keep = rng.choice(len(combos), size=self.max_trials, replace=False)
            combos = [combos[i] for i in keep]

        best: tuple[Specification, EvalResult] | None = None
        for combo in combos:
            spec = Specification(weights=_one_hot_sum(K, combo), name=f"grid_{combo}")
            result = sandbox.evaluate(spec)
            if best is None or result.sharpe > best[1].sharpe:
                best = (spec, result)
        sandbox.submit(best[0], Distribution.degenerate(best[1].sharpe))


class Adaptive(Searcher):
    """Sequential greedy forward selection: evaluate all singles, keep the
    best, then repeatedly try adding one more feature to the current best
    support, keeping the addition only if it improves. Trials are
    sequentially dependent, not just correlated -- this is the searcher that
    reproduces a real agent's search structure, where later trials are
    chosen conditional on earlier results."""
    name = "adaptive"

    def __init__(self, max_features: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.max_features = max_features

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        remaining = set(range(K))

        best_singles: tuple[int, EvalResult] | None = None
        for k in range(K):
            result = sandbox.evaluate(Specification(weights=_one_hot_sum(K, [k]), name=f"adaptive_f{k}"))
            if best_singles is None or result.sharpe > best_singles[1].sharpe:
                best_singles = (k, result)

        support = [best_singles[0]]
        best_sharpe = best_singles[1].sharpe
        best_spec = Specification(weights=_one_hot_sum(K, support), name=f"adaptive_{support}")
        remaining.discard(support[0])

        for _ in range(self.max_features - 1):
            round_best: tuple[int, EvalResult] | None = None
            for k in remaining:
                trial_support = support + [k]
                result = sandbox.evaluate(Specification(weights=_one_hot_sum(K, trial_support), name=f"adaptive_{trial_support}"))
                if round_best is None or result.sharpe > round_best[1].sharpe:
                    round_best = (k, result)
            if round_best is None or round_best[1].sharpe <= best_sharpe:
                break
            support.append(round_best[0])
            remaining.discard(round_best[0])
            best_sharpe = round_best[1].sharpe
            best_spec = Specification(weights=_one_hot_sum(K, support), name=f"adaptive_{support}")

        sandbox.submit(best_spec, Distribution.degenerate(best_sharpe))
