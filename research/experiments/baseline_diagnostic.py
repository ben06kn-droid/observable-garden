"""Diagnostic: LatticeAdaptive's naive and recursive type-I rate both read
~0.060 at n=150, B=300 -- about one Wilson-CI standard error above nominal
0.05 in both methods (they're mathematically identical for an oblivious
menu, so this is really one number, not a coincidence needing its own
explanation). Worth checking directly whether this is finite-B noise
(unlikely -- B=300 gives p-value granularity of ~0.0033, nowhere near
enough to explain a 1-point gap) or a persistent small bias, by running at
B=10,000 and seeing whether the reading moves toward 0.05 or holds steady.

Usage: python -m experiments.baseline_diagnostic
"""
from __future__ import annotations

import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from estimator.metrics import type1_rate, ks_critical_value
from searchers.diagnostic import LatticeAdaptive


def run(n_draws=60, M=50, T=500, T_oos=200, K=20, B=10_000, seed0=99_000):
    p_values = []
    t0 = time.time()
    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher = LatticeAdaptive(seed=seed0 + i)
        searcher.run(sandbox)
        _, dist = sandbox.submission
        p_values.append(deflate(sandbox.returns_matrix(), sr_sel=dist.mean, B=B, annualization=ann, seed=seed0 + i).p_value)
        if (i + 1) % 10 == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    p_values = np.array(p_values)
    stat, ks_p = kstest(p_values, "uniform")
    rate, lo, hi = type1_rate(p_values, alpha=0.05)
    d_crit = ks_critical_value(n_draws, alpha=0.05)
    print(f"\nB={B}  n={n_draws}  KS_stat={stat:.4f} (critical {d_crit:.4f})  KS_p={ks_p:.4f}  "
          f"type-I={rate:.3f} (95% CI {lo:.3f}-{hi:.3f})")


if __name__ == "__main__":
    run()
