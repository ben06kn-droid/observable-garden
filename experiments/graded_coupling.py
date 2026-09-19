"""graded-coupling: is the naive bootstrap's distortion graded in how strongly the anchor tracks performance?

Pre-registered at 254cdda, before this ran. GumbelAnchored(tau) spans loser (-inf),
uniform random (0) and winner (+inf) anchors; each draw builds the naive, recursive and full-class
nulls on common resampled indices and records the coupling kappa of the anchor it chose.

Usage: python -m experiments.graded_coupling [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle
import subprocess

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe
from estimator.full_class import full_class_matrix
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from searchers.dose_response import GumbelAnchored, normalized_rank

K, M, T, T_OOS, RHO = 20, 50, 500, 250, 0.3
D, N_DRAWS, B, ALPHA = 2, 500, 1500, 0.05
SEED0, BLOCK = 30_000, 50
TAUS = (-np.inf, -2.0, -1.0, 0.0, 1.0, 2.0, 4.0, np.inf)
N_PERMUTATIONS, TREND_ALPHA = 10_000, 0.01
METHODS = ("p_naive", "p_recursive", "p_full_class")
OUTPUT = "figures/graded_coupling_data.pkl"


def run_draw(tau: float, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = GumbelAnchored(tau=tau, max_features=D, seed=seed)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    L = select_block_length(base - base.mean(axis=0))

    nulls = {
        "p_naive": null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann, seed=seed).M_b,
        "p_recursive": recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann, seed=seed).M_b,
        "p_full_class": null_max_bootstrap(full_class_matrix(base, D), B=B, block_length=L, annualization=ann,
                                           seed=seed).M_b,
    }
    winner = int(np.argmax(sharpe(base, axis=0)))
    anchor = searcher._anchor(K, base, winner)
    out = {method: float((1 + np.sum(null >= sr_sel)) / (B + 1)) for method, null in nulls.items()}
    out.update({"kappa": normalized_rank(base, anchor), "anchor": anchor, "winner": winner, "sr_sel": sr_sel,
                "block_length": L})
    return out


def git_state() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"commit": head, "dirty": dirty}


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (str(tau), start): [(tau, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for tau in TAUS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "taus": TAUS, "git_at_launch": git, "settings": {
        "K": K, "M": M, "T": T, "rho": RHO, "d": D, "B": B, "alpha": ALPHA}}
    for field in (*METHODS, "kappa", "anchor", "winner", "sr_sel", "block_length"):
        data[field] = np.array([[d[field] for start in range(0, n_draws, BLOCK) for d in out[(str(tau), start)]]
                                for tau in TAUS])   # (n_taus, n_draws)
    return data


def trend_test(rejections: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """rejections: (n_taus, n_draws) booleans. One-sided test of increase across tau levels, permuting
    the levels within each draw so the pairing is respected."""
    R = rejections.T.astype(float)                       # (n_draws, n_taus)
    scores = np.arange(1, R.shape[1] + 1, dtype=float)
    observed = float(np.sum(R * scores))
    permuted = np.empty(N_PERMUTATIONS)
    for b in range(N_PERMUTATIONS):
        order = np.argsort(rng.random(R.shape), axis=1)
        permuted[b] = np.sum(np.take_along_axis(R, order, axis=1) * scores)
    return observed, float((1 + np.sum(permuted >= observed)) / (N_PERMUTATIONS + 1))


def report(data: dict) -> None:
    n = data["p_naive"].shape[1]
    git = data["git_at_launch"]
    print(f"\nn={n} paired draws per tau, K={K}, M={M}, T={T}, rho={RHO}, d={D}, B={B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}\n")
    print(f"{'tau':>6} {'mean kappa':>10} | " + " | ".join(f"{m[2:]:>12} type-I (95% CI) {'KS p':>6}" for m in METHODS))
    for i, tau in enumerate(TAUS):
        cols = []
        for method in METHODS:
            rate, lo, hi = type1_rate(data[method][i], alpha=ALPHA)
            cols.append(f"{rate:>12.3f} ({lo:.3f}-{hi:.3f}) {kstest(data[method][i], 'uniform').pvalue:>6.3f}")
        print(f"{tau:>6} {data['kappa'][i].mean():>10.3f} | " + " | ".join(cols))

    rng = np.random.default_rng(17)
    trend_p = {}
    print("\nWithin-draw permutation trend test across tau (one-sided, increasing):")
    for method in METHODS:
        observed, trend_p[method] = trend_test(data[method] < ALPHA, rng)
        label = "PRIMARY" if method == "p_naive" else "secondary"
        print(f"  {method[2:]:>10} ({label}): statistic {observed:.0f}, p = {trend_p[method]:.4f}")

    naive = [type1_rate(data["p_naive"][i], alpha=ALPHA)[0] for i in range(len(TAUS))]
    p_primary = trend_p["p_naive"]
    print("\nPre-registered readings:")
    print(f"  naive type-I point estimates nondecreasing in tau: {all(a <= b for a, b in zip(naive, naive[1:]))}")
    print(f"  naive type-I <= 5% for every tau <= 0: {all(r <= ALPHA for r, t in zip(naive, TAUS) if t <= 0)}")
    for method in ("p_recursive", "p_full_class"):
        lower_bounds = [type1_rate(data[method][i], alpha=ALPHA)[1] for i in range(len(TAUS))]
        print(f"  {method[2:]} not significantly above 5% at any tau (lower CI bound <= 5%): "
              f"{all(lo <= ALPHA for lo in lower_bounds)}")
    claim = "graded coupling" if p_primary < TREND_ALPHA else "winner-anchoring only, with worst-anchoring as its mirror"
    print(f"  DECISION (trend p = {p_primary:.4f}, threshold {TREND_ALPHA}): the note claims {claim}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/graded_coupling_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="8 draws, no checkpoints, nothing saved")
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
