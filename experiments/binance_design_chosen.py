"""Outcome-free design quantities for the chosen Binance variant (4h, formation 2021-01) under
the adopted rules (author, 2026-10-09), beside the flat-10-bps figures. Laptop; the PINNED
inputs (`environments.binance_pins`), served only at their hashes.

The rules:
- **Cost:** fee 5 bps (an assumption) + the half-spread estimate, floored at 1 bp
  (`environments.binance_costs`); dead contracts cost nothing after their exit.
- **Block length:** the median of the base columns' Politis-White lengths over the whole
  in-sample window after warm-up (proposal (a)).
- **Dead contracts:** positions are zero on every row whose earned bar is dead, after the
  model; learn2 is untouched, and the freed gross is not redeployed (proposal (b)).

Two cost schemes on the same book (the learner's fit does not depend on costs):
- flat 10 bps: the panel's cost;
- the rule: the pinned per-row rates, which also price the base columns behind the block
  length and the bootstrap.

For each scheme:
- the 95% stream bar (B 5,000, seed 695056), the net 80%-power Sharpe and the gross
  needed;
- cost drag, turnover per unit gross, cost per year, the dead-contract share;
- for the rule, the distribution of per-contract cost in bps.

**Never computed, printed or stored:** a mean return, a Sharpe, a p-value or any
certification.

    OMP_NUM_THREADS=1 python -m experiments.binance_design_chosen --out runs/binance_design_chosen/2026-10-09
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import time
from pathlib import Path

import numpy as np

from experiments import binance_design_v2 as D
from experiments import binance_design_v2_4h as E

NAME = "4h-2021-01"
SEED = 695056
SEED_CLASS = 695057
B = 5000
QS = (0.95, 0.96, 0.975, 0.99)


def pinned_raw():
    """raw_4h's panel and info with the pinned P, and the pinned v2 blocks and costs."""
    from environments import binance_pins as Pn
    raw = E.raw_4h(NAME)
    X = Pn.load("X")
    if X.shape != raw["panel"].features.shape:
        raise SystemExit("pinned X shape differs from the build")
    raw["panel"] = dataclasses.replace(raw["panel"], features=X)
    v2 = Pn.load("v2")
    costs = Pn.load("costs")
    return raw, v2, costs


def figures(book, panel, inp, rows, alive, ppy, years) -> dict:
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments.binance_design_quantities import certified_sharpe
    f = E.stream_figures(book, inp, rows, alive, ppy)
    s = f.pop("_stream")
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    pw = E.pw_lengths(bc)
    L = E.median_rule(pw, bc.shape[0])
    from estimator.bootstrap import stationary_bootstrap_indices
    from learn import stream_tier
    table = stream_tier.table_from_streams((s - s.mean())[None, :], ppy)
    rng = np.random.default_rng(SEED)
    R_b = np.asarray(table.null_max([stationary_bootstrap_indices(len(s), L, rng) for _ in range(B)]), float)
    del s
    bars = {str(q): float(np.quantile(R_b, q)) for q in QS}
    bar = bars["0.95"]
    net = certified_sharpe(bar, years, ppy)
    f.update({"block_length": L, "pw_median": float(np.nanmedian(pw)), "bar95": bar, "net_80": net,
              "gross_80": net + f["cost_drag_sharpe"],
              "bars": {q: {"bar": b, "net_80": certified_sharpe(b, years, ppy),
                           "gross_80": certified_sharpe(b, years, ppy) + f["cost_drag_sharpe"]} for q, b in bars.items()}})
    return f


def class_figures(panel) -> dict:
    """The class tier's null maxima on the whole scored panel (block length by the class
    rule over the same window, which is the whole in-sample window)."""
    import environments.planted_fast as pf
    import experiments.french_design_quantities as fdq
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments.binance_design_quantities import certified_sharpe
    t0 = time.time()
    cache = pf.build(panel, members_in_order(CLS, panel.features.shape[2]), name=f"binance-{NAME}-signed-3")
    t_build = time.time() - t0
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    fdq.B = B
    t0 = time.time()
    M_b, L = fdq.class_null(panel, cache, bc, SEED_CLASS)
    T = panel.features.shape[0]
    years = T / panel.periods_per_year
    return {"rows": T, "years": years, "block_length": int(L), "seconds_build": t_build,
            "seconds_null": time.time() - t0,
            "bars": {str(q): {"bar": float(np.quantile(M_b, q)),
                              "net_80": certified_sharpe(float(np.quantile(M_b, q)), years, panel.periods_per_year)}
                     for q in QS}}


