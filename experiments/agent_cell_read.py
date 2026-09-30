"""Read `prereg/agent-cell.md`'s check 1 ONCE, in registered order.

Check 1, as registered (amendment 4):

    Each s0 run's submitted Sharpe is placed within its own replay null: the
    position is the certifying null's p-value for that run. If the gate reproduces
    what the agent does on noise, those positions are uniform.

    Readouts: KS against U(0,1), and the type-I rate at alpha = 0.05 and 0.01.
    Per decision kind, the fraction of runs whose p-value falls in the lowest
    decile.

    Rule (validity, one-sided): fails high iff the LOWER end of the Wilson 95%
    interval for the type-I rate exceeds nominal.

    At n = 80 this detects a true rate near 13% or worse.

**The registered n is part of the rule, so this reader enforces it.** A run whose
verdict carries no certifying-null p-value has no position to place, and a reading
taken over whatever subset happens to be priced is not the registered check. So the
reader REFUSES when the priced set is smaller than the registered n, and names what
is missing and why — rather than silently reading a different quantity under check
1's name. `gate_comparison_read.py` is the precedent: a rule read at other than its
registered form had to be superseded.
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
N_REGISTERED = 80
LOWEST_DECILE = 0.10


def load_runs(directory: str) -> list[dict]:
    """One dict per run file, in run-index order."""
    d = Path(directory)
    out = []
    for f in sorted(d.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2])):
        x = json.loads(f.read_text())
        v = x.get("verdict") or {}
        log = [e for e in x["events"] if e.get("kind") == "session_log"]
        out.append({
            "index": int(f.name.split("_")[2]),
            "run_id": x.get("run_id"),
            "p_certifying": v.get("p_certifying"),
            "status": v.get("status"),
            "B": v.get("B"),
            "triggers_changed": bool(x.get("triggers_changed")),
            "decision_kinds": sorted({r["kind"] for r in log[0]["records"]})
                              if log else [],
        })
    return out


def read_check1(runs: list[dict], n_registered: int = N_REGISTERED) -> str:
    L: list[str] = []
    A = L.append
    A("prereg/agent-cell.md, CHECK 1 — CALIBRATION")
    A("=" * 78)
    A("  Registered: each s0 run's submitted Sharpe is placed within its own replay")
    A("  null; the position is the certifying null's p-value for that run. If the")
    A("  gate reproduces what the agent does on noise, those positions are uniform.")
    A("  Rule (validity, one-sided): FAILS HIGH iff the LOWER end of the Wilson 95%")
    A("  interval for the type-I rate exceeds nominal, at alpha = 0.05 and 0.01.")
    A("    Holds: no gross leakage, and the per-kind fractions are reported flat.")
    A("    Fails high: the per-kind fractions name the suspect kind, and NO")
    A("      behavioural readout from the cell is reported as a finding until it is")
    A("      understood.")
    A("    KS rejects with the rate inside its interval: reported as a shape")
    A("      departure with the ECDF, not as a size failure.")
    A("")
    A(f"  Registered n: {n_registered}. Runs found: {len(runs)}.")

    priced = [r for r in runs if r["p_certifying"] is not None]
    unpriced = [r for r in runs if r["p_certifying"] is None]
    A(f"  Runs carrying a certifying-null p-value: {len(priced)}.")

    if len(priced) < n_registered:
        A("")
        A("  REFUSED — THE REGISTERED n IS NOT AVAILABLE, AND THE SHORTFALL IS NOT")
        A("  RANDOM.")
        A("")
        A(f"  {len(unpriced)} of {len(runs)} runs carry no certifying-null p-value, so")
        A("  they have no position to place. `quixote/certify.py` does not price the")
        A("  certifying null on a run with a logged trigger change: the pre-change")
        A("  rule is what replays, so the search after the change is a decision the")
        A("  null cannot price, and the verdict is DEPENDS_ON_JUDGMENT with the")
        A("  fixed-sequence null reported as the bracket's liberal end instead.")
        by = Counter((r["status"], r["triggers_changed"]) for r in unpriced)
        for (st, ch), n in sorted(by.items()):
            A(f"    {n} run(s): status {st}, triggers_changed={ch}")
        A(f"    indices: {[r['index'] for r in unpriced]}")
        A("")
        A("  WHY THIS IS NOT A MATTER OF READING AT A SMALLER n. The missing runs are")
        A("  exactly the runs in which the AGENT CHANGED A RULE. Reading the")
        A("  remaining ones conditions the uniformity check on agent behaviour — on")
        A("  'runs that did not change a trigger' — which is not the population")
        A("  check 1 registered, and the direction of any resulting bias is not")
        A("  known. The detectability statement registered with the check ('at")
        A(f"  n = {n_registered} this detects a true rate near 13% or worse') does not")
        A("  hold at a smaller n either.")
        A("")
        A("  NOTHING IS READ. Check 1 remains unread, and a decision is needed before")
        A("  it can be: read at the reduced n with the exclusion recorded as a")
        A("  deviation and the conditioning stated; or register how a bracketed run's")
        A("  position is to be defined; or record check 1 as unreadable on this arm.")
        return "\n".join(L)

    p = np.asarray([r["p_certifying"] for r in priced], dtype=float)
    A("")
    A("  KS against U(0,1)")
    A("  " + "-" * 74)
    ks = stats.kstest(p, "uniform")
    A(f"    D = {ks.statistic:.4f}   p = {ks.pvalue:.4f}   "
      f"{'REJECTS at 0.05' if ks.pvalue < 0.05 else 'does not reject at 0.05'}")
    A("")
    A("  Type-I rate, one-sided: fails high iff the LOWER Wilson end exceeds nominal")
    A("  " + "-" * 74)
    fails = False
    for a in ALPHAS:
        k = int((p < a).sum())
        lo, hi = wilson_ci(k, len(p))
        high = lo > a
        fails = fails or high
        A(f"    alpha = {a:<5} {k:>3}/{len(p):<3} = {k / len(p):7.4f}   "
          f"Wilson [{lo:.4f}, {hi:.4f}]   "
          f"{'FAILS HIGH' if high else 'does not fail high'}")
    A("")
    A("  Per decision kind: fraction of runs whose p falls in the lowest decile")
    A("  " + "-" * 74)
    A("    Skew toward small p means a decision kind is leaking, and these say which.")
    kinds = sorted({k for r in priced for k in r["decision_kinds"]})
    for kind in kinds:
        sub = [r for r in priced if kind in r["decision_kinds"]]
        k = sum(1 for r in sub if r["p_certifying"] < LOWEST_DECILE)
        lo, hi = wilson_ci(k, len(sub))
        A(f"    {kind:<14} {k:>3}/{len(sub):<3} = {k / len(sub):7.4f}   "
          f"Wilson [{lo:.4f}, {hi:.4f}]")
    A(f"    (a flat reading is {LOWEST_DECILE:.2f} per kind)")
    A("")
    A("  Detectability at the registered n, stated so a pass is not over-read")
    A("  " + "-" * 74)
    for a in ALPHAS:
        for k in range(len(p) + 1):
            lo, _ = wilson_ci(k, len(p))
            if lo > a:
                A(f"    alpha = {a}: the rule fires at {k} or more of {len(p)} "
                  f"({k / len(p):.4f}); Wilson [{lo:.4f}, {wilson_ci(k, len(p))[1]:.4f}]")
                break
    A(f"    At n = {len(p)} this detects a true rate near 13% or worse. It rules out")
    A("    GROSS LEAKAGE AND NO MORE; the scripted arms of")
    A("    prereg/unfaithful-searchers.md carry the calibration claim, and a pass")
    A("    here is not a calibration result.")
    A("")
    A(f"  VERDICT, CHECK 1: {'FAILS HIGH' if fails else 'HOLDS'}")
    if not fails and ks.pvalue < 0.05:
        A("    with a KS rejection and the rate inside its interval: reported as a")
        A("    SHAPE DEPARTURE with the ECDF, not as a size failure.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--n-registered", type=int, default=N_REGISTERED)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text = read_check1(load_runs(a.dir), a.n_registered)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
        print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
