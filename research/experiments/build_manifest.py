"""Build the per-batch run manifest from the raw run directories.

    python -m experiments.build_manifest [--runs-dir runs] [--verify]

The agent arm produced 662 run directories holding 4,674 files. Nothing reads
them one at a time: every regressor the analysis uses is a per-run scalar, and
the 61,123 logged evaluate calls are consumed only as a count. This script
reduces each batch to the two tables that are actually computed on, archives
the raw logs byte-identically beside them, and leaves the directories
removable.

A batch is the real unit here: each one is a pre-registered amendment with its
own schedule file and its own model and arm allocation. Cells cross batches
(s0 control sonnet is 40 runs in b1, 30 in b2 and 30 in b3), and the analysis
already compares within and across them by hand. Making the batch the folder
makes that structure visible and leaves pooling as one deliberate step, in
runs/cells-pooled.csv.

Layout written under --runs-dir:

    README.md              the schema and how to regenerate      (hand-written)
    cells-pooled.csv       one row per cell, pooled across batches
    EXCLUSIONS.md          aborted, excluded, void, recovered    (hand-written)
    <batch>/BATCH.md       what ran and what it showed           (hand-written)
    <batch>/runs.csv       one row per run, load_run()'s fields exactly
    <batch>/cells.csv      one row per cell within this batch
    <batch>/raw.tar.gz     the run directories, byte-identical
    <batch>/SHA256SUMS     a checksum per archived file

Every CSV cell is JSON-encoded, so the tables round-trip through
load_run()'s types exactly -- str, float, bool, None and the three list-valued
fields alike. These are machine input, not reading material; BATCH.md is the
part written for a person. --verify re-reads what was written and asserts it
matches load_run() field for field, which is what licenses deleting the
directories.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tarfile
from pathlib import Path

from experiments.analyze_agent import (PREFIXES, cell_label, cells_of, crps_gaussian,
                                       gap, graded, load_run, med_iqr)

# Each batch is one pre-registered allocation. Seed ranges come from the
# schedule files under experiments/, which record the amendment that authorized
# them. analyze_agent.batch_of() collapses b4 and b5 into one label because it
# only ever needed contemporaneous comparison sets; they are different
# amendments and different models, so they are separate folders here.
BATCHES = [
    ("b1-baseline",  lambda s: s < 80,
     "the original s0 control/gate arm, Sonnet, before the model tag existed"),
    ("b2-arms",      lambda s: 80 <= s < 320 or s == 500,
     "amendment 4: the count and budget arms, and the first s3 cells at sigma=1"),
    ("b3-models",    lambda s: 320 <= s < 500,
     "amendment 7: the pushed arm, Sonnet against Fable"),
    ("b4-s3-recal",  lambda s: 501 <= s < 581,
     "amendment 9: s3 re-run at the recalibrated sigma=194.407, Sonnet"),
    ("b5-opus",      lambda s: 581 <= s <= 660,
     "amendments 11 and 12: s3 at the recalibrated sigma, Opus (the Fable arm was aborted)"),
]

# Every filename a run directory can carry. error.json appears once, on the
# opus run whose harness died before writing usage.jsonl; it is the record of
# why that run has no reported model string, so it is evidence and is archived.
# The archive is checked against `git ls-files runs/` -- a name missing here
# would be dropped silently, which is the one way this script can lose data.
RUN_FILES = ("config.json", "considered.json", "error.json", "oos.json",
             "stated.json", "transcript.jsonl", "usage.jsonl", "verdict.json",
             "verdict_v1.json", "no_submit.json", "void.json")


def batch_for(seed: int) -> str | None:
    for name, pred, _ in BATCHES:
        if pred(seed):
            return name
    return None


# ------------------------------------------------------------------ tables

def write_rows(path: Path, rows: list[dict], fields: list[str]) -> None:
    """JSON-encode every cell so the table round-trips load_run()'s types."""
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(fields)
        for r in rows:
            w.writerow([json.dumps(r.get(f)) for f in fields])


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="") as fh:
        rd = csv.reader(fh)
        fields = next(rd)
        return [{f: json.loads(v) for f, v in zip(fields, row)} for row in rd]


def cell_rows(runs: list[dict]) -> list[dict]:
    """One row per cell: the medians and counts per_cell_block reports, so the
    readable summary needs no access to the per-run table."""
    out = []
    for key, rs in cells_of(runs).items():
        g = graded(rs)
        row = {"cell": cell_label(key), "config": key[0], "arm": key[1],
               "budget": key[2], "model": key[3], "sigma": key[4],
               "n": len(rs), "n_graded": len(g)}
        for name, vals in (("n_evaluated", [r["n_evaluated"] for r in rs]),
                           ("stated_mean", [r["stated_mean"] for r in g]),
                           ("stated_sd", [r["stated_sd"] for r in g]),
                           ("oos", [r["oos"] for r in g if r["oos"] is not None]),
                           ("submitted_sr_is", [r["submitted_sr_is"] for r in g]),
                           ("considered", [r["considered"] for r in rs
                                           if r["considered"] is not None]),
                           ("deflation_gap", [gap(r) for r in g])):
            if vals:
                med, lo, hi = med_iqr(vals)
                row[f"{name}_median"], row[f"{name}_q1"], row[f"{name}_q3"] = med, lo, hi
        crps = [crps_gaussian(r["stated_mean"], r["stated_sd"], r["oos"])
                for r in g if r["oos"] is not None]
        if crps:
            row["crps_median"] = med_iqr(crps)[0]
        counts: dict[str, int] = {}
        for r in rs:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
        row["verdicts"] = counts
        row["cost_usd"] = round(sum(r["cost_usd"] for r in rs), 4)
        out.append(row)
    return out


