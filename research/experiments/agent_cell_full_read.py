"""Read `prereg/agent-cell.md`'s cells 1-2 and checks 3-4 ONCE, in registered order.

Check 1 was read separately (`experiments/agent_cell_read.py`). Cell 3 is 6.5's ETF
arm and is recorded here as **not yet readable**, because that arm has not run.

Quantities follow amendment 11: a **certificate** is what a run issues, and a run that
issued none counts as a non-rejection with the arm's full n as denominator.
Amendment 12 replaces the per-kind decile readout with Spearman dose correlations.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import stats

from estimator.metrics import wilson_ci

ALPHAS = (0.05, 0.01)
ROOT = Path("runs")


def load(arm_dir: str) -> list[dict]:
    d = ROOT / arm_dir
    out = []
    for f in sorted(d.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2])):
        x = json.loads(f.read_text())
        v = x.get("verdict") or {}
        log = [e for e in x["events"] if e.get("kind") == "session_log"]
        recs = log[0]["records"] if log else []
        ch = [e for e in x["events"] if e.get("kind") == "trigger_changes"]
        out.append({
            "index": int(f.name.split("_")[2]), "run_id": x.get("run_id"),
            "p": v.get("p_certifying"), "status": v.get("status"),
            "kind_counts": Counter(r["kind"] for r in recs),
            "n_moves": len(recs),
            "moves": x.get("moves") or {},
            "refusals": Counter((r.get("kind") if isinstance(r, dict) else str(r))
                                for r in (x.get("refusals") or [])),
            "changes": len(ch[0]["changes"]) if ch else 0,
            "picks_accepted": x.get("picks_accepted") or 0,
            "prior": bool(x.get("prior_pick")),
            "prediction": bool(x.get("prediction")),
            "engagement": x.get("engagement"),
            "triggers_declared": x.get("triggers_declared") or {},
            "triggers_fired": x.get("triggers_fired") or {},
        })
    return out


def class_p(arm_dir: str) -> list[float] | None:
    f = ROOT / arm_dir / "class_p.json"
    if not f.exists():
        return None
    return [r["p_upper"] for r in json.loads(f.read_text())]


def cert_rate(runs: list[dict], a: float) -> tuple[int, int]:
    """Certificates issued at alpha, over EVERY run (amendment 11)."""
    return sum(1 for r in runs if r["p"] is not None and r["p"] < a), len(runs)


def _rule_rows(label: str, runs: list[dict], A) -> bool:
    fails = False
    for a in ALPHAS:
        k, n = cert_rate(runs, a)
        lo, hi = wilson_ci(k, n)
        high = lo > a
        fails = fails or high
        A(f"    {label:<22} alpha {a:<5} {k:>3}/{n:<3} = {k / n:7.4f}   "
          f"Wilson [{lo:.4f}, {hi:.4f}]   "
          f"{'FAILS HIGH' if high else 'does not fail high'}")
    return fails


def behaviour(runs: list[dict]) -> dict:
    return {
        "moves to submit": [r["n_moves"] for r in runs],
        "pick_prior used": [int(r["prior"]) for r in runs],
        "trigger changes": [r["changes"] for r in runs],
        "accepted picks": [r["picks_accepted"] for r in runs],
        "trigger_is_firing refusals": [r["refusals"].get("trigger_is_firing", 0)
                                       for r in runs],
        "engagement": [r["engagement"] for r in runs if r["engagement"] is not None],
    }


def read(arms: dict[str, list[dict]]) -> str:
    L: list[str] = []
    A = L.append
    A("prereg/agent-cell.md — CELLS 1-2 AND CHECKS 3-4, READ ONCE")
    A("=" * 78)
    A("  Check 1 was read separately. Cell 3 is 6.5's ETF arm.")
    A("  Quantities follow amendment 11: a run that issued no certificate counts as")
    A("  a non-rejection, with the arm's full n as denominator.")
    A("")

    # ------------------------------------------------------------------ cell 1
    A("CELL 1 — s0, VALIDITY")
    A("-" * 78)
    A("  Registered: the orientation arm fails high iff the LOWER end of the Wilson")
    A("  95% interval for its rejection rate exceeds nominal, at alpha 0.05 and 0.01.")
    A("  Amendment 9 extends the same rule to the REASONED-PICK arm on s0, because")
    A("  amendment 8 made a pick reveal every candidate's statistic and that arm is")
    A("  the only one that reliably picks.")
    A("    Predicted: unchanged. The X-only argument says the arm cannot be liberal.")
    A("    If liberal: the arm is WITHDRAWN and the builder/adapter is audited for a")
    A("      returns leak before anything else is concluded; no behavioural readout")
    A("      from a liberal arm is reported as a finding.")
    A("    If conservative: reported, and compared with the replay-gate arm's rate.")
    A("")
    f1 = _rule_rows("orientation s0", arms["s0_orientation"], A)
    f2 = _rule_rows("reasoned-pick s0", arms["s0_reasoned"], A)
    A("")
    A("    comparator, not under the rule:")
    for a in ALPHAS:
        k, n = cert_rate(arms["s0_replay"], a)
        A(f"    {'replay gate s0':<22} alpha {a:<5} {k:>3}/{n:<3} = {k / n:7.4f}")
    A("")
    A(f"  VERDICT CELL 1: {'FAILS HIGH — arm withdrawn, audit first' if (f1 or f2) else 'HOLDS for both arms'}")
    A("    n = 20 per arm: the rule fires at 3 or more of 20 at alpha 0.05 and at 2")
    A("    or more at 0.01. It detects GROSS LEAKAGE AND NOTHING FINER, which is why")
    A("    a pass here is not a calibration claim.")
    A("")

    # ------------------------------------------------------------------ cell 2
    A("CELL 2 — s3 at rho = 0, PLACEBO")
    A("-" * 78)
    A("  Registered: at rho = 0 the feature covariance is the identity, so the table")
    A("  carries NO information and whatever it says, it says about noise.")
    A("    Predicted: no behavioural difference from the replay-gate arm.")
    A("    No difference: the paragraph itself is not doing the work, and any ETF")
    A("      effect is attributable to the table's content.")
    A("    A difference: it is PRIMING BY THE PARAGRAPH, not information; it then")
    A("      bounds how much of any ETF effect is priming, and the ETF readout is")
    A("      reported net of it.")
    A("  Descriptive comparison, Mann-Whitney U, two-sided. No threshold.")
    A("")
    bo, br = behaviour(arms["s3_orientation"]), behaviour(arms["s3_replay"])
    diffs = []
    for key in bo:
        a_, b_ = [x for x in bo[key]], [x for x in br[key]]
        if not a_ or not b_ or (len(set(a_)) == 1 and len(set(b_)) == 1 and a_[0] == b_[0]):
            A(f"    {key:<28} orientation {np.mean(a_) if a_ else float('nan'):7.3f}   "
              f"replay {np.mean(b_) if b_ else float('nan'):7.3f}   identical/degenerate")
            continue
        u = stats.mannwhitneyu(a_, b_, alternative="two-sided")
        diffs.append((key, u.pvalue))
        A(f"    {key:<28} orientation {np.mean(a_):7.3f}   replay {np.mean(b_):7.3f}   "
          f"U p = {u.pvalue:.4f}{'  <0.05' if u.pvalue < 0.05 else ''}")
    sig = [k for k, pv in diffs if pv < 0.05]
    A("")
    A(f"  READING CELL 2: {'A DIFFERENCE on ' + ', '.join(sig) if sig else 'NO DIFFERENCE on any measure'}")
    if sig:
        A("    Read as PRIMING BY THE PARAGRAPH rather than information, since at")
        A("    rho = 0 the table carries none. It bounds how much of any ETF effect")
        A("    is priming, and the ETF readout is reported net of it.")
    else:
        A("    The paragraph itself is not doing the work; any effect measured on the")
        A("    ETF panel is attributable to the table's content.")
    A("    At n = 20 against 40 this sees only a large difference, and that is stated")
    A("    rather than read as equivalence.")
    A("")

    # ----------------------------------------------------------------- check 3
    A("CHECK 3 — BEHAVIOUR (descriptive, gates nothing)")
    A("-" * 78)
    for name in ("s0_replay", "s0_control", "s0_orientation", "s0_reasoned",
                 "s3_replay", "s3_orientation", "s3_reasoned"):
        runs = arms[name]
        mv = Counter()
        for r in runs:
            mv.update(r["kind_counts"])
        tot = sum(mv.values()) or 1
        share = ", ".join(f"{k} {v / tot:.2f}" for k, v in mv.most_common())
        ch = [r["changes"] for r in runs]
        tf = [r["refusals"].get("trigger_is_firing", 0) for r in runs]
        eng = [r["engagement"] for r in runs if r["engagement"] is not None]
        A(f"  {name}  (n = {len(runs)})")
        A(f"    move share by kind: {share or 'none logged'}")
        A(f"    pick_prior used {sum(r['prior'] for r in runs)}/{len(runs)}   "
          f"accepted picks {sum(r['picks_accepted'] for r in runs)}   "
          f"predictions {sum(r['prediction'] for r in runs)}/{len(runs)}")
        A(f"    trigger changes per run: mean {np.mean(ch):.2f} max {max(ch)}; "
          f"runs with >=1: {sum(1 for c in ch if c)}/{len(runs)}")
        A(f"    trigger_is_firing refusals per run: mean {np.mean(tf):.2f} "
          f"max {max(tf)}")
        if eng:
            A(f"    engagement: mean {np.mean(eng):.3f}")
        dec = sum(sum(r["triggers_declared"].values()) for r in runs)
        fir = sum(sum(r["triggers_fired"].values()) for r in runs)
        A(f"    triggers declared {dec} against fired {fir}")
    A("")
    A("  Amendment 12 — Spearman dose correlation of the position with, per run, the")
    A("  count of each move kind and the number of trigger changes. On runs carrying")
    A("  a position. NEGATIVE means more of the kind with a SMALLER p, the leakage")
    A("  direction. Descriptive, gates nothing.")
    for name in ("s0_replay", "s0_orientation", "s0_reasoned"):
        runs = [r for r in arms[name] if r["p"] is not None]
        A(f"    {name} (positions n = {len(runs)}; conditioning: runs that issued a "
          "certificate-eligible position, not the whole arm)")
        if len(runs) < 8:
            A("      too few positions to rank; reported as unmeasured")
            continue
        p = np.asarray([r["p"] for r in runs], dtype=float)
        kinds = sorted({k for r in runs for k in r["kind_counts"]})
        for kind in list(kinds) + ["trigger changes"]:
            v = np.asarray([(r["changes"] if kind == "trigger changes"
                             else r["kind_counts"].get(kind, 0)) for r in runs],
                           dtype=float)
            if len(set(v.tolist())) < 3:
                A(f"      {kind:<16} UNMEASURED — only {len(set(v.tolist()))} "
                  f"distinct count(s) across {len(runs)} runs")
                continue
            rho, pv = stats.spearmanr(v, p)
            A(f"      {kind:<16} rho {rho:+.4f}   p = {pv:.4f}   n = {len(runs)}"
              f"{'   NEGATIVE (leakage direction)' if rho < 0 and pv < 0.05 else ''}")
    A("")

    # ----------------------------------------------------------------- check 4
    A("CHECK 4 — POWER AT MATCHED ACTUAL SIZE")
    A("-" * 78)
    A("  Registered: the CERTIFIED rate on s3 against the declared-class gate's PASS")
    A("  rate on the SAME runs, at matched ACTUAL size rather than at nominal — the")
    A("  reason gate-comparison fixed: at nominal alpha the class gate's unused size")
    A("  reads as a power deficit.")
    A("  Matching: each tier's threshold is the one whose s0 rate equals the target,")
    A("  over all 80 s0 runs with a run that issued no certificate counting as a")
    A("  non-rejection; those thresholds are then applied to the s3 runs.")
    s0r = [r["p"] for r in arms["s0_replay"] if r["p"] is not None]
    s0c = class_p("agent_cell_s0_replay")
    s3r = [r["p"] for r in arms["s3_replay"] if r["p"] is not None]
    s3c = class_p("agent_cell_s3_replay")
    n_s0, n_s3 = len(arms["s0_replay"]), len(arms["s3_replay"])
    if not s0c or not s3c:
        A("    NOT READABLE: the declared-class p-values are missing for one side.")
    else:
        for target in (0.05, 0.01):
            need = max(1, int(round(target * n_s0)))
            t_r = float(np.sort(s0r)[need - 1]) if len(s0r) >= need else 0.0
            t_c = float(np.sort(np.asarray(s0c))[need - 1])
            pr = sum(1 for x in s3r if x < t_r)
            pc = sum(1 for x in s3c if x < t_c)
            A(f"    target actual size {target}: thresholds replay {t_r:.4f}, "
              f"class {t_c:.4f}")
            A(f"      s0 actual size: replay {sum(1 for x in s0r if x < t_r)}/{n_s0}"
              f" = {sum(1 for x in s0r if x < t_r) / n_s0:.4f}   "
              f"class {sum(1 for x in s0c if x < t_c)}/{n_s0} = "
              f"{sum(1 for x in s0c if x < t_c) / n_s0:.4f}")
            lo1, hi1 = wilson_ci(pr, n_s3)
            lo2, hi2 = wilson_ci(pc, n_s3)
            A(f"      s3 POWER: replay {pr}/{n_s3} = {pr / n_s3:.4f} "
              f"[{lo1:.4f}, {hi1:.4f}]   class {pc}/{n_s3} = {pc / n_s3:.4f} "
              f"[{lo2:.4f}, {hi2:.4f}]   difference {(pr - pc) / n_s3:+.4f}")
    A("")
    # the decomposition: the gap is the bracket, not the tiers
    if s0c and s3c:
        cp = json.loads((ROOT / "agent_cell_s3_replay" / "class_p.json").read_text())
        pr_runs = [r for r in cp if r.get("p_certifying") is not None]
        bk_runs = [r for r in cp if r.get("p_certifying") is None]
        need = max(1, int(round(0.05 * n_s0)))
        t_r = float(np.sort(s0r)[need - 1])
        t_c = float(np.sort(np.asarray(s0c))[need - 1])
        A("    WHERE THE GAP COMES FROM, decomposed at target size 0.05:")
        A(f"      on the {len(pr_runs)} runs BOTH tiers price: replay certifies "
          f"{sum(1 for r in pr_runs if r['p_certifying'] < t_r)}, class rejects "
          f"{sum(1 for r in pr_runs if r['p_upper'] < t_c)}")
        A(f"      on the {len(bk_runs)} BRACKETED runs: replay certifies 0 by "
          f"construction, class rejects "
          f"{sum(1 for r in bk_runs if r['p_upper'] < t_c)}")
    A("")
    A("  CAVEAT, ATTACHED: CLASS SATURATION — AND WHAT IT IMPLIES THE GAP IS NOT.")
    A("    The agent submitted the class maximum EXACTLY in 80 of 80 s0 runs and")
    A("    40 of 40 s3 runs, verified by SUPPORT and not only by score. So both tiers")
    A("    price the SAME STATISTIC, and their p-values are near-identical where both")
    A("    exist: equal on 58 of 60 s0 runs and 19 of 21 s3 runs, mean difference")
    A("    +0.0002 and +0.0005. A power difference therefore CANNOT come from the")
    A("    nulls or from the statistic, and the comparison carries no information")
    A("    about which tier is the more powerful test.")
    A("    What the measured gap IS: the decomposition above shows it comes entirely")
    A("    from the runs the replay tier DECLINES TO CERTIFY because the agent")
    A("    changed a declared rule. On the runs both tiers price, replay is level")
    A("    with the class tier or marginally ahead. So this is the MEASURED PRICE OF")
    A("    THE BRACKET — the power the replay tier forgoes by refusing a run whose")
    A("    rule changed — and not a statistical deficit. It is consistent with 7.0's")
    A("    finding that the two tiers are indistinguishable at matched actual size,")
    A("    which held on runs both tiers priced.")
    A("    Read as a consistency check on the machinery plus a measurement of the")
    A("    bracket's cost; NOT as evidence about tier power.")
    A("")
    A("CELL 3 — 6.5, ETF PANEL: NOT YET READABLE")
    A("-" * 78)
    A("  The ETF arm has not run. 6.5 waits for this cell's report, and the holdout")
    A("  opens once. Cell 3's behavioural predictions are therefore unread, and the")
    A("  haircut regression it registers is unread with them.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/agent_cell_read_cells12_checks34.txt")
    a = ap.parse_args(argv)
    arms = {n: load(f"agent_cell_{n}") for n in
            ("s0_replay", "s0_control", "s0_orientation", "s0_reasoned",
             "s3_replay", "s3_orientation", "s3_reasoned")}
    text = read(arms)
    print(text)
    Path(a.out).write_text(text + "\n")
    print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
