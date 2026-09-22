"""6.5: the single fetch, the inclusion rule, and the in-sample export.

    python data/fetch_etf.py fetch      # once, on the holdout host only
    python data/fetch_etf.py rule       # the one look: bar dates and share volume
    python data/fetch_etf.py export     # 2005-2022 for the agent's machine; 2023-2025 stays

Registered in `prereg/agent-on-real-data.md` and `prereg/etf-universe.md`. **This
runs on the holdout host, the c7a.8xlarge `i-0886a189b85d4d051`, and nowhere
else.** The
agent harness never runs there, and the agent's machine never fetches.

- `fetch` pulls every candidate's full 2005-01-01..2025-12-31 daily series from
  Yahoo's chart endpoint in one pass, and hashes each response as received. One
  fetch, because back-adjusted closes are rewritten at every later dividend: two
  fetches are not one series.
- `rule` applies the inclusion rule reading **only the `timestamp` array and the
  `volume` array**. No price field is touched: not the close level, not a
  return. The code below indexes nothing else in the response.
- `export` writes, for the panel only, an in-sample file (dates up to
  2022-12-31) to be copied to the agent's machine, and a holdout file (from
  2023-01-01) that stays on this host. Both are hashed, as is the fetch they come
  from.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw" / "etf"
MANIFEST = ROOT / "etf_manifest.json"

TICKERS = ["SPY", "QQQ", "DIA", "IWM", "MDY",
           "IWD", "IWF", "IWN", "IWO", "IJH", "IJR",
           "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
           "EFA", "EWJ", "EWG", "EWU", "EWC", "EWA", "EWH",
           "EEM", "EWZ", "EWT", "EWY",
           "SHY", "IEF", "TLT",
           "LQD", "TIP", "AGG",
           "GLD", "IYR", "VNQ"]
START, END = dt.date(2005, 1, 1), dt.date(2025, 12, 31)
IN_SAMPLE_END = dt.date(2022, 12, 31)
FIRST_SESSION = dt.date(2005, 1, 3)
MIN_MEDIAN_SHARE_VOLUME = 500_000
MIN_PANEL = 30
HOST = "c7a.8xlarge i-0886a189b85d4d051"
NY = ZoneInfo("America/New_York")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n")


def fetch() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    p1 = int(dt.datetime(START.year, START.month, START.day, tzinfo=dt.timezone.utc).timestamp())
    p2 = int(dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    m = _load_manifest()
    files = {}
    for tk in TICKERS:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?period1={p1}"
               f"&period2={p2}&interval=1d&events=div%2Csplit&includeAdjustedClose=true")
        out = RAW / f"{tk}.json"
        for attempt in range(5):
            code = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0", "--max-time", "60",
                                   "-o", str(out), "-w", "%{http_code}", url],
                                  capture_output=True, text=True).stdout.strip()
            if code == "200":
                break
            time.sleep(10 * (attempt + 1))
        if code != "200":
            sys.exit(f"{tk}: HTTP {code} after retries; nothing downstream runs")
        files[tk] = {"file": str(out.relative_to(ROOT.parent)), "sha256": _sha(out),
                     "bytes": out.stat().st_size, "http": code}
        print(f"  {tk}: HTTP {code}, {files[tk]['bytes']} bytes", flush=True)
        time.sleep(1.0)
    m.update({"what": "6.5 ETF panel: the single fetch, the inclusion rule, the export",
              "holdout_host": HOST,
              "agent_harness_runs_here": False,
              "source": "Yahoo Finance chart endpoint query1.finance.yahoo.com/v8/finance/chart",
              "request": {"period1": START.isoformat(), "period2_exclusive": "2026-01-01",
                          "interval": "1d", "events": "div,split", "includeAdjustedClose": True},
              "adjustment": "adjclose: split- and dividend-adjusted (Yahoo); returns are total returns",
              "download_date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "fetch": files})
    import importlib.metadata as md
    m["tzdata"] = md.version("tzdata")
    m["exchange_calendars"] = md.version("exchange_calendars")
    _save_manifest(m)
    print("FETCH DONE", flush=True)


def _dates_and_volume(tk: str):
    """The only fields the rule reads."""
    r = json.loads((RAW / f"{tk}.json").read_text())["chart"]["result"][0]
    ts = r["timestamp"]
    vol = r["indicators"]["quote"][0]["volume"]
    dates = [dt.datetime.fromtimestamp(t, NY).date() for t in ts]
    return dates, vol


def rule() -> None:
    import exchange_calendars as xc
    cal = xc.get_calendar("XNYS", start="2004-01-01")
    sessions = [d.date() for d in cal.sessions_in_range(FIRST_SESSION.isoformat(), END.isoformat())]
    m = _load_manifest()
    look = {}
    for tk in TICKERS:
        dates, vol = _dates_and_volume(tk)
        have = set(dates)
        missing = [s for s in sessions if s not in have]
        consecutive = any((sessions.index(b) - sessions.index(a)) == 1
                          for a, b in zip(missing, missing[1:]))
        first_ok = min(dates) <= FIRST_SESSION
        insample_vol = sorted(v for d, v in zip(dates, vol)
                              if FIRST_SESSION <= d <= IN_SAMPLE_END and v is not None)
        med = insample_vol[len(insample_vol) // 2] if insample_vol else 0
        r1 = first_ok and not consecutive
        r2 = med >= MIN_MEDIAN_SHARE_VOLUME
        fails = ([] if r1 else ["1: continuous history"]) + ([] if r2 else ["2: share volume"])
        look[tk] = {"first_date": min(dates).isoformat(), "missing_sessions": len(missing),
                    "consecutive_missing": consecutive,
                    "median_insample_share_volume": int(med),
                    "passes": not fails, "fails": fails}
        print(f"  {tk}: {'PASS' if not fails else 'FAIL ' + ', '.join(fails)}", flush=True)
    panel = [tk for tk in TICKERS if look[tk]["passes"]]
    m["inclusion_look"] = {
        "date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "read": "timestamp and volume arrays only; no price field",
        "rule_3": "not a data check: ticker, merger and structure changes are checked by hand "
                  "against issuer records, recorded separately",
        "per_candidate": look}
    m["panel"] = panel
    m["panel_size"] = len(panel)
    m["panel_meets_minimum"] = len(panel) >= MIN_PANEL
    _save_manifest(m)
    print(f"PANEL {len(panel)} of {len(TICKERS)}; minimum {MIN_PANEL}: "
          f"{'met' if len(panel) >= MIN_PANEL else 'NOT MET -- 6.5 does not go live as registered'}",
          flush=True)


def export() -> None:
    m = _load_manifest()
    if not m.get("panel_meets_minimum"):
        sys.exit("panel below the registered minimum; nothing exported")
    ins, hold = RAW / "insample", RAW / "holdout"
    ins.mkdir(exist_ok=True)
    hold.mkdir(exist_ok=True)
    derived = {}
    for tk in m["panel"]:
        r = json.loads((RAW / f"{tk}.json").read_text())["chart"]["result"][0]
        dates = [dt.datetime.fromtimestamp(t, NY).date() for t in r["timestamp"]]
        adj = r["indicators"]["adjclose"][0]["adjclose"]
        vol = r["indicators"]["quote"][0]["volume"]
        for part, keep, d_out in (("insample", lambda d: d <= IN_SAMPLE_END, ins),
                                  ("holdout", lambda d: d > IN_SAMPLE_END, hold)):
            p = d_out / f"{tk}.csv"
            with p.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["date", "adjclose", "volume"])
                n = 0
                for d, a, v in zip(dates, adj, vol):
                    if keep(d) and d >= START:
                        w.writerow([d.isoformat(), a, v])
                        n += 1
            derived.setdefault(tk, {})[part] = {"file": str(p.relative_to(ROOT.parent)),
                                                "sha256": _sha(p), "rows": n,
                                                "from_fetch_sha256": m["fetch"][tk]["sha256"]}
    m["derived"] = derived
    m["export_rule"] = ("insample files are copied to the agent's machine; holdout files stay on "
                        "the holdout host and are never copied")
    _save_manifest(m)
    print(f"EXPORT DONE: {len(derived)} tickers", flush=True)


if __name__ == "__main__":
    {"fetch": fetch, "rule": rule, "export": export}[sys.argv[1]]()
