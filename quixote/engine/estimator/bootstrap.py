"""Bootstrapped null-maximum estimator: a nonparametric search null within the DSR framework.

The deflated Sharpe ratio judges a reported Sharpe against what the research
process could have produced without skill (López de Prado & Porcu 2025). This
module builds that null from the logged trials themselves, as White's (2000)
Reality Check does, instead of DSR-L's closed-form location benchmark
(estimator/deflated_sharpe.py).

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


SHARPE_CAP = 100.0
VARIANCE_FLOOR = 1e-10
GUARD_COUNTS = {"zero_variance": 0, "variance_floor": 0, "sharpe_cap": 0}


def reset_guard_counts() -> None:
    for key in GUARD_COUNTS:
        GUARD_COUNTS[key] = 0


def sharpe(R: np.ndarray, axis: int = 0, annualization: float = 1.0,
           var_reference: np.ndarray | None = None) -> np.ndarray:
    """Per-period Sharpe (mean/std, ddof=1) along `axis`, scaled by `annualization`
    (pass sqrt(periods_per_year) to match environments.sandbox's convention).

    Guards against degenerate resamples (SCOPE.md, Sparse strategies), counted in GUARD_COUNTS so
    a run can show whether they ever changed an output: variance at or below
    VARIANCE_FLOOR x `var_reference` (a column's full-sample variance; by default
    its own, so only exact zeros) gives Sharpe 0, and |Sharpe| is capped at
    SHARPE_CAP annualized."""
    mean = R.mean(axis=axis)
    std = R.std(axis=axis, ddof=1)
    var = std * std
    reference = var if var_reference is None else var_reference
    live = (std > 0) & (var > VARIANCE_FLOOR * reference)
    GUARD_COUNTS["zero_variance"] += int(np.sum(std == 0))
    GUARD_COUNTS["variance_floor"] += int(np.sum((std > 0) & ~live))
    with np.errstate(invalid="ignore", divide="ignore"):
        sr = np.where(live, mean / np.where(live, std, 1.0), 0.0) * annualization
    capped = np.abs(sr) > SHARPE_CAP
    GUARD_COUNTS["sharpe_cap"] += int(np.sum(capped))
    return np.where(capped, np.sign(sr) * SHARPE_CAP, sr)


def select_block_length(R: np.ndarray) -> int:
    """One shared block length for the joint resampling scheme: the median of
    each column's own Politis-White-optimal stationary block length. Median
    (not mean) so a handful of near-white-noise columns don't get dragged
    around by one highly autocorrelated outlier column. Columns with no
    variance (a rule that never trades) have no dependence to measure, and
    columns where Politis-White is undefined return NaN; both are skipped."""
    T, N = R.shape
    live = R.std(axis=0) > 0 if N else np.zeros(0, dtype=bool)
    if not live.any():
        return 1
    lengths = optimal_block_length(R[:, live])["stationary"].to_numpy()
    lengths = lengths[np.isfinite(lengths)]
    if lengths.size == 0:
        return 1
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


def stationary_bootstrap_index_matrix(T: int, L: int, n: int, rng: np.random.Generator) -> np.ndarray:
    """(n, T) stationary bootstrap index sequences in one vectorized draw, with the same
    distribution as n calls to stationary_bootstrap_indices. Uses the equivalent Markov form:
    each period starts a new block at a uniform index with probability 1/L, otherwise continues
    the previous block circularly, which gives geometric block lengths with mean L. It consumes a
    different random stream, so it cannot reproduce results drawn with the per-replicate sampler."""
    if L <= 1:
        return rng.integers(T, size=(n, T))
    new_block = rng.random((n, T)) < 1.0 / L
    new_block[:, 0] = True
    starts = rng.integers(T, size=(n, T))
    positions = np.arange(T)
    block_start = np.maximum.accumulate(np.where(new_block, positions, 0), axis=1)
    return (np.take_along_axis(starts, block_start, axis=1) + positions - block_start) % T


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

    var_full = R_demeaned.var(axis=0, ddof=1)
    M_b = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        R_boot = R_demeaned[idx, :]
        M_b[b] = sharpe(R_boot, axis=0, annualization=annualization, var_reference=var_full).max()

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
