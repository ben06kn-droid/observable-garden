"""Confidence fields (`quixote/confidence.py`; `prereg/confidence-output.md`, draft)."""
import json

import numpy as np
import pytest
from scipy.stats import norm

from estimator.trigger_replay import ReplayNulls
from quixote import confidence as cf


@pytest.fixture
def reps():
    return np.random.default_rng(0).normal(0.8, 0.2, size=1000)


def test_the_grid_is_the_registered_one():
    assert cf.GRID.size == 81 and cf.GRID[0] == -1.0 and cf.GRID[-1] == 3.0
    assert np.allclose(np.diff(cf.GRID), 0.05)
    assert 0.0 in cf.GRID


@pytest.mark.parametrize("S", [0.2, 0.8, 1.1, 2.5])
def test_c_at_zero_is_c0_exactly_and_c0_is_one_minus_the_tiers_p(reps, S):
    out = cf.confidence(S, reps)
    k0 = int(np.flatnonzero(cf.GRID == 0.0)[0])
    assert out["curve"][k0] == out["C0"]
    p = ReplayNulls(fixed_sequence=reps, trigger=reps, policy=reps, block_length=1,
                    B=reps.size, realized_score=S, realized_actions=()).p_value("trigger")
    assert out["C0"] == 1.0 - p


def test_the_curve_is_nonincreasing_and_matches_its_definition(reps):
    S = 1.0
    C = cf.curve(S, reps)
    assert np.all(np.diff(C) <= 0)
    for k in (0, 17, 40, 80):
        direct = 1 - (1 + np.sum(reps >= S - cf.GRID[k])) / (reps.size + 1)
        assert C[k] == pytest.approx(direct, abs=0)


def test_lower_bounds_are_the_quantile_arithmetic(reps):
    out = cf.confidence(1.3, reps)
    for g in cf.GS:
        assert out["L"][f"{g:.2f}"] == 1.3 - np.quantile(reps, g)


def test_the_horizon_readout_matches_a_direct_integration(reps):
    S, H, ppy = 1.2, 5, 252
    C = cf.curve(S, reps)
    # independent route: a loop over the grid, the CDF read as 1 - C
    total, prev_F = 0.0, 0.0
    for k, s in enumerate(cf.GRID):
        F = 1 - C[k]
        mass = F - prev_F + (1 - F if k == cf.GRID.size - 1 else 0.0)
        total += mass * norm.cdf(s * np.sqrt(H) / np.sqrt(1 + s * s / (2 * ppy)))
        prev_F = F
    assert cf.horizon(C, H, ppy) == pytest.approx(total, abs=1e-12)
    assert cf.masses(C).sum() == pytest.approx(1.0, abs=1e-12)


def test_extremes_put_the_mass_at_the_grid_ends():
    hi = cf.confidence(10.0, np.zeros(200))          # S far above every replicate
    assert hi["curve"][-1] == pytest.approx(1 - 1 / 201)
    lo = cf.confidence(-10.0, np.zeros(200))
    assert lo["curve"][0] == pytest.approx(1 - 201 / 201)
    assert lo["P_H"] < 0.05 < 0.95 < hi["P_H"]


def test_it_is_json_ready_and_labelled(reps):
    out = cf.confidence(1.0, reps, tier="declared class")
    json.dumps(out)
    assert "not a posterior" in out["label"] and out["tier"] == "declared class"
    # P_H is described as a floor, qualified by where V3 found it one, and cited
    assert "at least" in out["label"] and "only where the panel has an edge" in out["label"]
    assert "afdcb53" in out["label"] and "de348ea" in out["label"]
    with pytest.raises(ValueError):
        cf.confidence(1.0, [])


