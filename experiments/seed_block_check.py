"""Check proposed seed blocks against every pre-registration, live and removed.

`prereg/README.md` requires a new pre-registration's blocks to be used by no other.
This reads every file in `prereg/` and every pre-registration removed in history
(`git show <deleting commit>^:<path>`), plus `EXPERIMENTS.md` and `ROADMAP.md`, and
collects:

- **explicit ranges** `a–b` of integers (3 to 7 digits), and every integer >= 1000;
- **master seeds** (2026xxxx), each expanded to its first 5,000 draws of
  `default_rng(master).integers(0, 2**31 - 1)` -- the agent runners' construction --
  together with the masters the runners hold in code.

A proposed range collides if it overlaps an explicit range, contains a recorded
integer, or contains a draw of any master; a proposed master collides if it is
already a master, its draws collide with another master's, or a draw lands in an
explicit range. Over-inclusive by design: a false alarm costs a look, a miss
costs a contaminated block.

    python -m experiments.seed_block_check --exclude prereg/planted-edge.md \\
        --ranges 600000-601999,610000-611999 --masters 20261010,20261015
"""
from __future__ import annotations

import argparse
import glob
import re
import subprocess

import numpy as np

CODE_MASTERS = {20260916, 20260924, 20260925, 20260929, 20260930, 20261001}
DRAWS = 5000


def corpus(exclude: set[str]) -> dict[str, str]:
    texts = {p: open(p).read() for p in glob.glob("prereg/*.md") if p not in exclude}
    log = subprocess.run(["git", "log", "--all", "--diff-filter=D", "--format=%h",
                          "--name-only", "--", "prereg/"],
                         capture_output=True, text=True, check=True).stdout
    for chunk in log.split("\n\n"):
        parts = [x for x in chunk.split("\n") if x]
        if not parts:
            continue
        for f in parts[1:]:
            texts[f"{f}@{parts[0]}"] = subprocess.run(
                ["git", "show", f"{parts[0]}^:{f}"], capture_output=True, text=True).stdout
    for p in ("EXPERIMENTS.md", "ROADMAP.md"):
        texts[p] = open(p).read()
    return texts


def registry(texts):
    ranges, singles, masters = [], set(), set(CODE_MASTERS)
    for name, t in texts.items():
        for a, b in re.findall(r"\b(\d{3,7})\s*[–-]\s*(\d{3,7})\b", t):
            a, b = int(a), int(b)
            if a < b and b - a < 200000:
                ranges.append((a, b, name))
        for n in map(int, re.findall(r"\b(\d{4,8})\b", t)):
            if 20260000 <= n < 20270000:
                masters.add(n)
            elif n >= 1000:
                singles.add(n)
    return ranges, singles, masters


def draws(m: int) -> set[int]:
    return set(np.random.default_rng(m).integers(0, 2**31 - 1, size=DRAWS).tolist())


def check(prop_ranges, prop_masters, exclude=()) -> list[str]:
    texts = corpus(set(exclude))
    ranges, singles, masters = registry(texts)
    md = {m: draws(m) for m in masters}
    used = lambda x: x in singles or any(a <= x <= b for a, b, _ in ranges)
    bad = []
    for m in prop_masters:
        if m in masters:
            bad.append(f"master {m} already used")
        d = draws(m)
        bad += [f"master {m}: draws collide with master {m2}" for m2, d2 in md.items()
                if m2 != m and d & d2]
        if any(used(x) for x in d):
            bad.append(f"master {m}: a draw lands in a recorded block")
    for a, b in prop_ranges:
        bad += [f"range {a}-{b} overlaps {a2}-{b2} in {n}" for a2, b2, n in ranges
                if not (b < a2 or a > b2)]
        if any(a <= x <= b for x in singles):
            bad.append(f"range {a}-{b} contains a recorded integer")
        bad += [f"range {a}-{b} contains a draw of master {m2}" for m2, d2 in md.items()
                if any(a <= x <= b for x in d2)]
    # and the proposals against each other
    for i, (a, b) in enumerate(prop_ranges):
        for a2, b2 in prop_ranges[i + 1:]:
            if not (b < a2 or a > b2):
                bad.append(f"proposed ranges {a}-{b} and {a2}-{b2} overlap")
        for m in prop_masters:
            if any(a <= x <= b for x in draws(m)):
                bad.append(f"proposed master {m} draws into proposed {a}-{b}")
    print(f"scanned {len(texts)} files: {len(ranges)} explicit ranges, "
          f"{len(masters)} master seeds ({DRAWS:,} draws each)")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ranges", default="")
    ap.add_argument("--masters", default="")
    ap.add_argument("--exclude", action="append", default=[],
                    help="the proposing file itself, so its own blocks are not hits")
    a = ap.parse_args(argv)
    pr = [tuple(map(int, r.split("-"))) for r in a.ranges.split(",") if r]
    pm = [int(m) for m in a.masters.split(",") if m]
    bad = check(pr, pm, a.exclude)
    print("NO COLLISION" if not bad else "COLLISIONS:\n  " + "\n  ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
