"""The V2 driver (`experiments/confidence_cell.py`) on a small synthetic base."""
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from experiments import confidence_cell as cc
from experiments import planted_edge as pe
from quixote.confidence import GRID
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture(scope="module")
def inv(base, tmp_path_factory):
    return pp.invariants_for(base, cache_dir=tmp_path_factory.mktemp("inv"))


@pytest.mark.parametrize("beta", [0.0, 1.0])
def test_every_shared_field_equals_the_stage1_drivers(base, inv, beta):
    ref = pe.run_level(base, 640021, beta, B=30, inv=inv)
    got = cc.run_level_conf(base, 640021, beta, B=30, inv=inv)
    for k in ("c", "planted", "block_length_null", "class_max", "class_argmax",
              "pop_best", "pop_best_sr", "null_max_mean"):
        assert got[k] == ref[k], k
    for a, b in zip(got["searchers"], ref["searchers"]):
        for k in ("searcher", "support", "score", "n_moves", "p_class", "p_trigger",
                  "truth", "holdout_realized"):
            assert a[k] == b[k], (a["searcher"], k)
    np.testing.assert_array_equal(got["_overlap"][0], ref["_overlap"][0])


def test_d_bounds_every_members_error_and_matches_its_quantiles(base, inv):
    r = cc.run_level_conf(base, 640022, 1.0, B=40, inv=inv)
    v2 = r["v2"]
    for s in r["searchers"] + [r["argmax"]]:
        assert v2["D"] >= s["score"] - s["truth"]["in_sample"] - 1e-12
    for g in cc.GS:
        assert v2["covered"][f"{g:.2f}"] == (v2["D"] <= v2["q"][f"{g:.2f}"])
    assert 0.0 <= v2["u"] <= 1.0


def test_confidence_fields_agree_with_both_tiers_p_values(base, inv):
    r = cc.run_level_conf(base, 640023, 1.5, B=40, inv=inv)
    k0 = int(np.flatnonzero(GRID == 0.0)[0])
    for s in r["searchers"]:
        assert s["conf_class"]["C0"] == pytest.approx(1 - s["p_class"], abs=1e-15)
        assert s["conf_replay"]["C0"] == pytest.approx(1 - s["p_trigger"], abs=1e-15)
        C = 1 - (1 + np.array(s["conf_class"]["n_ge"])) / (40 + 1)
        assert C[k0] == pytest.approx(s["conf_class"]["C0"], abs=1e-15)
        assert np.all(np.diff(C) <= 0) and len(C) == GRID.size
    assert r["argmax"]["conf_class"]["S"] == r["class_max"]


def test_the_smoke_record_carries_no_rule_quantity(base, monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    real = pp.invariants_for
    monkeypatch.setattr(pp, "invariants_for", lambda b: real(b, cache_dir=tmp_path))
    rec = cc.run_seed((981000, [0.0, 1.0], 20))
    text = json.dumps(cc.cost_only(rec))
    for word in ("p_class", "p_trigger", "truth", "conf", "v2", "covered", "class_max",
                 "score", "pop_best", "\"D\"", "P_H"):
        assert word not in text, word


def test_the_registered_run_is_refused_until_v2_is_live(tmp_path):
    f = tmp_path / "p.md"
    f.write_text("# draft\n")
    with pytest.raises(SystemExit, match="not live"):
        cc.require_live(f)
    f.write_text("# x\n\n## V2 — LIVE, someday\n")
    cc.require_live(f)                                  # no raise
    if cc.LIVE_MARK not in cc.PREREG.read_text():
        with pytest.raises(SystemExit, match="not live"):
            cc.main(["--workers", "1"])


def test_the_smoke_block_is_this_files_own():
    assert cc.SEED0_SMOKE == 981_000 and cc.SEED0 == 620_000
    assert cc.LEVELS == (0.0, 1.0, 1.5)
    with pytest.raises(SystemExit, match="981000-981999"):
        cc.main(["--smoke", "1001"])
