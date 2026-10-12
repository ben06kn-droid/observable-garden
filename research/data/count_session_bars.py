"""Count regular-session 5-minute bars per name against the calendar's expectation.

    python data/count_session_bars.py

The one additional look before the feature commit, approved 2026-09-21 to size
the missing-bar rule. It reads ONLY the timestamp column `t` of each treated-panel
file: no price, volume or trade count is loaded. A bar is regular-session when its
start lies in [open, close) of an XNYS session, which gives 78 on a full day and
42 on a 13:00 half-day. The result is written into data/adr_manifest.json under
"looks" together with what was read.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import exchange_calendars as xc
import pandas as pd

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "adr_manifest.json"


def main() -> None:
    man = json.loads(MANIFEST.read_text())
    req = man["request"]
    cal = xc.get_calendar("XNYS")
    sessions = cal.sessions_in_range(req["from"], req["to"])
    opens, closes = cal.opens.loc[sessions], cal.closes.loc[sessions]
    expected_per = ((closes - opens).dt.total_seconds() // 300).astype(int)
    expected = int(expected_per.sum())
    half_days = int((expected_per < 78).sum())
    edges = pd.IntervalIndex.from_arrays(opens, closes, closed="left")

    out = {}
    for tk, f in man["files"].items():
        t = pd.to_datetime(pd.read_csv(ROOT.parent / f["file"], usecols=["t"])["t"], unit="ms", utc=True).astype("datetime64[ns, UTC]")
        idx = edges.get_indexer(t)
        inside = idx >= 0
        per_session = pd.Series(idx[inside]).value_counts()
        present = int(inside.sum())
        empty_sessions = int(len(sessions) - per_session.size)
        out[tk] = {"regular_bars_present": present, "expected": expected,
                   "missing": expected - present,
                   "missing_pct": round(100 * (expected - present) / expected, 3),
                   "sessions_with_no_bar": empty_sessions}
        print(f"{tk:5s} present {present:6d} / {expected}  missing {expected - present:5d} "
              f"({out[tk]['missing_pct']:.2f}%)  sessions with no bar {empty_sessions}")

    man.setdefault("looks", []).append({
        "date": date.today().isoformat(),
        "what": "regular-session bar counts per name against the XNYS calendar, to size the "
                "missing-bar rule; the one additional look approved before the feature commit",
        "read": "column t (timestamps) only; no price, volume or trade count loaded",
        "script": "data/count_session_bars.py",
        "sessions": len(sessions), "half_days": half_days, "expected_bars_per_name": expected,
        "result": out,
    })
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")


if __name__ == "__main__":
    main()
