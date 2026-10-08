"""Outcome-free design quantities for the French 49-industry panel (draft
`prereg/french-panel.md`, step 3). In-sample window only, on the laptop.

Computed and printed:
- the panel's shape and windows;
- the class tier: the fast kernel's acceptance and a check of its streams against the
  registered `streams_for` (the maximum absolute difference only), its build time, and the
  class null maximum at the 95% and 97.5% points (demeaned streams, stationary bootstrap,
  B = 1,000, block length by the class rule), with seconds per pricing call;
- ridge_stack (as pinned at fce5627; the laptop's macOS LightGBM pin): its scored window,
  and its null bar at 95% and 97.5% from the DEMEANED stream, with seconds per call;
- for each bar, the true net Sharpe certified with 80% power (normal approximation, below);
- whether ridge_stack's leak test passes on this panel (positions only).

**Never computed, printed or stored:** any member's or the class maximum's observed
Sharpe, ridge_stack's realised mean or Sharpe, any p-value or certification. The ridge
stream is demeaned in memory and only its bootstrap replicates are used.

Power: the annualised Sharpe estimate over T_years is taken as normal with mean SR and
standard error sqrt((1 + SR^2 / 2) / T_years) (Lo 2002, iid); the certified true Sharpe
is the SR solving SR - z_0.80 * se(SR) = bar, z_0.80 = 0.8416. It ignores selection: for
the class tier it is the Sharpe of a single member that is also the class's best.

Seeds 692000 (class null), 692001 (ridge null), 692002 (leak test), from the block
692000-692999 (seed_block_check: NO COLLISION on 2026-10-07).

    python -m experiments.french_design_quantities --out runs/french_design/2026-10-07
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np

B = 1000
SEED_CLASS, SEED_RIDGE, SEED_LEAK = 692000, 692001, 692002
QUANTILES = (0.95, 0.975)
Z80 = 0.8416212335729143
LEAK_ROWS = (1000, 1700, 2300)
CHECK_MEMBERS = 256


def certified_sharpe(bar: float, T_years: float) -> float:
    from scipy.optimize import brentq
    f = lambda sr: sr - Z80 * np.sqrt((1 + sr * sr / 2) / T_years) - bar
    return float(brentq(f, bar, bar + 10.0))


def class_null(panel, cache, bc, seed: int):
    """Replicate maxima of the class's DEMEANED streams. No observed score is formed."""
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    T = panel.features.shape[0]
    ann = float(np.sqrt(panel.periods_per_year))
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(seed)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    F = pf.feature_returns(panel)
    M_b = np.full(B, -np.inf)
    for s in range(0, cache.N, CHUNK):
        X = pf.streams(cache, F, s, min(s + CHUNK, cache.N))
        X0 = X - X.mean(axis=1, keepdims=True)
        mean = (X0 @ C) / T
        var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
        pos = var > 0
        rep = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
        M_b = np.maximum(M_b, rep.max(axis=0))
    return M_b, L


