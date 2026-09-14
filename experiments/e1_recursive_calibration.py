"""Experiment 1, re-run with the recursive bootstrap (estimator/
recursive_bootstrap.py) in place of the naive one, for all four searchers.

Prediction: Honest/Greedy/GridSearch should be essentially unchanged (their
menus are already data-oblivious -- SCOPE.md -- so re-deriving vs freezing
the selection shouldn't matter, and this experiment checks that directly as
a consistency guard). Adaptive should now ALSO pass, since the recursive
bootstrap re-derives each round's winner instead of freezing it at its
value on the real data.

Usage: python -m experiments.e1_recursive_calibration --n-draws 500
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.recursive_bootstrap import recursive_deflate
from searchers.scripted import Honest, Greedy, GridSearch, Adaptive

SEARCHER_FACTORIES = {
    "honest": lambda seed: Honest(seed=seed),
    "greedy": lambda seed: Greedy(seed=seed),
    "gridsearch": lambda seed: GridSearch(subset_sizes=(1, 2, 3), max_trials=1500, seed=seed),
    "adaptive": lambda seed: Adaptive(max_features=3, seed=seed),
}


def run(n_draws=100, M=100, T=1000, T_oos=500, K=30, B=2000, seed0=10_000, verbose=True):
    p_values = {name: [] for name in SEARCHER_FACTORIES}
    t0 = time.time()

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        data = generate(config)
        base_columns = Sandbox(data, periods_per_year=config.periods_per_year).base_feature_columns()

        for name, factory in SEARCHER_FACTORIES.items():
            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            searcher = factory(seed0 + i)
            searcher.run(sandbox)
            sr_sel = searcher.replay(base_columns, annualization=np.sqrt(config.periods_per_year))
            result = recursive_deflate(base_columns, searcher, sr_sel=sr_sel, B=B,
                                        annualization=np.sqrt(config.periods_per_year), seed=seed0 + i)
            p_values[name].append(result.p_value)

        if verbose and (i + 1) % max(1, n_draws // 10) == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    return {name: np.array(v) for name, v in p_values.items()}


def report(p_values):
    print(f"\n{'searcher':<12} {'KS stat':>10} {'KS p-value':>12}  verdict")
    for name, p in p_values.items():
        stat, ks_p = kstest(p, "uniform")
        verdict = "PASS (uniform)" if ks_p > 0.05 else "FAIL (not uniform)"
        print(f"{name:<12} {stat:>10.4f} {ks_p:>12.4f}  {verdict}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=100)
    parser.add_argument("--M", type=int, default=100)
    parser.add_argument("--T", type=int, default=1000)
    parser.add_argument("--K", type=int, default=30)
    parser.add_argument("--B", type=int, default=2000)
    args = parser.parse_args()

    pvals = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)
    report(pvals)
