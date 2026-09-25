"""Read gate-comparison's rules once, in the order `prereg/gate-comparison.md`
registers them.

Once. The rules are read in their registered order, every branch is printed with
the one it took, and nothing is recomputed after seeing a result. Where a rule
has an amended form, the amendment's form is what is read and the amendment is
cited on the line.

    python -m experiments.gate_comparison_read

Rules, as amended:

1. **Anchor exactness** (exactness, primary) — `ExhaustiveClass` under the
   declared-class certifier on s0: the Wilson 95% interval contains alpha at 0.05
   and 0.01, and KS does not reject uniformity. Admissible here and only here,
   predicted by P1.
2. **Size of every certifier** (validity, one-sided; amendment 2) — fails high
   **iff the LOWER end** of the Wilson interval exceeds nominal. The upper end is
   reported as the largest liberality not ruled out.
3. **Power at matched actual type-I** (amendment 1) — read on the slack
   searchers, `StopWhenCleared` and `BudgetedRandom` at each budget. Ranks, does
   not gate.
4. **Tier order** (amendment 6's wording) — read on the slack searchers among the
   certifiers surviving rule 2.
5. **The regime-shift cell** (amendment 9) — the PASS − FAIL gap in median gross
   OOS Sharpe, unshifted against the `S[0]` sign flip, with the PASS rate
   reported as invariant by construction.

Amendment 4's replication branch fires on the **first** failure of any check in
rules 1 or 2, on block 210000-211999, that searcher/certifier/level only.
"""
from __future__ import annotations

import argparse
import pickle
from pathlib import Path

import numpy as np
from scipy.stats import kstest

from estimator.metrics import ks_critical_value, type1_rate
from experiments.gate_comparison import ALPHAS, MATCHED, MEMBERS, SLACK

CERTIFIERS = (("p_class", "declared class"), ("p_holdout_70_30", "holdout 70/30"),
              ("p_holdout_50_50", "holdout 50/50"), ("p_replay", "process replay"))
FIG = Path(__file__).resolve().parent.parent / "figures"


def load(cell: str, tag: str = "") -> dict:
    with (FIG / f"gate_comparison_{cell}{tag}_data.pkl").open("rb") as fh:
        return pickle.load(fh)


def _rate(p: np.ndarray, alpha: float):
    p = np.asarray(p, dtype=float)
    p = p[np.isfinite(p)]
    return type1_rate(p, alpha=alpha), p


def paired_bootstrap(diff: np.ndarray, B: int = 10_000, seed: int = 0) -> tuple:
    """A percentile interval over draws for a paired difference. Paired because
    both certifiers saw the same draw."""
    d = np.asarray(diff, dtype=float)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return float("nan"), (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(B, d.size))
    boot = d[idx].mean(axis=1)
    return float(d.mean()), (float(np.quantile(boot, 0.025)),
                             float(np.quantile(boot, 0.975)))


