"""The score-rank reader, on SYNTHETIC files in the results' format -- never on the results."""
import json

import numpy as np
import pytest

from experiments import planted_twins_read as rd

SEARCHERS = ["stop-when-cleared", "extend-while-improving", "cleared-restart",
             "lookahead-stop-when-cleared", "random-extend-while-improving",
             "second-best-while-improving"]


def _synthetic(path, n=1000, reject_level0=None, seed0=650000, rng_seed=0):
    """`reject_level0[(searcher, construction)]` = how many level-0 panels reject."""
    rng = np.random.default_rng(rng_seed)
    reject_level0 = reject_level0 or {}
    lines = []
    for i in range(n):
        levels = []
        for beta in (0.0, 1.0):
            ss = []
            for name in SEARCHERS:
                rec = {"searcher": name, "support": [[0, 1.0]], "score_real": 0.1,
                       "truth_in_sample": (-0.2 if beta == 0 else (0.5 if i % 3 else -0.1))}
                for c in rd.CONSTRUCTIONS:
                    if beta == 0:
                        hit = i < reject_level0.get((name, c), 0)
                    else:
                        hit = i % 2 == 0
                    rec[f"p_score_{c}"] = 1 / 20 if hit else int(rng.integers(2, 21)) / 20
                    rec[f"ties_{c}"] = int(i % 10 == 0)
                ss.append(rec)
            levels.append({"seed": seed0 + i, "beta": beta, "c": 0.0, "searchers": ss,
                           "median_lag1_autocorr_signed_singles": float(rng.normal(-0.01, 0.02)),
                           "secs": {}})
        lines.append(json.dumps({"seed": seed0 + i, "cell": "score", "levels": levels}))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_it_refuses_anything_but_exactly_1000_distinct_seeds(tmp_path):
    with pytest.raises(SystemExit, match="exactly 1000"):
        rd.load(_synthetic(tmp_path / "a.jsonl", n=999))
    f = _synthetic(tmp_path / "b.jsonl")
    lines = f.read_text().splitlines()
    lines[-1] = lines[0]                                    # a duplicate seed
    f.write_text("\n".join(lines) + "\n")
    with pytest.raises(SystemExit, match="exactly 1000"):
        rd.load(f)
    f.write_text("\n".join(lines[:-1] + ['{"seed": 1, "lev']) + "\n")
    with pytest.raises(SystemExit, match="does not parse"):
        rd.load(f)


def test_t1_counts_and_the_registered_threshold(tmp_path):
    f = _synthetic(tmp_path / "c.jsonl", reject_level0={
        ("stop-when-cleared", "joint_time_permutation"): 63,
        ("stop-when-cleared", "block_permutation"): 50})
    text, failed = rd.read(rd.load(f))
    assert not failed
    row = next(l for l in text.splitlines() if "stop-when-cleared" in l and "joint_time" in l)
    assert " 63 " in row and "PASS" in row
    assert "3. LEVEL 1.0 — DESCRIPTIVE" in text


def test_a_failing_rule_stops_after_t1_and_prints_the_replication(tmp_path):
    f = _synthetic(tmp_path / "d.jsonl", reject_level0={
        ("cleared-restart", "block_permutation"): 64})
    text, failed = rd.read(rd.load(f))
    assert failed
    row = next(l for l in text.splitlines() if "cleared-restart" in l and "block_perm" in l
               and "lookahead" not in l)
    assert " 64 " in row and "FAILS HIGH" in row
    assert "LEVEL 1.0 — NOT PRINTED" in text and "--replication" in text
    assert "DESCRIPTIVE" not in text


def test_level_1_separates_correct_rejections_from_rejections_of_non_positive_truth(tmp_path):
    text, _ = rd.read(rd.load(_synthetic(tmp_path / "e.jsonl")))
    # level 1.0: rejections on even panels; truth > 0 unless i % 3 == 0
    k_correct = sum(1 for i in range(1000) if i % 2 == 0 and i % 3)
    k_wrong = sum(1 for i in range(1000) if i % 2 == 0 and i % 3 == 0)
    # table rows: a searcher, a Wilson interval, no seed (the separately listed lines
    # carry a seed); the first twelve are T1's, the next twelve level 1.0's
    rows = [l for l in text.splitlines()
            if "[" in l and "seed" not in l and any(f" {s} " in f" {l.strip()} " for s in SEARCHERS)]
    assert len(rows) == 24
    level1 = rows[12:24]
    assert all(f" {k_correct} " in r for r in level1)
    assert f"listed separately: {k_wrong * 12}" in text


def test_the_autocorrelation_sign_is_reported(tmp_path):
    text, _ = rd.read(rd.load(_synthetic(tmp_path / "f.jsonl")))
    assert "median_lag1_autocorr_signed_singles" in text and "negative: predicts" in text
