"""Four scripted searchers with a known, exact trial count (spec §3.1).
Deliberate choice: validate the estimator against searchers whose behavior
is fully specified before introducing agent messiness. If the estimator
fails here it fails everywhere, and the fault can't be pinned on the agent.

Every searcher submits a naive, undiscounted predictive distribution
(Distribution.degenerate at its own in-sample Sharpe) — none of these know
to discount for their own search. That's the point: calibration is scored
against the estimator's transcript-implied deflation, not against anything
the scripted searcher itself believes.

Every searcher also implements `replay` (searchers/base.py's `Replayable`
protocol): the SAME decision rule as `run`, re-expressed as pure array
operations on a set of (possibly resampled) base feature columns instead of
sandbox.evaluate() calls. `run` and `replay` share one core routine per
searcher so the two can't drift out of sync -- `replay` is what makes
estimator/recursive_bootstrap.py possible.
"""
from __future__ import annotations

import itertools

import numpy as np

from environments.sandbox import Sandbox, Specification, Distribution, EvalResult
from estimator.bootstrap import sharpe
from searchers.base import Searcher


def _one_hot_sum(K: int, indices) -> np.ndarray:
    w = np.zeros(K)
    w[list(indices)] = 1.0
    return w


def _column_sharpe(column: np.ndarray, annualization: float = 1.0) -> float:
    return float(sharpe(column[:, None], axis=0, annualization=annualization)[0])


def _greedy_forward_selection(K: int, max_features: int, singles_score, support_score):
    """Shared core of Adaptive's run() and replay(): evaluate all K singles,
    keep the best, then repeatedly try extending the current best support by
    one more feature, keeping the extension only if it improves.

    singles_score(k) -> float; support_score(support: list[int]) -> float.
    Returns (final_support, final_score)."""
    best_k, best_score = None, -np.inf
    for k in range(K):
        score = singles_score(k)
        if score > best_score:
            best_k, best_score = k, score

    support = [best_k]
    remaining = set(range(K)) - {best_k}

    for _ in range(max_features - 1):
        round_best_j, round_best_score = None, -np.inf
        for j in remaining:
            score = support_score(support + [j])
            if score > round_best_score:
                round_best_j, round_best_score = j, score
        if round_best_j is None or round_best_score <= best_score:
            break
        support.append(round_best_j)
        remaining.discard(round_best_j)
        best_score = round_best_score

    return support, best_score


def _support_name(support) -> str:
    return "[" + ",".join(f"{k}{'+' if s > 0 else '-'}" for k, s in support) + "]"


def _signed_sum(K: int, support) -> np.ndarray:
    """Weights for a signed subset: +-1 on each named feature, 0 elsewhere.
    `support` is an iterable of (feature_index, sign) pairs."""
    w = np.zeros(K)
    for k, s in support:
        w[k] = float(s)
    return w


