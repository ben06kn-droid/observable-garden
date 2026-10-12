"""The French in-sample reader on made-up results only (the read has not run)."""
import json

import pytest

from experiments import read_french_insample as R


def _t(p, alpha, S=0.8, cls=False):
    t = {"test": "made up", "alpha": alpha, "window_rows": [756, 2515], "n_rows": 1760,
         "B": 5000, "seed": 693000, "block_length": 1, "S": S, "p": p, "L90": S - 0.6,
         "confidence": {"S": S, "L": {"0.90": S - 0.6}, "curve": [0.1, 0.5, 0.9]}}
    if cls:
        t.update({"N": 82240, "best_member": {"index": 7, "support": [[3, 1.0], [9, -1.0]],
                                              "features": ["+mom21_z", "-vol63_rank"]}})
    return t


def _rec(p1, p2):
    return {"registration": "de9da1b", "platform": "Darwin arm64", "git_head": "x",
            "repeat_bit_identical": True, "i_stream": _t(p1, 0.04),
            "ii_class": _t(p2, 0.01, S=1.5, cls=True)}


@pytest.mark.parametrize("p1,p2,c1,c2", [(0.03, 0.005, True, True), (0.04, 0.01, False, False),
                                         (0.039, 0.02, True, False), (0.5, 0.0099, False, True)])
def test_each_branch_follows_its_own_weight(p1, p2, c1, c2):
    text, out = R.read(_rec(p1, p2))
    assert out["i_stream"]["certified"] is c1 and out["ii_class"]["certified"] is c2
    assert out["i_stream"]["branch"] == (R.CERTIFIED if c1 else R.REFUSED)
    assert out["ii_class"]["branch"] == (R.CERTIFIED if c2 else R.REFUSED)
    assert text.index("(i)") < text.index("(ii)")


def test_the_rendering_carries_sharpe_p_lower_bound_and_the_best_member():
    text, _ = R.read(_rec(0.2, 0.3))
    assert "observed net Sharpe 0.800; p 0.2000" in text
    assert "90% lower bound +0.200" in text
    assert "best member: +mom21_z, -vol63_rank" in text
    assert "no further reading" in text


def test_a_failed_repeat_or_a_missing_test_stops_the_read():
    rec = _rec(0.01, 0.001)
    rec["repeat_bit_identical"] = False
    text, out = R.read(rec)
    assert out == {"stopped": True} and "STOP" in text
    rec = _rec(0.01, 0.001)
    del rec["ii_class"]
    assert R.read(rec)[1] == {"stopped": True}


def test_main_reads_once_and_only_a_laptop_run(tmp_path):
    (tmp_path / "results.json").write_text(json.dumps(_rec(0.2, 0.3)))
    assert R.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="once"):
        R.main(["--dir", str(tmp_path)])
    d2 = tmp_path / "b"
    d2.mkdir()
    rec = _rec(0.2, 0.3)
    rec["platform"] = "Linux x86_64"
    (d2 / "results.json").write_text(json.dumps(rec))
    with pytest.raises(SystemExit, match="laptop"):
        R.main(["--dir", str(d2)])
