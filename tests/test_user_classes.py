"""Class files: size, hash, the bar on a panel, refusals, and a streams class."""
import json

import numpy as np
import pytest

from quixote import classes as C
from quixote import panel as P


@pytest.fixture(scope="module")
def arrays():
    t = P.tiny(seed=7, T=200, M=6)
    return dict(t, returns=np.asarray(t["returns"], float), features=np.asarray(t["features"], float),
                periods_per_year=252.0, cost_bps=5.0, borrow_bps_yr=50.0)


def test_bundled_class_size_and_sha(arrays):
    from quixote.cli import EXAMPLES
    path = EXAMPLES / "class.json"
    lc = C.load(path, arrays, compute_bar=False)
    assert lc.kind == "subsets" and lc.size == 128 and lc.bar is None
    assert lc.sha256 == C.file_sha256(path) and len(lc.sha256) == 64


def test_bar_is_computed_and_described(tmp_path, arrays):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"kind": "subsets", "features": "all", "max_size": 1, "signed": True}))
    lc = C.load(path, arrays, B=100, seed=0)
    assert lc.size == 16 and lc.bar is not None and np.isfinite(lc.bar) and lc.bar > 0
    text = lc.describe()
    assert "size 16" in text and "critical annualised Sharpe at alpha 0.05" in text


def test_hash_changes_with_the_file(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps({"kind": "subsets", "features": ["x"], "max_size": 1}))
    b.write_text(json.dumps({"kind": "subsets", "features": ["x"], "max_size": 2}))
    assert C.file_sha256(a) != C.file_sha256(b)


def test_refusals(tmp_path, arrays):
    unknown = tmp_path / "u.json"
    unknown.write_text(json.dumps({"kind": "subsets", "features": ["nope"], "max_size": 1}))
    with pytest.raises(C.ClassError, match="not in the panel"):
        C.load(unknown, arrays, compute_bar=False)
    kind = tmp_path / "k.json"
    kind.write_text(json.dumps({"kind": "trees"}))
    with pytest.raises(C.ClassError, match="kind"):
        C.load(kind)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    with pytest.raises(C.ClassError):
        C.load(bad)


def test_all_features_without_panel_has_unknown_size(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"kind": "subsets", "features": "all", "max_size": 2}))
    assert C.load(path).size == -1


def test_streams_kind(tmp_path, arrays):
    rng = np.random.default_rng(1)
    np.savez(tmp_path / "s.npz", streams=0.01 * rng.standard_normal((5, 150)))
    path = tmp_path / "s.json"
    path.write_text(json.dumps({"kind": "streams", "file": "s.npz"}))
    lc = C.load(path, arrays, B=100)
    assert lc.kind == "streams" and lc.size == 5 and lc.bar is not None
    sha = lc.sha256
    np.savez(tmp_path / "s.npz", streams=0.01 * rng.standard_normal((5, 150)))
    assert C.file_sha256(path) != sha          # the streams file is part of the class's hash
