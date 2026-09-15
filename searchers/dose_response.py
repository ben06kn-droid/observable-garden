"""Dose-response family: a scalar "dose" for how much a search's candidate
SET depends on realized data, interpolating between the two extremes
already measured (SCOPE.md, README "Results"):

    LatticeAdaptive  (full menu, dose 0 -- already shown calibrated)
    BeamAdaptive(k)  (top-k of round 1, dose = K/k)
    Adaptive         (= BeamAdaptive(1), argmax only, dose max -- already
                       shown to break the naive bootstrap)

Plus two structural variants, holding beam width at k=1:

    DepthAdaptive     -- one more round than Adaptive (selection compounds)
    NeighborAdaptive  -- round 2 expands around the feature most correlated
                         with the round-1 winner, not the winner itself
                         (tests whether it's Sharpe-argmax specifically, or
                         any realized-data-dependent anchor choice)

Every variant implements `round1_beam(base_columns) -> frozenset[int]`, the
set of features that survive round 0 to seed round 1's candidate
generation. This is what estimator/divergence.py measures across bootstrap
replicates: what fraction of a variant's round-1 beam, recomputed on
resampled data, differs from the real transcript's -- the quantitative
mechanism diagnostic, not just the type-I rate it produces.
"""
from __future__ import annotations

import numpy as np

from environments.sandbox import Sandbox, Specification, Distribution
from estimator.bootstrap import sharpe
from searchers.base import Searcher
from searchers.scripted import Adaptive, _one_hot_sum, _column_sharpe


def _base_columns_from_get_data(sandbox: Sandbox) -> np.ndarray:
    """A searcher computing this itself from get_data() (not touching the
    harness-only base_feature_columns()) -- legitimate self-service, since
    every entry here is already reconstructable from what get_data() hands
    a searcher (spec's own framing for why base_feature_columns() isn't a
    leak)."""
    df = sandbox.get_data()
    T = int(df["t"].max()) + 1
    M = sandbox.num_assets
    K = sandbox.num_features
    x = df[[f"f{k}" for k in range(K)]].to_numpy().reshape(T, M, K)
    r = df["r"].to_numpy().reshape(T, M)
    return (x * r[:, :, None]).mean(axis=1)


