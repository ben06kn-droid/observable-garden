"""French long history, item a (draft `prereg/french-long-history.md`): count the
library's missing-value flags per industry per year in the rows before 2008-12-29. COUNTS
ONLY. A cell is "missing" iff its value is -99.99 or -999. No value is printed, stored or
compared other than against those two codes. Rows dated 2008-12-29 or later are skipped
by their date field before any value is parsed.

It runs where the French zip is: the zip's SHA-256 must be the registered
8f394fe3...40de (or a new fetch's, named on the command line).

    python -m data.count_french_missing --zip <path to 49_Industry_Portfolios_daily_CSV.zip> \\
        --out french_missing_counts.json

Output: for each year, the number of rows, and per industry the number of missing cells;
the first date on which all 49 industries are present; the first date each industry is
present without a later gap.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

REGISTERED_ZIP = "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de"
STOP = 20081229
CODES = ("-99.99", "-999", "-999.0", "-99.990")


def counts(text: str) -> dict:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "Value Weighted Returns" in ln)
    header = next(i for i in range(start, len(lines)) if lines[i].strip().startswith(","))
    cols = [c.strip() for c in lines[header].split(",")[1:]]
    years, first_all, present_since = {}, None, {c: None for c in cols}
    for ln in lines[header + 1:]:
        d = ln.split(",", 1)[0].strip()
        if not d.isdigit() or len(d) != 8:
            break
        if int(d) >= STOP:
            continue                                   # never parsed
        cells = [x.strip() for x in ln.split(",")[1:]]
        miss = [c in CODES for c in cells]
        y = years.setdefault(d[:4], {"rows": 0, "missing": {c: 0 for c in cols}})
        y["rows"] += 1
        for c, m in zip(cols, miss):
            y["missing"][c] += int(m)
            if m:
                present_since[c] = None
            elif present_since[c] is None:
                present_since[c] = d
        if first_all is None and not any(miss):
            first_all = d
    return {"industries": cols, "years": years, "first_date_all_present": first_all,
            "present_without_later_gap_from": present_since, "codes": list(CODES), "stop_before": STOP}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--zip-sha256", default=REGISTERED_ZIP)
    a = ap.parse_args(argv)
    blob = Path(a.zip).expanduser().read_bytes()
    if hashlib.sha256(blob).hexdigest() != a.zip_sha256:
        raise SystemExit("REFUSED: the zip's SHA-256 is not the one named")
    z = zipfile.ZipFile(io.BytesIO(blob))
    rec = counts(z.read(z.namelist()[0]).decode("latin-1"))
    rec["zip_sha256"] = a.zip_sha256
    Path(a.out).write_text(json.dumps(rec, indent=1))
    print(f"counts written to {a.out}: {len(rec['years'])} years; first date all 49 present "
          f"{rec['first_date_all_present']}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
