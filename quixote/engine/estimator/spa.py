"""Hansen's (2005) test for superior predictive ability: the higher-power
successor to the Reality Check, and the structural answer to the degeneracy
refusal of SCOPE.md, Sparse strategies.

Two things separate SPA from `estimator/bootstrap.py`'s realized-menu null.

**Fixed studentization.** The statistic is studentized by a long-run standard
deviation estimated once from the full sample and held constant across every
replicate. The Reality Check implementation here re-estimates the Sharpe
denominator inside each resample, which is why a menu holding rules that
rarely trade can drive it to zero and make the critical value measure
near-empty resamples (SCOPE.md, Sparse strategies, verdict DEGENERATE). A denominator that
never moves cannot collapse. This is the statistic `garden/audit.py`'s
DEGENERATE_ROUTES and `garden/explain.py` both describe as "Sharpe
studentized by the full-sample standard deviation", and which the gate has
until now said it does not offer.

**Selective recentering.** White recenters every candidate at its own sample
mean, so candidates with no hope of beating the benchmark still push the
resampled maximum up and cost the test power. Hansen recenters a candidate
far below the benchmark at *zero* instead of at its own mean.

That is not a discarding rule, and Hansen is explicit about the
misreading: an earlier version of the paper "has been incorrectly quoted for
'discarding the poor models'". The candidate stays in the maximum; only its
recentering changes. Nor is `sqrt(2 log log n)` the only admissible rate —
Hansen notes others (e.g. `n^(1/4)/4`) work equally well. Wording that says
SPA "excludes" candidates is the error to avoid.

This is the check SCOPE.md, Prior art asks for: whether the power collapse
reported under Effective breadth is a property of the problem or of the
Reality Check's conservatism.

Specification, from the published text (JBES 23(4), §2.2-§3.1):

    T_n = max[ max_k sqrt(n) * dbar_k / omega_hat_k , 0 ]

with the bootstrap statistic, for a recentering rule g,

    Z*_{b,k} = sqrt(n) * ( dbar*_{b,k} - g(dbar_k) ) / omega_hat_k
    T*_b     = max[ max_k Z*_{b,k} , 0 ]
    p_hat    = (1/B) * sum_b 1{ T*_b > T_n }

Hansen's three recentering rules, which bracket the p-value:

    g_u(x) = x                                         (upper; mu_k = 0 for all k)
    g_c(x) = x * 1{ sqrt(n) x / omega_hat_k >= -sqrt(2 log log n) }  (consistent)
    g_l(x) = max(0, x)                                 (lower; mu_k = min(dbar_k, 0))

Hansen writes g_c twice, studentized in §2.1 and raw in §3.1
(`x >= -sqrt((omega_hat_k^2/n) 2 log log n)`); the forms are algebraically
identical and `consistent_keep_mask` implements both so a test can pin them
together.

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

import math
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


def consistent_keep_mask(dbar: np.ndarray, omega: np.ndarray, n: int,
                         form: str = "studentized") -> np.ndarray:
    """Hansen's consistent rule: True where a candidate keeps its own mean as
    the recentering, False where it is recentered at zero instead.

    The paper states the same rule twice, and the two parameterisations are
    algebraically identical (divide through by omega_k / sqrt(n)):

        studentized  (§2.1)   sqrt(n) * dbar_k / omega_k >= -sqrt(2 log log n)
        raw          (§3.1)   dbar_k                     >= -sqrt((omega_k^2/n) 2 log log n)

    The studentized form is the primary one here because it keeps the
    threshold a pure constant, so a scaling slip in omega cannot quietly move
    it. `tests/test_spa.py` asserts the two agree, which is the cheap guard
    against getting that scaling wrong."""
    if form == "studentized":
        return np.sqrt(n) * dbar / omega >= -np.sqrt(2.0 * np.log(np.log(n)))
    if form == "raw":
        return dbar >= -np.sqrt((omega ** 2 / n) * 2.0 * np.log(np.log(n)))
    raise ValueError(f"form must be 'studentized' or 'raw', got {form!r}")


@dataclass
class SPAResult:
    """p_lower <= p_consistent <= p_upper is Hansen's reported bracket.
    `p_upper` is the least-favourable-configuration case, i.e. White's
    Reality Check computed on this studentized statistic.

    Each p-value has a matching critical value built from the same float
    expression, so `p <= alpha` and `statistic > critical` can never disagree
    at the boundary (garden/power.py's guarantee, carried over)."""
    statistic: float
    p_lower: float
    p_consistent: float
    p_upper: float
    critical_lower: float
    critical_consistent: float
    critical_upper: float
    alpha: float
    omega: np.ndarray          # (N,) fixed full-sample long-run std devs
    t_stats: np.ndarray        # (N,) sqrt(n) * dbar_k / omega_k
    block_length: int
    B: int
    N: int
    n_recentered: int          # candidates the consistent rule left recentered
    submitted: int | None      # index tested, or None when testing the menu's best

    @property
    def p_value(self) -> float:
        """The one to quote: Hansen's consistent rule."""
        return self.p_consistent

    @property
    def critical(self) -> float:
        """Critical value matching `p_value`."""
        return self.critical_consistent

    @property
    def rejects(self) -> bool:
        return self.statistic > self.critical_consistent


def _p_value(null: np.ndarray, stat: float) -> float:
    """garden.power.bootstrap_p_value, inlined.

    `estimator` is imported by `garden`, not the reverse, so importing it here
    would invert the dependency. The expression is kept character-identical
    instead, and tests/test_spa.py asserts agreement against garden.power so
    any future drift fails loudly rather than silently."""
    return float((1 + np.sum(null >= stat)) / (len(null) + 1))


def _critical_value(null: np.ndarray, alpha: float) -> float:
    """garden.power.critical_value, inlined (see `_p_value`). Same float
    expression as `_p_value`, so the two cannot disagree at the boundary.
    inf when B is too small for any result to reject."""
    null = np.asarray(null, dtype=float)
    B = len(null)
    k = int(np.sum((1 + np.arange(B + 1)) / (B + 1) < alpha)) - 1
    if k < 0:
        return math.inf
    return float(np.sort(null)[B - 1 - k])


def spa_test(
    R: np.ndarray,
    B: int = 10_000,
    block_length: int | None = None,
    seed: int | None = None,
    variance_floor: float = 1e-12,
    submitted: int | None = None,
    alpha: float = 0.05,
) -> SPAResult:
    """Hansen's SPA on an (T, N) matrix of per-period returns, one column per
    evaluated specification, against a zero benchmark.

    `submitted`: index of the specification actually submitted. The statistic
    becomes that column's studentized mean rather than the menu's best, while
    the null stays the maximum over the whole menu -- so the multiplicity
    correction is unchanged and a sub-maximal submission is judged against the
    same bar. Omit it to test the menu's best, which is Hansen's own framing.
    Testing a sub-maximal submission is necessarily conservative: the statistic
    falls, the null does not move.

    `block_length`: taken from the caller so the gate can share one block
    length across the Reality Check and SPA. Computed from the demeaned matrix
    when omitted, matching every other call site in the repo.

    Columns whose long-run variance is at or below `variance_floor` carry no
    signal to test and are dropped from the maximum rather than dividing by
    something near zero. Unlike the Reality Check's per-replicate guards
    (`estimator.bootstrap.GUARD_COUNTS`), this is a property of the full
    sample only, so it cannot vary between replicates and cannot move a
    critical value.

    One deliberate deviation from the paper: Hansen counts bootstrap
    exceedances strictly (`T* > T`), while the gate counts them inclusively
    and adds one to each side, `(1 + #{T* >= T}) / (B + 1)`. The gate's
    convention is the more conservative of the two and is used here so SPA's
    p-values are comparable with the Reality Check's without adjustment."""
    R = np.asarray(R, dtype=float)
    if R.ndim != 2:
        raise ValueError("R must be (T, N)")
    n, N = R.shape
    if N == 0:
        raise ValueError("R has no columns to test")
    if n < 3:
        raise ValueError("SPA needs at least 3 periods for a long-run variance")

    if submitted is not None and not 0 <= submitted < R.shape[1]:
        raise ValueError(f"submitted index {submitted} out of range for {R.shape[1]} columns")

    # Demeaned, matching garden/audit.py and every experiment call site.
    L = block_length if block_length is not None else select_block_length(R - R.mean(axis=0))
    q = 1.0 / max(L, 1)

    dbar = R.mean(axis=0)
    omega2 = long_run_variance(R, q)
    live = omega2 > variance_floor
    if not live.any():
        raise ValueError("every column has zero long-run variance; nothing to test")
    omega = np.sqrt(np.where(live, omega2, 1.0))

    root_n = np.sqrt(n)
    t_stats = np.where(live, root_n * dbar / omega, -np.inf)
    if submitted is None:
        statistic = float(max(t_stats.max(), 0.0))
    else:
        if not live[submitted]:
            raise ValueError(f"submitted column {submitted} has zero long-run variance")
        # The null below is still the maximum over the whole menu, so the
        # multiplicity correction is identical; only the bar being cleared moves.
        statistic = float(max(t_stats[submitted], 0.0))

    # Hansen's three recentering rules, as the quantity subtracted from dbar*.
    keep = consistent_keep_mask(dbar, omega, n)
    subtract = {
        "upper": dbar,
        "consistent": np.where(keep, dbar, 0.0),
        "lower": np.maximum(dbar, 0.0),
    }
    n_recentered = int(np.sum(keep & live))

    rng = np.random.default_rng(seed)
    # Retained rather than counted: a critical value needs the draws themselves.
    # Three float64 arrays of length B (240 KB at B=10,000).
    nulls = {key: np.empty(B) for key in RECENTERINGS}
    # R[idx, :] materializes (chunk, n, N), so the cap has to count columns too:
    # a wide menu (N ~ 10,000 at oblivious-calibration's K=40) would otherwise ask for hundreds of GB.
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
            nulls[key][drawn:drawn + size] = np.maximum(z.max(axis=1), 0.0)
        drawn += size

    return SPAResult(
        statistic=statistic,
        p_lower=_p_value(nulls["lower"], statistic),
        p_consistent=_p_value(nulls["consistent"], statistic),
        p_upper=_p_value(nulls["upper"], statistic),
        critical_lower=_critical_value(nulls["lower"], alpha),
        critical_consistent=_critical_value(nulls["consistent"], alpha),
        critical_upper=_critical_value(nulls["upper"], alpha),
        alpha=alpha,
        omega=omega,
        t_stats=t_stats,
        block_length=L,
        B=B,
        N=N,
        n_recentered=n_recentered,
        submitted=submitted,
    )
