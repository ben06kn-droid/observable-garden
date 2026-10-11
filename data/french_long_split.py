"""French long history: the host-side cuts (draft `prereg/french-long-history.md`, custody).
Runs on the holdout host, where the registered zip is. **It refuses to run until the
registration is live** (REGISTRATION below is set by the commit that makes it live, and must
be an ancestor of HEAD).

Cuts of the value-weighted block of the registered zip (SHA-256 8f394fe3...40de):
- `b1`         1926-07-01 .. 1989-12-31  -> the B1 in-sample CSV (copied to the laptop and box);
- `b1-holdout` 1990-01-01 .. 1995-12-31  -> B1's graded window (stays on the host);
- `b2-extra`   1990-01-01 .. 2008-12-26  -> the rows B2 adds before the existing 2009-2019
  in-sample CSV (copied only after B1's grading is committed).
B2's graded window is the existing 2020+ holdout CSV on the host (`data/french_holdout_split.py`).

A cut never writes a row outside its window: rows after the window's end are skipped by their
date field before any value is parsed. Missing-value codes (-99.99, -999) are written as empty
cells. With each cut it writes a record (JSON): the CSV's SHA-256 and row count, its first and
last dates, and COUNTS ONLY: missing cells per industry per year, the first date all 49 are
present, each industry's entry date by rule (ii). **No value is printed.**

    python -m data.french_long_split --cut b1 --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b1_insample.csv
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

REGISTRATION = "756af89c0b7c7663bac184364b722cdb16a73807"
ZIP_SHA256 = "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de"
CUTS = {"b1": (19260701, 19891231), "b1-holdout": (19900101, 19951231), "b2-extra": (19900101, 20081226)}
CODES = ("-99.99", "-999", "-999.0", "-99.990")


class CutRefused(RuntimeError):
    pass


def cut(text: str, lo: int, hi: int) -> dict:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "Value Weighted Returns" in ln)
    header = next(i for i in range(start, len(lines)) if lines[i].strip().startswith(","))
    cols = [c.strip() for c in lines[header].split(",")[1:]]
    rows, years, first_all = [], {}, None
    for ln in lines[header + 1:]:
        d = ln.split(",", 1)[0].strip()
        if not d.isdigit() or len(d) != 8:
            break
        if int(d) < lo or int(d) > hi:
            continue                                  # never parsed
        cells = [x.strip() for x in ln.split(",")[1:]]
        if len(cells) != len(cols):
            raise CutRefused(f"{d}: {len(cells)} cells for {len(cols)} columns")
        miss = [c in CODES for c in cells]
        y = years.setdefault(d[:4], {"rows": 0, "missing": {c: 0 for c in cols}})
        y["rows"] += 1
        for c, m in zip(cols, miss):
            y["missing"][c] += int(m)
        if first_all is None and not any(miss):
            first_all = d
        rows.append((d, ["" if m else c for c, m in zip(cells, miss)]))
    if not rows:
        raise CutRefused("no row in the window")
    if int(rows[-1][0]) > hi or int(rows[0][0]) < lo:
        raise CutRefused("a row outside the window")
    entry = {}
    for j, c in enumerate(cols):
        last_gap = max((k for k, (_, v) in enumerate(rows) if v[j] == ""), default=-1)
        entry[c] = rows[last_gap + 1][0] if last_gap + 1 < len(rows) else None
    return {"columns": cols, "rows": rows, "counts": {"years": years, "first_date_all_present": first_all,
                                                      "entry_rule_ii": entry}}


def write_csv(path: Path, cols, rows) -> str:
    with open(path, "w") as fh:
        fh.write("date," + ",".join(cols) + "\n")
        for d, vals in rows:
            fh.write(f"{d[:4]}-{d[4:6]}-{d[6:]}," + ",".join(vals) + "\n")
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True, choices=list(CUTS))
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not REGISTRATION:
        raise SystemExit("REFUSED: the registration is not live (REGISTRATION is unset)")
    if subprocess.run(["git", "merge-base", "--is-ancestor", REGISTRATION, "HEAD"], capture_output=True).returncode:
        raise SystemExit(f"REFUSED: the registration {REGISTRATION} is not an ancestor of HEAD")
    blob = Path(a.zip).expanduser().read_bytes()
    if hashlib.sha256(blob).hexdigest() != ZIP_SHA256:
        raise SystemExit("REFUSED: the zip's SHA-256 is not the registered one")
    out = Path(a.out).expanduser()
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; each cut is made once")
    z = zipfile.ZipFile(io.BytesIO(blob))
    lo, hi = CUTS[a.cut]
    c = cut(z.read(z.namelist()[0]).decode("latin-1"), lo, hi)
    sha = write_csv(out, c["columns"], c["rows"])
    rec = {"cut": a.cut, "window": [lo, hi], "zip_sha256": ZIP_SHA256, "csv": str(out), "csv_sha256": sha,
           "rows": len(c["rows"]), "first_date": c["rows"][0][0], "last_date": c["rows"][-1][0],
           "registration": REGISTRATION, **c["counts"]}
    out.with_suffix(".cut.json").write_text(json.dumps(rec, indent=1))
    print(f"{a.cut}: {len(c['rows'])} rows {c['rows'][0][0]} .. {c['rows'][-1][0]}; SHA-256 {sha}; "
          f"record {out.with_suffix('.cut.json').name}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
