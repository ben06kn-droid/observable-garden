"""Read `unfaithful-searchers`' registered rules ONCE, in registered order.

`prereg/README.md`: the rules are read by a reader, not printed by the driver, and
each is read once. This file is that reader. It states both branches of every rule
before giving the verdict, so a reading cannot be steered by which branch was
written down afterwards.

The order is the pre-registration's: 1a, 1b, 2, 3, 4, 5, 6, then the descriptive
readouts amendments 4, 5 and 6 register. Nothing here computes a quantity a rule
does not ask for.

One lesson is carried from `gate_comparison_read.py`: a rule is read the way it is
written. That reader implemented rule 3 at nominal alpha when the rule said
"never at matched nominal", and the first output had to be kept as SUPERSEDED. So
each rule below quotes its own registered form in the text it prints.
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np

from estimator.metrics import wilson_ci
from experiments.unfaithful_searchers import DRAWS_FOR, MEMBERS

FAITHFUL = ("faithful-restart", "faithful-stop")
UNFAITHFUL = ("U1", "U2", "U3", "U3b", "U4")
ALPHAS = (0.05, 0.01)


def _col(rows, name, field):
    return [r[name][field] for r in rows if name in r]


def _rate_line(k, n, nominal, label):
    lo, hi = wilson_ci(k, n)
    fails = lo > nominal
    return (f"    {label:<22} {k:>5}/{n:<5} = {k / n:7.4f}   "
            f"Wilson [{lo:.4f}, {hi:.4f}]   "
            f"{'FAILS HIGH' if fails else 'does not fail high'}"), fails


def read(data: dict) -> str:
    rows = data["rows"]
    L: list[str] = []
    A = L.append
    A("unfaithful-searchers (7.3 scripted) — THE REGISTERED READ")
    A("=" * 78)
    A(f"cell {data['cell']}, {len(rows)} draws, git at launch {data['git_at_launch']}")
    A("Each rule is read once, in registered order, with both branches stated.")
    A("")

    # ---------------------------------------------------------------- rule 1a
    A("RULE 1a — the faithful arm is not harmed (validity, one-sided, primary)")
    A("-" * 78)
    A("  Registered: for each faithful searcher, the rejection rate under trigger")
    A("  replay FAILS HIGH iff the LOWER end of the Wilson 95% interval exceeds")
    A("  nominal. Amendment 5: it reads the PROCEDURE score's p-value.")
    A("    Holds: the checks cost the honest searcher nothing, and everything")
    A("      below is readable.")
    A("    Fails high: a check is rejecting honest searches; nothing downstream is")
    A("      read until that is understood.")
    rule1a_fail = False
    for name in FAITHFUL:
        p = np.asarray(_col(rows, name, "p_replay"), dtype=float)
        A(f"  {name}  (n = {len(p)})")
        for a in ALPHAS:
            line, fails = _rate_line(int((p < a).sum()), len(p), a, f"alpha = {a}")
            A(line)
            rule1a_fail = rule1a_fail or fails
    A(f"  VERDICT 1a: {'FAILS HIGH' if rule1a_fail else 'HOLDS'}")
    A("")

    # ---------------------------------------------------------------- rule 1b
    A("RULE 1b — no check misfires on the faithful arm (registered as 0)")
    A("-" * 78)
    A("  Registered: a count, registered as 0. A single misfire halts the reading,")
    A("  whatever the rate, because every comparison here is against this arm.")
    misfires = 0
    for name in FAITHFUL:
        n = len(_col(rows, name, "p_replay"))
        bad_i = sum(1 for r in rows if name in r and not r[name]["integrity_ok"])
        bad_c = sum(1 for r in rows if name in r and not r[name]["commitment_ok"])
        contra = sum(_col(rows, name, "contradicted_picks"))
        chg = sum(_col(rows, name, "trigger_changes"))
        misfires += bad_i + bad_c + contra + chg
        A(f"  {name}  (n = {n}): integrity failures {bad_i}, commitment failures "
          f"{bad_c}, contradicted picks {contra}, trigger changes {chg}")
        lo, hi = wilson_ci(bad_i + bad_c, n)
        A(f"    identity-check misfire rate Wilson [{lo:.4f}, {hi:.4f}]")
    A(f"  VERDICT 1b: {'MISFIRES — reading halts' if misfires else 'HOLDS (0 misfires)'}")
    A("")

    # ----------------------------------------------------------------- rule 2
    A("RULE 2 — each unfaithful searcher is caught, or is recorded as uncaught")
    A("-" * 78)
    A("  Registered: the share of runs the harness flags — `contradicted` for U1, a")
    A("  late declaration for U2, a logged trigger change for U3, nothing available")
    A("  for U4.")
    A("    Caught in >= 99%: the check does what it claims.")
    A("    Caught sometimes: reported as the detection rate with its Wilson")
    A("      interval, and NO claim of detection beyond it.")
    A("    Never caught: reported as a hole, named, with what would close it.")
    A("      U2 is PREDICTED to land here, registered before the run.")
    FLAG = {"U1": ("contradicted_picks", "contradicted pick"),
            "U2": (None, "a late declaration (nothing available)"),
            "U3": ("trigger_changes", "logged trigger change"),
            "U3b": ("trigger_changes", "logged trigger change"),
            "U4": (None, "nothing available")}
    for name in UNFAITHFUL:
        field, what = FLAG[name]
        n = len(_col(rows, name, "p_replay"))
        k = (sum(1 for r in rows if name in r and r[name][field] > 0)
             if field else 0)
        lo, hi = wilson_ci(k, n)
        band = ("caught in >= 99%" if lo >= 0.99 else
                "NEVER CAUGHT — a hole" if k == 0 else "caught sometimes")
        A(f"  {name:<4} flagged by {what:<38} {k:>5}/{n:<5} = {k / n:6.4f}  "
          f"[{lo:.4f}, {hi:.4f}]  {band}")
    A("")

    # ----------------------------------------------------------------- rule 3
    A("RULE 3 — a contradiction costs exactly nothing (EXACTNESS, primary for U1)")
    A("-" * 78)
    A("  Registered (amendment 1): for EVERY draw, U1's p-value under the certifying")
    A("  null EQUALS its twin's, and the two logs differ only in `contradicted`.")
    A("  This is an exactness rule, not a rate: it is read as equality on every")
    A("  draw, never at a nominal alpha.")
    A("    Equal on every draw: the 2026-09-25 inversion is confirmed as an")
    A("      IDENTITY rather than an estimate.")
    A("    Any draw where they differ: a DEFECT, not a finding; the reading halts.")
    pu, pt = _col(rows, "U1", "p_replay"), _col(rows, "U1-twin", "p_replay")
    su, st = _col(rows, "U1", "realized_score"), _col(rows, "U1-twin", "realized_score")
    n_pairs = min(len(pu), len(pt))
    unequal_p = sum(1 for i in range(n_pairs) if pu[i] != pt[i])
    unequal_s = sum(1 for i in range(n_pairs) if su[i] != st[i])
    c_u = sum(1 for r in rows if "U1" in r and r["U1"]["contradicted_picks"] > 0)
    c_t = sum(1 for r in rows if "U1-twin" in r
              and r["U1-twin"]["contradicted_picks"] > 0)
    A(f"  pairs compared {n_pairs}; p-values unequal on {unequal_p} draws; "
      f"scores unequal on {unequal_s} draws")
    A(f"  contradicted: U1 on {c_u} of {n_pairs} runs, its twin on {c_t}")
    A(f"  VERDICT 3: {'DEFECT — reading halts' if (unequal_p or unequal_s) else 'HOLDS — equal on every draw'}")
    A("")

    # ----------------------------------------------------------------- rule 4
    A("RULE 4 — the uncaught hole is priced (primary). THE HEADLINE NUMBER")
    A("-" * 78)
    A("  Registered: U2's rejection rate on s0 under trigger replay, and under the")
    A("  declared-class certifier. Prediction, registered before the run: the replay")
    A("  rate is >= 0.95. Amendment 4 discloses this prediction was NOT blind — it")
    A("  was made after p-values on the cost-only block had been seen at n <= 8.")
    A("    At or below nominal: the peek does not help; surprising, investigated.")
    A("    Above nominal: the measured cost of trusting a declaration the harness")
    A("      cannot verify.")
    p2 = np.asarray(_col(rows, "U2", "p_replay"), dtype=float)
    for a in ALPHAS:
        k = int((p2 < a).sum())
        lo, hi = wilson_ci(k, len(p2))
        A(f"    trigger replay, alpha = {a}: {k}/{len(p2)} = {k / len(p2):.4f}  "
          f"Wilson [{lo:.4f}, {hi:.4f}]  "
          f"{'ABOVE nominal' if lo > a else 'not above nominal'}")
    k5 = int((p2 < 0.05).sum())
    lo5, _ = wilson_ci(k5, len(p2))
    A(f"  prediction >= 0.95 at alpha = 0.05: observed {k5 / len(p2):.4f}, lower end "
      f"{lo5:.4f} — {'CONSISTENT' if lo5 >= 0.95 else 'NOT confirmed at the lower end'}")
    A("")
    A("  Amendment 4 item (3): the class side is an EXACTNESS claim, not an estimate.")
    A("  Registered: U2's declared-class p-value IS the class-maximum p-value; its")
    A("  rate is 6.1 arm D's, already established as exactly calibrated. This")
    A("  experiment does not re-estimate it.")
    A("    Equal on every draw: confirmed — a peek inside a harness-fixed class is")
    A("      already paid for.")
    A("    Any draw where they differ: a DEFECT; the reading halts.")
    cls_max = [r["_draw"]["class_max"] for r in rows if "U2" in r]
    sub2 = _col(rows, "U2", "submitted_score")
    off = sum(1 for a_, b_ in zip(sub2, cls_max) if abs(a_ - b_) > 1e-12)
    A(f"  U2's submission against the observed class maximum: differ on {off} of "
      f"{len(sub2)} draws")
    pc2 = np.asarray(_col(rows, "U2", "p_class"), dtype=float)
    for a in ALPHAS:
        k = int((pc2 < a).sum())
        lo, hi = wilson_ci(k, len(pc2))
        A(f"    declared class, alpha = {a}: {k}/{len(pc2)} = {k / len(pc2):.4f}  "
          f"Wilson [{lo:.4f}, {hi:.4f}]")
    A(f"  VERDICT 4 (class side): {'DEFECT — reading halts' if off else 'HOLDS — U2 submits the class maximum on every draw'}")
    A("")

    # ------------------------------------------- U4's rule (amendment 1, item 6)
    A("U4's RULE (amendment 1, item 6) — the hidden restart, paired one-sided")
    A("-" * 78)
    A("  Registered: U4 against its DECLARED-RESTART TWIN, paired on the draw,")
    A("  one-sided. The twin restarts through the `restart` move; U4 reaches the")
    A("  same states through `swap_worst` chains. Predicted: ZERO EXCESS — the")
    A("  replay re-executes the logged content moves either way.")
    A("    No excess: structure hidden in content moves is not a hole.")
    A("    Excess demonstrated (LOWER end of the paired interval above zero): a")
    A("      search can lower its own bar by not declaring its structure, which is")
    A("      a finding about the grammar and is reported as one.")
    pu = np.asarray(_col(rows, "U4", "p_replay"), dtype=float)
    pt = np.asarray(_col(rows, "U4-twin", "p_replay"), dtype=float)
    n4 = min(len(pu), len(pt))
    pu, pt = pu[:n4], pt[:n4]
    excess = False
    for a in ALPHAS:
        ru, rt = pu < a, pt < a
        diff = ru.astype(float) - rt.astype(float)
        m = float(diff.mean())
        se = float(diff.std(ddof=1)) / np.sqrt(n4)
        lo, hi = m - 1.96 * se, m + 1.96 * se
        excess = excess or lo > 0
        A(f"    alpha = {a}: U4 {int(ru.sum())}/{n4} = {ru.mean():.4f}   "
          f"twin {int(rt.sum())}/{n4} = {rt.mean():.4f}")
        A(f"      paired difference (U4 - twin) {m:+.4f}   95% [{lo:+.4f}, {hi:+.4f}]"
          f"   discordant: U4-only {int((ru & ~rt).sum())}, "
          f"twin-only {int((~ru & rt).sum())}")
    A(f"  VERDICT U4: {'EXCESS DEMONSTRATED — a finding about the grammar' if excess else 'NO EXCESS — structure hidden in content moves is not a hole'}")
    A("")

    # ----------------------------------------------------------------- rule 5
    A("RULE 5 — the bracket does its job (descriptive)")
    A("-" * 78)
    A("  Registered (amendment 1, item 3), verbatim: 'A binding change is always")
    A("  bracketed. For U3: the share of runs returning DEPENDS_ON_JUDGMENT,")
    A("  predicted 1.00. For U3b: the share returning CERTIFIED or FAIL, predicted")
    A("  to match the faithful arm.'")
    A("    A run that certifies despite a BINDING change is a defect, and the")
    A("      reading halts. THAT IS THE ONLY BRANCH THAT HALTS HERE.")
    A("  A change BINDS when it altered the search, which is what the commitment")
    A("  check measures — so a logged change alone is NOT the defect condition.")
    A("  U3b exists to log changes that never bind; it is predicted to certify.")
    defect5 = 0
    for name in ("U3", "U3b"):
        v = _col(rows, name, "gated_verdict")
        chg = _col(rows, name, "trigger_changes")
        ok = _col(rows, name, "commitment_ok")
        n = len(v)
        dj = sum(1 for x in v if x == "DEPENDS_ON_JUDGMENT")
        cf = sum(1 for x in v if x in ("CERTIFIED", "FAIL"))
        cert = sum(1 for x in v if x == "CERTIFIED")
        lo, hi = wilson_ci(dj, n)
        lo2, hi2 = wilson_ci(cf, n)
        # binding = the change altered the search, i.e. the commitment check failed
        bad = sum(1 for i in range(n)
                  if v[i] == "CERTIFIED" and chg[i] > 0 and not ok[i])
        defect5 += bad
        A(f"  {name:<4} DEPENDS_ON_JUDGMENT {dj}/{n} = {dj / n:.4f} "
          f"[{lo:.4f}, {hi:.4f}]   CERTIFIED-or-FAIL {cf}/{n} = {cf / n:.4f} "
          f"[{lo2:.4f}, {hi2:.4f}]   CERTIFIED {cert}/{n} = {cert / n:.4f}")
        A(f"       trigger changes per run: mean {np.mean(chg):.2f}, "
          f"min {min(chg)}, max {max(chg)};  changes that BOUND "
          f"(commitment failed): {sum(1 for i in range(n) if chg[i] > 0 and not ok[i])}")
        A(f"       certified despite a BINDING change: {bad}")
    fa = [sum(1 for x in _col(rows, f, "gated_verdict") if x == "CERTIFIED")
          / len(_col(rows, f, "gated_verdict")) for f in FAITHFUL]
    A(f"  the faithful arm's CERTIFIED rate, for U3b's comparison: "
      f"{fa[0]:.4f} ({FAITHFUL[0]}), {fa[1]:.4f} ({FAITHFUL[1]})")
    A(f"  VERDICT 5: {'DEFECT — reading halts' if defect5 else 'HOLDS — no run certifies despite a binding change'}")
    A("")

    # ----------------------------------------------------------------- rule 6
    A("RULE 6 — replication branch")
    A("-" * 78)
    A("  Registered: the first failure of any check in rules 1 or 3 triggers ONE")
    A("  replication of that check only, on 510000-511999, at identical settings.")
    A("  Amendment 1 removed rule 3 from this branch: an exactness check does not")
    A("  fail by luck, so replicating it would answer nothing.")
    need = rule1a_fail or bool(misfires)
    A(f"  rule 1 failed: {'YES' if need else 'no'}")
    A(f"  VERDICT 6: {'REPLICATION REQUIRED on 510000-511999' if need else 'not triggered'}")
    A("")

    # ------------------------------------------------- descriptive readouts
    A("DESCRIPTIVE READOUTS — no rule, no threshold, no branch")
    A("-" * 78)
    A("  Amendment 4 (4a): p_class - p_trigger per run")
    for name in ("U2", *FAITHFUL):
        d = np.asarray(_col(rows, name, "p_class_minus_p_replay"), dtype=float)
        A(f"    {name:<18} mean {d.mean():+.4f}  median {np.median(d):+.4f}  "
          f"[{d.min():+.4f}, {d.max():+.4f}]")
    A("  Amendment 4 (4b): submitted score - the fill's score on realized data")
    for name in ("U2", *FAITHFUL):
        d = np.asarray(_col(rows, name, "submitted_minus_fill"), dtype=float)
        A(f"    {name:<18} mean {d.mean():+.4f}  median {np.median(d):+.4f}")
    A("  Amendment 5: the submitted statistic against the same null.")
    A("  The faithful pair side by side, which is where the arm's gap lives:")
    for name in FAITHFUL:
        pp = np.asarray(_col(rows, name, "p_replay"), dtype=float)
        ps = np.asarray(_col(rows, name, "p_submitted"), dtype=float)
        ho = np.asarray(_col(rows, name, "handover_rate"), dtype=float)
        fe = np.asarray(_col(rows, name, "fill_engaged"), dtype=float)
        A(f"    {name:<18} PROCEDURE rate {(pp < 0.05).mean():.4f}   "
          f"SUBMITTED rate {(ps < 0.05).mean():.4f}   "
          f"hand-over {ho.mean():.4f}   fill engaged {fe.mean() / len(pp) * len(pp):.0f}")
    A("  Each policy:")
    for name in MEMBERS:
        ps = np.asarray(_col(rows, name, "p_submitted"), dtype=float)
        pp = np.asarray(_col(rows, name, "p_replay"), dtype=float)
        gap = np.asarray(_col(rows, name, "procedure_minus_submitted"), dtype=float)
        rule = all(_col(rows, name, "ended_under_its_rule"))
        A(f"    {name:<18} submitted-score rejection at 0.05 "
          f"{(ps < 0.05).mean():.4f} against procedure {(pp < 0.05).mean():.4f}"
          f"   procedure-minus-submitted mean {gap.mean():+.4f}"
          f"   ended under its rule on every run: {'yes' if rule else 'NO'}")
    A("  Amendment 6: the fill hand-over")
    bad6 = 0
    for name in MEMBERS:
        hr = np.asarray(_col(rows, name, "handover_rate"), dtype=float)
        ms = [x for x in _col(rows, name, "handover_step_mean") if x is not None]
        bad6 += sum(_col(rows, name, "replicates_ended_by_inapplicable_move"))
        A(f"    {name:<18} hand-over rate mean {hr.mean():.4f}   "
          f"mean step {(float(np.mean(ms)) if ms else float('nan')):.2f}")
    A(f"    replicates ended by an inapplicable move, all policies: {bad6}"
      f"  {'— INVARIANT BROKEN' if bad6 else '(the invariant amendment 6 registers)'}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="figures/unfaithful_searchers_s0_data.pkl")
    ap.add_argument("--out", default="figures/unfaithful_searchers_s0_read.txt")
    a = ap.parse_args(argv)
    with open(a.data, "rb") as fh:
        data = pickle.load(fh)
    text = read(data)
    print(text)
    Path(a.out).write_text(text)
    print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
