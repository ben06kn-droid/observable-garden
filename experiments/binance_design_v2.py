"""Outcome-free design quantities for the Binance panel with version 2 (the carried-forward
configuration: the base view (all available blocks, h 5, market, always), memory set M2
(rolling 756, expanding), rate grid G3 (0.3, 0.1, 0.03), L grid {1, 3, 10, 30}). Laptop;
PROVISIONAL unpinned builds, the in-sample data already fetched. The version-1 table is
`runs/binance_design_c/2026-10-08` (script `6ca2e0a`, outputs `28194a4`).

Variants, as in the version-1 table: the 4h panel (formation 2021-10) and the UTC daily
panel for formations 2020-09, 2021-01 and 2021-10.

Version 2's blocks on Binance, built on the full bar grid (warm-up included) from data
known at each bar's close, then cut to the panel's rows exactly as P is:
- X (10 columns) from PRICE-only bar returns and the live-average market;
- V from base volume, close and trade count (taker volume is not in the derived CSVs);
- F (3 columns) from the funding paid in each bar (its calc time is at or before the
  bar's close);
- neutrality groups from the trailing 252-row market-residual correlation.

For each variant:
- the blocks present and their columns, and what is missing;
- the row settings (first scored row, refit, memories, block windows) in rows and years,
  the scored window, the training rows at the first and last refit, and a stated
  time-matched alternative (arithmetic only; not run);
- the book's turnover per unit gross, cost per year at the panel's flat 10 bps, the
  stream's annualised volatility (a dispersion, not a mean), cost drag in Sharpe units,
  the share of gross in dead contracts;
- the stream's null bar at 95% (demeaned stream, B 5,000, block length by the class
  rule), the net Sharpe certified with 80% power (Lo's iid formula with the panel's ppy),
  and the gross Sharpe needed (net + drag);
- seconds per fit (one `fit_cell` per memory);
- a leak test (the learner's book up to t bit-identical when every input after t is
  replaced; and each block builder's rows up to t identical when its raw input after t is
  replaced) and a bit-for-bit repeat (the leak job's base book, built in a separate
  process, against the main job's; positions only, compared by SHA-256).

**Never computed, printed or stored:** a mean return, a Sharpe, a p-value or any
certification. The stream's mean is removed before the bootstrap and never kept. No
position is stored.

Seeds: stream nulls 695040-695043, leak perturbations 695044-695047 (block 695000-695999).

    OMP_NUM_THREADS=1 python -m experiments.binance_design_v2 --out runs/binance_design_v2/2026-10-09 --workers 3
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

B = 5000
Q = 0.95
VARIANTS = ("4h", "1d-2020-09", "1d-2021-01", "1d-2021-10")
SEED_STREAM = {v: 695040 + i for i, v in enumerate(VARIANTS)}
SEED_LEAK = {v: 695044 + i for i, v in enumerate(VARIANTS)}
H, NEUTRALITY, REGIME = 5, "market", "always"
RATES = (0.3, 0.1, 0.03)                         # G3
MEMORIES = ("roll756", "expand")                 # M2
L_GRID = {"L": (1.0, 3.0, 10.0, 30.0)}
V1_TABLE = Path("runs/binance_design_c/2026-10-08/design_c.json")


# -- raw arrays on the bar grid ------------------------------------------------------------

def kline_columns(times: np.ndarray, kl: list, dead: int | None) -> dict:
    """Base volume and trade count on the grid: NaN on bars with no kline row and from
    the death bar on."""
    pos = {t: i for i, t in enumerate(times.tolist())}
    vol = np.full(len(times), np.nan)
    cnt = np.full(len(times), np.nan)
    for r in kl:
        i = pos.get(r[0])
        if i is not None:
            vol[i], cnt[i] = r[5], r[7]
    if dead is not None:
        vol[dead:] = np.nan
        cnt[dead:] = np.nan
    return {"volume": vol, "count": cnt}


def raw_variant(name: str) -> dict:
    """Panel (unpinned), info, universe counts, and the grid-level raw arrays."""
    from data import fetch_binance as fb
    from data import fetch_binance_daily as fd
    from environments import binance_panel as bp
    if name == "4h":
        man = json.loads(fb.MANIFEST.read_text())
        symbols, directory, spec = man["universe"], bp.INSAMPLE_DIR, bp.FOUR_H
        u = {"formation": "2021-10", "universe": len(symbols)}
    else:
        f = name.split("-", 1)[1]
        man = json.loads(fd.MANIFEST.read_text())["formations"][f]
        symbols = man["universe"]
        directory = fb.REPO / "data" / "raw" / f"binance_daily_{f}"
        spec = bp.daily_spec(man["first_month"])
        u = {"formation": f, "universe": len(symbols)}
    times = bp.grid(spec)
    loaded = [bp.load_symbol(s, directory, spec.bar) for s in symbols]
    al = [bp.align(times, kl, fr, relist_gap=spec.relist_gap) for kl, fr in loaded]
    r, rp, alive = bp.returns_from(al, len(times))
    panel = bp.panel_from_arrays(times, symbols, r, alive, rp=rp, spec=spec)
    kc = [kline_columns(times, kl, a["dead"]) for (kl, _), a in zip(loaded, al)]
    live_n = alive.sum(axis=1)
    market = np.where(live_n > 0, (rp * alive).sum(axis=1) / np.maximum(live_n, 1), 0.0)
    close = np.stack([a["close"] for a in al], axis=1)
    close = np.where(alive, close, np.nan)
    info = {s: {"dead_bar": a["dead"], "alive_earned": alive[bp.WARM + bp.LAG:, j].tolist(),
                "funding_rows": len(fr)} for j, (s, a, (_, fr)) in enumerate(zip(symbols, al, loaded))}
    return {"panel": panel, "info": info, "universe": u, "spec": spec, "WARM": bp.WARM, "LAG": bp.LAG,
            "rp": rp, "market": market, "alive": alive, "close": close,
            "volume": np.stack([k["volume"] for k in kc], axis=1),
            "count": np.stack([k["count"] for k in kc], axis=1),
            "funding": np.stack([a["funding"] for a in al], axis=1)}


def build_blocks(raw: dict) -> dict:
    from learn2 import blocks as Bk
    T = raw["rp"].shape[0]
    keep = slice(raw["WARM"], T - raw["LAG"])
    X = Bk.build_X(raw["rp"], raw["market"])
    V, vnames = Bk.build_V(raw["volume"], raw["close"], raw["rp"], None, raw["count"])
    F = Bk.build_F(raw["funding"])
    G = Bk.build_groups(raw["rp"], raw["market"])
    return {"X": X[keep], "V": V[keep], "F": F[keep], "G": G[keep], "vnames": vnames}


def inputs(raw: dict, blk: dict):
    from learn2 import learner as Ln
    return Ln.from_panel(raw["panel"], blocks={"X": blk["X"], "V": blk["V"], "F": blk["F"]},
                         groups=blk["G"])


def book_of(inp) -> tuple[np.ndarray, int, dict]:
    from learn2 import views as Vw
    cache = Vw.FitCache(inp, grids=L_GRID)
    base = Vw.base_view(inp.available)
    secs, diags = {}, {}
    for mem in MEMORIES:
        t0 = time.time()
        f = cache.get(base[0], H, NEUTRALITY, mem)
        secs[mem] = time.time() - t0
        diags[mem] = [{"refit": x["refit"], "train_rows": x["train_rows"]} for x in f["diagnostics"]]
    vb = Vw.view_book(cache, base, rates=RATES, memories=MEMORIES)
    return vb["book"], vb["first"], {"seconds_per_fit": secs, "refits": diags, "view": [list(base[0]), *base[1:]]}


def sha(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


# -- settings in rows ----------------------------------------------------------------------

def settings(T: int, ppy: float, d: int = 1) -> dict:
    """The carried-forward row settings on a panel of T rows, in rows and years, and the
    time-matched alternative (rows scaled so each setting spans the calendar time it spans
    on the ETF panel at 252 rows a year). Arithmetic only."""
    from learn2 import blocks as Bk
    from learn2 import learner as Ln
    from learn2 import timing
    emb = timing.embargo(H, d)
    first = Ln.FIRST + emb
    scored = max(T - first, 0)
    reg = {"first_scored_row": first, "refit_rows": Ln.REFIT, "roll756_rows": 756,
           "block_window_rows": Bk.WIN, "short_window_rows": Bk.SHORT, "scored_rows": scored,
           "scored_years": scored / ppy, "refits": len(range(first, T, Ln.REFIT)),
           "years": {"first_scored_row": first / ppy, "refit": Ln.REFIT / ppy, "roll756": 756 / ppy,
                     "block_window": Bk.WIN / ppy}}
    k = ppy / 252.0
    tm_first = int(round(Ln.FIRST * k)) + emb
    tm = {"scale": k, "first_scored_row": tm_first, "refit_rows": int(round(Ln.REFIT * k)),
          "roll756_rows": int(round(756 * k)), "block_window_rows": int(round(Bk.WIN * k)),
          "scored_rows": max(T - tm_first, 0), "scored_years": max(T - tm_first, 0) / ppy}
    return {"T": T, "ppy": ppy, "carried_forward": reg, "time_matched_not_run": tm}


# -- jobs (each in its own process) --------------------------------------------------------

def job_main(name: str) -> dict:
    return quantities(name, raw_variant(name))


def quantities(name: str, raw: dict, B_null: int = B) -> dict:
    from experiments.binance_design_quantities import certified_sharpe
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from learn import stream_tier
    from learn2 import views as Vw
    t0 = time.time()
    blk = build_blocks(raw)
    t_blocks = time.time() - t0
    panel, info = raw["panel"], raw["info"]
    inp = inputs(raw, blk)
    book, first, meta = book_of(inp)
    T, ppy = inp.earned.shape[0], inp.ppy
    rows = np.arange(first, T)
    ts = Vw.turnover_stats(book, inp, rows)
    s = Vw.net_stream(book, inp, rows)
    vol = float(s.std(ddof=1) * np.sqrt(ppy))
    s = s - s.mean()
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    table = stream_tier.table_from_streams(s[None, :], ppy)
    del s
    brow, L = stream_tier.bootstrap_rows(bc[rows], B_null, SEED_STREAM[name])
    R_b = np.asarray(table.null_max(brow), float)
    bar = float(np.quantile(R_b, Q))
    years = len(rows) / ppy
    drag = ts["cost_per_year"] / vol if vol > 0 else float("nan")
    net = certified_sharpe(bar, years, ppy)
    alive = np.array([info[sym]["alive_earned"] for sym in panel.meta["symbols"]]).T
    g = np.abs(book[rows])
    dead_share = float(np.mean((g * ~alive[rows]).sum(axis=1) / np.maximum(g.sum(axis=1), 1e-300)))
    eo = panel.meta["earned_opens"]
    no_funding = [s_ for s_, x in info.items() if x["funding_rows"] == 0]
    return {"variant": name, "universe": {**raw["universe"],
                                          "dead_in_sample": sum(1 for x in info.values() if x["dead_bar"] is not None)},
            "blocks": {"available": list(inp.available), "P": int(inp.P.shape[2]), "X": int(blk["X"].shape[2]),
                       "V": list(blk["vnames"]), "F": int(blk["F"].shape[2]),
                       "missing": ["V: taker_last, taker_mean21 (no taker volume in the derived CSVs)"]
                                  + ([f"F: no funding rows for {no_funding}"] if no_funding else []),
                       "groups_warm_from_row": int(np.argmax((blk["G"] >= 0).all(axis=1)))},
            "settings": settings(T, ppy, inp.d),
            "stream": {"rows": int(len(rows)), "years": years, "first": eo[rows[0]], "last": eo[rows[-1]],
                       **ts, "ann_vol": vol, "cost_drag_sharpe": drag, "dead_gross_share": dead_share,
                       "block_length": int(L), "B": B_null, "seed": SEED_STREAM[name],
                       "bar95": bar, "net_80": net, "gross_80": net + drag},
            "seconds": {"blocks": t_blocks, **{f"fit_{k}": v for k, v in meta["seconds_per_fit"].items()}},
            "refits": meta["refits"], "view": meta["view"], "book_sha256": sha(book)}


def job_leak(name: str, raw: dict | None = None) -> dict:
    """The learner's leak test at the middle scored row, and the base book's hash for the
    repeat."""
    from learn2 import leak as Lk
    raw = raw if raw is not None else raw_variant(name)
    blk = build_blocks(raw)
    inp = inputs(raw, blk)
    from learn2 import learner as Ln
    from learn2 import timing
    first = Ln.FIRST + timing.embargo(H, inp.d)
    t = first + (inp.earned.shape[0] - first) // 2
    hashes = []

    def fn(i):
        b = book_of(i)[0]
        hashes.append(sha(b))
        return b
    res = Lk.leak_view(fn, inp, [t], seed=SEED_LEAK[name])
    return {"variant": name, "leak_view": res, "base_book_sha256": hashes[0]}


def job_block_leak(name: str, raw: dict | None = None) -> dict:
    """Each block builder: rows <= t identical when its raw input after t is replaced
    (t = the grid row of the middle scored row)."""
    from learn2 import blocks as Bk
    from learn2 import leak as Lk
    from learn2 import learner as Ln
    from learn2 import timing
    raw = raw if raw is not None else raw_variant(name)
    T = raw["rp"].shape[0]
    first = Ln.FIRST + timing.embargo(H, 1)
    t = raw["WARM"] + first + (T - raw["WARM"] - raw["LAG"] - first) // 2
    seed = SEED_LEAK[name]
    rp, m = raw["rp"], raw["market"]
    out = {"X(r)": Lk.leak_block(Bk.build_X, (rp, m), [t], seed, which=0),
           "X(market)": Lk.leak_block(Bk.build_X, (rp, m), [t], seed, which=1),
           "V(volume)": Lk.leak_block(Bk.build_V, (raw["volume"], raw["close"], rp, None, raw["count"]), [t], seed, which=0),
           "V(count)": Lk.leak_block(Bk.build_V, (raw["volume"], raw["close"], rp, None, raw["count"]), [t], seed, which=4),
           "F(funding)": Lk.leak_block(Bk.build_F, (raw["funding"],), [t], seed, which=0),
           "groups(r)": Lk.leak_block(Bk.build_groups, (rp, m), [t], seed, which=0)}
    return {"variant": name, "block_leak": out}


JOBS = {"main": job_main, "leak": job_leak, "block_leak": job_block_leak}


def run_job(task):
    kind, name = task
    t0 = time.time()
    r = JOBS[kind](name)
    r["job_seconds"] = time.time() - t0
    return kind, name, r


# -- report --------------------------------------------------------------------------------

def report(res: dict, v1: dict) -> list[str]:
    L = ["Binance design quantities, version 2 (outcome-free; provisional unpinned builds)",
         f"platform {platform.system()} {platform.machine()}; base view, M2, G3, L {{1, 3, 10, 30}}; flat 10 bps",
         "=" * 100]
    for v in VARIANTS:
        m, lk, bl = res[("main", v)], res[("leak", v)], res[("block_leak", v)]
        st, se, b = m["settings"], m["stream"], m["blocks"]
        cf, tm = st["carried_forward"], st["time_matched_not_run"]
        L.append(f"{v}: formation {m['universe']['formation']}; universe {m['universe']['universe']}; "
                 f"dead in-sample {m['universe']['dead_in_sample']}; ppy {st['ppy']:.0f}; panel rows {st['T']}")
        L.append(f"   blocks: {' '.join(b['available'])}  (P {b['P']}, X {b['X']}, V {len(b['V'])} = {', '.join(b['V'])}, "
                 f"F {b['F']}); groups warm from row {b['groups_warm_from_row']}")
        L.append(f"   missing: {'; '.join(b['missing'])}")
        L.append(f"   settings (carried forward, rows): first scored {cf['first_scored_row']} ({cf['years']['first_scored_row']:.2f} y), "
                 f"refit {cf['refit_rows']} ({cf['years']['refit']:.2f} y), roll756 ({cf['years']['roll756']:.2f} y), "
                 f"block window {cf['block_window_rows']} ({cf['years']['block_window']:.2f} y), short {cf['short_window_rows']}; "
                 f"{cf['refits']} refits")
        for mem, rr in m["refits"].items():
            if rr:
                L.append(f"      {mem}: training rows at first refit {rr[0]['train_rows']}, at last {rr[-1]['train_rows']}")
        L.append(f"   scored window: {se['rows']} rows, {se['years']:.2f} years ({se['first'][:10]} .. {se['last'][:10]})")
        L.append(f"   time-matched alternative (x{tm['scale']:.3f}; NOT run): first scored {tm['first_scored_row']}, "
                 f"refit {tm['refit_rows']}, roll756 -> {tm['roll756_rows']}, block window {tm['block_window_rows']}; "
                 f"scored {tm['scored_rows']} rows, {tm['scored_years']:.2f} years")
        L.append(f"   turnover per unit gross {se['turnover_per_unit_gross']:.4f} (mean gross {se['mean_gross']:.3f}); "
                 f"cost per year {se['cost_per_year']:.4f}; annualised vol {se['ann_vol']:.4f}; "
                 f"cost drag {se['cost_drag_sharpe']:.3f} Sharpe; gross share in dead contracts {se['dead_gross_share']:.4f}")
        L.append(f"   stream bar 0.95: {se['bar95']:.3f} (block length {se['block_length']}); net 80% {se['net_80']:.3f}; "
                 f"gross needed {se['gross_80']:.3f}")
        L.append(f"   seconds: blocks {m['seconds']['blocks']:.0f}; per fit " +
                 ", ".join(f"{k[4:]} {x:.0f}" for k, x in m["seconds"].items() if k.startswith("fit_")))
        lv = lk["leak_view"][0]
        L.append(f"   leak (learner, t = {lv['t']}): identical up to t {lv['identical_up_to_t']}, change visible {lv['changed_after_t']}")
        L.append("   leak (blocks): " + "; ".join(f"{k} {x[0]['identical_up_to_t']}/{x[0]['changed_after_t']}"
                                                  for k, x in bl["block_leak"].items()))
        L.append(f"   bit-for-bit repeat (positions, separate process): {m['book_sha256'] == lk['base_book_sha256']}")
    L.append("")
    L.append("COMPARISON (stream; net and gross Sharpe needed for 80% power at the 95% bar; flat 10 bps)")
    L.append(f"{'variant':<11} {'ver':<3} {'rows':>5} {'years':>5} {'turn':>7} {'cost/y':>7} {'drag':>6} "
             f"{'bar95':>6} {'net80':>6} {'gross':>6} {'s/fit':>6}")
    for v in VARIANTS:
        a = v1[v]["stream"]
        b5 = a["bars"]["0.95"]
        L.append(f"{v:<11} {'v1':<3} {a['rows']:>5} {a['years']:>5.2f} {a['turnover_per_row']:>7.4f} {a['cost_per_year']:>7.4f} "
                 f"{a['cost_drag_sharpe']:>6.3f} {b5['bar']:>6.3f} {b5['net_80']:>6.3f} {b5['gross_80']:>6.3f} {a['seconds_run']:>6.0f}")
        m = res[("main", v)]
        se = m["stream"]
        fit = np.mean([x for k, x in m["seconds"].items() if k.startswith("fit_")])
        L.append(f"{'':<11} {'v2':<3} {se['rows']:>5} {se['years']:>5.2f} {se['turnover_per_unit_gross']:>7.4f} "
                 f"{se['cost_per_year']:>7.4f} {se['cost_drag_sharpe']:>6.3f} {se['bar95']:>6.3f} {se['net_80']:>6.3f} "
                 f"{se['gross_80']:>6.3f} {fit:>6.0f}")
    L.append("v1 turnover is per row (ridge_stack holds unit gross); v1 s/fit is one ridge_stack run; "
             "v2 s/fit is the mean of the two memories' fits")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design_v2.json").exists():
        raise SystemExit(f"{out / 'design_v2.json'} exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    v1 = json.loads(V1_TABLE.read_text())
    # the 4h jobs first (the long ones), so the daily ones fill in around them
    tasks = [("main", "4h"), ("leak", "4h")] + [(k, v) for v in VARIANTS[1:] for k in ("main", "leak")] + \
            [("block_leak", v) for v in VARIANTS]
    res = {}
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        for kind, name, r in ex.map(run_job, tasks):
            res[(kind, name)] = r
            print(f"{kind} {name} done ({r['job_seconds']:.0f} s; {time.time() - t0:.0f} s elapsed)", flush=True)
    L = report(res, v1)
    L.append(f"wall {time.time() - t0:.0f} s")
    (out / "design_v2.txt").write_text("\n".join(L) + "\n")
    (out / "design_v2.json").write_text(json.dumps({f"{k} {v}": r for (k, v), r in res.items()}, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
