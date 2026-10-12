"""The version-2 confirmation (`prereg/ml-v2-confirmation.md`, live at
083c734724340b0d1ae7f6bfd98b0a61e23fe84c). Box only.

Tasks: `seed` (7 shapes x 80 seeds on 699000-699559, levels 1.0 and 1.5) and `level0`
(700000-700399). Per panel: version 2's base view as registered (P, X, V; h 5; market;
always; memory set M2 = rolling 756 and expanding; rate grid G3; L grid {1, 3, 10, 30}),
version 1 and the plain ridge, priced as single declared strategies in the registered and
the x5.0 cost arms (and at zero cost on level-0 panels); the class tier beside them at
the registered cost. Per-refit penalties and stack weights, and capture per memory, are
stored. **Nothing about any outcome is printed.** The reader is
`experiments/read_ml_v2_confirm_2026_10_09.py`.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_confirm_2026_10_09 --out runs/ml_v2_confirm/2026-10-09 \\
        --workers 180 --wheel ~/WHEEL.whl --expect-head <commit>
Dry path (699900-699909): ... --out runs/ml_v2_confirm_dry/2026-10-09 --dry --workers 2 ...
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

REGISTRATION = "083c734724340b0d1ae7f6bfd98b0a61e23fe84c"
PINNED_V2 = {"learn2/__init__.py": "4154f7f48affe0885fb361ffc309d09b0a4a566d",
             "learn2/timing.py": "bf55de9216cb7c822372b5d00ac67ddac6dfb652",
             "learn2/blocks.py": "7c39985f8fbb29eca16a268aecdf064ebf46b176",
             "learn2/states.py": "9060fdf0364fa4f00befeee79213b5a12de06bc6",
             "learn2/learner.py": "522627305a0f7b6ddb48f708c54b6709c129c363",
             "learn2/views.py": "232a79fb8ddb1f87a7ce7c42da1110b3d0a225df",
             "environments/etf_v2_inputs.py": "4c7837153bba98b302092b4f5265818a6eb1a226",
             "environments/planted_rules.py": "9b83867e3c4cf472c50651e0bf1ab050c1864171"}
SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
SHAPE_SEEDS = {s: 699000 + 80 * i for i, s in enumerate(SHAPES)}
PER_SHAPE = 80
LEVELS = (1.0, 1.5)
LEVEL0 = range(700000, 700400)
DRY_BLOCK = range(699900, 699910)
DRY = {"seed": (699900, "volcond"), "level0": 699901}
B = 1000
L_GRID = {"L": (1.0, 3.0, 10.0, 30.0)}
RATES = (0.3, 0.1, 0.03)                        # G3
MEMORIES = ("roll756", "expand")                # M2
COST_ARMS = {"registered": 1.0, "high": 5.0}
STREAMS = ("v2 base", "version 1", "plain ridge")


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
    for mem in MEMORIES:
        f = cache.get(base[0], 5, "market", mem)
        out["refits_v2"][mem] = [{"refit": x["refit"], "penalties": x["penalties"], "stack": x["stack"]}
                                 for x in f["diagnostics"]]
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
    vb = Vw.view_book(cache, base, rates=RATES, memories=MEMORIES)
    for arm, m in arms.items():
        pan = _scaled(panel, m)
        inp = dataclasses.replace(inp_reg, cost_rate=np.asarray(pan.cost_rate, float),
                                  borrow_rate=np.asarray(pan.borrow_rate, float))
        bc = P1._bc(pan)
        rec = {}
        rows = np.arange(vb["first"], inp.earned.shape[0])
        s = Vw.net_stream(vb["book"], inp, rows)
        r = P1._tier(s, bc[rows], inp.ppy, seed)
        r.update(Vw.turnover_stats(vb["book"], inp, rows))
        r["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
        if c > 0:
            r["pop"] = window_sharpes(W["base"], pan, vb["book"], w_star, c, rows)
            r["plant_window"] = window_sharpes(W["base"], pan, w_star, w_star, c, rows)
        rec["v2 base"] = r
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
    import environments.planted_fast as pf
    from environments import planted_rules as prl
    from experiments import ml_v2_pilot_2026_10_08 as P1
    kind, seed, shape = task
    W = P1._base()
    t0 = time.time()
    recs = []
    if kind == "seed":
        draws = P1._draws(seed, shape, LEVELS)
        classes, _ = pf.class_pass_draws(W["base"], W["cache"], seed, draws, B, summary=P1.class_summary)
        w_star = draws[0].w_star_is
        for d, cl in zip(draws, classes):
            recs.append({"kind": "seed", "seed": seed, "shape": shape, "rule": d.rule, "level": d.beta,
                         "c": d.c, "speed": prl.speed(w_star), "plant_turnover": prl.turnover(w_star),
                         "class": cl, **price_panel(d.in_sample, seed, w_star, d.c)})
    else:
        d = pp.make_draw(W["base"], seed, 0.0)
        classes, _ = pf.class_pass_draws(W["base"], W["cache"], seed, [d], B, summary=P1.class_summary)
        recs.append({"kind": "level0", "seed": seed, "shape": None, "rule": None, "level": 0.0,
                     "class": classes[0], **price_panel(d.in_sample, seed, arms={**COST_ARMS, "zero": 0.0})})
    for r in recs:
        r["task_seconds"] = time.time() - t0
    return recs


def refusals(expect_head: str, wheel: str | None) -> list[str]:
    """Linux pins, version 1's blobs, clean tree, HEAD (the first pilot's refusals), plus
    version 2's pinned blobs and this registration as an ancestor of HEAD."""
    from experiments import ml_confirm_ridge_stack as C
    from experiments import ml_v2_pilot_2026_10_08 as P1
    bad = list(P1.refusals(expect_head, wheel))
    for f, blob in PINNED_V2.items():
        got = C._git("rev-parse", f"HEAD:{f}").stdout.strip()
        if got != blob:
            bad.append(f"{f}: blob {got or 'missing'} is not the pinned {blob}")
    if C._git("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode != 0:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
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
    import platform
    (out / "provenance.json").write_text(json.dumps(
        {"git_head": a.expect_head, "registration": REGISTRATION, "dry_run": a.dry,
         "platform": f"{platform.system()} {platform.machine()}", "tasks": len(todo), "workers": a.workers,
         "task_list": todo, "l_grid": L_GRID, "rates": RATES, "memories": MEMORIES, "cost_arms": COST_ARMS,
         "pinned_v2": PINNED_V2}, indent=1))
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
