"""Reader for the ridge_stack confirmation (`prereg/ml-ridge-stack-confirmation.md`,
registered at 77f3ee19469f500d5c3959c9612a04d250856b02). Committed and tested on made-up
rows only (tests/test_read_ml_confirm_ridge_stack.py) before any result exists. Reads once,
in the registered order: level (section 4), primary (section 5), secondary (section 6).

    python -m experiments.read_ml_confirm_ridge_stack --dir runs/ml_confirm/ridge_stack \
        [--design runs/ml_design/2026-10-07/draws.jsonl]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

RULES = ("U", "corner", "product", "gated")
LEVELS = (1.0, 1.5, 2.5)
PRIMARY_LEVEL = 1.5
N_PRIMARY = 400
ALPHA = 0.05
LEVEL_BOUND = 0.05
B_PAIRED = 10_000
PAIRED_SEED = 689999
THIN = 5
RIDGE, CONTROL, CLASS = "ridge_stack", "control", "class tier"
BLOCK_NAMES = ("L", "Q", "I", "S")
OFF = 1e6                                        # learn.ridge_stack.BIG


def wilson(k: int, n: int) -> tuple[float, float]:
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def cert(rec: dict, name: str) -> bool:
    return (rec["class"]["p"] if name == CLASS else rec["predictors"][name]["p"]) < ALPHA


def rate_line(label: str, k: int, n: int) -> str:
    if n == 0:
        return f"   {label:<38} n   0"
    lo, hi = wilson(k, n)
    thin = "  THIN" if n < THIN else ""
    return f"   {label:<38} {k:3d}/{n:<3d} = {k / n:.3f}  [{lo:.3f}, {hi:.3f}]{thin}"


def rate(label: str, recs: list, name: str) -> str:
    return rate_line(label, sum(cert(r, name) for r in recs), len(recs))


def q(x) -> str:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    if x.size == 0:
        return "n 0"
    return f"n {x.size:3d}  med {np.median(x):7.3f}  [{x.min():7.3f}, {x.max():7.3f}]"


def paired(a: np.ndarray, b: np.ndarray, seed: int = PAIRED_SEED, B: int = B_PAIRED):
    """Mean of a - b and the 2.5th/97.5th percentiles of its paired panel bootstrap."""
    d = a.astype(float) - b.astype(float)
    idx = np.random.default_rng(seed).integers(0, len(d), size=(B, len(d)))
    lo, hi = np.quantile(d[idx].mean(axis=1), [0.025, 0.975])
    return float(d.mean()), float(lo), float(hi)


def level0(recs, cost):
    return [r for r in recs if r["kind"] == "level0" and r["cost"] == cost]


def planted(recs, level, shape=None, speed=None):
    return sorted((r for r in recs if r["kind"] == "planted" and r["level"] == level
                   and (shape is None or r["shape"] == shape)
                   and (speed is None or r["speed"] == speed)), key=lambda r: r["seed"])


# -- section 4 ---------------------------------------------------------------------------

def level_verdict(recs: list) -> dict:
    z = level0(recs, "zero")
    k = sum(cert(r, RIDGE) for r in z)
    lo, hi = wilson(k, len(z))
    return {"k": k, "n": len(z), "lo": lo, "hi": hi, "fails": lo > LEVEL_BOUND}


def read_level(recs: list, L: list) -> dict:
    v = level_verdict(recs)
    L.append("4. LEVEL: certification rate on level-0 panels (p < 0.05), Wilson 95%")
    L.append("   ridge_stack FAILS level iff the lower Wilson end of its ZERO-cost rate exceeds 0.05")
    for cost in ("zero", "registered"):
        g = level0(recs, cost)
        L.append(f"  {cost} cost")
        L.append(rate(RIDGE, g, RIDGE))
        L.append(rate("control (beside)", g, CONTROL))
        if cost == "registered":
            L.append(rate("class tier (beside)", g, CLASS))
    L.append("   ridge_stack " + ("FAILS level: the primary is VOID" if v["fails"] else
             f"holds level; largest excess not ruled out: rate up to {v['hi']:.3f}"))
    return v


# -- section 5 ---------------------------------------------------------------------------

def primary(recs: list, level: dict) -> dict:
    g = planted(recs, PRIMARY_LEVEL)
    a = np.array([cert(r, RIDGE) for r in g])
    b = np.array([cert(r, CLASS) for r in g])
    d, lo, hi = paired(a, b)
    out = {"n": len(g), "rate_ridge_stack": float(a.mean()), "rate_class_tier": float(b.mean()),
           "difference": d, "lo": lo, "hi": hi}
    if len(g) != N_PRIMARY:
        out["verdict"] = "INCOMPLETE"
        out["text"] = f"n = {len(g)}, not the registered {N_PRIMARY}: not read. STOP and ask."
    elif level["fails"]:
        out["verdict"] = "VOID"
        out["text"] = "ridge_stack failed level: the primary is void, and that is the result."
    elif lo > 0:
        out["verdict"] = "HOLDS"
        out["text"] = ("On these four planted rule shapes at net level 1.5, ridge_stack, named in "
                       "advance and priced as one declared strategy, certifies more panels than "
                       "the class tier.")
    else:
        out["verdict"] = "FAILED"
        out["text"] = f"The confirmation failed at n = {N_PRIMARY}."
    return out


def read_primary(recs: list, level: dict, L: list) -> dict:
    p = primary(recs, level)
    L.append(f"5. PRIMARY: ridge_stack minus class tier, certification rate at level {PRIMARY_LEVEL}, "
             f"pooled over rules, n = {p['n']} paired; bootstrap B = {B_PAIRED}, seed {PAIRED_SEED}")
    L.append(f"   rate ridge_stack {p['rate_ridge_stack']:.3f}; rate class tier {p['rate_class_tier']:.3f}")
    L.append(f"   difference {p['difference']:+.3f}  95% [{p['lo']:+.3f}, {p['hi']:+.3f}]"
             + ("  (VOID)" if p["verdict"] == "VOID" else ""))
    L.append(f"   decision: the claim holds iff the lower end exceeds 0 -> {p['verdict']}")
    L.append(f"   {p['text']}")
    return p


# -- section 6 ---------------------------------------------------------------------------

def penalty_label(v) -> str:
    return "off" if float(v) >= OFF else f"{float(v):g}"


def read_secondary(recs: list, L: list, design: list) -> dict:
    out = {}
    L.append("6. SECONDARY (descriptive; no claim)")
    L.append(f"  per-rule difference at level {PRIMARY_LEVEL} (paired bootstrap B {B_PAIRED}, seed {PAIRED_SEED})")
    for other in (CLASS, CONTROL):
        for shape in (None,) + RULES:
            g = planted(recs, PRIMARY_LEVEL, shape)
            if not g:
                continue
            d, lo, hi = paired(np.array([cert(r, RIDGE) for r in g]),
                               np.array([cert(r, other) for r in g]))
            out[f"ridge_stack - {other}, {shape or 'pooled'}"] = (d, lo, hi)
            L.append(f"   ridge_stack - {other:<11} {shape or 'pooled':<8} n {len(g):3d}  "
                     f"{d:+.3f}  [{lo:+.3f}, {hi:+.3f}]")
    L.append("  certification rates by rule x level, pooled / fast / slow")
    for shape in RULES:
        for lev in LEVELS:
            for sp in (None, "fast", "slow"):
                g = planted(recs, lev, shape, sp)
                L.append(f"  {shape} level {lev} {sp or 'pooled'}")
                for name in (RIDGE, CONTROL, CLASS):
                    L.append(rate(name, g, name))
    L.append("  capture: population Sharpe over the scored window / the plant's over the same "
             "window; medians [min, max]")
    for shape in RULES:
        for lev in LEVELS:
            for sp in (None, "fast", "slow"):
                g = planted(recs, lev, shape, sp)
                L.append(f"  {shape} level {lev} {sp or 'pooled'}" + ("  THIN" if 0 < len(g) < THIN else ""))
                for name in (RIDGE, CONTROL):
                    for kind in ("net", "gross"):
                        L.append(f"   {name:<12} {kind:<5} " + q(
                            [r["predictors"][name]["pop"][kind] / r["predictors"][name]["plant_window"][kind]
                             for r in g]))
                L.append(f"   {'linear shadow, these panels':<30} {q([r['shadow_share'] for r in g])}")
                dg = [d for d in design if d["shape"] == shape and (sp is None or d["speed"] == sp)]
                if design:
                    L.append(f"   {'linear shadow (5a), design block':<30} "
                             f"{q([d['shadow_share'][str(lev)] for d in dg])}")
    g = level0(recs, "registered")
    either = sum(cert(r, RIDGE) or cert(r, CLASS) for r in g)
    out["either_tier_level0"] = {"k": either, "n": len(g)}
    L.append("  level 0 at cost: EITHER tier certifies (class tier OR ridge_stack); no rule attaches")
    L.append(rate_line("either tier", either, len(g)))
    L.append(rate("ridge_stack alone", g, RIDGE))
    L.append(rate("class tier alone", g, CLASS))
    at_cost = [r for r in recs if r["cost"] == "registered"]
    ds = [d for r in at_cost for d in r["predictors"][RIDGE]["diagnostics"]]
    L.append(f"  ridge_stack diagnostics over {len(ds)} refits (all at-cost panels)")
    for j, b in enumerate(BLOCK_NAMES):
        vals = [penalty_label(d["penalties"][j]) for d in ds]
        L.append(f"   penalty {b}: " + ", ".join(f"{v} {vals.count(v)}" for v in
                                                  sorted(set(vals), key=lambda s: (s == 'off', s))))
    L.append(f"   stack weight (ridge) {q([d['stack_weights'][0] for d in ds])}")
    L.append(f"   stack weight (trees) {q([d['stack_weights'][1] for d in ds])}")
    for name in (RIDGE, CONTROL):
        L.append(f"   {name:<12} turnover {q([r['predictors'][name]['turnover'] for r in at_cost])}")
        L.append(f"   {name:<12} share of scored days the gross cap binds "
                 f"{q([r['predictors'][name]['cap_binding_share'] for r in at_cost])}")
    return out


def read(recs: list, design: list) -> tuple[str, dict]:
    L = ["RIDGE_STACK CONFIRMATION READ (registered at 77f3ee19469f500d5c3959c9612a04d250856b02). "
         "Box numbers only.", "=" * 88]
    lv = read_level(recs, L)
    L.append("")
    pr = read_primary(recs, lv, L)
    L.append("")
    sec = read_secondary(recs, L, design)
    return "\n".join(L), {"level": lv, "primary": pr, "secondary": sec}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--design", default="runs/ml_design/2026-10-07/draws.jsonl")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    prov = json.loads((d / "provenance.json").read_text())
    if prov["platform"] != "Linux x86_64" or prov.get("dry_run"):
        raise SystemExit("not a box run of the registered task list; not read")
    if (d / "read.txt").exists():
        raise SystemExit("already read; reads happen once")
    recs = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    design = []
    if a.design and Path(a.design).exists():
        design = [json.loads(x) for x in Path(a.design).read_text().splitlines() if x.strip()]
    text, res = read(recs, design)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(res, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
