"""French holdout grading, the split (`prereg/french-holdout-grading.md`, live at
4f11f952092831d77c4d8287f083bda12b425f22; checklist step 9). Runs on the holdout host.

It cuts the value-weighted block of the pinned zip into the holdout CSV (rows dated
2020-01-01 onward), hashes it, and records its row count (which must be 1,674) and its last
date. It refuses unless the registration is an ancestor of HEAD, the zip has the registered
SHA-256, and the output does not already exist. A missing-value code in a holdout row stops
the split, and the author is asked. **The holdout CSV never leaves the host.**

    python -m experiments.french_holdout_split --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip \\
        --out ~/french_holdout/holdout.csv
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

LIVE = "4f11f952092831d77c4d8287f083bda12b425f22"
ZIP_SHA256 = "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de"
CUT = 20200101
EXPECTED_ROWS = 1674
MISSING = (-99.99, -999.0)


class SplitRefused(RuntimeError):
    pass


def live_is_ancestor(live: str = LIVE) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", live, "HEAD"],
                          capture_output=True).returncode == 0


def split_holdout(text: str, expected_rows: int | None = EXPECTED_ROWS) -> dict:
    """The value-weighted block's rows dated on or after the cut: (columns, rows, record)."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "Value Weighted Returns" in ln)
    header = next(i for i in range(start, len(lines)) if lines[i].strip().startswith(","))
    cols = [c.strip() for c in lines[header].split(",")[1:]]
    rows = []
    for ln in lines[header + 1:]:
        d = ln.split(",", 1)[0].strip()
        if not d.isdigit() or len(d) != 8:
            break
        if int(d) < CUT:
            continue
        vals = [float(x) for x in ln.split(",")[1:]]
        if len(vals) != len(cols):
            raise SplitRefused(f"{d}: {len(vals)} values for {len(cols)} columns")
        if any(v in MISSING or v <= -99.99 for v in vals):
            raise SplitRefused(f"{d}: a missing-value code in a holdout row; stop and ask the author")
        rows.append((d, vals))
    if not rows:
        raise SplitRefused("no holdout row")
    if expected_rows is not None and len(rows) != expected_rows:
        raise SplitRefused(f"{len(rows)} holdout rows, not the counted {expected_rows}")
    return {"columns": cols, "rows": rows, "first_date": rows[0][0], "last_date": rows[-1][0]}


def write_csv(path: Path, cols, rows) -> str:
    with open(path, "w") as fh:
        fh.write("date," + ",".join(cols) + "\n")
        for d, vals in rows:
            fh.write(f"{d[:4]}-{d[4:6]}-{d[6:]}," + ",".join(repr(v) for v in vals) + "\n")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not live_is_ancestor():
        raise SystemExit(f"REFUSED: the registration {LIVE} is not an ancestor of HEAD")
    z = Path(a.zip).expanduser()
    blob = z.read_bytes()
    if hashlib.sha256(blob).hexdigest() != ZIP_SHA256:
        raise SystemExit("REFUSED: the zip's SHA-256 is not the registered one")
    out = Path(a.out).expanduser()
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; the split happens once")
    zf = zipfile.ZipFile(io.BytesIO(blob))
    s = split_holdout(zf.read(zf.namelist()[0]).decode("latin-1"))
    sha = write_csv(out, s["columns"], s["rows"])
    rec = {"zip_sha256": ZIP_SHA256, "holdout_csv": str(out), "holdout_csv_sha256": sha,
           "rows": len(s["rows"]), "first_date": s["first_date"], "last_date": s["last_date"],
           "registration": LIVE}
    out.with_suffix(".split.json").write_text(json.dumps(rec, indent=1))
    print(f"holdout CSV written ({len(s['rows'])} rows, {s['first_date']} .. {s['last_date']}); SHA-256 {sha}; "
          "no return value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
