"""Resume by seed for the planted drivers: which seeds a results file already holds.

Shared by `experiments/planted_edge.py` and `experiments/planted_twins.py` so the two
drivers cannot disagree about what counts as a finished seed.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_done(path: Path) -> set:
    """Seeds already on record, for resume. A process killed mid-write leaves a
    TRUNCATED LAST LINE with no newline: it is removed, and the file rewritten without
    it, so the next record is not glued onto it. A malformed line anywhere else is real
    corruption and raises."""
    if not path.exists():
        return set()
    text = path.read_text()
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    done, keep = set(), []
    for i, ln in enumerate(lines):
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                print(f"  resume: dropped a truncated last line ({len(ln)} chars); "
                      "its seed is redone", flush=True)
                path.write_text("".join(k + "\n" for k in keep))
                break
            raise SystemExit(f"{path}: line {i + 1} is malformed and is not the last line; "
                             "that is corruption, not an interrupted write")
        done.add(rec["seed"])
        keep.append(ln)
    return done
