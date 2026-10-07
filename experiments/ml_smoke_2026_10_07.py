"""Cost-only smoke for the ML pilot (`prereg/ml-pipeline-exploratory-2026-10-07.md`, Part 4),
with Part 5b's design quantity. Level-0 planted panels on the dedicated block 686000-686999.

Printed: seconds per panel for each predictor alone, and for the class tier beside it
(the fast kernel's class pass at B = 1,000, plus the supplied-streams tier on the
predictor's stream); the leak test; repeatability across two runs; and, from mv_combine's
fits, the effective parameters, total and by block, for each c in the grid. **No
certification rate, no capture, no Sharpe, no p-value and no rule quantity is printed or
stored.**

    python -m experiments.ml_smoke_2026_10_07 --out runs/ml_smoke/2026-10-07
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

SEEDS = (686000, 686001)
LEAK_ROWS = (1000, 1700, 2600)
B = 1000


def predictors():
    from learn import mv_combine, ridge_stack
    return {"mv_combine risk on": lambda p: mv_combine.run(p, True),
            "mv_combine risk off": lambda p: mv_combine.run(p, False),
            "ridge_stack": lambda p: ridge_stack.run(p, "ridge_stack"),
            "control": lambda p: ridge_stack.run(p, "control")}


def main(argv=None) -> int:
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.real_sandbox import RealSandbox
    from learn import inputs as I
    from learn import leak, mv_combine, stream_tier
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS),
                    help="smoke panels (the laptop smoke used 686000 686001; the box smoke "
                         "uses 686002 686003)")
    a = ap.parse_args(argv)
    seeds = tuple(a.seeds)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L: list[str] = []

    def P(s=""):
        L.append(s)
        print(s, flush=True)
    t_all = time.time()
    base = pp.load_base()
    cache = pf.build(base.in_sample, base.members)
    P("ML smoke, cost only — level-0 planted panels on 686000-686999; no outcome printed")
    P("=" * 88)
    preds = predictors()
    eff_rows = []
    import platform
    P(f"platform {platform.system()} {platform.machine()}; seeds {list(seeds)}")
    for seed in seeds:
        d = pp.make_draw(base, seed, 0.0)
        panel = d.in_sample
        T = panel.features.shape[0]
        P(f"panel {seed}: T {T}, {panel.features.shape[1]} assets, level 0")
        t0 = time.time()
        pf.class_pass_levels(base, cache, seed, [0.0], B)
        t_class = time.time() - t0
        P(f"   class tier (fast kernel class pass, B {B}): {t_class:.1f} s")
        bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
        for name, run in preds.items():
            t0 = time.time()
            res = run(panel)
            t_run = time.time() - t0
            rows = res["scored_rows"]
            stream = I.net_stream(res["positions"], panel, rows)
            t0 = time.time()
            stream_tier.certify(stream[None, :], bc[rows], panel.periods_per_year, B, seed)
            t_tier = time.time() - t0
            P(f"   {name:<20} alone {t_run:6.1f} s; supplied-streams tier {t_tier:4.1f} s; "
              f"with the class tier beside it {t_run + t_tier + t_class:6.1f} s; warm-up rows "
              f"dropped {res['warmup_dropped']}")
            if name.startswith("mv_combine"):
                for dg in res["diagnostics"]:
                    eff_rows.append({"seed": seed, "setting": name, "year": dg["year"],
                                     "T_years": dg["T_years"],
                                     "by_c": {str(c): v for c, v in dg["effective_by_c"].items()}})
            if seed == seeds[0]:
                res2 = run(panel)
                rep = bool(np.array_equal(res["positions"], res2["positions"]))
                lk = leak.leak_test(run, panel, LEAK_ROWS, seed=seed)
                ok = all(r["identical_up_to_d"] for r in lk)
                seen = any(r["changed_after_d"] for r in lk)
                P(f"   {'':<20} repeatability (two runs, positions bit-identical): {rep}; leak "
                  f"test at rows {list(LEAK_ROWS)}: {'PASS' if ok else 'FAIL'} (a later change "
                  f"was visible after d: {seen})")
    P("")
    P("5b. mv_combine EFFECTIVE PARAMETERS on level-0 panels, by c (mean over refits; first "
      "and last refit)")
    for name in ("mv_combine risk on", "mv_combine risk off"):
        rows_n = [r for r in eff_rows if r["setting"] == name]
        for c in mv_combine.C_GRID:
            tot = [r["by_c"][str(c)]["total"] for r in rows_n]
            byb = {b: np.mean([r["by_c"][str(c)][b] for r in rows_n]) for b in mv_combine.BLOCKS}
            first = [r["by_c"][str(c)]["total"] for r in rows_n if r["year"] == 3]
            last = [r["by_c"][str(c)]["total"] for r in rows_n if r["year"] == max(x["year"] for x in rows_n)]
            P(f"   {name:<20} c {c:<5} total mean {np.mean(tot):6.2f} (first refit {np.mean(first):6.2f}, "
              f"last {np.mean(last):6.2f}); by block " + ", ".join(f"{b} {v:.2f}" for b, v in byb.items()))
    T_last = np.mean([r["T_years"] for r in eff_rows if r["year"] == max(x["year"] for x in eff_rows)])
    P(f"   training years at the last refit: {T_last:.2f}")
    P(f"wall {time.time() - t_all:.0f} s")
    (out / "smoke.txt").write_text("\n".join(L) + "\n")
    (out / "effective_parameters.json").write_text(json.dumps(eff_rows, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
