"""The Binance panel and fetch helpers on synthetic data only (no network)."""
import datetime as dt
import io
import zipfile

import numpy as np
import pytest

from data import fetch_binance as fb
from environments import binance_panel as bp


def _zip(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("x.csv", text)
    return b.getvalue()


def test_eligibility_excludes_delivery_stable_and_index_contracts():
    assert fb.eligible("BTCUSDT") and fb.eligible("1000SHIBUSDT")
    for s in ("BTCUSDT_230331", "USDCUSDT", "BUSDUSDT", "DEFIUSDT", "BTCDOMUSDT", "ETHBUSD"):
        assert not fb.eligible(s)


def test_the_universe_needs_a_full_formation_month_and_ranks_by_quote_volume():
    form = [{"symbol": "A", "quote_volume": 5.0, "trading_days": 31},
            {"symbol": "B", "quote_volume": 9.0, "trading_days": 30},      # listed mid-month
            {"symbol": "C", "quote_volume": 7.0, "trading_days": 31},
            {"symbol": "D", "quote_volume": 7.0, "trading_days": 31}]
    assert [u["symbol"] for u in fb.rank_universe(form, 31, top=3)] == ["C", "D", "A"]


def test_kline_and_funding_parsing_with_and_without_headers():
    head = ",".join(fb.KLINE_COLS)
    row = "1640995200000,1,2,0.5,1.5,10,1640999999999,15,3,4,5,0"
    for text in (head + "\n" + row, row):
        assert fb.parse_klines(_zip(text)) == [[1640995200000, 1.0, 2.0, 0.5, 1.5, 10.0, 15.0, 3]]
    with pytest.raises(fb.FetchRefused):
        fb.parse_klines(_zip("1640995200000000,1,2,0.5,1.5,10,1,15,3,4,5,0"))
    f = fb.parse_funding(_zip("calc_time,funding_interval_hours,last_funding_rate\n1641024000000,8,0.0001"))
    assert f == [[1641024000000, 8.0, 0.0001]]


def test_the_grid_puts_the_first_scored_bar_at_2022_and_253_warm_up_rows_before_the_first_feature_row():
    g = bp.grid()
    first_feature = g[bp.WARM]
    assert g[bp.WARM + bp.LAG] == int(dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert first_feature == g[bp.WARM + bp.LAG] - 2 * bp.BAR_MS
    assert g[-1] == int(dt.datetime(2025, 3, 31, 20, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert np.all(np.diff(g) == bp.BAR_MS) and bp.PPY == 2190


def _times(n=20):
    return np.arange(n, dtype=np.int64) * bp.BAR_MS + 1_640_000_000_000


def test_funding_sign_a_long_pays_a_positive_rate_and_a_short_receives_it():
    t = _times()
    kl = [[int(x), 1, 1, 1, 100.0, 5.0, 500.0, 7] for x in t]          # flat price
    fr = [[int(t[5]), 8.0, 0.001]]                                       # funding at the open of bar 5
    a = bp.align(t, kl, fr)
    assert a["funding"][4] == 0.001 and a["funding"].sum() == 0.001      # the bar ENDING at that time
    r, rp, alive = bp.returns_from([a], len(t))
    assert r[4, 0] == pytest.approx(-0.001) and rp[4, 0] == 0.0          # signals never see funding                              # long earns -rate
    w_short = -1.0
    assert w_short * r[4, 0] == pytest.approx(+0.001)                    # short receives it


def test_gaps_carry_the_close_and_a_delisting_kills_the_contract():
    t = _times(400)
    kl = [[int(x), 1, 1, 1, 100.0 + i, 5.0, 500.0, 7] for i, x in enumerate(t) if i not in (10, 11)]
    kl += [[int(t[i]), 1, 1, 1, 0, 0.0, 0.0, 0] for i in ()]
    a = bp.align(t, kl[:300], [])                                        # no rows after bar 301
    assert a["dead"] == 302 and a["gap_bars"] == 2
    assert a["close"][10] == a["close"][9] == 109.0
    r, rp, alive = bp.returns_from([a], len(t))
    assert not alive[302:, 0].any() and alive[:302, 0].all() and np.all(r[302:, 0] == 0)
    # filler rows (zero trades, constant price) after the last trade are a death, not trading
    kl2 = [[int(x), 1, 1, 1, 50.0, 5.0, 500.0, 7] for x in t[:200]] + \
          [[int(x), 1, 1, 1, 50.0, 0.0, 0.0, 0] for x in t[200:]]
    assert bp.align(t, kl2, [])["dead"] == 200
    # a trade after a 30-day silence is a new contract: dead from the start of the silence
    kl3 = [[int(x), 1, 1, 1, 50.0, 5.0, 500.0, 7] for x in t[:100]] + \
          [[int(x), 1, 1, 1, 50.0, 5.0, 500.0, 7] for x in t[100 + bp.RELIST_GAP + 1:]]
    assert bp.align(t, kl3, [])["dead"] == 100


def test_dead_contracts_are_free_idle_and_have_all_features_exactly_zero():
    T, M = 700, 5
    rng = np.random.default_rng(0)
    r = 0.01 * rng.standard_normal((T, M))
    alive = np.ones((T, M), bool)
    alive[400:, 3] = False
    r[400:, 3] = 0.0                                   # flat price after death: zero volatility
    p = bp.panel_from_arrays(_times(T), list("abcde"), r, alive, rp=r)
    assert p.features.shape == (T - 253 - 2, M, 40)
    assert np.isfinite(p.features).all()
    k = 400 - 253                                      # feature row of the death bar
    assert np.all(p.features[k:, 3, :] == 0.0) and np.any(p.features[k - 1, 3, :] != 0.0)
    # the live contracts' ranks span [-1, 1] without the dead one
    j = p.feature_names.index("mom21_rank")
    assert np.allclose(np.sort(p.features[k + 10, [0, 1, 2, 4], j]), [-1, -1 / 3, 1 / 3, 1])
    k2 = 399 - 253                                     # feature row 399 executes at the close of bar 400, dead
    assert np.all(p.cost_rate[k2:, 3] == 0) and np.all(p.cost_rate[:k2, 3] == 10e-4)
    assert np.all(p.borrow_rate == 0) and p.periods_per_year == 2190.0
    assert np.allclose(p.returns[0], r[255])


def test_signals_are_price_only_and_earned_returns_carry_funding():
    T, M = 600, 4
    rng = np.random.default_rng(1)
    rp = 0.01 * rng.standard_normal((T, M))
    fund = np.zeros((T, M))
    fund[::2] = 0.0005
    alive = np.ones((T, M), bool)
    a = bp.panel_from_arrays(_times(T), list("abcd"), rp - fund, alive, rp=rp)
    b = bp.panel_from_arrays(_times(T), list("abcd"), rp, alive, rp=rp)
    assert np.array_equal(a.features, b.features)                      # funding never enters X
    assert np.allclose(a.returns, (rp - fund)[255:T])


def test_the_daily_spec_starts_the_month_after_formation_with_the_warm_up_inside():
    s = bp.daily_spec("2021-11")
    g = bp.grid(s)
    assert s.ppy == 365 and s.relist_gap == 30
    assert g[0] == int(dt.datetime(2021, 11, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    assert g[-1] == int(dt.datetime(2025, 3, 31, tzinfo=dt.timezone.utc).timestamp() * 1000)


def test_a_fill_never_overrides_a_monthly_row(tmp_path):
    t = _times(4)
    (tmp_path / "X_4h.csv").write_text("open_time,open,high,low,close,volume,quote_volume,count\n"
                                       f"{t[0]},1,1,1,10,1,1,1\n{t[2]},1,1,1,12,1,1,1\n")
    (tmp_path / "X_4h_fill.csv").write_text("open_time,open,high,low,close,volume,quote_volume,count\n"
                                            f"{t[1]},1,1,1,11,1,1,1\n{t[2]},1,1,1,99,1,1,1\n")
    (tmp_path / "X_funding.csv").write_text("calc_time,funding_interval_hours,rate\n")
    kl, _ = bp.load_symbol("X", tmp_path)
    assert sorted((r[0], r[4]) for r in kl) == [(t[0], 10.0), (t[1], 11.0), (t[2], 12.0)]


def test_the_loader_refuses_holdout_rows(tmp_path):
    (tmp_path / "X_4h.csv").write_text("open_time,open,high,low,close,volume,quote_volume,count\n"
                                       f"{bp.HOLDOUT_START_MS},1,1,1,1,1,1,1\n")
    (tmp_path / "X_funding.csv").write_text("calc_time,funding_interval_hours,rate\n")
    from data.etf_loader import HoldoutRefused
    with pytest.raises(HoldoutRefused):
        bp.load_symbol("X", tmp_path)


def test_fill_runs_and_agreement_rules():
    from data import fetch_binance_fill as ff
    d = dt.date
    assert ff.runs_of_days([d(2022, 2, 27), d(2022, 2, 26), d(2022, 4, 1), d(2022, 2, 28), d(2022, 4, 2)]) == \
        [[d(2022, 2, 26), d(2022, 2, 27), d(2022, 2, 28)], [d(2022, 4, 1), d(2022, 4, 2)]]
    a = [1, 10.0, 11.0, 9.0, 10.5, 100.0, 1000.0, 7]
    assert ff.agree(a, list(a))[0]
    b = list(a)
    b[4] = 10.5 * (1 + 1e-6)
    assert not ff.agree(a, b)[0]
    c = list(a)
    c[7] = 8
    assert not ff.agree(a, c)[0]


def test_daily_fetch_helpers():
    from data import fetch_binance_daily as fd
    assert fd.next_month("2020-09") == "2020-10" and fd.next_month("2020-12") == "2021-01"
    assert fd.FORMATIONS == ("2020-09", "2021-01", "2021-10")


def test_lag_one_is_d_zero_earning_the_next_bar_and_costing_the_same_bar():
    import numpy as np
    from environments import binance_panel as bp
    T, M = bp.WARM + 40, 3
    rng = np.random.default_rng(3)
    rp = 0.01 * rng.standard_normal((T, M))
    rp[0] = 0
    alive = np.ones((T, M), bool)
    alive[bp.WARM + 20:, 2] = False
    rp[bp.WARM + 20:, 2] = 0
    times = np.arange(T, dtype=np.int64) * bp.BAR_MS
    p2 = bp.panel_from_arrays(times, ["a", "b", "c"], rp, alive, rp=rp)
    p1 = bp.panel_from_arrays(times, ["a", "b", "c"], rp, alive, rp=rp, lag=1)
    assert p1.features.shape[0] == p2.features.shape[0] + 1
    assert np.array_equal(p1.features[:-1], p2.features)
    assert np.allclose(p1.returns[5], rp[bp.WARM + 6]) and np.allclose(p2.returns[5], rp[bp.WARM + 7])
    k = 20                                     # row k is grid bar WARM + 20, the death bar
    assert p1.cost_rate[k, 2] == 0 and p1.cost_rate[k - 1, 2] > 0
    assert p2.cost_rate[k - 1, 2] == 0 and p2.cost_rate[k - 2, 2] > 0
    assert p1.meta["delay"] == 0 and p2.meta["delay"] == 1
