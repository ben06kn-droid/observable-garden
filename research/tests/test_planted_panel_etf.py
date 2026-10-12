"""7.5's planted generator (`environments/planted_panel.py`) on the real ETF in-sample panel: these
need the machine-local ETF data, and the first reads the preflight in runs/. Moved from
tests/test_planted_panel.py in the 2026-10 cleanup."""
import numpy as np
import pytest

from environments import planted_panel as pp


ETF = pytest.mark.skipif(
    not (__import__("environments._paths", fromlist=["LOCAL_DATA"]).LOCAL_DATA
         / "raw" / "etf_insample").exists(), reason="ETF in-sample data absent")


@ETF
def test_the_registered_generator_reproduces_the_preflights_scale():
    """The preflight (`runs/planted_edge_preflight.json`) used the prototype with a
    ddof = 1 covariance; the registered definition is ddof = 0. Same member, and the
    scale agrees to the 1/T the definitions differ by."""
    import json
    base = pp.load_base()
    assert base.in_sample.features.shape[0] == 3019
    pre = {(r["seed"], r["beta"]): r for r in json.loads(
        open("runs/planted_edge_preflight.json").read())}
    for seed in (640000, 640001):
        d = pp.make_draw(base, seed, 1.0)
        r = pre[(seed, 1.0)]
        assert [list(p) for p in d.m_star] == r["planted"]
        assert d.c == pytest.approx(r["c"], rel=2.0 / 3019)


@ETF
def test_load_base_uses_the_pinned_matrix_not_the_build():
    base = pp.load_base()
    X = pp.pinned_features()
    n_is = base.in_sample.features.shape[0]
    assert np.array_equal(base.in_sample.features, X[:n_is])
    assert np.array_equal(base.holdout.features, X[n_is:n_is + base.holdout.features.shape[0]])
