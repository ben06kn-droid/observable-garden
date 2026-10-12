"""Reporting helpers. A KS statistic against U(0,1) summarizes the whole
p-value distribution but isn't the legible number for "how often would this
fool someone using alpha=0.05" -- that's the type-I rate, and it needs a
confidence interval, not a bare fraction, since calibration checks run on a
finite number of null draws."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Better small-sample
    and near-boundary coverage than the normal approximation, which matters
    here since type-I rates near 0.05 or near 0 are exactly the regime being
    checked."""
    z = norm.ppf(0.5 + confidence / 2)
    phat = successes / n
    denom = 1 + z ** 2 / n
    center = phat + z ** 2 / (2 * n)
    half = z * np.sqrt(phat * (1 - phat) / n + z ** 2 / (4 * n ** 2))
    # The boundaries are exact and are set as such. At k=0 the closed form gives
    # center == half, so the lower bound is zero -- but in floating point it came
    # out as +4.3e-19, which printed as "-0.000" in one report and, worse, made a
    # `lo <= rate <= hi` containment test read false for an arm whose observed
    # rate was exactly zero. Clamping to [0, 1] does not fix that: the residue is
    # positive. Symmetrically, k == n gives an upper bound of exactly one. The
    # final clamp guards the interior against the same kind of drift.
    lo = 0.0 if successes == 0 else (center - half) / denom
    hi = 1.0 if successes == n else (center + half) / denom
    return float(min(max(lo, 0.0), 1.0)), float(min(max(hi, 0.0), 1.0))


def type1_rate(p_values: np.ndarray, alpha: float = 0.05, confidence: float = 0.95) -> tuple[float, float, float]:
    """Fraction of p-values below alpha, with a Wilson CI. Report alongside
    the KS statistic, not instead of it -- KS summarizes shape across the
    whole [0,1] range, this answers the operating question directly."""
    n = len(p_values)
    k = int(np.sum(p_values < alpha))
    rate = k / n
    lo, hi = wilson_ci(k, n, confidence)
    return rate, lo, hi


def rmse(pred: np.ndarray, actual: np.ndarray) -> float:
    pred, actual = np.asarray(pred, dtype=float), np.asarray(actual, dtype=float)
    return float(np.sqrt(np.mean((pred - actual) ** 2)))


def r_squared(pred: np.ndarray, actual: np.ndarray) -> float:
    pred, actual = np.asarray(pred, dtype=float), np.asarray(actual, dtype=float)
    ss_res = np.sum((actual - pred) ** 2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def ks_critical_value(n: int, alpha: float = 0.05) -> float:
    """Asymptotic critical value for the two-sided one-sample KS test
    (Kolmogorov distribution approximation). A KS statistic below this
    fails to reject uniformity -- which is evidence FOR calibration only in
    the weak sense of "not detected as broken by this test at this n", not
    proof of correctness. Report n alongside any KS statistic near this
    value."""
    c_alpha = {0.10: 1.22, 0.05: 1.36, 0.01: 1.63}.get(alpha, 1.36)
    return c_alpha / np.sqrt(n)
