"""Replaces/augments the Jaccard-distance divergence rate with a magnitude
measure: normalized Shannon entropy of the round1_beam distribution across
bootstrap replicates (estimator/divergence.py's beam_entropy), normalized
by log(C(K, beam_width)) since raw entropy isn't comparable across beam
widths with different-sized outcome spaces (a beam of size 4 has a much
larger space of possible subsets than a beam of size 1, which inflates raw
entropy for larger beams in a way that has nothing to do with how much
"search freedom" naive fails to simulate).

Reuses the exact same seeds/config as experiments/e5_dose_response.py so
this is directly comparable to the already-measured type-I rates, without
re-running the (much more expensive) naive+recursive bootstrap passes.

Usage: python -m experiments.e5d_entropy_diagnostic --n-draws 150
"""
from __future__ import annotations

import argparse
import pickle
import time
from math import comb, log

import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.divergence import beam_entropy
from searchers.diagnostic import LatticeAdaptive
from searchers.dose_response import BeamAdaptive, DepthAdaptive, NeighborAdaptive
from searchers.scripted import Adaptive

VARIANTS = {
    "lattice_adaptive (dose 0)": (lambda seed: LatticeAdaptive(max_features=3, seed=seed), 20),
    "beam16": (lambda seed: BeamAdaptive(beam_width=16, max_features=3, seed=seed), 16),
    "beam4": (lambda seed: BeamAdaptive(beam_width=4, max_features=3, seed=seed), 4),
    "beam2": (lambda seed: BeamAdaptive(beam_width=2, max_features=3, seed=seed), 2),
    "adaptive (dose max, k=1)": (lambda seed: Adaptive(max_features=3, seed=seed), 1),
    "depth_adaptive": (lambda seed: DepthAdaptive(max_features=4, seed=seed), 1),
    "neighbor_adaptive": (lambda seed: NeighborAdaptive(max_features=3, seed=seed), 1),
}


def run(n_draws=150, M=50, T=500, T_oos=300, K=20, B=300, seed0=10_000, verbose=True):
    entropy = {name: [] for name in VARIANTS}
    norm_entropy = {name: [] for name in VARIANTS}
    t0 = time.time()

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        ann = np.sqrt(config.periods_per_year)
        data = generate(config)
        base_columns_ref = Sandbox(data, periods_per_year=config.periods_per_year).base_feature_columns()

        for name, (factory, k) in VARIANTS.items():
            searcher = factory(seed0 + i)
            h = beam_entropy(base_columns_ref, searcher, B=B, annualization=ann, seed=seed0 + i)
            max_h = log(comb(K, k)) if comb(K, k) > 1 else 1.0
            entropy[name].append(h)
            norm_entropy[name].append(h / max_h)

        if verbose and (i + 1) % max(1, n_draws // 20) == 0:
            print(f"  draw {i+1}/{n_draws}  ({time.time()-t0:.1f}s elapsed)")

    return ({k: np.array(v) for k, v in entropy.items()}, {k: np.array(v) for k, v in norm_entropy.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=150)
    parser.add_argument("--M", type=int, default=50)
    parser.add_argument("--T", type=int, default=500)
    parser.add_argument("--K", type=int, default=20)
    parser.add_argument("--B", type=int, default=300)
    args = parser.parse_args()

    entropy, norm_entropy = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)

    with open("figures/e5_dose_response_data.pkl", "rb") as f:
        data = pickle.load(f)
    from estimator.metrics import type1_rate

    print(f"\n{'variant':<26} {'mean H':>8} {'mean H_norm':>12} {'naive type-I':>13}")
    for name in VARIANTS:
        rate, _, _ = type1_rate(data["p_naive"][name], alpha=0.05)
        print(f"{name:<26} {entropy[name].mean():>8.3f} {norm_entropy[name].mean():>12.4f} {rate:>13.3f}")

    with open("figures/e5_entropy_data.pkl", "wb") as f:
        pickle.dump({"entropy": entropy, "norm_entropy": norm_entropy}, f)
