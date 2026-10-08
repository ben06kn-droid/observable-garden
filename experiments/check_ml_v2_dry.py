"""Checker for the version-2 pilot's dry run (`ml_v2_pilot_2026_10_08 --dry`). Prints only:
tasks completed, rows per kind, the number of fields, and whether every field is finite or
a declared null. No value is printed.

    python -m experiments.check_ml_v2_dry --dir runs/ml_v2_pilot_dry/2026-10-08
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from experiments.check_ml_pilot_dry import leaves

DECLARED_NULL = ("rule", "shape", "class")      # level-0 rows carry no rule; zero cost no class tier
EXPECTED_ROWS = {"seed": 4, "menu": 1, "level0": 2}


def check(d: Path) -> tuple[list[str], bool]:
    prov = json.loads((d / "provenance.json").read_text())
    rows = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    want = {(t[0], t[1]) for t in prov["task_list"]}
    got = {(r["kind"], r["seed"]) for r in rows}
    n_exp = sum(EXPECTED_ROWS[k] for k, _ in want)
    bad = sorted({p for r in rows for p, v in leaves(r)
                  if (v is None and not p.startswith(DECLARED_NULL))
                  or (isinstance(v, float) and not math.isfinite(v))})
    fields = {r["kind"]: len({p for p, _ in leaves(r)}) for r in rows}
    ok = got == want and len(rows) == n_exp and not bad and prov.get("dry_run") is True
    L = [f"platform {prov['platform']}; HEAD {prov['git_head']}",
         f"tasks completed: {len(got)} of {len(want)}", f"rows: {len(rows)} (expected {n_exp})",
         f"fields per kind: {fields}",
         "every field finite or a declared null: " + ("YES" if not bad else "NO " + str(bad[:20])),
         "DRY RUN CHECK: " + ("PASS" if ok else "PROBLEM")]
    return L, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    L, ok = check(Path(a.dir))
    (Path(a.dir) / "dry_check.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
