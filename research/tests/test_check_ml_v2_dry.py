"""The version-2 dry checker on made-up rows."""
import json

from experiments import check_ml_v2_dry as C


def _write(d, rows, dry=True):
    tasks = [["seed", 696500, "leadlag", None], ["menu", 696501, "volcond", 1.0], ["level0", 696502, None, None]]
    (d / "provenance.json").write_text(json.dumps({"platform": "Linux x86_64", "git_head": "x",
                                                   "dry_run": dry, "task_list": tasks}))
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def _rows():
    s = [{"kind": "seed", "seed": 696500, "rule": {"shape": "leadlag", "x": 3}, "streams": {"a": {"p": 0.4}}}] * 4
    m = [{"kind": "menu", "seed": 696501, "menus": {"G1": {"21": {"p": 0.3}}}}]
    z = [{"kind": "level0", "seed": 696502, "rule": None, "shape": None, "class": c, "streams": {"a": {"p": 0.5}}}
         for c in ({"p": 0.2}, None)]
    return s + m + z


def test_complete_rows_pass_and_problems_are_flagged(tmp_path):
    _write(tmp_path, _rows())
    L, ok = C.check(tmp_path)
    assert ok and L[-1] == "DRY RUN CHECK: PASS"
    rows = _rows()
    rows[0] = {**rows[0], "streams": {"a": {"p": float("nan")}}}
    _write(tmp_path, rows)
    assert not C.check(tmp_path)[1]
    _write(tmp_path, _rows()[:-1])
    assert not C.check(tmp_path)[1]