def main(argv=None) -> int:
    import environments.planted_fast as pf
    from environments.class_table import members_in_order, streams_for
    from environments.french_panel import build_french_panel
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from learn import inputs as I
    from learn import leak, ridge_stack, stream_tier
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L: list[str] = []
    rec: dict = {}

    def P(s=""):
        L.append(s)
        print(s, flush=True)

    import lightgbm
    P("French 49 industries: outcome-free design quantities (in-sample window only)")
    P("=" * 88)
    P(f"platform {platform.system()} {platform.machine()}; python {platform.python_version()}; "
      f"lightgbm {lightgbm.__version__} (laptop: macOS pin; not box numbers)")
    panel = build_french_panel()
    T, M, K = panel.features.shape
    ed = panel.meta["earned_dates"]
    P(f"panel: T {T} feature rows ({panel.meta['dates'][0]} .. {panel.meta['dates'][-1]}), earned "
      f"dates {ed[0]} .. {ed[-1]}; {M} industries; {K} features")
    rec["panel"] = {"T": T, "M": M, "K": K, "first_earned": str(ed[0]), "last_earned": str(ed[-1])}
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)

    # -- class tier -------------------------------------------------------------------
    P("")
    P("CLASS TIER: SubsetClass max_size 3, signed")
    members = members_in_order(CLS, K)
    try:
        pf.check_panel(panel)
        P(f"   fast kernel: accepts this panel (all periods tradable, not flat overnight); "
          f"{len(members)} members")
    except ValueError as e:
        P(f"   fast kernel REFUSES this panel: {e}")
        raise SystemExit(1)
    t0 = time.time()
    cache = pf.build(panel, members, name="french49-signed-3")
    P(f"   cache: {cache.path} (opened or built in {time.time() - t0:.0f} s)")
    rng = np.random.default_rng(0)
    pick = sorted(set(range(64)) | set(rng.choice(len(members), CHECK_MEMBERS - 64, replace=False).tolist()))
    F = pf.feature_returns(panel)
    fast = np.vstack([pf.streams(cache, F, j, j + 1) for j in pick])
    ref = streams_for(panel, [members[j] for j in pick])
    diff = float(np.abs(fast - ref).max() / max(np.abs(ref).max(), 1e-300))
    P(f"   fast streams vs registered streams_for on {len(pick)} members: max relative abs "
      f"difference {diff:.2e}")
    del fast, ref
    t0 = time.time()
    M_b, Lc = class_null(panel, cache, bc, SEED_CLASS)
    t_class = time.time() - t0
    T_years = T / panel.periods_per_year
    rec["class"] = {"N": len(members), "block_length": Lc, "B": B, "seconds": t_class,
                    "T_years": T_years, "stream_check_max_rel_diff": diff, "bars": {}}
    P(f"   window: all {T} feature rows, {T_years:.2f} years; block length {Lc} (class rule); "
      f"B {B}, seed {SEED_CLASS}")
    for qq in QUANTILES:
        bar = float(np.quantile(M_b, qq))
        sr = certified_sharpe(bar, T_years)
        rec["class"]["bars"][str(qq)] = {"bar": bar, "certified_sharpe_80": sr}
        P(f"   null maximum at {qq:.3f}: {bar:.3f}; true net Sharpe certified with 80% power: {sr:.3f}")
    P(f"   seconds per class-tier pricing call (null pass, cache open): {t_class:.1f}")

    # -- ridge_stack ---------------------------------------------------------------------
    P("")
    P("RIDGE_STACK as one declared stream (code as pinned at fce5627)")
    t0 = time.time()
    res = ridge_stack.run(panel, "ridge_stack")
    t_run = time.time() - t0
    rows = res["scored_rows"]
    ry = len(rows) / panel.periods_per_year
    P(f"   scored window: feature rows {rows[0]}..{rows[-1]} ({len(rows)} rows, {ry:.2f} years); "
      f"earned dates {ed[rows[0]]} .. {ed[rows[-1]]}; warm-up rows dropped {res['warmup_dropped']}")
    t0 = time.time()
    s0 = I.net_stream(res["positions"], panel, rows)
    s0 = s0 - s0.mean()                     # demeaned in memory; the mean is neither kept nor shown
    table = stream_tier.table_from_streams(s0[None, :], panel.periods_per_year)
    del s0
    brow, Lr = stream_tier.bootstrap_rows(bc[rows], B, SEED_RIDGE)
    R_b = np.asarray(table.null_max(brow), float)
    del table
    t_tier = time.time() - t0
    rec["ridge_stack"] = {"first_row": int(rows[0]), "last_row": int(rows[-1]), "n_rows": len(rows),
                          "T_years": ry, "first_earned": str(ed[rows[0]]),
                          "last_earned": str(ed[rows[-1]]), "block_length": Lr, "B": B,
                          "seconds_run": t_run, "seconds_tier": t_tier, "bars": {}}
    P(f"   block length {Lr} (class rule, on the scored rows); B {B}, seed {SEED_RIDGE}")
    for qq in QUANTILES:
        bar = float(np.quantile(R_b, qq))
        sr = certified_sharpe(bar, ry)
        rec["ridge_stack"]["bars"][str(qq)] = {"bar": bar, "certified_sharpe_80": sr}
        P(f"   null bar at {qq:.3f} (demeaned stream): {bar:.3f}; true net Sharpe certified with "
          f"80% power: {sr:.3f}")
    P(f"   seconds per pricing call: predictor {t_run:.1f} + supplied-streams tier {t_tier:.1f}")

    # -- leak test -------------------------------------------------------------------------
    t0 = time.time()
    lk = leak.leak_test(lambda p: ridge_stack.run(p, "ridge_stack"), panel, LEAK_ROWS, seed=SEED_LEAK)
    ok = all(r["identical_up_to_d"] for r in lk)
    seen = any(r["changed_after_d"] for r in lk)
    rec["leak_test"] = {"rows": list(LEAK_ROWS), "pass": ok, "change_visible_after_d": seen}
    P(f"   leak test at rows {list(LEAK_ROWS)} (positions only): {'PASS' if ok else 'FAIL'} "
      f"(a later change was visible after d: {seen}); {time.time() - t0:.0f} s")
    P("")
    P(f"power: SR - {Z80:.4f} * sqrt((1 + SR^2/2) / T_years) = bar (normal approximation, iid)")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
