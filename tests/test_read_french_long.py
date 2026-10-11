"""The French long-history reader on MADE-UP results only."""
import json

import pytest

from experiments import read_french_long as Rd


def _t(test, p, alphas, cls=False):
    t = {"test": test, "alphas": {"96%": alphas[0], "90%": alphas[1]}, "n_rows": 15000, "B": 5000, "seed": 718000,
         "block_length": 3, "block_length_last_neff": 4,
         "weighted_W2": {"S": 0.4, "p": p, "L90": -0.1, "certified": {"96%": p < alphas[0], "90%": p < alphas[1]}},
         "unweighted": {"label": "unweighted, descriptive, not the certificate", "S": 0.2, "p": 0.2, "L90": -0.3}}
    if cls:
        t["weighted_W2"]["best_member"] = {"features": ["+mom5_z"]}
    else:
        t["performance_line"] = {"lines": {"252": {"S": 0.5, "ci90": [-0.9, 1.9]}, "756": {"S": 0.3, "ci90": [-0.5, 1.1]}}}
    return t


def _rec(p1=0.02, p2=0.015, p3=0.5):
    return {"read": "b1", "registration": "x", "first_date": "1926-07-01", "last_date": "1989-12-29", "rows": 16000,
            "platform": "Linux x86_64", "repeat_bit_identical": {"d1": True, "d0": True},
            "test1_stream_d1": _t("Sancho stream, d = 1", p1, (0.03, 0.06)),
            "test2_stream_d0": _t("Sancho stream, d = 0, NOT IMPLEMENTABLE", p2, (0.01, 0.02)),
            "test3_class_d1": _t("class maximum, d = 1", p3, (0.01, 0.02), cls=True)}


def test_branches_labels_and_order():
    text, out = Rd.read(_rec())
    assert text.index("test1") < text.index("test2") < text.index("test3")
    assert out["test1_stream_d1"] == {"96%": True, "90%": True}
    assert out["test2_stream_d0"] == {"96%": False, "90%": True}
    assert "refused, NOT IMPLEMENTABLE; consistent" in text and "certified in-sample under the recency weights (W2) at the registered weight (90% level), NOT IMPLEMENTABLE" in text
    assert text.count("[unweighted, descriptive, not the certificate]") == 3 and Rd.LIMITS in text
    assert "performance line (unweighted; descriptive; never gates)" in text and "best member (weighted): +mom5_z" in text


def test_a_failed_repeat_stops_and_the_read_happens_once(tmp_path):
    r = _rec()
    r["repeat_bit_identical"] = {"d1": True, "d0": False}
    assert Rd.read(r)[1] == {"stopped": True}
    (tmp_path / "results.json").write_text(json.dumps(_rec()))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
