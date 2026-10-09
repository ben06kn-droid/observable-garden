"""Checker for the recency planted dry run (the smoke seeds 705900-705909, B 200). Prints
only: tasks completed, arms covered, the fields present per arm, and whether every number is
finite and every p in (0, 1]. No rate is printed.

    python -m experiments.check_recency_planted_dry --dir runs/recency_planted_dry/<date>
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from experiments import recency_planted as P


def check(d: Path) -> tuple[list[str], bool]:
    prov = json.loads((d / "provenance.json").read_text())
    rows = [json.loads(x) for x in (d / "results.jsonl").read_text().splitlines() if x.strip()]
    want = {(a, s) for a, s in P.smoke_tasks()}
    got = {(r["arm"], r["seed"]) for r in rows}
    bad = []
    for r in rows:
        tests = {"unweighted", "weighted"} | ({"weighted_superseded"} if r["arm"] in P.SUPERSEDED else set())
        if set(r.get("stream", {})) != tests:
            bad.append(f"{r['arm']} {r['seed']}: stream tests {sorted(r.get('stream', {}))}")
        if (r["arm"] in P.NULL_CLASS) != ("class" in r):
            bad.append(f"{r['arm']} {r['seed']}: class tests present = {'class' in r}")
        for blk in (r.get("stream", {}), r.get("class", {})):
            for t, v in blk.items():
                if not all(math.isfinite(x) for x in v.values()) or not 0 < v["p"] <= 1:
                    bad.append(f"{r['arm']} {r['seed']} {t}: a non-finite number or p outside (0, 1]")
        for k in ("block_length", "block_length_last_neff", "n_eff_rows"):
            if not isinstance(r.get(k), int) or r[k] < 1:
                bad.append(f"{r['arm']} {r['seed']}: {k} {r.get(k)}")
    ok = got == want and not bad and prov.get("dry_run") is True
    L = [f"platform {prov['platform']}; HEAD {prov.get('git_head')}",
         f"tasks completed: {len(got)} of {len(want)}; arms {sorted({a for a, _ in got})}",
         "fields and finiteness: " + ("YES" if not bad else "NO " + "; ".join(bad[:10])),
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
