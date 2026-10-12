"""The stage-1 secondary V1 reader, on SYNTHETIC files only."""
import json

import pytest

from experiments import confidence_v1_read as cv

NAMES = ["s1", "s2", "s3", "s4", "s5", "s6"]


def _rec(seed, cover=True, none_for=None):
    """One synthetic seed record. q_0.95 = 1.0 and q_0.99 = 1.5; scores 2.0, so
    L_0.95 = 1.0 and L_0.99 = 0.5. Truth 1.2 covers both; truth 0.8 covers 0.99 only."""
    levels = []
    for beta in cv.LEVELS:
        ss = []
        for nm in NAMES:
            sr = 1.2 if cover else 0.8
            sup = None if nm == none_for else [[0, 1.0]]
            ss.append({"searcher": nm, "support": sup, "score": 2.0,
                       "truth": None if sup is None else {"in_sample": sr, "holdout": 0.0}})
        levels.append({"beta": beta, "null_max_q": {"0.05": 1.0, "0.01": 1.5},
                       "class_max": 2.0, "class_argmax_truth": {"in_sample": 1.2},
                       "searchers": ss})
    return {"seed": seed, "levels": levels}


def _write(tmp_path, recs):
    f = tmp_path / "draws.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return f


def test_coverage_counts_and_verdicts(tmp_path):
    recs = [_rec(s, cover=(s % 10 != 0)) for s in cv.SEEDS]        # 90% cover at 0.95
    text = cv.read(cv.load(_write(tmp_path, recs), sha256=None))
    # g = 0.95: 1800 of 2000 covered, upper Wilson end < 0.95 -> FAILS LOW
    line = next(l for l in text.splitlines() if l.strip().startswith("s1") and "1800" in l)
    assert "FAILS LOW" in line
    # g = 0.99: everything covered (0.8 >= 0.5) -> conservative
    g99 = text.split("g = 0.99")[1]
    assert all("conservative" in l for l in g99.splitlines()
               if l.strip().startswith(("s1", "(class argmax)")))
    assert "FAILS LOW: 24 of 56 tests" in text                    # 6 searchers x 4 levels at 0.95
    assert "SECONDARY, ON DATA ALREADY READ" in text


def test_the_argmax_row_uses_class_max_and_its_own_truth(tmp_path):
    recs = [_rec(s, cover=False) for s in cv.SEEDS]
    text = cv.read(cv.load(_write(tmp_path, recs), sha256=None))
    g95 = text.split("g = 0.95")[1].split("g = 0.99")[0]
    arg = [l for l in g95.splitlines() if l.strip().startswith("(class argmax)")]
    assert len(arg) == 4 and all(" 2000   2000" in l for l in arg)      # 1.2 >= 1.0
    s1 = [l for l in g95.splitlines() if l.strip().startswith("s1 ")]
    assert all("      0   2000" in l for l in s1)                         # 0.8 < 1.0


def test_a_run_without_a_submission_is_excluded_and_counted(tmp_path):
    recs = [_rec(s, none_for="s3" if s < 600010 else None) for s in cv.SEEDS]
    text = cv.read(cv.load(_write(tmp_path, recs), sha256=None))
    s3 = [l for l in text.splitlines() if l.strip().startswith("s3 ")]
    assert all(l.rstrip().endswith(" 10") and " 1990 " in l for l in s3)


def test_it_refuses_anything_but_the_registered_file(tmp_path):
    recs = [_rec(s) for s in cv.SEEDS]
    f = _write(tmp_path, recs)
    with pytest.raises(SystemExit, match="SHA-256"):
        cv.load(f)                                                 # registered hash
    with pytest.raises(SystemExit, match="seeds not exactly"):
        cv.load(_write(tmp_path, recs[:-1]), sha256=None)
    bad = [_rec(s) for s in cv.SEEDS]
    bad[5]["levels"] = bad[5]["levels"][:3]
    with pytest.raises(SystemExit, match="levels"):
        cv.load(_write(tmp_path, bad), sha256=None)


def test_quantile_keys_are_one_minus_g():
    assert cv.QKEY == {0.95: "0.05", 0.99: "0.01"}


def test_verdict_branches():
    assert cv.verdict(1800, 2000, 0.95)[2] == "FAILS LOW"
    assert cv.verdict(2000, 2000, 0.95)[2] == "conservative"
    assert cv.verdict(1900, 2000, 0.95)[2] == "within"
