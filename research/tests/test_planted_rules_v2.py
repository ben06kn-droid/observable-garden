"""Version 2's planted shapes (`environments/planted_rules.py`, RULES_V2) on a synthetic base,
and the four existing shapes bit-identical to the code before version 2 (loaded from git)."""
import importlib.util
import subprocess
import sys

import numpy as np
import pytest

from environments import planted_panel as pp
from environments import planted_rules as prl
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(T=900, M=10, K=40, seed=4))


def _v2(base, seed=0):
    rng = np.random.default_rng(seed)
    seg = lambda p: {"X": rng.standard_normal(p.features.shape[:2] + (10,)),
                     "V": rng.standard_normal(p.features.shape[:2] + (2,))}
    return {"is": seg(base.in_sample), "ho": seg(base.holdout)}


@pytest.mark.parametrize("shape", prl.RULES_V2)
def test_v2_shapes_are_net_targeted_demeaned_and_unit_gross_where_on(base, shape):
    v2 = _v2(base)
    d = prl.make_draw_rule_v2(base, 689950, 1.5, shape, v2=v2)
    rec = prl.plant_record(base, d)
    assert rec["net"]["in_sample"] == pytest.approx(1.5, abs=1e-8)
    w = d.w_star_is
    g = np.abs(w).sum(axis=1)
    on = g > 0
    assert np.allclose(g[on], 1.0) and np.allclose(w.sum(axis=1), 0.0, atol=1e-12)
    assert rec["speed"] in ("fast", "slow")
    assert np.allclose(d.in_sample.returns, base.E_is[d.idx_is] + d.c * w)


def test_the_volume_rule_holds_only_high_volume_assets_and_the_regime_rule_is_gated(base):
    v2 = _v2(base, 1)
    d = prl.make_draw_rule_v2(base, 689951, 1.0, "volcond", v2=v2)
    vb = v2["is"]["V"][:, :, d.rule["b"]]
    low = vb <= np.median(vb, axis=1, keepdims=True)
    assert np.all(d.w_star_is[low] == 0)
    r = prl.make_draw_rule_v2(base, 689952, 1.0, "regime", v2=v2)
    from learn2.states import market_states, regime_gates
    on = regime_gates(market_states(base.E_is[r.idx_is], 1))[r.rule["g"]]
    assert np.all(r.w_star_is[~on] == 0) and r.rule["g"] in prl.REGIMES_GATED
    ll = prl.make_draw_rule_v2(base, 689953, 1.0, "leadlag", v2=v2)
    from learn import inputs as I
    assert np.array_equal(ll.w_star_is, I.unit(v2["is"]["X"][:, :, ll.rule["x"]]))


def test_v2_draws_are_seeded_and_dispatch_from_make_draw_rule(base):
    assert prl.draw_features_v2(689960, "regime") == prl.draw_features_v2(689960, "regime")
    v2 = _v2(base)
    a = prl.make_draw_rule_v2(base, 689961, 1.0, "leadlag", v2=v2)
    rule = prl.draw_features_v2(689961, "leadlag")
    assert a.rule == rule


def test_the_four_existing_shapes_are_bit_identical_to_the_code_before_version_2(base, tmp_path):
    old_src = subprocess.run(["git", "show", "30b8fe0:environments/planted_rules.py"],
                             capture_output=True, text=True, check=True).stdout
    f = tmp_path / "planted_rules_before_v2.py"
    f.write_text(old_src)
    spec = importlib.util.spec_from_file_location("planted_rules_before_v2", f)
    old = importlib.util.module_from_spec(spec)
    sys.modules["planted_rules_before_v2"] = old
    spec.loader.exec_module(old)
    for shape in prl.RULES:
        for seed in (685010, 685020):
            a = prl.make_draw_rule(base, seed, 1.5, shape)
            b = old.make_draw_rule(base, seed, 1.5, shape)
            assert a.rule == b.rule and a.c == b.c
            assert np.array_equal(a.w_star_is, b.w_star_is) and np.array_equal(a.w_star_ho, b.w_star_ho)
            assert prl.draw_features(seed, shape) == old.draw_features(seed, shape)
