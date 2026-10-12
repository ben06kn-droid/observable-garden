"""oblivious-calibration: are oblivious searchers calibrated at every menu size and correlation?

Pre-registered at 82bea64, before this ran. Table 1 of the note, and its gate: every
result from anchor-coupling on says the realized-menu bootstrap fails when a search builds candidates from its own
results, and this is the control showing it does not fail when the candidate set is fixed in advance.

Menu size is driven by K, not by max_trials: subsets up to size 3 saturate the cap, so K in
{10, 20, 30, 40} gives 175, 1350, 4525 and 10700 logged columns. LatticeAdaptive runs at the two smaller
K only, as the oblivious-generation / adaptive-selection control (SCOPE.md, The two repairs).

Usage: python -m experiments.oblivious_calibration [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest, kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator import bootstrap
from estimator.bootstrap import null_max_bootstrap, select_block_length
from estimator.metrics import type1_rate
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden.audit import effective_breadth
from searchers.diagnostic import LatticeAdaptive
from searchers.scripted import Greedy, GridSearch, Honest

M, T, T_OOS = 50, 500, 250
B, ALPHA = 1500, 0.05
N_DRAWS, SEED0, BLOCK = 1000, 90_000, 25
KS = (10, 20, 30, 40)
OMEGAS = (0.0, 0.3, 0.6, 0.9)
LATTICE_KS = (10, 20)          # LatticeAdaptive's menu is GridSearch's; two sizes separate selection
SEARCHERS = ("honest", "greedy", "gridsearch", "lattice")
FIELDS = ("p_value", "sr_sel", "sr_deflated", "menu_size", "block_length", "breadth",
          "floor", "cap", "zero_variance")
OUTPUT = "figures/oblivious_calibration_data.pkl"


def build(name: str, seed: int):
    if name == "honest":
        return Honest(feature_index=0, seed=seed)
    if name == "greedy":
        return Greedy(seed=seed)
    if name == "gridsearch":
        return GridSearch(subset_sizes=(1, 2, 3), max_trials=None, seed=seed)
    return LatticeAdaptive(max_features=3, seed=seed)


def cells_for(K: int) -> tuple[str, ...]:
    return SEARCHERS if K in LATTICE_KS else tuple(s for s in SEARCHERS if s != "lattice")


def run_draw(K: int, omega: float, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=omega, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    data = generate(config)
    out = {}
    for name in cells_for(K):
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher = build(name, seed)
        searcher.run(sandbox)
        R = sandbox.returns_matrix()
        spec, dist = sandbox.submission
        sr_sel = float(dist.mean)
        L = int(select_block_length(R - R.mean(axis=0)))
        # The guards are module-level counters, not fields on the result. Each worker is its own
        # process, so resetting here and reading back after makes the count per draw rather than
        # cumulative (the same pattern as experiments/verify_sharpe_guards.py).
        bootstrap.reset_guard_counts()
        boot = null_max_bootstrap(R, B=B, block_length=L, annualization=ann, seed=seed)
        guards = dict(bootstrap.GUARD_COUNTS)
        out[name] = {
            "p_value": float((1 + np.sum(boot.M_b >= sr_sel)) / (B + 1)),
            "sr_sel": sr_sel, "sr_deflated": sr_sel - float(boot.M_b.mean()),
            "menu_size": int(R.shape[1]), "block_length": L,
            "breadth": float(effective_breadth(R)),
            "floor": guards["variance_floor"], "cap": guards["sharpe_cap"],
            "zero_variance": guards["zero_variance"],
        }
    return out


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (K, omega, start): [(K, omega, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for K in KS for omega in OMEGAS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "Ks": KS, "omegas": OMEGAS, "git_at_launch": git,
            "settings": {"M": M, "T": T, "B": B, "alpha": ALPHA, "draws": n_draws}}
    for K in KS:
        for omega in OMEGAS:
            rows = [d for start in range(0, n_draws, BLOCK) for d in out[(K, omega, start)]]
            for name in cells_for(K):
                data[(K, omega, name)] = {f: np.array([row[name][f] for row in rows]) for f in FIELDS}
    return data


def holm(pvalues: dict) -> dict:
    """Holm step-down across every cell, fixed in the pre-registration rather than read cell by cell."""
    ordered = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, adjusted, running = len(ordered), {}, 0.0
    for i, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[key] = running
    return adjusted


def report(data: dict) -> None:
    git = data["git_at_launch"]
    n = data["settings"]["draws"]
    print(f"\nn={n} draws per cell, M={M}, T={T}, B={B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}")

    ks_p, rows = {}, []
    for K in KS:
        for omega in OMEGAS:
            for name in cells_for(K):
                cell = data[(K, omega, name)]
                p = cell["p_value"]
                rate, lo, hi = type1_rate(p, alpha=ALPHA)
                ks_p[(K, omega, name)] = float(kstest(p, "uniform").pvalue)
                rows.append((K, omega, name, int(cell["menu_size"][0]), rate, lo, hi,
                             float(cell["breadth"].mean()), ks_p[(K, omega, name)]))
    adjusted = holm(ks_p)

    print(f"\n{'K':>4} {'omega':>6} {'searcher':>11} {'N':>7} {'type-I (95% CI)':>22} {'breadth':>8} "
          f"{'KS p':>7} {'Holm':>7}")
    for K, omega, name, N, rate, lo, hi, breadth, p in rows:
        print(f"{K:>4} {omega:>6.1f} {name:>11} {N:>7} {rate:>9.3f} ({lo:.3f}-{hi:.3f}) {breadth:>8.1f} "
              f"{p:>7.3f} {adjusted[(K, omega, name)]:>7.3f}")

    print("\nPre-registered decisions")
    ks_fail = [k for k, v in adjusted.items() if v < ALPHA]
    contains = [(K, omega, name) for K, omega, name, _, rate, lo, hi, _, _ in rows if not lo <= ALPHA <= hi]
    gate = not ks_fail and not contains
    print(f"  1. GATE: no cell's KS rejects after Holm, and every type-I interval contains 5%: {gate}")
    if ks_fail:
        print(f"     KS rejections after Holm: {ks_fail}")
    if contains:
        print(f"     intervals excluding 5%: {contains}")

    liberal = []
    for K, omega, name, _, rate, lo, hi, _, _ in rows:
        if name in ("honest", "greedy") and lo > ALPHA:
            liberal.append((K, omega, name, rate))
    print(f"  2. Honest and Greedy never liberal: {not liberal}" + (f" ({liberal})" if liberal else ""))

    print("  3. selection vs generation (LatticeAdaptive against GridSearch, paired):")
    for K in LATTICE_KS:
        for omega in OMEGAS:
            a = data[(K, omega, "lattice")]["p_value"] < ALPHA
            b = data[(K, omega, "gridsearch")]["p_value"] < ALPHA
            x, y = int(np.sum(a & ~b)), int(np.sum(~a & b))
            p_mc = binomtest(x, x + y, 0.5).pvalue if x + y else 1.0
            print(f"     K={K}, omega={omega}: lattice-only {x}, gridsearch-only {y}, McNemar p = {p_mc:.3f}")

    print("\nSecondary")
    honest = np.concatenate([data[(K, o, "honest")]["sr_deflated"] for K in KS for o in OMEGAS])
    print(f"  Honest deflated Sharpe: mean {honest.mean():+.4f} (should centre on zero)")
    floor = sum(int(data[(K, o, s)]["floor"].sum()) for K in KS for o in OMEGAS for s in cells_for(K))
    cap = sum(int(data[(K, o, s)]["cap"].sum()) for K in KS for o in OMEGAS for s in cells_for(K))
    zeros = sum(int(data[(K, o, s)]["zero_variance"].sum()) for K in KS for o in OMEGAS for s in cells_for(K))
    print(f"  Sharpe guards across every replicate of every cell: variance floor {floor}, cap {cap} "
          f"(both must be 0), exact-zero variances {zeros}")
    blocks = np.concatenate([data[(K, o, s)]["block_length"] for K in KS for o in OMEGAS for s in cells_for(K)])
    print(f"  block lengths: {dict(zip(*[x.tolist() for x in np.unique(blocks, return_counts=True)]))}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/oblivious_calibration_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="4 draws per cell, no checkpoints, nothing saved")
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
