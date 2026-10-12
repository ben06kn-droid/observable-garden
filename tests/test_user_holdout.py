"""Holdout: split writes hashes and no value; grade runs once and then refuses."""
import json

import pytest

from quixote import holdout as H
from quixote import panel as P
from quixote.cli import EXAMPLES, main
from quixote.run import load_agent, run_session


@pytest.fixture
def split_dir(tmp_path):
    src = tmp_path / "panel.npz"
    P.save(src, **P.tiny(seed=7, T=300, M=8))
    out = tmp_path / "split"
    rec = H.split(src, "t0220", out)
    return {"tmp": tmp_path, "src": src, "out": out, "rec": rec}


def test_split_writes_hashes_and_prints_no_value(split_dir, capsys, tmp_path):
    rec, out = split_dir["rec"], split_dir["out"]
    assert rec["insample_rows"] == 220 and rec["holdout_rows"] == 80 and rec["holdout_first"] == "t0220"
    assert rec["holdout_sha256"] == P.sha256(out / "holdout.npz")
    assert json.loads((out / "holdout.json").read_text()) == rec
    assert not any("sharpe" in k.lower() or "return" in k.lower() for k in rec)
    with pytest.raises(H.HoldoutRefused):                      # a holdout is split once
        H.split(split_dir["src"], "t0220", out)
    code = main(["split", str(split_dir["src"]), "--holdout-from", "250", "--out", str(tmp_path / "s2")])
    text = capsys.readouterr().out
    assert code == 0 and "no holdout value printed" in text and "Sharpe" not in text


def test_grade_once_then_refuse(split_dir):
    out, tmp = split_dir["out"], split_dir["tmp"]
    cls = tmp / "class.json"
    cls.write_text((EXAMPLES / "class.json").read_text())
    log = tmp / "log.json"
    run_session(load_agent("examples.scripted_searcher:Agent"), out / "insample.npz", cls, log,
                B_bar=50, echo=lambda *_: None)
    rec = H.grade(log, out / "insample.npz", out / "holdout.npz", cls, tmp / "grades")
    assert rec["graded_periods"] > 0 and rec["first"] == "t0220"
    assert isinstance(rec["holdout_net_sharpe"], float)
    with pytest.raises(H.HoldoutRefused, match="graded already"):
        H.grade(log, out / "insample.npz", out / "holdout.npz", cls, tmp / "grades")
    with pytest.raises(H.HoldoutRefused, match="graded already"):
        H.grade(log, out / "insample.npz", out / "holdout.npz", cls, tmp / "grades")


def test_grade_refuses_a_log_from_other_data(split_dir):
    out, tmp = split_dir["out"], split_dir["tmp"]
    cls = tmp / "class.json"
    cls.write_text((EXAMPLES / "class.json").read_text())
    log = tmp / "log.json"
    log.write_text(json.dumps({"panel_sha256": "0" * 64, "class_sha256": "0" * 64}))
    with pytest.raises(H.HoldoutRefused, match="in-sample"):
        H.grade(log, out / "insample.npz", out / "holdout.npz", cls, tmp / "g")


def test_bad_cut(tmp_path):
    src = tmp_path / "p.npz"
    P.save(src, **P.tiny(seed=7, T=100, M=4))
    with pytest.raises(H.HoldoutRefused):
        H.split(src, "nowhere", tmp_path / "s")
    with pytest.raises(H.HoldoutRefused):
        H.split(src, "500", tmp_path / "s")
