"""Critical values and power.

`audit` uses the bootstrap forms: the critical value read off the null
maximum, and power from the submitted column's own bootstrap Sharpe
distribution. `preflight` has no data, so it uses the analytic forms: Lo
(2002)'s standard error and the exact null maximum of independent or
equicorrelated Gaussian trial Sharpes.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.integrate import trapezoid
from scipy.optimize import brentq
from scipy.special import log_ndtr, ndtri
from scipy.stats import norm


def bootstrap_p_value(null: np.ndarray, sr: float) -> float:
    return float((1 + np.sum(null >= sr)) / (len(null) + 1))


def critical_value(null: np.ndarray, alpha: float) -> float:
    """The reported Sharpe must strictly exceed this for bootstrap_p_value < alpha.
    inf when B is too small for any result to reject."""
    null = np.asarray(null, dtype=float)
    B = len(null)
    # Same float expression as bootstrap_p_value, so the two can never disagree at the boundary.
    k = int(np.sum((1 + np.arange(B + 1)) / (B + 1) < alpha)) - 1
    if k < 0:
        return math.inf
    return float(np.sort(null)[B - 1 - k])


def bootstrap_power(sharpe_draws: np.ndarray, reference_sharpe: float, c: float) -> float:
    """Share of the submitted spec's centered bootstrap Sharpe draws, shifted to
    the reference Sharpe, that clear c. Assumes a rejection would come from
    that spec itself."""
    if not math.isfinite(c):
        return 0.0
    centered = sharpe_draws - sharpe_draws.mean()
    return float(np.mean(reference_sharpe + centered > c))


def sharpe_se(sharpe_annual: float, n_periods: int, periods_per_year: int) -> float:
    """Lo (2002) standard error of an annualized Sharpe ratio, serially uncorrelated returns."""
    sr_period = sharpe_annual / math.sqrt(periods_per_year)
    return math.sqrt(periods_per_year * (1 + 0.5 * sr_period ** 2) / n_periods)


_Z = np.linspace(-12.0, 12.0, 8001)
_PHI = norm.pdf(_Z)


def _max_cdf(x: float, n: int, rho: float) -> float:
    """P(max of n equicorrelated standard normals <= x), conditioning on the common factor."""
    u = (x - math.sqrt(rho) * _Z) / math.sqrt(1 - rho)
    return float(trapezoid(_PHI * np.exp(n * log_ndtr(u)), _Z))


def null_max_critical_value(n_specs: int, n_periods: int, periods_per_year: int, alpha: float,
                            rho: float = 0.0) -> float:
    """(1 - alpha) quantile of the largest of n_specs null Sharpe estimates with pairwise correlation rho."""
    se0 = sharpe_se(0.0, n_periods, periods_per_year)
    if n_specs == 1 or rho >= 1:
        z = float(ndtri(1 - alpha))
    elif rho <= 0:
        z = float(ndtri((1 - alpha) ** (1 / n_specs)))
    else:
        z = brentq(lambda x: _max_cdf(x, n_specs, rho) - (1 - alpha), -10.0, 20.0)
    return z * se0


def analytic_power(reference_sharpe: float, c: float, n_periods: int, periods_per_year: int) -> float:
    se = sharpe_se(reference_sharpe, n_periods, periods_per_year)
    return float(norm.sf((c - reference_sharpe) / se))


def required_sharpe(c: float, n_periods: int, periods_per_year: int, target_power: float = 0.80) -> float:
    """Smallest true Sharpe with analytic_power >= target_power against critical value c."""
    se0 = sharpe_se(0.0, n_periods, periods_per_year)
    f = lambda s: analytic_power(s, c, n_periods, periods_per_year) - target_power  # noqa: E731
    lo, hi = c - 10 * se0, c + 10 * se0
    while f(hi) < 0:
        hi += 10 * se0
    return brentq(f, lo, hi)
