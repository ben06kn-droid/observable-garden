"""Reader for the version-2 confirmation (`prereg/ml-v2-confirmation.md`, live at
083c734724340b0d1ae7f6bfd98b0a61e23fe84c). Committed and tested on made-up rows only before
any result exists. Reads once, in order: level; claims H and R with their 97.5% intervals
and the joint outcome; then the secondaries.

    python -m experiments.read_ml_v2_confirm_2026_10_09 --dir runs/ml_v2_confirm/2026-10-09
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
STREAMS = ("v2 base", "version 1", "plain ridge")
ALPHA, LEVEL_BOUND, MARGIN = 0.05, 0.05, 0.03
B_PAIRED, PAIRED_SEED = 10_000, 699999
Q_LO, Q_HI = 0.0125, 0.9875                    # the 97.5% interval (Bonferroni over H and R)
N_PAIRED = 1120
BIG = 1e6
OUTCOMES = {
    (True, True): "H and R hold: version 2 is better under heavy costs and no worse beyond 0.03 at registered "
                  "costs. Version 2 replaces version 1.",
    (True, False): "H holds, R does not: better under heavy costs, possibly worse otherwise. Version 2 is not "
                   "adopted as the default; it is offered only for high-cost panels.",
    (False, True): "R holds, H does not: no worse, and no gain shown. Version 1 stays.",
    (False, False): "Neither H nor R holds. Version 1 stays.",
}


def wilson(k, n):
    from estimator.metrics import wilson_ci
    return wilson_ci(k, n)


def line(label, k, n):
    lo, hi = wilson(k, n) if n else (float("nan"), float("nan"))
    return f"   {label:<16} {k:4d}/{n:<4d} = {k / max(n, 1):.3f}  [{lo:.3f}, {hi:.3f}]"


def cert(rec, arm, s):
    return (rec["class"]["p"] if s == "class tier" else rec["arms"][arm][s]["p"]) < ALPHA


def paired(a, b, idx):
    d = np.asarray(a, float) - np.asarray(b, float)
    lo, hi = np.quantile(d[idx].mean(axis=1), [Q_LO, Q_HI])
    return float(d.mean()), float(lo), float(hi)


def level(recs, L) -> dict:
    L.append("LEVEL (400 level-0 panels): version 2 fails iff the lower Wilson end of its ZERO-cost rate exceeds 0.05")
    z = [r for r in recs if r["kind"] == "level0"]
    for arm in ("zero", "registered", "high"):
        L.append(f"  {arm} cost")
        for s in STREAMS:
            L.append(line(s, sum(cert(r, arm, s) for r in z), len(z)))
        if arm == "registered":
            L.append(line("class tier", sum(cert(r, arm, "class tier") for r in z), len(z)))
    k = sum(cert(r, "zero", "v2 base") for r in z)
    lo, hi = wilson(k, len(z))
    fails = lo > LEVEL_BOUND
    L.append("   version 2 " + ("FAILS level: claims H and R are VOID, and that is the result; version 1 stays"
                                if fails else f"holds level; largest excess not ruled out: rate up to {hi:.3f}"))
    return {"k": k, "n": len(z), "fails": fails}


def claims(recs, lv, L) -> dict:
    rule = sorted((r for r in recs if r["kind"] == "seed" and r["level"] in LEVELS), key=lambda r: (r["seed"], r["level"]))
    n = len(rule)
    idx = np.random.default_rng(PAIRED_SEED).integers(0, n, size=(B_PAIRED, n))
    c = {(arm, s): np.array([cert(r, arm, s) for r in rule]) for arm in ("registered", "high") for s in STREAMS}
    out = {"n": n, "rates": {f"{a} {s}": float(v.mean()) for (a, s), v in c.items()}}
    L.append(f"CLAIMS (n {n} paired; 97.5% paired bootstrap intervals, B {B_PAIRED}, seed {PAIRED_SEED})")
    for (a, s), v in c.items():
        L.append(f"   rate {a:<10} {s:<12} {v.mean():.3f}")
    if n != N_PAIRED:
        out["outcome"] = None
        L.append(f"   n = {n}, not the registered {N_PAIRED}: not read. STOP and ask.")
        return out
    h = paired(c[("high", "v2 base")], c[("high", "version 1")], idx)
    r = paired(c[("registered", "v2 base")], c[("registered", "version 1")], idx)
    H, R = h[1] > 0, r[1] > -MARGIN
    out.update(H=h, R=r, H_holds=H, R_holds=R)
    L.append(f"   H (high cost, superiority): v2 - v1 {h[0]:+.3f} [{h[1]:+.3f}, {h[2]:+.3f}] -> "
             f"{'holds' if H else 'not shown at high costs at n = 1,120'}")
    L.append(f"   R (registered, non-inferiority, margin {MARGIN}): v2 - v1 {r[0]:+.3f} [{r[1]:+.3f}, {r[2]:+.3f}] -> "
             f"{'holds' if R else 'non-inferiority at registered costs not shown at n = 1,120'}")
    if lv["fails"]:
        out["outcome"] = "VOID: version 2 failed level; version 1 stays"
        L.append("   JOINT OUTCOME: VOID (level failed); the intervals above are shown labelled void. Version 1 stays.")
    else:
        out["outcome"] = OUTCOMES[(H, R)]
        L.append(f"   JOINT OUTCOME: {OUTCOMES[(H, R)]}")
    out["_idx_rule"] = None
    return out, rule, c, idx


def q(x):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return "n 0" if x.size == 0 else f"n {x.size:4d} med {np.median(x):7.3f} [{x.min():7.3f}, {x.max():7.3f}]"


def secondary(rule, c, idx, recs, L) -> dict:
    out = {}
    L.append("SECONDARY (descriptive; no claim)")
    s = paired(c[("registered", "v2 base")], c[("registered", "version 1")], idx)
    out["registered superiority"] = s
    L.append(f"   superiority at registered cost: v2 - v1 {s[0]:+.3f} [{s[1]:+.3f}, {s[2]:+.3f}] "
             "(at the edge of detectability at this n; the pilot's +0.037 is likely optimistic)")
    orig = np.array([r["shape"] in ORIGINAL for r in rule])
    for arm in ("registered", "high"):
        a, b = c[(arm, "v2 base")][orig], c[(arm, "version 1")][orig]
        ii = np.random.default_rng(PAIRED_SEED).integers(0, len(a), size=(B_PAIRED, len(a)))
        d = paired(a, b, ii)
        out[f"original four, {arm}"] = d
        L.append(f"   original four shapes, {arm}: v2 - v1 {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}] (n {len(a)})")
    for arm in ("registered", "high"):
        L.append(f"   by shape, {arm} (v2 / v1 / plain ridge certified, of 160)")
        for sh in SHAPES:
            m = np.array([r["shape"] == sh for r in rule])
            L.append(f"      {sh:<8} " + " / ".join(str(int(c[(arm, st)][m].sum())) for st in STREAMS))
    cls = np.array([cert(r, "registered", "class tier") for r in rule])
    d = paired(c[("registered", "v2 base")], cls, idx)
    out["v2 vs class tier"] = d
    L.append(f"   v2 - class tier, registered: {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}]")
    for arm in ("registered", "high"):
        for st in STREAMS:
            cap = [r["arms"][arm][st]["pop"]["net"] / r["arms"][arm][st]["plant_window"]["net"] for r in rule]
            drag = [r["arms"][arm][st]["cost_per_year"] / r["arms"][arm][st]["ann_vol"] for r in rule
                    if r["arms"][arm][st]["ann_vol"] > 0]
            L.append(f"   {arm:<10} {st:<12} capture net {q(cap)}; cost drag {q(drag)}")
    for mem in ("roll756", "expand"):
        ref = [x for r in rule for x in r["refits_v2"][mem]]
        cnt = Counter("off" if float(x["penalties"]["L"]) >= BIG else f"{float(x['penalties']['L']):g}" for x in ref)
        L.append(f"   v2 L penalty, {mem}: " + " ".join(f"{k}:{v / max(len(ref), 1):.2f}" for k, v in sorted(cnt.items()))
                 + f"; capture net {q([r['capture_by_memory'][mem]['net'] for r in rule])}")
    return out


def read(recs):
    L = ["ML VERSION 2 CONFIRMATION READ (registered at 083c734). Box numbers only.", "=" * 88]
    lv = level(recs, L)
    L.append("")
    res = claims(recs, lv, L)
    if not isinstance(res, tuple):
        return "\n".join(L), {"level": lv, "claims": res}
    cl, rule, c, idx = res
    cl.pop("_idx_rule", None)
    L.append("")
    sec = secondary(rule, c, idx, recs, L)
    return "\n".join(L), {"level": lv, "claims": cl, "secondary": sec}


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
