"""The version-2 pilot's reader on made-up rows only."""
import numpy as np
import pytest

from experiments import read_ml_v2_pilot_2026_10_08 as R

S = R.SINGLES


def _st(p):
    return {"p": p, "score": 0.5, "turnover_per_row": 0.1, "turnover_per_unit_gross": 0.15,
            "cost_per_year": 0.01, "ann_vol": 0.06, "variant_corr_mean": 0.8,
            "pop": {"net": 0.6, "gross": 0.8}, "plant_window": {"net": 1.0, "gross": 1.2}}


def _menus(p=0.5, view=(["P", "X", "V"], 5, "market", "always")):
    return {g: {m: {"p": p, "score": 1.0, "view": list(view), "n": int(m)} for m in R.MENUS} for g in R.GRIDS}


def _recs(cert: dict, level0_cert: dict | None = None):
    """cert[stream] -> function(shape, i, level) -> bool."""
    recs = []
    for k, sh in enumerate(R.SHAPES):
        for i in range(50):
            for lev in R.LEVELS:
                streams = {s: _st(0.01 if cert.get(s, lambda *a: False)(sh, i, lev) else 0.5) for s in S}
                streams["v2 base edges"] = {"refits": 27, "at_edge": 20}
                rule = {"shape": sh, "g": "mkt_up"} if sh == "regime" else {"shape": sh}
                recs.append({"kind": "seed", "seed": 697000 + 50 * k + i, "shape": sh, "rule": rule,
                             "level": lev, "speed": "fast" if i < 3 else "slow", "class": {"p": 0.5},
                             "streams": streams})
                if i < 20 and lev in (1.0, 1.5):
                    v = (["X"], 1, "group", "always") if sh == "leadlag" else (["P"], 5, "market", "always")
                    recs.append({"kind": "menu", "seed": 697000 + 50 * k + i, "shape": sh, "rule": rule,
                                 "level": lev, "speed": "slow", "menus": _menus(0.01, v)})
    level0_cert = level0_cert or {}
    for i in range(100):
        for cost in ("zero", "registered"):
            streams = {s: _st(0.01 if i < level0_cert.get(s, 0) else 0.5) for s in S}
            streams["v2 base edges"] = {"refits": 27, "at_edge": 26}
            recs.append({"kind": "level0", "seed": 697400 + i, "shape": None, "rule": None, "level": 0.0,
                         "cost": cost, "class": {"p": 0.5} if cost == "registered" else None,
                         "streams": streams, "menus": _menus(0.5)})
    return recs


def test_replacement_holds_when_v2_beats_v1_with_level_held_and_grid_ties_go_slower():
    c = {"v2 base G1": lambda sh, i, l: i < 30, "v2 base G2": lambda sh, i, l: i < 30,
         "v2 base G3": lambda sh, i, l: i < 30, "version 1": lambda sh, i, l: i < 10}
    text, out = R.read(_recs(c))
    assert out["grid"] == "G3" and out["decision"] == "version 2 replaces version 1"
    assert out["replacement"][1] > 0 and not out["fairness_flag"]
    assert text.index("R1.") < text.index("R2.") < text.index("R3.") < text.index("R4.") < text.index("RULES")


def test_a_grid_failing_level_is_excluded_and_no_level_means_version_1_stays():
    c = {"v2 base G1": lambda sh, i, l: i < 40, "v2 base G3": lambda sh, i, l: i < 20,
         "version 1": lambda sh, i, l: i < 10}
    out = R.read(_recs(c, {"v2 base G1": 12}))[1]
    assert out["grids_holding_level"] == ["G2", "G3"] and out["grid"] == "G3"
    out2 = R.read(_recs(c, {f"v2 base {g}": 15 for g in R.GRIDS}))[1]
    assert out2["grid"] is None and out2["decision"] == "version 1 stays"


def test_no_significant_gain_keeps_version_1_and_the_fairness_flag_fires_on_new_shapes_only():
    same = lambda sh, i, l: i < 20
    out = R.read(_recs({"v2 base G1": same, "v2 base G2": same, "v2 base G3": same, "version 1": same}))[1]
    assert out["decision"] == "version 1 stays"
    new_only = lambda sh, i, l: (i < 45) if sh in ("leadlag", "volcond", "regime") else (i < 5)
    c = {"v2 base G1": new_only, "v2 base G2": new_only, "v2 base G3": new_only,
         "version 1": lambda sh, i, l: i < 15}
    out3 = R.read(_recs(c))[1]
    assert out3["fairness_flag"] and out3["fairness"][1] < -0.05


def test_tiered_scheme_and_natural_view_matching():
    rec = {"streams": {"v2 base G1": {"p": 0.03}}, "menus": {"G1": {"42": {"p": 0.03}, "294": {"p": 0.009}}}}
    assert R.tiered(rec, "G1")
    rec["menus"]["G1"]["294"]["p"] = 0.011
    assert not R.tiered(rec, "G1")
    assert R.matches({"shape": "leadlag", "rule": {}}, (["X", "P"], 1, "group", "always"))
    assert not R.matches({"shape": "volcond", "rule": {}}, (["P"], 1, "market", "always"))
    assert R.matches({"shape": "regime", "rule": {"g": "disp_low"}}, (["P"], 5, "market", "disp_low"))
    assert R.matches({"shape": "gated", "rule": {}}, (["P", "V"], 5, "market", "vol_high"))


def test_the_whole_read_renders_level_lines_and_thin_cells():
    text, _ = R.read(_recs({"version 1": lambda sh, i, l: i < 10}, {"plain ridge": 12}))
    assert "plain ridge" in text and "FAILS LEVEL" in text and "THIN" in text
    assert "294-winner matches natural view" in text and "class tier" in text
