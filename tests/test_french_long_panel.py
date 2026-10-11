"""The long-history panel builder on SYNTHETIC returns: entry by rule (ii), eligibility after the
253-row warm-up, both timings, costs."""
import datetime as dt

import numpy as np

from environments import french_long_panel as FL
from environments.french_panel import WARM


def _data(T=900, M=5, seed=0):
    rng = np.random.default_rng(seed)
    R = 0.01 * rng.standard_normal((T, M))
    R[:100, 3] = np.nan            # enters at row 100
    R[200, 4] = np.nan             # a gap at row 200: enters at 201
    R[10, 4] = np.nan
    d0 = dt.date(1926, 7, 1)
    dates = [d0 + dt.timedelta(days=k) for k in range(T)]
    return dates, [f"N{j}" for j in range(M)], R


def test_entry_rows_rule_ii():
    _, _, R = _data()
    assert FL.entry_rows(R).tolist() == [0, 0, 0, 100, 201]


def test_eligibility_features_returns_costs_and_both_timings():
    dates, names, R = _data()
    p2, i2 = FL.long_panel(dates, names, R, lag=2)
    p1, i1 = FL.long_panel(dates, names, R, lag=1)
    T = R.shape[0]
    assert p2.features.shape[0] == T - WARM - 2 and p1.features.shape[0] == T - WARM - 1
    assert p2.meta["delay"] == 1 and p1.meta["delay"] == 0 and "NOT IMPLEMENTABLE" in p1.meta["timing"]
    k4 = 201 + WARM - WARM                         # panel row of grid row 201 + WARM (industry 4 eligible)
    assert (p2.features[:k4, 4] == 0).all() and np.abs(p2.features[k4 + 5:, 4]).sum() > 0
    # earned returns: grid row t + lag; zero until eligible
    g = lambda k, lag: WARM + k + lag
    k = 50
    assert p2.returns[k, 3] == 0.0 and p2.returns[k, 0] == R[g(k, 2), 0]
    assert p1.returns[k, 0] == R[g(k, 1), 0]
    late = 600
    assert p2.returns[late, 3] == R[g(late, 2), 3]
    assert (p2.cost_rate[:k4 - 1, 4] == 0).all() and p2.cost_rate[k4 + 2, 4] > 0
    assert i2["entry_date"][3] == str(dates[100])
