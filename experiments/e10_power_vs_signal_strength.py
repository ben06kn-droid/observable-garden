"""Corrects a conflation in e9's power numbers: power rising with rho
(README/SCOPE.md's earlier framing) measures the DGP's difficulty gradient,
not the estimator's sensitivity -- true OOS Sharpe of the submitted spec
rises sixfold across the rho axis (0.15 -> 0.93) by construction (holding
the oracle ceiling fixed while rho makes noise features near-duplicates of
the signal), and power is a function of effect size. The "alignment"
finding reported earlier was the same fact restated, not an independent
explanation -- alignment and true OOS Sharpe are algebraically linked in
this linear DGP.

The deconfounded power axis is signal strength (spec section 2.2's own
difficulty knob: target oracle Sharpe in {0.5, 1.0, 2.0}), holding rho
FIXED at 0 -- the cleanest, hardest regime, with no correlated-noise
substitutes to inflate effect size for free. The rho axis stays reserved
for what it actually shows cleanly: bias divergence across correlation
(SCOPE.md section 9's main table).

Usage: python -m experiments.e10_power_vs_signal_strength
"""
from __future__ import annotations

import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, analytic_sharpe, calibrate_sigma, generate, oracle_sharpe_analytic
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from searchers.scripted import GridSearch

TARGET_SHARPE_LEVELS = [0.5, 1.0, 2.0]
N_LEVELS = [10, 1000]
RHO = 0.0   # fixed: the clean regime, no correlated-noise substitutes
K = 40
M, T, T_OOS = 60, 600, 300


def build_config(target_sharpe: float, seed: int) -> DGPConfig:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=1.0, seed=seed, heterogeneous=True)
    sigma = calibrate_sigma(target_sharpe, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=sigma, seed=seed, heterogeneous=True)


def run_cell(n_draws: int, N: int, target_sharpe: float, B: int, seed0: int):
    out = {k: [] for k in ["sr_is", "sr_oos_true", "sr_oracle", "p_value"]}
    for i in range(n_draws):
        config = build_config(target_sharpe, seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)

        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher = GridSearch(subset_sizes=(1, 2, 3), max_trials=N, seed=seed0 + i)
        searcher.run(sandbox)
        spec, dist = sandbox.submission
        R = sandbox.returns_matrix()

        out["sr_is"].append(dist.mean)
        out["sr_oos_true"].append(analytic_sharpe(config, spec.weights))
        out["sr_oracle"].append(oracle_sharpe_analytic(config))
        out["p_value"].append(deflate(R, sr_sel=dist.mean, B=B, annualization=ann, seed=seed0 + i).p_value)

    return {k: np.array(v) for k, v in out.items()}


def run(n_draws=100, B=1500, seed0=1_000_000, verbose=True):
    results = {}
    t0 = time.time()
    for target_sharpe in TARGET_SHARPE_LEVELS:
        for N in N_LEVELS:
            cell = run_cell(n_draws, N, target_sharpe, B, seed0)
            results[(N, target_sharpe)] = cell
            if verbose:
                print(f"  N={N:<5} target_sharpe={target_sharpe:<4} done  ({time.time()-t0:.1f}s elapsed)")
    return results


def report(results):
    print(f"\nrho={RHO} (fixed, clean regime), K={K}\n")
    print(f"{'N':>6} {'target SR':>10} {'power (frac p<0.05)':>20} {'mean SR_oos_true':>17} "
          f"{'within-cell SD':>15} {'mean SR_oracle':>15}")
    for (N, ts), cell in results.items():
        power = (cell["p_value"] < 0.05).mean()
        print(f"{N:>6} {ts:>10.1f} {power:>20.3f} {cell['sr_oos_true'].mean():>17.4f} "
              f"{cell['sr_oos_true'].std(ddof=1):>15.4f} {cell['sr_oracle'].mean():>15.4f}")


if __name__ == "__main__":
    results = run()
    report(results)
    with open("figures/e10_power_data.pkl", "wb") as f:
        pickle.dump(results, f)
