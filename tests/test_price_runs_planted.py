"""7.5 build item 4: `price_runs` for planted panels, on a small synthetic base.

A planted agent run is searched on the MASKED view and priced from its file: the
class tier and the population truths are written into the run file, and the panel is
rebuilt through `planted_panel.load_base`, which loads the pinned X. The class tier and
the truths are held equal to the scripted driver's (`experiments/planted_edge.run_level`)
on the same seed and level, which is what makes the agent and scripted halves one
measurement.
"""
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from environments.class_table import canonical
from environments.planted_view import agent_view
from environments.real_sandbox import RealSandbox
from experiments import planted_edge as pe
from experiments import price_runs as pr
from quixote.agent_adapter import ToolSession
from quixote.session import Session
from tests.test_planted_panel import _panel

B = 40


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture
def patched(base, monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    real = pp.invariants_for
    inv = real(base, cache_dir=tmp_path / "inv")
    monkeypatch.setattr(pp, "invariants_for", lambda b, **kw: inv)
    return base, inv


def _run_file(seed, beta, base, arm="replay gate"):
    """An agent run on the masked view, written as `experiments/agent_cell.py` writes
    a deferred run."""
    draw = pp.make_draw(base, seed, beta)
    view, mask = agent_view(draw.in_sample, seed)
    tools = ToolSession(Session.on_sandbox(RealSandbox(view, spec_class=pp.CLS), pp.CLS,
                                           name_prefix="t"), max_turns=60)
    tools.call("declare_triggers", triggers=[
        {"trigger": "failures_at_least", "param": 2, "action": "stop"}])
    tools.call("init")
    for _ in range(4):
        try:
            tools.call("extend_best")
        except Exception:
            break
    try:
        tools.call("stop", trigger="failures_at_least", param=2)
    except Exception:
        pass
    tools.call("submit")
    s = tools.session
    s.close()
    records = [
        {"step": r.step, "kind": r.move.kind, "support": list(r.support_after),
         "score": r.score_after, "n_candidates": r.n_candidates,
         "trigger": r.trigger, "trigger_value": r.trigger_value,
         "replayable": r.replayable, "contradicted": r.contradicted,
         "move": {"kind": r.move.kind, "statistic": r.move.statistic,
                  "feature": r.move.feature, "note": r.move.note,
                  "among": list(r.move.among or ()),
                  "else_statistic": r.move.else_statistic, "choice": r.move.choice}}
        for r in s.log.records]
    support, score = s.submission()
    return {"run_id": f"cell_planted_0_{arm.replace(' ', '_')}_{seed}", "arm": arm,
            "seed": seed,
            "submitted_support": [[int(k), float(x)] for k, x in support],
            "submitted_sharpe": float(score),
            "triggers_predeclared": [dict(t) for t in s.log.declared_trigger_records],
            "events": [
                {"t": 0, "kind": "start", "arm": arm, "seed": seed, "panel": "planted",
                 "level": beta},
                {"t": 1, "kind": "declared_budget", "budget": s.log.budget},
                {"t": 2, "kind": "session_log", "records": records},
                {"t": 3, "kind": "trigger_changes", "changes": []},
                {"t": 4, "kind": "pricing_deferred"},
                {"t": 5, "kind": "end"}]}, mask


@pytest.mark.parametrize("beta", [0.0, 1.0])
def test_a_planted_run_is_priced_at_both_tiers_with_its_truths(patched, beta, tmp_path):
    base, _ = patched
    d, mask = _run_file(640003, beta, base)
    f = tmp_path / "cell_planted_0_replay_gate_640003.json"
    f.write_text(json.dumps(d))
    r = pr.price_one((str(f), False, B))
    assert r["certifying_null_computable"] is True
    assert r["verdict"]["p_certifying"] is not None
    assert 1 / (B + 1) <= r["class_p"]["p_upper"] <= 1.0 and r["class_p"]["B"] == B
    t = r["planted_truth"]
    true = canonical(mask.to_true(tuple(tuple(x) for x in d["submitted_support"])))
    assert t["submitted_support_true"] == [list(x) for x in true]
    assert t["feature_mask"] == list(mask.perm)
    # the realized Sharpe the class tier priced is the one the agent was shown
    assert t["submitted_realized"] == pytest.approx(d["submitted_sharpe"], abs=1e-12)
    # the in-sample truth is the generator's own population Sharpe
    draw = pp.make_draw(base, 640003, beta)
    assert t["submitted_truth"]["in_sample"] == pytest.approx(
        pp.truth(base, draw, true)["in_sample"], abs=1e-9)
    if beta == 0.0:
        assert t["submitted_truth"]["in_sample"] < 0       # level 0 is a null
    else:
        assert t["planted_truth"]["in_sample"] == pytest.approx(beta, abs=1e-8)


def test_the_class_tier_and_truths_equal_the_scripted_drivers(patched):
    """For each scripted searcher's submission, masked and priced here, the class p,
    the population-best member, the class argmax and the planted rank are the
    scripted driver's own."""
    base, inv = patched
    seed, beta = 640004, 1.0
    ref = pe.run_level(base, seed, beta, B=B, inv=inv)
    b, draw, view, mask = pr.planted_basis(seed, beta)
    table, pop = pr.planted_table(b, draw, view, mask, inv=inv)
    sandbox = RealSandbox(view, spec_class=pp.CLS)
    for s in ref["searchers"]:
        sup_true = tuple(tuple(x) for x in s["support"])
        sup_m = [list(x) for x in mask.to_masked(sup_true)]
        cp = pr.class_p_etf(sandbox, table, seed, sup_m, B)
        assert cp["p_upper"] == s["p_class"], s["searcher"]
        assert cp["block_length"] == ref["block_length_null"]
        t = pr.planted_truth(b, draw, view, mask, table, pop, sup_m)
        assert t["submitted_truth"]["in_sample"] == pytest.approx(
            s["truth"]["in_sample"], abs=1e-12)
        assert t["submitted_truth"]["holdout"] == s["truth"]["holdout"]
        assert t["submitted_holdout_realized"] == pytest.approx(s["holdout_realized"],
                                                               abs=1e-12)
        for k in ("equals", "two_of_three", "equals_pop_best", "two_of_three_pop_best"):
            assert t["submitted_recovery"][k] == s[k], k
    for k in ("pop_best", "planted", "class_argmax", "pop_n_positive", "planted_rank"):
        assert t[k] == ref[k], k
    assert t["pop_best_sr"] == pytest.approx(ref["pop_best_sr"], abs=1e-12)
    assert t["class_max"] == pytest.approx(ref["class_max"], abs=1e-12)


def test_the_truths_are_written_into_the_run_file_once(patched, tmp_path):
    base, _ = patched
    d, _ = _run_file(640005, 1.0, base)
    f = tmp_path / "cell_planted_0_replay_gate_640005.json"
    f.write_text(json.dumps(d))
    r = pr.price_one((str(f), False, B))
    pr._write(f, pr.load_run(f), r)
    w = pr.load_run(f)
    kinds = [e["kind"] for e in w["events"]]
    assert kinds[-1] == "end"
    for k in ("verdict", "class_p", "planted_truth", "priced_from_log"):
        assert kinds.count(k) == 1, k
    assert w["planted_truth"]["seed"] == 640005
    before = f.read_bytes()
    r2 = pr.price_one((str(f), False, B))          # a second pass is a no-op
    pr._write(f, pr.load_run(f), r2)
    assert f.read_bytes() == before


def test_a_planted_directory_prints_counts_and_no_rate(patched, tmp_path, capsys):
    base, _ = patched
    d, _ = _run_file(640006, 0.5, base)
    (tmp_path / "cell_planted_0_replay_gate_640006.json").write_text(json.dumps(d))
    assert pr.main(["--dir", str(tmp_path), "--workers", "1", "--B", str(B)]) == 0
    text = (tmp_path / "pricing_readout.txt").read_text()
    assert "no rate is printed" in text
    for word in ("alpha =", "Wilson", "CERTIFIED", "FAIL", "p: min"):
        assert word not in text, word
    assert not (tmp_path / "class_p.json").exists()


def test_the_panel_is_rebuilt_through_load_base(monkeypatch):
    """`load_base` is what loads the pinned X and refuses a mismatch; pricing has no
    other route to a panel."""
    def refuse():
        raise SystemExit("pinned feature matrix missing")
    monkeypatch.setattr(pp, "load_base", refuse)
    with pytest.raises(SystemExit, match="pinned"):
        pr.planted_basis(640000, 1.0)


def test_a_planted_run_without_its_level_is_refused():
    with pytest.raises(ValueError, match="level"):
        pr.planted_level({"run_id": "x", "events": [{"kind": "start",
                                                     "panel": "planted"}]})
