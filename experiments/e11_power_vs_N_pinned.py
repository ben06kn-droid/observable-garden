"""Fixes a real confound in experiments/e10_power_vs_signal_strength.py,
caught on review: power there rose with N (16%->35% at target Sharpe 2.0),
which is impossible if sr_sel is truly held fixed while the transcript
grows. p = P(M_b >= sr_sel); adding columns to the transcript can only
make M_b stochastically larger, so p should rise and power should FALL,
monotonically, as N grows -- always, if sr_sel doesn't change. Power
rising means GridSearch was finding a materially better specification at
larger N, so the benefit of searching more and its multiple-testing cost
were still tangled together in one number.

This isolates them. searchers/diagnostic.py's PinnedSelector builds the
same combinatorial menu GridSearch does (so the transcript's size and
correlation structure grow with N exactly as before) but ALWAYS submits
the true signal triple, regardless of what any trial in the menu found.
For a fixed draw, the pinned spec's in-sample Sharpe does not depend on N
at all -- only the transcript around it does. Whatever power does as N
sweeps now, it's purely the bootstrap's response to a bigger transcript:
the pure multiple-testing cost of having looked, decoupled from the
benefit of having looked.

Prediction, stated before running: power falls monotonically in N at
fixed target Sharpe. If it doesn't, something is still wrong.

Usage: python -m experiments.e11_power_vs_N_pinned [--workers N] [--checkpoint-dir DIR]
"""
from __future__ import annotations

import argparse
import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, analytic_sharpe, calibrate_sigma, generate, oracle_sharpe_analytic
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from experiments._parallel import run_cells
from searchers.diagnostic import PinnedSelector

TARGET_SHARPE_LEVELS = [1.0, 2.0]
N_LEVELS = [10, 100, 1000]
RHO = 0.0   # same clean regime as e10, for direct comparison
K = 40
M, T, T_OOS = 60, 600, 300


def build_config(target_sharpe: float, seed: int) -> DGPConfig:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=1.0, seed=seed, heterogeneous=True)
    sigma = calibrate_sigma(target_sharpe, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=sigma, seed=seed, heterogeneous=True)


def run_draw(N: int, target_sharpe: float, B: int, seed: int) -> dict:
    config = build_config(target_sharpe, seed)
    ann = np.sqrt(config.periods_per_year)
    data = generate(config)

    pinned_weights = np.zeros(K)
    pinned_weights[data.S] = 1.0

    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    searcher = PinnedSelector(pinned_weights=pinned_weights, subset_sizes=(1, 2, 3), max_trials=N, seed=seed)
    searcher.run(sandbox)
    spec, dist = sandbox.submission
    R = sandbox.returns_matrix()
    return {
        "sr_is": dist.mean,
        "sr_oos_true": analytic_sharpe(config, spec.weights),
        "sr_oracle": oracle_sharpe_analytic(config),
        "p_value": deflate(R, sr_sel=dist.mean, B=B, annualization=ann, seed=seed).p_value,
        "n_logged": R.shape[1],
    }


def _stack(draws: list[dict]) -> dict[str, np.ndarray]:
    return {k: np.array([d[k] for d in draws]) for k in draws[0]}


def run_cell(n_draws: int, N: int, target_sharpe: float, B: int, seed0: int):
    return _stack([run_draw(N, target_sharpe, B, seed0 + i) for i in range(n_draws)])


def run(n_draws=100, B=1500, seed0=1_500_000, verbose=True, workers=None, checkpoint_dir=None):
    """Serial by default. With `workers` or `checkpoint_dir`, draws run across processes via
    experiments/_parallel.py; every draw carries its own seed, so the results are identical."""
    cells = {(N, ts): [(N, ts, B, seed0 + i) for i in range(n_draws)]
             for ts in TARGET_SHARPE_LEVELS for N in N_LEVELS}
    if workers is None and checkpoint_dir is None:
        results, t0 = {}, time.time()
        for (N, target_sharpe), tasks in cells.items():
            results[(N, target_sharpe)] = _stack([run_draw(*task) for task in tasks])
            if verbose:
                print(f"  N={N:<5} target_sharpe={target_sharpe:<4} done  ({time.time()-t0:.1f}s elapsed)")
        return results
    draws = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers, verbose=verbose)
    return {key: _stack(cell) for key, cell in draws.items()}


def report(results):
    print(f"\nrho={RHO} (fixed), K={K} -- sr_sel PINNED to the true triple regardless of N\n")
    print(f"{'N':>6} {'target SR':>10} {'power (frac p<0.05)':>20} {'mean sr_is (pinned)':>20} "
          f"{'SD(sr_is)':>10} {'mean n_logged':>14}")
    for (N, ts), cell in results.items():
        power = (cell["p_value"] < 0.05).mean()
        print(f"{N:>6} {ts:>10.1f} {power:>20.3f} {cell['sr_is'].mean():>20.4f} "
              f"{cell['sr_is'].std(ddof=1):>10.4f} {cell['n_logged'].mean():>14.1f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, help="run draws across this many processes (default: serial)")
    parser.add_argument("--checkpoint-dir", help="save each finished cell here, and resume from it")
    args = parser.parse_args()
    results = run(workers=args.workers, checkpoint_dir=args.checkpoint_dir)
    report(results)
    with open("figures/e11_power_pinned_data.pkl", "wb") as f:
        pickle.dump(results, f)
