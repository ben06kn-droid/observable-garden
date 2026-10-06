"""The replay-tier V3 reader, on SYNTHETIC files only."""
import json

import pytest

from experiments import confidence_v3_replay_read as vr
from tests.test_confidence_cell_read import _conf, _rec
from experiments import confidence_cell_read as cr


def _file(tmp_path, recs):
    f = tmp_path / "d.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return f


def test_it_reads_the_replay_tiers_p5_not_the_class_tiers(tmp_path):
    recs = [_rec(s) for s in cr.SEEDS]
    for r in recs:                                     # class 0.75 (fixture), replay 0.25
        for lv in r["levels"]:
            for s in lv["searchers"]:
                s["conf_replay"] = _conf(1.5, 0.5, 0.25)
    text = vr.read(cr.load(_file(tmp_path, recs)))
    assert "SECONDARY, ON DATA ALREADY READ" in text and "TRIGGER-REPLAY" in text
    assert "mean P 0.250" in text and "mean P 0.750" not in text
    # outcome always true: Brier (0.25 - 1)^2 = 0.5625 over 6,000 per level; the fixture
    # certifies every run, so "all" and "certified" both carry it: 3 levels x 2 x 2
    assert text.count("n 6000, Brier 0.5625") == 12


def test_the_certified_subset_follows_the_class_tier(tmp_path):
    recs = [_rec(s, p_class=(0.01 if s % 2 else 0.5)) for s in cr.SEEDS]
    text = vr.read(cr.load(_file(tmp_path, recs)))
    cert = [l for l in text.splitlines() if l.strip().startswith("certified")]
    assert len(cert) == 6 and all(" n 3000," in l for l in cert)


def test_it_refuses_any_file_but_the_registered_one(tmp_path):
    f = _file(tmp_path, [_rec(s) for s in cr.SEEDS])
    with pytest.raises(SystemExit, match="SHA-256"):
        vr.check(f)
    vr.check(f, sha256=None)
