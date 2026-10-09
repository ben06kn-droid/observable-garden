"""Summary of the refit records (`ml_v2_refit_records_2026_10_09`), for the author's
items 1 and 2 of 2026-10-09. Descriptive; exploratory; laptop-platform refits of
already-read pilot panels.

Item 1: for version 2's base view (by memory) and for version 1, on planted and null
panels separately:
- the share of refits at each grid value, per block (L, Q, I, S; "off" included);
- the stack weights' distribution;
- the share of refits where L is at its largest value (3);
- per block, the share of refits where a non-off penalty is at its smallest value.

Item 2, on the 50 product panels at level 1.5:
- the I block's chosen penalty under version 2 and version 1;
- capture by memory setting;
- how often the 3-fold choice (the version-2 cell with version 1's design: P, h 1,
  expanding) equals version 1's leave-one-year-out choice, per block, refit by refit;
- the same split by whether version 1 alone certified the panel in the pilot.

    python -m experiments.ml_v2_refit_summary_2026_10_09 --dir runs/ml_v2_refits/2026-10-09
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

BIG = 1e6
GRIDS = {"L": (0.3, 1.0, 3.0), "Q": (0.3, 1.0, 3.0, BIG), "I": (1.0, 3.0, 10.0, BIG), "S": (1.0, 3.0, 10.0, BIG)}
BLOCKS = ("L", "Q", "I", "S")


def lab(v) -> str:
    return "off" if float(v) >= BIG else f"{float(v):g}"


def as_dict(p) -> dict:
    return dict(zip(BLOCKS, p)) if isinstance(p, (list, tuple)) else p


def penalty_table(refits: list[dict], title: str) -> list[str]:
    L = [f"  {title}: {len(refits)} refits"]
    for b in BLOCKS:
        vals = [as_dict(r["penalties"]).get(b) for r in refits if b in as_dict(r["penalties"])]
        if not vals:
            continue
        c = Counter(lab(v) for v in vals)
        n = len(vals)
        L.append(f"     {b}: " + ", ".join(f"{k} {c.get(k, 0) / n:.3f}" for k in [lab(g) for g in GRIDS[b]]))
        low = GRIDS[b][0]
        L.append(f"        at its smallest non-off value ({lab(low)}): {sum(float(v) == low for v in vals) / n:.3f}")
    Ls = [as_dict(r["penalties"])["L"] for r in refits]
    L.append(f"     L at its largest value (3): {np.mean([float(v) == 3.0 for v in Ls]):.3f}")
    st = np.array([r["stack"] for r in refits], float)
    q = lambda x: f"med {np.median(x):.3f} [q10 {np.quantile(x, .1):.3f}, q90 {np.quantile(x, .9):.3f}]"
    L.append(f"     stack weight ridge {q(st[:, 0])}; trees {q(st[:, 1])}; trees at 0: {np.mean(st[:, 1] == 0):.3f}")
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--pilot", default="runs/ml_v2_pilot/2026-10-08/results.jsonl")
    a = ap.parse_args(argv)
    d = Path(a.dir)
    recs = [json.loads(x) for x in (d / "refits.jsonl").read_text().splitlines() if x.strip()]
    pilot = {(r["seed"], r["level"]): r for r in (json.loads(x) for x in open(a.pilot)) if r["kind"] == "seed"}
    L = ["Refit records on the pilot's panels (laptop refits; descriptive)", "=" * 88,
         "ITEM 1. Penalty choices and stack weights"]
    for grp in ("planted", "level0"):
        g = [r for r in recs if r["kind"] == grp]
        L.append(f" {grp} panels: {len(g)}")
        for mem in ("roll252", "roll756", "expand"):
            L += penalty_table([x for r in g for x in r["v2"][mem]], f"version 2 base view, memory {mem}")
        L += penalty_table([x for r in g for x in r["v1"]], "version 1")
    L.append("")
    L.append("ITEM 2. Product plants at level 1.5")
    prod = [r for r in recs if r["shape"] == "product"]
    L.append(f" panels: {len(prod)}")
    cert = lambda r, s: pilot[(r["seed"], 1.5)]["streams"][s]["p"] < 0.05
    v1_only = [r for r in prod if cert(r, "version 1") and not cert(r, "v2 base G3")]
    L.append(f" in the pilot: version 1 only {len(v1_only)}; both {sum(cert(r, 'version 1') and cert(r, 'v2 base G3') for r in prod)}; "
             f"version 2 only {sum(cert(r, 'v2 base G3') and not cert(r, 'version 1') for r in prod)}")
    for title, sub in (("all product panels", prod), ("version 1 only", v1_only)):
        L.append(f" {title} (n {len(sub)})")
        for mem in ("roll252", "roll756", "expand"):
            c = Counter(lab(as_dict(x["penalties"])["I"]) for r in sub for x in r["v2"][mem])
            n = sum(c.values())
            L.append(f"   I penalty, version 2 {mem:<8} " + ", ".join(f"{k} {c.get(k, 0) / max(n, 1):.3f}" for k in ("1", "3", "10", "off")))
        c = Counter(lab(as_dict(x["penalties"])["I"]) for r in sub for x in r["v1"])
        n = sum(c.values())
        L.append(f"   I penalty, version 1          " + ", ".join(f"{k} {c.get(k, 0) / max(n, 1):.3f}" for k in ("1", "3", "10", "off")))
        for mem in ("roll252", "roll756", "expand"):
            cn = [r["capture_by_memory"][mem]["net"] for r in sub]
            cg = [r["capture_by_memory"][mem]["gross"] for r in sub]
            L.append(f"   capture, memory {mem:<8} net med {np.median(cn):.3f}; gross med {np.median(cg):.3f}")
        agree = {b: [] for b in BLOCKS}
        for r in sub:
            for k, (a3, v1) in enumerate(zip(r["v2_p_h1"], r["v1"])):
                pa, pb = as_dict(a3["penalties"]), as_dict(v1["penalties"])
                for b in BLOCKS:
                    agree[b].append(float(pa[b]) == float(pb[b]))
        L.append("   3-fold (version 2, version 1's design) equal to version 1's leave-one-year-out choice, refit by refit: "
                 + ", ".join(f"{b} {np.mean(v):.3f}" for b, v in agree.items()))
    text = "\n".join(L)
    (d / "summary.txt").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
