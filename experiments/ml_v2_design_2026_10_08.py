"""Version 2's outcome-free design quantities (`prereg/ml-v2-exploratory-2026-10-08.md`,
Part 5): level-0 planted ETF panels (seeds 696010-696012), null only, laptop.

Per panel:
- all 126 fit cells; the 294 views' averaged books, and each view's nine variant books
  ("chosen" fit settings), all regime-gated and costed;
- the menu tier's bar (95% of the joint-bootstrap maximum over the menu's DEMEANED streams;
  B 1,000, block length by the class rule on the base feature columns) for the nested
  menus, averaged and chosen:
      base (1 | 9), information x horizon (21 | 189), + neutrality (42 | 378),
      + regime (294 | 2,646);
  all streams on one common window, from the latest first scored row (756 + 20 + 1 + d) on;
- the effective number of independent views each bar implies: n solving
  Phi(bar / sd)^n = 0.95, where sd is the SD of the base view's own replicate Sharpe
  (a normal approximation);
- the base view's turnover and cost drag (cost per year / annualised volatility of its net
  stream; a dispersion, not a mean), raw and per unit of gross held, beside version 1's
  (ridge_stack at fce5627) on the same panel;
- seconds: fits, views, menu nulls.
And the projected compute for the pilot proposed in Part 6.

**Never computed, printed or stored:** a mean return, a Sharpe ratio of any stream, a
p-value or a certification.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_design_2026_10_08 --out runs/ml_v2_design/2026-10-08 --workers 4
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SEEDS = (696010, 696011, 696012)
NULL_SEED = {s: 696020 + i for i, s in enumerate(SEEDS)}
B = 1000
Q = 0.95


def fit_one(task):
    from experiments.ml_v2_smoke_2026_10_08 import inputs_for
    from learn2 import learner as Ln
    seed, cell = task
    inp = inputs_for(seed)
    t0 = time.time()
    f = Ln.fit_cell(inp, *cell)
    return seed, cell, {"pred": f["pred"], "refit_of": f["refit_of"], "first": f["first"],
                        "diagnostics": f["diagnostics"]}, time.time() - t0


def n_eff(bar: float, sd: float) -> float:
    from scipy.stats import norm
    F = norm.cdf(bar / sd)
    return float(np.log(Q) / np.log(F)) if 0 < F < 1 else float("inf")


def panel_quantities(seed: int, fits: dict, fit_seconds: float) -> dict:
    import environments.planted_panel as pp
    from environments.real_sandbox import RealSandbox
    from experiments.ml_v2_smoke_2026_10_08 import inputs_for
    from learn import ridge_stack
    from learn import inputs as I1
    from learn2 import states as S
    from learn2 import views as Vw
    from learn2 import timing
    inp = inputs_for(seed)
    cache = Vw.FitCache(inp)
    cache.fits.update(fits)
    T = inp.earned.shape[0]
    gates = S.regime_gates(S.market_states(inp.earned, inp.d))
    start = max(756 + timing.embargo(h, inp.d) for h in Vw.HORIZONS)
    rows = np.arange(start, T)
    av = inp.available
    views = Vw.all_views(av)
    t0 = time.time()
    avg_streams, chosen_streams, keys_avg, keys_chosen = [], [], [], []
    for v in views:
        vb = Vw.view_book(cache, v, gates)
        avg_streams.append(Vw.net_stream(vb["book"], inp, rows))
        keys_avg.append(v)
        g = gates[v[3]][:, None]
        for k, b in vb["variants"].items():
            chosen_streams.append(Vw.net_stream(b * g, inp, rows))
            keys_chosen.append((v, k))
    t_views = time.time() - t0
    avg_streams, chosen_streams = np.array(avg_streams), np.array(chosen_streams)
    d = pp.make_draw(pp.load_base(), seed, 0.0)
    bc = np.asarray(RealSandbox(d.in_sample, spec_class=pp.CLS).base_feature_columns(), float)[rows]
    base = Vw.base_view(av)
    menus = {
        "base": lambda v: v == base,
        "information x horizon": lambda v: v[2] == "market" and v[3] == "always",
        "+ neutrality": lambda v: v[3] == "always",
        "+ regime": lambda v: True,
    }
    out = {"seed": seed, "rows": [int(rows[0]), int(rows[-1])], "n_rows": int(len(rows)),
           "fit_seconds": fit_seconds, "view_seconds": t_views, "menus": {}}
    # the base view's own replicate Sharpe SD, for n_eff
    M1, L = Vw.menu_null(avg_streams[[keys_avg.index(base)]], bc, inp.ppy, B, NULL_SEED[seed])
    sd1 = float(M1.std(ddof=1))
    out["base_replicate_sd"] = sd1
    out["block_length"] = int(L)
    for name, sel in menus.items():
        ia = [i for i, v in enumerate(keys_avg) if sel(v)]
        ic = [i for i, (v, _) in enumerate(keys_chosen) if sel(v)]
        t1 = time.time()
        Ma, _ = Vw.menu_null(avg_streams[ia], bc, inp.ppy, B, NULL_SEED[seed])
        Mc, _ = Vw.menu_null(chosen_streams[ic], bc, inp.ppy, B, NULL_SEED[seed])
        ba, bc_ = float(np.quantile(Ma, Q)), float(np.quantile(Mc, Q))
        out["menus"][name] = {"n_averaged": len(ia), "n_chosen": len(ic), "bar_averaged": ba,
                              "bar_chosen": bc_, "n_eff_averaged": n_eff(ba, sd1),
                              "n_eff_chosen": n_eff(bc_, sd1), "seconds": time.time() - t1}
    # turnover and cost drag: base view against version 1
    bb = Vw.view_book(cache, base, gates)["book"]
    st = Vw.turnover_stats(bb, inp, rows)
    s = Vw.net_stream(bb, inp, rows)
    st["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
    st["cost_drag_sharpe"] = st["cost_per_year"] / st["ann_vol"] if st["ann_vol"] > 0 else float("nan")
    t1 = time.time()
    v1 = ridge_stack.run(d.in_sample, "ridge_stack")
    t_v1 = time.time() - t1
    p1 = v1["positions"]
    s1 = I1.net_stream(p1, d.in_sample, rows)
    st1 = Vw.turnover_stats(p1, inp, rows)
    st1["ann_vol"] = float(s1.std(ddof=1) * np.sqrt(inp.ppy))
    st1["cost_drag_sharpe"] = st1["cost_per_year"] / st1["ann_vol"] if st1["ann_vol"] > 0 else float("nan")
    st1["seconds"] = t_v1
    del s, s1
    out["base_view"] = st
    out["version_1"] = st1
    base_cells = [k for k in fits if k[0] == tuple(av) and k[1] == 5 and k[2] == "market"]
    out["base_view_fit_cells"] = [list(map(str, k)) for k in base_cells]
    return out


def main(argv=None) -> int:
    from experiments.ml_v2_smoke_2026_10_08 import cells, inputs_for
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L = []

    def P(s=""):
        L.append(s)
        print(s, flush=True)

    P("ML v2 design quantities (null only): level-0 planted ETF panels 696010-696012")
    P(f"platform {platform.system()} {platform.machine()}; workers {a.workers}; B {B}")
    P("=" * 88)
    cl = cells(inputs_for(SEEDS[0]).available)
    t0 = time.time()
    fits = {s: {} for s in SEEDS}
    secs = {s: 0.0 for s in SEEDS}
    cell_secs = []
    with ProcessPoolExecutor(a.workers) as ex:
        for seed, cell, f, sec in ex.map(fit_one, [(s, c) for s in SEEDS for c in cl]):
            fits[seed][(tuple(cell[0]), cell[1], cell[2], cell[3])] = f
            secs[seed] += sec
            cell_secs.append(("P" in cell[0], cell[1], sec))
    P(f"fits: {sum(len(v) for v in fits.values())} cells, {time.time() - t0:.0f} s wall")
    recs = [panel_quantities(s, fits[s], secs[s]) for s in SEEDS]
    names = list(recs[0]["menus"])
    P("")
    P("MENU TIER BAR at 95% (mean over panels [min, max]); effective independent views")
    P(f"{'menu':<24} {'n avg':>6} {'bar avg':>16} {'n_eff':>7} | {'n chosen':>8} {'bar chosen':>16} {'n_eff':>7}")
    summary = {}
    for nm in names:
        ba = [r["menus"][nm]["bar_averaged"] for r in recs]
        bc = [r["menus"][nm]["bar_chosen"] for r in recs]
        na = [r["menus"][nm]["n_eff_averaged"] for r in recs]
        nc = [r["menus"][nm]["n_eff_chosen"] for r in recs]
        m0 = recs[0]["menus"][nm]
        summary[nm] = {"bar_averaged": ba, "bar_chosen": bc, "n_eff_averaged": na, "n_eff_chosen": nc}
        P(f"{nm:<24} {m0['n_averaged']:>6} {np.mean(ba):6.3f} [{min(ba):.3f},{max(ba):.3f}] {np.mean(na):7.1f} | "
          f"{m0['n_chosen']:>8} {np.mean(bc):6.3f} [{min(bc):.3f},{max(bc):.3f}] {np.mean(nc):7.1f}")
    P(f"   base view replicate Sharpe SD (for n_eff): {np.mean([r['base_replicate_sd'] for r in recs]):.3f}; "
      f"window rows {recs[0]['rows']} ({recs[0]['n_rows']} rows); block length "
      f"{[r['block_length'] for r in recs]}")
    P("")
    P("TURNOVER AND COST DRAG (mean over panels): base view (averaged) vs version 1")
    for who in ("base_view", "version_1"):
        k = ["turnover_per_row", "mean_gross", "turnover_per_unit_gross", "cost_per_year", "ann_vol", "cost_drag_sharpe"]
        P(f"   {who:<10} " + "; ".join(f"{x} {np.mean([r[who][x] for r in recs]):.4f}" for x in k))
    P("")
    fit_cs = np.array([c[2] for c in cell_secs])
    per_panel_fit = float(np.mean([r["fit_seconds"] for r in recs]))
    per_panel_views = float(np.mean([r["view_seconds"] for r in recs]))
    per_panel_menu = float(np.mean([sum(m["seconds"] for m in r["menus"].values()) for r in recs]))
    base_fit = float(np.mean([c[2] for c in cell_secs if c[0] and c[1] == 5])) * 3
    v1_sec = float(np.mean([r["version_1"]["seconds"] for r in recs]))
    P("COMPUTE (laptop, cell-seconds)")
    P(f"   full 294-view menu on one panel: fits {per_panel_fit:.0f} s + views {per_panel_views:.0f} s "
      f"+ nulls (both menus, all four sizes) {per_panel_menu:.0f} s")
    P(f"   base view alone: about {base_fit:.0f} s of fits; version 1: {v1_sec:.0f} s per panel")
    planted = 7 * 50 * 4
    level0 = 100
    proj = planted * (base_fit + v1_sec + 2) + level0 * 2 * (base_fit + v1_sec + 2) + level0 * (per_panel_fit + per_panel_views + per_panel_menu / 4)
    P(f"   pilot projection (7 shapes x 50 seeds x levels 0.5/1.0/1.5/2.5 = {planted} planted panels with the three "
      f"declared streams; 100 level-0 panels at cost and zero cost; the full menu on the 100 zero-cost panels): "
      f"about {proj / 3600:.0f} laptop cell-hours; on 150 box workers about {proj / 3600 / 150 * 60:.0f} min with no "
      f"allowance, or {proj / 3600 / 150 * 1.8 * 60:.0f} min at 1.8x (version 1's pilot: ridge_stack 55 s per panel on "
      f"150 box workers against about 30 s on the laptop)")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps({"panels": recs, "summary": summary,
                                                 "cell_seconds": [list(map(float, c)) for c in cell_secs],
                                                 "projection_cell_hours": proj / 3600}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
