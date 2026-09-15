"""Precondition check for Experiment 2 (spec §4.2-4.3), not Experiment 2
itself. The 0/300 greedy-convergence result under s=0 (README, SCOPE.md §5)
is a statement about this DGP's search landscape being effectively
unimodal at that configuration, not just about greedy selection -- and if
that unimodality persists at s=3, every searcher converges on roughly the
same specification regardless of trial budget, realized decay barely
varies with N, and spec §4.3's headline figure (E[SR_IS-SR_OOS] vs.
E[SR_IS-SR_deflated] tracking across trial budget) comes out flat no
matter how correct the estimator is. Cheap to check before spending the
full sweep's budget; expensive to discover after.

Two things checked, s=3 (real signal, unlike every prior experiment in
this repo, all of which ran at s=0):

1. Do searchers with different trial budgets select DIFFERENT specifications?
   GridSearch at N in {10, 100, 1000}, same draw, same seed -- compare
   submitted feature supports directly.
2. Does realized decay (SR_IS - SR_OOS) grow with N? Same sweep, averaged
   over several draws.

If either check fails, the fix is in the DGP (more features, higher K,
different correlation structure to make the search landscape genuinely
harder to search well by accident) -- not in the estimator, which is what
Experiment 2 is supposed to be evaluating.

Usage: python -m experiments.e6_pilot_signal_landscape
"""
from __future__ import annotations

import numpy as np

from environments.dgp import DGPConfig, calibrate_sigma, generate, true_signal_set
from environments.sandbox import Sandbox
from searchers.scripted import GridSearch

N_LEVELS = [10, 100, 1000]
K = 40
M, T, T_OOS = 60, 600, 300
RHO = 0.3
TARGET_ORACLE_SHARPE = 1.0


def build_config(seed: int) -> DGPConfig:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=1.0, seed=seed)
    sigma = calibrate_sigma(TARGET_ORACLE_SHARPE, template)
    return DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=sigma, seed=seed)


def run(n_draws: int = 20, seed0: int = 200_000):
    supports = {n: [] for n in N_LEVELS}
    decays = {n: [] for n in N_LEVELS}
    true_signal_hits = {n: [] for n in N_LEVELS}

    for i in range(n_draws):
        config = build_config(seed0 + i)
        data = generate(config)
        S_true = set(data.S.tolist())

        for n in N_LEVELS:
            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            searcher = GridSearch(subset_sizes=(1, 2, 3), max_trials=n, seed=seed0 + i)
            searcher.run(sandbox)
            spec, dist = sandbox.submission
            support = frozenset(np.flatnonzero(spec.weights).tolist())
            supports[n].append(support)
            sr_oos = sandbox.oos_sharpe_for_grading(spec)
            decays[n].append(dist.mean - sr_oos)
            true_signal_hits[n].append(len(support & S_true) / max(len(support), 1))

    print(f"K={K}, s=3, target oracle Sharpe={TARGET_ORACLE_SHARPE}, rho={RHO}, n_draws={n_draws}\n")

    print("-- Check 1: do different trial budgets select different supports? --")
    for i in range(min(5, n_draws)):
        row = [str(sorted(supports[n][i])) for n in N_LEVELS]
        same = len(set(supports[n][i] for n in N_LEVELS)) == 1
        print(f"draw {i}: " + "  |  ".join(f"N={n}: {s}" for n, s in zip(N_LEVELS, row)) + ("  [IDENTICAL]" if same else ""))
    identical_rate = np.mean([len(set(supports[n][i] for n in N_LEVELS)) == 1 for i in range(n_draws)])
    print(f"\nfraction of draws where all 3 budgets pick the IDENTICAL support: {identical_rate:.2f}")

    print("\n-- Check 2: does realized decay grow with N? --")
    print(f"{'N':>6} {'mean decay (SR_IS-SR_OOS)':>28} {'mean frac support in true S':>30}")
    for n in N_LEVELS:
        print(f"{n:>6} {np.mean(decays[n]):>28.4f} {np.mean(true_signal_hits[n]):>30.3f}")


if __name__ == "__main__":
    run()
