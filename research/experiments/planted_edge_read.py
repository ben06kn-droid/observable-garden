"""Read 7.5 stage 1, the scripted curve, ONCE, in the registered order.

`prereg/planted-edge.md`, "Stage 1 — LIVE, 2026-10-02". Everything here is that
section's definitions; the reading conventions the section leaves open are fixed below,
in this file, committed before the results are opened.

**Conventions fixed here, before any data:**
- **A certificate is `p_class < alpha`** (strict), the gate's own convention
  (`quixote/certify.py`: CERTIFIED iff p < alpha). The class tier certifies; the trigger
  tier (`p_trigger`) is reported beside as audit and decides nothing.
- **Rule 1, false certification:** a certificate whose submission has in-sample
  population Sharpe <= 0 (or no submission). Rate over ALL runs at the level, per
  searcher. Fails high iff the lower Wilson 95% end exceeds alpha (at n = 2,000: k >= 120
  at 0.05, k >= 29 at 0.01; checked against the Wilson rule). **Any failure: the reader
  stops after rule 1 and prints the registered replication's launch.**
- **Rule 2, power:** correct certificates (population Sharpe > 0) over all runs at the
  level, per searcher, at both alphas. **Nearest-the-bar:** the level among {0.5, 1.0,
  1.5} whose power at alpha = 0.05, pooled over the six searchers (correct certificates
  over 6 x 2,000), is nearest 0.50, ties to the lower.
- **Descriptive, power against the class maximum's population Sharpe:** the planted
  levels' panels binned by `pop_best_sr` at fixed edges 0.5, 1.0, 1.5, 2.0.
- **Rule 3, recovery:** per searcher and level, the submission equals `m*` / shares two
  of its three signed features, and equals `m+` / shares two of three, with Wilson
  intervals; beside each, the exhaustive base rate (the realized class argmax's). `m+`
  is read at the planted levels only.
- **Rule 5, out of sample:** within each level, the mean holdout population Sharpe of
  certified (alpha = 0.05) minus uncertified submissions, with a Welch standard error;
  combined across the planted levels as the mean of the within-level differences
  weighted by `nc*nu/(nc+nu)`. Secondary: the same for the realized holdout Sharpe.
- **The standing check:** for each searcher and level, the probability that a procedure
  with this curve's false-certification rate passes rule 1 at the agent half's n = 20
  per level (fires at k >= 3 at 0.05, k >= 2 at 0.01), and at n = 2,000; and, as stage
  2's input, the spread of holdout population Sharpe among submissions per level and the
  rule-5 difference detectable at 20 runs per level.

Refuses unless the file holds exactly the 2,000 registered seeds (600000-601999), each
with the four levels and the six searchers.

    python -m experiments.planted_edge_read --file runs/planted_edge_scripted/draws.jsonl \\
        --out runs/planted_edge_scripted/read.txt
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

from estimator.metrics import wilson_ci

SEEDS = range(600000, 602000)
LEVELS = (0.0, 0.5, 1.0, 1.5)
PLANTED = (0.5, 1.0, 1.5)
ALPHAS = (0.05, 0.01)
N_SEARCHERS = 6
BINS = (0.5, 1.0, 1.5, 2.0)
AGENT_N = 20
REPLICATION_LAUNCH = (
    "ssh og-48 'cd ~/observable-garden && git pull --ff-only && cloud/run.sh curve_rep "
    "bash -c \"echo commit \\$(git rev-parse HEAD); exec python -m experiments.planted_edge "
    "--replication --draws 2000 --workers 191\" && tmux new-session -d -s "
    "selfstop_after_curve_rep \"while tmux has-session -t '=curve_rep' 2>/dev/null; do "
    "sleep 60; done; sleep 600; sudo shutdown -h now\"'")


def kstar(n: int, a: float) -> int:
    for k in range(n + 1):
        if wilson_ci(k, n)[0] > a:
            return k
    return n + 1


def load(path: Path) -> dict:
    by_seed = {}
    for i, ln in enumerate(path.read_text().splitlines(), 1):
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: line {i} does not parse; refused")
        if r["seed"] in by_seed:
            raise SystemExit(f"{path}: seed {r['seed']} appears twice; refused")
        by_seed[r["seed"]] = r
    if set(by_seed) != set(SEEDS):
        raise SystemExit(f"{path}: {len(by_seed)} seeds, not exactly 600000-601999; refused")
    for s, r in by_seed.items():
        lv = sorted(x["beta"] for x in r["levels"])
        if lv != list(LEVELS) or any(len(x["searchers"]) != N_SEARCHERS for x in r["levels"]):
            raise SystemExit(f"seed {s}: not four levels of six searchers; refused")
    return by_seed


def at(by_seed, beta):
    return [next(x for x in r["levels"] if x["beta"] == beta) for r in by_seed.values()]


def cert(s, a):
    return s["support"] is not None and s["p_class"] < a


def truth_is(s):
    return None if s["truth"] is None else s["truth"]["in_sample"]


def false_cert(s, a):
    t = truth_is(s)
    return cert(s, a) and (t is None or t <= 0)


def correct_cert(s, a):
    t = truth_is(s)
    return cert(s, a) and t is not None and t > 0


def searcher(lv, name):
    return next(x for x in lv["searchers"] if x["searcher"] == name)


def fmt(k, n):
    lo, hi = wilson_ci(k, n)
    return f"{k:>5} {k / n:7.4f} [{lo:.4f}, {hi:.4f}]"


def read(by_seed) -> tuple[str, bool]:
    L: list[str] = []
    A = L.append
    levels = {b: at(by_seed, b) for b in LEVELS}
    names = [s["searcher"] for s in levels[0.0][0]["searchers"]]
    n = len(levels[0.0])
    A("7.5 stage 1 — the scripted curve, READ ONCE, in the registered order")
    A("=" * 78)
    A(f"  panels {n} (seeds 600000-601999), levels {list(LEVELS)}, six searchers; "
      "certificate = p_class < alpha")
    A("")

    # ---------------------------------------------------------------- rule 1
    A("RULE 1 — false certification (submission population Sharpe <= 0), per run")
    A("-" * 78)
    ks = {a: kstar(n, a) for a in ALPHAS}
    A(f"   fails high iff the lower Wilson end exceeds alpha: at n = {n}, k >= "
      f"{ks[0.05]} (0.05), k >= {ks[0.01]} (0.01)")
    A(f"   {'searcher':<30}{'level':>6}  {'alpha 0.05: k rate Wilson':<34}{'':<6}"
      f"{'alpha 0.01: k rate Wilson':<34}")
    failed = []
    fc_rate = {}
    for name in names:
        for b in LEVELS:
            row = f"   {name:<30}{b:>6}  "
            for a in ALPHAS:
                k = sum(false_cert(searcher(lv, name), a) for lv in levels[b])
                fc_rate[(name, b, a)] = k / n
                lo = wilson_ci(k, n)[0]
                fails = k >= ks[a]
                if fails != (lo > a):
                    raise SystemExit(f"{name} {b} {a}: k* and the Wilson rule disagree")
                if fails:
                    failed.append((name, b, a))
                row += f"{fmt(k, n)} {'FAILS' if fails else 'pass':<6}"
            A(row)
    A("")
    A("   Family: 48 tests; all pass 0.2393 if exactly valid and independent, 0.9587 with")
    A("   the replication branch; predicted conservative and correlated.")
    A(f"   RULE 1: {len(failed)} of 48 fail high" + (": " + "; ".join(
        f"{a} {b} at {c}" for a, b, c in failed) if failed else " — all 48 pass"))
    A("")
    if failed:
        A("RULES 2, 3, 5 AND THE STANDING CHECK — NOT PRINTED")
        A("-" * 78)
        A("   A rule-1 test fails high, so by the registered branch the whole block")
        A("   610000-611999 is rerun at identical settings and every failed rule re-read on")
        A("   it before anything else is read. Its launch, after a dated commit recording")
        A("   the failure:")
        A("   " + REPLICATION_LAUNCH)
        return "\n".join(L), True

    # ---------------------------------------------------------------- rule 2
    A("RULE 2 — power: correct certificates (population Sharpe > 0) over all runs")
    A("-" * 78)
    A(f"   {'searcher':<30}{'level':>6}  {'alpha 0.05 (class)':<30}{'alpha 0.01 (class)':<30}"
      f"{'0.05 trigger, audit':>20}")
    pooled = {}
    for b in LEVELS:
        tot = 0
        for name in names:
            ss = [searcher(lv, name) for lv in levels[b]]
            k05 = sum(correct_cert(s, 0.05) for s in ss)
            k01 = sum(correct_cert(s, 0.01) for s in ss)
            ktr = sum(s["support"] is not None and s["p_trigger"] < 0.05
                      and (truth_is(s) or 0) > 0 for s in ss)
            tot += k05
            A(f"   {name:<30}{b:>6}  {fmt(k05, n):<30}{fmt(k01, n):<30}{ktr:>20}")
        pooled[b] = tot / (N_SEARCHERS * n)
    A("")
    A("   pooled power at alpha 0.05, six searchers: " + ", ".join(
        f"level {b}: {pooled[b]:.4f}" for b in LEVELS))
    best = min(PLANTED, key=lambda b: (abs(pooled[b] - 0.5), b))
    A(f"   NEAREST-THE-BAR: level {best} (pooled power {pooled[best]:.4f}; nearest 0.50, "
      "ties to the lower)")
    A("")
    A("   descriptive: power at alpha 0.05 against the panel's class-maximum population")
    A("   Sharpe (pop_best_sr), planted levels pooled, binned at 0.5, 1.0, 1.5, 2.0")
    edges = (-np.inf,) + BINS + (np.inf,)
    for lo_, hi_ in zip(edges[:-1], edges[1:]):
        k = m = 0
        for b in PLANTED:
            for lv in levels[b]:
                if lo_ < lv["pop_best_sr"] <= hi_:
                    for name in names:
                        m += 1
                        k += correct_cert(searcher(lv, name), 0.05)
        if m:
            A(f"     ({lo_:>5}, {hi_:<5}]  {k:>6} of {m:<6} = {k / m:.4f}")
    A("")

    # ---------------------------------------------------------------- rule 3
    A("RULE 3 — recovery, with the exhaustive base rate (the realized class argmax)")
    A("-" * 78)
    A(f"   {'searcher':<30}{'level':>6}  {'= m*':<26}{'2 of 3 m*':<26}{'= m+':<26}"
      f"{'2 of 3 m+':<26}")
    for name in names + ["(class argmax)"]:
        for b in LEVELS:
            if name == "(class argmax)":
                rs = [lv["class_argmax_recovery"] for lv in levels[b]]
            else:
                rs = [searcher(lv, name) for lv in levels[b]]
            cells = [fmt(sum(bool(r["equals"]) for r in rs), n),
                     fmt(sum(bool(r["two_of_three"]) for r in rs), n)]
            if b in PLANTED:
                cells += [fmt(sum(bool(r["equals_pop_best"]) for r in rs), n),
                          fmt(sum(bool(r["two_of_three_pop_best"]) for r in rs), n)]
            else:
                cells += ["(not read at level 0)", ""]
            A(f"   {name:<30}{b:>6}  " + "".join(f"{c:<26}" for c in cells))
    A("")

    # ---------------------------------------------------------------- rule 5
    A("RULE 5 — out of sample, certified (alpha 0.05) against uncertified, within level")
    A("-" * 78)
    A("   PRIMARY: holdout population Sharpe.  SECONDARY: realized holdout Sharpe.")

    def diff(vals_c, vals_u):
        nc, nu = len(vals_c), len(vals_u)
        if nc < 2 or nu < 2:
            return None
        d = np.mean(vals_c) - np.mean(vals_u)
        se = np.sqrt(np.var(vals_c, ddof=1) / nc + np.var(vals_u, ddof=1) / nu)
        return d, se, nc, nu

    for key, label in (("pop", "PRIMARY"), ("real", "SECONDARY")):
        A(f"   {label}")
        for name in names:
            parts, w_sum, d_sum = [], 0.0, 0.0
            for b in LEVELS:
                c, u = [], []
                for lv in levels[b]:
                    s = searcher(lv, name)
                    if s["support"] is None:
                        continue
                    v = s["truth"]["holdout"] if key == "pop" else s["holdout_realized"]
                    (c if cert(s, 0.05) else u).append(v)
                r = diff(c, u)
                if r is None:
                    parts.append(f"{b}: n/a ({len(c)} cert)")
                    continue
                d, se, nc, nu = r
                parts.append(f"{b}: {d:+.4f} (SE {se:.4f}; {nc}/{nu})")
                if b in PLANTED:
                    w = nc * nu / (nc + nu)
                    w_sum += w
                    d_sum += w * d
            comb = f"{d_sum / w_sum:+.4f}" if w_sum else "n/a"
            A(f"     {name:<30} " + "  ".join(parts) + f"   combined (planted): {comb}")
    A("")

    # ------------------------------------------------------- the standing check
    A("THE STANDING CHECK")
    A("-" * 78)
    k20 = {a: kstar(AGENT_N, a) for a in ALPHAS}
    A(f"   probability a procedure with this curve's false-certification rate PASSES rule 1")
    A(f"   at the agent half's n = {AGENT_N} per level (fires at k >= {k20[0.05]} at 0.05, "
      f"k >= {k20[0.01]} at 0.01), and at n = {n}:")
    for name in names:
        row = f"     {name:<30}"
        for b in LEVELS:
            p20 = [stats.binom.cdf(k20[a] - 1, AGENT_N, fc_rate[(name, b, a)]) for a in ALPHAS]
            row += f" {b}: {p20[0]:.3f}/{p20[1]:.3f}"
        A(row + "   (0.05/0.01 at n = 20)")
    A(f"   at n = {n} every rule-1 test above passed on these draws.")
    A("")
    A("   stage 2's input — rule 5 at 20 runs per level: the spread of holdout population")
    A("   Sharpe among submissions, and the difference detectable at 80% (two-sided 0.05)")
    A("   with 10 certified against 10 uncertified")
    for b in PLANTED:
        v = [searcher(lv, nm)["truth"]["holdout"] for lv in levels[b] for nm in names
             if searcher(lv, nm)["support"] is not None]
        sd = float(np.std(v, ddof=1))
        A(f"     level {b}: sd {sd:.4f}; detectable difference "
          f"{2.8 * sd * np.sqrt(1 / 10 + 1 / 10):.4f}")
    return "\n".join(L), False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="runs/planted_edge_scripted/draws.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text, _ = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
