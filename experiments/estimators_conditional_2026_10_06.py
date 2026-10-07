"""The conditional tabulation of `prereg/estimators-exploratory-2026-10-06.md`, addendum
`8c933a3` and its append `0104920`. EXPLORATORY.

Reads only the per-panel rows the `--dump` of `experiments/estimators_2026_10_06.py`
writes. Certified: class tier, p_class < 0.05. Per submission and level: the number
certified, then among certified submissions only the bias, MAE, RMSE and SD (ddof 1)
of (estimate - target) against in-sample and holdout SR_pop.

    python -m experiments.estimators_conditional_2026_10_06 --rows <rows.jsonl> --out <txt>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

LEVELS = (0.0, 0.5, 1.0, 1.5)
SUBS = (("class argmax", ("E0", "EH", "EB")),
        ("extend-while-improving", ("E0", "EH", "EBs", "EB")))
ALPHA = 0.05


def stats(err) -> str:
    e = np.asarray(err, float)
    if e.size == 0:
        return "n    0"
    sd = f"{e.std(ddof=1):.3f}" if e.size >= 2 else "undef"
    return (f"n {e.size:4d}  bias {e.mean():+.3f}  MAE {np.abs(e).mean():.3f}  "
            f"RMSE {np.sqrt((e * e).mean()):.3f}  SD {sd}")


def tabulate(rows) -> str:
    L = ["Conditional on certification (class tier, alpha 0.05) — EXPLORATORY",
         "(prereg/estimators-exploratory-2026-10-06.md, addendum 8c933a3, append 0104920)",
         "=" * 96,
         "  error = estimate - target, among certified submissions only; SD is ddof 1"]
    for name, ests in SUBS:
        L += ["", name, "-" * 96]
        for lv in LEVELS:
            g = [r for r in rows if r["searcher"] == name and r["level"] == lv]
            c = [r for r in g if r["p_class"] < ALPHA]
            L.append(f"   level {lv:.1f}: certified {len(c)} of {len(g)}")
            for tgt, tname in (("in_sample", "in-sample SR_pop"), ("holdout", "holdout SR_pop")):
                for e in ests:
                    L.append(f"      vs {tname:<16} {e:<3}  "
                             + stats([r[e] - r[tgt] for r in c]))
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = [json.loads(ln) for ln in open(a.rows)]
    text = tabulate(rows)
    Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
