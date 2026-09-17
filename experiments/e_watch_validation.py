"""Step 5 bullets 1 and 2 of GARDEN_WATCH_PLAN.md: scripted searchers under Watch.

Pre-registered by the plan itself, committed at 499d66e before this ran. Its §5
fixes both readings:

  1. s = 0: submit-verdict type-I at or below nominal for every class size run.
  2. s = 3: realized power equals the preflight number at open, within Monte
     Carlo error.

Usage: python -m experiments.e_watch_validation [--workers N] [--checkpoint-dir DIR] [--smoke]

Two things about the readings, decided before running.

**Type-I counts PASS only.** A watched run can end PASS, FAIL, INADMISSIBLE or
DEGENERATE. Under s = 0 every PASS is a false positive, but INADMISSIBLE is a
refusal to certify, not a false positive -- and wide classes at T = 500 produce
many of them. Counting refusals as successes would make a cell that certifies
nothing look perfectly calibrated, so the INADMISSIBLE share is reported beside
the rate rather than folded into it.

**Bullet 2 pins the submission.** `power_at_reference` is power for a single
pre-specified strategy (SCOPE.md §13), not search power. Letting a searcher
choose its own winner folds search success into the comparison and measures
something else. PinnedSelector submits the true signal triple regardless of what
its menu found, so realized power isolates the estimator's response. The
reference Sharpe is the calibration target, which equals the pinned spec's own
analytic Sharpe exactly (verified: 0.5000 / 1.0000 / 2.0000).

The comparison in bullet 2 is between two different estimators of one quantity:
`power_at_reference` is the analytic Lo (2002) Sharpe sampling law evaluated
against the bootstrap critical value, while realized power is the PASS rate of a
full audit that re-estimates everything per replicate. A systematic gap is a
result about the preflight number, not a bug.
"""
from __future__ import annotations

import argparse
import pickle

import numpy as np

from environments.dgp import (
    DGPConfig, analytic_sharpe, calibrate_sigma, generate, oracle_sharpe_analytic,
)
from environments.sandbox import Sandbox
from estimator.metrics import wilson_ci
from experiments._parallel import run_cells
from experiments.e18_depth import git_state
from garden import watch as watch_mod
from garden.spec_class import SubsetClass
from searchers.diagnostic import LatticeAdaptive, PinnedSelector
from searchers.scripted import Adaptive, Greedy, GridSearch

M, T, T_OOS = 50, 500, 250
B, ALPHA = 2000, 0.05
N_DRAWS, SEED0, BLOCK = 400, 70_000, 50
POWER_FLOOR = 0.20
OUTPUT = "figures/e_watch_validation_data.pkl"

# Bullet 1: (K, d, searcher). Every searcher stays inside its class by
# construction -- confirmed before running; the sandbox would raise otherwise.
NULL_CELLS = (
    (10, 1, "greedy"),
    (10, 2, "adaptive"),
    (10, 3, "adaptive"),
    (10, 3, "gridsearch"),
    (10, 3, "lattice"),
    (20, 2, "adaptive"),
    (20, 3, "gridsearch"),
)

# Bullet 2: (K, d, target Sharpe). PinnedSelector throughout.
POWER_CELLS = (
    (10, 3, 0.5),
    (10, 3, 1.0),
    (10, 3, 2.0),
    (20, 3, 1.0),
    (20, 3, 2.0),
)


def build_searcher(name: str, d: int, seed: int, pinned=None):
    if name == "greedy":
        return Greedy(seed=seed)
    if name == "adaptive":
        return Adaptive(max_features=d, seed=seed)
    if name == "gridsearch":
        return GridSearch(subset_sizes=tuple(range(1, d + 1)), max_trials=None, seed=seed)
    if name == "lattice":
        return LatticeAdaptive(max_features=d, seed=seed)
    if name == "pinned":
        return PinnedSelector(pinned_weights=pinned, subset_sizes=tuple(range(1, d + 1)),
                              max_trials=None, seed=seed)
    raise ValueError(f"unknown searcher {name!r}")


