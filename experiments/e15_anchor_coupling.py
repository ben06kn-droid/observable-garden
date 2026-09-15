"""Does the naive bootstrap's distortion depend on how the menu couples to the selection statistic?

Background. SCOPE.md §5 reported that NeighborAdaptive, whose round-2 anchor
is the feature most correlated with the round-1 winner, inflated type-I
exactly as much as Adaptive, and concluded that any data-dependent anchor rule
distorts equally. That result was a bug: NeighborAdaptive._anchor set the
winner's correlation to -inf before taking absolute values, so |-inf| won and
the anchor was always the winner. NeighborAdaptive was Adaptive. The bug is
fixed (searchers/dose_response.py) and tested.

Design. Four searchers differ only in the round-2 anchor rule (each overrides
NeighborAdaptive._anchor), all with max_features=2, so the anchor choice is
the only data-dependent step in the menu:
  winner    the round-1 winner (Adaptive's rule): maximal coupling to the
            selection statistic
  neighbor  the feature most correlated with the winner (bug fixed): weaker
            coupling
  random    a feature drawn from the searcher's own seed: no coupling; the
            menu is fully data-oblivious, so this is the control
  worst     the round-1 loser: coupling in the opposite direction
Settings as in SCOPE.md §5's dose-response run: K=20, M=50, T=500, rho=0.3,
s=0 (pure null), sigma=1. n=500 paired seeds (every variant sees the same DGP
draw and the same bootstrap indices at each index), B=1500, alpha=0.05.
sr_sel is each searcher's own replay value on the real data. Both naive
(estimator.bootstrap.deflate on the logged transcript) and recursive
(estimator.recursive_bootstrap.recursive_deflate) p-values are computed and
saved raw.

Predictions, stated before running
  Naive type-I: winner > neighbor > random, with random ~ 5%, and worst <= 5%.
  Recursive type-I: near 5% for all four.

Analysis, fixed before running
  Per variant and method: type-I rate at alpha=0.05 with a Wilson 95% CI, and
  a KS test of the p-values against Uniform(0,1).
  Paired: exact McNemar test (two-sided binomial test on discordant pairs) of
  the naive rejection indicators, winner vs. each other rule; the same for
  recursive, reported as secondary.
  Readings:
  - Point estimates in the predicted order, random's CI containing 5%, and
    worst's point estimate at or below 5%: the distortion depends on how the
    menu couples to the selection statistic, not only on adaptivity.
  - Neighbor not distinguishable from winner (McNemar p >= 0.05): the original
    "the rule doesn't matter" conclusion holds after all, for a different reason.
  - Random's CI excluding 5%: the control is broken; stop and diagnose before
    reading anything else.
  - Any recursive CI excluding 5%: the recursive fix does not extend to that rule.

Usage: python -m experiments.e15_anchor_coupling [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest, kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate, sharpe
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_deflate
from experiments._parallel import run_cells
from searchers.dose_response import NeighborAdaptive, RandomAnchor, WinnerAnchor, WorstAnchor

K, M, T, T_OOS, RHO = 20, 50, 500, 250, 0.3
MAX_FEATURES = 2
N_DRAWS, B, ALPHA = 500, 1500, 0.05
SEED0 = 15_000_000
BLOCK = 50
VARIANTS = {"winner": WinnerAnchor, "neighbor": NeighborAdaptive, "random": RandomAnchor, "worst": WorstAnchor}
OUTPUT = "figures/e15_anchor_coupling_data.pkl"


def run_draw(variant: str, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = VARIANTS[variant](max_features=MAX_FEATURES, seed=seed)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    winner = int(np.argmax(sharpe(base, axis=0)))
    R = sandbox.returns_matrix()
    return {
        "p_naive": deflate(R, sr_sel=sr_sel, B=B, annualization=ann, seed=seed).p_value,
        "p_recursive": recursive_deflate(base, searcher, sr_sel=sr_sel, B=B, annualization=ann, seed=seed).p_value,
        "sr_sel": sr_sel, "winner": winner, "anchor": searcher._anchor(K, base, winner), "n_logged": R.shape[1],
    }


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None) -> dict:
    cells = {
        (variant, start): [(variant, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for variant in VARIANTS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "settings": {
        "K": K, "M": M, "T": T, "rho": RHO, "max_features": MAX_FEATURES, "B": B, "alpha": ALPHA}}
    for field in ("p_naive", "p_recursive", "sr_sel", "winner", "anchor", "n_logged"):
        data[field] = {
            variant: np.array([d[field] for start in range(0, n_draws, BLOCK) for d in out[(variant, start)]])
            for variant in VARIANTS
        }
    return data


def mcnemar_exact(reject_a: np.ndarray, reject_b: np.ndarray) -> tuple[int, int, float]:
    only_a = int(np.sum(reject_a & ~reject_b))
    only_b = int(np.sum(~reject_a & reject_b))
    p = binomtest(only_a, only_a + only_b, 0.5).pvalue if only_a + only_b else 1.0
    return only_a, only_b, float(p)


def report(data: dict) -> None:
    n = len(data["seeds"])
    print(f"\nn={n} paired draws, K={K}, M={M}, T={T}, rho={RHO}, s=0, max_features={MAX_FEATURES}, "
          f"B={B}, alpha={ALPHA}\n")
    print(f"{'variant':>9} {'anchor=winner':>13} | {'naive type-I (95% CI)':>24} {'KS D':>6} {'KS p':>7} | "
          f"{'recursive type-I (95% CI)':>26} {'KS D':>6} {'KS p':>7}")
    rates = {}
    for v in VARIANTS:
        row = [f"{v:>9} {np.mean(data['anchor'][v] == data['winner'][v]):>13.3f} |"]
        for method in ("p_naive", "p_recursive"):
            p = data[method][v]
            rate, lo, hi = type1_rate(p, alpha=ALPHA)
            ks = kstest(p, "uniform")
            rates[(v, method)] = (rate, lo, hi)
            row.append(f"{rate:>8.3f} ({lo:.3f}-{hi:.3f}) {ks.statistic:>12.3f} {ks.pvalue:>7.4f} |")
        print(" ".join(row).rstrip(" |"))

    for method in ("p_naive", "p_recursive"):
        label = "naive (primary)" if method == "p_naive" else "recursive (secondary)"
        print(f"\nExact McNemar, winner vs. each rule, {label}:")
        winner_reject = data[method]["winner"] < ALPHA
        for v in ("neighbor", "random", "worst"):
            only_w, only_v, p = mcnemar_exact(winner_reject, data[method][v] < ALPHA)
            print(f"  winner vs {v:<8}: rejected by winner only {only_w:>3}, by {v} only {only_v:>3}, p = {p:.4g}")

    naive = {v: rates[(v, "p_naive")] for v in VARIANTS}
    print("\nPre-registered readings:")
    print(f"  naive order winner > neighbor > random: "
          f"{naive['winner'][0] > naive['neighbor'][0] > naive['random'][0]}")
    print(f"  random CI contains 5% (control intact): {naive['random'][1] <= ALPHA <= naive['random'][2]}")
    print(f"  worst point estimate <= 5%: {naive['worst'][0] <= ALPHA}")
    for v in VARIANTS:
        lo, hi = rates[(v, 'p_recursive')][1:]
        print(f"  recursive CI contains 5% for {v}: {lo <= ALPHA <= hi}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/e15_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="10 draws, no checkpoints, nothing saved")
    args = parser.parse_args()
    if args.smoke:
        report(run(10, args.workers, None))
        return
    data = run(N_DRAWS, args.workers, args.checkpoint_dir)
    report(data)
    with open(OUTPUT, "wb") as f:
        pickle.dump(data, f)


if __name__ == "__main__":
    main()
