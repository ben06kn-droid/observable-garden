"""The Binance cost rule: EDGE and Abdi-Ranaldo on simulated bars with a known spread, the
monthly window (no look-ahead), the fill, floor, fee and dead mask."""
import datetime as dt

import numpy as np
import pytest

from environments import binance_costs as K


def simulate(n_bars, spread, sigma, trades=200, seed=0):
    rng = np.random.default_rng(seed)
    p = np.cumsum(rng.standard_normal(n_bars * trades) * sigma)
    q = rng.choice([-1.0, 1.0], size=p.size)
    x = np.exp(p + q * spread / 2).reshape(n_bars, trades)
    return x[:, 0], x.max(axis=1), x.min(axis=1), x[:, -1]


@pytest.mark.parametrize("spread", [0.002, 0.01])
def test_edge_recovers_a_known_spread(spread):
    o, h, l, c = simulate(3000, spread, 0.0003)
    assert K.edge(o, h, l, c) == pytest.approx(spread, rel=0.15)


def test_abdi_ranaldo_is_in_the_right_range_and_both_handle_missing_bars():
    o, h, l, c = simulate(3000, 0.01, 0.0003)
    assert K.abdi_ranaldo(h, l, c) == pytest.approx(0.01, rel=0.35)
    o2 = o.copy(); o2[::7] = np.nan
    assert np.isfinite(K.edge(o2, h, l, c))


def test_the_monthly_window_uses_only_bars_before_the_month():
    start = int(dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    times = start + np.arange(6 * 90) * 14_400_000
    o, h, l, c = simulate(len(times), 0.004, 0.0003, seed=1)
    O, H, L, C = (np.stack([x, x], axis=1) for x in (o, h, l, c))
    traded = np.ones_like(O, bool)
    starts, hs = K.monthly_half_spreads(times, O, H, L, C, traded)
    assert len(starts) == 3 and np.isnan(hs[0]).all() and np.isfinite(hs[1:]).all()
    # changing bars on or after February 1 leaves February's estimate unchanged
    feb = starts[1]
    C2 = C.copy(); C2[times >= feb] *= 1.5
    _, hs2 = K.monthly_half_spreads(times, O, H, L, C2, traded)
    assert hs2[1, 0] == hs[1, 0] and hs2[2, 0] != hs[2, 0]
    traded[:, 1] = False
    _, hs3 = K.monthly_half_spreads(times, O, H, L, C, traded)
    assert np.isnan(hs3[1, 1]) and K.fill_months(hs3)[1, 1] == hs3[1, 0]


def test_cost_rates_fee_floor_month_and_dead_mask():
    start = int(dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    times = start + np.arange(400) * 14_400_000
    starts = K.month_starts(times)
    hs = np.array([[np.nan, np.nan], [2e-5, 3e-4], [5e-4, 5e-4]])
    alive = np.ones((400, 2), bool)
    alive[300:, 1] = False
    r = K.cost_rates(times, starts, hs, alive, warm=10, lag=2)
    assert r.shape == (388, 2)
    k_feb = int(np.argmax(times[11:398] >= starts[1]))
    assert r[k_feb, 0] == pytest.approx(5e-4 + 1e-4) and r[k_feb, 1] == pytest.approx(5e-4 + 3e-4)
    assert r[0, 0] == pytest.approx(5e-4 + 1e-4)
    assert (r[300 - 11:, 1] == 0).all() and r[300 - 12, 1] > 0
