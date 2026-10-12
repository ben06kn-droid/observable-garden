"""Reader for the Binance panel's in-sample read (`prereg/binance-panel.md`, section m; live at
ecc07f0e6117e92db9ac03be462f418e3b0ac246). Committed and tested on made-up results only
(tests/test_read_binance_insample.py) before the read runs. Renders once, in the registered
order:
- the repeat;
- test 1, the d = 0 stream;
- test 2, the class maximum;
- then the d = 1 stream, labelled as looked at, with no verdict.

    python -m experiments.read_binance_insample --dir runs/binance_insample/2026-10-09
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CERTIFIED = "certified in-sample at the registered weight; whether it holds is the holdout grading's question."
REFUSED = "refused; consistent with the registered detection floor; no further reading."
DESCRIPTIVE = ("descriptive, not a test: the same stream with a one-bar delay. It is looked at to show how "
               "much depends on immediacy; it carries no p-value, no verdict and no claim.")


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
    L = []
    if rec.get("dry_run"):
        L.append("DRY RUN on a synthetic panel: these numbers are not this panel's and are not a read.")
    L += [f"BINANCE 4h (formation 2021-01) IN-SAMPLE READ (registered at {rec.get('registration')}); "
          f"platform {rec.get('platform')}; HEAD {rec.get('git_head')}", "=" * 88]
    rep = rec.get("repeat_bit_identical") or {}
    if not (rep.get("d0") and rep.get("d1")) or rec.get("stopped"):
        L.append(f"the bit-for-bit repeat FAILED or the read stopped ({rec.get('stopped')}; repeat {rep}): "
                 "nothing was priced. STOP and ask.")
        return "\n".join(L), {"stopped": True}
    L.append("bit-for-bit repeat: d = 0 identical, d = 1 identical")
    for key in ("test1_stream_d0", "test2_class_d0", "descriptive_stream_d1"):
        if key not in rec:
            L.append(f"{key} missing from the results: not read. STOP and ask.")
            return "\n".join(L), {"stopped": True}
    L.append("")
    L += render_test("Test 1", rec["test1_stream_d0"])
    L.append("")
    L += render_test("Test 2", rec["test2_class_d0"])
    d = rec["descriptive_stream_d1"]
    L += ["", "-" * 88, f"LOOKED AT, NOT TESTED: {DESCRIPTIVE}",
          f"   d = 1 stream, window rows {d['window_rows'][0]}..{d['window_rows'][1]} ({d['n_rows']} rows); "
          f"B {d['B']}, seed {d['seed']}, block length {d['block_length']}",
          f"   observed net Sharpe {d['S']:.3f}; 95% interval [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]",
          "   (no verdict)"]
    out = {k: {"certified": rec[k]["p"] < rec[k]["alpha"], "branch": branch(rec[k])}
           for k in ("test1_stream_d0", "test2_class_d0")}
    out["descriptive_stream_d1"] = {"S": d["S"], "ci95": d["ci95"], "verdict": None}
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    rec = json.loads((d / "results.json").read_text())
    if not rec.get("dry_run") and rec.get("platform") != "Darwin arm64":
        raise SystemExit("not a laptop (Darwin arm64) run; not read")
    text, out = read(rec)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
