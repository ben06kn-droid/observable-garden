"""Reader for the ML pilot (`prereg/ml-pipeline-exploratory-2026-10-07.md`, "The pilot",
2388f50). EXPLORATORY. Committed and tested on synthetic rows (tests/test_read_ml_pilot.py)
before any pilot result exists. Reads once, in the registered order: R1 level, R2 power,
R3 capture, R4 descriptive, then the carry-forward rule.

    python -m experiments.read_ml_pilot_2026_10_07 --dir runs/ml_pilot/2026-10-07 \
        [--design runs/ml_design/2026-10-07/draws.jsonl]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

PREDICTORS = ("control", "ridge_stack", "mv_combine risk on", "mv_combine risk off")
NONLINEAR = ("mv_combine", "ridge_stack")          # tie order: mv_combine before ridge_stack
RULES = ("U", "corner", "product", "gated")
LEVELS = (1.0, 1.5, 2.5)
ALPHA = 0.05
LEVEL_BOUND = 0.05
PRIMARY_LEVEL = 1.5
B_CARRY = 10_000
CARRY_SEED = 687999
THIN = 5


def wilson(k: int, n: int) -> tuple[float, float]:
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def certified(rec: dict, name: str) -> bool:
    return (rec["class"]["p"] if name == "class tier" else rec["predictors"][name]["p"]) < ALPHA


def rate_line(label: str, recs: list, name: str) -> str:
    n = len(recs)
    if n == 0:
        return f"   {label:<34} n   0"
    k = sum(certified(r, name) for r in recs)
    lo, hi = wilson(k, n)
    thin = "  THIN" if n < THIN else ""
    return f"   {label:<34} {k:3d}/{n:<3d} = {k / n:.3f}  [{lo:.3f}, {hi:.3f}]{thin}"


def q(x) -> str:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    if x.size == 0:
        return "n 0"
    return f"n {x.size:3d}  med {np.median(x):7.3f}  [{x.min():7.3f}, {x.max():7.3f}]"


# -- R1 ---------------------------------------------------------------------------------

def level_verdicts(recs: list) -> dict:
    """{predictor: {"k", "n", "lo", "hi", "fails"}} on the zero-cost level-0 panels."""
    zero = [r for r in recs if r["kind"] == "level0" and r["cost"] == "zero"]
    out = {}
    for name in PREDICTORS:
        k = sum(certified(r, name) for r in zero)
        lo, hi = wilson(k, len(zero))
        out[name] = {"k": k, "n": len(zero), "lo": lo, "hi": hi, "fails": lo > LEVEL_BOUND}
    return out


def r1(recs: list, L: list) -> dict:
    v = level_verdicts(recs)
    L.append("R1. LEVEL: certification rate on level-0 panels (p < 0.05), Wilson 95%")
    L.append("    a predictor FAILS level iff the lower Wilson end of its ZERO-cost rate exceeds 0.05")
    for cost in ("zero", "registered"):
        g = [r for r in recs if r["kind"] == "level0" and r["cost"] == cost]
        L.append(f"  {cost} cost")
        for name in PREDICTORS:
            L.append(rate_line(name, g, name))
        if cost == "registered":
            L.append(rate_line("class tier (beside; not a predictor)", g, "class tier"))
    for name in PREDICTORS:
        x = v[name]
        L.append(f"   {name:<20} " + ("FAILS level: not carried forward" if x["fails"] else
                 f"holds level; largest excess not ruled out: rate up to {x['hi']:.3f}"))
    return v


# -- R2 ---------------------------------------------------------------------------------

def cells(recs: list):
    planted = [r for r in recs if r["kind"] == "planted"]
    for shape in RULES:
        for lev in LEVELS:
            for sp in ("pooled", "fast", "slow"):
                g = [r for r in planted if r["shape"] == shape and r["level"] == lev
                     and (sp == "pooled" or r["speed"] == sp)]
                yield shape, lev, sp, g


def r2(recs: list, L: list) -> None:
    L.append("R2. POWER: certification rate per rule x level x predictor, class tier beside")
    for shape, lev, sp, g in cells(recs):
        L.append(f"  {shape} level {lev} {sp}")
        for name in PREDICTORS + ("class tier",):
            L.append(rate_line(name, g, name))


# -- R3 ---------------------------------------------------------------------------------

def ceiling(rec: dict, name: str) -> float | None:
    """5c's formula on this panel: mean over refits of 1/sqrt(1 + eff/(T_years SR^2)), with
    eff mv_combine's effective parameters at its chosen c and SR the planted level."""
    ds = rec["predictors"][name]["diagnostics"]
    v = [1 / np.sqrt(1 + d["effective"]["total"] / (d["T_years"] * rec["level"] ** 2)) for d in ds]
    return float(np.mean(v)) if v else None


