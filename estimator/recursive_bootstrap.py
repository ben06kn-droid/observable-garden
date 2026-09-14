"""Recursive bootstrap: the general fix for sequentially-adaptive search
(SCOPE.md). The naive bootstrap (estimator/bootstrap.py) resamples the
*observed* transcript's fixed columns; for a searcher whose later trials are
chosen conditional on earlier realized outcomes, that freezes the selection
at its value on the real data instead of re-deriving it, which under-
explores the true null and produces anti-conservative p-values (confirmed
mechanistically in experiments/verify_selective_inference_theory.py).

Efron (2014, "Estimation and Accuracy after Model Selection", JASA)'s
prescription: the bootstrap must re-run the selection step inside every
replicate. This module does that generically, for any searcher implementing
`Replayable` (searchers/base.py) -- `replay(base_columns)` re-derives the
searcher's own decision rule on a given set of (possibly resampled) base
return columns, without touching a Sandbox.

Scope: this requires the searcher's later-round candidates to be
reconstructable from the K base single-feature columns (true for every
searcher in searchers/scripted.py, since Specification is linear and every
candidate within one draw shares the same period noise -- confirmed to
float precision). A searcher whose decision rule can't be re-expressed this
way -- an LLM agent, in general -- would need the fully general version:
literally re-running the whole search against a resampled Sandbox each
replicate. That's intractable at the B~1000s-per-null-draw scale a
calibration check needs (SCOPE.md §5); this is the tractable version for
anything built out of linear combinations of a fixed base set.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from searchers.base import Replayable


@dataclass
class RecursiveBootstrapResult:
    M_b: np.ndarray
    block_length: int
    B: int

    @property
    def mean_null_max(self) -> float:
        return float(self.M_b.mean())

    @property
    def std_null_max(self) -> float:
        return float(self.M_b.std(ddof=1))


def recursive_null_max_bootstrap(
    base_columns: np.ndarray,
    searcher: Replayable,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> RecursiveBootstrapResult:
    """base_columns: (T, K) raw (undemeaned) single-feature return columns,
    from Sandbox.base_feature_columns() on the real data. Demeans (imposes
    the null), block-bootstraps the time index once per replicate, then
    calls searcher.replay on the resampled columns -- so the search's own
    data-dependent choices (which feature wins each round, etc.) are
    re-derived fresh each replicate rather than frozen at their value on the
    real data."""
    base_columns = np.asarray(base_columns, dtype=float)
    T, K = base_columns.shape
    S0 = base_columns - base_columns.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(S0)
    rng = np.random.default_rng(seed)

    M_b = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        M_b[b] = searcher.replay(S0[idx, :], annualization=annualization)
    return RecursiveBootstrapResult(M_b=M_b, block_length=L, B=B)


@dataclass
class RecursiveDeflationResult:
    sr_sel: float
    sr_deflated: float
    p_value: float
    mean_null_max: float
    block_length: int
    B: int


def recursive_deflate(
    base_columns: np.ndarray,
    searcher: Replayable,
    sr_sel: float,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> RecursiveDeflationResult:
    boot = recursive_null_max_bootstrap(
        base_columns, searcher, B=B, block_length=block_length, annualization=annualization, seed=seed,
    )
    p_value = (1 + np.sum(boot.M_b >= sr_sel)) / (boot.B + 1)
    return RecursiveDeflationResult(
        sr_sel=sr_sel,
        sr_deflated=sr_sel - boot.mean_null_max,
        p_value=float(p_value),
        mean_null_max=boot.mean_null_max,
        block_length=boot.block_length,
        B=boot.B,
    )
