"""The scripted twin cell's driver (`experiments/planted_twins.py`), small synthetic panel."""
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from environments.class_table import streams_for
from experiments import planted_twins as tw
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


def test_the_real_matrix_gives_the_sandboxs_streams(base):
    d = pp.make_draw(base, 3, 1.0)
    sups = base.members[:30]
    R = np.stack([d.in_sample.returns, d.in_sample.returns[::-1]], axis=2)
    X = tw.streams_multi(d.in_sample, sups, R)
    np.testing.assert_allclose(X[0], streams_for(d.in_sample, sups), rtol=0, atol=1e-15)


def test_a_twin_keeps_every_members_cost_path(base):
    """Positions depend on X alone, so with zero returns every matrix gives the same
    stream: minus cost and borrow, identically."""
    d = pp.make_draw(base, 4, 1.0)
    sups = base.members[:30]
    Z = np.zeros(d.in_sample.returns.shape + (3,))
    X = tw.streams_multi(d.in_sample, sups, Z)
    assert np.array_equal(X[0], X[1]) and np.array_equal(X[0], X[2])
    assert (X[0] <= 0).all()


def test_a_level_gives_registered_rank_p_values(base, monkeypatch):
    monkeypatch.setattr(tw, "CHUNK", 512)
    r = tw.run_level(base, 5, 0.0, B=30)
    assert len(r["block_lengths"]) == 1 + 2 * tw.K
    attainable = {k / 20 for k in range(1, 21)}
    for s in r["searchers"]:
        for c in tw.CONSTRUCTIONS:
            assert min(abs(s[f"p_twin_{c}"] - a) for a in attainable) < 1e-12
            assert 0 <= s[f"ties_{c}"] <= tw.K
        assert s["truth_in_sample"] < 0                 # level 0 is a null for every member


def test_the_smoke_record_carries_no_rule_quantity(base, monkeypatch):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    text = json.dumps(tw.cost_only(tw.run_seed((985000, [0.0, 1.0], 20))))
    for word in ("p_twin", "p_class", "score", "truth", "support", "ties", "autocorr"):
        assert word not in text, word
