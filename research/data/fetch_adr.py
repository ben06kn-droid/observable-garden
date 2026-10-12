"""Download the 7.4 ADR panel's 5-minute bars from Massive (formerly Polygon.io).

    python data/fetch_adr.py [--panel treated|fallback]   # resumes; re-run until DONE

What it downloads is fixed by the pre-registration. `treated` (the default) is
prereg/adr-universe.md's nine names plus SOXX, XLK and XLC; `fallback` is the
ROADMAP 7.4 widening to EU large-caps, fetched now under the same no-look rule
because the free window rolls a day per day, with its own manifest. Both are 5-minute aggregates, adjusted=true, 2024-09-23 to 2026-09-18. The
start is the first session inside the free tier's rolling two-year window
(probed 2026-09-21: 2024-09-16..20 returned 403 NOT_AUTHORIZED, 2024-09-23..27
returned 200); the end is the last complete session before the download date.

The key is read from POLYGON_API_KEY and handed to curl on stdin (`curl -K -`),
so it never appears in a URL, a process listing, a file or a log. Any next_url
the vendor returns is stripped of an apiKey parameter before it is stored.

Resumable at page level: each vendor page is written to data/raw/_pages/ as soon
as it arrives, with the cursor for the next one. A finished ticker is assembled
into data/raw/<TICKER>_5min_adj.csv.gz and its pages removed.

Nothing is read back beyond what the manifest needs: row count, first and last
bar timestamp, and a SHA-256 per file. No bar is opened, plotted or summarised
here; that waits for the feature-list commit.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import importlib.metadata as md
import io
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

PANELS = {
    "treated": (["ASML", "SAP", "STM", "NOK", "ERIC", "LOGI", "ARM", "NXPI", "SPOT",
                 "SOXX", "XLK", "XLC"], "adr_manifest.json"),
    "fallback": (["NVS", "AZN", "SNY", "NVO", "HSBC", "BCS", "UL", "DEO", "TTE", "SHEL",
                  "BP", "RIO",
                  # sector benchmarks for the large caps, added 2026-09-21 when the
                  # fallback was invoked; the name-to-ETF mapping awaits approval
                  "XLV", "XLF", "XLP", "XLE", "XLB"], "adr_fallback_manifest.json"),
}
START, END = "2024-09-23", "2026-09-18"
ADJUSTED = "true"
HOST = "https://api.massive.com"
MIN_GAP_S = 12.5          # free tier: 5 calls a minute
UNIVERSE_COMMITS = {"universe": "2ea8574", "universe_correction": "0a5a15a",
                    "correction_partly_in": "2dd4473", "gitignore": "53b3d70"}
COLUMNS = ["t", "o", "h", "l", "c", "v", "vw", "n"]

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw"
PAGES = RAW / "_pages"

KEY = os.environ.get("POLYGON_API_KEY")
if not KEY:
    sys.exit("POLYGON_API_KEY is not set; refusing to run")

_last_call = 0.0


def _strip_key(url: str) -> str:
    p = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if k.lower() != "apikey"]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(q), p.fragment))


def _get(url: str) -> tuple[int, dict]:
    global _last_call
    for attempt in range(6):
        wait = MIN_GAP_S - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
        cfg = f'header = "Authorization: Bearer {KEY}"\n'
        r = subprocess.run(
            ["curl", "-s", "--max-time", "60", "-w", "\n%{http_code}", "-K", "-", url],
            input=cfg, capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        code = int(code) if code.isdigit() else 0
        if code == 429 or code >= 500 or code == 0:
            print(f"    HTTP {code}; backing off 60 s (attempt {attempt + 1})", flush=True)
            time.sleep(60)
            continue
        try:
            return code, json.loads(body)
        except json.JSONDecodeError:
            return code, {"status": "non-JSON body"}
    sys.exit(f"giving up after repeated failures on {_strip_key(url)}")


def _first_url(ticker: str) -> str:
    return (f"{HOST}/v2/aggs/ticker/{ticker}/range/5/minute/{START}/{END}"
            f"?adjusted={ADJUSTED}&sort=asc&limit=50000")


def fetch_pages(ticker: str) -> list[Path]:
    d = PAGES / ticker
    d.mkdir(parents=True, exist_ok=True)
    state = d / "state.json"
    st = json.loads(state.read_text()) if state.exists() else {"next": _first_url(ticker), "n": 0}
    while st["next"]:
        code, js = _get(st["next"])
        if code != 200 or js.get("status") not in ("OK", "DELAYED"):
            sys.exit(f"{ticker}: HTTP {code} status={js.get('status')} message={js.get('message')}")
        page = d / f"page{st['n']:04d}.json.gz"
        tmp = page.with_suffix(".tmp")
        with gzip.open(tmp, "wt") as f:
            json.dump(js.get("results", []), f)
        tmp.replace(page)
        nxt = js.get("next_url")
        st = {"next": _strip_key(nxt) if nxt else None, "n": st["n"] + 1}
        state.write_text(json.dumps(st))
        print(f"    {ticker} page {st['n']} ({js.get('resultsCount', 0)} bars)", flush=True)
    return sorted(d.glob("page*.json.gz"))


def assemble(ticker: str, pages: list[Path]) -> dict:
    out = RAW / f"{ticker}_5min_adj.csv.gz"
    seen, n, first, last, dup = set(), 0, None, None, 0
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(COLUMNS)
    for p in pages:
        with gzip.open(p, "rt") as f:
            for bar in json.load(f):
                t = bar["t"]
                if t in seen:
                    dup += 1
                    continue
                seen.add(t)
                w.writerow([bar.get(c, "") for c in COLUMNS])
                n += 1
                first = t if first is None else min(first, t)
                last = t if last is None else max(last, t)
    # mtime=0 so the same bars always hash the same
    with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode())
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    for p in pages:
        p.unlink()
    (PAGES / ticker / "state.json").unlink()
    (PAGES / ticker).rmdir()
    iso = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()
    return {"file": str(out.relative_to(ROOT.parent)), "sha256": sha, "rows": n,
            "duplicate_timestamps_dropped": dup,
            "first_bar_start_utc": iso(first) if first else None,
            "last_bar_start_utc": iso(last) if last else None,
            "pages": len(pages)}


DIVIDEND_NAMES = {
    "treated": ["ASML", "SAP", "STM", "NOK", "ERIC", "LOGI", "ARM", "NXPI", "SPOT"],
    "fallback": ["NVS", "AZN", "SNY", "NVO", "HSBC", "BCS", "UL", "DEO", "TTE", "SHEL",
                 "BP", "RIO"],
}


def fetch_dividends(man: dict, panel: str) -> None:
    """Ex-dates and amounts per treated name, for the rule excluding ex-dates from the
    overnight-gap feature (decided 2026-09-21). One call per name; ARM and SPOT pay no
    dividend and are queried anyway so the manifest shows zero rather than assuming it."""
    out = man.setdefault("dividends", {})
    for tk in DIVIDEND_NAMES[panel]:
        if tk in out:
            continue
        url = (f"{HOST}/v3/reference/dividends?ticker={tk}&ex_dividend_date.gte={START}"
               f"&ex_dividend_date.lte={END}&order=asc&sort=ex_dividend_date&limit=1000")
        code, js = _get(url)
        if code != 200 or js.get("status") != "OK":
            sys.exit(f"dividends {tk}: HTTP {code} status={js.get('status')} message={js.get('message')}")
        keep = ("ex_dividend_date", "pay_date", "cash_amount", "currency", "dividend_type", "frequency")
        out[tk] = [{k: d.get(k) for k in keep} for d in js.get("results", [])]
        print(f"  dividends {tk}: {len(out[tk])} ex-dates", flush=True)
    man["dividends_source"] = f"{HOST}/v3/reference/dividends, ex_dividend_date {START}..{END}"
    # Splits and ratio changes, for the listing-structure check registered in
    # prereg/adr-universe.md's 2026-09-21 amendment. Recorded, not acted on.
    sp = man.setdefault("splits", {})
    for tk in DIVIDEND_NAMES[panel]:
        if tk in sp:
            continue
        url = (f"{HOST}/v3/reference/splits?ticker={tk}&execution_date.gte={START}"
               f"&execution_date.lte={END}&limit=1000")
        code, js = _get(url)
        if code != 200 or js.get("status") != "OK":
            sys.exit(f"splits {tk}: HTTP {code} status={js.get('status')} message={js.get('message')}")
        sp[tk] = [{k: d.get(k) for k in ("execution_date", "split_from", "split_to")}
                  for d in js.get("results", [])]
        print(f"  splits {tk}: {len(sp[tk])}", flush=True)
    man["splits_source"] = f"{HOST}/v3/reference/splits, execution_date {START}..{END}"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=sorted(PANELS), default="treated")
    ap.add_argument("--dividends", action="store_true",
                    help="fetch ex-dates and amounts for the panel's names instead of bars")
    args = ap.parse_args()
    panel = args.panel
    tickers, manifest_name = PANELS[panel]
    MANIFEST = ROOT / manifest_name
    RAW.mkdir(exist_ok=True)
    man = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    man.update({
        "what": f"7.4 ADR {panel} panel, 5-minute aggregates; see prereg/adr-universe.md"
                + (" and ROADMAP 7.4's fallback list" if panel == "fallback" else ""),
        "source": "Massive (formerly Polygon.io), /v2/aggs aggregates, free tier",
        "host": HOST,
        "commits": UNIVERSE_COMMITS,
        "request": {"multiplier": 5, "timespan": "minute", "from": START, "to": END,
                    "adjusted": ADJUSTED, "sort": "asc", "limit": 50000},
        "session_filter": "none at download; every bar the vendor returns is kept, "
                          "extended hours included. The 09:30-16:00 ET filter is applied "
                          "at feature build.",
        "timestamp_convention": "t = bar START, Unix ms, UTC (vendor convention)",
        "free_window_probe_2026-09-21": {"2024-09-16..2024-09-20": "HTTP 403 NOT_AUTHORIZED",
                                         "2024-09-23..2024-09-27": "HTTP 200 OK"},
        "tzdata": md.version("tzdata"),
        "exchange_calendars": md.version("exchange_calendars"),
    })
    if args.dividends:
        fetch_dividends(man, panel)
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
        print("DONE", flush=True)
        return
    man.setdefault("files", {})
    for tk in tickers:
        if tk in man["files"] and (ROOT.parent / man["files"][tk]["file"]).exists():
            print(f"  {tk}: done already", flush=True)
            continue
        print(f"  {tk}: fetching", flush=True)
        pages = fetch_pages(tk)
        man["files"][tk] = assemble(tk, pages)
        man["files"][tk]["download_date"] = date.today().isoformat()
        MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
        f = man["files"][tk]
        print(f"  {tk}: {f['rows']} rows, {f['first_bar_start_utc']} .. {f['last_bar_start_utc']}",
              flush=True)
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
