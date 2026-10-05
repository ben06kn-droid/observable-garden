"""The content-move cap enforced inside the replay null (7.5's unsaturable arm).

`prereg/planted-edge.md`, "Recorded for stage 2": on a capped run, every replicate
stops content moves at the same cap. **The reproduction test:** on a replicate equal
to the realized data, the capped replay reproduces the capped search.
"""
import numpy as np
import pytest

from estimator.bootstrap import stationary_bootstrap_indices
from garden.spec_class import SubsetClass
from quixote.agent_adapter import ToolSession
from quixote.replay import LoggedPolicy, integrity_check
from quixote.session import Session
from tests.test_agent_adapter import _fixture, _sandbox

CLS = SubsetClass(max_size=3, signed=True)


def _capped_session(cap=3, declare=True, moves=("init", "extend_best", "extend_best")):
    data, cfg, _ = _fixture(K=8)
    sb = _sandbox(data, cfg)
    tools = ToolSession(Session.on_sandbox(sb, CLS), max_turns=60, content_cap=cap)
    if declare:
        tools.call("declare_triggers", triggers=[
            {"trigger": "failures_at_least", "param": 99, "action": "stop"}])
    for m in moves:
        tools.call(m)
    tools.call("submit")
    s = tools.session
    return s, s.grammar.base, s.grammar.annualization, s.grammar._score_fn


def _continues(trace):
    return sum(1 for m in trace.moves if m in ("continue", "accept"))


def test_on_the_realized_data_the_capped_replay_reproduces_the_capped_search():
    s, base, ann, fn = _capped_session()
    support, score = s.submission()
    tr = LoggedPolicy(s.log, CLS).trace(base, ann, score_fn=fn)   # a replicate = the data
    assert tr.capped and _continues(tr) == 3
    assert tuple(tr.support) == tuple(support)
    assert tr.score == pytest.approx(score, abs=1e-12)
    assert integrity_check(s.log, CLS, base, ann, score_fn=fn).agrees


def test_the_cap_binds_without_it_the_same_log_searches_on():
    s, base, ann, fn = _capped_session()
    s.log.content_cap = None
    tr = LoggedPolicy(s.log, CLS).trace(base, ann, score_fn=fn)
    assert not tr.capped and _continues(tr) > 3


def test_no_replicate_makes_more_content_moves_than_the_cap():
    s, base, ann, _ = _capped_session()
    pol = LoggedPolicy(s.log, CLS)
    rng = np.random.default_rng(5)
    capped = 0
    for _ in range(25):
        rows = stationary_bootstrap_indices(base.shape[0], 5, rng)
        tr = pol.trace(base[rows] - base.mean(axis=0), ann)
        assert _continues(tr) <= 3
        capped += tr.capped
    assert capped > 0                     # the cap is what ended some replicates


def test_the_meta_path_counts_the_anchor_and_enforces_the_cap():
    s, base, ann, fn = _capped_session(declare=False)
    pol = LoggedPolicy(s.log, CLS)
    assert pol._runner()[2] == "run_meta"
    support, score = s.submission()
    tr = pol.trace(base, ann, score_fn=fn)
    assert tr.capped and _continues(tr) == 2          # the anchor is outside `moves`
    assert tuple(tr.support) == tuple(support)
    s.log.content_cap = None
    assert not pol.__class__(s.log, CLS).trace(base, ann, score_fn=fn).capped


def test_an_uncapped_log_is_replayed_exactly_as_before():
    s, base, ann, fn = _capped_session(cap=None)
    assert s.log.content_cap is None
    tr = LoggedPolicy(s.log, CLS).trace(base, ann, score_fn=fn)
    assert not tr.capped


def test_price_runs_restores_the_cap_from_the_run_file():
    from experiments.price_runs import rebuild_session_log
    s, *_ = _capped_session()
    records = [{"step": r.step, "kind": r.move.kind, "support": list(r.support_after),
                "score": r.score_after, "n_candidates": r.n_candidates,
                "trigger": r.trigger, "trigger_value": r.trigger_value,
                "replayable": r.replayable, "contradicted": r.contradicted,
                "move": {"kind": r.move.kind, "statistic": r.move.statistic,
                         "feature": r.move.feature, "note": r.move.note,
                         "among": [], "else_statistic": None, "choice": None}}
               for r in s.log.records]
    d = {"run_id": "x", "triggers_predeclared": list(s.log.declared_trigger_records),
         "events": [{"kind": "declared_budget", "budget": 60},
                    {"kind": "content_cap", "cap": 3},
                    {"kind": "session_log", "records": records}]}
    assert rebuild_session_log(d).content_cap == 3
    d["events"] = [e for e in d["events"] if e["kind"] != "content_cap"]
    assert rebuild_session_log(d).content_cap is None
