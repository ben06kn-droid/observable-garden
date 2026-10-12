"""The ETF recent panel's reader on MADE-UP results only."""
import json

import pytest

from experiments import read_etf_recent as Rd


def _t(test, p, alphas, cls=False):
    t = {"test": test, "alphas": {"96%": alphas[0], "90%": alphas[1]}, "n_rows": 4015, "B": 5000, "seed": 721000,
         "block_length": 3, "block_length_last_neff": 4,
         "weighted_W2": {"S": 0.4, "p": p, "L90": -0.1, "certified": {"96%": p < alphas[0], "90%": p < alphas[1]}},
         "unweighted": {"label": "unweighted, descriptive, not the certificate", "S": 0.2, "p": 0.2, "L90": -0.3}}
    if cls:
        t["weighted_W2"]["best_member"] = {"features": ["+mom5_z"]}
        t["unweighted"]["best_member"] = ["-ret1_rank", "+mom252_z"]
    else:
        t["performance_line"] = {"lines": {"252": {"S": 0.5, "ci90": [-0.9, 1.9]}, "756": {"S": 0.3, "ci90": [-0.5, 1.1]}}}
        t["cost_10bps_beside"] = {"label": "10 bps one-way, unweighted, descriptive", "S": 0.1}
    return t


def _rec(p1=0.02, p2=0.015, p3=0.5):
    return {"registration": "x", "first_date": "2005-01-03", "last_date": "2024-12-31", "rows": 5033,
            "cut": {"n_included": 38}, "platform": "Linux x86_64", "repeat_bit_identical": {"d1": True, "d0": True},
            "test1_stream_d1": _t("Sancho stream, d = 1", p1, (0.03, 0.06)),
            "test2_stream_d0": _t("Sancho stream, d = 0, NOT IMPLEMENTABLE", p2, (0.01, 0.02)),
            "test3_class_d1": _t("class maximum, d = 1", p3, (0.01, 0.02), cls=True)}


def test_branches_labels_both_members_and_limits():
    text, out = Rd.read(_rec())
    assert text.index("test1") < text.index("test2") < text.index("test3")
    assert out["test1_stream_d1"] == {"96%": True, "90%": True}
    assert out["test2_stream_d0"] == {"96%": False, "90%": True}
    assert out["test3_class_d1"] == {"96%": False, "90%": False}
    assert "refused, NOT IMPLEMENTABLE; consistent" in text
    assert "at the registered weight (90% level), NOT IMPLEMENTABLE" in text
    assert "best member (weighted): +mom5_z" in text
    assert "best member (unweighted): -ret1_rank, +mom252_z" in text
    assert text.count("[unweighted, descriptive, not the certificate] net Sharpe") == 3
    assert text.count("[10 bps one-way, unweighted, descriptive]") == 2
    assert Rd.LIMITS in text and Rd.PANEL_LIMITS in text and "NOT verified" in text
    assert "38 ETFs" in text


def test_a_certified_d0_carries_not_implementable_at_both_levels():
    text, _ = Rd.read(_rec(p2=0.005))
    assert text.count("registered weight, NOT IMPLEMENTABLE") == 1
    assert text.count("registered weight (90% level), NOT IMPLEMENTABLE") == 1


def test_a_failed_repeat_stops_and_the_read_happens_once(tmp_path):
    r = _rec()
    r["repeat_bit_identical"] = {"d1": False, "d0": True}
    assert Rd.read(r)[1] == {"stopped": True}
    (tmp_path / "results.json").write_text(json.dumps(_rec()))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
