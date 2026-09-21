"""Known-answer tests for the 7.4 spread estimators, on simulated trades only.

The formulas were taken from the `bidask` package source rather than the papers,
so this is what validates the implementation: a random-walk log midprice, trades
at mid +/- a fixed half-spread with a random side, aggregated to 5-minute OHLC
bars over the registered 20-session window, and the estimator must return the
spread that was put in.

Tolerances were read from a 40-seed simulation before this file was written,
and the test uses 10 seeds (0-9), all inside it:

- 10 bps at 17 bps/bar volatility (about 1.5% a day): 5th-95th percentile
  8.9-10.5 bps, mean 9.6. Asserted: seed mean within 10%, every seed within 20%.
- 4 bps at 8 bps/bar volatility: 3.4-4.3, mean 3.8. Same tolerances.
- 1 bp, below the 2 bp floor, at 8 bps/bar: raw estimates fall below the floor
  and `floored` returns the floor on at least 9 of 10 seeds.

Recorded, not asserted: the estimator runs 2-5% low at these settings, and at
17 bps/bar volatility a 4 bp spread is poorly resolved (5th-95th 0.7-5.4 bps).
That is a precision limit of a 20-session window, not an implementation error.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))

from adr_costs import FLOOR_BPS, abdi_ranaldo, floored, roll  # noqa: E402

SEEDS = range(10)


def simulate(spread, sigma_bar, seed, trades_per_bar=20, sessions=20, bars=78, p0=50.0):
    """Per-session lists of bar highs, lows and closes. The midprice is a random
    walk in logs, continuous within a session and restarted each session, so no
    overnight move exists for a pair to straddle."""
    rng = np.random.default_rng(seed)
    H, L, C = [], [], []
    for _ in range(sessions):
        n = bars * trades_per_bar
        mid = np.log(p0) + np.cumsum(rng.normal(0.0, sigma_bar / np.sqrt(trades_per_bar), n))
        side = rng.choice([-1.0, 1.0], n)
        px = np.exp(mid + side * spread / 2).reshape(bars, trades_per_bar)
        H.append(px.max(axis=1)); L.append(px.min(axis=1)); C.append(px[:, -1])
    return H, L, C


@pytest.mark.parametrize("spread,sigma_bar", [(10e-4, 17e-4), (4e-4, 8e-4)])
def test_abdi_ranaldo_recovers_a_known_spread(spread, sigma_bar):
    est = np.array([abdi_ranaldo(*simulate(spread, sigma_bar, s)) for s in SEEDS])
    assert abs(est.mean() / spread - 1) < 0.10, est / spread
    assert np.all(np.abs(est / spread - 1) < 0.20), est / spread


def test_a_spread_below_the_floor_is_floored():
    spread, floor = 1e-4, FLOOR_BPS * 1e-4
    est = np.array([abdi_ranaldo(*simulate(spread, 8e-4, s)) for s in SEEDS])
    assert est.mean() < floor
    applied = np.array([floored(e, prev_close=50.0) for e in est])
    assert np.sum(applied == floor) >= 9, applied


def test_roll_cross_check_recovers_a_known_spread():
    est = np.array([roll(simulate(10e-4, 17e-4, s)[2])[0] for s in SEEDS])
    assert abs(est.mean() / 10e-4 - 1) < 0.15, est / 10e-4


def test_no_pair_crosses_a_session_boundary():
    """Rescaling one whole session is a pure overnight jump in logs. If any pair
    straddled the boundary it would enter the estimate; none does, so the
    estimate is unchanged."""
    H, L, C = simulate(6e-4, 10e-4, 0, sessions=2)
    a = abdi_ranaldo(H, L, C)
    b = abdi_ranaldo([H[0], H[1] * 1.5], [L[0], L[1] * 1.5], [C[0], C[1] * 1.5])
    assert a == pytest.approx(b, rel=1e-12)
    assert roll(C)[0] == pytest.approx(roll([C[0], C[1] * 1.5])[0], rel=1e-9)


def test_the_floor_is_one_cent_or_two_bps_whichever_is_larger():
    assert floored(0.0, prev_close=5.0) == pytest.approx(0.01 / 5.0)     # 20 bps: cents bind
    assert floored(0.0, prev_close=800.0) == pytest.approx(2e-4)         # 2 bps binds
    assert floored(9e-4, prev_close=800.0) == pytest.approx(9e-4)        # estimate above both


def test_no_real_data_is_read():
    """The estimator module is pure: it never opens a file, so it needs no
    ancestor guard of its own."""
    src = (Path(__file__).resolve().parent.parent / "data" / "adr_costs.py").read_text()
    for token in ("open(", "read_csv", "np.load", "raw/"):
        assert token not in src, token
