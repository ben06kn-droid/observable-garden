"""The Binance in-sample reader on MADE-UP results only (no read has run)."""
import json

import pytest

from experiments import read_binance_insample as Rd


def _t(S, p, alpha, **kw):
    return {"test": kw.pop("test", "a test"), "alpha": alpha, "window_rows": [762, 8865], "n_rows": 8104,
            "B": 5000, "seed": 701000, "block_length": 2, "S": S, "p": p, "L90": S - 0.9,
            "confidence": {"curve": [0.1] * 81}, **kw}


def _rec(p1=0.2, p2=0.5, **kw):
    rec = {"registration": "ecc07f0", "platform": "Darwin arm64", "git_head": "abc",
           "repeat_bit_identical": {"d0": True, "d1": True},
           "test1_stream_d0": _t(0.42, p1, 0.04, test="version 2 stream at d = 0"),
           "test2_class_d0": _t(1.10, p2, 0.01, test="class maximum", N=82240,
                                best_member={"index": 7, "support": [[3, 1.0], [9, -1.0]],
                                             "features": ["+mom5_z", "-vol21_rank"]}),
           "descriptive_stream_d1": {"label": "x", "window_rows": [763, 8864], "n_rows": 8102, "S": 0.31,
                                     "ci95": [-0.70, 1.33], "block_length": 2, "B": 5000, "seed": 701002}}
    rec.update(kw)
    return rec


def test_both_refused_in_order_with_the_d1_stream_labelled_and_no_verdict():
    text, out = Rd.read(_rec())
    assert text.index("Test 1") < text.index("Test 2") < text.index("LOOKED AT, NOT TESTED")
    assert text.count(Rd.REFUSED) == 2 and Rd.CERTIFIED not in text
    assert "best member: +mom5_z, -vol21_rank" in text and "90% lower bound -0.480" in text
    d1 = text[text.index("LOOKED AT"):]
    assert "observed net Sharpe 0.310; 95% interval [-0.700, +1.330]" in d1
    assert "p " not in d1.split("\n", 2)[2] and Rd.CERTIFIED not in d1 and Rd.REFUSED not in d1
    assert out["descriptive_stream_d1"]["verdict"] is None


def test_each_branch_follows_its_own_alpha():
    text, out = Rd.read(_rec(p1=0.03, p2=0.03))
    assert out["test1_stream_d0"]["certified"] and not out["test2_class_d0"]["certified"]
    assert text.count(Rd.CERTIFIED) == 1 and text.count(Rd.REFUSED) == 1
    _, out2 = Rd.read(_rec(p1=0.0401, p2=0.0099))
    assert not out2["test1_stream_d0"]["certified"] and out2["test2_class_d0"]["certified"]


def test_a_failed_repeat_or_a_missing_test_stops():
    text, out = Rd.read(_rec(repeat_bit_identical={"d0": True, "d1": False}))
    assert out == {"stopped": True} and "STOP" in text and "Test 1" not in text
    r = _rec()
    del r["descriptive_stream_d1"]
    assert Rd.read(r)[1] == {"stopped": True}


def test_dry_results_are_bannered_and_the_read_happens_once(tmp_path):
    text, _ = Rd.read(_rec(dry_run=True))
    assert text.startswith("DRY RUN")
    (tmp_path / "results.json").write_text(json.dumps(_rec()))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "results.json").write_text(json.dumps(_rec(platform="Linux x86_64")))
    with pytest.raises(SystemExit, match="not a laptop"):
        Rd.main(["--dir", str(tmp_path / "b")])
