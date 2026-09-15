"""Experiment 2, rerun with both fixes from the criterion check
(experiments/e8_dgp_criterion_check.py), which ran and was read BEFORE this
file changed anything about which method wins:

1. Score against analytic_sharpe (environments/dgp.py) instead of a
   300-period OOS realization. Removes the ~0.917 measurement-noise floor
   entirely -- confirmed necessary, not optional: even heterogeneous Sigma_x
   left target SD 0.005-0.21 against that floor, nowhere close.
2. heterogeneous=True Sigma_x instead of equicorrelation. A smaller,
   rho-dependent fix on top -- matters most at high rho (target SD 2-4x
   higher than equicorrelation there), where equicorrelation's feature-
   exchangeability collapses the spread of achievable specifications most.

experiments/e7_predictive_power.py (the original, equicorrelation +
realized-OOS version) is kept as-is, not deleted -- the project's own
standard is to log every configuration run, including the ones that didn't
work, not just the final one.

Same grid as before for comparability: N in {10,100,1000} x rho in
{0,0.3,0.6,0.9}, K=40, s=3, sigma calibrated per rho to a fixed oracle
ceiling, GridSearch as the trial-budget knob. Reports RMSE/R2 as before,
plus BIAS (mean(predicted - realized decay)) per predictor -- the more
informative statistic once the target itself is exact: does each method
systematically over- or under-deflate, and does that bias track N or rho.

Usage: python -m experiments.e9_predictive_power_v2
"""
from __future__ import annotations

import argparse
import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, analytic_sharpe, calibrate_sigma, generate, oracle_sharpe_analytic
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from estimator.deflated_sharpe import deflate_closed_form
from estimator.metrics import rmse, r_squared
from searchers.scripted import GridSearch

N_LEVELS = [10, 100, 1000]
RHO_LEVELS = [0.0, 0.3, 0.6, 0.9]
K = 40
M, T, T_OOS = 60, 600, 300
TARGET_ORACLE_SHARPE = 1.0


def build_config(rho: float, seed: int) -> DGPConfig:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=1.0, seed=seed, heterogeneous=True)
    sigma = calibrate_sigma(TARGET_ORACLE_SHARPE, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=sigma, seed=seed, heterogeneous=True)


def run_cell(n_draws: int, N: int, rho: float, B: int, seed0: int):
    out = {k: [] for k in ["sr_is", "sr_oos_true", "sr_oracle", "sr_deflated_boot",
                            "sr_deflated_raw", "sr_deflated_eff", "p_value"]}
    for i in range(n_draws):
        config = build_config(rho, seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)

        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher = GridSearch(subset_sizes=(1, 2, 3), max_trials=N, seed=seed0 + i)
        searcher.run(sandbox)
        spec, dist = sandbox.submission
        R = sandbox.returns_matrix()

        sr_is = dist.mean
        sr_oos_true = analytic_sharpe(config, spec.weights)   # exact, no measurement noise
        sr_oracle = oracle_sharpe_analytic(config)

        boot = deflate(R, sr_sel=sr_is, B=B, annualization=ann, seed=seed0 + i)
        dsr_raw = deflate_closed_form(R, sr_sel=sr_is, annualization=ann, N_mode="raw")
        dsr_eff = deflate_closed_form(R, sr_sel=sr_is, annualization=ann, N_mode="effective")

        out["sr_is"].append(sr_is)
        out["sr_oos_true"].append(sr_oos_true)
        out["sr_oracle"].append(sr_oracle)
        out["sr_deflated_boot"].append(boot.sr_deflated)
        out["sr_deflated_raw"].append(dsr_raw.sr_deflated)
        out["sr_deflated_eff"].append(dsr_eff.sr_deflated)
        out["p_value"].append(boot.p_value)

    return {k: np.array(v) for k, v in out.items()}


def run(n_draws=100, B=1500, seed0=700_000, verbose=True):
    results = {}
    t0 = time.time()
    for rho in RHO_LEVELS:
        for N in N_LEVELS:
            cell = run_cell(n_draws, N, rho, B, seed0)
            results[(N, rho)] = cell
            if verbose:
                print(f"  N={N:<5} rho={rho:<4} done  ({time.time()-t0:.1f}s elapsed)")
    return results


def report(results):
    actual_key = "sr_oos_true"
    print(f"\n{'N':>6} {'rho':>5} {'RMSE(IS)':>10} {'RMSE(raw)':>10} {'RMSE(eff)':>10} {'RMSE(boot)':>11} | "
          f"{'R2(IS)':>8} {'R2(raw)':>8} {'R2(eff)':>8} {'R2(boot)':>9}")
    for (N, rho), cell in results.items():
        actual = cell[actual_key]
        row = []
        for pred_key in ["sr_is", "sr_deflated_raw", "sr_deflated_eff", "sr_deflated_boot"]:
            row.append((rmse(cell[pred_key], actual), r_squared(cell[pred_key], actual)))
        print(f"{N:>6} {rho:>5.1f} " + " ".join(f"{r[0]:>10.4f}" for r in row) + " | " +
              " ".join(f"{r[1]:>8.3f}" for r in row))

    print("\n-- bias: mean(predicted decay - realized decay), signed -- positive = under-deflates --")
    print(f"{'N':>6} {'rho':>5} {'bias(raw)':>11} {'bias(eff)':>11} {'bias(boot)':>12}")
    for (N, rho), cell in results.items():
        realized_decay = cell["sr_is"] - cell[actual_key]
        bias_raw = (cell["sr_is"] - cell["sr_deflated_raw"] - realized_decay).mean()
        bias_eff = (cell["sr_is"] - cell["sr_deflated_eff"] - realized_decay).mean()
        bias_boot = (cell["sr_is"] - cell["sr_deflated_boot"] - realized_decay).mean()
        print(f"{N:>6} {rho:>5.1f} {bias_raw:>11.4f} {bias_eff:>11.4f} {bias_boot:>12.4f}")

    print("\n-- rho=0 consistency check: bootstrap vs closed-form(raw) should agree --")
    for N in N_LEVELS:
        cell = results[(N, 0.0)]
        diff = cell["sr_deflated_boot"] - cell["sr_deflated_raw"]
        print(f"N={N:<5} mean(boot-closedform) = {diff.mean():+.4f} (SD {diff.std(ddof=1):.4f})")

    print("\n-- target spread check (should now be well above the old 0.917 noise floor) --")
    for (N, rho), cell in results.items():
        print(f"N={N:<6} rho={rho:<4} SD(sr_oos_true) = {cell[actual_key].std(ddof=1):.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=100)
    parser.add_argument("--B", type=int, default=1500)
    args = parser.parse_args()

    results = run(n_draws=args.n_draws, B=args.B)
    report(results)
    with open("figures/e9_predictive_power_v2_data.pkl", "wb") as f:
        pickle.dump(results, f)
