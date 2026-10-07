"""Planted non-linear rules (`environments/planted_rules.py`), on a synthetic 40-feature base."""
import numpy as np
import pytest

from environments import planted_panel as pp
from environments import planted_rules as prl
from learn import inputs as I
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(T=900, M=10, K=40, seed=4))


def test_features_are_drawn_from_all_40_and_pairs_cross_families():
    seen = set()
    for seed in range(685000, 685300):
        r = prl.draw_features(seed, "product")
        assert I.FAMILY_OF[r["a"]] != I.FAMILY_OF[r["b"]]
        seen.add(r["a"])
    assert seen == set(range(40))
    assert prl.draw_features(685001, "corner") == prl.draw_features(685001, "corner")


@pytest.mark.parametrize("shape", prl.RULES)
def test_positions_are_demeaned_and_unit_gross_where_on(base, shape):
    d = prl.make_draw_rule(base, 685010, 1.0, shape)
    w = d.w_star_is
    g = np.abs(w).sum(axis=1)
    on = g > 0
    assert np.allclose(g[on], 1.0) and np.allclose(w.sum(axis=1), 0.0, atol=1e-12)
    if shape == "gated":
        assert 0 < on.mean() < 1                    # off days are zero positions
    assert d.w_star_ho.shape[0] == base.holdout.features.shape[0]


@pytest.mark.parametrize("shape", prl.RULES)
def test_the_scale_hits_the_net_target_over_all_days(base, shape):
    d = prl.make_draw_rule(base, 685020, 1.5, shape)
    rec = prl.plant_record(base, d)
    assert rec["net"]["in_sample"] == pytest.approx(1.5, abs=1e-8)
    assert rec["gross"]["in_sample"] > rec["net"]["in_sample"]
    t = prl.truth_positions(base, d, d.w_star_is, d.w_star_ho)
    assert t["in_sample"] == pytest.approx(1.5, abs=1e-8)
    assert np.allclose(d.in_sample.returns, base.E_is[d.idx_is] + d.c * d.w_star_is)


def test_turnover_is_traded_over_gross_and_the_label_uses_0_5():
    w = np.zeros((4, 2))
    w[1] = [0.5, -0.5]
    w[2] = [0.5, -0.5]
    w[3] = [-0.5, 0.5]
    # changes 1 (entry) + 0 + 2 = 3 over gross 3
    assert prl.turnover(w) == pytest.approx(1.0)
    assert prl.speed(w) == "fast" and prl.FAST_TURNOVER == 0.5
    u = np.tile([[0.5, -0.5]], (10, 1))
    assert prl.turnover(u) == 0.0 and prl.speed(u) == "slow"


def test_the_gate_reads_only_the_residual_market_which_a_dollar_neutral_plant_cannot_move(base):
    d = prl.make_draw_rule(base, 685030, 1.5, "gated")
    assert np.allclose(d.w_star_is.sum(axis=1), 0.0, atol=1e-12)
    planted_market = d.in_sample.returns.mean(axis=1)
    resid_market = base.E_is[d.idx_is].mean(axis=1)
    assert np.allclose(planted_market, resid_market, atol=1e-15)
