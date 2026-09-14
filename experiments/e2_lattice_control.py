"""Isolates adaptive SELECTION from adaptive CANDIDATE GENERATION.

Adaptive's menu (what gets evaluate()'d) and its selection (what gets
submit()'d) are both conditional on realized outcomes. LatticeAdaptive
(searchers/diagnostic.py) keeps the exact same sequential greedy selection
rule but evaluates the FULL fixed lattice unconditionally first -- an
oblivious menu. Same null-calibration check (naive bootstrap, s=0, KS
against U(0,1)) as experiments/e1_null_calibration.py, run on Adaptive and
LatticeAdaptive on the SAME null draws.

If LatticeAdaptive is calibrated where Adaptive is not, adaptive candidate
generation -- not adaptive selection -- is what breaks the naive bootstrap.
That's the theory in SCOPE.md, stated as a one-variable-changed experiment
rather than argued from the mechanism alone.

Usage: python -m experiments.e2_lattice_control --n-draws 200
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from estimator.metrics import type1_rate, ks_critical_value
from searchers.diagnostic import LatticeAdaptive
from searchers.scripted import Adaptive

SEARCHER_FACTORIES = {
    "adaptive": lambda seed: Adaptive(max_features=3, seed=seed),
    "lattice_adaptive": lambda seed: LatticeAdaptive(max_features=3, seed=seed),
}


def run(n_draws=200, M=60, T=600, T_oos=300, K=20, B=1500, seed0=30_000, verbose=True):
    p_values = {name: [] for name in SEARCHER_FACTORIES}
    t0 = time.time()

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        data = generate(config)

        for name, factory in SEARCHER_FACTORIES.items():
            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            factory(seed0 + i).run(sandbox)
            # Explicit sr_sel = the searcher's OWN submitted value, not
            # deflate()'s default (max over the whole transcript). For
            # Adaptive these coincide (its transcript IS its greedy path,
            # so the running max already equals what it submits). For
            # LatticeAdaptive they do NOT: its transcript is the full
            # lattice, most of which the greedy rule never selects, so the
            # default would silently test "is the full-lattice max
            # calibrated" -- i.e. re-test GridSearch -- instead of "is this
            # searcher's own greedy-selected report calibrated."
            _, dist = sandbox.submission
            # dist.mean is annualized (Sandbox.evaluate() scales by
            # sqrt(periods_per_year)); deflate()'s bootstrap must use the
            # same annualization or sr_sel and M_b are in different units.
            ann = np.sqrt(config.periods_per_year)
            result = deflate(sandbox.returns_matrix(), sr_sel=dist.mean, B=B, annualization=ann, seed=seed0 + i)
            p_values[name].append(result.p_value)

        if verbose and (i + 1) % max(1, n_draws // 10) == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    return {name: np.array(v) for name, v in p_values.items()}


def report(p_values):
    n = len(next(iter(p_values.values())))
    d_crit = ks_critical_value(n, alpha=0.05)
    print(f"\nn_draws={n}  KS critical value (alpha=0.05) = {d_crit:.4f}\n")
    print(f"{'searcher':<18} {'KS stat':>9} {'KS p':>8}  {'type-I rate (95% CI)':<28}  verdict")
    for name, p in p_values.items():
        stat, ks_p = kstest(p, "uniform")
        rate, lo, hi = type1_rate(p, alpha=0.05)
        verdict = "PASS" if ks_p > 0.05 else "FAIL"
        print(f"{name:<18} {stat:>9.4f} {ks_p:>8.4f}  {rate:.3f} ({lo:.3f}-{hi:.3f}) vs nominal 0.05   {verdict}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=200)
    parser.add_argument("--M", type=int, default=60)
    parser.add_argument("--T", type=int, default=600)
    parser.add_argument("--K", type=int, default=20)
    parser.add_argument("--B", type=int, default=1500)
    args = parser.parse_args()

    pvals = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)
    report(pvals)
