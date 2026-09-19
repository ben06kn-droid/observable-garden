"""anchor-rank: does naive inflation grade with the anchor's rank, or step near the top?

Pre-registered at db6b64e, before this ran. RankAnchor(k) fixes round 2's anchor at the
k-th best single feature; each draw builds the naive and recursive nulls on common resampled indices.

Usage: python -m experiments.anchor_rank [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest, kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap, select_block_length, sharpe
from estimator.metrics import type1_rate
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from searchers.dose_response import RankAnchor, normalized_rank

K, M, T, T_OOS, RHO = 20, 50, 500, 250, 0.3
D, N_DRAWS, B, ALPHA = 2, 1000, 1500, 0.05
SEED0, BLOCK = 50_000, 50
RANKS = (1, 2, 3, 5, 10, 20)
LIMIT = {1: 0.091, 2: 0.091, 3: 0.066, 5: 0.049, 10: 0.043, 20: 0.043}   # anchor-rank's prereg, db6b64e, Gaussian limit
METHODS = ("p_naive", "p_recursive")
FIELDS = (*METHODS, "kappa", "anchor", "winner", "sr_sel", "block_length")
OUTPUT = "figures/anchor_rank_data.pkl"


def run_draw(rank: int, seed: int) -> dict:
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=RHO, sigma=1.0, seed=seed)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    searcher = RankAnchor(rank=rank, max_features=D, seed=seed)
    searcher.run(sandbox)
    base = sandbox.base_feature_columns()
    sr_sel = searcher.replay(base, annualization=ann)
    L = select_block_length(base - base.mean(axis=0))

    nulls = {
        "p_naive": null_max_bootstrap(sandbox.returns_matrix(), B=B, block_length=L, annualization=ann, seed=seed).M_b,
        "p_recursive": recursive_null_max_bootstrap(base, searcher, B=B, block_length=L, annualization=ann, seed=seed).M_b,
    }
    winner = int(np.argmax(sharpe(base, axis=0)))
    anchor = searcher._anchor(K, base, winner)
    out = {method: float((1 + np.sum(null >= sr_sel)) / (B + 1)) for method, null in nulls.items()}
    out.update({"kappa": normalized_rank(base, anchor), "anchor": anchor, "winner": winner, "sr_sel": sr_sel,
                "block_length": L})
    return out


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (rank, start): [(rank, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for rank in RANKS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "ranks": RANKS, "git_at_launch": git, "settings": {
        "K": K, "M": M, "T": T, "rho": RHO, "d": D, "B": B, "alpha": ALPHA}}
    for field in FIELDS:
        data[field] = np.array([[d[field] for start in range(0, n_draws, BLOCK) for d in out[(rank, start)]]
                                for rank in RANKS])   # (n_ranks, n_draws)
    return data


def mcnemar(first: np.ndarray, second: np.ndarray, alternative: str) -> tuple[int, int, float]:
    """Exact McNemar on paired rejections; 'greater' tests whether `first` rejects more often."""
    only_first, only_second = int(np.sum(first & ~second)), int(np.sum(~first & second))
    n = only_first + only_second
    return only_first, only_second, float(binomtest(only_first, n, 0.5, alternative=alternative).pvalue) if n else 1.0


def report(data: dict) -> None:
    n = data["p_naive"].shape[1]
    git = data["git_at_launch"]
    print(f"\nn={n} paired draws per rank, K={K}, M={M}, T={T}, rho={RHO}, d={D}, B={B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}\n")
    print(f"{'rank':>4} {'mean kappa':>10} {'limit':>6} | {'naive type-I (95% CI)':>22} {'binom p':>7} {'KS p':>6} | "
          f"{'recursive type-I (95% CI)':>26} {'KS p':>6} | {'naive<=rec':>10}")
    reject = {rank: data["p_naive"][i] < ALPHA for i, rank in enumerate(RANKS)}
    for i, rank in enumerate(RANKS):
        rate, lo, hi = type1_rate(data["p_naive"][i], alpha=ALPHA)
        rrate, rlo, rhi = type1_rate(data["p_recursive"][i], alpha=ALPHA)
        binom = binomtest(int(reject[rank].sum()), n, ALPHA, alternative="greater").pvalue
        below = np.mean(data["p_naive"][i] <= data["p_recursive"][i])
        print(f"{rank:>4} {data['kappa'][i].mean():>10.3f} {LIMIT[rank]:>6.3f} | {rate:>8.3f} ({lo:.3f}-{hi:.3f}) {binom:>7.4f} "
              f"{kstest(data['p_naive'][i], 'uniform').pvalue:>6.3f} | {rrate:>12.3f} ({rlo:.3f}-{rhi:.3f}) "
              f"{kstest(data['p_recursive'][i], 'uniform').pvalue:>6.3f} | {below:>10.3f}")

    print("\nPre-registered decision (exact McNemar on naive rejections, one-sided, p < 0.05)")
    a, b, p_u = mcnemar(reject[2], reject[3], "greater")
    print(f"  U: rank 2 vs rank 3: {a}-{b}, p = {p_u:.4f} -> rank 3 {'falls below' if p_u < ALPHA else 'not separated from'} the top")
    a, b, p_l = mcnemar(reject[3], reject[10], "greater")
    print(f"  L: rank 3 vs rank 10: {a}-{b}, p = {p_l:.4f} -> rank 3 {'stays above' if p_l < ALPHA else 'not separated from'} the bottom")
    outcome = {(True, True): "graded: the audit uses a graded function of anchor rank",
               (True, False): "step after rank 2: the audit counts anchors at ranks 1-2",
               (False, True): "step after rank 3: the audit counts anchors at ranks 1-3",
               (False, False): "unresolved: n does not place rank 3; the audit's summary stays open"}[(p_u < ALPHA, p_l < ALPHA)]
    print(f"  OUTCOME: {outcome}")

    print("\nSecondary")
    a, b, p = mcnemar(reject[1], reject[2], "two-sided")
    print(f"  1. rank 1 vs rank 2 (limit: no difference): {a}-{b}, p = {p:.4f}")
    rates = [reject[rank].mean() for rank in RANKS]
    print(f"  4. naive point estimates nonincreasing in rank: {all(x >= y for x, y in zip(rates, rates[1:]))}")
    for first, second in ((5, 10), (10, 20)):
        a, b, p = mcnemar(reject[first], reject[second], "two-sided")
        print(f"     rank {first} vs rank {second}: {a}-{b}, p = {p:.4f}")
    lower_bounds = [type1_rate(data["p_recursive"][i], alpha=ALPHA)[1] for i in range(len(RANKS))]
    print(f"  3. recursive not significantly above 5% at any rank: {all(lo <= ALPHA for lo in lower_bounds)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/anchor_rank_checkpoints")
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
