"""Sancho's config: the registered defaults, the hash, the one-line non-default notice."""
import json

import pytest

from sancho import config as C


def test_the_default_is_the_registered_version_2():
    cfg = C.load()
    v = cfg.values
    assert cfg.is_default and cfg.notice() is None and len(cfg.sha256) == 64
    assert v["information"] == "all" and v["horizon"] == 5 and v["neutrality"] == "market"
    assert v["regime"] == "always"
    assert v["memories"] == {"roll756": 756, "expand": None}                     # M2
    assert v["rates"] == [0.3, 0.1, 0.03]                                         # G3
    assert v["ridge"]["grids"]["L"] == [1.0, 3.0, 10.0, 30.0]                     # L {1, 3, 10, 30}
    assert v["first_scored_row"] == 756 and v["refit_every"] == 252 and v["warmup_rows"] == 64
    assert v["trees"]["lightgbm"] == "4.7.0" and v["trees"]["rounds"] == 50


def test_the_defaults_equal_the_learners_registered_constants():
    from sancho import learner as Ln
    from sancho import views as Vw
    v = C.load().values
    assert v["trees"]["params"] == Ln.TREES and v["trees"]["rounds"] == Ln.NTREE
    assert v["first_scored_row"] == Ln.FIRST and v["refit_every"] == Ln.REFIT and v["warmup_rows"] == Ln.WARMUP
    for b in ("Q", "I", "S"):
        assert tuple(v["ridge"]["grids"][b]) == Ln.GRIDS[b]
    assert tuple(v["rates"]) == Vw.RATE_GRIDS["G3"]


def test_a_changed_lever_changes_the_hash_and_prints_one_line(tmp_path, capsys):
    v = C.load().values
    v["horizon"] = 20
    p = tmp_path / "c.json"
    p.write_text(json.dumps(v))
    cfg = C.load(p)
    assert not cfg.is_default and cfg.sha256 != C.load().sha256
    line = cfg.notice()
    assert line.startswith(f"sancho: non-default configuration {cfg.sha256[:12]}.")
    assert "registered results apply to the default only" in line and "\n" not in line


def test_formatting_alone_does_not_change_the_hash(tmp_path):
    p = tmp_path / "same.json"
    p.write_text(json.dumps(C.load().values, indent=4))
    cfg = C.load(p)
    assert cfg.is_default and cfg.sha256 == C.load().sha256


def test_a_config_missing_a_lever_is_refused(tmp_path):
    v = C.load().values
    del v["rates"]
    p = tmp_path / "short.json"
    p.write_text(json.dumps(v))
    with pytest.raises(ValueError, match="missing levers"):
        C.load(p)
