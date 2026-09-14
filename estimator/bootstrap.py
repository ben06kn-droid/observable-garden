"""Bootstrapped null-maximum estimator: the replacement for closed-form DSR.

Given the full in-sample return matrix R (T x N) that a sandbox transcript
provides, demean every column (impose the null that nothing in the candidate
set carries true edge), then repeatedly draw a single stationary-bootstrap
time index and apply it to ALL columns simultaneously. This preserves the
cross-sectional correlation between trials exactly and the within-trial
autocorrelation approximately, so a search with heavily correlated or
duplicated trials does not get over-penalized the way an independence-
assuming closed form does.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from arch.bootstrap import optimal_block_length


def sharpe(R: np.ndarray, axis: int = 0, annualization: float = 1.0) -> np.ndarray:
    """Per-period Sharpe (mean/std, ddof=1) along `axis`, scaled by `annualization`
    (pass sqrt(periods_per_year) to match environments.sandbox's convention).
    Zero-variance columns return 0 rather than inf/nan."""
    mean = R.mean(axis=axis)
    std = R.std(axis=axis, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr = np.where(std > 0, mean / np.where(std > 0, std, 1.0), 0.0)
    return sr * annualization


def select_block_length(R: np.ndarray) -> int:
    """One shared block length for the joint resampling scheme: the median of
    each column's own Politis-White-optimal stationary block length. Median
    (not mean) so a handful of near-white-noise columns don't get dragged
    around by one highly autocorrelated outlier column."""
    T, N = R.shape
    if N == 0:
        return 1
    lengths = optimal_block_length(R)["stationary"].to_numpy()
    L = int(round(np.median(lengths)))
    return int(np.clip(L, 1, max(1, T // 4)))


def stationary_bootstrap_indices(T: int, L: int, rng: np.random.Generator) -> np.ndarray:
    """One draw of Politis-Romano (1994) stationary bootstrap indices: random-
    length geometric blocks (mean length L, circular wrap-around), concatenated
    to length T. Vectorized per-block rather than per-time-step for speed."""
    if L <= 1:
        return rng.integers(T, size=T)
    p = 1.0 / L
    idx = np.empty(T, dtype=np.int64)
    pos = 0
    while pos < T:
        start = rng.integers(T)
        length = min(int(rng.geometric(p)), T - pos)
        idx[pos:pos + length] = (start + np.arange(length)) % T
        pos += length
    return idx


@dataclass
class BootstrapResult:
    M_b: np.ndarray          # (B,) bootstrap null maxima
    block_length: int
    B: int

    @property
    def mean_null_max(self) -> float:
        return float(self.M_b.mean())

    @property
    def std_null_max(self) -> float:
        return float(self.M_b.std(ddof=1))


def null_max_bootstrap(
    R: np.ndarray,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> BootstrapResult:
    """The core estimator (spec §1.3). R: (T, N) in-sample return matrix, one
    column per evaluated specification. Returns the empirical distribution of
    the null maximum {M_b}."""
    R = np.asarray(R, dtype=float)
    if R.ndim != 2:
        raise ValueError("R must be (T, N)")
    T, N = R.shape
    if N == 0:
        raise ValueError("R has no columns to bootstrap over")

    R_demeaned = R - R.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(R_demeaned)
    rng = np.random.default_rng(seed)

    M_b = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        R_boot = R_demeaned[idx, :]
        M_b[b] = sharpe(R_boot, axis=0, annualization=annualization).max()

    return BootstrapResult(M_b=M_b, block_length=L, B=B)


@dataclass
class DeflationResult:
    sr_sel: float
    sr_deflated: float
    p_value: float
    mean_null_max: float
    block_length: int
    B: int
    N: int


def deflate(
    R: np.ndarray,
    sr_sel: float | None = None,
    B: int = 10_000,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> DeflationResult:
    """Deflate a reported in-sample Sharpe against the bootstrapped null
    maximum of the transcript that produced it. If `sr_sel` is omitted, it
    defaults to max_n SR(R[:, n]) — the argmax convention of spec §1.1."""
    R = np.asarray(R, dtype=float)
    if sr_sel is None:
        sr_sel = float(sharpe(R, axis=0, annualization=annualization).max())

    boot = null_max_bootstrap(R, B=B, block_length=block_length, annualization=annualization, seed=seed)
    p_value = (1 + np.sum(boot.M_b >= sr_sel)) / (boot.B + 1)

    return DeflationResult(
        sr_sel=sr_sel,
        sr_deflated=sr_sel - boot.mean_null_max,
        p_value=float(p_value),
        mean_null_max=boot.mean_null_max,
        block_length=boot.block_length,
        B=boot.B,
        N=R.shape[1],
    )
