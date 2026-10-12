"""Refit records for the version-2 pilot's panels (descriptive; exploratory; already-read
panels; laptop). The pilot stored no per-refit penalties or stack weights, and no capture
per memory setting, so they are refitted here on a sample of its panels. This is
LAPTOP-platform work (arm64, the macOS LightGBM pin): the pilot ran on Linux, so trees
can differ in the last digits and a penalty choice can occasionally differ.

Panels (the pilot's own seeds and levels): all 50 product seeds at level 1.5
(697100-697149); the first 10 seeds of each other shape at level 1.5; level-0 seeds
697400-697429 at the registered cost. 140 panels.

Per panel:
- version 2's base view (P, X, V; h 5; market) under each memory setting: every refit's
  penalties (L, Q, I, S) and stack weights; on planted panels, the population net and
  gross capture of that memory's book (averaged over grid G3's three rates, ungated, as
  the base view is "always");
- version 1 (ridge_stack at fce5627): every refit's penalties and stack weights;
- a version-2 cell with version 1's design (P only, h 1, market, expanding): its refits'
  penalties, to compare 3-fold with version 1's leave-one-year-out choice.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_refit_records_2026_10_09 --out runs/ml_v2_refits/2026-10-09 --workers 4
"""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
LEVEL = 1.5


def panels() -> list[tuple]:
    from experiments.ml_v2_pilot_2026_10_08 import SHAPE_SEEDS
    out = []
    for sh, s0 in SHAPE_SEEDS.items():
        n = 50 if sh == "product" else 10
        out += [("planted", s, sh) for s in range(s0, s0 + n)]
    out += [("level0", s, None) for s in range(697400, 697430)]
    return out


def one(task) -> dict:
    import environments.planted_panel as pp
    from experiments import ml_v2_pilot_2026_10_08 as P
    from experiments.ml_pilot_2026_10_07 import window_sharpes
    from learn import ridge_stack
    from learn2 import views as Vw
    kind, seed, shape = task
    W = P._base()
    if kind == "planted":
        (d,) = P._draws(seed, shape, (LEVEL,))
        panel, w_star, c = d.in_sample, d.w_star_is, d.c
    else:
        d = pp.make_draw(W["base"], seed, 0.0)
        panel, w_star, c = d.in_sample, None, 0.0
    inp = P._inputs(panel)
    cache = Vw.FitCache(inp)
    base = Vw.base_view(inp.available)
    rec = {"kind": kind, "seed": seed, "shape": shape, "v2": {}, "capture_by_memory": {}}
    rates = Vw.RATE_GRIDS["G3"]
    for mem in ("roll252", "roll756", "expand"):
        f = cache.get(base[0], 5, "market", mem)
        rec["v2"][mem] = [{"refit": x["refit"], "penalties": x["penalties"], "stack": x["stack"]}
                          for x in f["diagnostics"]]
        if c > 0:
            tgt = cache.target(base[0], 5, "market", mem)
            book = np.mean([Vw.rate_book(tgt, a, f["first"]) for a in rates], axis=0)
            rows = np.arange(f["first"], inp.earned.shape[0])
            pop = window_sharpes(W["base"], panel, book, w_star, c, rows)
            plant = window_sharpes(W["base"], panel, w_star, w_star, c, rows)
            rec["capture_by_memory"][mem] = {"net": pop["net"] / plant["net"], "gross": pop["gross"] / plant["gross"]}
    v1 = ridge_stack.run(panel, "ridge_stack")
    rec["v1"] = [{"year": x["year"], "penalties": list(x["penalties"]), "stack": x["stack_weights"]}
                 for x in v1["diagnostics"]]
    g = cache.get(("P",), 1, "market", "expand")
    rec["v2_p_h1"] = [{"refit": x["refit"], "penalties": x["penalties"], "stack": x["stack"]}
                      for x in g["diagnostics"]]
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "refits.jsonl").exists():
        raise SystemExit("exists; not overwriting")
    with ProcessPoolExecutor(a.workers) as ex, open(out / "refits.jsonl", "w") as fh:
        for i, r in enumerate(ex.map(one, panels())):
            fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            print(f"{i + 1}/{len(panels())}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
