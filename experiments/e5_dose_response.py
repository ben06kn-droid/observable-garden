"""Objective: establish whether the naive bootstrap's failure on Adaptive is
a general property of adaptive candidate generation, or an artifact of one
searcher. Success = a monotone dose-response between how data-dependent the
candidate set is and the type-I inflation.

Dose axis (beam width k, holding round structure fixed): LatticeAdaptive
(full menu) -> BeamAdaptive(16) -> BeamAdaptive(4) -> BeamAdaptive(2) ->
Adaptive (k=1). Prediction, stated before running: type-I rate decreases
monotonically in k.

Structural axis (k=1 throughout, changing which data-dependent rule
generates candidates): DepthAdaptive (one more round -- prediction:
inflation increases, selection compounds) and NeighborAdaptive (round 2
anchors on the feature most correlated with the round-1 winner rather than
the winner itself -- tests whether the specific rule matters or only its
data-dependence).

Falsifiers, declared before running: naive's type-I flat in k => the
mechanism story is wrong. Non-monotone => something's confounded with beam
width. Only original Adaptive breaks and BeamAdaptive(2) is fine => the
result is narrow, report it as such.

Paired seeds across all 7 variants (same DGP draw per index) so every
comparison is within-draw. Every draw also gets a divergence-rate
measurement (estimator/divergence.py) for the secondary diagnostic: does
naive's type-I inflation track candidate-set instability quantitatively,
not just qualitatively.

Scope note: run at n_draws=300 (not the requested 500) and procedure-level
bootstrap is NOT run here for all 7 variants -- see
experiments/e5b_procedure_level_spotcheck.py for that, at reduced n/B on a
handful of representative points. Full n=500 x B=2000 x 7 variants x 3
methods is not tractable in one session at procedure-level's B-full-re-runs
cost; naive and recursive (where the actual dose-response signal lives) get
full treatment, procedure-level gets a validation spot-check as it did for
the original Adaptive result.

Usage: python -m experiments.e5_dose_response --n-draws 300
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from estimator.divergence import recursive_bootstrap_and_divergence
from estimator.metrics import type1_rate, ks_critical_value
from searchers.diagnostic import LatticeAdaptive
from searchers.dose_response import BeamAdaptive, DepthAdaptive, NeighborAdaptive
from searchers.scripted import Adaptive

VARIANTS = {
    "lattice_adaptive (dose 0)": lambda seed: LatticeAdaptive(max_features=3, seed=seed),
    "beam16": lambda seed: BeamAdaptive(beam_width=16, max_features=3, seed=seed),
    "beam4": lambda seed: BeamAdaptive(beam_width=4, max_features=3, seed=seed),
    "beam2": lambda seed: BeamAdaptive(beam_width=2, max_features=3, seed=seed),
    "adaptive (dose max, k=1)": lambda seed: Adaptive(max_features=3, seed=seed),
    "depth_adaptive": lambda seed: DepthAdaptive(max_features=4, seed=seed),
    "neighbor_adaptive": lambda seed: NeighborAdaptive(max_features=3, seed=seed),
}


def run(n_draws=300, M=60, T=600, T_oos=300, K=25, B=1500, seed0=10_000, verbose=True):
    p_naive = {name: [] for name in VARIANTS}
    p_recursive = {name: [] for name in VARIANTS}
    divergence = {name: [] for name in VARIANTS}
    t0 = time.time()

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)
        base_columns_ref = Sandbox(data, periods_per_year=config.periods_per_year).base_feature_columns()

        for name, factory in VARIANTS.items():
            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            searcher = factory(seed0 + i)
            searcher.run(sandbox)
            R = sandbox.returns_matrix()

            # sr_sel MUST be the searcher's own submitted value, not
            # deflate()'s default (max over the whole transcript). Those
            # coincide only when greedy selection happens to land on the
            # transcript's true max -- true often but NOT always (found via
            # a direct counterexample: LatticeAdaptive's own greedy pick
            # was provably beaten by a fully-evaluated-but-unselected
            # triple on one draw). Any variant whose transcript can contain
            # unselected candidates -- LatticeAdaptive, every BeamAdaptive
            # width > 1 -- is exposed to this, not just LatticeAdaptive.
            sr_sel = searcher.replay(base_columns_ref, annualization=ann)
            p_naive[name].append(deflate(R, sr_sel=sr_sel, B=B, annualization=ann, seed=seed0 + i).p_value)

            M_b, mean_div, _entropy = recursive_bootstrap_and_divergence(
                base_columns_ref, searcher, B=B, annualization=ann, seed=seed0 + i,
            )
            p_recursive[name].append(float((1 + np.sum(M_b >= sr_sel)) / (B + 1)))
            divergence[name].append(mean_div)

        if verbose and (i + 1) % max(1, n_draws // 20) == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    return (
        {k: np.array(v) for k, v in p_naive.items()},
        {k: np.array(v) for k, v in p_recursive.items()},
        {k: np.array(v) for k, v in divergence.items()},
    )


def report(p_naive, p_recursive, divergence):
    n = len(next(iter(p_naive.values())))
    d_crit = ks_critical_value(n, alpha=0.05)
    print(f"\nn_draws={n}  KS critical value (alpha=0.05) = {d_crit:.4f}\n")
    header = f"{'variant':<26} {'mean div':>9} | {'naive KS':>9} {'naive p':>8} {'naive typeI (CI)':<22} | {'recur KS':>9} {'recur p':>8} {'recur typeI (CI)':<22}"
    print(header)
    print("-" * len(header))
    for name in p_naive:
        stat_n, p_n = kstest(p_naive[name], "uniform")
        rate_n, lo_n, hi_n = type1_rate(p_naive[name], alpha=0.05)
        stat_r, p_r = kstest(p_recursive[name], "uniform")
        rate_r, lo_r, hi_r = type1_rate(p_recursive[name], alpha=0.05)
        mean_div = divergence[name].mean()
        print(f"{name:<26} {mean_div:>9.3f} | {stat_n:>9.4f} {p_n:>8.4f} "
              f"{rate_n:.3f} ({lo_n:.3f}-{hi_n:.3f})  | {stat_r:>9.4f} {p_r:>8.4f} {rate_r:.3f} ({lo_r:.3f}-{hi_r:.3f})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=300)
    parser.add_argument("--M", type=int, default=60)
    parser.add_argument("--T", type=int, default=600)
    parser.add_argument("--K", type=int, default=25)
    parser.add_argument("--B", type=int, default=1500)
    args = parser.parse_args()

    p_naive, p_recursive, divergence = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)
    report(p_naive, p_recursive, divergence)

    import pickle
    with open("figures/e5_dose_response_data.pkl", "wb") as f:
        pickle.dump({"p_naive": p_naive, "p_recursive": p_recursive, "divergence": divergence}, f)