def capture(rec: dict, name: str, kind: str) -> float:
    p = rec["predictors"][name]
    return p["pop"][kind] / p["plant_window"][kind]


def design_shadow(path) -> list:
    if not path or not Path(path).exists():
        return []
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def r3(recs: list, L: list, design: list) -> None:
    L.append("R3. CAPTURE: predictor population Sharpe over its scored window / the plant's over the "
             "same window (net and gross); medians [min, max]")
    for shape, lev, sp, g in cells(recs):
        L.append(f"  {shape} level {lev} {sp}")
        for name in PREDICTORS:
            L.append(f"   {name:<20} net   {q([capture(r, name, 'net') for r in g])}")
            L.append(f"   {'':<20} gross {q([capture(r, name, 'gross') for r in g])}")
        L.append(f"   {'linear shadow (5a), these panels':<34} {q([r['shadow_share'] for r in g])}")
        dg = [d for d in design if d["shape"] == shape and (sp == "pooled" or d["speed"] == sp)]
        if design:
            L.append(f"   {'linear shadow (5a), design block':<34} "
                     f"{q([d['shadow_share'][str(lev)] for d in dg])}")
        for name in ("mv_combine risk on", "mv_combine risk off"):
            L.append(f"   {'ceiling (5c), ' + name.split(' ', 1)[1]:<34} "
                     f"{q([ceiling(r, name) for r in g])}")


# -- R4 ---------------------------------------------------------------------------------

def r4(recs: list, L: list) -> None:
    L.append("R4. DESCRIPTIVE (all at-cost panels: planted at every level and level 0)")
    at_cost = [r for r in recs if r["cost"] == "registered"]
    for name in ("mv_combine risk on", "mv_combine risk off"):
        ds = [d for r in at_cost for d in r["predictors"][name]["diagnostics"]]
        cs = [d["c"] for d in ds]
        L.append(f"  {name}: chosen c over {len(ds)} refits: " + ", ".join(
            f"{c} {cs.count(c)}" for c in sorted(set(cs))))
        L.append(f"   effective parameters total {q([d['effective']['total'] for d in ds])}")
        for b in [k for k in (ds[0]["effective"] if ds else {}) if k != "total"]:
            L.append(f"   effective parameters {b:<5} {q([d['effective'][b] for d in ds])}")
        for b in (ds[0]["abs_weight_by_block"] if ds else {}):
            L.append(f"   |block weight| sum {b:<7} {q([d['abs_weight_by_block'][b] for d in ds])}")
    ds = [d for r in at_cost for d in r["predictors"]["ridge_stack"]["diagnostics"]]
    if ds:
        pens = ds[0]["penalties"]
        keys = list(pens) if isinstance(pens, dict) else range(len(pens))
        for k in keys:
            vals = [str(d["penalties"][k]) for d in ds]
            L.append(f"  ridge_stack penalty {k}: " + ", ".join(
                f"{v} {vals.count(v)}" for v in sorted(set(vals))))
        L.append(f"  ridge_stack stack weight (ridge) {q([d['stack_weights'][0] for d in ds])}")
        L.append(f"  ridge_stack stack weight (trees) {q([d['stack_weights'][1] for d in ds])}")
    for name in PREDICTORS:
        L.append(f"  {name:<20} share of scored days the gross cap binds "
                 f"{q([r['predictors'][name]['cap_binding_share'] for r in at_cost])}")
        L.append(f"  {name:<20} turnover {q([r['predictors'][name]['turnover'] for r in at_cost])}")


# -- carry-forward ------------------------------------------------------------------------

