"""The second version-2 pilot (`prereg/ml-v2-exploratory-2026-10-08.md`, "The second
version-2 pilot", 4688d5e). EXPLORATORY. Box only.

Tasks: `seed` (planted; 7 shapes x 50 seeds on 698000-698349, levels 1.0 and 1.5) and
`level0` (698400-698499). Per panel, version 2's base view is fitted once per memory
setting with the revised L grid {1, 3, 10, 30}; its books under G3 for memory sets M1 (all
three memories) and M2 (rolling 756, expanding) are priced, with version 1 and the plain
ridge, in two cost arms (registered; x5.0) and, on level-0 panels, at zero cost. Every
refit's penalties and stack weights (version 2 per memory, and version 1) and the capture
per memory setting are stored. Results are JSON rows; **nothing about any outcome is
printed.** The reader is `experiments/read_ml_v2_pilot2_2026_10_09.py`.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_pilot2_2026_10_09 --out runs/ml_v2_pilot2/2026-10-09 \\
        --workers 180 --wheel ~/WHEEL.whl --expect-head <commit>
Dry path (smoke block): ... --out runs/ml_v2_pilot2_dry/2026-10-09 --dry --workers 2 ...
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

NOTE_COMMIT = "4688d5e22ea7270dd658c6c173e89b42e5564507"
SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
SHAPE_SEEDS = {s: 698000 + 50 * i for i, s in enumerate(SHAPES)}
PER_SHAPE = 50
LEVELS = (1.0, 1.5)
LEVEL0 = range(698400, 698500)
DRY_BLOCK = range(696000, 697000)
DRY = {"seed": (696600, "product"), "level0": 696601}
B = 1000
L_GRID = {"L": (1.0, 3.0, 10.0, 30.0)}
RATES = (0.3, 0.1, 0.03)                       # G3
MEMORY_SETS = {"M1": ("roll252", "roll756", "expand"), "M2": ("roll756", "expand")}
COST_ARMS = {"registered": 1.0, "high": 5.0}
NEW_SHAPES = ("leadlag", "volcond", "regime")


def tasks() -> list[tuple]:
    out = [("seed", s, sh) for sh, s0 in SHAPE_SEEDS.items() for s in range(s0, s0 + PER_SHAPE)]
    return out + [("level0", s, None) for s in LEVEL0]


def dry_tasks() -> list[tuple]:
    s, sh = DRY["seed"]
    return [("seed", s, sh), ("level0", DRY["level0"], None)]


def _scaled(panel, m: float):
    return dataclasses.replace(panel, cost_rate=np.asarray(panel.cost_rate, float) * m,
                               borrow_rate=np.asarray(panel.borrow_rate, float) * m)


def price_panel(panel, seed: int, w_star=None, c: float = 0.0, arms=None) -> dict:
    """All streams in every arm for one panel; refit records; capture per memory."""
    from experiments import ml_v2_pilot_2026_10_08 as P1
    from experiments.ml_pilot_2026_10_07 import window_sharpes
    from learn import inputs as I1
    from learn import ridge_stack
    from learn2 import views as Vw
    W = P1._base()
    arms = arms or COST_ARMS
    inp_reg = P1._inputs(panel)
    cache = Vw.FitCache(inp_reg, grids=L_GRID)
    base = Vw.base_view(inp_reg.available)
    out = {"refits_v2": {}, "capture_by_memory": {}, "arms": {}}
    for mem in MEMORY_SETS["M1"]:
        f = cache.get(base[0], 5, "market", mem)
        out["refits_v2"][mem] = [{"refit": x["refit"], "penalties": x["penalties"], "stack": x["stack"],
                                  "at_edge": x["at_edge"]} for x in f["diagnostics"]]
        if c > 0:
            tgt = cache.target(base[0], 5, "market", mem)
            bk = np.mean([Vw.rate_book(tgt, a, f["first"]) for a in RATES], axis=0)
            rows = np.arange(f["first"], inp_reg.earned.shape[0])
            pop = window_sharpes(W["base"], panel, bk, w_star, c, rows)
            plant = window_sharpes(W["base"], panel, w_star, w_star, c, rows)
            out["capture_by_memory"][mem] = {"net": pop["net"] / plant["net"], "gross": pop["gross"] / plant["gross"]}
    v1 = ridge_stack.run(panel, "ridge_stack")
    rr = ridge_stack.run(panel, "control")
    out["refits_v1"] = [{"year": x["year"], "penalties": list(x["penalties"]), "stack": x["stack_weights"]}
                        for x in v1["diagnostics"]]
    books = {ms: Vw.view_book(cache, base, rates=RATES, memories=mems) for ms, mems in MEMORY_SETS.items()}
    for arm, m in arms.items():
        pan = _scaled(panel, m)
        inp = dataclasses.replace(inp_reg, cost_rate=np.asarray(pan.cost_rate, float),
                                  borrow_rate=np.asarray(pan.borrow_rate, float))
        bc = P1._bc(pan)
        rec = {}
        for ms, vb in books.items():
            rows = np.arange(vb["first"], inp.earned.shape[0])
            s = Vw.net_stream(vb["book"], inp, rows)
            r = P1._tier(s, bc[rows], inp.ppy, seed)
            r.update(Vw.turnover_stats(vb["book"], inp, rows))
            r["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
            corr = vb["variant_corr"]
            n = corr.shape[0] if corr is not None else 0
            r["variant_corr_mean"] = float(corr[np.triu_indices(n, 1)].mean()) if corr is not None else None
            if c > 0:
                r["pop"] = window_sharpes(W["base"], pan, vb["book"], w_star, c, rows)
                r["plant_window"] = window_sharpes(W["base"], pan, w_star, w_star, c, rows)
            rec[f"v2 base {ms}"] = r
        for name, res in (("version 1", v1), ("plain ridge", rr)):
            rows = res["scored_rows"]
            p = res["positions"]
            s = I1.net_stream(p, pan, rows)
            r = P1._tier(s, bc[rows], pan.periods_per_year, seed)
            r.update(Vw.turnover_stats(p, inp, rows))
            r["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
            if c > 0:
                r["pop"] = window_sharpes(W["base"], pan, p, w_star, c, rows)
                r["plant_window"] = window_sharpes(W["base"], pan, w_star, w_star, c, rows)
            rec[name] = r
        out["arms"][arm] = rec
    return out


def one(task) -> list[dict]:
    import environments.planted_panel as pp
    from environments import planted_rules as prl
    from experiments import ml_v2_pilot_2026_10_08 as P1
    kind, seed, shape = task
    W = P1._base()
    t0 = time.time()
    recs = []
    if kind == "seed":
        draws = P1._draws(seed, shape, LEVELS)
        w_star = draws[0].w_star_is
        for d in draws:
            recs.append({"kind": "seed", "seed": seed, "shape": shape, "rule": d.rule, "level": d.beta,
                         "c": d.c, "speed": prl.speed(w_star), "plant_turnover": prl.turnover(w_star),
                         **price_panel(d.in_sample, seed, w_star, d.c)})
    else:
        d = pp.make_draw(W["base"], seed, 0.0)
        recs.append({"kind": "level0", "seed": seed, "shape": None, "rule": None, "level": 0.0,
                     **price_panel(d.in_sample, seed, arms={**COST_ARMS, "zero": 0.0})})
    for r in recs:
        r["task_seconds"] = time.time() - t0
    return recs


def refusals(expect_head: str, wheel: str | None) -> list[str]:
    """The first pilot's refusals (Linux pins, v1 blobs, v2 inputs pin, clean tree, expected
    HEAD), plus this pilot's section as an ancestor of HEAD."""
    from experiments import ml_confirm_ridge_stack as C
    from experiments import ml_v2_pilot_2026_10_08 as P1
    bad = list(P1.refusals(expect_head, wheel))
    if C._git("merge-base", "--is-ancestor", NOTE_COMMIT, "HEAD").returncode != 0:
        bad.append(f"the second pilot's section {NOTE_COMMIT} is not an ancestor of HEAD")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=180)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--expect-head", required=True)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out / 'results.jsonl'} exists; not overwriting")
    from experiments import ml_v2_pilot_2026_10_08 as P1
    P1._base()
    todo = dry_tasks() if a.dry else tasks()
    todo.sort(key=lambda t: {"seed": 0, "level0": 1}[t[0]])
    import platform
    (out / "provenance.json").write_text(json.dumps(
        {"git_head": a.expect_head, "note": NOTE_COMMIT, "platform": f"{platform.system()} {platform.machine()}",
         "dry_run": a.dry, "tasks": len(todo), "workers": a.workers, "task_list": todo,
         "l_grid": L_GRID, "rates": RATES, "memory_sets": MEMORY_SETS, "cost_arms": COST_ARMS}, indent=1))
    t0 = time.time()
    done = 0
    with open(out / "results.jsonl.partial", "w") as fh, ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for f in as_completed(futs):
            for r in f.result():
                fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            done += 1
            print(f"{done}/{len(todo)} tasks, {time.time() - t0:.0f} s", flush=True)
    os.replace(out / "results.jsonl.partial", out / "results.jsonl")
    print(f"wall {time.time() - t0:.0f} s; {len(todo)} tasks; no outcome printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
