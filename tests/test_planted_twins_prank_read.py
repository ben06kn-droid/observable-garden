"""The p-rank cell's reader, on SYNTHETIC files only."""
import json

import pytest

from experiments import planted_twins_prank_read as pr

NAMES = ["s1", "s2", "s3", "s4", "s5", "s6"]


def _rec(seed, rej0=False, rej15=True, cls15=True, truth15=0.5):
    def lv(beta, rej, cls, truth):
        return {"beta": beta, "median_lag1_autocorr_real": -0.05,
                "searchers": [{"searcher": nm, "p_class_real": 0.01 if cls else 0.5,
                               "truth_in_sample": truth,
                               **{f"p_twin_{c}": (0.05 if rej else 0.5)
                                  for c in pr.CONSTRUCTIONS},
                               **{f"ties_{c}": 0 for c in pr.CONSTRUCTIONS}}
                              for nm in NAMES]}
    return {"seed": seed, "cell": "prank",
            "levels": [lv(0.0, rej0, False, -0.2), lv(1.5, rej15, cls15, truth15)]}


def _f(tmp_path, recs):
    f = tmp_path / "d.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return f


def test_t1_passes_and_the_read_continues(tmp_path):
    recs = [_rec(s, rej0=(s % 100 < 4)) for s in pr.SEEDS]        # 40 of 1,000
    text, stopped = pr.read(pr.load(_f(tmp_path, recs)))
    assert not stopped and "all twelve PASS" in text and "3. T2" in text
    assert "negative: predicts a departure BELOW" in text


def test_t1_fails_high_at_64_and_the_read_stops(tmp_path):
    recs = [_rec(s, rej0=(s % 1000 < 64)) for s in pr.SEEDS]
    text, stopped = pr.read(pr.load(_f(tmp_path, recs)))
    assert stopped and "FAILS HIGH" in text and "3. T2" not in text
    assert "660000-660999" in text and "--replication" in text


def test_t2_counts_correct_rejections_and_discordance(tmp_path):
    # twin rejects on even seeds, class on all: twin 500, class 1000, class-only 500
    recs = [_rec(s, rej15=(s % 2 == 0)) for s in pr.SEEDS]
    text, _ = pr.read(pr.load(_f(tmp_path, recs)))
    line = next(l for l in text.split("3. T2")[1].splitlines() if l.strip().startswith("s1 "))
    assert " 500    1000         0        500" in line
    # a negative truth is never a correct rejection
    recs = [_rec(s, truth15=-0.1) for s in pr.SEEDS]
    text, _ = pr.read(pr.load(_f(tmp_path, recs)))
    line = next(l for l in text.split("3. T2")[1].splitlines() if l.strip().startswith("s1 "))
    assert "      0       0" in line


def test_it_refuses_the_wrong_block_shape_or_cell(tmp_path):
    recs = [_rec(s) for s in pr.SEEDS]
    with pytest.raises(SystemExit, match="seeds"):
        pr.load(_f(tmp_path, recs[1:]))
    bad = [_rec(s) for s in pr.SEEDS]
    bad[0]["cell"] = "score"
    with pytest.raises(SystemExit, match="p-rank"):
        pr.load(_f(tmp_path, bad))
    bad = [_rec(s) for s in pr.SEEDS]
    bad[0]["levels"][1]["beta"] = 1.0
    with pytest.raises(SystemExit, match="levels"):
        pr.load(_f(tmp_path, bad))
