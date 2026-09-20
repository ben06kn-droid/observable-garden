"""7.1's four nulls for a meta-adaptive search.

The replay gate re-executes an agent's typed moves on each bootstrap resample.
Content moves are rules and replay exactly; meta moves — when to stop, when to
restart — were chosen after seeing results, and what to do with them on a
replicate is the whole question (ROADMAP 7.1, THEORY.md P4).

Four nulls, all on the same resampled index so they are paired draw by draw:

1. **fixed_sequence** — meta choices frozen at their realized positions, content
   rules re-executed. The error being measured: the replicate is made to stop
   where the *real* search stopped, conditioning it on an event that has not
   happened to it.
2. **trigger** — each meta move's predicate re-evaluated on the replicate. A
   replicate whose predicate fires earlier stops there; one that would run past
   the realized sequence has no declared trigger left and is filled with greedy
   extension to the budget.
3. **policy** — the policy re-executed, exact because the policy is code. The
   reference the other two are scored against.
4. **declared_class** — the full-class bound, which does not depend on the
   search at all. Priced by `garden._full_class_engine`, not here.

Nothing in this module sweeps: it computes one null set for one searcher on one
sample. 7.1 drives it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from searchers.meta_adaptive import MetaAdaptive

NULLS = ("fixed_sequence", "trigger", "policy")


@dataclass
class ReplayNulls:
    """The three search-dependent nulls, paired: column b of each comes from the
    same resampled time index, so differences between them are the replay rule
    and nothing else."""
    fixed_sequence: np.ndarray
    trigger: np.ndarray
    policy: np.ndarray
    block_length: int
    B: int
    realized_score: float
    realized_actions: tuple[str, ...]

    def as_dict(self) -> dict[str, np.ndarray]:
        return {k: getattr(self, k) for k in NULLS}

    def p_value(self, which: str, sr: float | None = None) -> float:
        """The Monte Carlo p-value of the realized statistic against one null."""
        M_b = getattr(self, which)
        sr = self.realized_score if sr is None else sr
        return float((1 + np.sum(M_b >= sr)) / (M_b.size + 1))

    def kolmogorov_distance(self, which: str, against: str = "policy") -> float:
        """Sup-norm distance between two nulls' empirical CDFs. 7.1 reports this
        for fixed_sequence and trigger against policy."""
        a, b = np.sort(getattr(self, which)), np.sort(getattr(self, against))
        grid = np.concatenate([a, b])
        fa = np.searchsorted(a, grid, side="right") / a.size
        fb = np.searchsorted(b, grid, side="right") / b.size
        return float(np.max(np.abs(fa - fb)))


def replay_nulls(
    base_columns: np.ndarray,
    searcher: MetaAdaptive,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> ReplayNulls:
    """Price nulls 1-3 for `searcher` on `base_columns`.

    The realized search runs on `base_columns` **as they are**, not demeaned.
    That is the point of the fixed-sequence null: the sequence it freezes is the
    one the real search actually produced on the real data, including a stop that
    fired because the real data cleared a bar. Replicates are then drawn from the
    demeaned columns, so the null is imposed on the resamples while the frozen
    sequence stays the realized one.

    Taking the realized sequence from the demeaned columns instead would freeze a
    sequence that no search ever ran, and would usually invert the effect being
    measured: a stop-when-cleared policy rarely clears a bar on null data, so its
    "realized" sequence would run to the budget and the frozen null would come out
    *larger* than the policy null rather than smaller.
    """
    base_columns = np.asarray(base_columns, dtype=float)
    T, _ = base_columns.shape
    S0 = base_columns - base_columns.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(S0)
    rng = np.random.default_rng(seed)

    realized = searcher.trace(base_columns, annualization=annualization)
    actions = realized.actions()
    n_moves = realized.n_moves

    out = {k: np.empty(B) for k in NULLS}
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        R = S0[idx, :]
        out["fixed_sequence"][b] = searcher.replay_fixed_sequence(
            R, actions, annualization=annualization)
        out["trigger"][b] = searcher.replay_triggers(
            R, n_moves, annualization=annualization)
        out["policy"][b] = searcher.replay(R, annualization=annualization)

    return ReplayNulls(block_length=L, B=B, realized_score=realized.score,
                       realized_actions=tuple(actions), **out)
