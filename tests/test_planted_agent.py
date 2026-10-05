"""The planted-panel agent runner, in dry runs on a small synthetic base. No model call."""
import json

import pytest

from environments import planted_panel as pp
from experiments import planted_agent as pa
from experiments import price_runs as pr
from experiments.real_prompts import read_prompts
from tests.test_planted_panel import _panel
from tests.test_planted_view import REAL_NAMES


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture(scope="module")
def prompts():
    return read_prompts()


def _dry(base, prompts, arm, level=1.0, seed=640901):
    rec = pa.run_one(arm, seed, level, 0, prompts=prompts, dry_run=True, base=base)
    return json.loads(json.dumps(rec.to_json(), default=str))


def _ev(d, kind):
    return [e for e in d["events"] if e.get("kind") == kind]


@pytest.mark.parametrize("arm", pa.ARMS)
def test_a_dry_run_writes_a_complete_planted_run_file(base, prompts, arm):
    d = _dry(base, prompts, arm)
    start = _ev(d, "start")[0]
    assert start["panel"] == "planted" and start["level"] == 1.0 and start["masked"]
    for k in ("session_log", "declared_budget", "content_cap", "trigger_changes",
              "self_check", "pricing_deferred", "end"):
        assert _ev(d, k), k
    assert d["events"][-1]["kind"] == "end"
    assert _ev(d, "content_cap")[0]["cap"] == (3 if arm == "unsaturable" else None)
    assert _ev(d, "self_check")[0]["replayable"] is True


def test_the_unsaturable_arm_is_refused_past_three_content_moves(base, prompts):
    d = _dry(base, prompts, "unsaturable")
    refusals = [e for e in d["events"] if e.get("kind") == "refusal"]
    assert any("cap of 3 content moves" in json.dumps(e) for e in refusals)
    content = [r for r in _ev(d, "session_log")[0]["records"]
               if r["kind"] in ("init", "extend_best", "swap_worst", "flip", "refine", "pick")]
    assert len(content) <= 3


def test_prompts_carry_the_cap_sentence_on_the_unsaturable_arm_only(prompts):
    s = pa.cap_sentence()
    assert "at most 3 content moves" in s
    for arm in pa.ARMS:
        p = pa.prompt_for(arm, 40, 40, prompts)
        assert (s in p) == (arm == "unsaturable")
        assert not any(n in p for n in REAL_NAMES)


def test_price_runs_prices_dry_runs_with_the_cap_restored(base, prompts, monkeypatch,
                                                         tmp_path):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    inv = pp.invariants_for(base, cache_dir=tmp_path / "inv")
    monkeypatch.setattr(pp, "invariants_for", lambda b, **kw: inv)
    for arm in ("replay gate", "unsaturable"):
        d = _dry(base, prompts, arm, level=1.5, seed=640902)
        f = tmp_path / f"{d['run_id']}.json"
        f.write_text(json.dumps(d))
        r = pr.price_one((str(f), False, 30))
        assert r["certifying_null_computable"] is True, arm
        assert r["planted_truth"]["level"] == 1.5
        log = pr.rebuild_session_log(pr.load_run(f))
        assert log.content_cap == (3 if arm == "unsaturable" else None)


def test_only_dry_runs_on_design_seeds_until_stage_2_is_live():
    assert pa.AGENT_SEEDS is None and pa.LEVELS == (0.0, 1.0, 1.5)
    with pytest.raises(SystemExit, match="not live"):
        pa.check_seeds([640900], dry_run=False)
    with pytest.raises(SystemExit, match="design block"):
        pa.check_seeds([600000], dry_run=True)
    pa.check_seeds([640900, 640901], dry_run=True)
    with pytest.raises(SystemExit):
        pa.main(["--arm", "unsaturable", "--level", "1.0", "--runs", "1",
                 "--seed0", "640900"])                      # no --dry-run


def test_unregistered_arms_and_levels_are_refused(base, prompts):
    with pytest.raises(SystemExit):
        pa.run_one("control", 640901, 1.0, 0, prompts=prompts, dry_run=True, base=base)
    with pytest.raises(SystemExit):
        pa.run_one("unsaturable", 640901, 0.5, 0, prompts=prompts, dry_run=True, base=base)
