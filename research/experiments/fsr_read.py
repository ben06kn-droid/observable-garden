"""Read fixed-sequence-replay's rules, once, from a finished run.

    python -m experiments.fsr_read figures/fixed_sequence_replay_data.pkl

Rules 1-4 are `prereg/fixed-sequence-replay.md`'s, as amended: rule 1 one-sided
per amendment 1, rule 3 replaced by amendment 6 (null 2 against null 3, exact
zeros excluded and counted, a one-sided sign test at 0.005 each way, read on the
three searchers whose continuation differs from the fill), and amendment 6's
size readout and engagement rate. Nothing here chooses a threshold: every number
it prints was fixed before the run.
"""
from __future__ import annotations

import pickle
import sys

import numpy as np
from scipy.stats import binomtest

from estimator.metrics import type1_rate

ALPHAS = (0.05, 0.01)
SIGN_TEST_ALPHA = 0.005                      # amendment 6, each direction
RULE3 = {"lookahead-stop-when-cleared": "liberal",
         "random-extend-while-improving": "conservative",
         "second-best-while-improving": "conservative"}
SIZE_READOUT = "lookahead-stop-when-cleared"  # amendment 6


def _col(rows, name, field):
    return np.array([r[name][field] for r in rows])


def rule3_branch(signed: np.ndarray, predicted: str) -> tuple[str, dict]:
    nz = signed[signed != 0.0]
    stats = {"draws": signed.size, "zero": int(np.sum(signed == 0.0)),
             "nonzero": int(nz.size), "median_signed": float(np.median(signed)),
             "positive": int(np.sum(nz > 0)), "p_positive": None, "p_negative": None}
    if nz.size == 0:
        return "identical", stats
    up = binomtest(stats["positive"], nz.size, 0.5, alternative="greater").pvalue
    dn = binomtest(stats["positive"], nz.size, 0.5, alternative="less").pvalue
    stats["p_positive"], stats["p_negative"] = float(up), float(dn)
    if up < SIGN_TEST_ALPHA:
        found = "liberal"
    elif dn < SIGN_TEST_ALPHA:
        found = "conservative"
    else:
        return "no direction detected", stats
    if not predicted:
        return found, stats               # reported only: no prediction to compare
    return ("predicted direction confirmed: " + found if found == predicted
            else "OPPOSITE of the predicted direction: " + found), stats


