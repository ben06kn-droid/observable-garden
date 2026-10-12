"""The ETF recent panel's holdout session list, written on the holdout host by `~/venv-fetch`
(which has exchange_calendars 4.13.2 and tzdata 2026.4, the fetch's pins), so that the grader's
`.venv-grading` never imports exchange_calendars (`prereg/etf-recent-grading.md`, the author's
decision 3).

It lists the XNYS sessions from the first on or after 2025-01-01 to the cut record's last fetched
session, writes them as a small JSON, and prints its SHA-256. No price is read. The grader takes
the file pinned by that SHA-256, checks it against the cut record and against every ETF's fetched
holdout dates (none missing, none extra), and records the hash.

    ~/venv-fetch/bin/python -m data.etf_recent_sessions --cut ~/etf_recent/insample.cut.json \\
        --out ~/etf_recent/holdout_sessions.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

HOLDOUT_FROM = dt.date(2025, 1, 1)


def session_list(last: dt.date) -> dict:
    import importlib.metadata as md
    from data.etf_recent_cut import sessions
    s = sessions(HOLDOUT_FROM, last)
    return {"calendar": "XNYS", "exchange_calendars": md.version("exchange_calendars"),
            "tzdata": md.version("tzdata"), "on_or_after": str(HOLDOUT_FROM), "to": str(last),
            "n": len(s), "sessions": [d.isoformat() for d in s]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True, help="the in-sample cut record (its last_fetched_session)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out).expanduser()
    if out.exists():
        raise SystemExit(f"REFUSED: {out} exists; the session list is written once")
    cut = json.loads(Path(a.cut).expanduser().read_text())
    rec = session_list(dt.date.fromisoformat(cut["last_fetched_session"]))
    out.write_text(json.dumps(rec, indent=1))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"holdout sessions: {rec['n']}, {rec['sessions'][0]} .. {rec['sessions'][-1]} "
          f"(exchange_calendars {rec['exchange_calendars']}, tzdata {rec['tzdata']}); SHA-256 {sha}; "
          f"written {out}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
