"""unequal-correlation: does P4 survive when features are not exchangeable?

Pre-registered at 8f4acb5, before this ran. Arm (a): winner anchoring under a single-factor
heterogeneous correlation at K=20 and K=80, testing whether the lemma's conclusion (the process maximum
dominates the frozen-menu maximum) and the corrections survive. Arm (b): the neighbor rule under both
structures, measuring how much heterogeneity separates the correlations P6 leaves open.

Usage: python -m experiments.unequal_correlation [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest, kstest

from environments.dgp import DGPConfig, generate, get_sigma_x
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe, stationary_bootstrap_indices
from estimator.full_class import full_class_matrix
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from searchers.dose_response import NeighborAdaptive, WinnerAnchor, normalized_rank

M, T, T_OOS, RHO = 50, 500, 250, 0.3
D, N_DRAWS, B, ALPHA = 2, 500, 1500, 0.05
SEED0, BLOCK = 70_000, 25
STABILITY_REPS = 300
DOMINANCE_THRESHOLD, TOLERANCE = 0.99, 1e-12
CELLS = {   # label: (searcher class, K, heterogeneous)
    "winner_het_K20": (WinnerAnchor, 20, True),
    "winner_het_K80": (WinnerAnchor, 80, True),
    "neighbor_het_K20": (NeighborAdaptive, 20, True),
    "neighbor_equi_K20": (NeighborAdaptive, 20, False),
}
WINNER_CELLS = ("winner_het_K20", "winner_het_K80")
NEIGHBOR_CELLS = ("neighbor_het_K20", "neighbor_equi_K20")
METHODS = ("p_naive", "p_recursive", "p_full_class")
FIELDS = (*METHODS, "dominance", "mean_gap", "worst_gap", "kappa", "stability", "top_loading",
          "sr_sel", "block_length")
LIMIT = {"winner_het_K20": 0.0914, "winner_het_K80": 0.1438}   # unequal-correlation's prereg, 8f4acb5, Gaussian limit
OUTPUT = "figures/unequal_correlation_data.pkl"


def anchor_stability(searcher, base: np.ndarray, anchor: int, K: int, block_length: int, seed: int) -> float:
    """Share of resampled replicates whose neighbor anchor matches the real data's. Uses its own index
    stream, so it does not depend on the order in which the nulls draw theirs."""
    S0 = base - base.mean(axis=0)
    rng = np.random.default_rng(seed + 1)
    same = 0
    for _ in range(STABILITY_REPS):
        Sb = S0[stationary_bootstrap_indices(len(S0), block_length, rng), :]
        same += searcher._anchor(K, Sb, int(np.argmax(sharpe(Sb, axis=0)))) == anchor
    return same / STABILITY_REPS


def run_draw(label: str, seed: int) -> dict:
    cls, K, heterogeneous = CELLS[label]
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed,
                       heterogeneous=heterogeneous)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = cls(max_features=D, seed=seed)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    L = select_block_length(base - base.mean(axis=0))

    M_naive = null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann, seed=seed).M_b
    M_rec = recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann, seed=seed).M_b
    M_full = null_max_bootstrap(full_class_matrix(base, D), B=B, block_length=L, annualization=ann, seed=seed).M_b
    gap = M_rec - M_naive

    winner = int(np.argmax(sharpe(base, axis=0)))
    anchor = searcher._anchor(K, base, winner)
    out = {method: float((1 + np.sum(null >= sr_sel)) / (B + 1))
           for method, null in zip(METHODS, (M_naive, M_rec, M_full))}
    out.update({"dominance": int(np.sum(gap >= -TOLERANCE)), "mean_gap": float(gap.mean()),
                "worst_gap": float(gap.min()), "kappa": normalized_rank(base, anchor),
                "sr_sel": sr_sel, "block_length": L, "stability": np.nan, "top_loading": np.nan})
    if cls is NeighborAdaptive:
        off = get_sigma_x(config) - np.eye(K)
        out["top_loading"] = float(anchor == int(np.argmax(off.sum(axis=1))))
        out["stability"] = anchor_stability(searcher, base, anchor, K, L, seed)
    return out


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (label, start): [(label, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for label in CELLS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "git_at_launch": git, "settings": {
        "M": M, "T": T, "rho": RHO, "d": D, "B": B, "alpha": ALPHA, "draws": n_draws}}
    for label in CELLS:
        rows = [d for start in range(0, n_draws, BLOCK) for d in out[(label, start)]]
        data[label] = {field: np.array([row[field] for row in rows]) for field in FIELDS}
    return data


def report(data: dict) -> None:
    git = data["git_at_launch"]
    n = data["settings"]["draws"]
    print(f"\nn={n} draws per cell, M={M}, T={T}, rho={RHO}, d={D}, B={B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}\n")
    print(f"{'cell':>18} {'limit':>6} | " + " | ".join(f"{m[2:]:>10} type-I (95% CI) {'KS p':>6}" for m in METHODS)
          + f" | {'naive<=rec':>10} {'dominance':>9}")
    for label in CELLS:
        rows, cols = data[label], []
        for method in METHODS:
            rate, lo, hi = type1_rate(rows[method], alpha=ALPHA)
            cols.append(f"{rate:>10.3f} ({lo:.3f}-{hi:.3f}) {kstest(rows[method], 'uniform').pvalue:>6.3f}")
        below = np.mean(rows["p_naive"] <= rows["p_recursive"])
        dominance = rows["dominance"].sum() / (len(rows["p_naive"]) * B)
        limit = f"{LIMIT[label]:>6.3f}" if label in LIMIT else f"{'-':>6}"
        print(f"{label:>18} {limit} | " + " | ".join(cols) + f" | {below:>10.3f} {dominance:>9.5f}")

    print("\nPre-registered decisions")
    for label in WINNER_CELLS:
        rows = data[label]
        dominance = rows["dominance"].sum() / (len(rows["p_naive"]) * B)
        verdict = "holds" if dominance >= DOMINANCE_THRESHOLD else "FAILS: P4's conclusion is exchangeable-only"
        print(f"  1. {label}: replicates with M_P >= M_C {dominance:.5f} (threshold {DOMINANCE_THRESHOLD}) -> {verdict}; "
              f"worst gap {rows['worst_gap'].min():+.4f}, mean gap {rows['mean_gap'].mean():+.4f}")
    for label in WINNER_CELLS:
        rows = data[label]
        k = int((rows["p_naive"] < ALPHA).sum())
        p = binomtest(k, len(rows["p_naive"]), ALPHA, alternative="greater").pvalue
        print(f"  2. {label}: naive {k}/{len(rows['p_naive'])} rejections, binomial vs 5% p = {p:.4f} -> "
              f"{'inflated' if p < ALPHA else 'not detectably inflated'}")
    nominal = {label: all(type1_rate(data[label][m], alpha=ALPHA)[1] <= ALPHA
                          for m in ("p_recursive", "p_full_class")) for label in CELLS}
    print(f"  3. recursive and full-class not significantly above 5% in every cell: {all(nominal.values())}"
          + ("" if all(nominal.values()) else f" (failed in {[l for l, ok in nominal.items() if not ok]})"))
    het, equi = (data[label]["stability"] for label in NEIGHBOR_CELLS)
    wins, losses = int(np.sum(het > equi)), int(np.sum(het < equi))
    p = binomtest(wins, wins + losses, 0.5, alternative="greater").pvalue if wins + losses else 1.0
    print(f"  4. anchor stability higher under heterogeneity on {wins} of {wins + losses} decided seeds "
          f"(means {het.mean():.3f} vs {equi.mean():.3f}), sign test p = {p:.4g} -> "
          f"{'separates' if p < ALPHA else 'no detected separation'}")

    print("\nSecondary")
    for label in CELLS:
        rows = data[label]
        line = f"  {label:>18}: mean kappa {rows['kappa'].mean():.3f}"
        if np.isfinite(rows["top_loading"]).any():
            line += (f", anchor is the top-loading feature on {np.nanmean(rows['top_loading']):.3f} of draws"
                     f", anchor stability {np.nanmean(rows['stability']):.3f}")
        print(line + f", mean block length {rows['block_length'].mean():.2f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/unequal_correlation_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="8 draws per cell, no checkpoints, nothing saved")
    args = parser.parse_args()
    git = git_state()
    if args.smoke:
        report(run(8, args.workers, None, git))
        return
    data = run(N_DRAWS, args.workers, args.checkpoint_dir, git)
    report(data)
    with open(OUTPUT, "wb") as f:
        pickle.dump(data, f)


if __name__ == "__main__":
    main()
