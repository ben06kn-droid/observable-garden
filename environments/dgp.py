"""Synthetic data-generating process with a computable oracle.

Panel of M assets x T periods x K candidate features. Only s << K features
(the set S) carry true signal; the rest are pure noise correlated with the
signal features through Sigma_x, which is what makes search genuinely hard
rather than trivially solvable.

    x[i, k, t] ~ MVN(0, Sigma_x)                          (iid across i, t)
    r[i, t]    = sum_{k in S} beta_k * x[i, k, t] + eps[i, t]
    eps[i, t]  ~ N(0, sigma^2), optionally scaled Student-t for fat tails

The "t-1" lag in the proposal is a semantic label, not a mechanism: x is
drawn iid across time by construction, so there is nothing to actually lag.
x[:, :, t] denotes the features observed when period-t's return is decided.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np

CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "oracle"


@dataclass(frozen=True)
class DGPConfig:
    M: int = 200                # number of assets
    T: int = 2000                # in-sample periods
    T_oos: int = 1000            # out-of-sample periods
    K: int = 60                  # candidate features
    s: int = 3                   # true signal features, s << K
    rho: float = 0.0             # Sigma_x off-diagonal (equicorrelation)
    sigma: float = 1.0           # noise std
    beta: tuple[float, ...] | None = None   # per-signal-feature coefficients; default all-ones
    fat_tails: bool = False
    t_dof: float = 5.0           # Student-t degrees of freedom, if fat_tails
    periods_per_year: int = 252
    seed: int = 0
    heterogeneous: bool = False   # use heterogeneous_correlation instead of equicorrelation

    def beta_values(self) -> np.ndarray:
        if self.beta is not None:
            if len(self.beta) != self.s:
                raise ValueError(f"beta has {len(self.beta)} entries, expected s={self.s}")
            return np.array(self.beta, dtype=float)
        return np.ones(self.s, dtype=float)

    def cache_key(self) -> str:
        # Only fields that affect the oracle's distribution matter for caching;
        # T and T_oos do not (the oracle is a property of the generating process).
        relevant = {
            "M": self.M, "K": self.K, "s": self.s, "rho": self.rho,
            "sigma": self.sigma, "beta": list(self.beta_values()),
            "fat_tails": self.fat_tails, "t_dof": self.t_dof,
            "periods_per_year": self.periods_per_year,
            "heterogeneous": self.heterogeneous,
        }
        blob = json.dumps(relevant, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


@dataclass
class DGPData:
    x_in: np.ndarray    # (T, M, K)
    r_in: np.ndarray    # (T, M)
    x_oos: np.ndarray   # (T_oos, M, K)
    r_oos: np.ndarray   # (T_oos, M)
    S: np.ndarray        # (s,) indices into 0..K-1, the true signal set
    beta_full: np.ndarray  # (K,) zero outside S


def equicorrelation(K: int, rho: float) -> np.ndarray:
    """K x K correlation matrix: 1 on diagonal, rho off-diagonal."""
    if K > 1 and rho < -1.0 / (K - 1):
        raise ValueError(f"rho={rho} is not PSD-feasible for K={K} (min {-1.0/(K-1):.4f})")
    Sigma = np.full((K, K), rho, dtype=float)
    np.fill_diagonal(Sigma, 1.0)
    return Sigma


def heterogeneous_correlation(K: int, rho: float, seed: int) -> np.ndarray:
    """Single-factor correlation structure: Sigma = outer(l,l) with the
    diagonal reset to 1 (equivalently outer(l,l) + diag(1-l^2)) -- the
    K-vector of loadings l is drawn once per (K, rho, seed), not shared
    across features.

    Replaces equicorrelation's feature-exchangeability. That symmetry is
    harmless under s=0 (every null-calibration experiment in this project
    ran at rho=0.3 under equicorrelation and it cost nothing -- SCOPE.md
    §1). Under s>0 it isn't: every noise feature is equally (un)correlated
    with the true signal, so which wrong features a search lands on has no
    consequence, and the spread of achievable Sharpe across candidate
    specifications collapses -- exactly what made the first version of
    Experiment 2's target hard to predict for reasons having nothing to do
    with the estimator (SCOPE.md §8/§9).

    Loadings are centered near sqrt(rho) so the average pairwise
    correlation is still ~rho, keeping the existing knob's interpretation
    intact, with real heterogeneity around it. Automatically PSD by
    construction (rank-1 outer(l,l) plus a nonnegative diagonal) -- no
    feasibility check needed, unlike equicorrelation's negative-rho bound.
    rho<=0 returns the identity: "no correlation" has only one meaning,
    heterogeneous or not, and this keeps rho=0 a clean independent-features
    baseline."""
    if rho <= 0:
        return np.eye(K)
    rng = np.random.default_rng(seed + 500_009)  # decorrelated from true_signal_set's own draw
    center = np.sqrt(rho)
    loadings = np.clip(rng.uniform(center - 0.15, center + 0.15, size=K), 0.0, 0.97)
    Sigma = np.outer(loadings, loadings)
    np.fill_diagonal(Sigma, 1.0)
    return Sigma


def get_sigma_x(config: DGPConfig) -> np.ndarray:
    """The single call site every other function should use instead of
    calling equicorrelation directly -- switches structure via
    config.heterogeneous without touching any existing caller's behavior
    when it's left at its default False."""
    if config.heterogeneous:
        return heterogeneous_correlation(config.K, config.rho, config.seed)
    return equicorrelation(config.K, config.rho)