def paired_interval(a: np.ndarray, b: np.ndarray, idx: np.ndarray) -> tuple[float, float, float]:
    """Rate difference a - b and its 95% percentile interval over panel resamples idx."""
    d = a.astype(float) - b.astype(float)
    boot = d[idx].mean(axis=1)
    lo, hi = np.quantile(boot, [0.025, 0.975])
    return float(d.mean()), float(lo), float(hi)


def carry_forward(recs: list, level: dict) -> dict:
    """The registered rule. Returns the decision and every interval it used."""
    g = sorted((r for r in recs if r["kind"] == "planted" and r["level"] == PRIMARY_LEVEL),
               key=lambda r: r["seed"])
    n = len(g)
    cert = {name: np.array([certified(r, name) for r in g]) for name in PREDICTORS}
    idx = np.random.default_rng(CARRY_SEED).integers(0, n, size=(B_CARRY, n))
    out = {"n": n, "rates": {k: float(v.mean()) for k, v in cert.items()}, "comparisons": {}}
    if level["control"]["fails"]:
        out["decision"] = None
        out["note"] = ("the control fails level; the registered rule does not say what is "
                       "carried forward then. STOP and ask.")
        return out
    on, off = "mv_combine risk on", "mv_combine risk off"
    holds = [s for s in (on, off) if not level[s]["fails"]]
    if len(holds) == 2:
        dlt, lo, hi = paired_interval(cert[off], cert[on], idx)
        out["comparisons"]["risk off - risk on"] = (dlt, lo, hi)
        mv = off if lo > 0 else on               # includes zero, or favours on: risk sizing on
    else:
        mv = holds[0] if holds else None
    out["mv_setting"] = mv
    cands = [c for c in ([mv] if mv else []) + ["ridge_stack"]
             if not level[c]["fails"]]
    qual = []
    for c in cands:
        dlt, lo, hi = paired_interval(cert[c], cert["control"], idx)
        out["comparisons"][f"{c} - control"] = (dlt, lo, hi)
        if lo > 0:
            qual.append(c)
    if not qual:
        out["decision"] = "control"
        out["note"] = ("no non-linear predictor qualified: the non-linear layers added nothing "
                       f"detectable at n = {n}")
        return out
    order = {name: i for i, name in enumerate(cands)}          # mv_combine first
    best = max(qual, key=lambda c: (out["rates"][c], -order[c]))
    out["decision"] = best
    out["note"] = (f"qualified: {', '.join(qual)}; highest rate carried forward"
                   + ("; tie broken mv_combine before ridge_stack"
                      if len({out['rates'][c] for c in qual}) < len(qual) else ""))
    return out


def render_carry(cf: dict, L: list) -> None:
    L.append(f"CARRY-FORWARD (level {PRIMARY_LEVEL}, pooled over rules, n = {cf['n']} paired; "
             f"bootstrap B = {B_CARRY}, seed {CARRY_SEED})")
    for k, v in cf["rates"].items():
        L.append(f"   rate {k:<20} {v:.3f}")
    for k, (dlt, lo, hi) in cf["comparisons"].items():
        L.append(f"   {k:<34} {dlt:+.3f}  [{lo:+.3f}, {hi:+.3f}]")
    if "mv_setting" in cf:
        L.append(f"   mv_combine setting: {cf['mv_setting']}")
    L.append(f"   carried forward: {cf['decision']}  ({cf['note']})")


def read(recs: list, design: list) -> tuple[str, dict]:
    L = ["ML PILOT READ (EXPLORATORY; no claim rests on it). Box numbers only.", "=" * 88]
    lv = r1(recs, L)
    L.append("")
    r2(recs, L)
    L.append("")
    r3(recs, L, design)
    L.append("")
    r4(recs, L)
    L.append("")
    cf = carry_forward(recs, lv)
    render_carry(cf, L)
    return "\n".join(L), cf


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--design", default="runs/ml_design/2026-10-07/draws.jsonl")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    prov = json.loads((d / "provenance.json").read_text())
    if prov["platform"] != "Linux x86_64":
        raise SystemExit("not a box run; the pilot is read from box numbers only")
    recs = [json.loads(x) for x in (d / "pilot.jsonl").read_text().splitlines() if x.strip()]
    text, cf = read(recs, design_shadow(a.design))
    (d / "read.txt").write_text(text + "\n")
    (d / "carry_forward.json").write_text(json.dumps(cf, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
