"""search-depth: how does search depth change the distortion, and do recursive nulls coincide across beam widths?

Pre-registered at 3a2c335, before this ran. Anchor rules at d=3 on n=1,000 paired draws;
dose-response-beam's dose axis and DepthAdaptive on the first 500 of the same draws. Each draw builds the naive,
recursive and full-class nulls on common resampled indices and records, per replicate, whether the
searcher's replayed value equals the full-class maximum (P5's mechanism).

Usage: python -m experiments.search_depth [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle
import subprocess

import numpy as np
from scipy.stats import binomtest, kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe
from estimator.full_class import full_class_matrix
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from searchers.diagnostic import LatticeAdaptive
from searchers.dose_response import (
    BeamAdaptive, DepthAdaptive, GumbelAnchored, NeighborAdaptive, RandomAnchor, WinnerAnchor, normalized_rank,
)
from searchers.scripted import Adaptive

K, M, T, T_OOS, RHO = 20, 50, 500, 250, 0.3
B, ALPHA = 1500, 0.05
SEED0, BLOCK = 40_000, 50
N_ANCHOR, N_DOSE = 1000, 500
REPLICATE_THRESHOLD, DECISION_THRESHOLD = 0.99, 0.99
METHODS = ("p_naive", "p_recursive", "p_full_class")
SEARCHERS = {   # label: (class, keyword arguments, draws)
    "winner": (WinnerAnchor, {"max_features": 3}, N_ANCHOR),
    "neighbor": (NeighborAdaptive, {"max_features": 3}, N_ANCHOR),
    "random": (RandomAnchor, {"max_features": 3}, N_ANCHOR),
    "gumbel0": (GumbelAnchored, {"tau": 0.0, "max_features": 3}, N_ANCHOR),
    "lattice": (LatticeAdaptive, {"max_features": 3}, N_DOSE),
    "beam16": (BeamAdaptive, {"beam_width": 16, "max_features": 3}, N_DOSE),
    "beam4": (BeamAdaptive, {"beam_width": 4, "max_features": 3}, N_DOSE),
    "beam2": (BeamAdaptive, {"beam_width": 2, "max_features": 3}, N_DOSE),
    "adaptive": (Adaptive, {"max_features": 3}, N_DOSE),
    "depth": (DepthAdaptive, {"max_features": 4}, N_DOSE),
}
DOSE_AXIS = ("lattice", "beam16", "beam4", "beam2", "adaptive")
OUTPUT = "figures/search_depth_data.pkl"


def run_draw(label: str, seed: int) -> dict:
    cls, kwargs, _ = SEARCHERS[label]
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = cls(seed=seed, **kwargs)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    L = select_block_length(base - base.mean(axis=0))

    M_naive = null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann, seed=seed).M_b
    M_rec = recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann, seed=seed).M_b
    M_full = null_max_bootstrap(full_class_matrix(base, kwargs["max_features"]), B=B, block_length=L,
                                annualization=ann, seed=seed).M_b
    equal = np.isclose(M_rec, M_full, rtol=1e-9, atol=1e-12)
    out = {method: float((1 + np.sum(null >= sr_sel)) / (B + 1))
           for method, null in zip(METHODS, (M_naive, M_rec, M_full))}
    out.update({"rep_rec_equals_full": int(equal.sum()), "rep_rec_above_full": int(np.sum((M_rec > M_full) & ~equal)),
                "sr_sel": sr_sel, "block_length": L, "anchor": -1, "kappa": np.nan})
    if isinstance(searcher, NeighborAdaptive):
        anchor = searcher._anchor(K, base, int(np.argmax(sharpe(base, axis=0))))
        out.update({"anchor": anchor, "kappa": normalized_rank(base, anchor)})
    return out


def git_state() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"commit": head, "dirty": dirty}


def run(scale: float, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    counts = {label: max(1, int(n * scale)) for label, (_, _, n) in SEARCHERS.items()}
    cells = {
        (label, start): [(label, SEED0 + i) for i in range(start, min(start + BLOCK, counts[label]))]
        for label in SEARCHERS for start in range(0, counts[label], BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    fields = (*METHODS, "rep_rec_equals_full", "rep_rec_above_full", "sr_sel", "block_length", "anchor", "kappa")
    data = {"git_at_launch": git, "settings": {"K": K, "M": M, "T": T, "rho": RHO, "B": B, "alpha": ALPHA,
                                              "seed0": SEED0, "draws": counts}}
    for label in SEARCHERS:
        rows = [d for start in range(0, counts[label], BLOCK) for d in out[(label, start)]]
        data[label] = {field: np.array([row[field] for row in rows]) for field in fields}
    return data


def mcnemar(first: np.ndarray, second: np.ndarray) -> tuple[int, int, float]:
    only_first, only_second = int(np.sum(first & ~second)), int(np.sum(~first & second))
    n = only_first + only_second
    return only_first, only_second, float(binomtest(only_first, n, 0.5).pvalue) if n else 1.0


def report(data: dict) -> None:
    git = data["git_at_launch"]
    print(f"\nK={K}, M={M}, T={T}, rho={RHO}, B={B}; git at launch {git['commit'][:7]}"
          f"{' (dirty)' if git['dirty'] else ''}\n")
    print(f"{'searcher':>9} {'n':>5} {'mean kappa':>10} | "
          + " | ".join(f"{m[2:]:>10} type-I (95% CI) {'KS p':>6}" for m in METHODS))
    for label, rows in ((label, data[label]) for label in SEARCHERS):
        cols = []
        for method in METHODS:
            rate, lo, hi = type1_rate(rows[method], alpha=ALPHA)
            cols.append(f"{rate:>10.3f} ({lo:.3f}-{hi:.3f}) {kstest(rows[method], 'uniform').pvalue:>6.3f}")
        kappa = np.nanmean(rows["kappa"]) if np.isfinite(rows["kappa"]).any() else float("nan")
        print(f"{label:>9} {len(rows['p_naive']):>5} {kappa:>10.3f} | " + " | ".join(cols))

    print("\nPre-registered readings")
    shared = len(data["adaptive"]["p_naive"])
    identical = all(np.array_equal(data["winner"][m][:shared], data["adaptive"][m]) for m in METHODS)
    print(f"  1. winner and adaptive identical on {shared} shared draws: {identical}")

    rate_r, lo_r, hi_r = type1_rate(data["random"]["p_naive"], alpha=ALPHA)
    rate_g, lo_g, hi_g = type1_rate(data["gumbel0"]["p_naive"], alpha=ALPHA)
    print(f"  2. random {rate_r:.3f} ({lo_r:.3f}-{hi_r:.3f}) and gumbel0 {rate_g:.3f} ({lo_g:.3f}-{hi_g:.3f}) "
          f"within each other's intervals: {lo_g <= rate_r <= hi_g and lo_r <= rate_g <= hi_r}")

    winner_reject = data["winner"]["p_naive"] < ALPHA
    for label in ("neighbor", "random"):
        reject = data[label]["p_naive"] < ALPHA
        k, n = int(reject.sum()), len(reject)
        p_binom = binomtest(k, n, ALPHA, alternative="greater").pvalue
        only_w, only_r, p_mc = mcnemar(winner_reject, reject)
        if p_binom >= ALPHA:
            outcome = "(c) not detectably inflated (minimum detectable rate about 6.9% at n=1,000)"
        elif p_mc < ALPHA and only_w > only_r:
            outcome = "(a) partly inflated"
        else:
            outcome = "(b) fully inflated: not separated from winner"
        print(f"  3. {label}: {k}/{n} rejections, binomial vs 5% p = {p_binom:.4f}; McNemar vs winner "
              f"{only_w}-{only_r}, p = {p_mc:.4f} -> {outcome}")

    for label in (*DOSE_AXIS,):
        rows = data[label]
        frac = rows["rep_rec_equals_full"].sum() / (len(rows["p_naive"]) * B)
        above = int(rows["rep_rec_above_full"].sum())
        print(f"  4. {label}: replicates where the replayed value equals the full-class maximum {frac:.4f} "
              f"(threshold {REPLICATE_THRESHOLD}); replicates above it (should be 0): {above} -> "
              f"{'holds' if frac >= REPLICATE_THRESHOLD else 'FAILS: narrow P5'}")

    adaptive_reject = data["adaptive"]["p_recursive"] < ALPHA
    for label in ("lattice", "beam16", "beam4", "beam2"):
        rows = data[label]
        agree = float(np.mean((rows["p_recursive"] < ALPHA) == adaptive_reject))
        exact = float(np.mean(rows["p_recursive"] == data["adaptive"]["p_recursive"]))
        print(f"  5. {label} vs adaptive: recursive rejection decisions agree {agree:.3f} "
              f"(threshold {DECISION_THRESHOLD}), exact p-value agreement {exact:.3f}")

    nominal = all(type1_rate(data[label][m], alpha=ALPHA)[1] <= ALPHA
                  for label in SEARCHERS for m in ("p_recursive", "p_full_class"))
    print(f"  6. recursive and full-class not significantly above 5% for every searcher: {nominal}")

    dose = [type1_rate(data[label]["p_naive"], alpha=ALPHA)[0] for label in DOSE_AXIS]
    print(f"  7. naive type-I along {' -> '.join(DOSE_AXIS)}: {', '.join(f'{r:.3f}' for r in dose)}; "
          f"nondecreasing: {all(a <= b for a, b in zip(dose, dose[1:]))}")

    print("\nSecondary: exact McNemar between adjacent dose-axis rows (naive)")
    for first, second in zip(DOSE_AXIS, DOSE_AXIS[1:]):
        a, b, p = mcnemar(data[first]["p_naive"] < ALPHA, data[second]["p_naive"] < ALPHA)
        print(f"  {first} vs {second}: {a}-{b}, p = {p:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/search_depth_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="1%% of the draws, no checkpoints, nothing saved")
    args = parser.parse_args()
    git = git_state()
    if args.smoke:
        report(run(0.01, args.workers, None, git))
        return
    data = run(1.0, args.workers, args.checkpoint_dir, git)
    report(data)
    with open(OUTPUT, "wb") as f:
        pickle.dump(data, f)


if __name__ == "__main__":
    main()