def true_signal_set(config: DGPConfig) -> tuple[np.ndarray, np.ndarray]:
    """Choose S (indices) and beta_full (K,), deterministic given config.seed."""
    rng = np.random.default_rng(config.seed)
    S = rng.choice(config.K, size=config.s, replace=False)
    S.sort()
    beta_full = np.zeros(config.K)
    beta_full[S] = config.beta_values()
    return S, beta_full


def signal_variance(config: DGPConfig, S: np.ndarray, beta_full: np.ndarray) -> float:
    """v_s = Var[sum_{k in S} beta_k x_k] = beta_S^T Sigma_x[S,S] beta_S."""
    Sigma_x = get_sigma_x(config)
    beta_S = beta_full[S]
    Sigma_SS = Sigma_x[np.ix_(S, S)]
    return float(beta_S @ Sigma_SS @ beta_S)


def _draw_noise(rng: np.random.Generator, shape: tuple[int, ...], config: DGPConfig) -> np.ndarray:
    if not config.fat_tails:
        return rng.normal(0.0, config.sigma, size=shape)
    if config.t_dof <= 2:
        raise ValueError("t_dof must be > 2 for finite variance")
    raw = rng.standard_t(config.t_dof, size=shape)
    scale = config.sigma * np.sqrt((config.t_dof - 2) / config.t_dof)
    return raw * scale


def _draw_features(rng: np.random.Generator, n: int, config: DGPConfig) -> np.ndarray:
    """(n, M, K) draw from MVN(0, Sigma_x), iid across period and asset."""
    Sigma_x = get_sigma_x(config)
    L = np.linalg.cholesky(Sigma_x)
    z = rng.standard_normal((n, config.M, config.K))
    return z @ L.T


def generate(config: DGPConfig) -> DGPData:
    """Draw a full in-sample + out-of-sample panel for one run of the DGP."""
    rng = np.random.default_rng(config.seed)
    S, beta_full = true_signal_set(config)

    x_in = _draw_features(rng, config.T, config)
    r_in = x_in @ beta_full + _draw_noise(rng, (config.T, config.M), config)

    x_oos = _draw_features(rng, config.T_oos, config)
    r_oos = x_oos @ beta_full + _draw_noise(rng, (config.T_oos, config.M), config)

    return DGPData(x_in=x_in, r_in=r_in, x_oos=x_oos, r_oos=r_oos, S=S, beta_full=beta_full)


# --------------------------------------------------------------------------
# The oracle: S and beta are known, so the optimal linear strategy is known
# by construction. Its portfolio return each period is the cross-sectional
# average R_t = (1/M) sum_i signal[i,t] * r[i,t], with signal = true beta_S
# on true x_S (no estimation error). This has a closed form:
#
#   let s_i = beta_S . x_S[i]  ~ N(0, v_s),  r_i = s_i + eps_i
#   R_t = mean_i(s_i * r_i) = mean_i(s_i^2 + s_i*eps_i)
#   E[R_t]   = v_s                              (exact, iid terms averaged)
#   Var[R_t] = (2*v_s^2 + v_s*sigma^2) / M       (exact for any M, s_i Gaussian)
#   SR_period  = sqrt(M) * sqrt(v_s / (2*v_s + sigma^2))
#   SR_annual  = SR_period * sqrt(periods_per_year)
#
# This holds for any independent, mean-zero, finite-variance eps (Gaussian or
# the scaled Student-t used for fat_tails) since only E[eps]=0, E[eps^2]=sigma^2
# and independence from s are used — s itself is exactly Gaussian because x_S
# is Gaussian regardless of what the other K-s noise features look like.
# --------------------------------------------------------------------------

def oracle_sharpe_analytic(config: DGPConfig) -> float:
    S, beta_full = true_signal_set(config)
    v_s = signal_variance(config, S, beta_full)
    sr_period = np.sqrt(config.M * v_s / (2 * v_s + config.sigma ** 2))
    return float(sr_period * np.sqrt(config.periods_per_year))


