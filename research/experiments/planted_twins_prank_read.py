"""Read the twin-calibration p-rank cell ONCE, in the registered order.

`prereg/twin-calibration.md`, the p-rank cell (levels 0 and 1.5, panels 650000-650999):

1. **T1 at level 0**, per searcher and construction (6 x 2 = 12 rules). Twin rejections
   (`p_twin <= 1/20`) over all 1,000 panels. At level 0 every member's population
   Sharpe is negative, so every rejection is false. The rate is given with its Wilson
   95% interval. **FAILS HIGH iff the lower Wilson end exceeds 0.05, which at n =
   1,000 is iff k >= 64** (the reader checks that the two agree). Tie counts and the
   attainable grid are beside each rule. **If any rule fails high, the reader stops**
   and prints the one-shot replication's launch.
2. **The autocorrelation sign at level 0**: the median over panels of
   `median_lag1_autocorr_real`, and the direction it predicts.
3. **T2 at 1.5, descriptive.** Correct twin rejections (population Sharpe > 0) beside
   the class tier's correct certificates (`p_class_real < 0.05`) on the same panels,
   with the paired discordance both ways.

It refuses to run unless the file holds exactly 650000-650999, each at levels 0 and 1.5
with six searchers, every line parsing, and every record from the p-rank cell.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from estimator.metrics import wilson_ci

SEEDS = range(650_000, 651_000)
LEVELS = (0.0, 1.5)
ALPHA = 0.05
P_REJECT = 1 / 20
K_FIRES = 64
CONSTRUCTIONS = ("joint_time_permutation", "block_permutation")
REPLICATION_LAUNCH = (
    "ssh og-48 'cd ~/observable-garden && git pull --ff-only && cloud/run.sh prank_rep "
    "bash -c \"echo commit \\$(git rev-parse HEAD); exec python -m experiments.planted_twins "
    "--cell prank --planted 1.5 --replication --draws 1000 --workers 191\" && tmux "
    "new-session -d -s selfstop_after_prank_rep \"while tmux has-session -t "
    "'=prank_rep' 2>/dev/null; do sleep 60; done; sleep 600; sudo shutdown -h now\"'")


def load(path: Path, seeds=SEEDS) -> list[dict]:
    recs = []
    for i, ln in enumerate(path.read_text().splitlines(), 1):
        try:
            recs.append(json.loads(ln))
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: line {i} does not parse; refused")
    if sorted(r["seed"] for r in recs) != list(seeds):
        raise SystemExit(f"{path}: seeds are not exactly {seeds.start}-{seeds.stop - 1}; "
                         "refused")
    for r in recs:
        if r.get("cell") != "prank":
            raise SystemExit(f"seed {r['seed']}: not a p-rank record; refused")
        if tuple(lv["beta"] for lv in r["levels"]) != LEVELS:
            raise SystemExit(f"seed {r['seed']}: levels are not {LEVELS}; refused")
        if any(len(lv["searchers"]) != 6 for lv in r["levels"]):
            raise SystemExit(f"seed {r['seed']}: not six searchers per level; refused")
    return recs


def level(recs, beta):
    return [next(lv for lv in r["levels"] if lv["beta"] == beta) for r in recs]


def rejects(s: dict, c: str) -> bool:
    return s[f"p_twin_{c}"] <= P_REJECT + 1e-12


def read(recs) -> tuple[str, bool]:
    L: list[str] = []
    A = L.append
    l0, l1 = level(recs, 0.0), level(recs, 1.5)
    names = [s["searcher"] for s in l0[0]["searchers"]]
    n = len(l0)
    A("twin-calibration p-rank cell — READ ONCE, in the registered order")
    A("=" * 78)
    A(f"  panels {n} (seeds {SEEDS.start}-{SEEDS.stop - 1}), levels 0 and 1.5, K = 19 per "
      "construction, B = 1,000, alpha = 0.05 (p_twin <= 1/20)")
    A("")
    A("1. T1 AT LEVEL 0 — false certification, one-sided on the lower Wilson end")
    A("-" * 78)
    A(f"   fails high iff the lower Wilson 95% end exceeds 0.05; at n = 1,000, iff k >= {K_FIRES}")
    A("   attainable grid: multiples of 1/20; ties counted against the real run (conservative)")
    A(f"   {'searcher':<30}{'construction':<24}{'k':>5}{'rate':>8}   {'Wilson 95%':<18}"
      f"{'verdict':<12}{'ties':>6}{'tied panels':>12}")
    any_fail = False
    for name in names:
        for c in CONSTRUCTIONS:
            k = ties = tied = 0
            for lv in l0:
                s = next(x for x in lv["searchers"] if x["searcher"] == name)
                k += rejects(s, c)
                ties += s[f"ties_{c}"]
                tied += s[f"ties_{c}"] > 0
            lo, hi = wilson_ci(k, n)
            fails = k >= K_FIRES
            if n == 1000 and fails != (lo > ALPHA):
                raise SystemExit(f"{name}/{c}: k >= {K_FIRES} and the lower-Wilson rule "
                                 f"disagree (k {k}, lower {lo:.4f}); refused")
            any_fail |= fails
            A(f"   {name:<30}{c:<24}{k:>5}{k / n:>8.4f}   [{lo:.4f}, {hi:.4f}]   "
              f"{'FAILS HIGH' if fails else 'PASS':<12}{ties:>6}{tied:>12}")
    A("")
    A("   Registered beside the twelve: an exactly valid rule passes 0.9716; twelve")
    A("   independent valid rules all pass 0.69-0.71, 0.99 with the replication branch.")
    A(f"   T1: {'AT LEAST ONE RULE FAILS HIGH' if any_fail else 'all twelve PASS'}")
    A("")
    if any_fail:
        A("2-3. NOT PRINTED")
        A("-" * 78)
        A("   A T1 rule fails high, so by the registered branch the one-shot replication on")
        A("   660000-660999 runs before anything else is read. Its launch, after a dated")
        A("   commit recording the failure:")
        A("   " + REPLICATION_LAUNCH)
        return "\n".join(L), True
    A("2. THE AUTOCORRELATION SIGN (level 0)")
    A("-" * 78)
    ac = np.array([lv["median_lag1_autocorr_real"] for lv in l0], dtype=float)
    med = float(np.median(ac))
    A(f"   median over the {n} level-0 panels of median_lag1_autocorr_real: {med:+.6f}")
    A("   sign " + ("positive: predicts a departure ABOVE 1/20 (liberal)" if med > 0 else
                    "negative: predicts a departure BELOW 1/20 (conservative)" if med < 0
                    else "zero: predicts no departure")
      + "; predicted small, smaller under block permutation")
    A(f"   (panels positive: {int((ac > 0).sum())}, negative: {int((ac < 0).sum())})")
    A("")
    A("3. T2 AT 1.5 — DESCRIPTIVE; twin power beside the class tier's, same panels")
    A("-" * 78)
    A(f"   {'searcher':<30}{'construction':<24}{'twin k':>7}{'class k':>8}"
      f"{'twin only':>10}{'class only':>11}   twin Wilson 95%")
    for name in names:
        for c in CONSTRUCTIONS:
            kt = kc = t_only = c_only = 0
            for lv in l1:
                s = next(x for x in lv["searchers"] if x["searcher"] == name)
                good = s["truth_in_sample"] is not None and s["truth_in_sample"] > 0
                tw = rejects(s, c) and good
                cl = s["p_class_real"] < ALPHA and good
                kt += tw
                kc += cl
                t_only += tw and not cl
                c_only += cl and not tw
            lo, hi = wilson_ci(kt, n)
            A(f"   {name:<30}{c:<24}{kt:>7}{kc:>8}{t_only:>10}{c_only:>11}   "
              f"[{lo:.4f}, {hi:.4f}]")
    A("")
    A("   predicted: twin below class, since the static part of the planted signal")
    A("   survives into every twin")
    return "\n".join(L), False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="runs/planted_twins/draws.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text, _ = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
