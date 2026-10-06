"""Diagnostics 2026-10-06, A3's family-level recovery, CORRECTED after the run.

The run (`7ebaf25`, output `4d0c7e1`) paired a submission with fewer than three
features only with m*'s first features, so it undercounted family-level recovery.
This recomputes that one table with the corrected matching
(`diagnostics_2026_10_06.family_matching`), on the same stored supports and the same
panel-independent single-feature correlations. No other table is touched.

    python -m experiments.diagnostics_2026_10_06_a3fix --out runs/diagnostics/2026-10-06_a3_corrected.txt
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np

from experiments import diagnostics_2026_10_06 as dg


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    K = 40
    singles = [((k, 1.0),) for k in range(K)]
    Cm = np.empty((K, K))
    for i in range(K):
        Cm[i] = [dg.pair_corr(singles[i], singles[j]) if j >= i else Cm[j, i] for j in range(K)]

    def families(tau):
        lab = list(range(K))

        def find(i):
            while lab[i] != i:
                lab[i] = lab[lab[i]]
                i = lab[i]
            return i
        for i in range(K):
            for j in range(i + 1, K):
                if abs(Cm[i, j]) >= tau:
                    lab[find(i)] = find(j)
        return [find(i) for i in range(K)]
    fams = {t: families(t) for t in dg.TAUS}

    def hit(sub, mstar, tau):
        fam = fams[tau]

        def match(a_, b_):
            (k, s), (j, t) = a_, b_
            return fam[k] == fam[j] and s * t * np.sign(Cm[k, j]) > 0
        return dg.family_matching(list(dg.canon(sub)), list(dg.canon(mstar)), match) >= 2

    rows = []
    for ln in open(dg.STAGE1):
        r = json.loads(ln)
        if r["seed"] not in dg.STAGE1_SEEDS:
            continue
        for rec in r["levels"]:
            ewi = next(x for x in rec["searchers"] if x["searcher"] == dg.EWI)
            rows.append((dg.S1_SRC_NAMES[0], float(rec["beta"]), ewi["support"],
                         rec["planted"], ewi["two_of_three"]))
            rows.append((dg.S1_SRC_NAMES[1], float(rec["beta"]), rec["class_argmax"],
                         rec["planted"], rec["class_argmax_recovery"]["two_of_three"]))
    for f in sorted(glob.glob(str(dg.AGENTS / "*.json"))):
        d = json.load(open(f))
        pt = d["planted_truth"]
        if d.get("submitted") and pt.get("submitted_support_true"):
            rows.append((d["arm"], float(pt["level"]), pt["submitted_support_true"],
                         pt["planted"], pt["submitted_recovery"]["two_of_three"]))
    L = ["A3 — FAMILY-LEVEL RECOVERY, CORRECTED AFTER THE RUN (exploratory)",
         "-" * 96,
         "   The run's A3 recovery table (4d0c7e1) undercounted submissions with fewer than three",
         "   features. Same supports, same families, corrected matching. Every other table stands.",
         "   check: family-level >= registered on every row (an exact match is a family match)"]
    bad = 0
    for src in dg.S1_SRC_NAMES + dg.ARMS:
        lvls = dg.S1_LEVELS if src in dg.S1_SRC_NAMES else dg.AGENT_LEVELS
        for lv in lvls:
            g = [x for x in rows if x[0] == src and x[1] == lv and x[2]]
            if not g:
                continue
            reg = [bool(x[4]) for x in g]
            parts = []
            for t in dg.TAUS:
                h = [hit(x[2], x[3], t) for x in g]
                bad += sum(1 for r_, h_ in zip(reg, h) if r_ and not h_)
                parts.append(f"tau {t:.1f} {dg.share(h)}")
            L.append(f"   {src:<28} {dg.lvl(lv)}  registered {dg.share(reg)}   " + "  ".join(parts))
    L.append(f"   rows registered-hit but family-miss: {bad} (must be 0)")
    assert bad == 0
    text = "\n".join(L)
    Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
