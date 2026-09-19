"""non-additive-scoring: does winner-chasing inflate the naive test when the scoring is not additive?

Pre-registered at f298103, before this ran. Moving-average crossover rules on driftless
random walks: a rule's position is the sign of a difference of moving averages, so no rule's return stream
is a linear combination of the others and the recursive bootstrap does not apply.

Five nulls per draw, from one pass over a shared set of circular shifts plus two bootstrap runs:

  naive (winner)      Reality Check on the rules the winner-anchored search logged
  naive (loser)       the same for the loser-anchored search
  procedure-level     the search re-executed on each shifted surrogate, per searcher
  explicit class      the class maximum on the SAME shifts (exact P3 check)
  explicit class      the Reality Check over the whole class (the gate's own path)

The shift arms take the search's selected value and the class maximum from one Sharpe vector per shift, so
both sides of the P3 inequality come from the same engine and ties cannot register as violations.

Usage: python -m experiments.non_additive_scoring [--workers N] [--checkpoint-dir DIR] [--smoke]
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np
from scipy.stats import binomtest, kstest

from environments.prices import (
    draw_shifts, forward_returns, panel, returns_from_positions, rule_positions, shifted_surrogate,
    simulate_walk,
)
from estimator.bootstrap import select_block_length
from estimator.metrics import type1_rate
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden._engine import null_max_bootstrap
from searchers.crossover import AdaptiveCrossover, CrossoverGrid

T, WARMUP, EXCLUDE = 5040, 200, 200
B, RERUN_B, ALPHA = 1500, 500, 0.05
N_DRAWS, SEED0, BLOCK = 2000, 80_000, 25
SHIFT_SEED_OFFSET = 1_000_000
PANEL_ASSETS = 5
TOLERANCE = 1e-10          # non-additive-scoring's prereg, f298103: violations smaller than this are floating-point ties
AGREEMENT_THRESHOLD = 0.99
ANN = np.sqrt(252)
WORLDS = {"single": 1, "panel": PANEL_ASSETS}
ANCHORS = ("winner", "loser")
FIELDS = ("p_naive_winner", "p_naive_loser", "p_proc_winner", "p_proc_loser", "p_class_shift",
          "p_class_boot", "violations_winner", "violations_loser", "sr_winner", "sr_loser",
          "menu_winner", "menu_loser", "block_length")
OUTPUT = "figures/non_additive_scoring_data.pkl"


def all_sharpes(R: np.ndarray) -> np.ndarray:
    mu, sd = R.mean(axis=0), R.std(axis=0, ddof=1)
    return np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), 0.0) * ANN


def p_value(null: np.ndarray, statistic: float) -> float:
    return float((1 + np.sum(null >= statistic)) / (len(null) + 1))


def run_draw(world: str, seed: int) -> dict:
    grid = CrossoverGrid()
    rules = grid.rules
    rng = np.random.default_rng(seed)
    n_assets = WORLDS[world]
    if n_assets == 1:
        r = simulate_walk(T, rng, WARMUP)
        P, fwd = rule_positions(r, rules, WARMUP), forward_returns(r, WARMUP)
    else:
        P, fwd = panel(n_assets, T, rules, WARMUP, rng)

    R = returns_from_positions(P, fwd)
    real = all_sharpes(R)
    # blocks=n_assets: the coarse round spans every asset, so the search can reach the whole declared class.
    searchers = {a: AdaptiveCrossover(grid, anchor=a, blocks=n_assets) for a in ANCHORS}
    picks, menus = {}, {}
    for anchor in ANCHORS:
        res = searchers[anchor].run_from_sharpes(real)     # `real` is already computed; one vector, one engine
        picks[anchor], menus[anchor] = res.selected, res.evaluated

    # A well-separated stream: seed + 1 would draw shifts from the stream the next draw uses for prices.
    shifts = draw_shifts(R.shape[0], EXCLUDE, RERUN_B, np.random.default_rng(seed + SHIFT_SEED_OFFSET))
    proc = {a: np.empty(len(shifts)) for a in ANCHORS}
    class_shift = np.empty(len(shifts))
    violations = {a: 0 for a in ANCHORS}
    for i, shift in enumerate(shifts):
        surrogate = shifted_surrogate(P, fwd, int(shift))
        s_all = all_sharpes(surrogate)                       # one engine for both sides of the inequality
        class_shift[i] = float(s_all.max())
        for anchor in ANCHORS:
            sel = searchers[anchor].run_from_sharpes(s_all).selected
            proc[anchor][i] = float(s_all[sel])
            if proc[anchor][i] > class_shift[i] + TOLERANCE:
                violations[anchor] += 1

    # One block length for every bootstrap null, taken from the class, as in graded-coupling through unequal-correlation.
    block = int(select_block_length(R - R.mean(axis=0)))
    naive = {a: null_max_bootstrap(R[:, list(menus[a])], B=B, block_length=block, annualization=ANN,
                                   seed=seed).M_b for a in ANCHORS}
    class_boot = null_max_bootstrap(R, B=B, block_length=block, annualization=ANN, seed=seed).M_b

    sr = {a: float(real[picks[a]]) for a in ANCHORS}
    return {
        "p_naive_winner": p_value(naive["winner"], sr["winner"]),
        "p_naive_loser": p_value(naive["loser"], sr["loser"]),
        "p_proc_winner": p_value(proc["winner"], sr["winner"]),
        "p_proc_loser": p_value(proc["loser"], sr["loser"]),
        "p_class_shift": p_value(class_shift, sr["winner"]),
        "p_class_boot": p_value(class_boot, sr["winner"]),
        "violations_winner": violations["winner"], "violations_loser": violations["loser"],
        "sr_winner": sr["winner"], "sr_loser": sr["loser"],
        "menu_winner": len(menus["winner"]), "menu_loser": len(menus["loser"]),
        "block_length": block,
    }


def run(n_draws: int, workers: int | None, checkpoint_dir: str | None, git: dict) -> dict:
    cells = {
        (world, start): [(world, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
        for world in WORLDS for start in range(0, n_draws, BLOCK)
    }
    out = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"seeds": SEED0 + np.arange(n_draws), "git_at_launch": git, "settings": {
        "T": T, "B": B, "rerun_B": RERUN_B, "alpha": ALPHA, "draws": n_draws, "worlds": dict(WORLDS)}}
    for world in WORLDS:
        rows = [d for start in range(0, n_draws, BLOCK) for d in out[(world, start)]]
        data[world] = {field: np.array([row[field] for row in rows]) for field in FIELDS}
    return data


def report(data: dict) -> None:
    git = data["git_at_launch"]
    n = data["settings"]["draws"]
    print(f"\nn={n} draws per world, T={T}, B={B}, rerun_B={RERUN_B}; "
          f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}")
    for world in WORLDS:
        rows = data[world]
        print(f"\n=== {world} ({WORLDS[world]} asset(s))")
        print(f"{'null':>22} {'type-I (95% CI)':>22} {'KS p':>7}")
        for label, key in (("naive, winner-anchored", "p_naive_winner"), ("naive, loser-anchored", "p_naive_loser"),
                           ("procedure-level winner", "p_proc_winner"), ("procedure-level loser", "p_proc_loser"),
                           ("explicit class, shifts", "p_class_shift"), ("explicit class, bootstrap", "p_class_boot")):
            rate, lo, hi = type1_rate(rows[key], alpha=ALPHA)
            print(f"{label:>22} {rate:>10.3f} ({lo:.3f}-{hi:.3f}) {kstest(rows[key], 'uniform').pvalue:>7.3f}")

        print("  Pre-registered decisions")
        lo_proc = type1_rate(rows["p_proc_winner"], alpha=ALPHA)[1]
        print(f"    1. procedure-level nominal (Wilson lower <= 5%): {lo_proc <= ALPHA} (lower bound {lo_proc:.3f})")

        ge = rows["p_class_shift"] >= rows["p_proc_winner"]
        shift_viol = int(rows["violations_winner"].sum())
        print(f"    2. explicit-class shift p >= procedure-level p on every draw: {bool(ge.all())} "
              f"({int((~ge).sum())} exceptions); per-shift violations beyond {TOLERANCE:g}: {shift_viol}")

        rate, lo, hi = type1_rate(rows["p_class_boot"], alpha=ALPHA)
        agree = float(np.mean((rows["p_class_boot"] < ALPHA) == (rows["p_class_shift"] < ALPHA)))
        print(f"    3. explicit-class bootstrap valid (upper CI {hi:.3f} vs 5%): {hi <= ALPHA or lo <= ALPHA <= hi}; "
              f"decisions agree with the shift version on {agree:.3f} (threshold {AGREEMENT_THRESHOLD})")

        for rule, label, key, predicted in ((4, "winner", "p_naive_winner", "inflated"),
                                            (5, "loser", "p_naive_loser", "at or below nominal")):
            k = int((rows[key] < ALPHA).sum())
            p_high = binomtest(k, n, ALPHA, alternative="greater").pvalue
            p_two = binomtest(k, n, ALPHA).pvalue
            rate = k / n
            if p_high < ALPHA:
                outcome = "inflated"
            elif rate < ALPHA and p_two < ALPHA:
                outcome = "conservative"
            else:
                outcome = "not detectably inflated"
            print(f"    {rule}. naive {label} ({k}/{n} = {rate:.3f}, predicted {predicted}): binomial p = "
                  f"{p_high:.4f} -> {outcome}")

        class_width = len(CrossoverGrid().rules) * WORLDS[world]
        print(f"  Secondary: menu sizes {rows['menu_winner'].mean():.1f} winner / {rows['menu_loser'].mean():.1f} "
              f"loser of {class_width}; block length "
              f"{np.bincount(rows['block_length'].astype(int)).argmax()} most often")
        a, b = rows["p_naive_winner"] < ALPHA, rows["p_naive_loser"] < ALPHA
        x, y = int(np.sum(a & ~b)), int(np.sum(~a & b))
        p_mc = binomtest(x, x + y, 0.5).pvalue if x + y else 1.0
        print(f"             naive winner vs loser, paired: {x}-{y}, exact McNemar p = {p_mc:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int)
    parser.add_argument("--checkpoint-dir", default=".cache/non_additive_scoring_checkpoints")
    parser.add_argument("--smoke", action="store_true", help="4 draws per world, no checkpoints, nothing saved")
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
