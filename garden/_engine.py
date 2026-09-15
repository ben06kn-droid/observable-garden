"""The gate's Reality Check bootstrap.

Draws the same stationary-bootstrap indices, from the same RNG stream, as
estimator.bootstrap.null_max_bootstrap, so M_b matches it to floating point
(tests/test_garden.py). Instead of copying resampled rows, each replicate is
a vector of index counts: a resampled column's mean and second moment are
count-weighted sums over the original rows, so a chunk of replicates is two
matrix products.

Beyond the null maximum it records what the gate's other checks need: the
submitted column's Sharpe in every replicate (a nonparametric sampling
distribution for power), and for the degeneracy check (SCOPE.md §11) whether
each replicate's argmax entry was degenerate plus the maximum over
non-degenerate entries. An entry is degenerate when its resample holds fewer
than `support_min` distinct periods with a non-zero return for that column,
or its resampled standard deviation is below `q_min` times the full-sample
one. The same variance floor and Sharpe cap as estimator.bootstrap.sharpe
apply, with counters.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from estimator.bootstrap import SHARPE_CAP, VARIANCE_FLOOR, select_block_length, stationary_bootstrap_indices


@dataclass
class EngineResult:
    M_b: np.ndarray
    tracked: np.ndarray | None
    block_length: int
    M_b_screened: np.ndarray       # per-replicate max over non-degenerate entries (-inf if none)
    argmax_degenerate: np.ndarray  # bool: was each replicate's argmax entry degenerate
    argmax_column: np.ndarray      # int: which column set each replicate's maximum
    floor_binds: int
    cap_binds: int


def null_max_bootstrap(
    R: np.ndarray,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
    track_index: int | None = None,
    support_min: int = 0,
    q_min: float = 0.0,
    chunk: int = 64,
) -> EngineResult:
    R = np.asarray(R, dtype=float)
    T, _ = R.shape
    Rd = R - R.mean(axis=0, keepdims=True)
    R2 = Rd * Rd
    var_full = Rd.var(axis=0, ddof=1)
    sd_full = np.sqrt(np.where(var_full > 0, var_full, 1.0))
    active = (R != 0).astype(float) if support_min > 0 else None
    L = block_length if block_length is not None else select_block_length(Rd)
    rng = np.random.default_rng(seed)

    M_b, screened = np.empty(B), np.empty(B)
    degenerate, argmax = np.empty(B, dtype=bool), np.empty(B, dtype=np.int64)
    tracked = np.empty(B) if track_index is not None else None
    floor_binds = cap_binds = 0
    offsets = T * np.arange(chunk)
    for start in range(0, B, chunk):
        c = min(chunk, B - start)
        cols, sl = np.arange(c), slice(start, start + c)
        idx = np.stack([stationary_bootstrap_indices(T, L, rng) for _ in range(c)])
        counts = np.bincount((idx + offsets[:c, None]).ravel(), minlength=T * c).reshape(c, T).T
        W = counts / T
        m1 = Rd.T @ W
        m2 = R2.T @ W
        var = np.maximum((m2 - m1 * m1) * (T / (T - 1)), 0.0)
        live = var > VARIANCE_FLOOR * var_full[:, None]
        floor_binds += int(np.sum(~live & (var > 0)))
        sr = np.where(live, m1 / np.sqrt(np.where(live, var, 1.0)), 0.0) * annualization
        capped = np.abs(sr) > SHARPE_CAP
        cap_binds += int(np.sum(capped))
        sr = np.where(capped, np.sign(sr) * SHARPE_CAP, sr)

        a = sr.argmax(axis=0)
        M_b[sl], argmax[sl] = sr[a, cols], a
        flag = np.sqrt(var) < q_min * sd_full[:, None]
        if active is not None:
            flag |= (active.T @ (counts > 0).astype(float)) < support_min
        degenerate[sl] = flag[a, cols]
        screened[sl] = np.where(flag, -np.inf, sr).max(axis=0)
        if tracked is not None:
            tracked[sl] = sr[track_index]
    return EngineResult(
        M_b=M_b, tracked=tracked, block_length=L, M_b_screened=screened, argmax_degenerate=degenerate,
        argmax_column=argmax, floor_binds=floor_binds, cap_binds=cap_binds,
    )
