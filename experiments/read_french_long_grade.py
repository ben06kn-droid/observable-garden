"""Reader for the French long history's B1 holdout grading (`prereg/french-long-b1-grading.md`,
live at 00417de103785335f2b3a4b6860b7e81a1b33135). Tested on made-up grades only before the
grading runs. Reads `grades.json` once and prints, for each graded object in the registered
order, the branch sentence of section 7, the realised UNWEIGHTED holdout net Sharpe with its
90% interval, the in-sample weighted L90 (the bound) and held or not; then the descriptive
lines, each so labelled. Always: the validation's limits and the 6-year window's line. It
refuses unless the registration is an ancestor of HEAD.

    python -m experiments.read_french_long_grade --dir runs/french_long_b1_grade/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LIVE = "00417de103785335f2b3a4b6860b7e81a1b33135"
WINDOW = "1990-01-01 to 1995-12-31"
ORDER = ("stream_d1", "stream_d0", "class_member")
LIMITS = ("W2's size is checked by simulation on four null shapes, not proved; overshoots of about 10% "
          "are not reliably detected; the class checks are weak (amendment 8a23368's tables).")
SIX_YEARS = ("a 6-year window: the standard error is about 0.41; values within about 0.4 of the bound "
             "are not distinguished from it.")


def label(name: str, o: dict) -> str:
    if name == "stream_d1":
        return "(1) the Sancho stream, d = 1"
    if name == "stream_d0":
        return "(2) the Sancho stream, d = 0, NOT IMPLEMENTABLE"
    return f"(3) the class's best member under the weights, d = 1 ({', '.join(o['member']['features'])})"


def branch(name: str, o: dict) -> str:
    """Section 7's sentence. Certified objects name the highest level they were certified at."""
    x, L, obj = o["realized"], o["L90_weighted"], label(name, o)
    cert = o["certified"]
    if cert.get("96%") or cert.get("90%"):
        lvl = "96% level" if cert.get("96%") else "90% level"
        head = f"{obj}: certified in-sample under the recency weights (W2) at the registered weight ({lvl})"
        if o["held"]:
            return f"{head}; its weighted lower bound held on {WINDOW} (realised {x:+.3f} ≥ bound {L:+.3f})."
        return f"{head}; its weighted lower bound did not hold on {WINDOW} (realised {x:+.3f} < bound {L:+.3f})."
    rel = "≥" if o["held"] else "<"
    return (f"{obj}: refused in-sample; consistent with the registered detection floor. "
            f"Graded: realised {x:+.3f} {rel} its weighted lower bound {L:+.3f}.")


def read(g: dict) -> tuple[str, dict]:
    L = [f"FRENCH LONG HISTORY, B1 HOLDOUT GRADING (registered at {g.get('registration')}); HEAD {g.get('git_head')}",
         "=" * 92,
         f"holdout {g['first_holdout_date']} .. {g['last_date']} ({g['n_periods']} graded periods); "
         f"stationary bootstrap, block length {g['block_length']}, B {g['B']}, seed {g['seed']}",
         f"limits of the certificate: {LIMITS}", SIX_YEARS]
    out = {}
    for name in ORDER:
        o = g["objects"][name]
        lo, hi = o["ci90"]
        d = o["descriptive"]
        L += ["", label(name, o),
              f"   realised holdout net Sharpe (unweighted) {o['realized']:+.3f}  90% [{lo:+.3f}, {hi:+.3f}]; "
              f"in-sample weighted L90 (the bound) {o['L90_weighted']:+.3f}; {'HELD' if o['held'] else 'NOT HELD'}",
              f"   -> {branch(name, o)}",
              f"   [descriptive] realised - bound {d['realized_minus_L90']:+.3f}  90% "
              f"[{d['ci90_minus_L90'][0]:+.3f}, {d['ci90_minus_L90'][1]:+.3f}]",
              f"   [descriptive] in-sample weighted confidence curve at the realised value: C = {d['C_at_realized']:.3f}"
              + ("  (outside the curve's grid; the end value)" if d["C_clipped"] else "")]
        if "unweighted" in d:
            u = d["unweighted"]
            L.append(f"   [{u['label']}] realised against the in-sample unweighted L90 {u['L90_unweighted']:+.3f}: "
                     f"{u['realized_minus_L90_unweighted']:+.3f}")
        out[name] = {"held": o["held"], "realized": o["realized"], "L90_weighted": o["L90_weighted"],
                     "certified": o["certified"]}
    return "\n".join(L), out


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
    if g.get("registration") != LIVE:
        raise SystemExit("REFUSED: the grades are not this registration's")
    text, out = read(g)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