# ------------------------------------------------------------------ archive

def archive(batch_dir: Path, dirs: list[Path]) -> None:
    """Tar the run directories byte-identically and record a checksum each, so
    the evidence claim survives the directories being removed."""
    sums = []
    with tarfile.open(batch_dir / "raw.tar.gz", "w:gz") as tar:
        for d in sorted(dirs):
            for name in RUN_FILES:
                p = d / name
                if not p.exists():
                    continue
                tar.add(p, arcname=f"{d.name}/{name}")
                sums.append((hashlib.sha256(p.read_bytes()).hexdigest(),
                             f"{d.name}/{name}"))
    (batch_dir / "SHA256SUMS").write_text(
        "".join(f"{h}  {n}\n" for h, n in sums))


def skeleton(batch_dir: Path, name: str, note: str, rows, cells) -> None:
    """Seed BATCH.md once. Never overwritten: the tables regenerate, the prose
    does not."""
    p = batch_dir / "BATCH.md"
    if p.exists():
        return
    seeds = sorted(r["seed_index"] for r in rows)
    lines = [f"# {name}", "", f"{note.capitalize()}.", "",
             f"- **Runs**: {len(rows)}, seeds {seeds[0]}-{seeds[-1]}",
             f"- **Cells**: {len(cells)}",
             f"- **Cost**: ${sum(r['cost_usd'] for r in rows):,.2f}", "",
             "| cell | n | evaluations | stated mean | verdicts |",
             "|---|---|---|---|---|"]
    for c in cells:
        lines.append(f"| {c['cell']} | {c['n']} | {c.get('n_evaluated_median', '-')} "
                     f"| {c.get('stated_mean_median', '-')} | {c['verdicts']} |")
    lines += ["", "## What it showed", "", "_To be written._", ""]
    p.write_text("\n".join(lines))


# ------------------------------------------------------------------ main

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default="runs")
    ap.add_argument("--verify", action="store_true",
                    help="re-read the written tables and assert they match load_run()")
    a = ap.parse_args()
    root = Path(a.runs_dir)

    dirs = sorted(d for d in root.iterdir()
                  if d.is_dir() and d.name.startswith(PREFIXES))
    if not dirs:
        raise SystemExit(f"no runs matching {PREFIXES} under {root}")

    loaded: dict[str, list[dict]] = {}
    by_dir: dict[str, list[Path]] = {}
    unassigned, failed = [], []
    for d in dirs:
        try:
            r = load_run(d)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            failed.append(f"{d.name} ({type(e).__name__})")
            continue
        b = batch_for(r["seed_index"])
        if b is None:
            unassigned.append(d.name)
            continue
        loaded.setdefault(b, []).append(r)
        by_dir.setdefault(b, []).append(d)

    fields = list(loaded[next(iter(loaded))][0].keys())
    pooled: list[dict] = []
    for name, _, note in BATCHES:
        rows = loaded.get(name, [])
        if not rows:
            continue
        bd = root / name
        bd.mkdir(exist_ok=True)
        rows.sort(key=lambda r: r["seed_index"])
        cells = cell_rows(rows)
        write_rows(bd / "runs.csv", rows, fields)
        write_rows(bd / "cells.csv", cells, sorted({k for c in cells for k in c}))
        archive(bd, by_dir[name])
        skeleton(bd, name, note, rows, cells)
        pooled.extend(rows)
        print(f"{name:14} {len(rows):4} runs  {len(cells)} cells  "
              f"-> runs.csv, cells.csv, raw.tar.gz, SHA256SUMS")

    allcells = cell_rows(pooled)
    write_rows(root / "cells-pooled.csv", allcells,
               sorted({k for c in allcells for k in c}))
    print(f"\ncells-pooled.csv  {len(allcells)} cells over {len(pooled)} runs")
    if unassigned:
        print(f"unassigned to any batch (see EXCLUSIONS.md): {unassigned}")
    if failed:
        print(f"did not load: {failed}")

    if a.verify:
        bad = 0
        for name, _, _ in BATCHES:
            p = root / name / "runs.csv"
            if not p.exists():
                continue
            for want, got in zip(sorted(loaded[name], key=lambda r: r["seed_index"]),
                                 read_rows(p)):
                for f in fields:
                    if want.get(f) != got.get(f):
                        print(f"MISMATCH {got['run_id']}.{f}: "
                              f"{want.get(f)!r} != {got.get(f)!r}")
                        bad += 1
        print(f"verify: {bad} mismatched fields" if bad
              else "verify: every field round-trips")
        raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
