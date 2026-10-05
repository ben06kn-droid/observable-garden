"""Read the V2 confidence cell ONCE, in order: V2, then V1 (both tiers), then V3.

`prereg/confidence-output.md` (draft until its V2 section is live). From
`experiments/confidence_cell.py`'s records:

1. **V2, the exactness rule**, per level and g in {0.90, 0.95, 0.99}: `r_g`, the share
   of panels with `D <= quantile_g(M_b)`, and its Wilson 95% interval. **EXACT** iff the
   interval contains g, **FAILS LOW** iff the upper end < g, **CONSERVATIVE** iff the
   lower end > g. Beside it, a KS test of the PIT values `u` against uniform, descriptive.
   **If any V2 test fails low, the reader stops there.** P7's premise then fails on this
   design and every confidence output is withdrawn pending a cause, so V1 and V3 are
   not printed.
2. **V1, coverage of `L_g`**, per row (the six searchers and the class argmax), level
   and g, on the class tier, with the replay tier (searchers only) as audit. A run is
   covered iff its in-sample population Sharpe is >= `L_g`. Fails low iff the upper
   Wilson end < g; conservative iff the lower end > g.
3. **V3, reliability, descriptive.** `P_5` (class tier) is binned into deciles against
   whether the realized holdout Sharpe is > 0, per level. All submissions and certified
   ones (`p_class < 0.05`) are shown separately, with the Brier score. Beside them: the
   same against the holdout population Sharpe > 0, and the mean in-sample-to-holdout
   shift in population Sharpe.

It refuses to run unless the file holds exactly 620000-620999, three levels
(0, 1.0, 1.5) of six searchers each, every line parsing.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import kstest

from estimator.metrics import wilson_ci

SEEDS = range(620_000, 621_000)
LEVELS = (0.0, 1.0, 1.5)
GS = (0.90, 0.95, 0.99)
ARGMAX = "(class argmax)"
CERT_ALPHA = 0.05


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
        if tuple(lv["beta"] for lv in r["levels"]) != LEVELS:
            raise SystemExit(f"seed {r['seed']}: levels are not {LEVELS}; refused")
        if any(len(lv["searchers"]) != 6 for lv in r["levels"]):
            raise SystemExit(f"seed {r['seed']}: not six searchers per level; refused")
    return recs


def verdict(k: int, n: int, g: float, exact_word: str = "within") -> tuple:
    lo, hi = wilson_ci(k, n)
    if hi < g:
        return lo, hi, "FAILS LOW"
    if lo > g:
        return lo, hi, "CONSERVATIVE" if exact_word == "EXACT" else "conservative"
    return lo, hi, exact_word


def by_level(recs, beta):
    return [next(lv for lv in r["levels"] if lv["beta"] == beta) for r in recs]


def read_v2(recs, A) -> bool:
    A("1. V2 — the class maximum's estimation error against the null (exactness rule)")
    A("-" * 78)
    A("   EXACT iff the Wilson 95% interval contains g; FAILS LOW iff the upper end < g;")
    A("   CONSERVATIVE iff the lower end > g. Predicted: slightly conservative.")
    A(f"   {'level':>6}{'g':>6}{'k':>7}{'n':>7}{'r_g':>9}   {'Wilson 95%':<18}{'verdict':<14}")
    fails = False
    for beta in LEVELS:
        lvs = by_level(recs, beta)
        for g in GS:
            k = sum(lv["v2"]["covered"][f"{g:.2f}"] for lv in lvs)
            lo, hi, v = verdict(k, len(lvs), g, "EXACT")
            fails |= v == "FAILS LOW"
            A(f"   {beta:>6.1f}{g:>6.2f}{k:>7}{len(lvs):>7}{k / len(lvs):>9.4f}   "
              f"[{lo:.4f}, {hi:.4f}]  {v:<14}")
    A("")
    A("   PIT u = #{M_b < D}/B against uniform (KS, descriptive):")
    for beta in LEVELS:
        u = np.array([lv["v2"]["u"] for lv in by_level(recs, beta)])
        ks = kstest(u, "uniform")
        D = np.array([lv["v2"]["D"] for lv in by_level(recs, beta)])
        A(f"     level {beta:.1f}: KS D = {ks.statistic:.4f}, p = {ks.pvalue:.4f}; "
          f"mean u {u.mean():.4f}; D mean {D.mean():+.4f}")
    A(f"   V2: {'AT LEAST ONE TEST FAILS LOW' if fails else 'no test fails low'}")
    A("")
    return fails


def _covered(row: dict, conf_key: str, g: float):
    conf, truth = row.get(conf_key), row.get("truth")
    if conf is None or truth is None:
        return None
    return truth["in_sample"] >= conf["L"][f"{g:.2f}"]


def read_v1(recs, A) -> None:
    names = [s["searcher"] for s in recs[0]["levels"][0]["searchers"]]
    for tier, key, rows in (("class tier", "conf_class", names + [ARGMAX]),
                            ("trigger replay (AUDIT)", "conf_replay", names)):
        A(f"2. V1 — coverage of L_g, {tier}")
        A("-" * 78)
        A(f"   {'row':<32}{'level':>6}{'g':>6}{'k':>7}{'n':>7}{'rate':>9}   "
          f"{'Wilson 95%':<18}{'verdict':<13}{'excl':>5}")
        for name in rows:
            for beta in LEVELS:
                lvs = by_level(recs, beta)
                for g in GS:
                    cov = []
                    for lv in lvs:
                        row = lv["argmax"] if name == ARGMAX else next(
                            s for s in lv["searchers"] if s["searcher"] == name)
                        cov.append(_covered(row, key, g))
                    k = sum(1 for c in cov if c)
                    n = sum(1 for c in cov if c is not None)
                    lo, hi, v = verdict(k, n, g) if n else (np.nan, np.nan, "n/a")
                    A(f"   {name:<32}{beta:>6.1f}{g:>6.2f}{k:>7}{n:>7}"
                      f"{(k / n if n else np.nan):>9.4f}   [{lo:.4f}, {hi:.4f}]  "
                      f"{v:<13}{len(cov) - n:>5}")
        A("")


def read_v3(recs, A) -> None:
    A("3. V3 — reliability of P_5 (class tier), descriptive; no rule reads it")
    A("-" * 78)
    edges = np.linspace(0, 1, 11)
    for beta in LEVELS:
        subs = [s for lv in by_level(recs, beta) for s in lv["searchers"]
                if s.get("conf_class") is not None]
        shift = np.mean([s["truth"]["holdout"] - s["truth"]["in_sample"] for s in subs])
        A(f"   level {beta:.1f}: mean holdout - in-sample population Sharpe "
          f"{shift:+.4f} over {len(subs)} submissions")
        for label, pick in (("all", subs),
                            ("certified", [s for s in subs if s["p_class"] < CERT_ALPHA])):
            for outcome, f in (("realized holdout > 0", lambda s: s["holdout_realized"] > 0),
                               ("holdout population > 0",
                                lambda s: s["truth"]["holdout"] > 0)):
                P = np.array([s["conf_class"]["P_H"] for s in pick])
                y = np.array([f(s) for s in pick], dtype=float)
                if not len(P):
                    A(f"     {label:<10}{outcome:<26} none")
                    continue
                A(f"     {label:<10}{outcome:<26} n {len(P)}, Brier "
                  f"{np.mean((P - y) ** 2):.4f}")
                for i in range(10):
                    m = (P >= edges[i]) & ((P < edges[i + 1]) if i < 9 else (P <= 1))
                    if not m.any():
                        continue
                    k, n = int(y[m].sum()), int(m.sum())
                    lo, hi = wilson_ci(k, n)
                    A(f"       P_5 in [{edges[i]:.1f}, {edges[i + 1]:.1f}{')' if i < 9 else ']'}:"
                      f" mean P {P[m].mean():.3f}, observed {k}/{n} = {k / n:.3f} "
                      f"[{lo:.3f}, {hi:.3f}]")
        A("")


def read(recs) -> tuple[str, bool]:
    L: list[str] = []
    A = L.append
    A("confidence cell (V2, with V1 and V3) — READ ONCE, in the registered order")
    A("=" * 78)
    A(f"  panels {len(recs)} (seeds {SEEDS.start}-{SEEDS.stop - 1}), levels {list(LEVELS)}")
    A("")
    fails = read_v2(recs, A)
    if fails:
        A("V1 AND V3 ARE NOT PRINTED: a V2 test fails low, so by the registered rule every")
        A("L_g, C0 and C(s) is withdrawn pending a cause.")
        return "\n".join(L), True
    read_v1(recs, A)
    read_v3(recs, A)
    return "\n".join(L), False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="runs/confidence_cell/draws.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text, _ = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
