"""Hansen's (2005) test for superior predictive ability: the higher-power
successor to the Reality Check, and the structural answer to the degeneracy
refusal of SCOPE.md §11.

Two things separate SPA from `estimator/bootstrap.py`'s realized-menu null.

**Fixed studentization.** The statistic is studentized by a long-run standard
deviation estimated once from the full sample and held constant across every
replicate. The Reality Check implementation here re-estimates the Sharpe
denominator inside each resample, which is why a menu holding rules that
rarely trade can drive it to zero and make the critical value measure
near-empty resamples (SCOPE.md §11, verdict DEGENERATE). A denominator that
never moves cannot collapse. This is the statistic `garden/audit.py`'s
DEGENERATE_ROUTES and `garden/explain.py` both describe as "Sharpe
studentized by the full-sample standard deviation", and which the gate has
until now said it does not offer.

**Selective recentering.** White recenters every candidate at its own sample
mean, so candidates with no hope of beating the benchmark still push the
resampled maximum up and cost the test power. Hansen recenters only those not
too far below the benchmark. This is the check SCOPE.md §6 asks for: whether
the power collapse of §10 is a property of the problem or of the Reality
Check's conservatism.

Specification, from the published text (JBES 23(4), §2.2-§3.1):

    T_n = max[ max_k sqrt(n) * dbar_k / omega_hat_k , 0 ]

with the bootstrap statistic, for a recentering rule g,

    Z*_{b,k} = sqrt(n) * ( dbar*_{b,k} - g(dbar_k) ) / omega_hat_k
    T*_b     = max[ max_k Z*_{b,k} , 0 ]
    p_hat    = (1/B) * sum_b 1{ T*_b > T_n }

Hansen's three recentering rules, which bracket the p-value:

    g_u(x) = x                                         (upper; mu_k = 0 for all k)
    g_c(x) = x * 1{ x >= -sqrt((omega_hat_k^2/n) * 2 log log n) }   (consistent)
    g_l(x) = max(0, x)                                 (lower; mu_k = min(dbar_k, 0))

`g_u` imposes the least favourable configuration and is exactly White's
Reality Check, so `p_upper` is this module's cross-check against
`estimator/bootstrap.py` rather than a separate claim. Hansen recommends
reporting the bracket `p_lower <= p_consistent <= p_upper`, and `spa_test`
returns all three from one set of bootstrap draws.

The long-run variance uses Hansen's kernel, matched to the stationary
bootstrap's restart probability `q = 1/L`:

    omega_hat_k^2 = gamma_0k + 2 * sum_{i=1}^{n-1} kappa(n,i) * gamma_ik
    kappa(n,i)    = ((n-i)/n) * (1-q)^i + (i/n) * (1-q)^(n-i)

`L` comes from the same `select_block_length` the rest of the estimator uses,
so SPA and the Reality Check resample the identical dependence structure and
any difference between them is the recentering, not the block length.

Scope: this tests a menu against a zero benchmark (cash), which is the
comparison the transcripts here carry. A non-zero benchmark is a matter of
passing `R` already differenced against it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_index_matrix

RECENTERINGS = ("lower", "consistent", "upper")


def hansen_kappa(n: int, q: float) -> np.ndarray:
    """kappa(n,i) for i = 1..n-1: the weight Hansen puts on the i-th sample
    autocovariance, implied by the stationary bootstrap with restart
    probability q. The first term decays geometrically in the lag; the second
    is the wrap-around contribution, negligible except at lags near n."""
    i = np.arange(1, n)
    return ((n - i) / n) * (1 - q) ** i + (i / n) * (1 - q) ** (n - i)


def long_run_variance(D: np.ndarray, q: float) -> np.ndarray:
    """(N,) Hansen long-run variances, one per column, via FFT autocovariances.

    gamma_ik = (1/n) sum_t (d_tk - dbar_k)(d_{t+i,k} - dbar_k), all lags at
    once: the autocovariance sequence is the inverse transform of the power
    spectrum of the centred series, zero-padded to avoid circular wrap."""
    D = np.asarray(D, dtype=float)
    n = D.shape[0]
    centred = D - D.mean(axis=0, keepdims=True)
    size = int(2 ** np.ceil(np.log2(2 * n)))
    spectrum = np.fft.rfft(centred, n=size, axis=0)
    acov = np.fft.irfft(spectrum * np.conj(spectrum), n=size, axis=0)[:n] / n
    weights = hansen_kappa(n, q)
    omega2 = acov[0] + 2.0 * (weights[:, None] * acov[1:]).sum(axis=0)
    return omega2


@dataclass
class SPAResult:
    """p_lower <= p_consistent <= p_upper is Hansen's reported bracket.
    `p_upper` is the least-favourable-configuration case, i.e. White's
    Reality Check computed on this studentized statistic."""
    statistic: float
    p_lower: float
    p_consistent: float
    p_upper: float
    omega: np.ndarray          # (N,) fixed full-sample long-run std devs
    t_stats: np.ndarray        # (N,) sqrt(n) * dbar_k / omega_k
    block_length: int
    B: int
    N: int
    n_recentered: int          # candidates the consistent rule left recentered

    @property
    def p_value(self) -> float:
        """The one to quote: Hansen's consistent rule."""
        return self.p_consistent


