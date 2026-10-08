"""Reader for the version-2 pilot (`prereg/ml-v2-exploratory-2026-10-08.md`, pilot section
817f8d2). EXPLORATORY. Committed and tested on made-up rows before any pilot result exists.
Reads once, in order: R1, R2, R3, R4, then the grid rule, the replacement rule and the
fairness flag. Menu pricing is descriptive only.

    python -m experiments.read_ml_v2_pilot_2026_10_08 --dir runs/ml_v2_pilot/2026-10-08
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
ORIGINAL = ("U", "corner", "product", "gated")
LEVELS = (0.5, 1.0, 1.5, 2.5)
RULE_LEVELS = (0.5, 1.0, 1.5)
GRIDS = ("G1", "G2", "G3")
SLOWER_FIRST = ("G3", "G2", "G1")
SINGLES = tuple(f"v2 base {g}" for g in GRIDS) + ("version 1", "plain ridge")
MENUS = ("21", "42", "294")
ALPHA, LEVEL_BOUND = 0.05, 0.05
B_PAIRED, PAIRED_SEED = 10_000, 697999
THIN = 5
NATURAL = {"U": ({"P"}, "always"), "corner": ({"P"}, "always"), "product": ({"P"}, "always"),
           "gated": ({"P"}, "vol_high"), "leadlag": ({"X"}, "always"),
           "volcond": ({"P", "V"}, "always"), "regime": ({"P"}, None)}


def wilson(k, n):
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def line(label, k, n):
    if n == 0:
        return f"   {label:<34} n   0"
    lo, hi = wilson(k, n)
    return f"   {label:<34} {k:3d}/{n:<4d} = {k / n:.3f}  [{lo:.3f}, {hi:.3f}]" + ("  THIN" if n < THIN else "")


def tiered(rec: dict, g: str) -> bool:
    m = rec["menus"][g]
    return (rec["streams"][f"v2 base {g}"]["p"] < 0.02 or m["42"]["p"] < 0.02 or m["294"]["p"] < 0.01)


def paired(a, b, seed=PAIRED_SEED, B=B_PAIRED):
    d = np.asarray(a, float) - np.asarray(b, float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(B, len(d)))
    lo, hi = np.quantile(d[idx].mean(axis=1), [0.025, 0.975])
    return float(d.mean()), float(lo), float(hi)


def r1(recs, L) -> dict:
    L.append("R1. LEVEL on the 100 level-0 panels; fails iff the lower Wilson end exceeds 0.05")
    out = {}
    for cost in ("zero", "registered"):
        g0 = [r for r in recs if r["kind"] == "level0" and r["cost"] == cost]
        L.append(f"  {cost} cost (n {len(g0)})")
        items = [(s, lambda r, s=s: r["streams"][s]["p"] < ALPHA) for s in SINGLES]
        for g in GRIDS:
            items += [(f"menu {m} max {g}", lambda r, g=g, m=m: r["menus"][g][m]["p"] < ALPHA) for m in MENUS]
            items.append((f"tiered {g}", lambda r, g=g: tiered(r, g)))
        if cost == "registered":
            items.append(("class tier", lambda r: r["class"]["p"] < ALPHA))
        for name, f in items:
            k = sum(f(r) for r in g0)
            lo, _ = wilson(k, len(g0))
            fails = lo > LEVEL_BOUND
            out[(cost, name)] = {"k": k, "n": len(g0), "fails": fails}
            L.append(line(name, k, len(g0)) + ("  FAILS LEVEL" if fails else ""))
    return out


def r2(recs, L):
    L.append("R2. POWER of the single streams by shape x level (class tier beside)")
    planted = [r for r in recs if r["kind"] == "seed"]
    for sh in SHAPES:
        for lev in LEVELS:
            for sp in (None, "fast", "slow"):
                g = [r for r in planted if r["shape"] == sh and r["level"] == lev and (sp is None or r["speed"] == sp)]
                L.append(f"  {sh} level {lev} {sp or 'pooled'}")
                for s in SINGLES:
                    L.append(line(s, sum(r["streams"][s]["p"] < ALPHA for r in g), len(g)))
                L.append(line("class tier", sum(r["class"]["p"] < ALPHA for r in g), len(g)))


def matches(rec, view) -> bool:
    need, regime = NATURAL[rec["shape"]]
    regime = rec["rule"]["g"] if rec["shape"] == "regime" else regime
    return need <= set(view[0]) and view[3] == regime


def r3(recs, L):
    L.append("R3. THE MENU on the 280 panels (levels 1.0 and 1.5, first 20 seeds per shape)")
    menu = [r for r in recs if r["kind"] == "menu"]
    seeds = {(r["seed"], r["level"]): r for r in recs if r["kind"] == "seed"}
    for g in GRIDS:
        L.append(f"  grid {g}")
        for sh in SHAPES + ("pooled",):
            m = [r for r in menu if sh == "pooled" or r["shape"] == sh]
            if not m:
                continue
            n = len(m)
            base = sum(seeds[(r["seed"], r["level"])]["streams"][f"v2 base {g}"]["p"] < ALPHA
                       for r in m if (r["seed"], r["level"]) in seeds)
            parts = [f"(a) base {base}/{n}"]
            parts += [f"(b) {mm} {sum(r['menus'][g][mm]['p'] < ALPHA for r in m)}/{n}" for mm in MENUS]
            tier = sum(tiered({**r, "streams": seeds[(r["seed"], r["level"])]["streams"]}, g)
                       for r in m if (r["seed"], r["level"]) in seeds)
            parts.append(f"(c) tiered {tier}/{n}")
            match = sum(matches(r, r["menus"][g]["294"]["view"]) for r in m) if sh != "pooled" else \
                sum(matches(r, r["menus"][g]["294"]["view"]) for r in m)
            parts.append(f"294-winner matches natural view {match}/{n}")
            L.append(f"   {sh:<8} " + "; ".join(parts))


def q(x):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return "n 0" if x.size == 0 else f"n {x.size:4d} med {np.median(x):7.3f} [{x.min():7.3f}, {x.max():7.3f}]"


def r4(recs, L):
    L.append("R4. DESCRIPTIVE: planted against null")
    planted = [r for r in recs if r["kind"] == "seed"]
    null = [r for r in recs if r["kind"] == "level0" and r["cost"] == "registered"]
    for s in SINGLES:
        cap = [r["streams"][s]["pop"]["net"] / r["streams"][s]["plant_window"]["net"] for r in planted]
        L.append(f"  {s:<14} capture net {q(cap)}")
        for k in ("turnover_per_row", "turnover_per_unit_gross", "cost_per_year"):
            L.append(f"  {'':<14} {k:<24} planted {q([r['streams'][s][k] for r in planted])}; null {q([r['streams'][s][k] for r in null])}")
        drag = lambda rr: [r["streams"][s]["cost_per_year"] / r["streams"][s]["ann_vol"] for r in rr if r["streams"][s]["ann_vol"] > 0]
        L.append(f"  {'':<14} cost drag (Sharpe)        planted {q(drag(planted))}; null {q(drag(null))}")
    for g in GRIDS:
        s = f"v2 base {g}"
        L.append(f"  {s:<14} variant agreement (mean pairwise corr) planted {q([r['streams'][s]['variant_corr_mean'] for r in planted])}; "
                 f"null {q([r['streams'][s]['variant_corr_mean'] for r in null])}")
    e = lambda rr: sum(r["streams"]["v2 base edges"]["at_edge"] for r in rr) / max(1, sum(r["streams"]["v2 base edges"]["refits"] for r in rr))
    L.append(f"  v2 base refits with a penalty at a grid edge: planted {e(planted):.3f}; null {e(null):.3f}")


def rules(recs, lv, L) -> dict:
    L.append("RULES")
    rule = sorted((r for r in recs if r["kind"] == "seed" and r["level"] in RULE_LEVELS),
                  key=lambda r: (r["seed"], r["level"]))
    cert = {s: np.array([r["streams"][s]["p"] < ALPHA for r in rule]) for s in SINGLES}
    rates = {s: float(v.mean()) for s, v in cert.items()}
    for s in SINGLES:
        L.append(f"   pooled rate at 0.5-1.5 (n {len(rule)}): {s:<14} {rates[s]:.3f}")
    holds = [g for g in GRIDS if not lv[("zero", f"v2 base {g}")]["fails"]]
    out = {"n": len(rule), "rates": rates, "grids_holding_level": holds}
    if not holds:
        out.update(grid=None, decision="version 1 stays",
                   note="no grid's base view holds level; none carried forward")
        L.append("   grid: none holds level -> none carried forward; version 1 stays")
        return out
    best = max(rates[f"v2 base {g}"] for g in holds)
    grid = next(g for g in SLOWER_FIRST if g in holds and rates[f"v2 base {g}"] == best)
    out["grid"] = grid
    L.append(f"   grid carried forward: {grid} (highest pooled rate among {holds}; ties to the slower)")
    d, lo, hi = paired(cert[f"v2 base {grid}"], cert["version 1"])
    out["replacement"] = (d, lo, hi)
    replaces = lo > 0
    out["decision"] = "version 2 replaces version 1" if replaces else "version 1 stays"
    L.append(f"   replacement: v2 base {grid} - version 1 {d:+.3f} [{lo:+.3f}, {hi:+.3f}] -> {out['decision']}")
    orig = [i for i, r in enumerate(rule) if r["shape"] in ORIGINAL]
    fd, flo, fhi = paired(cert[f"v2 base {grid}"][orig], cert["version 1"][orig])
    out["fairness"] = (fd, flo, fhi)
    flag = flo < -0.05
    out["fairness_flag"] = flag
    L.append(f"   fairness (original four shapes, n {len(orig)}): {fd:+.3f} [{flo:+.3f}, {fhi:+.3f}]"
             + (" -> FLAG: version 2 wins only where the plant uses its new inputs; the decision returns to the author"
                if flag else " -> no flag"))
    return out


def read(recs) -> tuple[str, dict]:
    L = ["ML V2 PILOT READ (EXPLORATORY; no claim rests on it). Box numbers only.", "=" * 88]
    lv = r1(recs, L)
    L.append("")
    r2(recs, L)
    L.append("")
    r3(recs, L)
    L.append("")
    r4(recs, L)
    L.append("")
    out = rules(recs, lv, L)
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    prov = json.loads((d / "provenance.json").read_text())
    if prov.get("dry_run") or prov.get("platform") != "Linux x86_64":
        raise SystemExit("not a box run of the registered task list; not read")
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    recs = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    text, out = read(recs)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1, default=str))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