def null_draw(K: int, d: int, searcher: str, T: int, seed: int) -> dict:
    """One s = 0 run under watch, start to verdict."""
    cls = SubsetClass(max_size=d)
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    sandbox = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year, spec_class=cls)
    w = watch_mod.open(sandbox, cls, alpha=ALPHA, reference_sharpe=1.0,
                       power_floor=POWER_FLOOR, B=B, seed=seed)
    build_searcher(searcher, d, seed).run(w.sandbox)
    v = w.submit()
    return {
        "status": v.status,
        "p_value": float(v.p_value),
        "sr_reported": float(v.sr_reported),
        "critical_value": float(v.critical_value),
        "power_at_open": float(w.state.power_at_reference),
        "open_status": w.state.status,
        "class_size": int(w.state.class_size),
        "n_evaluated": int(v.n_trials),
    }


def power_draw(K: int, d: int, target: float, T: int, seed: int) -> dict:
    """One s = 3 run with the submission pinned to the true triple."""
    cls = SubsetClass(max_size=d)
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=0.0, sigma=1.0, seed=seed)
    sigma = calibrate_sigma(target, template)
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=0.0, sigma=sigma, seed=seed)
    data = generate(cfg)
    pinned = np.zeros(K)
    pinned[data.S] = 1.0

    sandbox = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    # reference_sharpe is the pinned spec's own true Sharpe, so power at open is
    # the quantity realized power is meant to reproduce.
    w = watch_mod.open(sandbox, cls, alpha=ALPHA, reference_sharpe=target,
                       power_floor=POWER_FLOOR, B=B, seed=seed)
    build_searcher("pinned", d, seed, pinned=pinned).run(w.sandbox)
    v = w.submit()
    return {
        "status": v.status,
        "p_value": float(v.p_value),
        "sr_reported": float(v.sr_reported),
        "power_at_open": float(w.state.power_at_reference),
        "open_status": w.state.status,
        "class_size": int(w.state.class_size),
        "oracle": float(oracle_sharpe_analytic(cfg)),
        "pinned_true_sharpe": float(analytic_sharpe(cfg, pinned)),
    }


FIELDS_NULL = ("status", "p_value", "sr_reported", "critical_value", "power_at_open",
               "open_status", "class_size", "n_evaluated")
FIELDS_POWER = ("status", "p_value", "sr_reported", "power_at_open", "open_status",
                "class_size", "oracle", "pinned_true_sharpe")


