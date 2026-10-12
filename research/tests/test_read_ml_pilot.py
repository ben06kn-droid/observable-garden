"""The ML pilot's reader on synthetic rows only (no pilot result exists when this is written)."""
import numpy as np
import pytest

from experiments import read_ml_pilot_2026_10_07 as R

NAMES = R.PREDICTORS


def _pred(p, level=1.5, net=0.9, gross=1.2):
    return {"p": p, "turnover": 0.2, "cap_binding_share": 0.0,
            "pop": {"net": net, "gross": gross},
            "plant_window": {"net": level, "gross": level * 1.3},
            "diagnostics": [{"year": 3, "c": 1.0, "T_years": 3.0, "effective": {"total": 6.0, "A": 6.0},
                             "abs_weight_by_block": {"A": 1.0},
                             "penalties": [1, 3], "stack_weights": [0.7, 0.3]}]}


def _level0(n_cert: dict, cost: str, n=100):
    out = []
    for i in range(n):
        out.append({"seed": 687200 + i, "kind": "level0", "cost": cost, "level": 0.0,
                    "class": {"p": 0.5} if cost == "registered" else None,
                    "predictors": {k: _pred(0.01 if i < n_cert.get(k, 0) else 0.5)
                                   for k in NAMES}})
    return out


def _planted(cert: dict, level=1.5):
    """cert: {predictor: boolean array over the 200 panels, ordered by seed}."""
    out = []
    shapes = [s for s in R.RULES for _ in range(50)]
    for i in range(200):
        out.append({"seed": 687000 + i, "kind": "planted", "shape": shapes[i], "level": level,
                    "cost": "registered", "speed": "fast" if i % 25 == 0 else "slow",
                    "shadow_share": 0.5, "class": {"p": 0.01},
                    "predictors": {k: _pred(0.01 if cert[k][i] else 0.5, level) for k in NAMES}})
    return out


def test_level_fails_iff_the_lower_wilson_end_of_the_zero_cost_rate_exceeds_005():
    recs = _level0({"control": 9, "ridge_stack": 10}, "zero") + _level0({}, "registered")
    v = R.level_verdicts(recs)
    assert v["control"]["k"] == 9 and not v["control"]["fails"]
    assert v["ridge_stack"]["k"] == 10 and v["ridge_stack"]["fails"]
    # the at-cost panels never decide level
    recs2 = _level0({}, "zero") + _level0({k: 30 for k in NAMES}, "registered")
    assert not any(x["fails"] for x in R.level_verdicts(recs2).values())


def _cf(cert, zero_cert=None):
    recs = _planted(cert) + _level0(zero_cert or {}, "zero") + _level0({}, "registered")
    return R.carry_forward(recs, R.level_verdicts(recs))


def _arr(k, n=200, offset=0):
    a = np.zeros(n, bool)
    a[offset:offset + k] = True
    return a


def test_no_qualifier_carries_the_control_forward():
    same = _arr(60)
    cf = _cf({k: same for k in NAMES})
    assert cf["decision"] == "control" and "nothing detectable" in cf["note"]
    assert cf["mv_setting"] == "mv_combine risk on"            # interval includes zero


def test_a_clear_winner_is_carried_forward_and_the_interval_is_paired():
    cf = _cf({"control": _arr(40), "ridge_stack": _arr(100), "mv_combine risk on": _arr(40),
              "mv_combine risk off": _arr(40)})
    assert cf["decision"] == "ridge_stack"
    d, lo, hi = cf["comparisons"]["ridge_stack - control"]
    assert d == pytest.approx(0.30) and lo > 0
    # nested certifications: the paired difference has a narrow interval
    assert hi - lo < 0.15


def test_ties_go_to_mv_combine_and_risk_sizing_off_needs_an_interval_above_zero():
    cf = _cf({"control": _arr(40), "ridge_stack": _arr(100), "mv_combine risk on": _arr(100),
              "mv_combine risk off": _arr(100)})
    assert cf["mv_setting"] == "mv_combine risk on"
    assert cf["decision"] == "mv_combine risk on" and "tie" in cf["note"]
    cf2 = _cf({"control": _arr(40), "ridge_stack": _arr(40), "mv_combine risk on": _arr(60),
               "mv_combine risk off": _arr(120)})
    assert cf2["mv_setting"] == "mv_combine risk off"
    assert cf2["decision"] == "mv_combine risk off"


def test_a_predictor_that_fails_level_is_not_carried_forward():
    cf = _cf({"control": _arr(40), "ridge_stack": _arr(150), "mv_combine risk on": _arr(40),
              "mv_combine risk off": _arr(40)}, zero_cert={"ridge_stack": 20})
    assert cf["decision"] == "control"
    assert "ridge_stack - control" not in cf["comparisons"]


def test_a_control_that_fails_level_stops_the_rule():
    cf = _cf({k: _arr(60) for k in NAMES}, zero_cert={"control": 20})
    assert cf["decision"] is None and "STOP" in cf["note"]


def test_the_bootstrap_is_seeded_from_the_block():
    cert = {"control": _arr(40), "ridge_stack": _arr(55, offset=30),
            "mv_combine risk on": _arr(40), "mv_combine risk off": _arr(40)}
    a, b = _cf(cert), _cf(cert)
    assert a["comparisons"] == b["comparisons"]
    assert R.CARRY_SEED == 687999 and R.B_CARRY == 10_000


def test_the_whole_read_renders_with_thin_cells_marked():
    cert = {k: _arr(60) for k in NAMES}
    recs = _planted(cert) + _level0({}, "zero") + _level0({}, "registered")
    text, cf = R.read(recs, [])
    for head in ("R1. LEVEL", "R2. POWER", "R3. CAPTURE", "R4. DESCRIPTIVE", "CARRY-FORWARD"):
        assert head in text
    assert text.index("R1.") < text.index("R2.") < text.index("R3.") < text.index("R4.") \
        < text.index("CARRY-FORWARD")
    assert "THIN" in text                      # 2 fast panels per rule
    assert R.capture(recs[0], "control", "net") == pytest.approx(0.9 / 1.5)
