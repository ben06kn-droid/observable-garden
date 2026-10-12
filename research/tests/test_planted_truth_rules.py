"""`price_runs.planted_truth`'s rule branch, on a small synthetic class: 6 features, the
registered signed class up to depth 3 (232 members), so the full table builds in a test.

(a) at level 0 the panel is identical whatever the rule;
(b) the rule path's own population net Sharpe equals the target level, for all four rules,
    through `planted_truth` itself;
(c) the gross and net truths of an arbitrary position array agree with a direct computation
    from `planted_panel.population_moments`.
"""
import dataclasses
import tempfile

import numpy as np
import pytest

from environments import planted_panel as pp
from environments import planted_rules as prl
from environments.planted_view import agent_view
from experiments import price_runs as pr
from tests.test_planted_panel import _panel

K = 6
RULES = {"U": {"shape": "U", "a": 1, "b": None},
         "corner": {"shape": "corner", "a": 0, "b": 4},
         "product": {"shape": "product", "a": 2, "b": 5},
         "gated": {"shape": "gated", "a": 3, "b": None}}


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(T=900, M=8, K=K, seed=9))


@pytest.fixture(scope="module")
def inv(base):
    return pp.invariants_for(base, cache_dir=tempfile.mkdtemp())


def test_at_level_0_the_panel_is_identical_whatever_the_rule(base):
    draws = [prl.make_draw_rule(base, 687900, 0.0, s, r) for s, r in RULES.items()]
    for d in draws[1:]:
        assert d.c == 0.0
        assert np.array_equal(d.in_sample.returns, draws[0].in_sample.returns)
        assert np.array_equal(d.holdout.returns, draws[0].holdout.returns)
        assert np.array_equal(d.in_sample.features, draws[0].in_sample.features)


@pytest.mark.parametrize("shape", list(RULES))
def test_planted_truth_records_the_rules_own_net_sharpe_at_the_target(base, inv, shape):
    seed = 687901
    d = prl.make_draw_rule(base, seed, 1.5, shape, RULES[shape])
    view, mask = agent_view(d.in_sample, seed)
    table, pop = pr.planted_table(base, d, view, mask, inv=inv)
    assert table.N == 232
    sup = [list(x) for x in table.members[17]]
    t = pr.planted_truth(base, d, view, mask, table, pop, sup)
    assert t["planted_rule"] == RULES[shape]
    assert t["planted_truth"]["in_sample"] == pytest.approx(1.5, abs=1e-8)
    assert t["planted_truth_gross"]["in_sample"] >= t["planted_truth"]["in_sample"]
    assert t["submitted_recovery"].startswith("not applicable")
    assert t["linear_shadow"] == pytest.approx(float(np.max(pop)) / 1.5)
    assert t["planted_speed"] in ("fast", "slow")


def test_gross_and_net_truths_of_any_position_array_match_population_moments(base):
    d = prl.make_draw_rule(base, 687902, 1.0, "product", RULES["product"])
    rng = np.random.default_rng(3)
    from learn.inputs import unit
    T, M = d.w_star_is.shape
    w = unit(rng.standard_normal((T, M)))
    t = prl.truth_positions(base, d, w, None)
    m, v = pp.population_moments(base.in_sample, base.Sigma_is, w, d.w_star_is, d.c)
    assert t["in_sample"] == pytest.approx(m / np.sqrt(v) * np.sqrt(252), rel=1e-12)
    free = dataclasses.replace(base.in_sample, cost_rate=np.zeros_like(base.in_sample.cost_rate),
                               borrow_rate=np.zeros_like(base.in_sample.borrow_rate))
    mg, vg = pp.population_moments(free, base.Sigma_is, w, d.w_star_is, d.c)
    g = prl.gross_population_sharpe(base.in_sample, base.Sigma_is, w, d.w_star_is, d.c)
    assert g == pytest.approx(mg / np.sqrt(vg) * np.sqrt(252), rel=1e-12)
    assert t["holdout"] is None
