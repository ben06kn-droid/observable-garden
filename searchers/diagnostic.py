"""Control searchers used to isolate exactly which property of Adaptive
breaks the naive bootstrap. SCOPE.md's theory says it's the candidate
MENU's obliviousness (fixed given config, independent of realized
outcomes) that matters, not how a searcher picks among an oblivious menu.
LatticeAdaptive tests this directly, holding selection logic fixed and
changing only whether the menu is built up front or round-by-round.
"""
from __future__ import annotations

import itertools

import numpy as np

from environments.sandbox import Sandbox, Specification, Distribution
from searchers.base import Searcher
from searchers.scripted import _one_hot_sum, _column_sharpe


class LatticeAdaptive(Searcher):
    """Evaluates and logs the FULL fixed lattice -- every feature subset of
    size 1..max_features -- unconditionally on every run: an oblivious
    menu, identical in shape to GridSearch(subset_sizes=range(1,
    max_features+1), max_trials=None)'s transcript. It then SELECTS the
    submitted spec via the exact same sequential greedy rule as Adaptive:
    best single, then the best already-evaluated extension of it, and so
    on -- selection is just as sequentially data-dependent as Adaptive's.

    The one thing changed relative to Adaptive: candidate GENERATION
    (what gets evaluate()'d) no longer depends on realized outcomes; only
    the final SELECTION (what gets submit()'d) does. If the naive
    bootstrap calibrates here but not on Adaptive, adaptive selection is
    not the problem -- adaptive candidate generation is."""
    name = "lattice_adaptive"

    def __init__(self, max_features: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.max_features = max_features

    def _lattice(self, K: int) -> list[tuple[int, ...]]:
        return list(itertools.chain.from_iterable(
            itertools.combinations(range(K), size) for size in range(1, self.max_features + 1)
        ))

    def _select(self, K: int, sharpe_of: dict[tuple[int, ...], float]) -> tuple[list[int], float]:
        best_k = max(range(K), key=lambda k: sharpe_of[(k,)])
        support = [best_k]
        best_sharpe = sharpe_of[(best_k,)]
        remaining = set(range(K)) - {best_k}

        for _ in range(self.max_features - 1):
            round_best_j, round_best_sr = None, -np.inf
            for j in remaining:
                sr = sharpe_of[tuple(sorted(support + [j]))]
                if sr > round_best_sr:
                    round_best_j, round_best_sr = j, sr
            if round_best_j is None or round_best_sr <= best_sharpe:
                break
            support.append(round_best_j)
            remaining.discard(round_best_j)
            best_sharpe = round_best_sr

        return support, best_sharpe

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        sharpe_of = {}
        for combo in self._lattice(K):
            spec = Specification(weights=_one_hot_sum(K, combo), name=f"lat_{combo}")
            sharpe_of[combo] = sandbox.evaluate(spec).sharpe

        support, best_sharpe = self._select(K, sharpe_of)
        spec = Specification(weights=_one_hot_sum(K, support), name=f"lat_final_{support}")
        sandbox.submit(spec, Distribution.degenerate(best_sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]
        sharpe_of = {
            combo: _column_sharpe(base_columns[:, list(combo)].sum(axis=1), annualization)
            for combo in self._lattice(K)
        }
        _, best_sharpe = self._select(K, sharpe_of)
        return best_sharpe

    def round1_beam(self, base_columns: np.ndarray, annualization: float = 1.0) -> frozenset[int]:
        """Dose 0: the full menu, always. Divergence rate is 0 by
        construction -- nothing about the menu depends on realized data."""
        return frozenset(range(base_columns.shape[1]))


class PinnedSelector(Searcher):
    """Diagnostic searcher: builds a menu of `max_trials` OTHER candidates
    the same way GridSearch does (same combinatorial generation, same
    random-thinning seed), evaluates and logs every one of them -- but
    ALWAYS submits a specific, externally supplied weight vector regardless
    of what any of those trials found.

    Exists to isolate the pure multiple-testing cost of a larger transcript
    from a confound found in experiments/e10_power_vs_signal_strength.py:
    letting a real searcher (GridSearch) pick its own best spec means
    `sr_sel` improves as `N` grows (a bigger search finds a better
    specification), which pushed power UP with N there -- the opposite of
    what P(M_b >= sr_sel) should do when sr_sel is genuinely held fixed
    and the transcript (hence M_b) grows. Pinning the submission to a
    known weight vector (typically the true signal triple) removes that
    confound: for a FIXED draw, the pinned spec's in-sample Sharpe doesn't
    depend on N at all (it's the same evaluate() call on the same data
    regardless of how many other trials are also logged), so any change in
    power as N sweeps is now purely the bootstrap's response to a bigger
    transcript -- experiments/e11_power_vs_N_pinned.py."""
    name = "pinned_selector"

    def __init__(self, pinned_weights: np.ndarray, subset_sizes=(1, 2, 3), max_trials: int | None = None, seed: int = 0):
        super().__init__(seed=seed)
        self.pinned_weights = np.asarray(pinned_weights, dtype=float)
        self.subset_sizes = subset_sizes
        self.max_trials = max_trials

    def _combos(self, K: int) -> list[tuple[int, ...]]:
        combos = list(itertools.chain.from_iterable(
            itertools.combinations(range(K), size) for size in self.subset_sizes
        ))
        if self.max_trials is not None and len(combos) > self.max_trials:
            rng = np.random.default_rng(self.seed)
            keep = rng.choice(len(combos), size=self.max_trials, replace=False)
            combos = [combos[i] for i in keep]
        return combos

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        for combo in self._combos(K):
            sandbox.evaluate(Specification(weights=_one_hot_sum(K, combo), name=f"menu_{combo}"))
        pinned_spec = Specification(weights=self.pinned_weights, name="pinned")
        result = sandbox.evaluate(pinned_spec)
        sandbox.submit(pinned_spec, Distribution.degenerate(result.sharpe))
