"""ETF recent panel: the single fetch (`prereg/etf-recent-panel.md`, section f). **Runs on the
holdout host, by the author, and nowhere else. It refuses to run until the registration is live**
(REGISTRATION below must be an ancestor of HEAD), and it refuses an existing output directory:
one fetch.

The source is that of the 6.5 fetch (`data/fetch_etf.py`): Yahoo's chart endpoint, by `curl`,
interval 1d, events div and split, adjusted close. period1 is 2005-01-01 00:00 UTC; period2 is
the fetch time. Each response is saved as received to <out>/<TICKER>.json, with its SHA-256 in
<out>/fetch.json. A failed request is retried once, and both attempts are recorded; a ticker
that still fails is recorded as failed (the cut then refuses: nothing runs, the author is asked).

It prints, per ticker, the HTTP status, the number of bars and the first and last bar dates.
**No price or volume value is printed.**

    python -m data.fetch_etf_recent --out ~/etf_recent/raw
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from data.fetch_etf import TICKERS

REGISTRATION = "310225cd4932bc18e1c8e2e248cbbb133124a004"
PERIOD1 = dt.datetime(2005, 1, 1, tzinfo=dt.timezone.utc)
NY = ZoneInfo("America/New_York")


def registration_live(registration: str = REGISTRATION) -> bool:
    """True iff the registration commit is an ancestor of HEAD."""
    return subprocess.run(["git", "merge-base", "--is-ancestor", registration, "HEAD"],
                          capture_output=True).returncode == 0


def url_for(tk: str, p1: int, p2: int) -> str:
    return (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?period1={p1}"
            f"&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true")


def curl(url: str, out: Path) -> str:
    """One request; the response body goes to `out` as received. Returns the HTTP code."""
    return subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", "--max-time", "60",
                           "-o", str(out), "-w", "%{http_code}", url],
                          capture_output=True, text=True).stdout.strip()


def bar_dates(raw: bytes) -> list[dt.date]:
    """The bar dates (America/New_York) from the timestamp array only; [] if none."""
    try:
        res = json.loads(raw, parse_float=lambda s: s)["chart"]["result"]
        ts = (res or [{}])[0].get("timestamp") or []
    except (ValueError, KeyError, TypeError, IndexError):
        return []
    return [dt.datetime.fromtimestamp(int(t), NY).date() for t in ts]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not registration_live():
        raise SystemExit(f"REFUSED: the registration {REGISTRATION} is not an ancestor of HEAD")
    out = Path(a.out).expanduser()
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; the fetch is made once")
    out.mkdir(parents=True)
    t0 = dt.datetime.now(dt.timezone.utc)
    p1, p2 = int(PERIOD1.timestamp()), int(t0.timestamp())
    rec = {"registration": REGISTRATION, "source": "Yahoo chart endpoint query1.finance.yahoo.com/v8/finance/chart",
           "request": {"period1": PERIOD1.isoformat(), "period2": t0.isoformat(timespec="seconds"),
                       "interval": "1d", "events": "div,split", "includeAdjustedClose": True},
           "fetch_start_utc": t0.isoformat(timespec="seconds"), "tickers": {}}
    for tk in TICKERS:
        url = url_for(tk, p1, p2)
        f = out / f"{tk}.json"
        attempts = []
        for _ in range(2):                                   # one retry, recorded
            code = curl(url, f)
            attempts.append({"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "http": code})
            if code == "200":
                break
            time.sleep(10)
        entry = {"url": url, "http": code, "attempts": attempts}
        if f.exists():
            raw = f.read_bytes()
            entry.update({"file": f.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
            d = bar_dates(raw)
        else:
            d = []
        if code != "200":
            entry["error"] = f"HTTP {code} after {len(attempts)} attempts"
        rec["tickers"][tk] = entry
        span = f"{d[0]} .. {d[-1]}" if d else "no bars"
        print(f"  {tk}: HTTP {code}, {len(d)} bars, {span}", flush=True)
        time.sleep(1.0)
    import importlib.metadata as md
    rec["fetch_end_utc"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    rec["versions"] = {p: md.version(p) for p in ("tzdata", "exchange_calendars")}
    (out / "fetch.json").write_text(json.dumps(rec, indent=1))
    bad = [tk for tk, e in rec["tickers"].items() if e["http"] != "200"]
    print(f"FETCH DONE: {len(TICKERS) - len(bad)} of {len(TICKERS)} HTTP 200"
          + (f"; FAILED: {', '.join(bad)} (the cut will refuse; ask the author)" if bad else "")
          + f"; record {out / 'fetch.json'}; no value printed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
