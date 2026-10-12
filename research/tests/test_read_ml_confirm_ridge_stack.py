"""The confirmation reader on made-up rows only (no confirmation result exists when this is
written)."""
import numpy as np
import pytest

from experiments import read_ml_confirm_ridge_stack as R

RULE_SEEDS = {"U": 689000, "corner": 689100, "product": 689200, "gated": 689300}


def _pred(p, level=1.5):
    return {"p": p, "turnover": 0.1, "cap_binding_share": 0.0,
            "pop": {"net": 0.5, "gross": 0.7},
            "plant_window": {"net": max(level, 1e-9), "gross": max(level, 1e-9) * 1.3},
            "diagnostics": [{"year": 3, "penalties": [3, 1e6, 10, 1e6], "stack_weights": [0.4, 0.2]}]}


def _planted(ridge, klass, control=None, level=1.5):
    """ridge, klass, control: boolean arrays over the 400 panels ordered by seed."""
    control = np.zeros(400, bool) if control is None else control
    out = []
    i = 0
    for shape, s0 in RULE_SEEDS.items():
        for j in range(100):
            out.append({"seed": s0 + j, "kind": "planted", "shape": shape, "level": level,
                        "cost": "registered", "speed": "fast" if j % 40 == 0 else "slow",
                        "shadow_share": 0.4, "class": {"p": 0.01 if klass[i] else 0.6},
                        "predictors": {"ridge_stack": _pred(0.01 if ridge[i] else 0.6, level),
                                       "control": _pred(0.01 if control[i] else 0.6, level)}})
            i += 1
    return out


def _level0(ridge_zero=0, ridge_cost=0, class_cost=0, n=400):
    out = []
    for i in range(n):
        for cost in ("zero", "registered"):
            k = ridge_zero if cost == "zero" else ridge_cost
            out.append({"seed": 689400 + i, "kind": "level0", "cost": cost, "level": 0.0,
                        "class": ({"p": 0.01 if i >= n - class_cost else 0.6}
                                  if cost == "registered" else None),
                        "predictors": {"ridge_stack": _pred(0.01 if i < k else 0.6, 0.0),
                                       "control": _pred(0.6, 0.0)}})
    return out


def _arr(k, n=400, offset=0):
    a = np.zeros(n, bool)
    a[offset:offset + k] = True
    return a


def test_level_fails_at_29_of_400_and_holds_at_28():
    assert not R.level_verdict(_level0(ridge_zero=28))["fails"]
    assert R.level_verdict(_level0(ridge_zero=29))["fails"]
    assert not R.level_verdict(_level0(ridge_cost=200))["fails"]      # cost panels never decide


def test_primary_holds_iff_the_lower_end_exceeds_zero():
    recs = _planted(_arr(240), _arr(80)) + _level0()
    p = R.primary(recs, R.level_verdict(recs))
    assert p["n"] == 400 and p["verdict"] == "HOLDS" and p["lo"] > 0
    assert p["difference"] == pytest.approx(0.40)


def test_primary_fails_at_this_n_when_the_interval_reaches_zero():
    recs = _planted(_arr(80, offset=0), _arr(80, offset=40)) + _level0()
    p = R.primary(recs, R.level_verdict(recs))
    assert p["lo"] <= 0 and p["verdict"] == "FAILED" and "failed at n = 400" in p["text"]


def test_primary_is_void_when_level_fails_even_if_the_interval_is_above_zero():
    recs = _planted(_arr(240), _arr(80)) + _level0(ridge_zero=40)
    p = R.primary(recs, R.level_verdict(recs))
    assert p["lo"] > 0 and p["verdict"] == "VOID"


def test_an_incomplete_primary_is_not_read():
    recs = _planted(_arr(240), _arr(80))[:-1] + _level0()
    assert R.primary(recs, R.level_verdict(recs))["verdict"] == "INCOMPLETE"


def test_the_paired_bootstrap_is_seeded_and_paired():
    a, b = _arr(120), _arr(100)                 # nested: every class certification is shared
    d, lo, hi = R.paired(a, b)
    assert (d, lo, hi) == R.paired(a, b)
    assert d == pytest.approx(0.05) and lo > 0 and hi - lo < 0.06
    assert R.PAIRED_SEED == 689999 and R.B_PAIRED == 10_000


def test_the_whole_read_in_order_with_either_tier_and_labels():
    recs = (_planted(_arr(240), _arr(80)) + _planted(_arr(10), _arr(5), level=1.0)[:200]
            + _level0(ridge_cost=6, class_cost=4))
    text, res = R.read(recs, [])
    assert text.index("4. LEVEL") < text.index("5. PRIMARY") < text.index("6. SECONDARY")
    e = res["secondary"]["either_tier_level0"]
    assert e == {"k": 10, "n": 400}             # 6 ridge (first rows) and 4 class (last rows)
    assert "penalty S: off" in text and "penalty L: 3 " in text and "1000000" not in text
    assert "THIN" in text                       # 3 fast panels per rule at level 1.5
    assert "no rule attaches" in text
