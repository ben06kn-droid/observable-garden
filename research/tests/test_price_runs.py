"""Deferred pricing: `agent_cell --defer-pricing` then `price_runs` must give the
verdict the in-line path gives, field for field.

The session is the scripted policy `--dry-run` uses, but driven through the
NON-dry path (the model call is replaced, nothing else), so the in-line run is
actually priced and there is something to compare against. `CERTIFY_B` and the
class-p B are cut to keep this fast; both paths read the same constant, so the
comparison is unaffected.
"""
import json

import pytest

import experiments.agent_backend as ab
import experiments.agent_cell as ac
from experiments import price_runs as pr

SEED = 20260929


@pytest.fixture
def scripted(monkeypatch):
    monkeypatch.setattr(ac, "_drive_model", lambda arm, rec, handlers, *a, **k:
                        ac._scripted(rec, handlers, arm))
    monkeypatch.setattr(ab, "CERTIFY_B", 20)


def _write(tmp_path, name, defer):
    rec, _ = ac.run_one("replay gate", "s0", SEED, 0, prompts=ac.read_prompts(),
                        credential="seat", defer_pricing=defer)
    d = tmp_path / name
    d.mkdir()
    path = d / f"{rec.run_id}.json"
    path.write_text(json.dumps(rec.to_json(), indent=1, default=str))
    return path


def test_a_deferred_run_carries_its_log_and_self_check_and_no_verdict(tmp_path, scripted):
    d = json.loads(_write(tmp_path, "deferred", True).read_text())
    kinds = [e["kind"] for e in d["events"]]
    assert "pricing_deferred" in kinds and "self_check" in kinds
    assert "session_log" in kinds and kinds[-1] == "end"
    assert d["verdict"] is None and d["certifying_null_computable"] is None
    assert "verdict" not in kinds and "certify_error" not in kinds


def test_check_mode_reproduces_an_in_line_verdict_field_for_field(tmp_path, scripted):
    path = _write(tmp_path, "inline", False)
    stored = json.loads(path.read_text())
    assert stored["verdict"] is not None, "the in-line path must have priced the run"
    r = pr.price_one((str(path), True, 20))
    assert pr.compare(stored, r) == []
    assert path.read_text() == json.dumps(stored, indent=1, default=str), \
        "--check must write nothing"


def test_pricing_a_deferred_run_gives_the_in_line_verdict(tmp_path, scripted):
    inline = json.loads(_write(tmp_path, "inline", False).read_text())
    path = _write(tmp_path, "deferred", True)
    assert pr.main(["--dir", str(path.parent), "--workers", "1", "--B", "20"]) == 0
    priced = json.loads(path.read_text())
    assert pr.compare(inline, {**priced, "verdict_events": [
        e for e in priced["events"] if e["kind"] in ("verdict", "certify_error")]}) == []
    kinds = [e["kind"] for e in priced["events"]]
    assert kinds[-1] == "end", "`end` stays the completion marker"
    assert {"class_p", "priced_from_log", "pricing_deferred"} <= set(kinds)
    assert 0 < priced["class_p"]["p_upper"] <= 1
    # a second pass finds nothing left to write
    before = path.read_text()
    assert pr.main(["--dir", str(path.parent), "--workers", "1", "--B", "20"]) == 0
    assert path.read_text() == before


def test_an_in_line_verdict_is_never_overwritten(tmp_path, scripted):
    path = _write(tmp_path, "inline", False)
    verdict = json.loads(path.read_text())["verdict"]
    assert pr.main(["--dir", str(path.parent), "--workers", "1", "--B", "20"]) == 0
    d = json.loads(path.read_text())
    assert d["verdict"] == json.loads(json.dumps(verdict, default=str))
    assert d["class_p"] is not None
