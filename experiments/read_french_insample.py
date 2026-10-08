"""Reader for the French panel's in-sample read (`prereg/french-panel.md`, section k;
live at de9da1b914bcd2522ef95ddc4be4231eb47b1af0). Committed and tested on made-up results
only (tests/test_read_french_insample.py) before the read runs. Renders once, in the
registered order: (i) the stream, then (ii) the class maximum.

    python -m experiments.read_french_insample --dir runs/french_insample/2026-10-07
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CERTIFIED = "certified in-sample at the registered weight; whether it holds is the holdout grading's question."
REFUSED = "refused; consistent with the registered detection floor; no further reading."


def branch(t: dict) -> str:
    return CERTIFIED if t["p"] < t["alpha"] else REFUSED


def render_test(label: str, t: dict) -> list[str]:
    L = [f"{label}: {t['test']}",
         f"   window rows {t['window_rows'][0]}..{t['window_rows'][1]} ({t['n_rows']} rows); "
         f"B {t['B']}, seed {t['seed']}, block length {t['block_length']}",
         f"   observed net Sharpe {t['S']:.3f}; p {t['p']:.4f} (certified iff p < {t['alpha']})",
         f"   90% lower bound {t['L90']:+.3f}; confidence fields stored in full (curve of "
         f"{len(t['confidence']['curve'])} points)"]
    if "best_member" in t:
        L.append(f"   best member: {', '.join(t['best_member']['features'])} "
                 f"(supports {t['best_member']['support']}; index {t['best_member']['index']} of {t['N']})")
    L.append(f"   -> {branch(t)}")
    return L


def read(rec: dict) -> tuple[str, dict]:
    L = [f"FRENCH 49-INDUSTRY IN-SAMPLE READ (registered at {rec.get('registration')}); "
         f"platform {rec.get('platform')}; HEAD {rec.get('git_head')}", "=" * 88]
    if not rec.get("repeat_bit_identical"):
        L.append("the bit-for-bit repeat FAILED: nothing was priced; the read stopped. STOP and ask.")
        return "\n".join(L), {"stopped": True}
    for key in ("i_stream", "ii_class"):
        if key not in rec:
            L.append(f"{key} missing from the results: not read. STOP and ask.")
            return "\n".join(L), {"stopped": True}
    L += render_test("(i)", rec["i_stream"])
    L.append("")
    L += render_test("(ii)", rec["ii_class"])
    out = {"i_stream": {"certified": rec["i_stream"]["p"] < rec["i_stream"]["alpha"],
                        "branch": branch(rec["i_stream"])},
           "ii_class": {"certified": rec["ii_class"]["p"] < rec["ii_class"]["alpha"],
                        "branch": branch(rec["ii_class"])}}
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    if (d / "read.txt").exists():
        raise SystemExit("already read; the read happens once")
    rec = json.loads((d / "results.json").read_text())
    if rec.get("platform") != "Darwin arm64":
        raise SystemExit("not a laptop (Darwin arm64) run; not read")
    text, out = read(rec)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
