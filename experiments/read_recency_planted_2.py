"""Reader for the recency planted validation, ROUND 2 (`prereg/recency-weight-planted-2.md`,
46b589e; amendment 86277fc). Committed and tested on made-up rows only before any panel is
drawn. Reads once, in this order:

  1. W2's checks: the stream on N40, NV40, NA40, NAREV40, and the class on N40 and NA40, at both
     levels. A rate FAILS iff the lower end of its 95% Wilson interval exceeds the level.
  2. R15's checks: the stream on the four null arms, at both levels.
  3. THE REGISTERED RULE: W2 adopted iff none of its checks fails; otherwise R15, provided none
     of its checks fails; otherwise stop, and the author decides.
  4. Beside, descriptive: the round-1 fixed centring and the unweighted statistic on every null
     arm, and the two block-length medians.
  5. NA40 under W2: its branch sentence (no expectation was registered).
  6. Power (not in the rule): paired W2 - unweighted, R15 - unweighted and W2 - R15 on E20, D20
     and C20, at both levels; 95% paired bootstrap intervals, B 10,000, seed 714999.

    python -m experiments.read_recency_planted_2 --dir runs/recency_planted_2/<date>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from experiments.read_recency_planted import paired, rate_line

LEVELS = {"96%": {"stream": 0.04, "class": 0.01}, "90%": {"stream": 0.08, "class": 0.02}}
NULLS = ("N40", "NV40", "NA40", "NAREV40")
CLASS_ARMS = ("N40", "NA40")
EDGES = ("E20", "D20", "C20")
N_REGISTERED = {"N40": 1000, "NV40": 1000, "NA40": 1000, "NAREV40": 1000, "E20": 400, "D20": 400, "C20": 400}
PAIRED_SEED = 714999


def read(rows: list[dict]) -> tuple[str, dict]:
    by = {}
    for r in rows:
        by.setdefault(r["arm"], []).append(r)
    for arm in by:
        by[arm].sort(key=lambda r: r["seed"])
    L = ["RECENCY-WEIGHTED CERTIFICATE ON PLANTED PANELS, ROUND 2 (plan 46b589e; amendment 86277fc)", "=" * 92]
    short = [a for a, n in N_REGISTERED.items() if len(by.get(a, [])) != n]
    if short:
        L.append(f"arms with other than the registered n: {short}: not read. STOP and ask.")
        return "\n".join(L), {"stopped": short}
    cert = lambda arm, tier, test, lvl: np.array([r[tier][test]["p"] < LEVELS[lvl][tier] for r in by[arm]])
    out = {}

    def checks(test: str, tiers) -> bool:
        any_fail = False
        for tier, arms in tiers:
            for arm in arms:
                for lvl in ("96%", "90%"):
                    t, o = rate_line(f"{tier} {arm} {test}, {lvl} level", cert(arm, tier, test, lvl), LEVELS[lvl][tier])
                    L.append(t)
                    out[f"{test} {tier} {arm} {lvl}"] = o
                    any_fail |= bool(o["fails"])
        return any_fail

    L.append("1. W2's CHECKS (a rate fails iff its lower 95% Wilson end exceeds the level)")
    w2_fails = checks("W2", (("stream", NULLS), ("class", CLASS_ARMS)))
    L.append("")
    L.append("2. R15's CHECKS")
    r15_fails = checks("R15", (("stream", NULLS),))
    L.append("")
    if not w2_fails:
        decision = "W2 is ADOPTED for weighted reads"
    elif not r15_fails:
        decision = "W2 is NOT adopted (a check failed); recency reads use R15 (none of its checks failed)"
    else:
        decision = "W2 and R15 both fail a check: STOP; the author decides"
    L.append(f"3. THE REGISTERED RULE: {decision}")
    out["decision"] = decision
    out["W2 any fail"], out["R15 any fail"] = w2_fails, r15_fails
    L.append("")
    L.append("4. BESIDE (descriptive): the round-1 fixed centring and the unweighted statistic; block lengths")
    for arm in NULLS:
        for test in ("fixed", "unweighted"):
            for lvl in ("96%", "90%"):
                t, o = rate_line(f"stream {arm} {test}, {lvl}", cert(arm, "stream", test, lvl), LEVELS[lvl]["stream"])
                L.append(t)
                out[f"beside {test} {arm} {lvl}"] = o
        bl = np.array([r["block_length"] for r in by[arm]])
        bt = np.array([r["block_length_last_neff"] for r in by[arm]])
        L.append(f"   {arm} block length: registered rule median {np.median(bl):.0f} [{bl.min()}, {bl.max()}]; "
                 f"last n_eff rows median {np.median(bt):.0f} [{bt.min()}, {bt.max()}]")
    L.append("")
    na_fail = any(out[f"W2 stream NA40 {lvl}"]["fails"] for lvl in ("96%", "90%"))
    L.append("5. NA40 UNDER W2 (no expectation registered): " + (
        "it fails: reported with its rate; the rule decides" if na_fail else
        "it does not fail: the weighted draw corrects the null's long-run variance on this shift"))
    out["NA40 W2 fails"] = na_fail
    L.append("")
    L.append("6. POWER (not in the rule): paired differences, 95% intervals")
    rng = np.random.default_rng(PAIRED_SEED)
    for arm in EDGES:
        for lvl in ("96%", "90%"):
            v = {t: cert(arm, "stream", t, lvl) for t in ("W2", "R15", "unweighted")}
            parts = [f"rates W2 {v['W2'].mean():.3f}, R15 {v['R15'].mean():.3f}, unweighted {v['unweighted'].mean():.3f}"]
            for a, b in (("W2", "unweighted"), ("R15", "unweighted"), ("W2", "R15")):
                d = paired(v[a], v[b], rng)
                out[f"power {arm} {lvl} {a}-{b}"] = d
                parts.append(f"{a} - {b} {d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}]")
            L.append(f"   {arm} {lvl}: " + "; ".join(parts))
    return "\n".join(L), out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    d = Path(a.dir)
    prov = json.loads((d / "provenance.json").read_text())
    if prov.get("dry_run") or prov.get("smoke") or prov.get("platform") != "Linux x86_64":
        raise SystemExit("not a box run of the registered task list; not read")
    if (d / "read.txt").exists():
        raise SystemExit("already read")
    rows = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    text, out = read(rows)
    (d / "read.txt").write_text(text + "\n")
    (d / "decision.json").write_text(json.dumps(out, indent=1, default=float))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
