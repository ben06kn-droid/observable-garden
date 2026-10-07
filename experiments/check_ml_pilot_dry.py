"""Checker for the ML pilot's dry run (`experiments/ml_pilot_2026_10_07.py --dry-seeds`).

Prints only: tasks completed, the row count, the field names, and whether every field is
finite or a declared null. **No value is printed**: no certification, Sharpe, p-value or
capture. The reader is not run on a dry run.

    python -m experiments.check_ml_pilot_dry --dir runs/ml_pilot_dry/2026-10-07
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# Paths that may be null, and when: level-0 rows carry no rule; zero-cost rows no class
# tier; single-feature rules (U, gated) no second feature.
DECLARED_NULL = {"rule": "level0", "shape": "level0", "class": "zero cost", "rule.b": "U or gated"}
EXPECTED_ROWS = {"planted": 3, "level0": 2}          # three levels; at cost and zero cost


def leaves(x, path=""):
    if isinstance(x, dict):
        for k, v in x.items():
            yield from leaves(v, f"{path}.{k}" if path else str(k))
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v, f"{path}[]")
    else:
        yield path, x


def problems(row: dict) -> list[str]:
    bad = []
    for path, v in leaves(row):
        if v is None:
            if path not in DECLARED_NULL:
                bad.append(f"{path}: undeclared null")
        elif isinstance(v, bool) or isinstance(v, str):
            continue
        elif isinstance(v, (int, float)):
            if not math.isfinite(v):
                bad.append(f"{path}: not finite")
        else:
            bad.append(f"{path}: unexpected type {type(v).__name__}")
    return bad


def check(d: Path) -> tuple[list[str], bool]:
    L = []
    prov = json.loads((d / "provenance.json").read_text())
    f = d / "pilot.jsonl"
    if not f.exists():
        return [f"no pilot.jsonl in {d} (partial: {(d / 'pilot.jsonl.partial').exists()})"], False
    rows = [json.loads(x) for x in f.read_text().splitlines() if x.strip()]
    tasks = {(r["kind"], r["seed"]) for r in rows}
    want = {(k, s) for k, s, _ in prov["task_list"]}
    n_expected = sum(EXPECTED_ROWS[k] for k, _ in want)
    ok = tasks == want and len(rows) == n_expected and prov.get("dry_run") is True
    L.append(f"platform {prov['platform']}; lightgbm {prov['lightgbm']}; HEAD {prov['git_head']}")
    L.append(f"tasks completed: {len(tasks)} of {len(want)}"
             + ("" if tasks == want else f"  MISSING {sorted(want - tasks)}"))
    L.append(f"rows: {len(rows)} (expected {n_expected})")
    by_type = {}
    for r in rows:
        key = f"{r['kind']}, {r['cost']} cost"
        by_type.setdefault(key, set()).update(p for p, _ in leaves(r))
    for key, names in sorted(by_type.items()):
        L.append(f"fields, {key} ({len(names)}):")
        L.extend(f"   {n}" for n in sorted(names))
    bad = sorted({p for r in rows for p in problems(r)})
    ok = ok and not bad
    L.append("every field finite or a declared null: " + ("YES" if not bad else "NO"))
    L.extend(f"   PROBLEM {p}" for p in bad)
    L.append(f"declared nulls: {DECLARED_NULL}")
    L.append("DRY RUN CHECK: " + ("PASS" if ok else "PROBLEM"))
    return L, ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args(argv)
    L, ok = check(Path(a.dir))
    text = "\n".join(L)
    (Path(a.dir) / "dry_check.txt").write_text(text + "\n")
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
