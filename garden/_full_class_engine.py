"""The full-class null computed from moments, without materializing the class's columns.

For a unit-weight subset S with signs s, the subset's return is a signed sum of base columns, so its
resampled mean is s·μ and its resampled second moment is sᵀ M s, where μ (K) and M (K×K) are the
resampled mean vector and second-moment matrix of the demeaned base columns. Each replicate computes
those once and scores every class member from them, which keeps memory at O(K² + members) however
large the class is (36,050 members at K=60, d=3; 1,333,500 at K=200).

Draws the same stationary-bootstrap indices, from the same RNG stream, as
estimator.bootstrap.null_max_bootstrap, and applies the same variance floor and Sharpe cap, so on a
materialized class (estimator.full_class.full_class_matrix) the two agree to floating point
(tests/test_garden.py).
"""
from __future__ import annotations

import numpy as np

from estimator.bootstrap import SHARPE_CAP, VARIANCE_FLOOR, select_block_length, stationary_bootstrap_indices
from garden.spec_class import SubsetClass

MEMBER_CHUNK = 100_000


def _quadratic(moment: np.ndarray, idx: np.ndarray, signs: np.ndarray) -> np.ndarray:
    """(n, c): sᵀ moment[S, S] s for each member, from a (K, K, c) moment array."""
    total = np.zeros((idx.shape[0], moment.shape[2]))
    for a in range(idx.shape[1]):
        for b in range(idx.shape[1]):
            total += (signs[:, a] * signs[:, b])[:, None] * moment[idx[:, a], idx[:, b], :]
    return total


def full_class_observed_max(
    base_returns: np.ndarray,
    spec_class: SubsetClass,
    annualization: float = 1.0,
) -> tuple[float, np.ndarray, int, int]:
    """The largest Sharpe ratio any member of the class attains on the observed
    data, and the weight vector attaining it.

    Costs nothing next to the null: `full_class_null_max` already forms
    `s^T cov s` per member at setup, and the observed numerator is just the
    member's full-sample mean, `signs . column means`. No resampling, one pass
    over the members -- 7 ms at K=40, d=3 signed, against ~160 s for B=10,000.

    Returns (max Sharpe, weights attaining it, variance-floor binds, cap binds).
    The guards match `full_class_null_max`'s exactly, so the observed statistic
    and the replicate statistic are the same function of a return stream --
    without that the comparison is between two slightly different Sharpes.

    This is the quantity that makes a searcher's p-value uniform rather than
    conservative: P2 says anything submitting less than this comes in under
    nominal, so submitting exactly this is the only way to test the null's
    exactness rather than its validity."""
    base = np.asarray(base_returns, dtype=float)
    K = base.shape[1]
    mu = base.mean(axis=0)
    demeaned = base - mu
    full_second = np.atleast_2d(np.cov(demeaned, rowvar=False, ddof=1))[:, :, None]

    best, best_idx, best_signs = -np.inf, None, None
    floor_binds = cap_binds = 0
    for m in range(1, min(spec_class.max_size, K) + 1):
        idx, signs = spec_class.members(K, m)
        var = _quadratic(full_second, idx, signs)[:, 0]
        num = np.einsum("nm,nm->n", signs, mu[idx])
        # The same two guards the replicate path applies, in the same order and
        # against the same reference variance, so the observed statistic and the
        # null statistic are the same function. Here var IS var_full, so the
        # floor reduces to var > 0; it is written this way so the two paths
        # cannot drift apart.
        live = var > VARIANCE_FLOOR * var
        floor_binds += int(np.sum(~live & (var > 0)))
        sr = np.where(live, num / np.sqrt(np.where(live, var, 1.0)), 0.0) * annualization
        capped = np.abs(sr) > SHARPE_CAP
        cap_binds += int(np.sum(capped))
        sr = np.where(capped, np.sign(sr) * SHARPE_CAP, sr)
        j = int(np.argmax(sr))
        if sr[j] > best:
            best, best_idx, best_signs = float(sr[j]), idx[j], signs[j]

    weights = np.zeros(K)
    weights[best_idx] = best_signs
    return best, weights, floor_binds, cap_binds


def full_class_null_max(
    base_returns: np.ndarray,
    spec_class: SubsetClass,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
    chunk: int = 64,
) -> tuple[np.ndarray, int, int, int]:
    """Returns (M_b, block_length, variance_floor_binds, sharpe_cap_binds), where M_b[b] is the largest
    Sharpe ratio over every member of the class on replicate b."""
    base = np.asarray(base_returns, dtype=float)
    T, K = base.shape
    demeaned = base - base.mean(axis=0, keepdims=True)
    full_second = np.atleast_2d(np.cov(demeaned, rowvar=False, ddof=1))[:, :, None]
    L = block_length if block_length is not None else select_block_length(demeaned)
    rng = np.random.default_rng(seed)

    groups = []
    for m in range(1, min(spec_class.max_size, K) + 1):
        idx, signs = spec_class.members(K, m)
        for start in range(0, len(idx), MEMBER_CHUNK):
            gi, gs = idx[start:start + MEMBER_CHUNK], signs[start:start + MEMBER_CHUNK]
            groups.append((gi, gs, _quadratic(full_second, gi, gs)[:, 0]))

    M_b = np.empty(B)
    floor_binds = cap_binds = 0
    offsets = T * np.arange(chunk)
    for start in range(0, B, chunk):
        c = min(chunk, B - start)
        idx_t = np.stack([stationary_bootstrap_indices(T, L, rng) for _ in range(c)])
        W = np.bincount((idx_t + offsets[:c, None]).ravel(), minlength=T * c).reshape(c, T).T / T
        mean = demeaned.T @ W
        second = np.stack([(demeaned * W[:, [b]]).T @ demeaned for b in range(c)], axis=2)
        best = np.full(c, -np.inf)
        for gi, gs, var_full in groups:
            numerator = np.einsum("nm,nmc->nc", gs, mean[gi])
            var = np.maximum((_quadratic(second, gi, gs) - numerator * numerator) * (T / (T - 1)), 0.0)
            live = var > VARIANCE_FLOOR * var_full[:, None]
            floor_binds += int(np.sum(~live & (var > 0)))
            sr = np.where(live, numerator / np.sqrt(np.where(live, var, 1.0)), 0.0) * annualization
            capped = np.abs(sr) > SHARPE_CAP
            cap_binds += int(np.sum(capped))
            sr = np.where(capped, np.sign(sr) * SHARPE_CAP, sr)
            best = np.maximum(best, sr.max(axis=0))
        M_b[start:start + c] = best
    return M_b, L, floor_binds, cap_binds
