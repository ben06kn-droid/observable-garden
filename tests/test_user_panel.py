"""The user panel format: read, save, the tiny panel, and the engine panel's timing."""
import numpy as np
import pytest

from quixote import panel as P


@pytest.fixture(scope="module")
def tiny():
    return P.tiny(seed=7, T=200, M=6)


def test_save_read_roundtrip(tmp_path, tiny):
    path = tmp_path / "p.npz"
    sha = P.save(path, **tiny)
    assert sha == P.sha256(path) and len(sha) == 64
    d = P.read(path)
    assert d["returns"].shape == (200, 6) and d["features"].shape == (200, 6, 8)
    assert d["feature_names"] == tiny["feature_names"]
    assert d["row_labels"][0] == "t0000" and d["asset_names"][0] == "A00"
    assert (d["delay"], d["cost_bps"], d["borrow_bps_yr"]) == (1, 5.0, 50.0)


def test_defaults_when_optional_arrays_absent(tmp_path):
    rng = np.random.default_rng(0)
    path = tmp_path / "bare.npz"
    np.savez(path, returns=rng.standard_normal((20, 3)), features=rng.standard_normal((20, 3, 2)),
             feature_names=np.array(["a", "b"]), periods_per_year=np.asarray(252.0))
    d = P.read(path)
    assert d["delay"] == 1 and d["row_labels"] == [str(i) for i in range(20)]
    assert d["asset_names"] == ["a0", "a1", "a2"]


def test_engine_timing_features_earn_returns_t_plus_1_plus_delay(tiny):
    d = dict(tiny, returns=np.asarray(tiny["returns"], float), features=np.asarray(tiny["features"], float),
             cost_bps=5.0, borrow_bps_yr=50.0)
    for delay in (0, 1, 2):
        d["delay"] = delay
        panel = P.to_engine(d)
        lag = 1 + delay
        T = d["returns"].shape[0]
        assert panel.returns.shape[0] == T - lag
        np.testing.assert_array_equal(panel.returns, d["returns"][lag:])
        np.testing.assert_array_equal(panel.features, d["features"][:T - lag])
        assert panel.meta["earned_labels"][0] == d["row_labels"][lag]
        assert panel.cost_rate[0, 0] == pytest.approx(5e-4)
        assert panel.borrow_rate[0, 0] == pytest.approx(50e-4 / 252)


def test_nan_returns_are_not_tradable(tiny):
    d = dict(tiny, cost_bps=5.0, borrow_bps_yr=50.0)
    R = np.asarray(tiny["returns"], float).copy()
    R[10, 2] = np.nan
    d["returns"] = R
    panel = P.to_engine(d)
    assert not panel.tradable[10 - 2, 2] and panel.returns[10 - 2, 2] == 0.0


def test_feature_subset(tiny):
    d = dict(tiny, cost_bps=5.0, borrow_bps_yr=50.0)
    panel = P.to_engine(d, features=[1, 3])
    assert panel.feature_names == [tiny["feature_names"][1], tiny["feature_names"][3]]
    assert panel.features.shape[2] == 2


def test_errors(tmp_path):
    with pytest.raises(P.PanelError):
        P.read(tmp_path / "missing.npz")
    bad = tmp_path / "bad.npz"
    np.savez(bad, returns=np.zeros((10, 3)))
    with pytest.raises(P.PanelError, match="lacks"):
        P.read(bad)
    shape = tmp_path / "shape.npz"
    np.savez(shape, returns=np.zeros((10, 3)), features=np.zeros((10, 4, 2)),
             feature_names=np.array(["a", "b"]), periods_per_year=np.asarray(252.0))
    with pytest.raises(P.PanelError, match="must be"):
        P.read(shape)
    names = tmp_path / "names.npz"
    np.savez(names, returns=np.zeros((10, 3)), features=np.zeros((10, 3, 2)),
             feature_names=np.array(["a"]), periods_per_year=np.asarray(252.0))
    with pytest.raises(P.PanelError, match="feature_names"):
        P.read(names)


def test_bundled_tiny_panel_loads():
    from quixote.cli import EXAMPLES
    panel = P.load(EXAMPLES / "data" / "tiny_panel.npz")
    assert panel.features.shape[2] == 8
