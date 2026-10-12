"""Fill bars missing from the monthly 4h files with the archive's DAILY 4h files (draft
`prereg/binance-panel.md`, decision B2), only where the daily files agree with the monthly
file on overlapping bars.

For each universe contract, the grid bars missing from its monthly 4h rows (between its
first and last row) are grouped into runs of whole UTC days. For each run:
- the daily 4h files for the missing days, and for the days just before and just after the
  run (the OVERLAP days, which the monthly file has), are downloaded and verified against
  their published CHECKSUM, and quarantined under ~/Desktop as all raw files are;
- every overlap bar must agree with the monthly row: open, high, low, close, volume and
  quote volume to a relative difference of at most TOL = 1e-9, and an equal trade count;
- if they all agree, the missing bars are written to `{SYM}_4h_fill.csv`; otherwise
  nothing is filled for that run and its bars stay carried (flagged in the manifest).

Every file is in-sample (2022); nothing on or after 2025-04-01 is fetched.

    python -m data.fetch_binance_fill
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from data import fetch_binance as fb
from environments import binance_panel as bp

TOL = 1e-9
FILL_MANIFEST = fb.REPO / "data" / "binance_fill_manifest.json"
DAY = 86_400_000


def day_of(ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()


def runs_of_days(days: list[dt.date]) -> list[list[dt.date]]:
    out = []
    for d in sorted(set(days)):
        if out and (d - out[-1][-1]).days == 1:
            out[-1].append(d)
        else:
            out.append([d])
    return out


def agree(a: list, b: list) -> tuple[bool, float]:
    """Monthly row a against daily row b, both (t, o, h, l, c, v, qv, n)."""
    rel = max(abs(x - y) / max(abs(x), abs(y), 1e-300) for x, y in zip(a[1:7], b[1:7]))
    return (rel <= TOL and a[7] == b[7]), rel


def daily_rows(sym: str, day: dt.date) -> tuple[list, str | None]:
    key = f"data/futures/um/daily/klines/{sym}/4h/{sym}-4h-{day.isoformat()}.zip"
    try:
        blob = fb.verified(key)
    except Exception as e:                       # absent or unverifiable: no fill from it
        return [], f"{key}: {e.__class__.__name__}"
    fb._save(key, blob)
    return fb.parse_klines(blob), hashlib.sha256(blob).hexdigest()


def fill_symbol(sym: str) -> dict:
    kl, _ = bp.load_symbol(sym)
    have = {r[0]: r for r in kl}
    times = bp.grid()
    first, last = min(have), max(have)
    missing = [int(t) for t in times if first <= t <= last and int(t) not in have]
    rec = {"symbol": sym, "missing_bars": len(missing), "runs": []}
    fill = []
    for run in runs_of_days([day_of(t) for t in missing]):
        before, after = run[0] - dt.timedelta(days=1), run[-1] + dt.timedelta(days=1)
        r = {"days": [d.isoformat() for d in run], "overlap_days": [before.isoformat(), after.isoformat()],
             "files": {}}
        ok, worst, n_overlap = True, 0.0, 0
        for d in (before, after):
            rows, sha = daily_rows(sym, d)
            r["files"][d.isoformat()] = sha
            for row in rows:
                if row[0] in have:
                    good, rel = agree(have[row[0]], row)
                    ok &= good
                    worst = max(worst, rel)
                    n_overlap += 1
        ok &= n_overlap > 0
        cand = []
        for d in run:
            rows, sha = daily_rows(sym, d)
            r["files"][d.isoformat()] = sha
            cand += [row for row in rows if row[0] in set(missing)]
        r.update({"overlap_bars": n_overlap, "max_rel_diff": worst, "agree": bool(ok),
                  "bars_available": len(cand)})
        r["decision"] = "filled" if ok and cand else "carried (flagged)"
        if ok:
            fill += cand
        rec["runs"].append(r)
    rec["filled_bars"] = len(fill)
    if fill:
        with open(fb.INSAMPLE_DIR / f"{sym}_4h_fill.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
            w.writerows(sorted(fill))
    return rec


def main(argv=None) -> int:
    if FILL_MANIFEST.exists():
        raise SystemExit(f"{FILL_MANIFEST} exists: the fill is fetched once")
    uni = json.loads(fb.MANIFEST.read_text())["universe"]
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    recs = [fill_symbol(s) for s in uni]
    out = {"fetched_at_utc": fetched_at, "tolerance_rel": TOL,
           "symbols": [r for r in recs if r["missing_bars"]]}
    FILL_MANIFEST.write_text(json.dumps(out, indent=1) + "\n")
    for r in out["symbols"]:
        print(f"{r['symbol']:<12} missing {r['missing_bars']:3d}  filled {r['filled_bars']:3d}  "
              + "; ".join(f"{x['days'][0]}..{x['days'][-1]} {x['decision']} (overlap {x['overlap_bars']}, "
                          f"max rel diff {x['max_rel_diff']:.1e})" for x in r["runs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
