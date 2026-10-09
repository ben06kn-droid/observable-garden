"""The recency-weighted certificate (estimator/recency.py): the flag-off path is the current
computation; the equal-weights limit of the weighted path reproduces it; the two centrings
differ at finite h; synthetic data only."""
import numpy as np
import pytest

from estimator import recency as Rc
from estimator.bootstrap import select_block_length
from learn import stream_tier


def _stream(seed, n=1500, drift=0.0005):
    rng = np.random.default_rng(seed)
    return 0.01 * rng.standard_normal(n) + drift, np.cumsum(rng.standard_normal((n, 5)), axis=0) * 1e-3


def test_weights_and_the_weighted_sharpe():
    w = Rc.weights(5, 2.0)
    assert w[-1] == 1.0 and w[-3] == 0.5 and np.all(np.diff(w) > 0)
    assert np.array_equal(Rc.weights(4, None), np.ones(4)) and np.array_equal(Rc.weights(4, np.inf), np.ones(4))
    x = np.random.default_rng(0).standard_normal(300)
    assert Rc.weighted_sharpe(x, np.ones(300), 252.0) == pytest.approx(x.mean() / x.std(ddof=1) * np.sqrt(252))
    assert Rc.DAILY_H == 5 * 252 and Rc.FOURH_H == 5 * 2190


def test_the_flag_off_stream_path_is_the_current_tier_bit_for_bit():
    from experiments.binance_insample_read import stream_test as current
    s, bc = _stream(1)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    a, b = Rc.stream_test(s, L, 252.0, 300, 9), current(s, L, 252.0, 300, 9)
    ref = stream_tier.certify(s[None, :], bc, 252.0, 300, 9)
    assert a["S"] == b["S"] == ref["score"] and a["p"] == b["p"] == ref["p"]
    assert np.array_equal(a["null_max"], b["null_max"]) and a["confidence"] == b["confidence"]


def test_equal_weights_reproduce_the_current_null():
    s, _ = _stream(2)
    a, b = Rc.stream_test(s, 3, 252.0, 300, 4, h=np.inf), Rc.stream_test(s, 3, 252.0, 300, 4)
    assert a["S"] == pytest.approx(b["S"], rel=1e-12) and a["p"] == b["p"]
    assert np.allclose(a["null_max"], b["null_max"], rtol=1e-10, atol=1e-12)
    c = Rc.stream_test(s, 3, 252.0, 300, 4, h=np.inf, centring="weighted_superseded")
    assert np.allclose(c["null_max"], b["null_max"], rtol=1e-10, atol=1e-12)     # the limit cannot tell them apart


def test_the_two_centrings_differ_at_finite_h_and_n_eff_is_reported():
    s, _ = _stream(3, n=3000, drift=0.001)
    a = Rc.stream_test(s, 2, 252.0, 200, 5, h=1260)
    b = Rc.stream_test(s, 2, 252.0, 200, 5, h=1260, centring="weighted_superseded")
    assert a["S"] == b["S"] and not np.allclose(a["null_max"], b["null_max"])
    assert 0 < a["n_eff"] < 3000 and a["confidence"]["L"]["0.90"] == pytest.approx(a["S"] - np.quantile(a["null_max"], 0.9))
    with pytest.raises(ValueError):
        Rc.stream_test(s, 2, 252.0, 10, 5, h=1260, centring="other")


def test_the_class_null_equal_weights_match_the_count_kernel_and_finite_h_differs():
    rng = np.random.default_rng(7)
    T, N = 400, 30
    X = 0.01 * rng.standard_normal((N, T)) + 0.0004 * rng.standard_normal((N, 1))
    obs1, M1 = Rc.class_null([X[:12], X[12:]], T, 3, 252.0, 200, 11, np.inf)
    # the count kernel, as `experiments.french_insample_read.price_class` computes it
    from estimator.bootstrap import stationary_bootstrap_indices
    r = np.random.default_rng(11)
    C = np.stack([np.bincount(stationary_bootstrap_indices(T, 3, r), minlength=T) for _ in range(200)], axis=1).astype(float)
    X0 = X - X.mean(axis=1, keepdims=True)
    mean = (X0 @ C) / T
    var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
    M2 = (mean / np.sqrt(var) * np.sqrt(252.0)).max(axis=0)
    assert np.allclose(M1, M2, rtol=1e-10)
    assert np.allclose(obs1, X.mean(axis=1) / X.std(axis=1, ddof=1) * np.sqrt(252.0), rtol=1e-12)
    _, M3 = Rc.class_null([X], T, 3, 252.0, 200, 11, 100.0)
    assert not np.allclose(M1, M3)


def test_levels_and_the_performance_line():
    assert Rc.levels(0.05, 0.015) == {"96% level": {"stream": False, "class": False},
                                       "90% level": {"stream": True, "class": True}}
    s, _ = _stream(4, n=8000)
    d = Rc.performance_line(s, 2190.0, 2, 100, 3)
    assert set(d["lines"]) == {"2190", "6570"} and d["lines"]["2190"]["rows"] == 2190
    k = Rc.performance_line(s, 252.0, 2, 100, 3)["lines"]
    assert set(k) == {"252", "756"} and k["252"]["ci90"][0] <= k["252"]["ci90"][1]


def test_price_class_on_a_synthetic_panel_flag_off_and_equal_weights(tmp_path):
    import environments.planted_fast as pf
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments.binance_insample_read import setup, synthetic
    raw, v2, c = synthetic(1)
    panel, _, _ = setup(raw, v2, c)
    cache = pf.build(panel, members_in_order(CLS, 40)[:128], name="recency-test", cache_dir=tmp_path)
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    off = Rc.price_class(panel, cache, bc, 5, 150, 0.01, panel.feature_names)
    inf = Rc.price_class(panel, cache, bc, 5, 150, 0.01, panel.feature_names, h=np.inf)
    assert off["h"] is None and inf["best_member"] == off["best_member"]
    assert inf["S"] == pytest.approx(off["S"], rel=1e-10) and inf["p"] == off["p"]
    fin = Rc.price_class(panel, cache, bc, 5, 150, 0.01, panel.feature_names, h=300)
    assert fin["n_eff"] < panel.features.shape[0] and fin["centring"] == "unweighted"