class BeamAdaptive(Searcher):
    """Adaptive generalized to keep the top-`beam_width` candidates each
    round instead of only the single best. beam_width=1 is exactly
    Adaptive; beam_width=K keeps everything, approximating LatticeAdaptive's
    full-menu behavior (mod evaluation-order redundancy). Beam width is the
    dose knob: round r+1's menu is filtered by round r's realized outcomes
    more aggressively as beam_width shrinks."""
    name = "beam_adaptive"

    def __init__(self, beam_width: int, max_features: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.beam_width = beam_width
        self.max_features = max_features

    def _search(self, K: int, score) -> tuple[list[int], float, frozenset[int]]:
        singles = sorted(range(K), key=lambda k: -score([k]))
        beam = [(tuple([k]), score([k])) for k in singles[: self.beam_width]]
        round1_beam = frozenset(k for (k,), _ in beam)
        best_support, best_sharpe = list(beam[0][0]), beam[0][1]
        seen = {support for support, _ in beam}

        for _ in range(self.max_features - 1):
            candidates = []
            for support, _ in beam:
                support_set = set(support)
                for j in range(K):
                    if j in support_set:
                        continue
                    new_support = tuple(sorted(support + (j,)))
                    if new_support in seen:
                        continue
                    seen.add(new_support)
                    candidates.append((new_support, score(list(new_support))))
            if not candidates:
                break
            candidates.sort(key=lambda x: -x[1])
            round_best_support, round_best_sharpe = candidates[0]
            if round_best_sharpe <= best_sharpe:
                break  # no improvement this round -- stop expanding, matching Adaptive
            best_support, best_sharpe = list(round_best_support), round_best_sharpe
            beam = candidates[: self.beam_width]

        return best_support, best_sharpe, round1_beam

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features

        def score(support):
            return sandbox.evaluate(Specification(weights=_one_hot_sum(K, support), name=f"beam_{support}")).sharpe

        support, best_sharpe, _ = self._search(K, score)
        spec = Specification(weights=_one_hot_sum(K, support), name=f"beam_final_{support}")
        sandbox.submit(spec, Distribution.degenerate(best_sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]

        def score(support):
            return _column_sharpe(base_columns[:, support].sum(axis=1), annualization)

        _, best_sharpe, _ = self._search(K, score)
        return best_sharpe

    def round1_beam(self, base_columns: np.ndarray, annualization: float = 1.0) -> frozenset[int]:
        K = base_columns.shape[1]
        sr = sharpe(base_columns, axis=0, annualization=annualization)
        top = np.argsort(-sr)[: self.beam_width]
        return frozenset(int(k) for k in top)


class DepthAdaptive(Adaptive):
    """Adaptive with one more round: three extension rounds instead of two
    (max_features=4 by default). Tests whether inflation compounds when
    the same k=1 greedy rule runs for longer."""
    name = "depth_adaptive"

    def __init__(self, max_features: int = 4, seed: int = 0):
        super().__init__(max_features=max_features, seed=seed)


class NeighborAdaptive(Searcher):
    """Round 1 picks the best single by Sharpe, same as Adaptive. Round 2
    expands around the feature most correlated (in realized aggregate
    return attribution) WITH the round-1 winner, rather than around the
    winner itself -- same menu size and round structure as Adaptive, only
    the RULE choosing round 2's anchor differs (correlation instead of
    Sharpe-argmax). Round 3+ proceeds with Adaptive's normal greedy rule on
    top of round 2's pick. Isolates whether it's specifically Sharpe-argmax
    that causes inflation, or any realized-data-dependent anchor choice."""
    name = "neighbor_adaptive"

    def __init__(self, max_features: int = 3, seed: int = 0):
        super().__init__(seed=seed)
        self.max_features = max_features

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        corr = np.abs(np.nan_to_num(np.corrcoef(base_columns, rowvar=False)[best_k], nan=0.0))
        # Exclude the winner after taking |corr|: excluding first made |-inf| the maximum, so the
        # anchor was always the winner itself (SCOPE.md §5's NeighborAdaptive result was that bug).
        corr[best_k] = -np.inf
        return int(np.argmax(corr))

    def _core(self, K: int, base_columns: np.ndarray, singles_score, support_score):
        best_k, best_sharpe = None, -np.inf
        for k in range(K):
            sr = singles_score(k)
            if sr > best_sharpe:
                best_k, best_sharpe = k, sr

        if self.max_features < 2:
            return [best_k], best_sharpe, frozenset({best_k})

        anchor = self._anchor(K, base_columns, best_k)
        round1_beam = frozenset({anchor})

        remaining = set(range(K)) - {anchor}
        round_best_j, round_best_sr = None, -np.inf
        for j in remaining:
            sr = support_score(sorted({anchor, j}))
            if sr > round_best_sr:
                round_best_j, round_best_sr = j, sr

        if round_best_j is None or round_best_sr <= best_sharpe:
            return [best_k], best_sharpe, round1_beam

        support = sorted({anchor, round_best_j})
        best_sharpe = round_best_sr
        remaining = set(range(K)) - set(support)

        for _ in range(self.max_features - 2):
            round_best_j, round_best_sr = None, -np.inf
            for j in remaining:
                sr = support_score(sorted(support + [j]))
                if sr > round_best_sr:
                    round_best_j, round_best_sr = j, sr
            if round_best_j is None or round_best_sr <= best_sharpe:
                break
            support = sorted(support + [round_best_j])
            remaining.discard(round_best_j)
            best_sharpe = round_best_sr

        return support, best_sharpe, round1_beam

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features

        def singles_score(k):
            return sandbox.evaluate(Specification(weights=_one_hot_sum(K, [k]), name=f"nbr_f{k}")).sharpe

        def support_score(support):
            return sandbox.evaluate(Specification(weights=_one_hot_sum(K, support), name=f"nbr_{support}")).sharpe

        base_columns = _base_columns_from_get_data(sandbox)
        support, best_sharpe, _ = self._core(K, base_columns, singles_score, support_score)
        spec = Specification(weights=_one_hot_sum(K, support), name=f"nbr_final_{support}")
        sandbox.submit(spec, Distribution.degenerate(best_sharpe))

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        K = base_columns.shape[1]

        def singles_score(k):
            return _column_sharpe(base_columns[:, k], annualization)

        def support_score(support):
            return _column_sharpe(base_columns[:, support].sum(axis=1), annualization)

        _, best_sharpe, _ = self._core(K, base_columns, singles_score, support_score)
        return best_sharpe

    def round1_beam(self, base_columns: np.ndarray, annualization: float = 1.0) -> frozenset[int]:
        K = base_columns.shape[1]
        sr = sharpe(base_columns, axis=0, annualization=annualization)
        best_k = int(np.argmax(sr))
        return frozenset({self._anchor(K, base_columns, best_k)})


class WinnerAnchor(NeighborAdaptive):
    """Round 2 expands around the round-1 winner itself (Adaptive's rule): the anchor is maximally
    coupled to the selection statistic."""
    name = "winner_anchor"

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        return best_k


class RandomAnchor(NeighborAdaptive):
    """Round 2 expands around a feature drawn from the searcher's own seed, independent of the data.
    With max_features=2 the whole menu is data-oblivious, which makes this the control."""
    name = "random_anchor"

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        return int(np.random.default_rng(self.seed).integers(K))


class WorstAnchor(NeighborAdaptive):
    """Round 2 expands around the round-1 loser: coupling to the selection statistic in the opposite
    direction."""
    name = "worst_anchor"

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        return int(np.argmin(sharpe(base_columns, axis=0)))


class GumbelAnchored(NeighborAdaptive):
    """Round 2 expands around a feature drawn with probability proportional to exp(tau * z_k), where z_k
    is feature k's single-feature Sharpe standardized across features. Uses the Gumbel-max trick with the
    noise drawn once from the searcher's seed, so a replay on resampled data reuses the same noise. tau
    sets the coupling to the selection statistic: +inf anchors on the winner, 0 is uniform random, and
    -inf anchors on the loser."""
    name = "gumbel_anchored"

    def __init__(self, tau: float, max_features: int = 2, seed: int = 0):
        super().__init__(max_features=max_features, seed=seed)
        self.tau = tau

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        if self.tau == np.inf:
            return best_k
        sr = sharpe(base_columns, axis=0)
        if self.tau == -np.inf:
            return int(np.argmin(sr))
        spread = sr.std()
        z = (sr - sr.mean()) / spread if spread > 0 else np.zeros(K)
        return int(np.argmax(self.tau * z + np.random.default_rng(self.seed).gumbel(size=K)))


class RankAnchor(NeighborAdaptive):
    """Round 2 expands around the feature whose single-feature Sharpe ranks `rank`-th, 1 being the round-1
    winner. Fixing the rank sets the anchor's coupling by design, instead of selecting draws by the rank a
    rule happened to pick. A replay re-ranks on the data it is given."""
    name = "rank_anchor"

    def __init__(self, rank: int, max_features: int = 2, seed: int = 0):
        super().__init__(max_features=max_features, seed=seed)
        if rank < 1:
            raise ValueError(f"rank must be at least 1, got {rank}")
        self.rank = rank

    def _anchor(self, K: int, base_columns: np.ndarray, best_k: int) -> int:
        if self.rank > K:
            raise ValueError(f"rank {self.rank} exceeds the {K} features")
        # Rank from the winner the search found, then the rest by Sharpe, so rank 1 is always the winner and
        # no other rank can be, even when floating-point near-ties reorder the top of the Sharpe sort.
        order = [j for j in np.argsort(-sharpe(base_columns, axis=0), kind="stable") if j != best_k]
        return int(([best_k] + order)[self.rank - 1])


def normalized_rank(base_columns: np.ndarray, k: int) -> float:
    """Where feature k's single-feature Sharpe ranks among all features: 1 for the best, 0 for the worst.
    Averaged over a search's anchors, this is the coupling kappa."""
    sr = sharpe(base_columns, axis=0)
    return float(np.sum(sr < sr[k]) / (len(sr) - 1))
