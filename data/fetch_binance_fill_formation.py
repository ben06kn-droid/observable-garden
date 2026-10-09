"""Fill the bars missing from a 4h FORMATION universe's monthly files with the archive's
DAILY 4h files, exactly as decision B2 did for the 2021-10 universe
(`data/fetch_binance_fill.py`). Run for the chosen variant, formation 2021-01 (author,
2026-10-09).

For each contract, the grid bars missing from its monthly 4h rows, between its first and
last row, are grouped into runs of whole UTC days. For each run:
- the daily 4h files for the missing days, and for the day just before and just after the
  run, are verified against their published CHECKSUM and quarantined;
- every overlap bar must agree with the monthly row: open, high, low, close, volume and
  quote volume to a relative difference of at most 1e-9, and an equal trade count;
- if they all agree, the missing bars are written to `{SYM}_4h_fill.csv`, with their
  taker-buy columns in `{SYM}_4h_fill_taker.csv`; otherwise the run is carried and flagged.

Every file is in-sample; nothing on or after 2025-04-01 is fetched.

    python -m data.fetch_binance_fill_formation --formation 2021-01
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json

from data import fetch_binance as fb
from data import fetch_binance_daily as fd             # installs the retrying _get
from data import fetch_binance_fill as F
from data import rebuild_binance_taker as rt


def daily_rows(sym: str, day: dt.date):
    key = f"data/futures/um/daily/klines/{sym}/4h/{sym}-4h-{day.isoformat()}.zip"
    if f"{day.isoformat()}" >= "2025-04-01":
        raise fb.FetchRefused(f"{key}: not in-sample")
    try:
        blob = fb.verified(key)
    except fb.FetchRefused:
        raise
    except Exception as e:                       # absent: no fill from it
        return [], f"{key}: {e.__class__.__name__}"
    fb._save(key, blob)
    return rt.parse_klines_taker(blob), hashlib.sha256(blob).hexdigest()


def fill_symbol(sym: str, directory, times) -> dict:
    from environments import binance_panel as bp
    kl, _ = bp.load_symbol(sym, directory, "4h")
    have = {r[0]: r for r in kl}
    first, last = min(have), max(have)
    missing = [int(t) for t in times if first <= t <= last and int(t) not in have]
    rec = {"symbol": sym, "missing_bars": len(missing), "runs": []}
    fill = []
    miss = set(missing)
    for run in F.runs_of_days([F.day_of(t) for t in missing]):
        before, after = run[0] - dt.timedelta(days=1), run[-1] + dt.timedelta(days=1)
        r = {"days": [d.isoformat() for d in run], "overlap_days": [before.isoformat(), after.isoformat()],
             "files": {}}
        ok, worst, n_overlap = True, 0.0, 0
        for d in (before, after):
            rows, sha = daily_rows(sym, d)
            r["files"][d.isoformat()] = sha
            for row in rows:
                if row[0] in have:
                    good, rel = F.agree(have[row[0]], row[:8])
                    ok &= good
                    worst = max(worst, rel)
                    n_overlap += 1
        ok &= n_overlap > 0
        cand = []
        for d in run:
            rows, sha = daily_rows(sym, d)
            r["files"][d.isoformat()] = sha
            cand += [row for row in rows if row[0] in miss]
        r.update({"overlap_bars": n_overlap, "max_rel_diff": worst, "agree": bool(ok),
                  "bars_available": len(cand)})
        r["decision"] = "filled" if ok and cand else "carried (flagged)"
        if ok:
            fill += cand
        rec["runs"].append(r)
    rec["filled_bars"] = len(fill)
    if fill:
        with open(directory / f"{sym}_4h_fill.csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
            w.writerows(sorted(x[:8] for x in fill))
        rec["fill_taker_sha256"] = rt.write_taker(directory / f"{sym}_4h_fill_taker.csv", fill)
    return rec


def main(argv=None) -> int:
    from experiments.binance_design_v2_4h import spec_for
    from environments import binance_panel as bp
    ap = argparse.ArgumentParser()
    ap.add_argument("--formation", required=True)
    a = ap.parse_args(argv)
    manifest = fb.REPO / "data" / f"binance_4h_{a.formation}_fill_manifest.json"
    if manifest.exists():
        raise SystemExit(f"{manifest} exists: the fill is fetched once")
    symbols, directory, spec, _ = spec_for(f"4h-{a.formation}")
    times = bp.grid(spec)
    recs = [fill_symbol(s, directory, times) for s in symbols]
    out = {"fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "formation": a.formation, "tolerance_rel": F.TOL, "symbols": [r for r in recs if r["missing_bars"]]}
    manifest.write_text(json.dumps(out, indent=1) + "\n")
    for r in out["symbols"]:
        print(f"{r['symbol']:<12} missing {r['missing_bars']:3d}  filled {r['filled_bars']:3d}  "
              + "; ".join(f"{x['days'][0]}..{x['days'][-1]} {x['decision']} (overlap {x['overlap_bars']}, "
                          f"max rel diff {x['max_rel_diff']:.1e})" for x in r["runs"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
