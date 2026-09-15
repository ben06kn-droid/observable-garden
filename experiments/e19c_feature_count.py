"""E19(c): does naive inflation grow with the number of candidate features?

Pre-registered in prereg/E19c.md, committed before this ran. A winner-anchored depth-2 search sees the first
K of 80 generated features, K in {10, 20, 40, 80}, so draws are paired across K; each K builds the naive,
recursive and full-class nulls on common resampled indices.

Usage: python -m experiments.e19c_feature_count [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, DGPData, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length
from estimator.full_class import full_class_matrix
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from experiments.e17_graded_coupling import trend_test
from experiments.e18_depth import git_state
from searchers.dose_response import WinnerAnchor

K_MAX, KS, RHOS = 80, (10, 20, 40, 80), (0.0, 0.3)
M, T, T_OOS = 50, 500, 250
D, N_DRAWS, B, ALPHA = 2, 500, 1500, 0.05
SEED0, BLOCK = 70_000, 25
TREND_ALPHA = 0.01
LIMIT = {0.0: {10: 0.101, 20: 0.155, 40: 0.242, 80: 0.357},    # prereg/E19c.md, Gaussian limit
         0.3: {10: 0.073, 20: 0.091, 40: 0.113, 80: 0.137}}
METHODS = ("p_naive", "p_recursive", "p_full_class")
FIELDS = (*METHODS, "sr_sel", "block_length")
OUTPUT = "figures/e19c_feature_count_data.pkl"


def first_features(data: DGPData, K: int) -> DGPData:
    """The same draw restricted to its first K features. Valid only without signal (s=0), where returns do not
    depend on the features."""
    if data.S.size:
        raise ValueError("first_features needs s=0: with signal, returns depend on features outside the slice")
    return DGPData(x_in=data.x_in[:, :, :K], r_in=data.r_in, x_oos=data.x_oos[:, :, :K], r_oos=data.r_oos,
                   S=data.S, beta_full=data.beta_full[:K])


def run_draw(rho: float, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K_MAX, s=0, rho=rho, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    full = generate(config)
    out = {}
    for K in KS:
        sandbox = Sandbox(first_features(full, K), periods_per_year=config.periods_per_year)
        searcher = WinnerAnchor(max_features=D, seed=seed)
        searcher.run(sandbox)
        base = sandbox.base_feature_columns()
        sr_sel = searcher.replay(base, annualization=ann)
        L = select_block_length(base - base.mean(axis=0))
        nulls = {
            "p_naive": null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann,
                                          seed=seed).M_b,
            "p_recursive": recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann,
                                                        seed=seed).M_b,
            "p_full_class": null_max_bootstrap(full_class_matrix(base, D), B=B, block_length=L, annualization=ann,
                                               seed=seed).M_b,
        }
        for method, null in nulls.items():
            out[(method, K)] = float((1 + np.sum(null >= sr_sel)) / (B + 1))
        out[("sr_sel", K)], out[("block_length", K)] = sr_sel, L
    return out


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (rho, start): [(rho, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for rho in RHOS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "Ks": KS, "rhos": RHOS, "git_at_launch": git, "settings": {
        "K_max": K_MAX, "M": M, "T": T, "d": D, "B": B, "alpha": ALPHA}}
    for field in FIELDS:
        data[field] = np.array([[[d[(field, K)] for start in range(0, n_draws, BLOCK) for d in out[(rho, start)]]
                                 for K in KS] for rho in RHOS])   # (n_rhos, n_Ks, n_draws)
    return data


def report(data: dict) -> None:
    n = data["p_naive"].shape[2]
    git = data["git_at_launch"]
    print(f"\nn={n} nested draws per rho, K in {KS} of {K_MAX}, M={M}, T={T}, d={D}, B={B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}")
    rng = np.random.default_rng(19)
    for r, rho in enumerate(RHOS):
        print(f"\nrho = {rho}")
        print(f"{'K':>4} {'limit':>6} | " + " | ".join(f"{m[2:]:>10} type-I (95% CI) {'KS p':>6}" for m in METHODS)
              + f" | {'naive<=rec':>10} {'full>rec':>8}")
        for k, K in enumerate(KS):
            cols = []
            for method in METHODS:
                rate, lo, hi = type1_rate(data[method][r, k], alpha=ALPHA)
                cols.append(f"{rate:>10.3f} ({lo:.3f}-{hi:.3f}) {kstest(data[method][r, k], 'uniform').pvalue:>6.3f}")
            below = np.mean(data["p_naive"][r, k] <= data["p_recursive"][r, k])
            above = np.mean(data["p_full_class"][r, k] > data["p_recursive"][r, k])
            print(f"{K:>4} {LIMIT[rho][K]:>6.3f} | " + " | ".join(cols) + f" | {below:>10.3f} {above:>8.3f}")

        naive = data["p_naive"][r] < ALPHA
        observed, p = trend_test(naive, rng)
        claim = "grows with the number of candidate features" if p < TREND_ALPHA else "no claim"
        print(f"  PRIMARY: naive trend test, increasing in K: statistic {observed:.0f}, p = {p:.4f} "
              f"(threshold {TREND_ALPHA}) -> {claim}")
        rates = naive.mean(axis=1)
        print(f"  5. naive type-I per doubling of K: {(rates[-1] - rates[0]) / (len(KS) - 1):+.4f}")
        observed, p = trend_test((data["p_full_class"][r] < ALPHA)[::-1], rng)
        print(f"  3. full-class trend test, decreasing in K: statistic {observed:.0f}, p = {p:.4f}")
        nominal = all(type1_rate(data[m][r, k], alpha=ALPHA)[1] <= ALPHA
                      for m in ("p_recursive", "p_full_class") for k in range(len(KS)))
        print(f"  2. recursive and full-class not significantly above 5% at every K: {nominal}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/e19c_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="4 draws per rho, no checkpoints, nothing saved")
    args = parser.parse_args()
    git = git_state()
    if args.smoke:
        report(run(4, args.workers, None, git))
        return
    data = run(N_DRAWS, args.workers, args.checkpoint_dir, git)
    report(data)
    with open(OUTPUT, "wb") as f:
        pickle.dump(data, f)


if __name__ == "__main__":
    main()
