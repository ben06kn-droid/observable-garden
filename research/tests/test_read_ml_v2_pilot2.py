"""The second version-2 pilot's reader on made-up rows only."""
import numpy as np

from experiments import read_ml_v2_pilot2_2026_10_09 as R


def _st(p):
    return {"p": p, "cost_per_year": 0.01, "ann_vol": 0.06, "turnover_per_unit_gross": 0.1,
            "pop": {"net": 0.5, "gross": 0.7}, "plant_window": {"net": 1.0, "gross": 1.2}}


REF = {m: [{"penalties": {"L": 10.0, "Q": 1e6, "I": 3.0, "S": 1.0}, "stack": [0.5, 0.1]}] * 9
       for m in ("roll252", "roll756", "expand")}


def _recs(cert, level0=None, arms=("registered", "high")):
    level0 = level0 or {}
    recs = []
    for k, sh in enumerate(R.SHAPES):
        for i in range(50):
            for lev in R.LEVELS:
                recs.append({"kind": "seed", "seed": 698000 + 50 * k + i, "shape": sh, "level": lev,
                             "speed": "fast" if i < 3 else "slow", "refits_v2": REF,
                             "capture_by_memory": {m: {"net": 0.4, "gross": 0.5} for m in REF},
                             "arms": {a: {s: _st(0.01 if cert.get((a, s), lambda *x: False)(sh, i, lev) else 0.5)
                                          for s in R.STREAMS} for a in arms}})
    for i in range(100):
        recs.append({"kind": "level0", "seed": 698400 + i, "refits_v2": REF, "capture_by_memory": {},
                     "arms": {a: {s: _st(0.01 if i < level0.get((a, s), 0) else 0.5) for s in R.STREAMS}
                              for a in arms + ("zero",)}})
    return recs


def both(s, f):
    return {("registered", s): f, ("high", s): f}


def test_replacement_in_both_arms_with_m2_carried_when_higher():
    c = {**both("v2 base M1", lambda sh, i, l: i < 25), **both("v2 base M2", lambda sh, i, l: i < 30),
         **both("version 1", lambda sh, i, l: i < 10)}
    text, out = R.read(_recs(c))
    for arm in R.ARMS:
        assert out["arms"][arm]["memory_set"] == "M2"
        assert out["arms"][arm]["decision"] == "version 2 replaces version 1"
    assert out["arms_agree"]
    assert text.index("R1.") < text.index("R2.") < text.index("R3.") < text.index("RULES")


def test_ties_go_to_m1_and_a_set_failing_level_is_excluded():
    same = lambda sh, i, l: i < 20
    c = {**both("v2 base M1", same), **both("v2 base M2", same), **both("version 1", same)}
    out = R.read(_recs(c))[1]
    assert out["arms"]["registered"]["memory_set"] == "M1"
    assert out["arms"]["registered"]["decision"] == "version 1 stays"
    out2 = R.read(_recs({**both("v2 base M2", lambda sh, i, l: i < 40)}, {("zero", "v2 base M2"): 15}))[1]
    assert out2["arms"]["high"]["sets_holding_level"] == ["M1"] and out2["arms"]["high"]["memory_set"] == "M1"


def test_disagreeing_arms_return_the_decision_and_the_fairness_flag_fires():
    c = {("registered", "v2 base M1"): lambda sh, i, l: i < 40, ("high", "v2 base M1"): lambda sh, i, l: i < 10,
         ("registered", "version 1"): lambda sh, i, l: i < 10, ("high", "version 1"): lambda sh, i, l: i < 10}
    out = R.read(_recs(c))[1]
    assert out["arms"]["registered"]["decision"] == "version 2 replaces version 1"
    assert out["arms"]["high"]["decision"] == "version 1 stays" and not out["arms_agree"]
    new_only = lambda sh, i, l: (i < 45) if sh in ("leadlag", "volcond", "regime") else (i < 5)
    out3 = R.read(_recs({**both("v2 base M1", new_only), **both("version 1", lambda sh, i, l: i < 15)}))[1]
    assert out3["arms"]["registered"]["fairness_flag"]


def test_no_set_holding_level_keeps_version_1():
    lv = {("zero", "v2 base M1"): 15, ("zero", "v2 base M2"): 15}
    text, out = R.read(_recs({}, lv))
    assert out["arms"]["registered"]["memory_set"] is None and "FAILS LEVEL" in text
    assert "THIN" in text and "version 1's cost drag on level-0 panels, high-cost arm" in text
