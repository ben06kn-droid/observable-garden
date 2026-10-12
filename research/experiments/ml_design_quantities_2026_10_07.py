"""Design quantities for the ML pilot that read no outcome
(`prereg/ml-pipeline-exploratory-2026-10-07.md`): Part 3a (each rule's turnover, its
fast/slow label, c and the plant's gross and net population Sharpe, and for the gated rule
the dispersion state with and without the plant) and Part 5a (the linear shadow: the best
class member's population Sharpe as a share of the planted edge).

Draws on the dedicated block 685000-685999: U and gated on all 40 features (seeds
685000+a and 685100+a for the residual), corner and product by seeded pair draws (100 each,
685200-685299 and 685300-685399). Positions, costs and population moments only; no
realised return of any predictor is computed.

    python -m experiments.ml_design_quantities_2026_10_07 --out runs/ml_design/2026-10-07 --workers 2
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

BETAS = (1.0, 1.5, 2.5)
BETA_RECORD = 1.5


def draws() -> list[tuple[int, str, dict]]:
    from environments import planted_rules as prl
    out = []
    for a in range(40):
        out.append((685000 + a, "U", {"shape": "U", "a": a, "b": None}))
        out.append((685100 + a, "gated", {"shape": "gated", "a": a, "b": None}))
    for i in range(100):
        out.append((685200 + i, "corner", prl.draw_features(685200 + i, "corner")))
        out.append((685300 + i, "product", prl.draw_features(685300 + i, "product")))
    return out


_W = {}


def _init():
    if not _W:
        import environments.planted_panel as pp
        import environments.planted_fast as pf
        base = pp.load_base()
        _W.update(base=base, cache=pf.build(base.in_sample, base.members),
                  D=pf.demeaned(base.in_sample), inv=pp.invariants_for(base))
    return _W


def one(task):
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments import planted_rules as prl
    from environments.class_table import CHUNK
    from learn import inputs as I
    seed, shape, rule = task
    W = _init()
    base, cache, D, inv = W["base"], W["cache"], W["D"], W["inv"]
    t0 = time.time()
    d = prl.make_draw_rule(base, seed, BETA_RECORD, shape, rule)
    w = d.w_star_is
    rec = prl.plant_record(base, d)
    G = np.einsum("tmk,tm->tk", D, w)
    N = cache.N
    Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    for s in range(0, N, CHUNK):
        a = pf.overlap(cache, G, s, min(s + CHUNK, N))
        k = np.asarray(cache.k[s:s + len(a)])
        Ea[s:s + len(a)] = a.mean(axis=1)
        Ea2[s:s + len(a)] = (a * a).mean(axis=1)
        Eak[s:s + len(a)] = (a * k).mean(axis=1)
    ppy = base.in_sample.periods_per_year
    shadow = {}
    for beta in BETAS:
        c = pp.planted_scale(base.in_sample, base.Sigma_is, w, beta)
        pop = pp.population_from_moments(Ea, Ea2, Eak, inv, c, ppy)
        shadow[str(beta)] = float(pop.max() / beta)
    out = {"seed": seed, "shape": shape, "rule": rule, "turnover": rec["turnover"],
           "speed": rec["speed"], "c_1.5": rec["c"], "gross_1.5": rec["gross"]["in_sample"],
           "net_1.5": rec["net"]["in_sample"], "gross_ho_1.5": rec["gross"]["holdout"],
           "net_ho_1.5": rec["net"]["holdout"], "shadow_share": shadow}
    if shape == "gated":
        E = base.E_is[d.idx_is]
        gate = prl.gate(E).astype(float)
        disp_without = I.market_states(E)[:, 2]
        disp_with = I.market_states(d.in_sample.returns)[:, 2]
        ok = np.arange(len(gate)) >= 252 + 22
        cc = lambda x: float(np.corrcoef(x[ok], gate[ok])[0, 1]) if x[ok].std() > 0 else 0.0
        out["dispersion"] = {"corr_gate_without_plant": cc(disp_without),
                             "corr_gate_with_plant": cc(disp_with),
                             "mean_abs_shift": float(np.abs(disp_with - disp_without)[ok].mean()),
                             "on_share": float(gate.mean())}
    out["seconds"] = time.time() - t0
    return out


def q(x):
    x = np.asarray(x, float)
    if x.size == 0:
        return "n 0"
    p = np.percentile(x, [0, 25, 50, 75, 100])
    return (f"n {x.size:3d}  min {p[0]:.3f}  q25 {p[1]:.3f}  med {p[2]:.3f}  q75 {p[3]:.3f}  "
            f"max {p[4]:.3f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limit", type=int, default=None, help="first n draws only (a check)")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tasks = draws()[:a.limit] if a.limit else draws()
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        res = list(ex.map(one, tasks))
    with open(out / "draws.jsonl", "w") as fh:
        for r in res:
            fh.write(json.dumps(r) + "\n")
    L = ["ML design quantities (no outcome read) — draws on 685000-685999",
         "=" * 88]
    L.append("3a. TURNOVER (sum |change| / sum gross) and the fast/slow label (> 0.5), with c and "
             f"the plant's population Sharpe at net level {BETA_RECORD}")
    for shape in ("U", "corner", "product", "gated"):
        g = [r for r in res if r["shape"] == shape]
        if not g:
            continue
        L.append(f"   {shape:<8} turnover {q([r['turnover'] for r in g])}")
        L.append(f"   {'':<8} fast {sum(r['speed'] == 'fast' for r in g)} / slow "
                 f"{sum(r['speed'] == 'slow' for r in g)}")
        L.append(f"   {'':<8} c        {q([r['c_1.5'] for r in g])}")
        L.append(f"   {'':<8} gross SR {q([r['gross_1.5'] for r in g])}   (net fixed at 1.5)")
        L.append(f"   {'':<8} holdout net SR {q([r['net_ho_1.5'] for r in g])}")
    gd = [r for r in res if r["shape"] == "gated"]
    if gd:
        L.append("   gated: the 21-row dispersion state against the gate (correlation), without and "
                 "with the plant, at net 1.5")
        L.append(f"   {'':<8} without  {q([r['dispersion']['corr_gate_without_plant'] for r in gd])}")
        L.append(f"   {'':<8} with     {q([r['dispersion']['corr_gate_with_plant'] for r in gd])}")
        L.append(f"   {'':<8} mean |shift| of the state {q([r['dispersion']['mean_abs_shift'] for r in gd])}")
        L.append(f"   {'':<8} share of days on {q([r['dispersion']['on_share'] for r in gd])}")
    L.append("")
    L.append("5a. LINEAR SHADOW: best class member's population net Sharpe / planted net Sharpe")
    for shape in ("U", "corner", "product", "gated"):
        for beta in BETAS:
            for sp in ("pooled", "fast", "slow"):
                g = [r for r in res if r["shape"] == shape and (sp == "pooled" or r["speed"] == sp)]
                thin = "  THIN" if 0 < len(g) < 5 else ""
                L.append(f"   {shape:<8} level {beta}  {sp:<6} {q([r['shadow_share'][str(beta)] for r in g])}{thin}")
    L.append("")
    L.append(f"wall {time.time() - t0:.0f} s, {len(res)} draws, {a.workers} workers")
    text = "\n".join(L)
    (out / "design_quantities.txt").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