def run(n_draws: int, workers, checkpoint_dir, git: dict, T_run: int) -> dict:
    """T_run is carried in every task tuple and every cell key.

    In the key because `_parallel._checkpoint_path` derives filenames from it:
    without T there, a second pass at a different sample length would silently
    reload the first pass's checkpoints and report them as new results. In the
    tuple because macOS spawns workers by re-importing this module, so a
    module-level override in the parent would never reach them."""
    cells = {}
    for K, d, s in NULL_CELLS:
        for start in range(0, n_draws, BLOCK):
            cells[("null", K, d, s, T_run, start)] = [
                (K, d, s, T_run, SEED0 + i) for i in range(start, min(start + BLOCK, n_draws))]
    for K, d, tgt in POWER_CELLS:
        for start in range(0, n_draws, BLOCK):
            cells[("power", K, d, tgt, T_run, start)] = [
                (K, d, tgt, T_run, SEED0 + 500_000 + i)
                for i in range(start, min(start + BLOCK, n_draws))]

    out = run_cells(_dispatch, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    data = {"git_at_launch": git, "settings": {"M": M, "T": T_run, "T_oos": T_OOS, "B": B,
                                               "alpha": ALPHA, "draws": n_draws,
                                               "power_floor": POWER_FLOOR},
            "null_cells": NULL_CELLS, "power_cells": POWER_CELLS}
    for K, d, s in NULL_CELLS:
        rows = [r for start in range(0, n_draws, BLOCK)
                for r in out[("null", K, d, s, T_run, start)]]
        data[("null", K, d, s)] = {f: np.array([r[f] for r in rows]) for f in FIELDS_NULL}
    for K, d, tgt in POWER_CELLS:
        rows = [r for start in range(0, n_draws, BLOCK)
                for r in out[("power", K, d, tgt, T_run, start)]]
        data[("power", K, d, tgt)] = {f: np.array([r[f] for r in rows]) for f in FIELDS_POWER}
    return data


def _dispatch(*task):
    """run_cells applies one function to every task; the third element says
    which draw this is (a searcher name for null, a target Sharpe for power).
    Module level so worker processes can import it."""
    if isinstance(task[2], str):
        return null_draw(*task)
    return power_draw(*task)


def report(data: dict) -> None:
    n = data["settings"]["draws"]
    # From settings, not the module constant: a second pass at a different
    # sample length must be identifiable from its own output alone.
    T_run = data["settings"]["T"]
    print(f"\nn={n} draws per cell, M={M}, T={T_run}, B={B}, alpha={ALPHA}; "
          f"git at launch {data['git_at_launch']['commit'][:7]}")

    print("\n" + "=" * 78)
    print("Bullet 1 - s=0: submit-verdict type-I at or below nominal")
    print("=" * 78)
    print(f"{'K':>3} {'d':>2} {'searcher':>11} {'class':>7} {'PASS':>6} "
          f"{'type-I (95% CI)':>22} {'INADM':>7} {'<= 5%?':>7}")
    null_ok = True
    for K, d, s in NULL_CELLS:
        c = data[("null", K, d, s)]
        status = c["status"]
        n_pass = int((status == "PASS").sum())
        rate = n_pass / len(status)
        lo, hi = wilson_ci(n_pass, len(status))
        inadm = float((status == "INADMISSIBLE").mean())
        # Pre-registered rule is one-sided: at or below nominal.
        ok = lo <= ALPHA
        null_ok &= ok
        print(f"{K:>3} {d:>2} {s:>11} {int(c['class_size'][0]):>7} {n_pass:>6} "
              f"{rate:>8.3f} ({lo:.3f}-{hi:.3f}) {inadm:>7.1%} {'yes' if ok else 'NO':>7}")

    print("\n" + "=" * 78)
    print("Bullet 2 - s=3: realized power against the preflight number at open")
    print("=" * 78)
    print(f"{'K':>3} {'d':>2} {'target':>7} {'class':>7} {'predicted':>10} "
          f"{'realized (95% CI)':>24} {'gap':>7} {'agrees?':>8}")
    power_ok = True
    for K, d, tgt in POWER_CELLS:
        c = data[("power", K, d, tgt)]
        status = c["status"]
        n_pass = int((status == "PASS").sum())
        rate = n_pass / len(status)
        lo, hi = wilson_ci(n_pass, len(status))
        predicted = float(np.mean(c["power_at_open"]))
        agrees = lo <= predicted <= hi
        power_ok &= agrees
        print(f"{K:>3} {d:>2} {tgt:>7.2f} {int(c['class_size'][0]):>7} {predicted:>10.3f} "
              f"{rate:>10.3f} ({lo:.3f}-{hi:.3f}) {rate - predicted:>+7.3f} "
              f"{'yes' if agrees else 'NO':>8}")

    print("\nPre-registered decisions (GARDEN_WATCH_PLAN.md §5)")
    print(f"  1. s=0 type-I at or below nominal in every cell: {null_ok}")
    print(f"  2. s=3 realized power contains the preflight number in every cell: {power_ok}")
    print(f"\nAt n={n} the Wilson half-width at 5% is about "
          f"{(wilson_ci(int(0.05 * n), n)[1] - wilson_ci(int(0.05 * n), n)[0]) / 2:.3f}: "
          f"enough for the one-sided rule above, not enough to separate 5% from 6%.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--workers", type=int)
    p.add_argument("--T", type=int, default=T, help="in-sample periods (default 500)")
    p.add_argument("--checkpoint-dir", default=".cache/e_watch_validation_checkpoints")
    p.add_argument("--smoke", action="store_true", help="8 draws per cell, nothing saved")
    a = p.parse_args()
    git = git_state()
    if a.smoke:
        report(run(8, a.workers, None, git, a.T))
        return
    data = run(N_DRAWS, a.workers, a.checkpoint_dir, git, a.T)
    report(data)
    out = OUTPUT if a.T == T else OUTPUT.replace("_data.pkl", f"_T{a.T}_data.pkl")
    with open(out, "wb") as f:
        pickle.dump(data, f)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
