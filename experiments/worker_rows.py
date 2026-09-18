"""Assign schedule rows to parallel workers (prereg AGENT_PROMPTS.md 6, amendment 6).

Rows are dealt round-robin *within each block*, not strided over the flat row
order. Striding splits the design: measured on schedule_240.txt from line 11,
--workers 4 gives each worker only one budget dose and --workers 8 leaves four
workers with no budget row at all, which would confound the dose-response arm
with worker identity. Dealing within a block gives every worker the same
rotation across all eight cells at any N.

    python -m experiments.worker_rows --schedule F --start 11 --workers 4 --worker 2

prints that worker's schedule line indices, one per line, in ascending order --
so a worker still sees the blocks in the rotation order the schedule fixes.
"""
from __future__ import annotations

from pathlib import Path


def read_rows(path) -> list[list[str]]:
    """The data rows only, in file order. Comments and blanks are dropped, so an
    index here is the same index run_arms.sh counts with --start."""
    rows = []
    for line in Path(path).read_text().splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            rows.append(s.split())
    return rows


def block_of(row: list[str]) -> tuple[str, str, str]:
    """The design cell: config, arm, dose.

    The model column is deliberately not part of the block. Batch 2 is one
    model, and batch 3 crosses models inside a cell, where the rotation that
    matters is still over arms and doses."""
    return (row[1], row[2], row[3])


def assign(rows: list[list[str]], start: int = 0, workers: int = 1) -> list[list[int]]:
    """Line indices for each worker, dealt round-robin within each block.

    Deterministic in (rows, start, workers) alone, which is what makes a stopped
    worker resumable: re-running with the same three reproduces its row set."""
    if workers < 1:
        raise ValueError(f"workers must be >= 1, got {workers}")
    if start < 0 or start > len(rows):
        raise ValueError(f"start {start} is outside the schedule (0..{len(rows)})")
    out: list[list[int]] = [[] for _ in range(workers)]
    dealt: dict[tuple[str, str, str], int] = {}
    for n in range(start, len(rows)):
        b = block_of(rows[n])
        j = dealt.get(b, 0)
        dealt[b] = j + 1
        out[j % workers].append(n)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--worker", type=int, required=True)
    a = ap.parse_args(argv)

    if not 0 <= a.worker < a.workers:
        raise SystemExit(f"worker {a.worker} is outside 0..{a.workers - 1}")
    for n in assign(read_rows(a.schedule), a.start, a.workers)[a.worker]:
        print(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
