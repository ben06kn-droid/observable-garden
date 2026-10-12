"""French holdout grading, the reader (`prereg/french-holdout-grading.md`, live at
4f11f952092831d77c4d8287f083bda12b425f22; checklist step 12). Tested on made-up grades only
before the grading runs. Reads `grades.json` once and prints, for each graded object
(n = 2, no pooled test): the realised holdout net Sharpe with its 95% interval; realised
minus the in-sample 90% lower bound, with the same interval shifted; where the realised
value falls on the in-sample confidence curve; and the registered branch sentence (section
6). It refuses unless the registration is an ancestor of HEAD.

    python -m experiments.read_french_holdout --dir runs/french_holdout/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LIVE = "4f11f952092831d77c4d8287f083bda12b425f22"
LABELS = {"ridge_stack": "the ridge_stack stream", "member_2937": "class member 2937 (+ma_spread_z, -ma_spread_rank)"}
ALWAYS = "Both graded objects were refused in-sample. This grading cannot test whether a pass holds."


def branch(name: str, o: dict) -> str:
    x, L = o["realized"], o["L90_insample"]
    if o["held"]:
        return f"{LABELS[name]}: the in-sample 90% lower bound held on the holdout (realised {x:+.3f} >= bound {L:+.3f})."
    return f"{LABELS[name]}: the in-sample 90% lower bound did not hold on the holdout (realised {x:+.3f} < bound {L:+.3f})."


def read(g: dict) -> str:
    L = [f"FRENCH HOLDOUT GRADING READ (registered at {g.get('registration')}); HEAD {g.get('git_head')}",
         "=" * 88,
         f"holdout {g['first_holdout_date']} .. {g['last_date']} ({g['n_periods']} graded periods); "
         f"stationary block bootstrap, block length {g['block_length']}, B {g['B']}, seed {g['seed']}"]
    for name in ("ridge_stack", "member_2937"):
        o = g["objects"][name]
        lo, hi = o["ci95"]
        dlo, dhi = o["ci95_minus_L90"]
        L.append(f"{LABELS[name]}")
        L.append(f"   realised holdout net Sharpe {o['realized']:+.3f}  95% [{lo:+.3f}, {hi:+.3f}]")
        L.append(f"   realised - in-sample L_0.90 ({o['L90_insample']:+.3f}): {o['realized_minus_L90']:+.3f}  "
                 f"95% [{dlo:+.3f}, {dhi:+.3f}]")
        L.append(f"   in-sample confidence curve at the realised value: C = {o['C_at_realized']:.3f}"
                 + ("  (outside the curve's grid; the end value)" if o["C_clipped"] else ""))
        L.append(f"   -> {branch(name, o)}")
    L.append(ALWAYS)
    return "\n".join(L)


def main(argv=None) -> int:
    import subprocess
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    if subprocess.run(["git", "merge-base", "--is-ancestor", LIVE, "HEAD"], capture_output=True).returncode != 0:
        raise SystemExit(f"REFUSED: the registration {LIVE} is not an ancestor of HEAD")
    d = Path(a.dir)
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    g = json.loads((d / "grades.json").read_text())
    text = read(g)
    (d / "read.txt").write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