def main(argv=None) -> int:
    from learn2 import learner as Ln
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit("exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    D.configure("4h")
    t0 = time.time()
    raw, v2, costs = pinned_raw()
    panel, info = raw["panel"], raw["info"]
    inp = Ln.from_panel(panel, blocks={"X": v2["X"], "V": v2["V"], "F": v2["F"]}, groups=v2["G"])
    book, first, meta = D.book_of(inp)
    T, ppy = inp.earned.shape[0], inp.ppy
    rows = np.arange(first, T)
    years = len(rows) / ppy
    alive = np.array([info[s]["alive_earned"] for s in panel.meta["symbols"]]).T
    closed = E.close_dead(book, alive)
    rates = np.asarray(costs["rates"], float)
    res = {"variant": NAME, "rows": int(len(rows)), "years": years, "estimator": str(costs["estimator"]),
           "seconds_per_fit": meta["seconds_per_fit"], "book_sha256": D.sha(book), "schemes": {}}
    for scheme, cr in (("flat_10bps", np.asarray(panel.cost_rate, float)), ("rule", rates)):
        pan = dataclasses.replace(panel, cost_rate=cr)
        ip = dataclasses.replace(inp, cost_rate=cr)
        res["schemes"][scheme] = {lab: figures(bk, pan, ip, rows, alive, ppy, years)
                                  for lab, bk in (("as_is", book), ("closed", closed))}
        res["schemes"][scheme]["class"] = class_figures(pan)
    # per-contract cost in bps under the rule: live rows of the scored window
    live = rates[rows] > 0
    bps = rates[rows][live] * 1e4
    per_contract = [float(np.median(rates[rows][:, j][rates[rows][:, j] > 0]) * 1e4)
                    if (rates[rows][:, j] > 0).any() else float("nan") for j in range(rates.shape[1])]
    hsf = np.asarray(costs["half_spread"], float)
    res["cost_bps"] = {"rows_q": {q: float(np.quantile(bps, q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
                       "rows_mean": float(bps.mean()),
                       "per_contract_median": dict(zip(panel.meta["symbols"], per_contract)),
                       "share_at_floor": float(np.mean(np.isclose(bps, 6.0))),
                       "months_without_estimate": int(np.isnan(hsf).sum()), "contract_months": int(hsf.size)}
    res["wall_seconds"] = time.time() - t0
    L = [f"Chosen Binance variant {NAME}, version 2, adopted rules (outcome-free; pinned inputs)",
         f"platform {platform.system()} {platform.machine()}; estimator {res['estimator']}; seed {SEED}, B {B}",
         f"scored {res['rows']} rows, {years:.2f} years", "=" * 96,
         f"{'scheme':<11} {'book':<7} {'L':>3} {'bar95':>6} {'net80':>6} {'gross':>6} {'drag':>6} "
         f"{'turn':>7} {'cost/y':>7} {'deadsh':>7}"]
    for scheme, v in res["schemes"].items():
        for lab, f in ((k, x) for k, x in v.items() if k != "class"):
            L.append(f"{scheme:<11} {lab:<7} {f['block_length']:>3} {f['bar95']:>6.3f} {f['net_80']:>6.3f} "
                     f"{f['gross_80']:>6.3f} {f['cost_drag_sharpe']:>6.3f} {f['turnover_per_unit_gross']:>7.4f} "
                     f"{f['cost_per_year']:>7.4f} {f['dead_gross_share']:>7.4f}")
    L.append("")
    L.append("bars by quantile (stream: closed book; class: whole panel) -> net Sharpe at 80% power [gross for the stream]")
    for scheme, v in res["schemes"].items():
        st, cl = v["closed"], v["class"]
        L.append(f"   {scheme}: stream " + "; ".join(f"{float(q):.3f}: {b['bar']:.3f} -> {b['net_80']:.3f} [{b['gross_80']:.3f}]"
                                                   for q, b in st["bars"].items()))
        L.append(f"   {scheme}: class ({cl['rows']} rows, {cl['years']:.2f} y, L {cl['block_length']}) " +
                 "; ".join(f"{float(q):.3f}: {b['bar']:.3f} -> {b['net_80']:.3f}" for q, b in cl["bars"].items())
                 + f"  (cache {cl['seconds_build']:.0f} s, null {cl['seconds_null']:.0f} s)")
    c = res["cost_bps"]
    L.append("")
    L.append("per-row cost under the rule (live rows, scored window), bps: " +
             ", ".join(f"q{int(q * 100):02d} {v:.2f}" for q, v in c["rows_q"].items()) +
             f"; mean {c['rows_mean']:.2f}; share at the 6 bps minimum {c['share_at_floor']:.3f}")
    L.append(f"contract-months without an estimate (filled by the month's median): {c['months_without_estimate']} "
             f"of {c['contract_months']}")
    L.append("per-contract median cost, bps: " + ", ".join(f"{s[:-4]} {v:.1f}" for s, v in
                                                         sorted(c["per_contract_median"].items(), key=lambda x: x[1])))
    L.append(f"wall {res['wall_seconds']:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(res, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
