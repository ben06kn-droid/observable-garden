"""`collect_submissions` writes exactly `name` and `weights`, and nothing else.

A submission file is the only thing that crosses to the holdout host, so anything extra
in it is something that did not need to cross. The weight rule is the gate's own
`quixote.grammar.weights`, because a second implementation of "what the submission means"
could disagree with the one that was certified.
"""
import json

import pytest

from experiments.collect_submissions import K_FOR, submissions_for


def _run(tmp_path, name, support, extra=None):
    d = tmp_path
    (d / f"{name}.json").write_text(json.dumps({
        "run_id": name, "submitted_support": support,
        # the fields a real run carries, none of which may reach the output
        "submitted_sharpe": 1.234, "seed": 7, "arm": "orientation",
        "credential": "seat", "verdict": {"status": "CERTIFIED", "p_certifying": 0.01},
        "events": [{"kind": "session_log", "records": []}],
        **(extra or {})}))
    return d


def test_only_name_and_weights_are_written(tmp_path):
    _run(tmp_path, "r0", [[3, 1.0], [7, -1.0]])
    subs = submissions_for([str(tmp_path)], K_FOR["etf"])
    assert len(subs) == 1
    assert set(subs[0]) == {"name", "weights"}
    # nothing from the run leaks through
    blob = json.dumps(subs)
    for leaked in ("submitted_sharpe", "1.234", "verdict", "CERTIFIED", "p_certifying",
                   "credential", "seat", "session_log", "arm"):
        assert leaked not in blob, leaked


def test_the_weights_are_the_gates_own_signed_indicator(tmp_path):
    _run(tmp_path, "r0", [[3, 1.0], [7, -1.0]])
    w = submissions_for([str(tmp_path)], 40)[0]["weights"]
    assert len(w) == 40
    assert w[3] == 1.0 and w[7] == -1.0
    assert sum(1 for v in w if v) == 2
    from quixote.grammar import weights
    assert w == [float(v) for v in weights(((3, 1.0), (7, -1.0)), 40)]


def test_run_config_and_derived_files_are_skipped(tmp_path):
    _run(tmp_path, "r0", [[1, 1.0]])
    (tmp_path / "run_config.json").write_text(json.dumps({"run_id": "cfg", "runs": 1}))
    (tmp_path / "class_p.json").write_text(json.dumps([{"run_id": "cp"}]))
    (tmp_path / "regrade_2026-09-28.json").write_text(json.dumps([{"file": "x"}]))
    subs = submissions_for([str(tmp_path)], 40)
    assert [s["name"] for s in subs] == ["r0"]


def test_a_run_that_did_not_submit_is_omitted(tmp_path):
    _run(tmp_path, "r0", [[1, 1.0]])
    (tmp_path / "r1.json").write_text(json.dumps(
        {"run_id": "r1", "submitted_support": None, "events": []}))
    assert [s["name"] for s in submissions_for([str(tmp_path)], 40)] == ["r0"]


def test_a_duplicate_name_is_refused(tmp_path):
    """The grader keys its output on the name, so a collision would silently merge two
    submissions into one row."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    _run(a, "same", [[1, 1.0]])
    _run(b, "same", [[2, 1.0]])
    with pytest.raises(SystemExit, match="duplicate run_id"):
        submissions_for([str(a), str(b)], 40)


def test_a_feature_index_outside_the_class_is_refused(tmp_path):
    _run(tmp_path, "r0", [[99, 1.0]])
    with pytest.raises(SystemExit, match="out of range"):
        submissions_for([str(tmp_path)], 40)


def test_the_real_shakeout_directory_yields_a_clean_file():
    """An integration check on a committed artifact: the ETF shake-out run."""
    from pathlib import Path
    d = Path("runs/shakeout_etf_orientation")
    if not d.exists():
        pytest.skip("the ETF shake-out directory is not present")
    subs = submissions_for([str(d)], K_FOR["etf"])
    assert subs and all(set(s) == {"name", "weights"} for s in subs)
    assert all(len(s["weights"]) == 40 for s in subs)
    assert all(any(v for v in s["weights"]) for s in subs)
