"""French long history: the smoke, COST ONLY (seconds recorded; no rule quantity). On a
SYNTHETIC panel of B1's length (16,000 rows, 49 industries, staggered entries), never the real
file. Seeds 717000-717009 (checked 2026-10-11: NO COLLISION): 717000 draws the synthetic
returns; 717001-717003 the test seeds.

Times: one Sancho fit at d = 1 (two memories); the W2 stream test and the unweighted one at
B 5,000; the fast kernel's table build and the W2 class null at B 5,000 on 1,024 members,
extrapolated linearly to 82,240.

    python -m experiments.french_long_smoke --out runs/french_long_smoke/<date>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import time
from pathlib import Path

import numpy as np


def synthetic(T: int = 16000, M: int = 49, seed: int = 717000):
    rng = np.random.default_rng(seed)
    R = 0.01 * rng.standard_normal((T, M))
    starts = rng.integers(0, 4000, size=M)
    starts[:30] = 0
    for j, s in enumerate(starts):
        R[:s, j] = np.nan
    d0 = dt.date(1926, 7, 1)
    return [d0 + dt.timedelta(days=k) for k in range(T)], [f"N{j:02d}" for j in range(M)], R


def main(argv=None) -> int:
    import environments.planted_fast as pf
    from environments.class_table import CHUNK, members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import french_long_read as FL
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sec = {}
    dates, names, R = synthetic()
    t0 = time.time()
    lag, book, first, s = FL._fit((dates, names, R, 2))
    sec["sancho_fit_d1"] = time.time() - t0
    sec["sancho_fit_d1_by_memory"] = s
    panel, info, inp = FL.sancho_inputs(dates, names, R, 2)
    from learn2 import views as Vw
    rows = np.arange(first, inp.earned.shape[0])
    x = Vw.net_stream(book, inp, rows)
    t0 = time.time()
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    sec["base_columns_and_block_length"] = time.time() - t0
    t0 = time.time()
    Rc.stream_test_w2(x, L, 252.0, 5000, 717001, h=1260)
    sec["stream_W2_B5000"] = time.time() - t0
    t0 = time.time()
    Rc.stream_test(x, L, 252.0, 5000, 717001)
    sec["stream_unweighted_B5000"] = time.time() - t0
    members = members_in_order(CLS, 40)[:1024]
    t0 = time.time()
    cache = pf.build(panel, members, name="french-long-smoke", cache_dir=out / "cache")
    sec["class_table_build_1024"] = time.time() - t0
    F = pf.feature_returns(panel)
    t0 = time.time()
    Rc.class_null_w2((pf.streams(cache, F, s0, min(s0 + CHUNK, cache.N)) for s0 in range(0, cache.N, CHUNK)),
                     panel.features.shape[0], L, 252.0, 5000, 717002, 1260)
    sec["class_W2_null_1024_B5000"] = time.time() - t0
    k = 82240 / 1024
    sec["extrapolated_class_82240"] = {"table_build": sec["class_table_build_1024"] * k,
                                       "W2_null": sec["class_W2_null_1024_B5000"] * k}
    rec = {"smoke": True, "platform": f"{platform.system()} {platform.machine()}", "rows": int(R.shape[0]),
           "panel_rows": int(panel.features.shape[0]), "seconds": sec}
    (out / "smoke.json").write_text(json.dumps(rec, indent=1, default=float))
    import shutil
    shutil.rmtree(out / "cache", ignore_errors=True)
    print(json.dumps(rec, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
