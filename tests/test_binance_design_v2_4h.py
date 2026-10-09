"""The three-variant 4h design script on a SYNTHETIC Binance-shaped panel (no real data)."""
import numpy as np
import pytest

from environments import binance_panel as bp
from experiments import binance_design_v2_4h as E
from learn2 import learner as Ln


@pytest.fixture(scope="module")
def raw():
    rng = np.random.default_rng(9)
    M, T = 8, bp.WARM + 900 + bp.LAG
    spec = bp.daily_spec("2020-10")
    times = np.arange(T, dtype=np.int64) * 86_400_000
    rp = 0.02 * rng.standard_normal((T, M))
    rp[0] = 0.0
    alive = np.ones((T, M), bool)
    alive[1000:, 7] = False
    rp[1000:, 7] = 0.0
    fund = 1e-4 * rng.standard_normal((T, M))
    panel = bp.panel_from_arrays(times, [f"S{j}" for j in range(M)], rp - fund, alive, rp=rp, spec=spec)
    market = (rp * alive).sum(axis=1) / alive.sum(axis=1)
    vol = np.where(alive, np.exp(rng.standard_normal((T, M))) * 1e6, np.nan)
    info = {f"S{j}": {"dead_bar": 1000 if j == 7 else None, "gap_bars": 0,
                      "alive_earned": alive[bp.WARM + bp.LAG:, j].tolist(), "funding_rows": 3 * T} for j in range(M)}
    return {"panel": panel, "info": info, "universe": {"formation": "synthetic", "full_month_traders": 9, "universe": M},
            "spec": spec, "WARM": bp.WARM, "LAG": bp.LAG, "rp": rp, "market": market, "alive": alive,
            "close": np.where(alive, np.exp(np.cumsum(rp, axis=0)), np.nan), "volume": vol,
            "count": np.where(alive, rng.integers(1000, 5000, (T, M)).astype(float), np.nan),
            "taker": vol * rng.uniform(0.3, 0.7, (T, M)), "funding": fund}


def test_five_column_v_and_the_closure_and_block_length_fields(raw):
    q = E.quantities("4h-2020-09", raw, B_null=100)
    assert q["blocks"]["V"] == ["logvol_ratio", "taker_last", "taker_mean21", "count_ratio", "amihud21"]
    assert q["closed"]["dead_gross_share"] == 0.0 and q["as_is"]["dead_gross_share"] > 0
    bl = q["block_length"]
    assert len(bl["pw_scored"]) == len(bl["pw_whole"]) == 40 and bl["median_scored"] >= 1
    for lab in ("as_is", "closed"):
        for k in ("current", "proposed"):
            b = q[lab]["bars"][k]
            assert b["gross_80"] == pytest.approx(b["net_80"] + q[lab]["cost_drag_sharpe"])
    assert Ln.FIRST == 756


def test_close_dead_zeroes_dead_rows_and_the_exit_is_costed(raw):
    from learn2 import views as Vw
    book = np.full((10, 2), 0.25)
    alive = np.ones((10, 2), bool)
    alive[6:, 1] = False
    c = E.close_dead(book, alive)
    assert (c[6:, 1] == 0).all() and (c[:6] == 0.25).all()
    inp = Ln.Inputs(P=None, earned=np.zeros((10, 2)), cost_rate=np.full((10, 2), 1e-3),
                    borrow_rate=np.zeros((10, 2)), ppy=365.0, d=1)
    s_open = Vw.net_stream(book, inp, np.arange(10))
    s_closed = Vw.net_stream(c, inp, np.arange(10))
    assert s_closed[6] == pytest.approx(s_open[6] - 0.25 * 1e-3)


def test_the_median_rule_matches_select_block_length():
    from estimator.bootstrap import select_block_length
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.standard_normal((400, 5)), axis=0) * 0.01 + rng.standard_normal((400, 5))
    assert E.median_rule(E.pw_lengths(x), 400) == select_block_length(x - x.mean(axis=0))