def _greedy_forward_selection_signed(K: int, max_features: int, singles_score,
                                     support_score):
    """The signed counterpart of `_greedy_forward_selection`: identical control
    flow, but every candidate is tried at both signs.

    Shared by SignedAdaptive's run() and replay() for the same reason the
    unsigned core is shared -- two implementations of one decision rule drift,
    and recursive_bootstrap.py is only valid while they agree.

    singles_score(k, sign) -> float; support_score(support) -> float, where
    support is a list of (index, sign) pairs. Returns (support, score).
    """
    best, best_score = None, -np.inf
    for k in range(K):
        for sign in (1.0, -1.0):
            score = singles_score(k, sign)
            if score > best_score:
                best, best_score = (k, sign), score

    support = [best]
    remaining = set(range(K)) - {best[0]}

    for _ in range(max_features - 1):
        round_best, round_best_score = None, -np.inf
        for j in remaining:
            for sign in (1.0, -1.0):
                score = support_score(support + [(j, sign)])
                if score > round_best_score:
                    round_best, round_best_score = (j, sign), score
        if round_best is None or round_best_score <= best_score:
            break
        support.append(round_best)
        remaining.discard(round_best[0])
        best_score = round_best_score

    return support, best_score


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

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        return _column_sharpe(base_columns[:, self.feature_index], annualization)


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

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        return float(sharpe(base_columns, axis=0, annualization=annualization).max())


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

    def _combos(self, K: int) -> list[tuple[int, ...]]:
        # A function of K/subset_sizes/seed only -- never of realized returns
        # -- so it is exactly reproducible inside replay() without having
        # observed the original run's transcript. Cached: replay() calls this
        # once per bootstrap replicate, and it's identical every time.
        cached = getattr(self, "_combos_cache", None)
        if cached is not None and cached[0] == K:
            return cached[1]
        combos = list(itertools.chain.from_iterable(
            itertools.combinations(range(K), size) for size in self.subset_sizes
        ))
        if self.max_trials is not None and len(combos) > self.max_trials:
            rng = np.random.default_rng(self.seed)
            keep = rng.choice(len(combos), size=self.max_trials, replace=False)
            combos = [combos[i] for i in keep]
        self._combos_cache = (K, combos)
        return combos

    def _membership_matrix(self, K: int) -> np.ndarray:
        # (K, n_combos) 0/1 matrix so replay() can score every combo in one
        # matmul + vectorized Sharpe instead of a per-combo Python loop --
        # replay() runs once per bootstrap replicate, so this matters.
        cached = getattr(self, "_membership_cache", None)
        if cached is not None and cached[0] == K:
            return cached[1]
        combos = self._combos(K)
        M = np.zeros((K, len(combos)))
        for c, combo in enumerate(combos):
            M[list(combo), c] = 1.0
        self._membership_cache = (K, M)
        return M

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        best: tuple[Specification, EvalResult] | None = None
        for combo in self._combos(K):
            spec = Specification(weights=_one_hot_sum(K, combo), name=f"grid_{combo}")
            result = sandbox.evaluate(spec)
            if best is None or result.sharpe > best[1].sharpe:
                best = (spec, result)
        sandbox.submit(best[0], Distribution.degenerate(best[1].sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]
        candidates = base_columns @ self._membership_matrix(K)   # (T, n_combos)
        return float(sharpe(candidates, axis=0, annualization=annualization).max())


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

        def singles_score(k):
            return sandbox.evaluate(Specification(weights=_one_hot_sum(K, [k]), name=f"adaptive_f{k}")).sharpe

        def support_score(support):
            return sandbox.evaluate(Specification(weights=_one_hot_sum(K, support), name=f"adaptive_{support}")).sharpe

        support, best_sharpe = _greedy_forward_selection(K, self.max_features, singles_score, support_score)
        spec = Specification(weights=_one_hot_sum(K, support), name=f"adaptive_{support}")
        sandbox.submit(spec, Distribution.degenerate(best_sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]

        def singles_score(k):
            return _column_sharpe(base_columns[:, k], annualization)

        def support_score(support):
            return _column_sharpe(base_columns[:, support].sum(axis=1), annualization)

        _, best_sharpe = _greedy_forward_selection(K, self.max_features, singles_score, support_score)
        return best_sharpe

    def round1_beam(self, base_columns: np.ndarray, annualization: float = 1.0) -> frozenset[int]:
        """The dose-response family's uniform diagnostic hook (searchers/
        dose_response.py, estimator/divergence.py): the set of features
        that survive round 0 to seed later-round candidate generation.
        For beam_width=1 (Adaptive), that's just the single best feature."""
        sr = sharpe(base_columns, axis=0, annualization=annualization)
        return frozenset({int(np.argmax(sr))})


class SignedGreedy(Searcher):
    """Greedy over the *signed* single-feature class: every feature at +1 and at
    -1, exactly N = 2K trials.

    Why it exists. `Greedy` and `Adaptive` build weights with `_one_hot_sum`,
    which is unsigned, so they are confined to the unsigned sublattice -- 10,700
    members of the 82,240-member signed class at K=40, d=3. Pricing them against
    a signed bar measures their confinement, not the bootstrap; that is what made
    `calibration-at-1pct` arm B unreadable. 7.0 matches each scripted arm to a
    class its searcher can actually reach, which needs signed searchers to exist.
    """
    name = "signed-greedy"

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        best: tuple[Specification, EvalResult] | None = None
        for k in range(K):
            for sign in (1.0, -1.0):
                spec = Specification(weights=_signed_sum(K, [(k, sign)]),
                                     name=f"signed_greedy_f{k}{'+' if sign > 0 else '-'}")
                result = sandbox.evaluate(spec)
                if best is None or result.sharpe > best[1].sharpe:
                    best = (spec, result)
        sandbox.submit(best[0], Distribution.degenerate(best[1].sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        # A negated column's Sharpe is the negation of the column's, so the best
        # over both signs is the largest absolute single-feature Sharpe.
        return float(np.abs(sharpe(base_columns, axis=0, annualization=annualization)).max())


class SignedAdaptive(Searcher):
    """Forward selection over the signed class: the same rule as `Adaptive`, but
    each candidate is tried at +1 and -1 and the better sign is kept.

    Its reach is `SubsetClass(max_size=max_features, signed=True)`, which is the
    class 7.0 prices it against.
    """
    name = "signed-adaptive"

    def __init__(self, max_features: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.max_features = max_features

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features

        def singles_score(k, sign):
            return sandbox.evaluate(Specification(
                weights=_signed_sum(K, [(k, sign)]),
                name=f"signed_adaptive_f{k}{'+' if sign > 0 else '-'}")).sharpe

        def support_score(support):
            return sandbox.evaluate(Specification(
                weights=_signed_sum(K, support),
                name=f"signed_adaptive_{_support_name(support)}")).sharpe

        support, best = _greedy_forward_selection_signed(
            K, self.max_features, singles_score, support_score)
        spec = Specification(weights=_signed_sum(K, support),
                             name=f"signed_adaptive_{_support_name(support)}")
        sandbox.submit(spec, Distribution.degenerate(best))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]

        def singles_score(k, sign):
            return _column_sharpe(base_columns[:, k] * sign, annualization)

        def support_score(support):
            stream = sum(base_columns[:, k] * s for k, s in support)
            return _column_sharpe(stream, annualization)

        _, best = _greedy_forward_selection_signed(
            K, self.max_features, singles_score, support_score)
        return best

    def round1_beam(self, base_columns: np.ndarray, annualization: float = 1.0) -> frozenset[int]:
        """Signed search still keeps one feature out of round 0; which sign it
        took does not change *which* feature seeds the next round."""
        sr = np.abs(sharpe(base_columns, axis=0, annualization=annualization))
        return frozenset({int(np.argmax(sr))})


class BudgetedRandom(Searcher):
    """Draws a fixed budget of members uniformly from the declared class, scores
    each, and submits the best seen.

    Specified in `prereg/gate-comparison.md` amendment 5. It exists because 7.0
    needs searchers that genuinely submit **below** their class maximum: arm D
    measured sub-maximal greedy search as costing 0.0001 in mean Sharpe, so an
    efficient searcher leaves replay almost nothing to recover. Here the slack is
    set by the budget and is tunable by construction.

    Two properties the certifier comparison needs:

    - **capped to the declared class by construction.** It samples members *of*
      the class, so it can reach nothing outside it. No `set_class` call is
      needed and none is possible.
    - **replayable.** The sample is drawn from a generator seeded by the
      searcher's seed, so a bootstrap replicate re-executes the *same* sample of
      members: the budget is a property of the searcher, not of the data. That is
      what `Replayable` requires, and it is why this searcher can be priced by
      process replay at all.
    """
    name = "budgeted-random"

    def __init__(self, budget: int = 100, max_size: int = 3, signed: bool = True,
                 seed: int = 0):
        super().__init__(seed=seed)
        self.budget = int(budget)
        self.max_size = int(max_size)
        self.signed = bool(signed)

    # -- the sample, a function of the seed and K alone ---------------------

    def _sample(self, K: int) -> list[list[tuple[int, float]]]:
        rng = np.random.default_rng(self.seed)
        signs = (1.0, -1.0) if self.signed else (1.0,)
        out = []
        for _ in range(self.budget):
            m = int(rng.integers(1, self.max_size + 1))
            feats = rng.choice(K, size=m, replace=False)
            out.append([(int(j), float(signs[rng.integers(len(signs))])) for j in feats])
        return out

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        best = None
        for i, support in enumerate(self._sample(K)):
            spec = Specification(weights=_signed_sum(K, support),
                                 name=f"budgeted_random_{i}")
            result = sandbox.evaluate(spec)
            if best is None or result.sharpe > best[1].sharpe:
                best = (spec, result)
        sandbox.submit(best[0], Distribution.degenerate(best[1].sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]
        best = float("-inf")
        for support in self._sample(K):
            stream = sum(base_columns[:, k] * s for k, s in support)
            best = max(best, _column_sharpe(stream, annualization))
        return best