def test_a_verdict_carries_the_replay_tiers_confidence():
    """certify() attaches confidence from the certifying null's own replicates, and
    its C0 is 1 - p_certifying."""
    from tests.test_agent_adapter import _fixture, _sandbox, policy_via_tools
    from quixote.agent_adapter import ToolSession
    from quixote.certify import certify
    from quixote.session import Session
    data, cfg, cls = _fixture()
    sb = _sandbox(data, cfg)
    tools = ToolSession(Session.on_sandbox(sb, cls))
    policy_via_tools(tools)
    log = tools.session.log
    v = certify(log, cls, sb.base_feature_columns(), np.sqrt(cfg.periods_per_year),
                B=60, seed=3)
    if v.p_certifying is None:
        pytest.skip("this log is not priced by the certifying null")
    c = v.confidence_replay
    assert c["tier"].startswith("trigger replay") and c["B"] == 60
    assert c["C0"] == pytest.approx(1 - v.p_certifying, abs=0)


def test_price_runs_class_tier_carries_confidence_with_c0_one_minus_p_upper():
    from tests.test_price_runs_planted import _panel
    from environments import planted_panel as pp
    from environments.real_sandbox import RealSandbox
    from experiments import price_runs as pr
    base = pp.base_from(_panel(K=5))
    draw = pp.make_draw(base, 640011, 1.0)
    from environments.planted_view import agent_view
    view, mask = agent_view(draw.in_sample, 640011)
    import tempfile
    inv = pp.invariants_for(base, cache_dir=tempfile.mkdtemp())
    table, _ = pr.planted_table(base, draw, view, mask, inv=inv)
    sup = [list(x) for x in table.members[7]]
    cp = pr.class_p_etf(RealSandbox(view, spec_class=pp.CLS), table, 640011, sup, 50)
    assert cp["confidence"]["C0"] == pytest.approx(1 - cp["p_upper"], abs=0)
    assert cp["confidence"]["tier"] == "declared class"
    shown = f"{cp['confidence']['P_H']:.3f}" in cp["confidence_text"]
    assert shown == (cp["p_upper"] < 0.05)          # P_H printed only when certified


def test_check_mode_ignores_a_field_the_stored_run_predates():
    from experiments import price_runs as pr
    stored = {"certifying_null_computable": True, "verdict": {"status": "FAIL", "B": 200},
              "events": []}
    repriced = {"certifying_null_computable": True,
                "verdict": {"status": "FAIL", "B": 200, "confidence": {"C0": 0.1}},
                "verdict_events": []}
    assert pr.compare(stored, repriced) == []
    stored["verdict"]["confidence"] = {"C0": 0.2}
    assert any("confidence" in d for d in pr.compare(stored, repriced))


def test_p_h_is_printed_only_beside_a_certified_verdict(reps):
    conf = cf.confidence(1.3, reps, tier="declared class")
    shown = cf.render(conf, certified=True)
    hidden = cf.render(conf, certified=False)
    assert f"{conf['P_H']:.3f}" in shown and "at least" in shown and "afdcb53" in shown
    assert f"{conf['P_H']:.3f}" not in hidden and "not shown" in hidden
    assert "P_H" in conf and conf["P_H"] == cf.confidence(1.3, reps)["P_H"]   # stored
    assert cf.render(None, certified=True).startswith("confidence: none")


def test_the_verdict_and_class_p_follow_the_rule():
    from tests.test_agent_adapter import _fixture, _sandbox, policy_via_tools
    from quixote.agent_adapter import ToolSession
    from quixote.certify import certify
    from quixote.session import Session
    data, cfg, cls = _fixture()
    sb = _sandbox(data, cfg)
    tools = ToolSession(Session.on_sandbox(sb, cls))
    policy_via_tools(tools)
    v = certify(tools.session.log, cls, sb.base_feature_columns(),
                np.sqrt(cfg.periods_per_year), B=60, seed=3)
    if v.confidence_replay is None:
        pytest.skip("not priced by the certifying null")
    line = next(r for r in v.reasons if r.startswith("confidence ("))
    P = f"{v.confidence_replay['P_H']:.3f}"
    assert (P in line) == (v.status == "CERTIFIED")
