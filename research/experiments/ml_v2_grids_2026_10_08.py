"""Outcome-free turnover and cost drag of version 2's base view under the three trading-rate
grids (note, design change 2), beside version 1's, on the design panels 696010-696012
(level 0). The base view is market-neutral, so the re-pinned groups do not enter it.

Cost drag = cost per year / annualised volatility of the net stream (a dispersion, not a
mean). **No mean, Sharpe or p-value is computed.**

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_grids_2026_10_08 --out runs/ml_v2_grids/2026-10-08
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

SEEDS = (696010, 696011, 696012)


def main(argv=None) -> int:
    import environments.planted_panel as pp
    from experiments.ml_v2_smoke_2026_10_08 import inputs_for
    from learn import inputs as I1
    from learn import ridge_stack
    from learn2 import views as Vw
    from learn2 import timing
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rows_all, L = {}, []
    for seed in SEEDS:
        inp = inputs_for(seed)
        cache = Vw.FitCache(inp)
        base = Vw.base_view(inp.available)
        start = max(756 + timing.embargo(h, inp.d) for h in Vw.HORIZONS)
        rows = np.arange(start, inp.earned.shape[0])
        rec = {}
        for g, rates in Vw.RATE_GRIDS.items():
            bb = Vw.view_book(cache, base, rates=rates)["book"]
            st = Vw.turnover_stats(bb, inp, rows)
            s = Vw.net_stream(bb, inp, rows)
            st["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
            st["cost_drag_sharpe"] = st["cost_per_year"] / st["ann_vol"]
            rec[g] = st
        d = pp.make_draw(pp.load_base(), seed, 0.0)
        p1 = ridge_stack.run(d.in_sample, "ridge_stack")["positions"]
        st = Vw.turnover_stats(p1, inp, rows)
        s1 = I1.net_stream(p1, d.in_sample, rows)
        st["ann_vol"] = float(s1.std(ddof=1) * np.sqrt(inp.ppy))
        st["cost_drag_sharpe"] = st["cost_per_year"] / st["ann_vol"]
        rec["version 1"] = st
        rows_all[seed] = rec
    keys = ["turnover_per_row", "mean_gross", "turnover_per_unit_gross", "cost_per_year", "ann_vol", "cost_drag_sharpe"]
    L.append("Base view under three trading-rate grids vs version 1 (level-0 planted ETF panels 696010-696012; means)")
    L.append(f"{'':<10} " + " ".join(f"{k:>24}" for k in keys))
    for g in list(Vw.RATE_GRIDS) + ["version 1"]:
        L.append(f"{g:<10} " + " ".join(f"{np.mean([rows_all[s][g][k] for s in SEEDS]):>24.4f}" for k in keys))
    for g in Vw.RATE_GRIDS:
        L.append(f"   {g} = {Vw.RATE_GRIDS[g]}")
    text = "\n".join(L)
    (out / "grids.txt").write_text(text + "\n")
    (out / "grids.json").write_text(json.dumps({str(k): v for k, v in rows_all.items()}, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
