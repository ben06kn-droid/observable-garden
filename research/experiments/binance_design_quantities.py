"""Outcome-free design quantities for the Binance 4h panel (draft `prereg/binance-panel.md`).
In-sample window only, on the laptop. PROVISIONAL: computed on the UNPINNED build under the
draft's proposed data rules; X is pinned only after the author settles those rules.

Printed: each tier's scored window (rows, calendar dates, years at 2,190 bars a year); the
class null maximum and the stream's null bar at 95%, 96%, 97.5% and 99% (B 5,000,
stationary bootstrap, block length by the class rule); the true net Sharpe each bar
certifies with 80% power; seconds per pricing call (fast kernel, and the slow path
`streams_for` extrapolated from a sample); ridge_stack's leak test and bit-for-bit repeat
(positions only).

**Never computed, printed or stored:** any observed member Sharpe, the class maximum,
ridge_stack's realised mean or Sharpe, any p-value or certification.

Power: the annualised Sharpe estimate over T_years (rows / 2,190) is normal with standard
error sqrt((1 + SR^2 / (2 * ppy)) / T_years) (Lo 2002, iid, per-period SR = SR / sqrt(ppy));
the certified SR solves SR - 0.8416 * se(SR) = bar. Selection is ignored.

Seeds 695000 (class null), 695001 (stream null), 695002 (leak test); block 695000-695999.

    python -m experiments.binance_design_quantities --out runs/binance_design/2026-10-08
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

B = 5000
QUANTILES = (0.95, 0.96, 0.975, 0.99)
SEED_CLASS, SEED_STREAM, SEED_LEAK = 695000, 695001, 695002
Z80 = 0.8416212335729143
SLOW_SAMPLE = 128


def certified_sharpe(bar: float, T_years: float, ppy: float) -> float:
    from scipy.optimize import brentq
    f = lambda sr: sr - Z80 * np.sqrt((1 + sr * sr / (2 * ppy)) / T_years) - bar
    return float(brentq(f, bar, bar + 20.0))


def main(argv=None) -> int:
    import environments.planted_fast as pf
    from environments.binance_panel import build_binance_panel
    from environments.class_table import members_in_order, streams_for
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments.french_design_quantities import class_null
    from learn import inputs as I
    from learn import leak, ridge_stack, stream_tier
    import experiments.french_design_quantities as fdq
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L, rec = [], {}

    def P(s=""):
        L.append(s)
        print(s, flush=True)

    import lightgbm
    P("Binance USDT-M perpetuals, 4h: outcome-free design quantities (in-sample only). PROVISIONAL: unpinned build")
    P("=" * 88)
    P(f"platform {platform.system()} {platform.machine()}; lightgbm {lightgbm.__version__} (laptop)")
    panel, info = build_binance_panel(pinned=False, with_info=True)
    T, M, K = panel.features.shape
    ppy = panel.periods_per_year
    eo = panel.meta["earned_opens"]
    P(f"panel: {T} feature rows, earned bars {eo[0]} .. {eo[-1]}; {M} contracts; {K} features; ppy {ppy:.0f}")
    dead = {s: v["dead_bar"] for s, v in info.items() if v["dead_bar"] is not None}
    P(f"   contracts dead before the end of the in-sample window: {len(dead)}")
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)

    members = members_in_order(CLS, K)
    pf.check_panel(panel)
    t0 = time.time()
    cache = pf.build(panel, members, name="binance-usdtm-4h-signed-3")
    P("")
    P(f"CLASS TIER: fast kernel accepts the panel (no mask); cache opened/built in {time.time() - t0:.0f} s")
    rng = np.random.default_rng(0)
    pick = sorted(rng.choice(len(members), SLOW_SAMPLE, replace=False).tolist())
    F = pf.feature_returns(panel)
    fast = np.vstack([pf.streams(cache, F, j, j + 1) for j in pick])
    t0 = time.time()
    ref = streams_for(panel, [members[j] for j in pick])
    t_slow = time.time() - t0
    diff = float(np.abs(fast - ref).max() / max(np.abs(ref).max(), 1e-300))
    del fast, ref
    P(f"   fast vs registered streams_for on {SLOW_SAMPLE} members: max relative difference {diff:.1e}")
    P(f"   slow path (streams_for): {t_slow:.1f} s for {SLOW_SAMPLE} members -> about "
      f"{t_slow * len(members) / SLOW_SAMPLE / 60:.0f} min for one pass over all {len(members)} "
      f"(observed streams only; a null pass needs the streams again or 82,240 x {T} in memory, "
      f"{82240 * T * 8 / 1e9:.1f} GB)")
    fdq.B = B
    t0 = time.time()
    M_b, Lc = class_null(panel, cache, bc, SEED_CLASS)
    t_class = time.time() - t0
    Ty = T / ppy
    rec["class"] = {"rows": T, "years": Ty, "first": eo[0], "last": eo[-1], "block_length": Lc,
                    "B": B, "seed": SEED_CLASS, "seconds": t_class, "slow_path_sample_seconds": t_slow,
                    "bars": {}}
    P(f"   window: all {T} rows ({eo[0]} .. {eo[-1]}), {Ty:.2f} years; block length {Lc}; B {B}, seed {SEED_CLASS}")
    for qq in QUANTILES:
        bar = float(np.quantile(M_b, qq))
        sr = certified_sharpe(bar, Ty, ppy)
        rec["class"]["bars"][str(qq)] = {"bar": bar, "certified_sharpe_80": sr}
        P(f"   null maximum at {qq:.3f}: {bar:.3f}; certified with 80% power: {sr:.3f}")
    P(f"   seconds per class-tier pricing call (fast kernel, B {B}): {t_class:.1f}")

    P("")
    P("RIDGE_STACK, one declared stream (code as pinned at fce5627)")
    run = lambda p: ridge_stack.run(p, "ridge_stack")
    t0 = time.time()
    res = run(panel)
    t_run = time.time() - t0
    rows = res["scored_rows"]
    Ry = len(rows) / ppy
    P(f"   252-row 'years' = 42 days; refits every 252 rows; scored rows {rows[0]}..{rows[-1]} "
      f"({len(rows)} rows, {Ry:.2f} years; earned bars {eo[rows[0]]} .. {eo[rows[-1]]})")
    t0 = time.time()
    s0 = I.net_stream(res["positions"], panel, rows)
    s0 = s0 - s0.mean()
    table = stream_tier.table_from_streams(s0[None, :], ppy)
    del s0
    brow, Lr = stream_tier.bootstrap_rows(bc[rows], B, SEED_STREAM)
    R_b = np.asarray(table.null_max(brow), float)
    t_tier = time.time() - t0
    rec["ridge_stack"] = {"rows": int(len(rows)), "years": Ry, "first": eo[rows[0]], "last": eo[rows[-1]],
                          "block_length": Lr, "B": B, "seed": SEED_STREAM,
                          "seconds_run": t_run, "seconds_tier": t_tier, "bars": {}}
    P(f"   block length {Lr}; B {B}, seed {SEED_STREAM}")
    for qq in QUANTILES:
        bar = float(np.quantile(R_b, qq))
        sr = certified_sharpe(bar, Ry, ppy)
        rec["ridge_stack"]["bars"][str(qq)] = {"bar": bar, "certified_sharpe_80": sr}
        P(f"   null bar at {qq:.3f} (demeaned stream): {bar:.3f}; certified with 80% power: {sr:.3f}")
    P(f"   seconds per pricing call: predictor {t_run:.0f} + tier {t_tier:.1f}")
    rep = bool(np.array_equal(res["positions"], run(panel)["positions"]))
    lrows = (int(rows[0]) + 500, T // 2, T - 300)
    lk = leak.leak_test(run, panel, lrows, seed=SEED_LEAK)
    ok = all(r["identical_up_to_d"] for r in lk)
    seen = any(r["changed_after_d"] for r in lk)
    rec["repeat_bit_identical"] = rep
    rec["leak_test"] = {"rows": list(lrows), "pass": ok, "change_visible_after_d": seen}
    P(f"   bit-for-bit repeat (positions): {rep}; leak test at rows {list(lrows)}: "
      f"{'PASS' if ok else 'FAIL'} (a later change was visible after d: {seen})")
    P("")
    P("power: SR - 0.8416 * sqrt((1 + SR^2/(2 ppy)) / T_years) = bar (Lo 2002, iid)")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
