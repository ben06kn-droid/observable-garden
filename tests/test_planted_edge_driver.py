"""7.5's scripted driver (`experiments/planted_edge.py`) on a small synthetic panel."""
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from experiments import planted_edge as pe
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.mark.parametrize("beta", [0.0, 1.0])
def test_a_level_prices_every_searcher_at_both_tiers(base, beta):
    r = pe.run_level(base, 7, beta, B=40)
    assert (r["c"] == 0.0) == (beta == 0.0)
    assert len(r["searchers"]) == 6
    for s in r["searchers"]:
        assert s["score"] <= r["class_max"] + 1e-12          # searchers are class-capped
        for k in ("p_class", "p_trigger"):
            assert 1 / 41 <= s[k] <= 1.0
        assert set(s["truth"]) == {"in_sample", "holdout"}
    if beta == 0.0:                                         # a null for every member
        assert all(s["truth"]["in_sample"] < 0 for s in r["searchers"])


def test_a_searchers_score_is_its_members_class_pass_value(base):
    """Searchers read the class pass's own arrays, so a submission's score IS that
    member's realized Sharpe in the pass, and the class tier prices it exactly."""
    r = pe.run_level(base, 8, 1.0, B=20)
    d = pp.make_draw(base, 8, 1.0)
    ann = np.sqrt(d.in_sample.periods_per_year)
    from environments.class_table import streams_for
    for s in r["searchers"]:
        sup = [tuple(p) for p in s["support"]]
        assert pe._sharpe_rows(streams_for(d.in_sample, [sup, sup]), ann)[0] == s["score"]


def test_the_smoke_record_carries_no_rule_quantity(base, monkeypatch):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    rec = pe.run_seed((980000, [0.0, 1.0], 20))
    text = json.dumps(pe.cost_only(rec))
    for word in ("p_class", "p_trigger", "truth", "equals", "two_of_three",
                 "class_max", "planted", "score"):
        assert word not in text, word
