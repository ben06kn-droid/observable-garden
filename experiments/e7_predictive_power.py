"""Experiment 2 (spec §4.2, predictive power under the alternative) with
the correlation sweep (spec §4.4) folded in rather than deferred -- rho has
never been varied in this repo (every prior experiment ran at rho=0.3), the
obliviousness claim in SCOPE.md §1 is stated generally while tested at one
rho, and rho=0 gives a free consistency check: bootstrap deflation and
closed-form DSR should agree there (spec §4.4), which hasn't been run yet.

Also includes spec §4.3's scaling axis (trial budget N) using GridSearch's
max_trials as the clean parametric knob, matching the precondition check in
experiments/e6_pilot_signal_landscape.py, which confirmed this DGP is not
unimodal at s=3 before this (much more expensive) sweep was run.

Grid: N in {10, 100, 1000} x rho in {0.0, 0.3, 0.6, 0.9}, s=3, sigma
calibrated per rho so the ORACLE ceiling stays fixed at a target Sharpe
across the whole grid (isolating rho's effect on the SEARCH's approach to
that fixed ceiling, not confounding it with a shifting ceiling).

Four predictors of SR_OOS, per spec's comparison table: SR_IS (naive),
closed-form DSR with raw N, closed-form DSR with effective N (eigenvalue-
based), and bootstrap deflation.

Usage: python -m experiments.e7_predictive_power
"""
from __future__ import annotations

import argparse
import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, calibrate_sigma, generate, oracle_sharpe_analytic
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
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=1.0, seed=seed)
    sigma = calibrate_sigma(TARGET_ORACLE_SHARPE, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=rho, sigma=sigma, seed=seed)


def run_cell(n_draws: int, N: int, rho: float, B: int, seed0: int):
    """One (N, rho) grid cell: n_draws independent s=3 draws, one GridSearch
    run each at max_trials=N. Returns a dict of arrays."""
    out = {k: [] for k in ["sr_is", "sr_oos", "sr_oracle", "sr_deflated_boot",
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
        sr_oos = sandbox.oos_sharpe_for_grading(spec)
        sr_oracle = oracle_sharpe_analytic(config)

        boot = deflate(R, sr_sel=sr_is, B=B, annualization=ann, seed=seed0 + i)
        dsr_raw = deflate_closed_form(R, sr_sel=sr_is, annualization=ann, N_mode="raw")
        dsr_eff = deflate_closed_form(R, sr_sel=sr_is, annualization=ann, N_mode="effective")

        out["sr_is"].append(sr_is)
        out["sr_oos"].append(sr_oos)
        out["sr_oracle"].append(sr_oracle)
        out["sr_deflated_boot"].append(boot.sr_deflated)
        out["sr_deflated_raw"].append(dsr_raw.sr_deflated)
        out["sr_deflated_eff"].append(dsr_eff.sr_deflated)
        out["p_value"].append(boot.p_value)

    return {k: np.array(v) for k, v in out.items()}


def run(n_draws=50, B=1500, seed0=300_000, verbose=True):
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
    print(f"\n{'N':>6} {'rho':>5} {'RMSE(IS)':>10} {'RMSE(raw)':>10} {'RMSE(eff)':>10} {'RMSE(boot)':>11} | "
          f"{'R2(IS)':>8} {'R2(raw)':>8} {'R2(eff)':>8} {'R2(boot)':>9}")
    for (N, rho), cell in results.items():
        actual = cell["sr_oos"]
        row = []
        for pred_key in ["sr_is", "sr_deflated_raw", "sr_deflated_eff", "sr_deflated_boot"]:
            row.append((rmse(cell[pred_key], actual), r_squared(cell[pred_key], actual)))
        print(f"{N:>6} {rho:>5.1f} " + " ".join(f"{r[0]:>10.4f}" for r in row) + " | " +
              " ".join(f"{r[1]:>8.3f}" for r in row))

    print("\n-- decay tracking (spec §4.3's figure): realized vs predicted, mean over draws --")
    print(f"{'N':>6} {'rho':>5} {'realized decay':>16} {'boot-predicted decay':>22} {'closedform(raw)-pred':>22}")
    for (N, rho), cell in results.items():
        realized = (cell["sr_is"] - cell["sr_oos"]).mean()
        boot_pred = (cell["sr_is"] - cell["sr_deflated_boot"]).mean()
        raw_pred = (cell["sr_is"] - cell["sr_deflated_raw"]).mean()
        print(f"{N:>6} {rho:>5.1f} {realized:>16.4f} {boot_pred:>22.4f} {raw_pred:>22.4f}")

    print("\n-- rho=0 consistency check: bootstrap vs closed-form(raw) should agree --")
    for N in N_LEVELS:
        cell = results[(N, 0.0)]
        diff = cell["sr_deflated_boot"] - cell["sr_deflated_raw"]
        print(f"N={N:<5} mean(boot-closedform) = {diff.mean():+.4f} (SD {diff.std(ddof=1):.4f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=50)
    parser.add_argument("--B", type=int, default=1500)
    args = parser.parse_args()

    results = run(n_draws=args.n_draws, B=args.B)
    report(results)
    with open("figures/e7_predictive_power_data.pkl", "wb") as f:
        pickle.dump(results, f)
