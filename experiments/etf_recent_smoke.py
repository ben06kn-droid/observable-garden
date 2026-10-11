"""ETF recent panel: the smoke, COST ONLY (seconds and bytes recorded; no rule quantity), for
`prereg/etf-recent-panel.md` section j. On a SYNTHETIC panel of the read's size (40 ETFs x
5,033 sessions, prices and volumes, SPY among them), never real data; laptop. Seeds from the
block 721100-721199 (checked 2026-10-11: NO COLLISION): 721100 draws the synthetic panel,
721101 the stream tests, 721102 the class null.

Times: one Sancho fit at d = 1 (both memories, by memory); the W2 stream test and the
unweighted one at B 5,000; the fast kernel's table build and the W2 class null at B 5,000 on
1,024 members, extrapolated linearly to 82,240; and the class table's size in bytes at 82,240
members x the panel's feature rows: the fast kernel's cache holds two float64 arrays (g and k),
so 16 bytes per member-row on disk.

    python -m experiments.etf_recent_smoke --out runs/etf_recent_smoke/<date>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import shutil
import time
from pathlib import Path

import numpy as np

N_MEMBERS = 82240


def synthetic(T: int = 5033, M: int = 40, seed: int = 721100):
    """(dates, tickers, P, Vol): business days from 2005-01-03, a common factor plus noise,
    lognormal volumes. SPY is one of the tickers (the declared market)."""
    rng = np.random.default_rng(seed)
    f = 0.008 * rng.standard_normal(T)
    R = f[:, None] * rng.uniform(0.5, 1.5, M)[None, :] + 0.008 * rng.standard_normal((T, M))
    P = 100.0 * np.cumprod(1.0 + R, axis=0)
    Vol = np.exp(rng.normal(14.0, 0.6, (T, M)))
    days = np.busday_offset("2005-01-03", np.arange(T), roll="forward")
    dates = [dt.date.fromisoformat(str(d)) for d in days]
    tickers = ["SPY"] + [f"E{j:02d}" for j in range(M - 1)]
    return dates, tickers, P, Vol


def main(argv=None) -> int:
    import environments.planted_fast as pf
    from environments.class_table import CHUNK, members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import etf_recent_read as ER
    from learn2 import views as Vw
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "smoke.json").exists():
        raise SystemExit("exists; the smoke runs once")
    out.mkdir(parents=True, exist_ok=True)
    sec = {}
    dates, tickers, P, Vol = synthetic()
    t0 = time.time()
    lag, book, first, by_mem = ER._fit((dates, tickers, P, Vol, 2))
    sec["sancho_fit_d1"] = time.time() - t0
    sec["sancho_fit_d1_by_memory"] = by_mem
    panel, inp = ER.sancho_inputs(dates, tickers, P, Vol, 2)
    rows = np.arange(first, inp.earned.shape[0])
    x = Vw.net_stream(book, inp, rows)
    t0 = time.time()
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    sec["base_columns_and_block_length"] = time.time() - t0
    t0 = time.time()
    Rc.stream_test_w2(x, L, 252.0, 5000, 721101, h=1260)
    sec["stream_W2_B5000"] = time.time() - t0
    t0 = time.time()
    Rc.stream_test(x, L, 252.0, 5000, 721101)
    sec["stream_unweighted_B5000"] = time.time() - t0
    members = members_in_order(CLS, 40)[:1024]
    t0 = time.time()
    cache = pf.build(panel, members, name="etf-recent-smoke", cache_dir=out / "cache")
    sec["class_table_build_1024"] = time.time() - t0
    F = pf.feature_returns(panel)
    t0 = time.time()
    Rc.class_null_w2((pf.streams(cache, F, s0, min(s0 + CHUNK, cache.N)) for s0 in range(0, cache.N, CHUNK)),
                     panel.features.shape[0], L, 252.0, 5000, 721102, 1260)
    sec["class_W2_null_1024_B5000"] = time.time() - t0
    k = N_MEMBERS / 1024
    sec["extrapolated_class_82240"] = {"table_build": sec["class_table_build_1024"] * k,
                                       "W2_null": sec["class_W2_null_1024_B5000"] * k}
    T_feat = int(panel.features.shape[0])
    rec = {"smoke": True, "platform": f"{platform.system()} {platform.machine()}", "sessions": int(P.shape[0]),
           "etfs": int(P.shape[1]), "panel_rows": T_feat, "first_scored_row_d1": int(first),
           "class_table_bytes_82240": N_MEMBERS * T_feat * 8 * 2, "seconds": sec}
    (out / "smoke.json").write_text(json.dumps(rec, indent=1, default=float))
    lines = [f"ETF recent panel smoke (COST ONLY; synthetic {rec['etfs']} x {rec['sessions']}; {rec['platform']})",
             f"one Sancho fit at d = 1: {sec['sancho_fit_d1']:.0f} s "
             + "(" + ", ".join(f"{m} {s:.0f} s" for m, s in by_mem.items()) + ")",
             f"stream W2 B 5,000: {sec['stream_W2_B5000']:.0f} s; unweighted: {sec['stream_unweighted_B5000']:.0f} s",
             f"class, 82,240 members (extrapolated from 1,024): table {sec['extrapolated_class_82240']['table_build']:.0f} s, "
             f"W2 null {sec['extrapolated_class_82240']['W2_null']:.0f} s; cache (g and k) {rec['class_table_bytes_82240'] / 1e9:.2f} GB"]
    (out / "smoke.txt").write_text("\n".join(lines) + "\n")
    shutil.rmtree(out / "cache", ignore_errors=True)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
