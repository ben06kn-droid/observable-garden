"""Read check 2 (rule 6, fidelity) ONCE, from a live run's presentation log.

`prereg/planted-edge.md`, rule 6, and `prereg/agent-cell.md` amendment 7 as settled.
The input is `fidelity_live_presentations.jsonl`, written by `experiments/fidelity.py
--live`: one line per presentation, with its options, the raw answer, the parsed
answer and the declared rule's prediction. **Agreement is recomputed here from those
fields**; the summary rows are not trusted.

Per decision kind (`pick`, `stop`, `restart`):
- **decisions** (distinct run and step), **presentations**, **agreed**, **no answer**,
  the agreement rate and its Wilson 95% interval.
- **The rule:**
  - fewer than **10 decisions**: **UNMEASURED, with its count** (`prereg/README.md`'s
    low-n rule);
  - otherwise a rate **at or above 0.80**: **not priced locally**;
  - a rate **below 0.80**: **priced locally from then on**, and a liberal local price
    drops the run to the class tier.

  The tolerance is read on the point rate, as registered, with the Wilson interval
  beside it.
- No answer counts as disagreement.

It refuses a file that is not a live run's: a missing file, a line without the live
fields, or a presentation whose answer is outside its options.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from estimator.metrics import wilson_ci

TOLERANCE = 0.80
MIN_DECISIONS = 10
FIELDS = ("run_id", "step", "kind", "options", "raw", "answer", "predicted")


def load(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path} is missing: rule 6 reads a LIVE run's presentation log")
    rows = []
    for i, ln in enumerate(path.read_text().splitlines(), 1):
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            raise SystemExit(f"{path}: line {i} does not parse; refused")
        missing = [k for k in FIELDS if k not in r]
        if missing:
            raise SystemExit(f"{path}: line {i} lacks {missing}; not a live presentation log")
        if r["answer"] is not None and r["answer"] not in r["options"]:
            raise SystemExit(f"{path}: line {i}'s answer is outside its options; refused")
        rows.append(r)
    if not rows:
        raise SystemExit(f"{path} holds no presentations")
    return rows


def read(rows) -> str:
    by = defaultdict(lambda: {"dec": set(), "pres": 0, "agree": 0, "none": 0})
    for r in rows:
        b = by[r["kind"]]
        b["dec"].add((r["run_id"], r["step"]))
        b["pres"] += 1
        b["agree"] += int(r["answer"] is not None and r["answer"] == r["predicted"])
        b["none"] += int(r["answer"] is None)
    L = ["check 2 (rule 6) — FIDELITY, READ ONCE from the live presentation log",
         "=" * 78,
         f"  tolerance {TOLERANCE:.2f} on the point rate; a kind with fewer than "
         f"{MIN_DECISIONS} decisions is unmeasured; no answer counts as disagreement",
         f"   {'kind':<10}{'decisions':>10}{'presentations':>15}{'agreed':>8}{'no answer':>11}"
         f"{'rate':>8}   {'Wilson 95%':<18}verdict"]
    for kind in sorted(by):
        b = by[kind]
        n_dec, pres, ag = len(b["dec"]), b["pres"], b["agree"]
        lo, hi = wilson_ci(ag, pres)
        rate = ag / pres
        if n_dec < MIN_DECISIONS:
            v = f"UNMEASURED ({n_dec} decisions)"
        elif rate >= TOLERANCE:
            v = "at or above tolerance: NOT priced locally"
        else:
            v = "below tolerance: PRICED LOCALLY from then on"
        L.append(f"   {kind:<10}{n_dec:>10}{pres:>15}{ag:>8}{b['none']:>11}{rate:>8.4f}   "
                 f"[{lo:.4f}, {hi:.4f}]  {v}")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True,
                    help="a live run's fidelity_live_presentations.jsonl")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    text = read(load(Path(a.file)))
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
