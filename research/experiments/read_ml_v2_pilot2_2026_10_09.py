"""Reader for the second version-2 pilot (`prereg/ml-v2-exploratory-2026-10-08.md`, section
4688d5e). EXPLORATORY. Committed and tested on made-up rows before any result exists.
Reads once, in order: R1, R2, R3, then the rules per cost arm and their agreement.

    python -m experiments.read_ml_v2_pilot2_2026_10_09 --dir runs/ml_v2_pilot2/2026-10-09
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
ORIGINAL = ("U", "corner", "product", "gated")
LEVELS = (1.0, 1.5)
ARMS = ("registered", "high")
SETS = ("M1", "M2")
STREAMS = ("v2 base M1", "v2 base M2", "version 1", "plain ridge")
ALPHA, LEVEL_BOUND, THIN = 0.05, 0.05, 5
B_PAIRED, PAIRED_SEED = 10_000, 698999
BIG = 1e6


def wilson(k, n):
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def line(label, k, n):
    if n == 0:
        return f"   {label:<22} n   0"
    lo, hi = wilson(k, n)
    return f"   {label:<22} {k:3d}/{n:<4d} = {k / n:.3f}  [{lo:.3f}, {hi:.3f}]" + ("  THIN" if n < THIN else "")


def cert(rec, arm, s):
    return rec["arms"][arm][s]["p"] < ALPHA


def paired(a, b):
    d = np.asarray(a, float) - np.asarray(b, float)
    idx = np.random.default_rng(PAIRED_SEED).integers(0, len(d), size=(B_PAIRED, len(d)))
    lo, hi = np.quantile(d[idx].mean(axis=1), [0.025, 0.975])
    return float(d.mean()), float(lo), float(hi)


def q(x):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return "n 0" if x.size == 0 else f"n {x.size:4d} med {np.median(x):7.3f} [{x.min():7.3f}, {x.max():7.3f}]"


def r1(recs, L) -> dict:
    L.append("R1. LEVEL on the 100 level-0 panels; a stream fails iff the lower Wilson end of its ZERO-cost rate exceeds 0.05")
    z = [r for r in recs if r["kind"] == "level0"]
    out = {}
    L.append(f"  zero cost (n {len(z)})")
    for s in STREAMS:
        k = sum(cert(r, "zero", s) for r in z)
        lo, _ = wilson(k, len(z))
        out[s] = {"k": k, "n": len(z), "fails": lo > LEVEL_BOUND}
        L.append(line(s, k, len(z)) + ("  FAILS LEVEL" if out[s]["fails"] else ""))
    for arm in ARMS:
        L.append(f"  {arm} cost")
        for s in STREAMS:
            L.append(line(s, sum(cert(r, arm, s) for r in z), len(z)))
    return out


def r2(recs, L):
    L.append("R2. POWER by shape x level x cost arm")
    planted = [r for r in recs if r["kind"] == "seed"]
    for arm in ARMS:
        for sh in SHAPES:
            for lev in LEVELS:
                for sp in (None, "fast", "slow"):
                    g = [r for r in planted if r["shape"] == sh and r["level"] == lev and (sp is None or r["speed"] == sp)]
                    L.append(f"  {arm} | {sh} level {lev} {sp or 'pooled'}")
                    for s in STREAMS:
                        L.append(line(s, sum(cert(r, arm, s) for r in g), len(g)))


def r3(recs, L):
    L.append("R3. DESCRIPTIVE")
    planted = [r for r in recs if r["kind"] == "seed"]
    null = [r for r in recs if r["kind"] == "level0"]
    for arm in ARMS:
        for s in STREAMS:
            cap = [r["arms"][arm][s]["pop"]["net"] / r["arms"][arm][s]["plant_window"]["net"] for r in planted]
            drag = [r["arms"][arm][s]["cost_per_year"] / r["arms"][arm][s]["ann_vol"] for r in planted if r["arms"][arm][s]["ann_vol"] > 0]
            L.append(f"  {arm:<10} {s:<12} capture net {q(cap)}; cost drag {q(drag)}; "
                     f"turnover/gross {q([r['arms'][arm][s]['turnover_per_unit_gross'] for r in planted])}")
    v1d = [r["arms"]["high"]["version 1"]["cost_per_year"] / r["arms"]["high"]["version 1"]["ann_vol"] for r in null]
    L.append(f"  version 1's cost drag on level-0 panels, high-cost arm (target about 1.0): {q(v1d)}")
    for grp, rr in (("planted", planted), ("null", null)):
        for mem in ("roll252", "roll756", "expand"):
            ref = [x for r in rr for x in r["refits_v2"][mem]]
            parts = []
            for b in ("L", "Q", "I", "S"):
                c = Counter("off" if float(x["penalties"][b]) >= BIG else f"{float(x['penalties'][b]):g}" for x in ref if b in x["penalties"])
                n = sum(c.values())
                parts.append(f"{b} " + " ".join(f"{k}:{v / n:.2f}" for k, v in sorted(c.items())))
            L.append(f"  v2 penalties, {grp}, {mem} ({len(ref)} refits): " + "; ".join(parts))
    for mem in ("roll252", "roll756", "expand"):
        L.append(f"  capture by memory {mem}: net {q([r['capture_by_memory'][mem]['net'] for r in planted])}")


def rules(recs, lv, L) -> dict:
    L.append("RULES (per cost arm)")
    rule = sorted((r for r in recs if r["kind"] == "seed" and r["level"] in LEVELS), key=lambda r: (r["seed"], r["level"]))
    out = {"n": len(rule), "arms": {}}
    orig = [i for i, r in enumerate(rule) if r["shape"] in ORIGINAL]
    for arm in ARMS:
        c = {s: np.array([cert(r, arm, s) for r in rule]) for s in STREAMS}
        rates = {s: float(v.mean()) for s, v in c.items()}
        holds = [m for m in SETS if not lv[f"v2 base {m}"]["fails"]]
        rec = {"rates": rates, "sets_holding_level": holds}
        for s in STREAMS:
            L.append(f"   {arm:<10} pooled rate at 1.0-1.5 (n {len(rule)}): {s:<12} {rates[s]:.3f}")
        if not holds:
            rec.update(memory_set=None, decision="version 1 stays")
            L.append(f"   {arm:<10} memory set: none holds level -> version 1 stays")
            out["arms"][arm] = rec
            continue
        best = max(rates[f"v2 base {m}"] for m in holds)
        ms = next(m for m in SETS if m in holds and rates[f"v2 base {m}"] == best)       # ties to M1
        rec["memory_set"] = ms
        d, lo, hi = paired(c[f"v2 base {ms}"], c["version 1"])
        rec["replacement"] = (d, lo, hi)
        rec["decision"] = "version 2 replaces version 1" if lo > 0 else "version 1 stays"
        fd, flo, fhi = paired(c[f"v2 base {ms}"][orig], c["version 1"][orig])
        rec["fairness"] = (fd, flo, fhi)
        rec["fairness_flag"] = flo < -0.05
        L.append(f"   {arm:<10} memory set carried: {ms} (higher pooled rate among {holds}; ties to M1)")
        L.append(f"   {arm:<10} replacement: v2 base {ms} - version 1 {d:+.3f} [{lo:+.3f}, {hi:+.3f}] -> {rec['decision']}")
        L.append(f"   {arm:<10} fairness (original four shapes, n {len(orig)}): {fd:+.3f} [{flo:+.3f}, {fhi:+.3f}]"
                 + (" -> FLAG: version 2 wins only where the plant uses its new inputs; the decision returns to the author"
                    if rec["fairness_flag"] else " -> no flag"))
        out["arms"][arm] = rec
    a, b = out["arms"]["registered"], out["arms"]["high"]
    agree = a.get("memory_set") == b.get("memory_set") and a["decision"] == b["decision"]
    out["arms_agree"] = agree
    L.append("   the two cost arms " + ("agree" if agree else
             "DISAGREE on the memory set or on replacement -> the decision returns to the author"))
    return out


def read(recs):
    L = ["ML V2 SECOND PILOT READ (EXPLORATORY; no claim rests on it). Box numbers only.", "=" * 88]
    lv = r1(recs, L)
    L.append("")
    r2(recs, L)
    L.append("")
    r3(recs, L)
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
