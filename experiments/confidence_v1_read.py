"""The stage-1 secondary analysis: V1 coverage of `L_g`, class tier, READ ONCE.

`prereg/confidence-output.md`, "Stage-1 secondary analysis: V1, class tier, on data
already read" (LIVE 2026-10-04). **SECONDARY, ON DATA ALREADY READ.** Per row (the six
registered searchers and the class argmax), level and g in {0.95, 0.99}:

    L_g = S - q_g,   q_0.95 = null_max_q["0.05"],   q_0.99 = null_max_q["0.01"]

`S` is the searcher's `score`, or `class_max` for the argmax row. A run is covered iff
its in-sample population Sharpe is >= `L_g`. The output gives k of n, the rate and the
Wilson 95% interval. **FAILS LOW iff the upper Wilson end < g**, CONSERVATIVE iff the
lower end > g, and WITHIN otherwise. A run with no submission is excluded and counted.

It refuses any file but the registered one: exactly 2,000 distinct seeds on
600000-601999, four levels of six searchers each, and the SHA-256 of `30ee870`'s file.

    python -m experiments.confidence_v1_read --out runs/planted_edge_scripted/confidence_v1.txt
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from estimator.metrics import wilson_ci

FILE = "runs/planted_edge_scripted/draws.jsonl"
REGISTERED_SHA256 = "cd7e9f8fe07724952d9d7f0fef1e3e0580c2a6ea9f1121d6e5f20828a6259ce1"
SEEDS = range(600_000, 602_000)
LEVELS = (0.0, 0.5, 1.0, 1.5)
GS = (0.95, 0.99)
QKEY = {0.95: "0.05", 0.99: "0.01"}       # null_max_q[str(alpha)] = quantile(M_b, 1 - alpha)
ARGMAX = "(class argmax)"


def load(path: Path, sha256: str | None = REGISTERED_SHA256) -> list[dict]:
    raw = path.read_bytes()
    if sha256 is not None and hashlib.sha256(raw).hexdigest() != sha256:
        raise SystemExit(f"{path}: SHA-256 is not the registered {sha256}; refused")
    recs = []
    for i, ln in enumerate(raw.decode().splitlines(), 1):
        try:
            recs.append(json.loads(ln))
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: line {i} does not parse; refused")
    seeds = sorted(r["seed"] for r in recs)
    if seeds != list(SEEDS):
        raise SystemExit(f"{path}: {len(recs)} lines, seeds not exactly "
                         f"{SEEDS.start}-{SEEDS.stop - 1}; refused")
    for r in recs:
        if sorted(lv["beta"] for lv in r["levels"]) != list(LEVELS):
            raise SystemExit(f"seed {r['seed']}: levels are not {LEVELS}; refused")
        for lv in r["levels"]:
            if len(lv["searchers"]) != 6:
                raise SystemExit(f"seed {r['seed']} level {lv['beta']}: "
                                 f"{len(lv['searchers'])} searchers, not 6; refused")
    return recs


def rows_of(lv: dict):
    """(row name, S, in-sample population Sharpe or None) for one level record."""
    for s in lv["searchers"]:
        truth = s.get("truth")
        yield (s["searcher"], s["score"],
               None if (s.get("support") is None or truth is None) else truth["in_sample"])
    yield ARGMAX, lv["class_max"], lv["class_argmax_truth"]["in_sample"]


def verdict(k: int, n: int, g: float) -> tuple[float, float, str]:
    lo, hi = wilson_ci(k, n)
    if hi < g:
        return lo, hi, "FAILS LOW"
    if lo > g:
        return lo, hi, "conservative"
    return lo, hi, "within"


def read(recs) -> str:
    names = [s["searcher"] for s in recs[0]["levels"][0]["searchers"]] + [ARGMAX]
    tally = {}                       # (name, level, g) -> [covered, n, excluded]
    for r in recs:
        for lv in r["levels"]:
            for name, S, sr in rows_of(lv):
                for g in GS:
                    t = tally.setdefault((name, lv["beta"], g), [0, 0, 0])
                    if sr is None:
                        t[2] += 1
                        continue
                    t[1] += 1
                    t[0] += int(sr >= S - lv["null_max_q"][QKEY[g]])
    L = []
    A = L.append
    A("V1 — coverage of L_g = S - quantile_g(M_b), class tier — READ ONCE")
    A("SECONDARY, ON DATA ALREADY READ (stage 1 read at 8660508; this quantity was not")
    A("computed in that read). prereg/confidence-output.md, live 2026-10-04.")
    A("=" * 78)
    A(f"  panels {len(recs)} (seeds {SEEDS.start}-{SEEDS.stop - 1}), levels {list(LEVELS)}; "
      "covered iff in-sample population Sharpe >= L_g")
    A("  fails low iff the upper Wilson end < g; conservative iff the lower end > g")
    A("")
    fails = []
    for g in GS:
        A(f"g = {g}")
        A("-" * 78)
        A(f"   {'row':<32}{'level':>6}{'k':>7}{'n':>7}{'rate':>9}   {'Wilson 95%':<18}"
          f"{'verdict':<13}{'excl':>5}")
        for name in names:
            for beta in LEVELS:
                k, n, ex = tally[(name, beta, g)]
                lo, hi, v = verdict(k, n, g) if n else (float("nan"), float("nan"), "n/a")
                if v == "FAILS LOW":
                    fails.append((name, beta, g))
                rate = k / n if n else float("nan")
                A(f"   {name:<32}{beta:>6.1f}{k:>7}{n:>7}{rate:>9.4f}   "
                  f"[{lo:.4f}, {hi:.4f}]  {v:<13}{ex:>5}")
        A("")
    A(f"FAILS LOW: {len(fails)} of {len(names) * len(LEVELS) * len(GS)} tests"
      + ("" if not fails else " — " + "; ".join(f"{n} {b} g={g}" for n, b, g in fails)))
    A("No family-wise pass rate is claimed; the tests share panels and replicates.")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=FILE)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
