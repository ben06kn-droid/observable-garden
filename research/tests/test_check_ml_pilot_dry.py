"""The dry-run checker on synthetic rows: it passes complete finite rows with declared nulls,
flags undeclared nulls, non-finite values and missing tasks, and prints no value."""
import json

import pytest

from experiments import check_ml_pilot_dry as C


def _rows():
    pred = {"p": 0.3, "status": "FAIL", "pop": {"net": 0.4, "gross": 0.6},
            "diagnostics": [{"year": 3, "weights": [0.1, -0.2]}]}
    planted = [{"seed": 686004, "kind": "planted", "cost": "registered", "level": lev,
                "rule": {"shape": "gated", "a": 3, "b": None}, "shape": "gated",
                "class": {"p": 0.2}, "predictors": {"control": pred}} for lev in (1.0, 1.5, 2.5)]
    level0 = [{"seed": 686005, "kind": "level0", "cost": c, "level": 0.0, "rule": None,
               "shape": None, "class": {"p": 0.5} if c == "registered" else None,
               "predictors": {"control": pred}} for c in ("registered", "zero")]
    return planted + level0


def _write(d, rows, tasks=None):
    tasks = tasks or [["planted", 686004, "gated"], ["level0", 686005, None]]
    (d / "provenance.json").write_text(json.dumps({"platform": "Linux x86_64", "lightgbm": "4.7.0",
                                                   "git_head": "x", "dry_run": True,
                                                   "task_list": tasks}))
    (d / "pilot.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_complete_finite_rows_pass_and_no_value_is_printed(tmp_path):
    _write(tmp_path, _rows())
    L, ok = C.check(tmp_path)
    assert ok and L[-1] == "DRY RUN CHECK: PASS"
    text = "\n".join(L)
    assert "rows: 5 (expected 5)" in text and "tasks completed: 2 of 2" in text
    assert "predictors.control.pop.net" in text
    assert "0.4" not in text and "0.3" not in text and "FAIL" not in text.replace("PASS", "")


@pytest.mark.parametrize("break_it,needle", [
    (lambda r: r[0]["predictors"]["control"]["pop"].__setitem__("net", float("nan")),
     "predictors.control.pop.net: not finite"),
    (lambda r: r[1]["predictors"]["control"].__setitem__("p", None),
     "predictors.control.p: undeclared null"),
    (lambda r: r.pop(), "rows: 4 (expected 5)"),
])
def test_problems_are_flagged(tmp_path, break_it, needle):
    rows = _rows()
    break_it(rows)
    _write(tmp_path, rows)
    L, ok = C.check(tmp_path)
    assert not ok and any(needle in x for x in L) and L[-1] == "DRY RUN CHECK: PROBLEM"


def test_a_missing_task_is_flagged(tmp_path):
    _write(tmp_path, _rows()[:3], tasks=[["planted", 686004, "gated"]])
    L, ok = C.check(tmp_path)
    assert ok                                     # what was asked for is complete
    _write(tmp_path, _rows()[:3])
    L, ok = C.check(tmp_path)
    assert not ok and any("MISSING" in x for x in L)


def test_the_checker_reads_a_named_rows_file(tmp_path):
    _write(tmp_path, _rows())
    (tmp_path / "pilot.jsonl").rename(tmp_path / "results.jsonl")
    assert not C.check(tmp_path)[1]
    L, ok = C.check(tmp_path, "results.jsonl")
    assert ok and L[-1] == "DRY RUN CHECK: PASS"
