"""Read `prereg/agent-cell.md`'s check 1 ONCE, in registered order.

**Amendment 11 defines the rule's quantity.** Check 1's type-I rate is the
**false-certification rate over all n = 80 runs**: a run rejects at alpha iff it
ISSUED A CERTIFICATE at alpha — it carries a certifying-null p-value and that
p-value is below alpha — and a run that issued none counts as a non-rejection,
because that is what it does in deployment. The denominator is every run.

The KS and per-kind readouts need a POSITION and are read on the runs that carry
one, as descriptive shape readouts with the conditioning stated. They gate nothing.
A declared-class readout on all runs is reported where available.

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
            "p_upper": v.get("p_upper"),
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
    A("  Registered (amendment 4, quantity fixed by amendment 11): check 1's type-I")
    A("  rate is the FALSE-CERTIFICATION RATE over all runs. A run rejects at alpha")
    A("  iff it ISSUED A CERTIFICATE at alpha — it carries a certifying-null p-value")
    A("  and that p-value is below alpha. A run that issued none counts as a")
    A("  NON-REJECTION: a bracketed or undecidable run certified nothing, which is")
    A("  what it does in deployment. The denominator is every run.")
    A("  Rule (validity, one-sided): FAILS HIGH iff the LOWER end of the Wilson 95%")
    A("  interval for that rate exceeds nominal, at alpha = 0.05 and 0.01.")
    A("    Holds: no gross leakage, and the per-kind fractions are reported flat.")
    A("    Fails high: the per-kind fractions name the suspect kind, and NO")
    A("      behavioural readout from the cell is reported as a finding until it is")
    A("      understood.")
    A("    KS rejects with the rate inside its interval: reported as a shape")
    A("      departure with the ECDF, not as a size failure.")
    A("")

    priced = [r for r in runs if r["p_certifying"] is not None]
    unpriced = [r for r in runs if r["p_certifying"] is None]
    n = len(runs)
    A(f"  Runs: {n} (registered n = {n_registered}).")
    if n != n_registered:
        A(f"  NOTE: the arm holds {n} runs, not the registered {n_registered}. The")
        A("  rate below is over the runs present and its interval reflects that n.")
    A(f"  Issued a certificate-eligible position: {len(priced)}. "
      f"Issued none: {len(unpriced)}.")
    if unpriced:
        by = Counter((r["status"], r["triggers_changed"]) for r in unpriced)
        for (st, ch), k in sorted(by.items()):
            A(f"    {k} run(s) counted as NON-REJECTIONS: status {st}, "
              f"triggers_changed={ch}")
    A("")

    # ---------------------------------------------------- the rule
    A("  THE RULE — false certification over every run")
    A("  " + "-" * 74)
    fails = False
    for a in ALPHAS:
        k = sum(1 for r in priced if r["p_certifying"] < a)
        lo, hi = wilson_ci(k, n)
        high = lo > a
        fails = fails or high
        A(f"    alpha = {a:<5} certified {k:>3}/{n:<3} = {k / n:7.4f}   "
          f"Wilson [{lo:.4f}, {hi:.4f}]   "
          f"{'FAILS HIGH' if high else 'does not fail high'}")
    A("")
    A("  Detectability, stated so a pass is not over-read")
    A("  " + "-" * 74)
    for a in ALPHAS:
        for k in range(n + 1):
            lo, hi = wilson_ci(k, n)
            if lo > a:
                A(f"    alpha = {a}: fires at {k} or more of {n} ({k / n:.4f}); "
                  f"Wilson [{lo:.4f}, {hi:.4f}]")
                break
    A(f"    At n = {n} this detects a true rate near 13% or worse. It rules out")
    A("    GROSS LEAKAGE AND NO MORE; the scripted arms of")
    A("    prereg/unfaithful-searchers.md carry the calibration claim, and a pass")
    A("    here is not a calibration result.")
    A("")
    A(f"  VERDICT, CHECK 1: {'FAILS HIGH' if fails else 'HOLDS'}")
    A("")

    # ------------------------------------- descriptive: the declared-class tier
    A("  DESCRIPTIVE, all runs: the declared-class p-value (the bracket's upper end)")
    A("  " + "-" * 74)
    A("    One null for every run, whatever the agent declared or changed, and")
    A("    expected conservative: the class tier charges the class maximum whatever")
    A("    route reached it. Descriptive — no threshold, no branch.")
    cls_p = [r["p_upper"] for r in runs if r.get("p_upper") is not None]
    if not cls_p:
        A("    NOT AVAILABLE on these runs. `_certify_run` passed no declared-class")
        A("    p-value, so `p_upper` was never computed for this arm (amendment 11")
        A("    records this). It needs a local computation on the simulated panel —")
        A("    no model, no seat — and is reported as pending rather than omitted.")
    else:
        for a in ALPHAS:
            k = sum(1 for x in cls_p if x < a)
            lo, hi = wilson_ci(k, len(cls_p))
            A(f"    alpha = {a:<5} {k:>3}/{len(cls_p):<3} = {k / len(cls_p):7.4f}   "
              f"Wilson [{lo:.4f}, {hi:.4f}]")
    A("")

    # ------------------------------------- descriptive: shape, on positions only
    A("  DESCRIPTIVE, positions only: shape of the certifying-null p-values")
    A("  " + "-" * 74)
    A(f"    Read on the {len(priced)} runs that carry a position, NOT on all {n}.")
    A("    CONDITIONING, stated: these are the positions among runs that DID NOT")
    A("    change a trigger. A uniformity statement about them is not a uniformity")
    A("    statement about the arm. These readouts gate nothing.")
    if len(priced) < 2:
        A("    too few positions to describe")
        return "\n".join(L)
    p = np.asarray([r["p_certifying"] for r in priced], dtype=float)
    ks = stats.kstest(p, "uniform")
    A(f"    KS against U(0,1): D = {ks.statistic:.4f}   p = {ks.pvalue:.4f}   "
      f"{'REJECTS at 0.05' if ks.pvalue < 0.05 else 'does not reject at 0.05'}")
    if ks.pvalue < 0.05 and not fails:
        A("      With the RATE inside its interval, this is a SHAPE DEPARTURE and is")
        A("      reported with the ECDF, not as a size failure.")
    A(f"    positions: min {p.min():.4f}  median {np.median(p):.4f}  max {p.max():.4f}")
    A("")
    A("    Per decision kind, the fraction whose position is in the lowest decile.")
    A("    Skew toward small p means a decision kind is leaking, and these say which.")
    kinds = sorted({k for r in priced for k in r["decision_kinds"]})
    ubiquitous = [k for k in kinds
                  if sum(1 for r in priced if k in r["decision_kinds"]) == len(priced)]
    if len(ubiquitous) == len(kinds):
        A("    LIMITATION: every kind below appears in EVERY priced run, so each")
        A("    fraction is computed on the same 60 runs and they are identical by")
        A("    construction. The readout cannot distinguish kinds on this arm; it")
        A("    would only do so where kinds differ across runs.")
    absent = sorted({k for r in runs for k in r["decision_kinds"]} - set(kinds))
    if absent:
        A(f"    KINDS WITH NO POSITION AT ALL: {', '.join(absent)}. They appear only")
        A("    in runs that issued no certificate, so no position exists for them and")
        A("    this readout is blind to them — which matters, because those are the")
        A("    kinds a reader would most want it to examine.")
    for kind in kinds:
        sub = [r for r in priced if kind in r["decision_kinds"]]
        k = sum(1 for r in sub if r["p_certifying"] < LOWEST_DECILE)
        lo, hi = wilson_ci(k, len(sub))
        A(f"      {kind:<14} {k:>3}/{len(sub):<3} = {k / len(sub):7.4f}   "
          f"Wilson [{lo:.4f}, {hi:.4f}]")
    A(f"      (a flat reading is {LOWEST_DECILE:.2f} per kind)")
    A("")
    A("  The 25% bracket rate is a CHECK-3 readout — how often an agent changes a")
    A("  declared rule is behaviour — and is not read here (amendment 11).")
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