def report(data: dict) -> str:
    rows = data["rows"]
    names = [k for k in rows[0] if not k.startswith("_")]
    g = data["git_at_launch"]
    L = [f"fixed-sequence-replay — rules at n={data['draws']} draws, B={data['B']:,}, "
         f"seeds from {data['seed0']}", "=" * 78,
         f"git at launch {g['commit'][:7]}" + (" (tracked changes)" if g.get("dirty") else ""),
         f"searchers: {len(names)} (amendment 6)", "",
         "ENGAGEMENT — registered readout (amendment 6): the share of replicates",
         "running past the realized length, where the fill can act at all",
         "-" * 78]
    for nm in names:
        eng = _col(rows, nm, "engaged")
        L.append(f"  {nm:32s} {eng.sum() / (len(rows) * data['B']):7.2%} of replicates; "
                 f"draws with none: {int(np.sum(eng == 0)):5d} of {len(rows)}")

    L += ["", "RULE 1 — trigger replay is valid (primary, one-sided per amendment 1:",
          "         fails high iff the LOWER end of the Wilson 95% interval exceeds",
          "         nominal; the upper end is the largest liberality not ruled out)",
          "-" * 78,
          f"    {'searcher':34s}{'a':>6}{'k':>7}{'rate':>9}{'lower':>9}{'upper':>9}{'liberal?':>10}"]
    fired = []
    for nm in names:
        p = _col(rows, nm, "p_trigger")
        for a in ALPHAS:
            rate, lo, hi = type1_rate(p, alpha=a)
            bad = lo > a
            fired += [(nm, a)] if bad else []
            L.append(f"    {nm:34s}{a:>6}{int(np.sum(p < a)):>7}{rate:>9.4f}{lo:>9.4f}"
                     f"{hi:>9.4f}{'YES' if bad else 'no':>10}")
    L.append("")
    L.append("  rule 1: " + ("PASSES for every searcher at both levels" if not fired
                             else f"FAILS HIGH: {fired} — the replication branch (amendment 3c) applies"))

    L += ["", "RULE 2 — the frozen-decision error (primary readout, no halt):",
          "         null 1's rejection rate beside null 3's. Predicted: liberal",
          "-" * 78,
          f"    {'searcher':34s}{'a':>6}{'null 1':>9}{'null 3':>9}{'diff':>9}"
          f"{'median realized length':>24}"]
    for nm in names:
        p1, p3 = _col(rows, nm, "p_fixed"), _col(rows, nm, "p_policy")
        ln = np.array([len(r[nm]["realized_actions"]) for r in rows])
        for a in ALPHAS:
            r1, r3 = float(np.mean(p1 < a)), float(np.mean(p3 < a))
            L.append(f"    {nm:34s}{a:>6}{r1:>9.4f}{r3:>9.4f}{r1 - r3:>+9.4f}"
                     f"{int(np.median(ln)):>24}")

    L += ["", "RULE 3 (amendment 6) — null 2 against null 3, content only.",
          "         Exact zeros excluded and counted; one-sided sign test at 0.005",
          "         each way; read on the three searchers below, reported for all",
          "-" * 78]
    for nm in names:
        s = _col(rows, nm, "signed_ks_2v3")
        predicted = RULE3.get(nm)
        branch, st = rule3_branch(s, predicted or "")
        read = f"READ, predicted {predicted}" if predicted else "reported only"
        L.append(f"  {nm:34s} [{read}]")
        L.append(f"    zero-distance draws {st['zero']:5d} of {st['draws']} "
                 f"({st['zero'] / st['draws']:.1%}); median signed distance {st['median_signed']:+.4f}")
        if st["nonzero"]:
            L.append(f"    positive on {st['positive']} of {st['nonzero']} non-zero draws; "
                     f"sign test p(positive) {st['p_positive']:.2e}, p(negative) {st['p_negative']:.2e}")
        L.append(f"    -> {branch}")

    L += ["", f"SIZE READOUT (amendment 6) — {SIZE_READOUT}: type-I under null 2 and null 3,",
          "         and a paired exact McNemar test on the discordant draws",
          "-" * 78]
    p2, p3 = _col(rows, SIZE_READOUT, "p_trigger"), _col(rows, SIZE_READOUT, "p_policy")
    for a in ALPHAS:
        r2, lo2, hi2 = type1_rate(p2, alpha=a)
        r3, lo3, hi3 = type1_rate(p3, alpha=a)
        b = int(np.sum((p2 < a) & ~(p3 < a)))
        c = int(np.sum(~(p2 < a) & (p3 < a)))
        mc = binomtest(b, b + c, 0.5, alternative="greater").pvalue if b + c else 1.0
        L += [f"  a={a}: null 2 {r2:.4f} ({lo2:.4f}-{hi2:.4f})   null 3 {r3:.4f} ({lo3:.4f}-{hi3:.4f})"
              f"   inflation {r2 - r3:+.4f}",
              f"        discordant draws: null 2 only {b}, null 3 only {c}; "
              f"McNemar one-sided p = {mc:.4f} -> "
              f"{'DETECTABLE at 0.05' if mc < 0.05 else 'not detectable at 0.05'}"]
    L += ["", "  Consequence (amendment 6): detectable inflation makes strengthening the",
          "  agent-path fill mandatory in 7.2 part two (multi-step fill, the local-max",
          "  upper end, or a declared continuation); undetectable makes it optional and",
          "  stated with the interval's upper end.", ""]

    L += ["RULE 4 — distance of null 1 from null 3, with null 2's for contrast",
          "-" * 78, f"    {'searcher':34s}{'KS(1,3)':>10}{'KS(2,3)':>10}"]
    for nm in names:
        L.append(f"    {nm:34s}{np.mean(_col(rows, nm, 'ks_1v3')):>10.4f}"
                 f"{np.mean(_col(rows, nm, 'ks_2v3')):>10.4f}")
    secs = np.array([r["_draw"]["seconds"] for r in rows])
    L += ["", "COST", "-" * 78,
          f"  per draw mean {secs.mean():.1f}s; {secs.sum() / 3600:,.0f} CPU-hours over "
          f"{len(rows)} draws", ""]
    return "\n".join(L)


if __name__ == "__main__":
    print(report(pickle.load(open(sys.argv[1], "rb"))))
