"""The version-2 confirmation reader on made-up rows only."""
import numpy as np

from experiments import read_ml_v2_confirm_2026_10_09 as R


def _st(p):
    return {"p": p, "cost_per_year": 0.01, "ann_vol": 0.06, "pop": {"net": 0.5, "gross": 0.7},
            "plant_window": {"net": 1.0, "gross": 1.2}}


REF = {m: [{"penalties": {"L": 30.0, "Q": 1e6, "I": 3.0, "S": 1.0}, "stack": [0.5, 0.1]}] * 9 for m in ("roll756", "expand")}


def _recs(cert, level0=None, seeds=80):
    level0 = level0 or {}
    recs = []
    for k, sh in enumerate(R.SHAPES):
        for i in range(seeds):
            for lev in R.LEVELS:
                recs.append({"kind": "seed", "seed": 699000 + 80 * k + i, "shape": sh, "level": lev,
                             "class": {"p": 0.5}, "refits_v2": REF,
                             "capture_by_memory": {m: {"net": 0.3, "gross": 0.4} for m in REF},
                             "arms": {a: {s: _st(0.01 if cert.get((a, s), lambda *x: False)(sh, i, lev) else 0.5)
                                          for s in R.STREAMS} for a in ("registered", "high")}})
    for i in range(400):
        recs.append({"kind": "level0", "seed": 700000 + i, "class": {"p": 0.5},
                     "arms": {a: {s: _st(0.01 if i < level0.get((a, s), 0) else 0.5) for s in R.STREAMS}
                              for a in ("zero", "registered", "high")}})
    return recs


def arms(s, f):
    return {("registered", s): f, ("high", s): f}


def test_both_hold_replaces_and_the_order_is_level_claims_secondary():
    c = {**arms("v2 base", lambda sh, i, l: i < 40), ("registered", "version 1"): lambda sh, i, l: i < 40,
         ("high", "version 1"): lambda sh, i, l: i < 10}
    text, out = R.read(_recs(c))
    assert out["claims"]["H_holds"] and out["claims"]["R_holds"]
    assert "Version 2 replaces version 1" in out["claims"]["outcome"]
    assert text.index("LEVEL") < text.index("CLAIMS") < text.index("SECONDARY")
    assert out["claims"]["R"][0] == 0.0 and out["claims"]["R"][1] > -0.03


def test_h_only_r_only_and_neither():
    h_only = {("high", "v2 base"): lambda sh, i, l: i < 40, ("high", "version 1"): lambda sh, i, l: i < 10,
              ("registered", "v2 base"): lambda sh, i, l: i < 10, ("registered", "version 1"): lambda sh, i, l: i < 40}
    o = R.read(_recs(h_only))[1]["claims"]
    assert o["H_holds"] and not o["R_holds"] and "offered only for high-cost panels" in o["outcome"]
    same = lambda sh, i, l: i < 30
    o2 = R.read(_recs({**arms("v2 base", same), **arms("version 1", same)}))[1]["claims"]
    assert o2["R_holds"] and not o2["H_holds"] and "Version 1 stays" in o2["outcome"]
    worse = {**arms("v2 base", lambda sh, i, l: i < 10), **arms("version 1", lambda sh, i, l: i < 40)}
    o3 = R.read(_recs(worse))[1]["claims"]
    assert not o3["H_holds"] and not o3["R_holds"] and o3["outcome"].startswith("Neither")


def test_the_margin_and_the_97_5_interval():
    rng = np.random.default_rng(0)
    a, b = rng.random(1120) < 0.4, rng.random(1120) < 0.4
    idx = np.random.default_rng(R.PAIRED_SEED).integers(0, 1120, size=(R.B_PAIRED, 1120))
    d, lo, hi = R.paired(a, b, idx)
    boot = (a.astype(float) - b)[idx].mean(axis=1)
    assert lo == np.quantile(boot, 0.0125) and hi == np.quantile(boot, 0.9875)
    assert R.MARGIN == 0.03 and R.PAIRED_SEED == 699999


def test_level_failure_voids_both_claims():
    c = {**arms("v2 base", lambda sh, i, l: i < 40), **arms("version 1", lambda sh, i, l: i < 10)}
    text, out = R.read(_recs(c, {("zero", "v2 base"): 29}))
    assert out["level"]["fails"] and out["claims"]["outcome"].startswith("VOID") and "VOID" in text


def test_a_short_task_list_is_not_read():
    text, out = R.read(_recs({}, seeds=79))
    assert out["claims"]["outcome"] is None and "STOP" in text
