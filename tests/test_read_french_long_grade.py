"""The B1 grading reader on MADE-UP grades only: each branch of section 7 (certified and held,
certified and not held, refused and graded either way), NOT IMPLEMENTABLE carried by (2) in
every branch, the descriptive lines labelled, the limits and the 6-year line always printed."""
import json

import pytest

from experiments import read_french_long_grade as R


def _obj(realized, L90, certified, extra=None):
    o = {"test": "x", "certified": {"96%": certified, "90%": certified}, "L90_weighted": L90, "realized": realized,
         "ci90": [realized - 0.6, realized + 0.6], "held": realized >= L90,
         "descriptive": {"realized_minus_L90": realized - L90, "ci90_minus_L90": [realized - 0.6 - L90, realized + 0.6 - L90],
                         "C_at_realized": 0.4, "C_clipped": False}}
    o.update(extra or {})
    return o


def _grades(r1, r2, r3):
    unw = lambda L: {"unweighted": {"label": "unweighted, descriptive, not the rule", "L90_unweighted": L,
                                    "realized_minus_L90_unweighted": 0.0}}
    g = {"registration": R.LIVE, "git_head": "g" * 40, "first_holdout_date": "1990-01-02", "last_date": "1995-12-29",
         "n_periods": 1517, "block_length": 9, "B": 10000, "seed": 719000,
         "objects": {"stream_d1": _obj(r1, 0.674, True), "stream_d0": _obj(r2, 0.889, True),
                     "class_member": _obj(r3, -0.324, False, {"member": {"index": 54952, "features":
                                          ["+mom252_rank", "+volmom252_rank", "+ma50_rank"]}})}}
    g["objects"]["stream_d1"]["descriptive"].update(unw(0.594))
    g["objects"]["stream_d0"]["descriptive"].update(unw(1.517))
    return g


def test_held_and_not_held_branches():
    text, out = R.read(_grades(0.90, 0.50, 0.10))
    assert ("(1) the Sancho stream, d = 1: certified in-sample under the recency weights (W2) at the registered "
            "weight (96% level); its weighted lower bound held on 1990-01-01 to 1995-12-31 (realised +0.900 ≥ bound +0.674).") in text
    assert ("(2) the Sancho stream, d = 0, NOT IMPLEMENTABLE: certified in-sample under the recency weights (W2) at the "
            "registered weight (96% level); its weighted lower bound did not hold on 1990-01-01 to 1995-12-31 "
            "(realised +0.500 < bound +0.889).") in text
    assert ("(3) the class's best member under the weights, d = 1 (+mom252_rank, +volmom252_rank, +ma50_rank): refused "
            "in-sample; consistent with the registered detection floor. Graded: realised +0.100 ≥ its weighted lower "
            "bound -0.324.") in text
    assert out["stream_d1"]["held"] and not out["stream_d0"]["held"] and out["class_member"]["held"]


def test_the_refused_object_not_held_and_the_always_lines():
    text, out = R.read(_grades(0.70, 1.20, -0.50))
    assert "Graded: realised -0.500 < its weighted lower bound -0.324." in text
    assert text.count("NOT IMPLEMENTABLE") >= 2                     # the label and the branch sentence
    assert R.LIMITS in text and R.SIX_YEARS in text
    assert text.count("[unweighted, descriptive, not the rule]") == 2 and text.count("[descriptive]") == 6
    assert not out["class_member"]["held"]


def test_a_90_level_only_certificate_is_so_labelled():
    g = _grades(0.9, 1.0, 0.0)
    g["objects"]["stream_d1"]["certified"] = {"96%": False, "90%": True}
    text, _ = R.read(g)
    assert "at the registered weight (90% level); its weighted lower bound held" in text


def test_main_reads_once(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: type("P", (), {"returncode": 0})())
    (tmp_path / "grades.json").write_text(json.dumps(_grades(0.9, 1.0, 0.0)))
    assert R.main(["--dir", str(tmp_path)]) == 0
    assert (tmp_path / "read.txt").exists() and json.loads((tmp_path / "decision.json").read_text())["stream_d0"]["held"]
    with pytest.raises(SystemExit, match="already read"):
        R.main(["--dir", str(tmp_path)])
