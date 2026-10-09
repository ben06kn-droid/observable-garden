"""The formation fill on a synthetic contract with a one-day hole (network faked)."""
import csv
import datetime as dt

import numpy as np

from data import fetch_binance_fill_formation as FF

BAR = 14_400_000
T0 = int(dt.datetime(2022, 2, 20, tzinfo=dt.timezone.utc).timestamp() * 1000)


def _row(t, k):
    return [t, 1.0 + k, 2.0, 0.5, 1.5, 10.0 + k, 15.0 + k, 3 + k, 4.0 + k, 6.0 + k]


def _write(d, rows):
    with open(d / "AUSDT_4h.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
        w.writerows([r[:8] for r in rows])
    with open(d / "AUSDT_funding.csv", "w", newline="") as fh:
        csv.writer(fh).writerow(["calc_time", "funding_interval_hours", "rate"])


def test_a_hole_is_filled_when_the_overlap_agrees_and_carried_when_not(tmp_path, monkeypatch):
    times = np.arange(T0, T0 + 30 * 6 * BAR, BAR, dtype=np.int64)
    all_rows = [_row(int(t), k) for k, t in enumerate(times.tolist())]
    hole = set(range(6 * 10, 6 * 11))                         # day 10 missing
    _write(tmp_path, [r for k, r in enumerate(all_rows) if k not in hole])
    by_day = {}
    for r in all_rows:
        by_day.setdefault(dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone.utc).date(), []).append(r)
    monkeypatch.setattr(FF, "daily_rows", lambda sym, day: (by_day.get(day, []), "a" * 64))
    rec = FF.fill_symbol("AUSDT", tmp_path, times)
    assert rec["missing_bars"] == 6 and rec["filled_bars"] == 6 and rec["runs"][0]["decision"] == "filled"
    assert (tmp_path / "AUSDT_4h_fill_taker.csv").read_text().splitlines()[1].endswith(",64.0,66.0")
    bad = {d: [r[:5] + [r[5] * 1.01] + r[6:] for r in rows] for d, rows in by_day.items()}
    (tmp_path / "AUSDT_4h_fill.csv").unlink()
    monkeypatch.setattr(FF, "daily_rows", lambda sym, day: (bad.get(day, []), "a" * 64))
    rec2 = FF.fill_symbol("AUSDT", tmp_path, times)
    assert rec2["filled_bars"] == 0 and rec2["runs"][0]["decision"] == "carried (flagged)"
