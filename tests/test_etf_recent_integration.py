"""The host cut's output is the runner's input: a synthetic fetch, cut, then the runner's own cut
check and loader (no network, no fit)."""
from __future__ import annotations

import datetime as dt

from data import etf_recent_cut as C
from experiments import etf_recent_read as R
from tests.test_etf_recent_fetch_cut import write_raw


def test_cut_output_loads_in_the_runner(tmp_path):
    raw = write_raw(tmp_path)
    C.cut(raw, tmp_path / "insample")
    rec, bad, paths = R.check_cut(tmp_path / "insample.cut.json")
    assert bad == []
    assert rec["registration"] == R.REGISTRATION
    dates, tickers, P, Vol = R.load(paths)
    assert dates[0] == dt.date(2005, 1, 3) and dates[-1] == dt.date(2024, 12, 31)
    assert len(dates) == 5033 and P.shape == Vol.shape == (5033, 40)
    assert tickers == sorted(rec["included"])
    # amendment 2: the runner uses rows from 2010-01-04 only (1,259 sessions of 2005-2009 dropped)
    d2, t2, P2, V2, n_drop = R.load_from(paths)
    assert d2[0] == dt.date(2010, 1, 4) and d2[-1] == dt.date(2024, 12, 31)
    assert n_drop == 1259 and len(d2) == 5033 - 1259 == 3774
