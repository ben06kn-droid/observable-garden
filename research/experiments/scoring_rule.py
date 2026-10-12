"""scoring-rule: does the naive scoring rule explain the gap between search-depth's and adaptive-powered's Adaptive type-I?

Pre-registered at 8383b11, before this ran. search-depth's adaptive row, same draws, block length
and resampled indices; the only change is the Sharpe the naive null is compared against: Adaptive's own
selected value (search-depth's rule) or the largest Sharpe in the transcript (adaptive-powered's rule, deflate's default).

Usage: python -m experiments.scoring_rule [--workers N]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe
from estimator.metrics import type1_rate
from experiments._parallel import run_cells
from experiments.search_depth import ALPHA, B, BLOCK, K, M, N_DOSE, RHO, SEED0, T, T_OOS, git_state
from searchers.scripted import Adaptive

SEARCH_DEPTH_OUTPUT = "figures/search_depth_data.pkl"
OUTPUT = "figures/scoring_rule_data.pkl"
FIELDS = ("p_selected", "p_transcript_max", "sr_selected", "sr_transcript_max")


def run_draw(seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = Adaptive(max_features=3, seed=seed)
    searcher.run(sandbox)
    base, R = sandbox.base_feature_columns(), sandbox.returns_matrix()
    sr_selected = searcher.replay(base, annualization=ann)
    sr_transcript_max = float(sharpe(R, axis=0, annualization=ann).max())
    L = select_block_length(base - base.mean(axis=0))
    null = null_max_bootstrap(R, B=B, block_length=L, annualization=ann, seed=seed).M_b
    return {"p_selected": float((1 + np.sum(null >= sr_selected)) / (B + 1)),
            "p_transcript_max": float((1 + np.sum(null >= sr_transcript_max)) / (B + 1)),
            "sr_selected": sr_selected, "sr_transcript_max": sr_transcript_max}


def run(workers: int | None, git: dict) -> dict:
    cells = {start: [(SEED0 + i,) for i in range(start, min(start + BLOCK, N_DOSE))] for start in range(0, N_DOSE, BLOCK)}
    out = run_cells(run_draw, cells, workers=workers)
    rows = [d for start in range(0, N_DOSE, BLOCK) for d in out[start]]
    data = {field: np.array([row[field] for row in rows]) for field in FIELDS}
    data.update({"git_at_launch": git, "seeds": SEED0 + np.arange(N_DOSE)})
    return data


def report(data: dict) -> None:
    git = data["git_at_launch"]
    print(f"\nsearch-depth's adaptive row, n={N_DOSE}, B={B}; git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}")
    with open(SEARCH_DEPTH_OUTPUT, "rb") as f:
        search_depth_p = pickle.load(f)["adaptive"]["p_naive"]
    reproduced = np.array_equal(data["p_selected"], search_depth_p)
    print(f"  1. reproduction: p under search-depth's rule equals search-depth's stored p_naive on all draws: {reproduced}")
    if not reproduced:
        print("     STOP: not search-depth's draws; nothing below is interpreted.")
        return

    diff = np.abs(data["sr_transcript_max"] - data["sr_selected"])
    print(f"  draws where the two sr_sel values differ by more than 1e-12: {int(np.sum(diff > 1e-12))}; largest difference {diff.max():.2e}")
    for field, label in (("p_selected", "selected value (search-depth)"), ("p_transcript_max", "transcript maximum (adaptive-powered)")):
        rate, lo, hi = type1_rate(data[field], alpha=ALPHA)
        print(f"  naive type-I scoring the {label}: {rate:.3f} ({lo:.3f}-{hi:.3f})")
    sel, mx = data["p_selected"] < ALPHA, data["p_transcript_max"] < ALPHA
    only_max, only_sel = int(np.sum(mx & ~sel)), int(np.sum(sel & ~mx))
    n = only_max + only_sel
    p = float(binomtest(only_max, n, 0.5).pvalue) if n else 1.0
    verdict = ("the scoring rule moves Adaptive's naive type-I" if p < ALPHA else
               "the scoring rule does not explain the gap; configuration and the block-length rule remain")
    print(f"  2. McNemar, rejections only under transcript maximum vs only under selected value: {only_max}-{only_sel}, "
          f"p = {p:.4f} -> {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    data = run(args.workers, git_state())
    report(data)
    with open(OUTPUT, "wb") as f:
        pickle.dump(data, f)


if __name__ == "__main__":
    main()
