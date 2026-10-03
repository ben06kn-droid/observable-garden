"""Read the twin-calibration score-rank cell ONCE, in the registered order.

`prereg/twin-calibration.md`, "Score-rank cell — LIVE, 2026-10-02". Everything here is
the live section's definitions and nothing else:

1. **T1 at level 0**, per searcher and construction (6 x 2 = 12 rules): k rejections
   (`p <= 1/20`) over all 1,000 panels, the rate, the Wilson 95% interval, and **PASS or
   FAILS HIGH: fails iff the lower Wilson end exceeds 0.05, which at n = 1,000 is iff
   k >= 64** (the reader checks the two agree). Tie counts and empty-submission counts
   beside each. The registered family figures are printed beside the twelve.
2. **The autocorrelation sign**: the median across the level-0 panels of
   `median_lag1_autocorr_signed_singles`, its sign, and the direction it predicts.
3. **Level 1.0, descriptive**: correct rejections (submission population Sharpe > 0)
   per searcher and construction with Wilson intervals, and rejections of submissions
   with population Sharpe <= 0 (or none) listed separately. **Not printed if any T1 rule
   fails high**: the reader stops after T1 and prints the registered replication's launch
   instead.

It refuses to run unless the file holds exactly 1,000 distinct seeds, every line parsing.

    python -m experiments.planted_twins_read --file runs/planted_twins_score/draws.jsonl \\
        --out runs/planted_twins_score/read.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from estimator.metrics import wilson_ci

N_REGISTERED = 1000
ALPHA = 0.05
P_REJECT = 1 / 20                     # K = 19: the only attainable level
K_FIRES = 64                          # the registered rule at n = 1,000
CONSTRUCTIONS = ("joint_time_permutation", "block_permutation")
REPLICATION_LAUNCH = (
    "ssh -i ~/Desktop/'Observable garden'/observable-garden.pem ubuntu@<BOX_IP> "
    "'cd ~/observable-garden && git pull --ff-only && cloud/run.sh twin_score_rep bash -c "
    "\"echo commit \\$(git rev-parse HEAD); exec python -m experiments.planted_twins "
    "--cell score --replication --draws 1000 --workers 191\" && tmux new-session -d -s "
    "twin_score_rep_selfstop \"while tmux has-session -t twin_score_rep 2>/dev/null; do "
    "sleep 60; done; sleep 600; sudo shutdown -h now\"'")


def load(path: Path) -> list[dict]:
    recs, seeds = [], set()
    for i, ln in enumerate(path.read_text().splitlines(), 1):
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: line {i} does not parse; refused")
        recs.append(r)
        seeds.add(r["seed"])
    if len(recs) != N_REGISTERED or len(seeds) != N_REGISTERED:
        raise SystemExit(f"{path}: {len(recs)} lines and {len(seeds)} distinct seeds; the "
                         f"registered read needs exactly {N_REGISTERED} of each. Refused.")
    return recs


def level(recs, beta: float) -> list[dict]:
    out = []
    for r in recs:
        lv = [x for x in r["levels"] if x["beta"] == beta]
        if len(lv) != 1:
            raise SystemExit(f"seed {r['seed']}: {len(lv)} records at level {beta}")
        out.append(lv[0])
    return out


def rejects(s: dict, c: str) -> bool:
    return s[f"p_score_{c}"] <= P_REJECT + 1e-12


def read(recs) -> tuple[str, bool]:
    L: list[str] = []
    A = L.append
    l0, l1 = level(recs, 0.0), level(recs, 1.0)
    searchers = [s["searcher"] for s in l0[0]["searchers"]]
    n = len(l0)
    A("twin-calibration score-rank cell — READ ONCE, in the registered order")
    A("=" * 78)
    A(f"  panels {n} (seeds {min(r['seed'] for r in recs)}-{max(r['seed'] for r in recs)}), "
      f"levels 0 and 1.0, K = 19 per construction, alpha = 0.05 (p <= 1/20)")
    A("")
    A("1. T1 AT LEVEL 0 — false certification, one-sided on the lower Wilson end")
    A("-" * 78)
    A("   fails high iff the lower Wilson 95% end exceeds 0.05; at n = 1,000, iff k >= 64")
    A(f"   {'searcher':<30}{'construction':<24}{'k':>5}{'rate':>8}   {'Wilson 95%':<18}"
      f"{'verdict':<12}{'ties':>6}{'tied panels':>12}{'empty':>7}")
    any_fail = False
    for name in searchers:
        for c in CONSTRUCTIONS:
            k = ties = tied_panels = empty = 0
            for lv in l0:
                s = next(x for x in lv["searchers"] if x["searcher"] == name)
                k += rejects(s, c)
                ties += s[f"ties_{c}"]
                tied_panels += s[f"ties_{c}"] > 0
                empty += s["support"] is None
            lo, hi = wilson_ci(k, n)
            fails = k >= K_FIRES
            if fails != (lo > ALPHA):
                raise SystemExit(f"{name}/{c}: k >= 64 and the lower-Wilson rule disagree "
                                 f"(k {k}, lower {lo:.4f}); refused")
            any_fail |= fails
            A(f"   {name:<30}{c:<24}{k:>5}{k / n:>8.4f}   [{lo:.4f}, {hi:.4f}]   "
              f"{'FAILS HIGH' if fails else 'PASS':<12}{ties:>6}{tied_panels:>12}{empty:>7}")
    A("")
    A("   Registered beside the twelve: an exactly valid rule passes 0.9716 and 80% detects a")
    A("   true rate of 0.0705; twelve independent valid rules all pass 0.69-0.71 of the time,")
    A("   0.99 with the one-shot replication branch.")
    A(f"   T1: {'AT LEAST ONE RULE FAILS HIGH' if any_fail else 'all twelve PASS'}")
    A("")
    A("2. THE AUTOCORRELATION SIGN (level 0)")
    A("-" * 78)
    ac = np.array([lv["median_lag1_autocorr_signed_singles"] for lv in l0], dtype=float)
    med = float(np.median(ac))
    direction = ("positive: predicts a departure ABOVE 1/20 (liberal)" if med > 0 else
                 "negative: predicts a departure BELOW 1/20 (conservative)" if med < 0 else
                 "zero: predicts no departure")
    A(f"   median across the {n} level-0 panels of median_lag1_autocorr_signed_singles: "
      f"{med:+.6f}")
    A(f"   sign {direction}; predicted small either way, smaller under block permutation")
    A(f"   (panels with a positive figure: {int((ac > 0).sum())}, negative: "
      f"{int((ac < 0).sum())})")
    A("")
    if any_fail:
        A("3. LEVEL 1.0 — NOT PRINTED")
        A("-" * 78)
        A("   A T1 rule fails high, so by the registered branch the one-shot replication on")
        A("   660000-660999 runs before anything else is read. Its launch, after a dated")
        A("   commit recording the failure:")
        A("   " + REPLICATION_LAUNCH)
        return "\n".join(L), any_fail
    A("3. LEVEL 1.0 — DESCRIPTIVE; no rule reads it")
    A("-" * 78)
    A(f"   correct rejection: p <= 1/20 AND the submission's population Sharpe > 0")
    A(f"   {'searcher':<30}{'construction':<24}{'k':>5}{'rate':>8}   {'Wilson 95%':<18}")
    wrong = []
    for name in searchers:
        for c in CONSTRUCTIONS:
            k = 0
            for lv in l1:
                s = next(x for x in lv["searchers"] if x["searcher"] == name)
                if rejects(s, c):
                    t = s["truth_in_sample"]
                    if t is not None and t > 0:
                        k += 1
                    else:
                        wrong.append((name, c, lv["seed"], t))
            lo, hi = wilson_ci(k, n)
            A(f"   {name:<30}{c:<24}{k:>5}{k / n:>8.4f}   [{lo:.4f}, {hi:.4f}]")
    A("")
    A("   rejections at level 1.0 of submissions with population Sharpe <= 0 (or none), "
      f"listed separately: {len(wrong)}")
    for name, c, seed, t in wrong:
        A(f"     {name:<30}{c:<24} seed {seed}  population Sharpe "
          f"{'none' if t is None else f'{t:+.6f}'}")
    return "\n".join(L), any_fail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="runs/planted_twins_score/draws.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text, failed = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
