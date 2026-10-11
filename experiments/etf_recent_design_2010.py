"""ETF recent panel, amendment 2 (`850d59d`): the design numbers recomputed under its windows.
Outcome-free; laptop; nothing is fetched; no row before 2010-01-04 is used.

**The pool, from already-read data only, with no row before 2010.**
- The source is the 2026-09-22 fetch's in-sample files (`data/raw/etf_insample/`, read for
  `prereg/agent-on-real-data.md`, 2005-2022), each checked against `data/etf_manifest.json`.
- Only the 38 ETFs of this panel's cut, and only rows from 2010-01-04 to 2022-12-31: rows
  before 2010-01-04 are skipped by date before any value is parsed.
- Built with the runner's own panel (`experiments.etf_recent_read.etf_panel`, d = 1) at zero
  cost. Each of the 82,240 signed members' gross streams is demeaned over the pool, so every
  null is exact and only the dependence is used. The base feature columns are demeaned too.
- The pool is written once to `data/planted_cache/etf2010_pool/` with a manifest of SHA-256s.

**The lengths (amendment 2):** every test is scored on 2015-01-02..2024-12-31, 2,516 rows.
The method is that of `experiments/etf_recent_design_w2.py`: the stream's W2 bars (5 panels,
B 2,000) at d = 1 (0.03 / 0.06) and d = 0 (0.01 / 0.02); the class's W2 bars (3 panels) at
0.01 / 0.02; the net Sharpe at 80% power over the weighted effective years; the null's 0.90
quantile g (L90 = S - g); the holdout SE and the approximate P(held) at 444 rows.

Seeds: 722000-722999 (checked 2026-10-11: NO COLLISION).

    python -m experiments.etf_recent_design_2010 --out runs/etf_recent_design_2010/2026-10-11
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np

SRC = Path("data/raw/etf_insample")
MANIFEST = Path("data/etf_manifest.json")
CUT = Path("runs/etf_recent_cuts/insample.cut.json")
POOL = Path("data/planted_cache/etf2010_pool")
USE_FROM = dt.date(2010, 1, 4)
SRC_END = dt.date(2022, 12, 31)
SCORED_ROWS = 2516                  # XNYS sessions 2015-01-02..2024-12-31
ALPHAS = {"stream d = 1": (0.03, 0.06), "stream d = 0 (NOT IMPLEMENTABLE)": (0.01, 0.02), "class": (0.01, 0.02)}
B = 2000
H = 1260


def tickers() -> list[str]:
    return sorted(json.loads(CUT.read_text())["included"])


def load_src(tks: list[str]):
    """(dates, P, Vol) from 2010-01-04 to 2022-12-31; each file's SHA-256 checked first; rows
    before 2010-01-04 skipped by date before any value is parsed."""
    man = json.loads(MANIFEST.read_text())["derived"]
    dates0, cols = None, []
    for t in tks:
        f = SRC / f"{t}.csv"
        if hashlib.sha256(f.read_bytes()).hexdigest() != man[t]["insample"]["sha256"]:
            raise SystemExit(f"REFUSED: {f} is not its manifest SHA-256")
        ds, px, vo = [], [], []
        with open(f, newline="") as fh:
            for row in csv.DictReader(fh):
                d = dt.date.fromisoformat(row["date"])
                if d < USE_FROM or d > SRC_END:
                    continue
                ds.append(d)
                px.append(float(row["adjclose"]))
                vo.append(float(row["volume"]))
        if dates0 is None:
            dates0 = ds
        elif ds != dates0:
            raise SystemExit(f"REFUSED: {t}'s dates differ")
        cols.append((px, vo))
    if dates0[0] != USE_FROM:
        raise SystemExit(f"REFUSED: the pool starts {dates0[0]}, not {USE_FROM}")
    P = np.ascontiguousarray(np.array([c[0] for c in cols], float).T)
    Vol = np.ascontiguousarray(np.array([c[1] for c in cols], float).T)
    return dates0, P, Vol


def build_pool() -> dict:
    import dataclasses
    import environments.planted_fast as pf
    from environments.class_table import CHUNK, members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments import etf_recent_read as ER
    if (POOL / "manifest.json").exists():
        raise SystemExit(f"{POOL / 'manifest.json'} exists; the pool is built once")
    POOL.mkdir(parents=True, exist_ok=True)
    tks = tickers()
    dates, P, Vol = load_src(tks)
    panel, _ = ER.etf_panel(dates, tks, P, Vol, lag=2)
    z = np.zeros_like(np.asarray(panel.cost_rate, float))
    panel = dataclasses.replace(panel, cost_rate=z, borrow_rate=np.zeros_like(z))
    members = members_in_order(CLS, 40)
    cache = pf.build(panel, members, name="etf2010-pool-gross", cache_dir=POOL / "cache")
    F = pf.feature_returns(panel)
    T, N = panel.features.shape[0], len(members)
    G = np.lib.format.open_memmap(POOL / "G.npy", mode="w+", dtype=np.float64, shape=(N, T))
    for s0 in range(0, N, CHUNK):
        X = pf.streams(cache, F, s0, min(s0 + CHUNK, N))
        G[s0:s0 + len(X)] = X - X.mean(axis=1, keepdims=True)
    G.flush()
    del G
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    np.save(POOL / "BC.npy", bc - bc.mean(axis=0))
    sha = {f: hashlib.sha256((POOL / f).read_bytes()).hexdigest() for f in ("G.npy", "BC.npy")}
    man = {"T_pool": T, "N": N, "tickers": tks, "first_feature_date": str(panel.meta["dates"][0]),
           "last_earned_date": str(panel.meta["earned_dates"][-1]), "rows_from": str(USE_FROM),
           "sha256": sha, "built_on": f"{platform.system()} {platform.machine()}"}
    (POOL / "manifest.json").write_text(json.dumps(man, indent=1))
    return man


def main(argv=None) -> int:
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import recency_planted as P1
    from experiments.binance_design_quantities import certified_sharpe
    from experiments.etf_recent_design_w2 import phi, se_sharpe, sessions
    from experiments.french_long_design_w2 import class_maxima_w2
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout-end", default="2026-10-09")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit("exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    man = build_pool()
    G = np.load(POOL / "G.npy", mmap_mode="r")
    BC = np.load(POOL / "BC.npy")
    n_pool = BC.shape[0]
    if sessions("2015-01-02", "2024-12-31") != SCORED_ROWS:
        raise SystemExit("REFUSED: the scored window's session count is not 2,516")
    seeds = iter(range(722000, 723000))
    qs = sorted({round(1 - x, 4) for v in ALPHAS.values() for x in v} | {0.9})
    n_ho = sessions("2025-01-02", a.holdout_end)
    y_ho = n_ho / 252
    rec = {"pool": man, "B": B, "h": H, "scored_rows": SCORED_ROWS,
           "holdout": {"end": a.holdout_end, "rows": n_ho, "years": y_ho, "se_at_0": se_sharpe(0, y_ho)}}
    r = {}
    for kind, n_panels in (("stream", 5), ("class", 3)):
        T = SCORED_ROWS
        w = Rc.weights(T, H)
        neff_y = w.sum() ** 2 / (w * w).sum() / 252
        panels = []
        for _ in range(n_panels):
            s = next(seeds)
            rng = np.random.default_rng(s)
            i = P1.pool_rows(T, n_pool, P1.ROW_BLOCK, rng)
            bc = BC[i]
            L = int(select_block_length(bc - bc.mean(axis=0)))
            t1 = time.time()
            if kind == "stream":
                x = bc[:, int(rng.integers(bc.shape[1]))]
                M = Rc.stream_test_w2(x, L, 252.0, B, s, h=H)["null_max"]
            else:
                M = class_maxima_w2(G, i, L, s, B)
            panels.append({"seed": s, "L": L, "seconds": time.time() - t1,
                           "q": {f"{q:.4f}": float(np.quantile(M, q)) for q in qs}})
        r[kind] = {"rows": T, "years": T / 252, "n_eff_years": neff_y, "panels": panels}
    summ = {}
    for test, alphas in ALPHAS.items():
        src = r["class" if test == "class" else "stream"]
        g = float(np.mean([p["q"]["0.9000"] for p in src["panels"]]))
        for lvl, al in zip(("96%", "90%"), alphas):
            bar = float(np.mean([p["q"][f"{1 - al:.4f}"] for p in src["panels"]]))
            se = se_sharpe(bar, y_ho)
            summ[f"{test}, {lvl} (alpha {al})"] = {
                "bar": bar, "net80": certified_sharpe(bar, src["n_eff_years"], 252.0), "g_L90": g,
                "holdout_se_at_bar": se, "P_held_true_eq_bar": phi(g / se),
                "P_held_true_0_certified_at_bar": phi(-(bar - g) / se_sharpe(0, y_ho))}
    rec["tests"], rec["summary"] = r, summ
    rec["seconds"] = time.time() - t0
    L = [f"ETF recent panel, amendment 2: design numbers under W2 (outcome-free; the 2010+ pool: "
         f"{len(man['tickers'])} ETFs, {n_pool} rows {man['first_feature_date']}..{man['last_earned_date']}; h {H}; B {B})",
         "=" * 100,
         f"scored 2015-01-02..2024-12-31: {SCORED_ROWS} rows (weighted effective {r['stream']['n_eff_years']:.1f} y); "
         f"holdout 2025-01-02..{a.holdout_end}: {n_ho} rows ({y_ho:.2f} y), SE at Sharpe 0 {rec['holdout']['se_at_0']:.3f}"]
    for k, v in summ.items():
        L.append(f"   {k:<44} W2 bar {v['bar']:.3f} -> net 80% {v['net80']:.3f}; L90 gap {v['g_L90']:.3f}; "
                 f"P(held | true = bar) {v['P_held_true_eq_bar']:.2f}; P(held | true 0, certified at bar) "
                 f"{v['P_held_true_0_certified_at_bar']:.2f}")
    L.append(f"wall {rec['seconds']:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
