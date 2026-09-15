"""Written and run BEFORE any RMSE is looked at, per spec §8's own warning
against tuning the DGP until the estimator looks good. The criterion,
stated first:

    Var_across_draws[SR_true(submitted spec)] must exceed the measurement
    noise a finite-T_oos realized Sharpe would carry.

Checkable from Sigma_x, beta, sigma, and T_oos alone, with no estimator
involved: the measurement-noise floor is Lo (2002)'s closed-form standard
error for a sample Sharpe ratio, SE[SR_hat_period] ~ sqrt(1+SR_period^2/2)/
T_oos, annualized by scaling by sqrt(periods_per_year) (an early sanity
check that skipped this scaling produced a spurious factor-of-~16 error --
corrected before this file was written). At T_oos=300, periods_per_year=
252, this floor is essentially sqrt(252/300) ~ 0.917, matching what the
original Experiment 2 grid was fighting regardless of which deflation
method was used.

The target's own variance -- Var_across_draws[SR_true] -- is computed with
analytic_sharpe (environments/dgp.py), itself estimator-free: it's a closed
-form population quantity, not a simulated or estimated one.

Run this, look at the numbers, THEN decide whether to rerun Experiment 2.
Not the other way around -- that ordering is what makes the DGP change
defensible rather than "the numbers looked bad so I changed the DGP."

Usage: python -m experiments.e8_dgp_criterion_check
"""
from __future__ import annotations

import numpy as np

from environments.dgp import DGPConfig, analytic_sharpe, calibrate_sigma
from environments.sandbox import Sandbox
from searchers.scripted import GridSearch

N_LEVELS = [10, 100, 1000]
RHO_LEVELS = [0.0, 0.3, 0.6, 0.9]
K = 40
M, T, T_OOS = 60, 600, 300
TARGET_ORACLE_SHARPE = 1.0
PERIODS_PER_YEAR = 252


def measurement_noise_floor(T_oos: int, periods_per_year: int = PERIODS_PER_YEAR) -> float:
    """Lo (2002) sample-Sharpe SE, annualized. SR_period's own contribution
    (+SR_period^2/2) is negligible here (SR_period ~ 0.06) and dropped for
    the headline number, kept in the precise version below."""
    return float(np.sqrt(periods_per_year / T_oos))


def build_config(rho: float, seed: int, heterogeneous: bool) -> DGPConfig:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=1.0, seed=seed, heterogeneous=heterogeneous)
    sigma = calibrate_sigma(TARGET_ORACLE_SHARPE, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=sigma, seed=seed, heterogeneous=heterogeneous)


def target_sd(n_draws: int, N: int, rho: float, heterogeneous: bool, seed0: int) -> float:
    """SD, across n_draws independent draws, of the TRUE (analytic, no
    measurement noise) Sharpe of whatever GridSearch(max_trials=N) submits.
    No bootstrap, no OOS realization -- cheap."""
    sr_true = []
    for i in range(n_draws):
        config = build_config(rho, seed0 + i, heterogeneous)
        from environments.dgp import generate
        data = generate(config)
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        GridSearch(subset_sizes=(1, 2, 3), max_trials=N, seed=seed0 + i).run(sandbox)
        spec, _ = sandbox.submission
        sr_true.append(analytic_sharpe(config, spec.weights))
    return float(np.std(sr_true, ddof=1))


if __name__ == "__main__":
    noise_floor = measurement_noise_floor(T_OOS)
    print(f"Measurement noise floor (Lo 2002, T_oos={T_OOS}, ppy={PERIODS_PER_YEAR}): {noise_floor:.3f}\n")

    print(f"{'structure':<14} {'N':>6} {'rho':>5} {'target SD':>10}  vs noise floor")
    for label, het in [("equicorrelation", False), ("heterogeneous", True)]:
        for rho in RHO_LEVELS:
            for N in N_LEVELS:
                sd = target_sd(n_draws=30, N=N, rho=rho, heterogeneous=het, seed0=900_000)
                verdict = "PASS (signal > noise)" if sd > noise_floor else "FAIL (noise dominates)"
                print(f"{label:<14} {N:>6} {rho:>5.1f} {sd:>10.4f}  {verdict}")