def spa_test(
    R: np.ndarray,
    B: int = 10_000,
    block_length: int | None = None,
    seed: int | None = None,
    variance_floor: float = 1e-12,
) -> SPAResult:
    """Hansen's SPA on an (T, N) matrix of per-period returns, one column per
    evaluated specification, against a zero benchmark.

    Columns whose long-run variance is at or below `variance_floor` carry no
    signal to test and are dropped from the maximum rather than dividing by
    something near zero. Unlike the Reality Check's per-replicate guards
    (`estimator.bootstrap.GUARD_COUNTS`), this is a property of the full
    sample only, so it cannot vary between replicates and cannot move a
    critical value."""
    R = np.asarray(R, dtype=float)
    if R.ndim != 2:
        raise ValueError("R must be (T, N)")
    n, N = R.shape
    if N == 0:
        raise ValueError("R has no columns to test")
    if n < 3:
        raise ValueError("SPA needs at least 3 periods for a long-run variance")

    L = block_length if block_length is not None else select_block_length(R)
    q = 1.0 / max(L, 1)

    dbar = R.mean(axis=0)
    omega2 = long_run_variance(R, q)
    live = omega2 > variance_floor
    if not live.any():
        raise ValueError("every column has zero long-run variance; nothing to test")
    omega = np.sqrt(np.where(live, omega2, 1.0))

    root_n = np.sqrt(n)
    t_stats = np.where(live, root_n * dbar / omega, -np.inf)
    statistic = float(max(t_stats.max(), 0.0))

    # Hansen's three recentering rules, as the quantity subtracted from dbar*.
    threshold = -np.sqrt((omega2 / n) * 2.0 * np.log(np.log(n))) if n >= 3 else np.zeros(N)
    subtract = {
        "upper": dbar,
        "consistent": np.where(dbar >= threshold, dbar, 0.0),
        "lower": np.maximum(dbar, 0.0),
    }
    n_recentered = int(np.sum((dbar >= threshold) & live))

    rng = np.random.default_rng(seed)
    exceed = {key: 0 for key in RECENTERINGS}
    # R[idx, :] materializes (chunk, n, N), so the cap has to count columns too:
    # a wide menu (N ~ 10,000 at E21's K=40) would otherwise ask for hundreds of GB.
    chunk = max(1, min(B, int(2e7 // max(n * N, 1))))
    drawn = 0
    while drawn < B:
        size = min(chunk, B - drawn)
        idx = stationary_bootstrap_index_matrix(n, L, size, rng)
        # (size, N) bootstrap column means, one shared time index per replicate
        # so the cross-sectional correlation between candidates is preserved.
        dbar_star = R[idx, :].mean(axis=1)
        for key in RECENTERINGS:
            z = root_n * (dbar_star - subtract[key]) / omega
            z[:, ~live] = -np.inf
            t_star = np.maximum(z.max(axis=1), 0.0)
            exceed[key] += int(np.sum(t_star > statistic))
        drawn += size

    return SPAResult(
        statistic=statistic,
        p_lower=exceed["lower"] / B,
        p_consistent=exceed["consistent"] / B,
        p_upper=exceed["upper"] / B,
        omega=omega,
        t_stats=t_stats,
        block_length=L,
        B=B,
        N=N,
        n_recentered=n_recentered,
    )
