"""Outcome-free design quantities for three 4h Binance variants with version 2 (the author's
request of 2026-10-09). Laptop; PROVISIONAL unpinned builds; in-sample data only.

Variants: 4h bars for the formation universes 2020-09, 2021-01 and 2021-10. The first two
start the month after formation (the 253-row warm-up inside it). The third is the existing
4h panel, re-run here with five-column V. All end 2025-03-31. Configuration as carried
forward: base view (P X V F; h 5; market; always), first scored row 763, M2 (rolling 756,
expanding), G3, L {1, 3, 10, 30}. V now has all five columns: logvol_ratio, taker_last,
taker_mean21, count_ratio, amihud21. The taker-buy volume comes from the restored taker
files.

Per variant, as in `binance_design_v2`:
- contracts that qualify (full-month traders) and the universe;
- deaths in-sample;
- rows and years scored;
- the 95% stream bar, net 80%-power Sharpe and gross needed;
- cost drag and the dead-contract gross share;
- seconds per fit, the leak tests and the bit-for-bit repeat.

And two proposals, shown outcome-free:
- **(a) Block length.** The Politis-White length of each demeaned base column, on the
  scored window (the current rule) and on the whole in-sample window (the panel's rows
  after warm-up). Both medians, and the 95% bar under each. For the 2021-10 panel, also
  on the old 4h-cal scored window (rows 2,197 on), to show why the median moved from 11
  to 2.
- **(b) Dead-contract closure.** Applied after the model; learn2 is untouched. A position
  is zero on every row whose earned bar is dead. The closing trade executes at the close
  of the last live bar, which is the death bar's carried price, and the panel's 10 bps
  cost applies to it. Shown with and without: the dead-contract share, cost per year,
  cost drag, and the bar, net and gross needed.

**Never computed, printed or stored:** a mean return, a Sharpe, a p-value or any
certification. Streams are demeaned before any bootstrap, and no position is stored.

Seeds: stream nulls 695050-695052, leak perturbations 695053-695055 (block 695000-695999).

    OMP_NUM_THREADS=1 python -m experiments.binance_design_v2_4h --out runs/binance_design_v2_4h/2026-10-09 --workers 3
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from experiments import binance_design_v2 as D

VARIANTS = ("4h-2020-09", "4h-2021-01", "4h-2021-10")
SEED_STREAM = {v: 695050 + i for i, v in enumerate(VARIANTS)}
SEED_LEAK = {v: 695053 + i for i, v in enumerate(VARIANTS)}
B = 5000
CAL_FIRST = 2190 + 7                          # the dropped 4h-cal variant's first scored row


def load_taker(sym: str, directory: Path) -> dict:
    """{open_time: taker_buy_volume} from the restored taker files (and the fill's)."""
    from data.etf_loader import HoldoutRefused, refuse_sealed_or_quarantined
    from environments import binance_panel as bp
    out = {}
    for name in (f"{sym}_4h_taker.csv", f"{sym}_4h_fill_taker.csv"):
        p = Path(directory) / name
        if not p.exists():
            if name.endswith("_4h_taker.csv"):
                raise FileNotFoundError(p)
            continue
        with refuse_sealed_or_quarantined(p).open(newline="") as fh:
            rd = csv.reader(fh)
            next(rd)
            for r in rd:
                t = int(r[0])
                if t >= bp.HOLDOUT_START_MS:
                    raise HoldoutRefused(f"{p.name} holds a row on or after 2025-04-01")
                out.setdefault(t, float(r[1]))
    return out


def spec_for(name: str):
    from data import fetch_binance as fb
    from environments import binance_panel as bp
    f = name[3:]
    if f == "2021-10":
        man = json.loads(fb.MANIFEST.read_text())
        u = {"formation": f, "full_month_traders": sum(1 for x in man["formation"] if x["trading_days"] == 31),
             "universe": len(man["universe"])}
        return man["universe"], bp.INSAMPLE_DIR, bp.FOUR_H, u
    fm = json.loads((fb.REPO / "data" / "binance_4h_formations_manifest.json").read_text())["formations"][f]
    y, m = map(int, fm["first_month"].split("-"))
    spec = bp.BarSpec("4h", bp.BAR_MS, bp.PPY, None, dt.datetime(y, m, 1, tzinfo=dt.timezone.utc),
                      bp.LAST_INSAMPLE_OPEN, bp.RELIST_GAP)
    u = {"formation": f, "full_month_traders": fm["full_month_traders"], "universe": len(fm["universe"])}
    return fm["universe"], fb.REPO / "data" / "raw" / f"binance_4h_{f}", spec, u


def raw_4h(name: str, lag: int | None = None) -> dict:
    """`lag` = 1 + d (default: the panel builder's 2, d = 1)."""
    from environments import binance_panel as bp
    lag = bp.LAG if lag is None else lag
    symbols, directory, spec, u = spec_for(name)
    times = bp.grid(spec)
    loaded = [bp.load_symbol(s, directory, "4h") for s in symbols]
    al = [bp.align(times, kl, fr, relist_gap=spec.relist_gap) for kl, fr in loaded]
    r, rp, alive = bp.returns_from(al, len(times))
    panel = bp.panel_from_arrays(times, symbols, r, alive, rp=rp, spec=spec, lag=lag)
    kc = [D.kline_columns(times, kl, a["dead"]) for (kl, _), a in zip(loaded, al)]
    tk = np.full((len(times), len(symbols)), np.nan)
    pos = {t: i for i, t in enumerate(times.tolist())}
    for j, (s, a) in enumerate(zip(symbols, al)):
        for t, v in load_taker(s, directory).items():
            i = pos.get(t)
            if i is not None:
                tk[i, j] = v
        if a["dead"] is not None:
            tk[a["dead"]:, j] = np.nan
    live_n = alive.sum(axis=1)
    market = np.where(live_n > 0, (rp * alive).sum(axis=1) / np.maximum(live_n, 1), 0.0)
    close = np.where(alive, np.stack([a["close"] for a in al], axis=1), np.nan)
    info = {s: {"dead_bar": a["dead"], "gap_bars": a["gap_bars"],
                "alive_earned": alive[bp.WARM + lag:, j].tolist(), "funding_rows": len(fr)}
            for j, (s, a, (_, fr)) in enumerate(zip(symbols, al, loaded))}
    return {"panel": panel, "info": info, "universe": u, "spec": spec, "WARM": bp.WARM, "LAG": lag,
            "rp": rp, "market": market, "alive": alive, "close": close,
            "volume": np.stack([k["volume"] for k in kc], axis=1),
            "count": np.stack([k["count"] for k in kc], axis=1), "taker": tk,
            "funding": np.stack([a["funding"] for a in al], axis=1)}


def build_blocks(raw: dict) -> dict:
    from learn2 import blocks as Bk
    T = raw["rp"].shape[0]
    keep = slice(raw["WARM"], T - raw["LAG"])
    X = Bk.build_X(raw["rp"], raw["market"])
    V, vnames = Bk.build_V(raw["volume"], raw["close"], raw["rp"], raw["taker"], raw["count"])
    F = Bk.build_F(raw["funding"])
    G = Bk.build_groups(raw["rp"], raw["market"])
    return {"X": X[keep], "V": V[keep], "F": F[keep], "G": G[keep], "vnames": vnames}


def inputs(raw: dict, blk: dict):
    from learn2 import learner as Ln
    return Ln.from_panel(raw["panel"], blocks={"X": blk["X"], "V": blk["V"], "F": blk["F"]}, groups=blk["G"])


# -- the two proposals ---------------------------------------------------------------------

def pw_lengths(bc: np.ndarray) -> np.ndarray:
    """Each demeaned column's Politis-White stationary length (NaN where undefined or the
    column has no variance), as `select_block_length` computes them before its median."""
    from arch.bootstrap import optimal_block_length
    x = bc - bc.mean(axis=0)
    out = np.full(x.shape[1], np.nan)
    live = x.std(axis=0) > 0
    if live.any():
        out[live] = optimal_block_length(x[:, live])["stationary"].to_numpy()
    return out


def median_rule(lengths: np.ndarray, T: int) -> int:
    v = lengths[np.isfinite(lengths)]
    return 1 if v.size == 0 else int(np.clip(int(round(np.median(v))), 1, max(1, T // 4)))


def bar_with_L(stream: np.ndarray, L: int, ppy: float, seed: int, B_null: int = B) -> float:
    from estimator.bootstrap import stationary_bootstrap_indices
    from learn import stream_tier
    s = stream - stream.mean()
    table = stream_tier.table_from_streams(s[None, :], ppy)
    rng = np.random.default_rng(seed)
    rows = [stationary_bootstrap_indices(len(s), L, rng) for _ in range(B_null)]
    return float(np.quantile(np.asarray(table.null_max(rows), float), 0.95))


def close_dead(book: np.ndarray, alive_earned: np.ndarray) -> np.ndarray:
    """Zero on every row whose earned bar is dead; the change into zero is traded at the
    last live bar's close and costed by the panel."""
    return np.where(alive_earned, book, 0.0)


def stream_figures(book, inp, rows, alive_earned, ppy) -> dict:
    from learn2 import views as Vw
    ts = Vw.turnover_stats(book, inp, rows)
    s = Vw.net_stream(book, inp, rows)
    vol = float(s.std(ddof=1) * np.sqrt(ppy))
    return {**ts, "ann_vol": vol, "cost_drag_sharpe": ts["cost_per_year"] / vol if vol > 0 else float("nan"),
            "dead_gross_share": float(np.mean((np.abs(book[rows]) * ~alive_earned[rows]).sum(axis=1)
                                              / np.maximum(np.abs(book[rows]).sum(axis=1), 1e-300))),
            "_stream": s}


def quantities(name: str, raw: dict, B_null: int = B) -> dict:
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments.binance_design_quantities import certified_sharpe
    D.configure("4h")
    t0 = time.time()
    blk = build_blocks(raw)
    t_blocks = time.time() - t0
    panel, info = raw["panel"], raw["info"]
    inp = inputs(raw, blk)
    book, first, meta = D.book_of(inp)
    T, ppy = inp.earned.shape[0], inp.ppy
    rows = np.arange(first, T)
    years = len(rows) / ppy
    alive = np.array([info[s]["alive_earned"] for s in panel.meta["symbols"]]).T
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    seed = SEED_STREAM[name]
    # block lengths: scored window (current rule), whole in-sample window (proposed)
    pw_scored, pw_whole = pw_lengths(bc[rows]), pw_lengths(bc)
    L_cur, L_prop = median_rule(pw_scored, len(rows)), median_rule(pw_whole, T)
    out = {"variant": name, "universe": {**raw["universe"],
                                         "dead_in_sample": sum(1 for x in info.values() if x["dead_bar"] is not None),
                                         "gap_bars": {s: x["gap_bars"] for s, x in info.items() if x["gap_bars"]}},
           "blocks": {"available": list(inp.available), "V": list(blk["vnames"])},
           "settings": D.settings(T, ppy, inp.d), "rows": int(len(rows)), "years": years,
           "first": panel.meta["earned_opens"][rows[0]], "last": panel.meta["earned_opens"][rows[-1]],
           "seconds": {"blocks": t_blocks, **{f"fit_{k}": v for k, v in meta["seconds_per_fit"].items()}},
           "book_sha256": D.sha(book), "block_length": {
               "feature_names": list(panel.feature_names),
               "pw_scored": pw_scored.tolist(), "pw_whole": pw_whole.tolist(),
               "median_scored": L_cur, "median_whole": L_prop}}
    if name == "4h-2021-10":
        cal = np.arange(CAL_FIRST, T)
        pw_cal = pw_lengths(bc[cal])
        out["block_length"]["pw_cal_window"] = pw_cal.tolist()
        out["block_length"]["median_cal_window"] = median_rule(pw_cal, len(cal))
    for label, bk in (("as_is", book), ("closed", close_dead(book, alive))):
        f = stream_figures(bk, inp, rows, alive, ppy)
        s = f.pop("_stream")
        bars = {"current": bar_with_L(s, L_cur, ppy, seed, B_null), "proposed": bar_with_L(s, L_prop, ppy, seed, B_null)}
        del s
        f["bars"] = {k: {"L": (L_cur if k == "current" else L_prop), "bar95": b,
                         "net_80": certified_sharpe(b, years, ppy),
                         "gross_80": certified_sharpe(b, years, ppy) + f["cost_drag_sharpe"]} for k, b in bars.items()}
        out[label] = f
    return out


def job_main(name):
    return quantities(name, raw_4h(name))


def job_leak(name, raw=None):
    from learn2 import leak as Lk
    from learn2 import learner as Ln
    from learn2 import timing
    D.configure("4h")
    raw = raw if raw is not None else raw_4h(name)
    inp = inputs(raw, build_blocks(raw))
    first = Ln.FIRST + timing.embargo(D.H, inp.d)
    t = first + (inp.earned.shape[0] - first) // 2
    hashes = []

    def fn(i):
        b = D.book_of(i)[0]
        hashes.append(D.sha(b))
        return b
    return {"variant": name, "leak_view": Lk.leak_view(fn, inp, [t], seed=SEED_LEAK[name]),
            "base_book_sha256": hashes[0]}


def job_block_leak(name, raw=None):
    from learn2 import blocks as Bk
    from learn2 import leak as Lk
    raw = raw if raw is not None else raw_4h(name)
    T = raw["rp"].shape[0]
    t = raw["WARM"] + 763 + (T - raw["WARM"] - raw["LAG"] - 763) // 2
    sd = SEED_LEAK[name]
    rp, m = raw["rp"], raw["market"]
    va = (raw["volume"], raw["close"], rp, raw["taker"], raw["count"])
    return {"variant": name, "block_leak": {
        "X(r)": Lk.leak_block(Bk.build_X, (rp, m), [t], sd, which=0),
        "V(volume)": Lk.leak_block(Bk.build_V, va, [t], sd, which=0),
        "V(taker)": Lk.leak_block(Bk.build_V, va, [t], sd, which=3),
        "V(count)": Lk.leak_block(Bk.build_V, va, [t], sd, which=4),
        "F(funding)": Lk.leak_block(Bk.build_F, (raw["funding"],), [t], sd, which=0),
        "groups(r)": Lk.leak_block(Bk.build_groups, (rp, m), [t], sd, which=0)}}


JOBS = {"main": job_main, "leak": job_leak, "block_leak": job_block_leak}


def run_job(task):
    kind, name = task
    t0 = time.time()
    r = JOBS[kind](name)
    r["job_seconds"] = time.time() - t0
    return kind, name, r


def report(res: dict) -> list[str]:
    L = ["Binance 4h design quantities, version 2, three formations (outcome-free; provisional unpinned builds)",
         f"platform {platform.system()} {platform.machine()}; base view, first scored row 763, M2, G3, L {{1, 3, 10, 30}}; "
         "V five columns; flat 10 bps", "=" * 100]
    for v in VARIANTS:
        m, lk, bl = res[("main", v)], res[("leak", v)], res[("block_leak", v)]
        u, a = m["universe"], m["as_is"]
        L.append(f"{v}: {u['full_month_traders']} full-month traders; universe {u['universe']}; deaths in-sample "
                 f"{u['dead_in_sample']}; gap bars {sum(u['gap_bars'].values())} over {len(u['gap_bars'])} contracts")
        L.append(f"   blocks {' '.join(m['blocks']['available'])}; V = {', '.join(m['blocks']['V'])}")
        L.append(f"   scored {m['rows']} rows, {m['years']:.2f} years ({m['first'][:10]} .. {m['last'][:10]})")
        b = a["bars"]["current"]
        L.append(f"   turnover per unit gross {a['turnover_per_unit_gross']:.4f} (mean gross {a['mean_gross']:.3f}); "
                 f"cost per year {a['cost_per_year']:.4f}; drag {a['cost_drag_sharpe']:.3f}; dead share {a['dead_gross_share']:.4f}")
        L.append(f"   bar95 {b['bar95']:.3f} (L {b['L']}); net 80% {b['net_80']:.3f}; gross needed {b['gross_80']:.3f}")
        L.append(f"   seconds per fit " + ", ".join(f"{k[4:]} {x:.0f}" for k, x in m["seconds"].items() if k.startswith("fit_")))
        L.append(f"   leak (learner) {lk['leak_view'][0]['identical_up_to_t']}/{lk['leak_view'][0]['changed_after_t']}; "
                 "blocks " + "; ".join(f"{k} {x[0]['identical_up_to_t']}/{x[0]['changed_after_t']}" for k, x in bl["block_leak"].items())
                 + f"; repeat {m['book_sha256'] == lk['base_book_sha256']}")
    L += ["", "TABLE (current block-length rule; positions as the model gives them)",
          f"{'variant':<11} {'qual':>4} {'univ':>4} {'dead':>4} {'rows':>5} {'years':>5} {'bar95':>6} {'net80':>6} "
          f"{'gross':>6} {'drag':>6} {'deadsh':>7}"]
    for v in VARIANTS:
        m = res[("main", v)]
        a, b = m["as_is"], m["as_is"]["bars"]["current"]
        L.append(f"{v:<11} {m['universe']['full_month_traders']:>4} {m['universe']['universe']:>4} "
                 f"{m['universe']['dead_in_sample']:>4} {m['rows']:>5} {m['years']:>5.2f} {b['bar95']:>6.3f} "
                 f"{b['net_80']:>6.3f} {b['gross_80']:>6.3f} {a['cost_drag_sharpe']:>6.3f} {a['dead_gross_share']:>7.4f}")
    L += ["", "PROPOSAL (a): block length -- Politis-White per base column, median; scored window vs whole in-sample window"]
    for v in VARIANTS:
        bl = res[("main", v)]["block_length"]
        sc, wh = np.array(bl["pw_scored"], float), np.array(bl["pw_whole"], float)
        q = lambda x: f"q25 {np.nanquantile(x, .25):5.1f} med {np.nanmedian(x):5.1f} q75 {np.nanquantile(x, .75):5.1f}"
        L.append(f"   {v}: scored window {q(sc)} -> L {bl['median_scored']}; whole window {q(wh)} -> L {bl['median_whole']}")
        if "pw_cal_window" in bl:
            cal = np.array(bl["pw_cal_window"], float)
            L.append(f"      (old 4h-cal window, rows 2197 on: {q(cal)} -> L {bl['median_cal_window']})")
            L.append("      per column (scored / 4h-cal window / whole):")
            for nm, a_, c_, w_ in zip(bl["feature_names"], sc, cal, wh):
                L.append(f"         {nm:<28} {a_:6.1f} {c_:6.1f} {w_:6.1f}")
        a = res[("main", v)]["as_is"]["bars"]
        L.append(f"      bar95 current (L {a['current']['L']}) {a['current']['bar95']:.3f}; proposed (L {a['proposed']['L']}) "
                 f"{a['proposed']['bar95']:.3f}; gross needed {a['current']['gross_80']:.3f} -> {a['proposed']['gross_80']:.3f}")
    L += ["", "PROPOSAL (b): dead-contract closure after the model (learn2 untouched)",
          f"{'variant':<11} {'':<8} {'deadsh':>7} {'turn':>7} {'cost/y':>7} {'drag':>6} {'bar95':>6} {'gross':>6}"]
    for v in VARIANTS:
        for lab in ("as_is", "closed"):
            f = res[("main", v)][lab]
            b = f["bars"]["current"]
            L.append(f"{v if lab == 'as_is' else '':<11} {lab:<8} {f['dead_gross_share']:>7.4f} {f['turnover_per_unit_gross']:>7.4f} "
                     f"{f['cost_per_year']:>7.4f} {f['cost_drag_sharpe']:>6.3f} {b['bar95']:>6.3f} {b['gross_80']:>6.3f}")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit(f"{out / 'design.json'} exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    tasks = [(k, v) for v in VARIANTS for k in ("main", "leak")] + [("block_leak", v) for v in VARIANTS]
    res = {}
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        for kind, name, r in ex.map(run_job, tasks):
            res[(kind, name)] = r
            print(f"{kind} {name} done ({r['job_seconds']:.0f} s; {time.time() - t0:.0f} s elapsed)", flush=True)
    L = report(res) + [f"wall {time.time() - t0:.0f} s"]
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps({f"{k} {v}": r for (k, v), r in res.items()}, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
