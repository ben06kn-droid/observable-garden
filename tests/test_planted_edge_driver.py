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
def test_a_level_prices_every_searcher_at_both_tiers(base, beta, tmp_path_factory):
    r = pe.run_level(base, 7, beta, B=40, inv=pp.invariants_for(base, cache_dir=tmp_path_factory.mktemp('inv')))
    assert (r["c"] == 0.0) == (beta == 0.0)
    assert len(r["searchers"]) == 6
    for s in r["searchers"]:
        assert s["score"] <= r["class_max"] + 1e-12          # searchers are class-capped
        for k in ("p_class", "p_trigger"):
            assert 1 / 41 <= s[k] <= 1.0
        assert set(s["truth"]) == {"in_sample", "holdout"}
        assert {"equals_pop_best", "two_of_three_pop_best"} <= set(s)
    if beta == 0.0:                                         # a null for every member
        assert all(s["truth"]["in_sample"] < 0 for s in r["searchers"])


def test_a_searchers_score_is_its_members_class_pass_value(base, tmp_path):
    """Searchers read the class pass's own arrays, so a submission's score IS that
    member's realized Sharpe in the pass, and the class tier prices it exactly."""
    r = pe.run_level(base, 8, 1.0, B=20, inv=pp.invariants_for(base, cache_dir=tmp_path))
    r.pop("_overlap")
    d = pp.make_draw(base, 8, 1.0)
    ann = np.sqrt(d.in_sample.periods_per_year)
    from environments.class_table import streams_for
    for s in r["searchers"]:
        sup = [tuple(p) for p in s["support"]]
        assert pe._sharpe_rows(streams_for(d.in_sample, [sup, sup]), ann)[0] == s["score"]


def test_the_smoke_record_carries_no_rule_quantity(base, monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    real = pp.invariants_for
    monkeypatch.setattr(pp, "invariants_for", lambda b: real(b, cache_dir=tmp_path))
    rec = pe.run_seed((980000, [0.0, 1.0], 20))
    text = json.dumps(pe.cost_only(rec))
    for word in ("p_class", "p_trigger", "truth", "equals", "two_of_three",
                 "class_max", "planted", "score", "pop_best", "rank"):
        assert word not in text, word


def test_peak_rss_is_megabytes_on_either_platform(monkeypatch):
    import resource
    import sys

    class R:
        ru_maxrss = 512 * 2**20          # macOS: bytes for 512 MB
    monkeypatch.setattr(resource, "getrusage", lambda who: R())
    monkeypatch.setattr(sys, "platform", "darwin")
    assert pe.peak_rss_mb() == 512
    R.ru_maxrss = 512 * 2**10            # Linux: kilobytes for 512 MB
    monkeypatch.setattr(sys, "platform", "linux")
    assert pe.peak_rss_mb() == 512


def test_later_levels_reuse_the_first_levels_overlap_and_agree(base, tmp_path):
    """Overlap moments once per seed: a later level fed the first level's moments
    gives the same population figures as one that computes its own."""
    inv = pp.invariants_for(base, cache_dir=tmp_path)
    first = pe.run_level(base, 21, 0.0, B=10, inv=inv)
    reused = pe.run_level(base, 21, 1.0, B=10, inv=inv, overlap=first["_overlap"])
    own = pe.run_level(base, 21, 1.0, B=10, inv=inv)
    for k in ("pop_best", "pop_best_sr", "pop_n_positive", "planted_rank"):
        assert reused[k] == own[k], k
