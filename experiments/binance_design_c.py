"""Outcome-free design quantities for choosing the Binance bar size (draft
`prereg/binance-panel.md`, item C). Laptop; PROVISIONAL unpinned builds.

Variants: the 4h panel (formation 2021-10, scored 2022-01-01 to 2025-03-31) and the UTC
daily panel for formations 2020-09, 2021-01 and 2021-10 (data from the month after
formation to 2025-03-31; the 253-row warm-up lies inside that span; ppy 365).

For each variant, from ridge_stack's positions over its scored window:
- mean turnover per row: the mean over scored rows (after the first) of sum |w_t - w_{t-1}|;
- implied cost per year in return units at the panel's cost (10 bps one-way): the mean of
  the per-row cost over the same rows, times periods per year;
- the stream's annualised volatility (sd of the net stream x sqrt(ppy)); a dispersion, not
  a mean;
- cost drag in Sharpe units = cost per year / annualised volatility;
- the stream's null bar (demeaned stream, B 5,000, block length by the class rule) at 95%
  and 96%, the NET Sharpe certified with 80% power (Lo's iid formula with ppy), and the
  GROSS Sharpe needed = that net Sharpe + the cost drag;
- the share of gross held in dead contracts (mean over scored rows, by the dead status of
  the bar each position is held over).
For the daily variants, also the class null maximum at 95% and 96% (fast kernel, B 5,000).
And the universe counts: full-month traders, universe size, contracts dead in-sample.

**Never computed, printed or stored:** a mean return, a Sharpe, a p-value or any
certification. The stream's mean is removed before the bootstrap and never kept.

Seeds: stream nulls 695010-695013, class nulls 695020-695023 (block 695000-695999).

    python -m experiments.binance_design_c --out runs/binance_design_c/2026-10-08
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

B = 5000
QUANTILES = (0.95, 0.96)
VARIANTS = ("4h", "1d-2020-09", "1d-2021-01", "1d-2021-10")
SEED_STREAM = {v: 695010 + i for i, v in enumerate(VARIANTS)}
SEED_CLASS = {v: 695020 + i for i, v in enumerate(VARIANTS)}


def variant(name: str):
    """(panel, info, universe counts) for one variant, unpinned."""
    from data import fetch_binance as fb
    from data import fetch_binance_daily as fd
    from environments import binance_panel as bp
    if name == "4h":
        man = json.loads(fb.MANIFEST.read_text())
        panel, info = bp.build_binance_panel(pinned=False, with_info=True)
        n_full = sum(1 for f in man["formation"] if f["trading_days"] == 31)
        return panel, info, {"formation": "2021-10", "full_month_traders": n_full,
                             "universe": len(man["universe"])}
    f = name.split("-", 1)[1]
    man = json.loads(fd.MANIFEST.read_text())["formations"][f]
    d = fb.REPO / "data" / "raw" / f"binance_daily_{f}"
    panel, info = bp.build_binance_panel(symbols=man["universe"], directory=d, pinned=False,
                                         with_info=True, spec=bp.daily_spec(man["first_month"]))
    return panel, info, {"formation": f, "full_month_traders": man["full_month_traders"],
                         "universe": len(man["universe"])}


def stream_quantities(panel, info, seed: int) -> dict:
    from experiments.binance_design_quantities import certified_sharpe
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from learn import inputs as I
    from learn import ridge_stack, stream_tier
    ppy = float(panel.periods_per_year)
    t0 = time.time()
    res = ridge_stack.run(panel, "ridge_stack")
    t_run = time.time() - t0
    rows = res["scored_rows"]
    P = res["positions"][rows]
    dw = np.abs(np.diff(P, axis=0)).sum(axis=1)
    cost = I.cost_of(P, np.asarray(panel.cost_rate, float)[rows],
                     np.asarray(panel.borrow_rate, float)[rows])[1:]
    s = I.net_stream(res["positions"], panel, rows)
    vol = float(s.std(ddof=1) * np.sqrt(ppy))
    s = s - s.mean()
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    table = stream_tier.table_from_streams(s[None, :], ppy)
    del s
    brow, L = stream_tier.bootstrap_rows(bc[rows], B, seed)
    R_b = np.asarray(table.null_max(brow), float)
    alive = np.array([info[sym]["alive_earned"] for sym in panel.meta["symbols"]]).T   # (T, M)
    g = np.abs(P)
    dead_share = float(np.mean((g * ~alive[rows]).sum(axis=1) / np.maximum(g.sum(axis=1), 1e-300)))
    years = len(rows) / ppy
    cost_yr = float(cost.mean() * ppy)
    drag = cost_yr / vol if vol > 0 else float("nan")
    eo = panel.meta["earned_opens"]
    out = {"rows": int(len(rows)), "years": years, "first": eo[rows[0]], "last": eo[rows[-1]],
           "turnover_per_row": float(dw.mean()), "turnover_per_year": float(dw.mean() * ppy),
           "cost_per_year": cost_yr, "ann_vol": vol, "cost_drag_sharpe": drag,
           "dead_gross_share": dead_share, "block_length": int(L), "B": B, "seed": seed,
           "seconds_run": t_run, "bars": {}}
    for q in QUANTILES:
        bar = float(np.quantile(R_b, q))
        net = certified_sharpe(bar, years, ppy)
        out["bars"][str(q)] = {"bar": bar, "net_80": net, "gross_80": net + drag}
    return out


def class_quantities(panel, seed: int, name: str) -> dict:
    import environments.planted_fast as pf
    import experiments.french_design_quantities as fdq
    from experiments.binance_design_quantities import certified_sharpe
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    members = members_in_order(CLS, panel.features.shape[2])
    t0 = time.time()
    cache = pf.build(panel, members, name=f"binance-{name}-signed-3")
    t_build = time.time() - t0
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    fdq.B = B
    t0 = time.time()
    M_b, L = fdq.class_null(panel, cache, bc, seed)
    T = panel.features.shape[0]
    years = T / panel.periods_per_year
    out = {"rows": T, "years": years, "block_length": int(L), "seed": seed,
           "seconds_build": t_build, "seconds_null": time.time() - t0, "bars": {}}
    for q in QUANTILES:
        bar = float(np.quantile(M_b, q))
        out["bars"][str(q)] = {"bar": bar, "net_80": certified_sharpe(bar, years, panel.periods_per_year)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L, rec = [], {}

    def P(s=""):
        L.append(s)
        print(s, flush=True)

    P("Binance bar-size design quantities (outcome-free; provisional unpinned builds)")
    P(f"platform {platform.system()} {platform.machine()}")
    P("=" * 88)
    for v in VARIANTS:
        panel, info, u = variant(v)
        dead = sum(1 for x in info.values() if x["dead_bar"] is not None)
        st = stream_quantities(panel, info, SEED_STREAM[v])
        r = {"universe": {**u, "dead_in_sample": dead}, "stream": st}
        P(f"{v}: formation {u['formation']}: {u['full_month_traders']} full-month traders; universe "
          f"{u['universe']}; dead in-sample {dead}; ppy {panel.periods_per_year:.0f}")
        P(f"   ridge_stack scored {st['rows']} rows, {st['years']:.2f} years ({st['first'][:10]} .. {st['last'][:10]}); "
          f"block length {st['block_length']}; {st['seconds_run']:.0f} s per run")
        P(f"   turnover per row {st['turnover_per_row']:.4f} ({st['turnover_per_year']:.1f} per year); "
          f"cost per year {st['cost_per_year']:.4f}; annualised vol {st['ann_vol']:.4f}; "
          f"cost drag {st['cost_drag_sharpe']:.3f} Sharpe; gross share in dead contracts {st['dead_gross_share']:.4f}")
        for q, b in st["bars"].items():
            P(f"   stream bar {float(q):.2f}: {b['bar']:.3f}; net 80% {b['net_80']:.3f}; gross needed {b['gross_80']:.3f}")
        if v != "4h":
            c = class_quantities(panel, SEED_CLASS[v], v)
            r["class"] = c
            P(f"   class tier over {c['rows']} rows ({c['years']:.2f} years): " + "; ".join(
                f"{float(q):.2f} bar {b['bar']:.3f} net 80% {b['net_80']:.3f}" for q, b in c["bars"].items())
              + f"  (cache {c['seconds_build']:.0f} s, null {c['seconds_null']:.0f} s)")
        rec[v] = r
        del panel
    P("")
    P("C3. COMPARISON (ridge_stack stream; net and gross Sharpe needed for 80% power)")
    P(f"{'variant':<12} {'rows':>6} {'years':>6} {'dead':>5} {'drag':>6} {'net95':>7} {'gross95':>8} {'net96':>7} {'gross96':>8}")
    for v, r in rec.items():
        st = r["stream"]
        b5, b6 = st["bars"]["0.95"], st["bars"]["0.96"]
        P(f"{v:<12} {st['rows']:>6} {st['years']:>6.2f} {r['universe']['dead_in_sample']:>5} "
          f"{st['cost_drag_sharpe']:>6.3f} {b5['net_80']:>7.3f} {b5['gross_80']:>8.3f} {b6['net_80']:>7.3f} {b6['gross_80']:>8.3f}")
    (out / "design_c.txt").write_text("\n".join(L) + "\n")
    (out / "design_c.json").write_text(json.dumps(rec, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