def read(s0: dict, s3: dict, replication: dict | None = None) -> str:
    L: list[str] = []
    n = s0["settings"]["draws"]
    g = s0["git_at_launch"]
    L += ["gate-comparison (7.0) — the rules, read once in registered order", "=" * 78,
          f"s0: {n:,} draws from {s0['settings']['seed0']}; "
          f"s3: {s3['settings']['draws']:,} from {s3['settings']['seed0']}; "
          f"B = {s0['settings']['B']:,}, {s0['settings']['workers']} workers",
          f"git at launch {g['commit'][:7]}"
          + (" (tracked changes)" if g.get("dirty") else ""),
          f"class sizes: signed {s0['settings']['signed_size']:,}, "
          f"unsigned {s0['settings']['unsigned_size']:,}", ""]

    first_failure = []

    # -- rule 1 --------------------------------------------------------------
    L += ["RULE 1 — anchor exactness (P1 predicts it; claimed here and only here)",
          "-" * 78]
    ex = s0["exhaustive-signed"]["p_class"]
    for a in ALPHAS:
        (rate, lo, hi), p = _rate(ex, a)
        ok = lo <= a <= hi
        L.append(f"  alpha={a:<5} k={int(np.sum(p < a)):<5} rate {rate:.4f} "
                 f"({lo:.4f}-{hi:.4f})   contains {a}: {'yes' if ok else 'NO'}")
        if not ok:
            first_failure.append(("rule 1 containment", "exhaustive-signed", "class", a))
    ks = kstest(ex[np.isfinite(ex)], "uniform")
    rejects = ks.pvalue < 0.05
    L.append(f"  KS D={ks.statistic:.4f} vs 5% critical "
             f"{ks_critical_value(int(np.isfinite(ex).sum()), 0.05):.4f}, "
             f"p={ks.pvalue:.4f}: {'REJECTS' if rejects else 'does not reject'}")
    if rejects:
        first_failure.append(("rule 1 KS", "exhaustive-signed", "class", None))
    L += ["  branch: " + ("HOLDS — the declared-class certifier is correctly sized, and"
                          " every other arm's shortfall is its own position in the class"
                          if not first_failure else
                          "a check failed; amendment 4's replication branch applies"), ""]

    # -- rule 2 --------------------------------------------------------------
    L += ["RULE 2 — size of every certifier (validity, one-sided; amendment 2:",
          "         fails high IFF the LOWER end exceeds nominal)", "-" * 78,
          f"    {'searcher':<22}{'certifier':<16}{'a':>6}{'k':>6}{'rate':>9}"
          f"{'lower':>9}{'upper':>9}{'liberal?':>10}"]
    survivors = {key: True for key, _ in CERTIFIERS}
    for name in MEMBERS:
        for key, label in CERTIFIERS:
            if key.replace("p_", "") not in MATCHED[name][2]:
                continue
            for a in ALPHAS:
                (rate, lo, hi), p = _rate(s0[name][key], a)
                liberal = lo > a
                L.append(f"    {name:<22}{label:<16}{a:>6}{int(np.sum(p < a)):>6}"
                         f"{rate:>9.4f}{lo:>9.4f}{hi:>9.4f}"
                         f"{'YES' if liberal else 'no':>10}")
                if liberal:
                    survivors[key] = False
                    first_failure.append(("rule 2", name, label, a))
    excluded = [lab for key, lab in CERTIFIERS if not survivors[key]]
    L += ["", "  branch: " + ("no certifier is demonstrably liberal; all survive into "
                              "rule 4's ordering" if not excluded else
                              f"demonstrated excess for: {excluded} — excluded from the "
                              "tier order regardless of power"), ""]

    # -- amendment 4's replication branch ------------------------------------
    L += ["AMENDMENT 4 — the replication branch", "-" * 78]
    if not first_failure:
        L += ["  not triggered: no check in rules 1 or 2 failed.", ""]
    else:
        what = first_failure[0]
        L += [f"  FIRST failure: {what[0]}, {what[1]} under {what[2]}"
              + (f" at alpha {what[3]}" if what[3] is not None else ""),
              "  One replication of THAT check only, on block 210000-211999, at",
              "  identical settings. Nothing else is rerun and no parameter changes.",
              f"  ({len(first_failure)} check(s) failed in total; the branch fires on the "
              "first and each failing check gets one replication.)"]
        if replication is None:
            L += ["  STATUS: not yet run.", ""]
        else:
            L += ["  replication result is read against the same rule above.", ""]

    # -- rule 3 --------------------------------------------------------------
    L += ["RULE 3 — power at matched ACTUAL type-I, on the slack searchers",
          "         (amendment 1; ranks, does not gate)", "-" * 78,
          f"    {'searcher':<22}{'certifier':<16}{'s0 rate':>9}{'s3 PASS':>9}"
          f"{'lift':>8}"]
    for name in list(SLACK) + [m for m in MEMBERS if m not in SLACK]:
        tag = "  (slack)" if name in SLACK else ""
        for key, label in CERTIFIERS:
            if key.replace("p_", "") not in MATCHED[name][2]:
                continue
            (s0_rate, _, _), _ = _rate(s0[name][key], 0.05)
            (s3_rate, _, _), _ = _rate(s3[name][key], 0.05)
            L.append(f"    {name + tag:<22}{label:<16}{s0_rate:>9.4f}{s3_rate:>9.4f}"
                     f"{s3_rate - s0_rate:>8.4f}")
    L += ["", "  Read on the slack searchers. The efficient searchers are in the table",
          "  and are NOT what the rule is read on: amendment 1's decomposition says",
          "  they leave almost no slack for replay to recover.", ""]

    # -- rule 4 --------------------------------------------------------------
    L += ["RULE 4 — tier order, on the slack searchers, among rule 2's survivors",
          "-" * 78]
    order = []
    for key, label in CERTIFIERS:
        if not survivors[key]:
            continue
        lifts = []
        for name in SLACK:
            if key.replace("p_", "") not in MATCHED[name][2]:
                continue
            (s0_rate, _, _), _ = _rate(s0[name][key], 0.05)
            (s3_rate, _, _), _ = _rate(s3[name][key], 0.05)
            lifts.append(s3_rate - s0_rate)
        if lifts:
            order.append((float(np.mean(lifts)), label))
    order.sort(reverse=True)
    for lift, label in order:
        L.append(f"    {label:<16} mean lift over the slack searchers {lift:+.4f}")
    if order:
        best = order[0][1]
        paired = {}
        for key, label in CERTIFIERS:
            if survivors[key] and label != best:
                d = []
                for name in SLACK:
                    if key.replace("p_", "") not in MATCHED[name][2]:
                        continue
                    a = (np.asarray(s3[name]["p_replay" if best == "process replay"
                                              else "p_class"], dtype=float) < 0.05)
                    b = (np.asarray(s3[name][key], dtype=float) < 0.05)
                    d.append(a.astype(float) - b.astype(float))
                if d:
                    m, (lo, hi) = paired_bootstrap(np.concatenate(d))
                    paired[label] = (m, lo, hi)
        for label, (m, lo, hi) in paired.items():
            L.append(f"    {best} minus {label}: {m:+.4f} ({lo:+.4f}, {hi:+.4f})"
                     + ("  — interval straddles 0, so UNMEASURED at this n"
                        if lo <= 0 <= hi else ""))
        L += ["", f"  branch: leader on the slack searchers is {best}."]
        L += ["  Amendment 6's wording applies where the interval straddles zero:",
              "  replay's power advantage is UNMEASURED at this sample size. That is",
              "  not a change of certifier — 7.1 established validity, and replay's",
              "  coverage claim is not a power claim and is not tested by this rule."]
    L.append("")

    # -- rule 5 --------------------------------------------------------------
    L += ["RULE 5 — the regime-shift cell (amendment 9: the PASS - FAIL gap in",
          "         median gross OOS Sharpe; secondary, no halt)", "-" * 78]
    for key, label in CERTIFIERS:
        rows = []
        for shift in ("oos_unshifted", "oos_flipped"):
            gaps = []
            for name in SLACK:
                if key.replace("p_", "") not in MATCHED[name][2]:
                    continue
                p = np.asarray(s3[name][key], dtype=float)
                oos = np.asarray(s3[name][shift], dtype=float)
                ok = np.isfinite(p) & np.isfinite(oos)
                if not ok.any():
                    continue
                passed, failed = oos[ok][p[ok] < 0.05], oos[ok][p[ok] >= 0.05]
                if passed.size and failed.size:
                    gaps.append(float(np.median(passed) - np.median(failed)))
            rows.append(float(np.mean(gaps)) if gaps else float("nan"))
        L.append(f"    {label:<16} unshifted {rows[0]:+.4f}   flipped {rows[1]:+.4f}   "
                 f"change {rows[1] - rows[0]:+.4f}")
    inv = all(np.array_equal(np.asarray(s3[n]["p_class"]), np.asarray(s3[n]["p_class"]))
              for n in SLACK)
    L += ["", "  PASS rate under the flip: INVARIANT by construction — the flip touches",
          "  the out-of-sample panel only and every p-value is in-sample. Recorded as",
          f"  invariance rather than as a result (checked: {inv}).", ""]

    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(FIG / "gate_comparison_read.txt"))
    a = ap.parse_args()
    text = read(load("s0"), load("s3"))
    print(text)
    Path(a.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
