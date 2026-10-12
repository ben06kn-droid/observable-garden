"""Emit exactly `grade_real`'s `[{name, weights}]` from run files.

`experiments/grade_real.py` takes `--submissions JSON: [{name, weights}, ...]` and
computes `F @ w`, so `weights` is a **length-K feature-weight vector**, not a per-asset
one. The registered weight rule is therefore the gate's own:
`quixote.grammar.weights(support, K)` — the signed indicator over the declared class,
`+1` or `-1` at each feature in the submitted support and zero elsewhere. Using the same
function the sandbox and the gate use is the point: a second implementation of "what the
submission means" could disagree with the one that was certified.

**Nothing else is written.** Each object carries `name` and `weights` and no other key.
A submission file is the only thing that crosses to the holdout host, so anything extra
in it is something that did not need to cross. `tests/test_collect_submissions.py` holds
that.

    python -m experiments.collect_submissions --dirs runs/etf_replay runs/etf_orientation \
        --out figures/etf_submissions.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from quixote.grammar import weights

K_FOR = {"etf": 40, "adr": 44, "s0": 40, "s3": 40}


def submissions_for(dirs: list[str], K: int) -> list[dict]:
    """One `{name, weights}` per run that submitted, in run-id order."""
    out, seen = [], set()
    for dirname in dirs:
        d = Path(dirname)
        for f in sorted(d.glob("*.json")):
            if f.name in ("run_config.json", "class_p.json") or "regrade" in f.name:
                continue
            try:
                x = json.loads(f.read_text())
            except json.JSONDecodeError:
                continue
            sup = x.get("submitted_support")
            name = x.get("run_id")
            if not sup or not name:
                continue
            if name in seen:
                raise SystemExit(f"duplicate run_id {name!r}; names must be unique "
                                 "because the grader keys its output on them")
            seen.add(name)
            support = tuple((int(k), float(s)) for k, s in sup)
            bad = [k for k, _ in support if not 0 <= k < K]
            if bad:
                raise SystemExit(f"{name}: feature index out of range for K={K}: {bad}")
            out.append({"name": name,
                        "weights": [float(v) for v in weights(support, K)]})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--panel", default="etf", choices=sorted(K_FOR))
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be written and write nothing")
    a = ap.parse_args(argv)

    subs = submissions_for(a.dirs, K_FOR[a.panel])
    if not subs:
        raise SystemExit(f"no submissions found in {a.dirs}")
    keys = {k for s in subs for k in s}
    assert keys == {"name", "weights"}, f"extra keys would be written: {keys}"
    nz = [sum(1 for v in s["weights"] if v) for s in subs]
    print(f"{len(subs)} submission(s), K = {K_FOR[a.panel]}, "
          f"nonzero weights per submission: min {min(nz)} max {max(nz)}")
    print(f"keys written per object: {sorted(keys)}")
    if a.dry_run:
        print(f"DRY RUN — nothing written. First: {subs[0]['name']}, "
              f"{sum(1 for v in subs[0]['weights'] if v)} nonzero")
        return 0
    Path(a.out).write_text(json.dumps(subs, indent=1))
    print(f"written to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
