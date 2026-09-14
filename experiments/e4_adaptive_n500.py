"""Adaptive-only, both estimators, at n=500 -- properly powered enough that
a KS statistic near the critical value doesn't leave the call ambiguous.
Skips Honest/Greedy/GridSearch (already confirmed well-calibrated at n=200
under both estimators; no open question to resolve there) to keep this
affordable at n=500.

Usage: python -m experiments.e4_adaptive_n500 --n-draws 500
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from estimator.recursive_bootstrap import recursive_deflate
from estimator.metrics import type1_rate, ks_critical_value
from searchers.scripted import Adaptive


def run(n_draws=500, M=60, T=600, T_oos=300, K=25, B=1500, seed0=10_000, verbose=True):
    p_naive, p_recursive = [], []
    t0 = time.time()
    ann = None

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)

        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher = Adaptive(max_features=3, seed=seed0 + i)
        searcher.run(sandbox)
        R = sandbox.returns_matrix()

        p_naive.append(deflate(R, B=B, seed=seed0 + i).p_value)

        base_columns = sandbox.base_feature_columns()
        sr_sel = searcher.replay(base_columns, annualization=ann)
        p_recursive.append(recursive_deflate(base_columns, searcher, sr_sel=sr_sel, B=B, annualization=ann, seed=seed0 + i).p_value)

        if verbose and (i + 1) % max(1, n_draws // 20) == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    return np.array(p_naive), np.array(p_recursive)


def report(p_naive, p_recursive):
    n = len(p_naive)
    d_crit = ks_critical_value(n, alpha=0.05)
    print(f"\nn_draws={n}  KS critical value (alpha=0.05) = {d_crit:.4f}\n")
    for name, p in [("naive", p_naive), ("recursive", p_recursive)]:
        stat, ks_p = kstest(p, "uniform")
        rate, lo, hi = type1_rate(p, alpha=0.05)
        verdict = "PASS" if ks_p > 0.05 else "FAIL"
        print(f"{name:<10} KS_stat={stat:.4f} ({'above' if stat > d_crit else 'below'} critical)  "
              f"KS_p={ks_p:.4f}  type-I rate={rate:.3f} (95% CI {lo:.3f}-{hi:.3f}) vs nominal 0.05  {verdict}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=500)
    parser.add_argument("--M", type=int, default=60)
    parser.add_argument("--T", type=int, default=600)
    parser.add_argument("--K", type=int, default=25)
    parser.add_argument("--B", type=int, default=1500)
    args = parser.parse_args()

    p_naive, p_recursive = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)
    report(p_naive, p_recursive)
