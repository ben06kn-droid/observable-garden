"""E16: does the P4 lemma's pointwise dominance explain e15's winner inflation?

Pre-registered in prereg/E16.md, committed before this ran. For winner- and
worst-anchored two-step searches, builds the naive (realized-menu) and the
recursive (process) null on the same resampled time indices, then checks
draw by draw whether p_naive <= p_recursive (winner) or >= (worst), and
replicate by replicate whether M_P >= M_C.

Usage: python -m experiments.e16_pointwise_dominance [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle
import subprocess

import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe
from estimator.metrics import type1_rate, wilson_ci
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from searchers.dose_response import WinnerAnchor, WorstAnchor

K, M, T, T_OOS, RHO = 20, 50, 500, 250, 0.3
MAX_FEATURES, N_DRAWS, B, ALPHA = 2, 500, 1500, 0.05
SEED0, BLOCK = 20_000, 50
GATE_PASS, GATE_STOP = 0.90, 0.80
VARIANTS = {"winner": WinnerAnchor, "worst": WorstAnchor}
OUTPUT = "figures/e16_pointwise_dominance_data.pkl"


def run_draw(variant: str, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = VARIANTS[variant](max_features=MAX_FEATURES, seed=seed)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    L = select_block_length(base - base.mean(axis=0))

    M_C = null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann, seed=seed).M_b
    M_P = recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann, seed=seed).M_b
    equal = np.isclose(M_P, M_C, rtol=1e-9, atol=1e-12)
    winner = int(np.argmax(sharpe(base, axis=0)))
    return {
        "p_naive": float((1 + np.sum(M_C >= sr_sel)) / (B + 1)),
        "p_recursive": float((1 + np.sum(M_P >= sr_sel)) / (B + 1)),
        "rep_P_gt_C": int(np.sum((M_P > M_C) & ~equal)),
        "rep_equal": int(np.sum(equal)),
        "rep_P_lt_C": int(np.sum((M_P < M_C) & ~equal)),
        "sr_sel": sr_sel, "winner": winner, "anchor": searcher._anchor(K, base, winner), "block_length": L,
    }


def git_state() -> dict:
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip())
    return {"commit": head, "dirty": dirty}


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None) -> dict:
    cells = {
        (variant, start): [(variant, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for variant in VARIANTS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "git": git_state(), "settings": {
        "K": K, "M": M, "T": T, "rho": RHO, "max_features": MAX_FEATURES, "B": B, "alpha": ALPHA}}
    fields = ("p_naive", "p_recursive", "rep_P_gt_C", "rep_equal", "rep_P_lt_C", "sr_sel", "winner", "anchor",
              "block_length")
    for field in fields:
        data[field] = {v: np.array([d[field] for start in range(0, n_draws, BLOCK) for d in out[(v, start)]])
                       for v in VARIANTS}
    return data


def report(data: dict) -> None:
    n = len(data["seeds"])
    print(f"\nn={n} draws per searcher, K={K}, M={M}, T={T}, rho={RHO}, max_features={MAX_FEATURES}, B={B}; "
          f"git {data['git']['commit'][:7]}{' (dirty)' if data['git']['dirty'] else ''}\n")
    for v, direction in (("winner", "<="), ("worst", ">=")):
        pn, pr = data["p_naive"][v], data["p_recursive"][v]
        holds = pn <= pr if direction == "<=" else pn >= pr
        k = int(holds.sum())
        lo, hi = wilson_ci(k, n)
        ties = float(np.mean(pn == pr))
        gt, eq, lt = (int(data[f][v].sum()) for f in ("rep_P_gt_C", "rep_equal", "rep_P_lt_C"))
        total = gt + eq + lt
        rep_holds = (gt + eq) if v == "winner" else (lt + eq)
        print(f"{v}: draws with p_naive {direction} p_recursive: {k}/{n} = {k / n:.3f} (95% CI {lo:.3f}-{hi:.3f}); "
              f"exact ties {ties:.3f}")
        print(f"{'':>{len(v) + 2}}replicates M_P > M_C {gt / total:.3f}, equal {eq / total:.3f}, M_P < M_C {lt / total:.3f}; "
              f"predicted direction holds in {rep_holds / total:.3f}")
        for method in ("p_naive", "p_recursive"):
            rate, rlo, rhi = type1_rate(data[method][v], alpha=ALPHA)
            print(f"{'':>{len(v) + 2}}{method[2:]} type-I {rate:.3f} ({rlo:.3f}-{rhi:.3f})")
        print()

    primary = float(np.mean(data["p_naive"]["winner"] <= data["p_recursive"]["winner"]))
    if primary >= GATE_PASS:
        verdict = "P4 supported as the mechanism: proceed to E17-E22"
    elif primary < GATE_STOP:
        verdict = "P4 is not the mechanism behind e15: pause E17-E22 and rethink §4 of the note"
    else:
        verdict = "ambiguous (0.80-0.90): decide explicitly before running E17"
    print(f"PRE-REGISTERED GATE: winner fraction {primary:.3f} -> {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/e16_checkpoints")
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
