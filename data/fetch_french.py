"""One fetch of Ken French's 49 Industry Portfolios, daily (draft `prereg/french-panel.md`).

What it does, once:
1. GETs `49_Industry_Portfolios_daily_CSV.zip`, hashes it (SHA-256), and records its size,
   `Last-Modified` header and the fetch time in `data/french_manifest.json`.
2. Writes the zip, unopened by any loader, to a quarantine directory OUTSIDE the
   repository and under `~/Desktop`, which `data/etf_loader.py` already refuses. Before any
   agent session runs on this panel the zip moves to the holdout host and is deleted here,
   its hash checked on arrival (draft, section f).
3. From the value-weighted block, writes the in-sample CSV only: the 253 warm-up rows
   before the first feature row, then every row through 2019-12-31. The first feature row
   is the one whose earned return (dated two rows later) is the first scored date,
   2010-01-04.
4. Rows dated on or after 2020-01-01 are COUNTED from their date field only; their values
   are never parsed, printed or stored.

Missing-value codes (-99.99, -999) in the rows written are counted per industry and the
fetch refuses to write the CSV if any is present.

    python -m data.fetch_french
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import ssl
import urllib.request
import zipfile
from pathlib import Path

URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
       "49_Industry_Portfolios_daily_CSV.zip")
CUT = 20200101                       # first holdout date
FIRST_SCORED = 20100104              # first scored (earned-return) date
WARM = 252 + 1                       # the ETF builder's warm-up
LAG = 2                              # feature row t earns the return dated t + 2
MISSING = (-99.99, -999.0)
REPO = Path(__file__).resolve().parent.parent
INSAMPLE_DIR = REPO / "data" / "raw" / "french_insample"
INSAMPLE_CSV = INSAMPLE_DIR / "french49_vw_daily.csv"
MANIFEST = REPO / "data" / "french_manifest.json"
QUARANTINE = Path.home() / "Desktop" / "og-quarantine" / "french"


class FetchRefused(RuntimeError):
    pass


def _get(url: str) -> tuple[bytes, dict]:
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={"User-Agent": "observable-garden-french"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        return r.read(), dict(r.headers)


def split_text(text: str) -> dict:
    """The value-weighted block, split at the cut. Holdout lines are counted from their
    date field only. Returns columns, the in-sample rows (date, values) from the warm-up
    start, and counts."""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "Value Weighted Returns" in ln)
    header = next(i for i in range(start, len(lines)) if lines[i].strip().startswith(","))
    cols = [c.strip() for c in lines[header].split(",")[1:]]
    pre, n_after = [], 0
    for ln in lines[header + 1:]:
        d = ln.split(",", 1)[0].strip()
        if not d.isdigit() or len(d) != 8:
            break                                    # end of the value-weighted block
        if int(d) >= CUT:
            n_after += 1                             # counted; the line is not parsed further
            continue
        pre.append((d, ln))
    dates = [d for d, _ in pre]
    if str(FIRST_SCORED) not in dates:
        raise FetchRefused(f"{FIRST_SCORED} is not a row of the file")
    i_scored = dates.index(str(FIRST_SCORED))
    i_feat = i_scored - LAG                          # first feature row
    i_warm = i_feat - WARM                           # first warm-up row
    if i_warm < 0:
        raise FetchRefused("not enough rows before the first feature row for the warm-up")
    rows = []
    for d, ln in pre[i_warm:]:
        vals = [float(x) for x in ln.split(",")[1:]]
        if len(vals) != len(cols):
            raise FetchRefused(f"{d}: {len(vals)} values for {len(cols)} columns")
        rows.append((d, vals))
    missing = {c: sum(1 for _, v in rows if v[j] in MISSING or v[j] <= -99.99)
               for j, c in enumerate(cols)}
    return {"columns": cols, "rows": rows, "n_holdout_lines": n_after,
            "n_unused_before": i_warm, "warm_start": pre[i_warm][0],
            "first_feature_row": pre[i_feat][0], "first_scored": pre[i_scored][0],
            "last_insample": pre[-1][0], "missing": {c: n for c, n in missing.items() if n}}


def write_csv(path: Path, cols: list, rows: list) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        fh.write("date," + ",".join(cols) + "\n")
        for d, vals in rows:
            iso = f"{d[:4]}-{d[4:6]}-{d[6:]}"
            fh.write(iso + "," + ",".join(repr(v) for v in vals) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    for p in (MANIFEST, INSAMPLE_CSV, QUARANTINE / Path(URL).name):
        if p.exists():
            raise SystemExit(f"{p} exists: the fetch happens once and is not repeated")
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    blob, headers = _get(URL)
    sha = hashlib.sha256(blob).hexdigest()
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    (QUARANTINE / Path(URL).name).write_bytes(blob)
    zf = zipfile.ZipFile(io.BytesIO(blob))
    inner = zf.namelist()
    text = zf.read(inner[0]).decode("latin-1")
    s = split_text(text)
    if s["missing"]:
        raise SystemExit(f"missing-value codes in the in-sample rows: {s['missing']}; not "
                         "written. Stop and ask.")
    csv_sha = write_csv(INSAMPLE_CSV, s["columns"], s["rows"])
    man = {"source": URL, "fetched_at_utc": fetched_at,
           "last_modified": headers.get("Last-Modified"), "zip_bytes": len(blob),
           "zip_sha256": sha, "zip_members": inner,
           "quarantine": str(QUARANTINE / Path(URL).name),
           "block": "Average Value Weighted Returns -- Daily", "units": "percent",
           "columns": s["columns"],
           "insample_csv": str(INSAMPLE_CSV.relative_to(REPO)), "insample_csv_sha256": csv_sha,
           "insample_rows": len(s["rows"]), "warm_start": s["warm_start"],
           "first_feature_row": s["first_feature_row"], "first_scored": s["first_scored"],
           "last_insample": s["last_insample"], "rows_before_warm_start_unused": s["n_unused_before"],
           "holdout_lines_counted_only": s["n_holdout_lines"],
           "missing_value_codes_in_insample": s["missing"] or "none"}
    MANIFEST.write_text(json.dumps(man, indent=1) + "\n")
    print(json.dumps({k: v for k, v in man.items() if k != "columns"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
