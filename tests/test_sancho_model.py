"""Sancho run under its config: the default is bit-identical to the registered runner; the
levers are restored after a run; the CLI writes the config hash; LightGBM missing is explained."""
import json

import numpy as np
import pytest

from sancho import config as C
from sancho import learner as Ln
from sancho import model as SM

T, M = 1100, 8


def _inputs(seed=7):
    rng = np.random.default_rng(seed)
    f = 0.01 * rng.standard_normal(T)
    earned = f[:, None] + 0.01 * rng.standard_normal((T, M))
    P = rng.standard_normal((T, M, 40))
    X = rng.standard_normal((T, M, 10))
    V = rng.standard_normal((T, M, 4))
    return Ln.Inputs(P=P, earned=earned, cost_rate=np.full((T, M), 5e-4), borrow_rate=np.full((T, M), 50e-4 / 252),
                     ppy=252.0, d=1, blocks={"X": X, "V": V})


@pytest.mark.slow
def test_the_default_is_bit_identical_to_the_registered_runner():
    pytest.importorskip("lightgbm")
    from experiments import binance_design_v2 as D
    inp = _inputs()
    D.configure("carried")
    ref_book, ref_first, _ = D.book_of(inp)
    book, first, meta = SM.run(inp)
    assert first == ref_first == 756 + 5 + 1 + 1
    assert np.array_equal(book, ref_book)
    assert meta["is_default"] and meta["config_sha256"] == C.load().sha256
    assert meta["view"] == [["P", "X", "V"], 5, "market", "always"]


def test_the_levers_are_restored_after_a_run(tmp_path, monkeypatch):
    pytest.importorskip("lightgbm")
    before = (Ln.FIRST, Ln.REFIT, Ln.WARMUP, dict(Ln.MEMORIES), dict(Ln.TREES), Ln.NTREE)
    v = C.load().values
    v["first_scored_row"], v["memories"], v["information"] = 300, {"roll252": 252}, ["X"]
    v["trees"]["rounds"] = 5
    p = tmp_path / "c.json"
    p.write_text(json.dumps(v))
    rng = np.random.default_rng(1)
    n = 500
    inp = Ln.Inputs(P=None, earned=0.01 * rng.standard_normal((n, 6)), cost_rate=np.full((n, 6), 5e-4),
                    borrow_rate=np.zeros((n, 6)), ppy=252.0, d=1, blocks={"X": rng.standard_normal((n, 6, 10))})
    book, first, meta = SM.run(inp, C.load(p))
    assert first == 300 + 7 and np.abs(book[first:]).sum() > 0 and not meta["is_default"]
    assert (Ln.FIRST, Ln.REFIT, Ln.WARMUP, dict(Ln.MEMORIES), dict(Ln.TREES), Ln.NTREE) == before


def test_an_unavailable_block_is_refused():
    v = dict(C.load().values, information=["P"])
    inp = Ln.Inputs(P=None, earned=np.zeros((10, 2)), cost_rate=np.zeros((10, 2)), borrow_rate=np.zeros((10, 2)),
                    ppy=252.0, d=1, blocks={"X": np.zeros((10, 2, 10))})
    with pytest.raises(ValueError, match="not in these inputs"):
        SM.information(inp, v)


def test_lightgbm_missing_is_explained(monkeypatch):
    import builtins
    real = builtins.__import__

    def guard(name, *a, **k):
        if name == "lightgbm":
            raise ImportError("no lightgbm")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", guard)
    with pytest.raises(RuntimeError, match=r"optional extra .*\[sancho\]"):
        SM._need_lightgbm("4.7.0")


def _panel(path, T_=700, M_=6, K=5, seed=3):
    rng = np.random.default_rng(seed)
    r = 0.01 * rng.standard_normal((T_, M_))
    np.savez(path, returns=r, features=rng.standard_normal((T_, M_, K)), periods_per_year=252,
             feature_names=np.array([f"f{k}" for k in range(K)]))
    return path


def test_the_cli_writes_the_stream_and_the_config_hash(tmp_path, capsys):
    pytest.importorskip("lightgbm")
    from sancho import cli
    panel = _panel(tmp_path / "p.npz")
    v = C.load().values
    v["first_scored_row"], v["trees"]["rounds"] = 300, 5
    cp = tmp_path / "fast.json"
    cp.write_text(json.dumps(v))
    rc = cli.main(["--panel", str(panel), "--config", str(cp), "--out", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines()[0].startswith("sancho: non-default configuration")       # the one line
    rec = json.loads((tmp_path / "out" / "sancho.json").read_text())
    assert rec["config_sha256"] == C.load(cp).sha256 and rec["is_default"] is False
    assert rec["view"][0] == ["X"] and rec["panel_about"]["P_used"] is False
    assert len(rec["stream"]) == 700 - 2 - rec["first_scored_row"] and np.isfinite(rec["net_sharpe_in_sample"])


def test_the_cli_refuses_a_malformed_panel(tmp_path):
    from sancho import cli
    np.savez(tmp_path / "bad.npz", returns=np.zeros((5, 2)))
    assert cli.main(["--panel", str(tmp_path / "bad.npz"), "--out", str(tmp_path / "o")]) == cli.EXIT_USAGE
