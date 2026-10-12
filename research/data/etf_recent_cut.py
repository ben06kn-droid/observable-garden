"""ETF recent panel: the host cut (`prereg/etf-recent-panel.md`, sections b, c and f). **Runs on
the holdout host, by the author. It refuses to run until the registration is live**, refuses
an existing output, and checks every raw response against its SHA-256 in `fetch.json`.

From the raw responses of `data/fetch_etf_recent.py` it applies the inclusion rule on the
formation window 2005-01-03 .. 2014-12-31 only (section b):
1. a bar on EVERY XNYS session of the window (no gap; a bar whose adjusted close is null is a
   missing session);
2. the median daily share volume over the window at least 500,000;
3. ticker, merger or structure changes: NOT verified (recorded as such; nothing applied);
5. at least 30 included.
Then the in-sample checks:
- a candidate with no data at all (a failed or empty response) -> the cut REFUSES (nothing
  runs; the author is asked; the old fetch is not used to check it);
- fewer than 30 included -> the cut REFUSES;
- an included ETF missing any XNYS session in 2015-01-02 .. 2024-12-31 (a gap, or a death after
  2014) -> the cut REFUSES, so the runner never sees an in-sample gap.
On a refusal the record is written (counts and dates only) and no CSV is.

**Rows dated 2025-01-01 or later are never parsed beyond their date field.** The JSON is read
with numbers kept as their source text; only in-sample rows' text is converted, and holdout
rows are counted from their timestamps alone. The last fetched session is the last XNYS
session strictly before the fetch date in New York; later bars are ignored.

On success it writes <out>/<TICKER>.csv for each included ETF (header `date,adjclose,volume`;
XNYS sessions 2005-01-03 .. 2024-12-31; adjclose as the response gives it; volume an integer)
and the record <out>.cut.json. **No value is printed.**

    python -m data.etf_recent_cut --raw ~/etf_recent/raw --out ~/etf_recent/insample
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

from data.fetch_etf import TICKERS
from data.fetch_etf_recent import REGISTRATION, registration_live

NY = ZoneInfo("America/New_York")
FORM = (dt.date(2005, 1, 3), dt.date(2014, 12, 31))
LATER = (dt.date(2015, 1, 2), dt.date(2024, 12, 31))
INSAMPLE_END = dt.date(2024, 12, 31)
HOLDOUT_START = dt.date(2025, 1, 1)
MIN_MEDIAN_SHARE_VOLUME = 500_000
MIN_PANEL = 30


class CutRefused(RuntimeError):
    pass


def sessions(a: dt.date, b: dt.date) -> list[dt.date]:
    import exchange_calendars as xc
    cal = xc.get_calendar("XNYS", start="2004-01-01", end=(b + dt.timedelta(days=400)).isoformat())
    return [d.date() for d in cal.sessions_in_range(a.isoformat(), b.isoformat())]


def last_session_before(day: dt.date) -> dt.date:
    """The last XNYS session strictly before `day`."""
    return sessions(day - dt.timedelta(days=20), day - dt.timedelta(days=1))[-1]


def parse(raw: bytes):
    """(timestamps, adjclose tokens, volume tokens), numbers kept as source text; None if the
    response holds no bars."""
    try:
        res = json.loads(raw, parse_float=lambda s: s, parse_int=lambda s: s)["chart"]["result"]
        r = res[0]
        ts = r.get("timestamp") or []
        adj = r["indicators"]["adjclose"][0]["adjclose"]
        vol = r["indicators"]["quote"][0]["volume"]
    except (ValueError, KeyError, TypeError, IndexError):
        return None
    if not ts:
        return None
    return ts, adj, vol


def one(tk: str, raw: bytes | None, last: dt.date, form_s: list, later_s: list) -> tuple[dict, list]:
    """The record for one candidate, and its in-sample rows [(date, adj text, volume int|None)]."""
    p = parse(raw) if raw is not None else None
    if p is None:
        return {"status": "no data", "bars_total": 0, "included": False, "reason": "no data in this fetch"}, []
    ts, adj, vol = p
    rows, seen, dup, off, holdout, after = {}, set(), 0, 0, 0, 0
    form_set, later_set = set(form_s), set(later_s)
    for k, t in enumerate(ts):
        d = dt.datetime.fromtimestamp(int(t), NY).date()
        if d >= HOLDOUT_START:                       # the date field only; no value is touched
            if d <= last:
                holdout += 1
            else:
                after += 1
            continue
        if d in seen:
            dup += 1
            continue
        seen.add(d)
        if d not in form_set and d not in later_set:
            off += 1                                 # before 2005-01-03, or not an XNYS session
            continue
        a = adj[k] if k < len(adj) else None
        v = vol[k] if k < len(vol) else None
        if a is None:
            continue                                 # a null adjusted close is a missing session
        rows[d] = (a, int(v) if v is not None else None)
    miss_form = [s for s in form_s if s not in rows]
    miss_later = [s for s in later_s if s not in rows]
    vols = [rows[s][1] for s in form_s if s in rows and rows[s][1] is not None]
    med = float(statistics.median(vols)) if vols else 0.0
    fails = ([] if not miss_form else ["1: a missing session in 2005-01-03..2014-12-31"]) + \
            ([] if med >= MIN_MEDIAN_SHARE_VOLUME else ["2: median share volume below 500,000"])
    first = min(seen) if seen else None
    rec = {"status": "ok", "bars_total": len(ts), "first_date": first.isoformat() if first else None,
           "missing_sessions_2005_2014": len(miss_form),
           "first_missing_2005_2014": miss_form[0].isoformat() if miss_form else None,
           "median_volume_2005_2014": med, "volume_nulls_2005_2014": sum(1 for s in form_s if s in rows and rows[s][1] is None),
           "included": not fails, "reason": "; ".join(fails) if fails else "passes items 1 and 2",
           "missing_sessions_2015_2024": len(miss_later),
           "first_missing_2015_2024": miss_later[0].isoformat() if miss_later else None,
           "duplicate_dates": dup, "off_calendar_or_pre_2005_bars": off,
           "holdout_rows": holdout, "bars_after_last_session": after}
    out = [(s, *rows[s]) for s in form_s + later_s if s in rows] if not fails else []
    return rec, out


def cut(raw_dir: Path, out: Path) -> dict:
    """The cut. Writes the record always and the CSVs only on success; raises CutRefused after
    writing the record on a refusal."""
    rec_path = out.with_name(out.name + ".cut.json")
    if out.exists() or rec_path.exists():
        raise CutRefused(f"{out} or its record exists; the cut is made once")
    fetch_path = raw_dir / "fetch.json"
    fetch = json.loads(fetch_path.read_text())
    fetch_day = dt.datetime.fromisoformat(fetch["fetch_start_utc"]).astimezone(NY).date()
    last = last_session_before(fetch_day)
    form_s, later_s = sessions(*FORM), sessions(*LATER)
    per, data = {}, {}
    for tk in TICKERS:
        e = fetch["tickers"].get(tk, {})
        f = raw_dir / f"{tk}.json"
        raw = f.read_bytes() if (f.exists() and e.get("http") == "200") else None
        if raw is not None and hashlib.sha256(raw).hexdigest() != e.get("sha256"):
            raise CutRefused(f"{tk}.json is not its fetch record's SHA-256")
        per[tk], data[tk] = one(tk, raw, last, form_s, later_s)
    included = [tk for tk in TICKERS if per[tk]["included"]]
    refusals = []
    nodata = [tk for tk in TICKERS if per[tk]["status"] == "no data"]
    if nodata:
        refusals.append(f"no data in this fetch for {', '.join(nodata)}: nothing runs; ask the author")
    if len(included) < MIN_PANEL:
        refusals.append(f"{len(included)} included, fewer than {MIN_PANEL}: nothing runs; ask the author")
    gaps = [tk for tk in included if per[tk]["missing_sessions_2015_2024"]]
    if gaps:
        refusals.append(f"in-sample gap or death after 2014 for {', '.join(gaps)}: ask the author")
    rec = {"registration": REGISTRATION, "fetch_json_sha256": hashlib.sha256(fetch_path.read_bytes()).hexdigest(),
           "fetch_start_utc": fetch["fetch_start_utc"], "last_fetched_session": last.isoformat(),
           "formation_window": [d.isoformat() for d in FORM], "insample_end": INSAMPLE_END.isoformat(),
           "sessions_2005_2014": len(form_s), "sessions_2015_2024": len(later_s),
           "rule": {"1": "a bar on every XNYS session 2005-01-03..2014-12-31",
                    "2": f"median daily share volume 2005-01-03..2014-12-31 >= {MIN_MEDIAN_SHARE_VOLUME:,}",
                    "3": "item 3: not verified", "5": f"at least {MIN_PANEL} included"},
           "per_ticker": per, "included": included, "n_included": len(included),
           "refused": refusals or None}
    if refusals:
        rec_path.write_text(json.dumps(rec, indent=1))
        raise CutRefused("; ".join(refusals))
    out.mkdir(parents=True)
    shas, nrows = {}, {}
    for tk in included:
        p = out / f"{tk}.csv"
        with open(p, "w") as fh:
            fh.write("date,adjclose,volume\n")
            for d, a, v in data[tk]:
                fh.write(f"{d.isoformat()},{a},{'' if v is None else v}\n")
        shas[tk] = hashlib.sha256(p.read_bytes()).hexdigest()
        nrows[tk] = len(data[tk])
    rec.update({"csv_sha256": shas, "rows": nrows,
                "combined_sha256": hashlib.sha256("\n".join(f"{t} {shas[t]}" for t in sorted(included)).encode()).hexdigest()})
    rec_path.write_text(json.dumps(rec, indent=1))
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not registration_live():
        raise SystemExit(f"REFUSED: the registration {REGISTRATION} is not an ancestor of HEAD")
    out = Path(a.out).expanduser()
    try:
        rec = cut(Path(a.raw).expanduser(), out)
    except CutRefused as e:
        raise SystemExit(f"REFUSED: {e} (record: {out.name}.cut.json if written; no CSV written)")
    print(f"cut: {rec['n_included']} of {len(TICKERS)} included ({', '.join(rec['included'])}); "
          f"last fetched session {rec['last_fetched_session']}; combined SHA-256 {rec['combined_sha256']}; "
          f"record {out.name}.cut.json; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
