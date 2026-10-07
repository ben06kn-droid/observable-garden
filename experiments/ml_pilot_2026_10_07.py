"""The ML pilot (`prereg/ml-pipeline-exploratory-2026-10-07.md`, "The pilot", 2388f50).
EXPLORATORY: no claim rests on it. Runs on the box only (Linux x86_64, the pinned
manylinux LightGBM 4.7.0 wheel); refuses to run elsewhere unless --allow-laptop is given,
which is for a code check on a couple of panels and is never evidence.

Panels on 687000-687999:
  planted  U 687000-687049, corner 687050-687099, product 687100-687149,
           gated 687150-687199; each seed at levels 1.0, 1.5 and 2.5 (one residual draw
           and one set of rule features per seed, shared by its levels)
  level 0  687200-687299 at the registered cost, and the same panels at zero cost
           (cost_rate and borrow_rate zeroed; predictors only, no class tier)

Per panel, each predictor (control, ridge_stack, mv_combine risk on, mv_combine risk off)
is priced through the supplied-streams tier as one declared strategy (B 1,000, the panel's
seed, base columns on the scored rows). Beside it, on the at-cost panels, the class tier:
the fast kernel's class maximum against its class null (B 1,000, the panel's seed, the
whole in-sample window).

Recorded per panel and predictor: p and status; the population net and gross Sharpe of the
positions over the scored window, and the plant's over the same window (both books start
from zero at the window's first row, as `learn.inputs.net_stream` does); turnover; the
share of scored days the gross cap binds; mv_combine's per-refit c, effective parameters
and block weights; ridge_stack's per-refit penalties and stack weights. Per planted panel:
the rule, its fast/slow label, c, the plant's net and gross population Sharpe over all
in-sample rows, the class tier's p and maximum, and the panel's linear shadow share.

**No holdout quantity is computed** (the known defect of f41583b). **Nothing about any
outcome is printed**: the runner prints progress counts and seconds only. The reader is
`experiments/read_ml_pilot_2026_10_07.py`.

    python -m experiments.ml_pilot_2026_10_07 --out runs/ml_pilot/2026-10-07 --workers 150

A dry run of the same task path on the smoke block (checked by
`experiments/check_ml_pilot_dry.py`, which prints no outcome):

    python -m experiments.ml_pilot_2026_10_07 --out runs/ml_pilot_dry/2026-10-07 \
        --dry-seeds 686004 686005 --workers 2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import numpy as np

LEVELS = (1.0, 1.5, 2.5)
RULE_SEEDS = {"U": 687000, "corner": 687050, "product": 687100, "gated": 687150}
PER_RULE = 50
LEVEL0_SEEDS = range(687200, 687300)
CARRY_SEED = 687999                  # used by the reader, recorded here
B = 1000
CAP_TOL = 1e-9
LINUX_WHEEL_SHA256 = "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7"
PREDICTORS = ("control", "ridge_stack", "mv_combine risk on", "mv_combine risk off")


def tasks() -> list[tuple]:
    out = [("planted", s, shape) for shape, s0 in RULE_SEEDS.items()
           for s in range(s0, s0 + PER_RULE)]
    out += [("level0", s, None) for s in LEVEL0_SEEDS]
    return out


DRY_BLOCK = range(686000, 687000)            # the smoke block; never pilot panels


def dry_tasks(seeds, shape: str) -> list[tuple]:
    """One planted task (all three levels) on seeds[0] and one level-0 task (at cost and at
    zero cost) on seeds[1], both from the smoke block: the full task path, for a dry run."""
    a, b = (int(x) for x in seeds)
    if a == b or a not in DRY_BLOCK or b not in DRY_BLOCK:
        raise SystemExit("--dry-seeds takes two distinct seeds from the smoke block 686000-686999")
    if shape not in RULE_SEEDS:
        raise SystemExit(f"--dry-shape must be one of {list(RULE_SEEDS)}")
    return [("planted", a, shape), ("level0", b, None)]


def run_predictor(name: str, panel) -> dict:
    from learn import mv_combine, ridge_stack
    if name == "control":
        return ridge_stack.run(panel, "control")
    if name == "ridge_stack":
        return ridge_stack.run(panel, "ridge_stack")
    return mv_combine.run(panel, name.endswith("on"))


def window(panel, rows: np.ndarray):
    """The cost function and annualisation of `panel` on `rows` only."""
    return SimpleNamespace(cost_rate=np.asarray(panel.cost_rate, float)[rows],
                           borrow_rate=np.asarray(panel.borrow_rate, float)[rows],
                           periods_per_year=panel.periods_per_year)


def window_sharpes(base, panel, w, w_star, c, rows) -> dict:
    """Population net and gross Sharpe of positions `w` over `rows` under the draw's DGP,
    the book starting from zero at rows[0]."""
    import environments.planted_panel as pp
    from environments import planted_rules as prl
    win = window(panel, rows)
    return {"net": pp.population_sharpe(win, base.Sigma_is, w[rows], w_star[rows], c),
            "gross": prl.gross_population_sharpe(win, base.Sigma_is, w[rows], w_star[rows], c)}


def _diag(name: str, res: dict) -> list:
    keep = (("year", "c", "effective", "T_years", "weights", "abs_weight_by_block")
            if name.startswith("mv_combine") else ("year", "penalties", "stack_weights"))
    return [{k: d[k] for k in keep} for d in res["diagnostics"]]


def price(name: str, panel, base, w_star, c, seed) -> dict:
    from environments.real_sandbox import RealSandbox
    import environments.planted_panel as pp
    from environments import planted_rules as prl
    from learn import inputs as I
    from learn import mv_combine, stream_tier
    t0 = time.time()
    res = run_predictor(name, panel)
    rows = res["scored_rows"]
    pos = res["positions"]
    stream = I.net_stream(pos, panel, rows)
    bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
    st = stream_tier.certify(stream[None, :], bc[rows], panel.periods_per_year, B, seed)
    g = np.abs(pos[rows]).sum(axis=1)
    out = {"p": st["p"], "status": st["status"], "score": st["score"],
           "block_length": st["block_length"], "first_row": int(rows[0]),
           "n_rows": int(len(rows)), "warmup_dropped": res["warmup_dropped"],
           "turnover": prl.turnover(pos[rows]),
           "cap_binding_share": float(np.mean(g >= mv_combine.GROSS_CAP - CAP_TOL)),
           "pop": window_sharpes(base, panel, pos, w_star, c, rows),
           "diagnostics": _diag(name, res)}
    if c > 0:
        out["plant_window"] = window_sharpes(base, panel, w_star, w_star, c, rows)
    out["seconds"] = time.time() - t0
    return out


_W: dict = {}


def _init():
    if not _W:
        import environments.planted_panel as pp
        import environments.planted_fast as pf
        base = pp.load_base()
        _W.update(base=base, cache=pf.build(base.in_sample, base.members),
                  inv=pp.invariants_for(base))
    return _W


def _class_summary(d, obs, rep, L) -> dict:
    M_b = rep.max(axis=0)
    S = float(obs.max())
    return {"p": (1 + int(np.sum(M_b >= S))) / (len(M_b) + 1), "class_max": S,
            "null_max_mean": float(M_b.mean()), "block_length": int(L), "B": int(len(M_b))}


def one(task) -> list[dict]:
    import dataclasses
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments import planted_rules as prl
    kind, seed, shape = task
    W = _init()
    base, cache, inv = W["base"], W["cache"], W["inv"]
    t0 = time.time()
    recs = []
    if kind == "planted":
        rule = prl.draw_features(seed, shape)
        draws = [prl.make_draw_rule(base, seed, beta, shape, rule) for beta in LEVELS]
        classes, (Ea, Ea2, Eak) = pf.class_pass_draws(base, cache, seed, draws, B,
                                                      summary=_class_summary)
        w_star = draws[0].w_star_is
        tov, spd = prl.turnover(w_star), prl.speed(w_star)
        for d, cl in zip(draws, classes):
            panel = d.in_sample
            pop = pp.population_from_moments(Ea, Ea2, Eak, inv, d.c, panel.periods_per_year)
            rec = {"seed": seed, "kind": "planted", "rule": rule, "shape": shape,
                   "level": d.beta, "cost": "registered", "c": d.c,
                   "plant_turnover": tov, "speed": spd,
                   "plant_all_rows": {
                       "net": pp.population_sharpe(base.in_sample, base.Sigma_is, w_star,
                                                   w_star, d.c),
                       "gross": prl.gross_population_sharpe(base.in_sample, base.Sigma_is,
                                                            w_star, w_star, d.c)},
                   "shadow_share": float(pop.max() / d.beta), "class": cl,
                   "predictors": {n: price(n, panel, base, w_star, d.c, seed)
                                  for n in PREDICTORS}}
            recs.append(rec)
    else:
        d = pp.make_draw(base, seed, 0.0)
        classes, _ = pf.class_pass_draws(base, cache, seed, [d], B, summary=_class_summary)
        zero = np.zeros_like(np.asarray(d.in_sample.cost_rate, float))
        free = dataclasses.replace(d.in_sample, cost_rate=zero,
                                   borrow_rate=np.zeros_like(zero))
        for cost, panel, cl in (("registered", d.in_sample, classes[0]),
                                ("zero", free, None)):
            recs.append({"seed": seed, "kind": "level0", "rule": None, "shape": None,
                         "level": 0.0, "cost": cost, "c": 0.0, "class": cl,
                         "predictors": {n: price(n, panel, base, d.w_star_is, 0.0, seed)
                                        for n in PREDICTORS}})
    for r in recs:
        r["task_seconds"] = time.time() - t0
    return recs


def provenance() -> dict:
    import lightgbm
    lib = Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.so"
    if not lib.exists():
        lib = Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.dylib"
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    return {"platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "numpy": np.__version__,
            "lightgbm": lightgbm.__version__,
            "lib_lightgbm_sha256": hashlib.sha256(lib.read_bytes()).hexdigest(),
            "pinned_linux_wheel_sha256": LINUX_WHEEL_SHA256,
            "git_head": head, "tracked_changes": bool(dirty), "B": B,
            "carry_forward_seed": CARRY_SEED, "cpus": os.cpu_count()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=150)
    ap.add_argument("--limit", type=int, default=None, help="first n tasks (a code check)")
    ap.add_argument("--allow-laptop", action="store_true",
                    help="permit a non-Linux code check; its output is never evidence")
    ap.add_argument("--dry-seeds", nargs=2, type=int, default=None,
                    help="dry run: one planted and one level-0 task on two smoke-block seeds")
    ap.add_argument("--dry-shape", default="gated", help="the dry run's planted rule")
    a = ap.parse_args(argv)
    if a.dry_seeds and a.limit:
        raise SystemExit("--dry-seeds excludes --limit")
    prov = provenance()
    if prov["platform"] != "Linux x86_64" and not a.allow_laptop:
        raise SystemExit(f"the pilot runs on the box only (Linux x86_64); this is {prov['platform']}")
    if prov["tracked_changes"]:
        raise SystemExit("uncommitted changes to tracked files; the pilot runs committed code only")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "pilot.jsonl").exists():
        raise SystemExit(f"{out / 'pilot.jsonl'} exists; not overwriting")
    _init()                                          # build or open the cache once, before forking
    if a.dry_seeds:
        todo = dry_tasks(a.dry_seeds, a.dry_shape)
    else:
        todo = tasks()[:a.limit] if a.limit else tasks()
    (out / "provenance.json").write_text(json.dumps({**prov, "tasks": len(todo),
                                                     "workers": a.workers,
                                                     "dry_run": bool(a.dry_seeds),
                                                     "task_list": todo}, indent=1))
    t0 = time.time()
    done = 0
    with open(out / "pilot.jsonl.partial", "w") as fh, \
            ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for f in as_completed(futs):
            for r in f.result():
                fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            done += 1
            print(f"{done}/{len(todo)} tasks, {time.time() - t0:.0f} s", flush=True)
    os.replace(out / "pilot.jsonl.partial", out / "pilot.jsonl")
    print(f"wall {time.time() - t0:.0f} s; {len(todo)} tasks; results in {out}; no outcome printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