def analytic_sharpe(config: DGPConfig, weights: np.ndarray) -> float:
    """Population (T -> infinity) Sharpe of an ARBITRARY linear
    specification with weight vector `weights` -- generalizes
    oracle_sharpe_analytic (the special case weights == the true
    beta_full) to any candidate a searcher might submit. This is the
    T_oos -> infinity limit of what Sandbox.oos_sharpe_for_grading
    estimates from a finite T_oos-period sample: scoring against it
    instead removes OOS measurement noise entirely, so RMSE against it
    measures only the deflation estimator's own accuracy, not a mix of
    that and finite-sample noise in the target itself.

    Same algebra as the oracle derivation above, generalized: with
    s_i = weights . x_S[i] and c_i = beta . x_S[i] jointly Gaussian,

        s_gs = w^T Sigma_x beta   (Cov(s_i, c_i))
        v_g  = w^T Sigma_x w      (Var(s_i), the candidate's own signal variance)
        v_s  = beta^T Sigma_x beta (Var(c_i), the true signal variance)
        Var[R] = (v_g*v_s + s_gs^2 + v_g*sigma^2) / M
        SR = s_gs / sqrt(Var[R]) * sqrt(periods_per_year)

    Reduces exactly to oracle_sharpe_analytic when weights == beta_full
    (v_g = v_s = s_gs, giving Var[R] = (2 v_s^2 + v_s sigma^2) / M, the
    original formula) -- checked as a test, not just asserted. Verified
    against simulation for oracle / partial-true / pure-noise weight
    vectors (tests/test_analytic_sharpe.py)."""
    beta_full = true_signal_set(config)[1]
    Sigma_x = get_sigma_x(config)
    weights = np.asarray(weights, dtype=float)

    v_s = float(beta_full @ Sigma_x @ beta_full)
    v_g = float(weights @ Sigma_x @ weights)
    s_gs = float(weights @ Sigma_x @ beta_full)

    var_R = (v_g * v_s + s_gs ** 2 + v_g * config.sigma ** 2) / config.M
    if var_R <= 0:
        return 0.0
    sr_period = s_gs / np.sqrt(var_R)
    return float(sr_period * np.sqrt(config.periods_per_year))


def calibrate_sigma(target_annual_sharpe: float, config: DGPConfig) -> float:
    """Solve for sigma such that oracle_sharpe_analytic(config) == target, holding
    M, K, s, rho, beta fixed. Returns the required sigma; raises if infeasible."""
    S, beta_full = true_signal_set(config)
    v_s = signal_variance(config, S, beta_full)
    sr_period = target_annual_sharpe / np.sqrt(config.periods_per_year)
    sigma_sq = config.M * v_s / sr_period ** 2 - 2 * v_s
    if sigma_sq <= 0:
        raise ValueError(
            f"target_annual_sharpe={target_annual_sharpe} is infeasible for "
            f"M={config.M}, v_s={v_s:.4g} (implied sigma^2={sigma_sq:.4g} <= 0); "
            "increase M or v_s, or lower the target."
        )
    return float(np.sqrt(sigma_sq))


def oracle_sharpe_simulated(
    config: DGPConfig,
    T_sim: int = 1_000_000,
    chunk: int = 50_000,
    use_cache: bool = True,
) -> float:
    """Monte Carlo estimate of the oracle's annualized Sharpe, simulating only
    the s signal features (the K-s noise features provably do not enter r, so
    they are irrelevant to the oracle and skipped for tractability). Cached to
    disk per config since this is meant to run once per configuration."""
    cache_path = CACHE_DIR / f"{config.cache_key()}_{T_sim}.json"
    if use_cache and cache_path.exists():
        return float(json.loads(cache_path.read_text())["sharpe_annual"])

    S, beta_full = true_signal_set(config)
    beta_S = beta_full[S]
    Sigma_x = get_sigma_x(config)
    Sigma_SS = Sigma_x[np.ix_(S, S)]
    L = np.linalg.cholesky(Sigma_SS)

    rng = np.random.default_rng(config.seed + 1_000_003)  # decorrelated from generate()
    total, total_sq, n = 0.0, 0.0, 0
    remaining = T_sim
    while remaining > 0:
        b = min(chunk, remaining)
        z = rng.standard_normal((b, config.M, config.s))
        x_S = z @ L.T
        signal = x_S @ beta_S                       # (b, M)
        eps = _draw_noise(rng, (b, config.M), config)
        r = signal + eps
        R_t = (signal * r).mean(axis=1)              # (b,)
        total += R_t.sum()
        total_sq += (R_t ** 2).sum()
        n += b
        remaining -= b

    mean = total / n
    var = total_sq / n - mean ** 2
    sr_period = mean / np.sqrt(var)
    sharpe_annual = float(sr_period * np.sqrt(config.periods_per_year))

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"sharpe_annual": sharpe_annual, "T_sim": T_sim}))
    return sharpe_annual
