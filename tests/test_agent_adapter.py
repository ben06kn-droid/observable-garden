"""The adapter's milestone: tool calls and a direct Session run are the same run.

7.2 item (a): "a scripted policy expressed as tool calls reproduces its direct
Session run bit-identically." Bit-identically means the move records agree field
by field — support, score, candidate count, trigger, trigger value, replayable —
and the sandbox transcript agrees stream by stream. Timestamps are excluded and
only timestamps: they are wall-clock readings taken at different moments by
construction, and the log records them precisely so that a late declaration can
be refused.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from quixote.agent_adapter import (CONTENT_TOOLS, META_TOOLS, TOOLS, QuixoteAgent,
                                   ToolRefused, ToolSession)
from quixote.grammar import Move
from quixote.session import Session
from quixote.triggers import Trigger

BAR = 0.8


def _fixture(seed=0, K=8, T=600, s=1):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    data = generate(cfg)
    return data, cfg, SubsetClass(max_size=3, signed=False)


def _sandbox(data, cfg):
    return Sandbox(data, periods_per_year=cfg.periods_per_year)


# -- the two ways of running the same policy ---------------------------------

def policy_via_tools(tools: ToolSession) -> None:
    """Anchor, then extend while it improves, stopping at a bar or when the
    support is full. Every meta move names its declared trigger."""
    tools.call("declare_budget", budget=4)
    tools.call("init")
    for _ in range(4):
        st = tools.session
        if st.best_score > BAR:
            tools.call("stop", trigger="best_so_far_above", param=BAR)
            return
        if len(st.support) >= 3:
            break
        before = st.best_score
        res = tools.call("extend_best")
        if not res.ok:
            break
        if st.best_score <= before:          # it did not improve: put it back
            break
    if tools.session.best_score > BAR:
        tools.call("stop", trigger="best_so_far_above", param=BAR)
    tools.call("submit")


def policy_direct(session: Session) -> None:
    """The same policy, driving the Session itself."""
    session.declare_budget(4)
    support, score, n = session.propose(Move("init"))
    session.accept()
    for _ in range(4):
        if session.best_score > BAR:
            t = Trigger(kind="best_so_far_above", param=BAR, action="stop")
            fires, value, stamp = session.evaluate_trigger(t)
            assert fires
            session.stop(t, value, stamped_at=stamp)
            return
        if len(session.support) >= 3:
            break
        before = session.best_score
        support, score, n = session.propose(Move("extend_best"))
        if n == 0:
            session.cancel()
            break
        session.accept()
        if session.best_score <= before:
            break
    if session.best_score > BAR:
        t = Trigger(kind="best_so_far_above", param=BAR, action="stop")
        fires, value, stamp = session.evaluate_trigger(t)
        assert fires
        session.stop(t, value, stamped_at=stamp)


FIELDS = ("step", "support_after", "score_after", "n_candidates", "trigger",
          "trigger_value", "replayable", "trigger_params")


def _records(log):
    out = []
    for r in log.records:
        row = {f: getattr(r, f) for f in FIELDS}
        row["move"] = (r.move.kind, r.move.statistic, r.move.feature, r.move.among,
                       r.move.choice, r.move.note)
        row["info"] = (r.information.step, r.information.support_before,
                       r.information.score_before, r.information.n_candidates_seen)
        out.append(row)
    return out


def test_the_milestone_a_scripted_policy_as_tool_calls_is_the_direct_run():
    """The milestone, on a seed where the bar fires."""
    data, cfg, cls = _fixture()

    sb_tools = _sandbox(data, cfg)
    agent = QuixoteAgent(cls, policy_via_tools)
    agent.run(sb_tools)

    sb_direct = _sandbox(data, cfg)
    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
    policy_direct(session)

    assert _records(agent.log) == _records(session.log)
    assert agent.log.budget == session.log.budget
    assert agent.tools.session.submission() == session.submission()

    # and the evaluations themselves: same specifications, same streams, in order
    assert len(sb_tools.transcript) == len(sb_direct.transcript)
    for a, b in zip(sb_tools.transcript, sb_direct.transcript):
        np.testing.assert_array_equal(a.spec.weights, b.spec.weights)
        np.testing.assert_array_equal(a.return_stream, b.return_stream)
        assert a.sharpe == b.sharpe
    np.testing.assert_array_equal(sb_tools.submission[0].weights,
                                  session.submitted_weights())


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_the_milestone_holds_across_seeds_including_ones_that_never_stop(seed):
    """Different seeds take different branches — the bar fires on some and not
    others, and the extension stops improving at different depths."""
    data, cfg, cls = _fixture(seed=seed)
    agent = QuixoteAgent(cls, policy_via_tools)
    sb_tools = _sandbox(data, cfg)
    agent.run(sb_tools)
    sb_direct = _sandbox(data, cfg)
    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
    policy_direct(session)
    assert _records(agent.log) == _records(session.log)
    assert [e.sharpe for e in sb_tools.transcript] == [e.sharpe for e in sb_direct.transcript]


# -- the surface -------------------------------------------------------------

def test_the_tool_list_is_the_grammar_plus_the_declaration_slots():
    from quixote.grammar import CONTENT_KINDS
    assert CONTENT_TOOLS == CONTENT_KINDS
    assert META_TOOLS == ("stop", "restart")
    assert set(TOOLS) == set(CONTENT_TOOLS) | set(META_TOOLS) | {
        "pick_prior", "short_list", "declare_budget", "predict", "submit"}


def test_an_unknown_tool_is_refused_with_the_list():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    with pytest.raises(ToolRefused, match="unknown tool"):
        tools.call("evaluate")             # llm_agent.py's tool, deliberately absent
    with pytest.raises(ToolRefused, match="unknown tool"):
        tools.call("submit_weights", weights=[1, 0, 0])


def test_every_tool_has_a_schema_taken_from_its_own_implementation():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    schemas = tools.tool_schemas()
    assert [s["name"] for s in schemas] == list(TOOLS)
    assert all(s["description"] for s in schemas)
    assert {s["name"] for s in schemas if s["meta"]} == set(META_TOOLS)


# -- refusals are part of the contract ---------------------------------------

def test_a_meta_move_whose_trigger_does_not_fire_is_refused():
    """'A meta move is taken because a declared trigger fired.' A stop the agent
    merely prefers is refused, and nothing is recorded."""
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    before = len(tools.session.log.records)
    with pytest.raises(ToolRefused, match="does not fire"):
        tools.call("stop", trigger="best_so_far_above", param=99.0)
    assert len(tools.session.log.records) == before


def test_a_meta_move_with_an_unknown_trigger_is_refused_with_the_library():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    with pytest.raises(ToolRefused, match="unknown trigger"):
        tools.call("stop", trigger="i_feel_done", param=0.0)


def test_the_trigger_is_stamped_before_the_move_it_justifies():
    """`Session.evaluate_trigger` takes the stamp; the adapter must pass that
    stamp through rather than taking a fresh one after the move."""
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    tools.call("stop", trigger="best_so_far_above", param=-99.0)
    rec = tools.session.log.records[-1]
    assert rec.trigger_stamped_at is not None
    assert rec.trigger_stamped_at <= rec.timestamp
    assert rec.trigger_params == {"kind": "best_so_far_above", "param": -99.0, "action": "stop"}


def test_a_declaration_after_the_first_evaluation_is_refused():
    """The slots are pre-evaluation by construction (`SessionLog.refuse_if_late`),
    and the adapter does not soften that."""
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    with pytest.raises(ValueError):
        tools.call("pick_prior", support=[[0, 1.0]])
    with pytest.raises(ValueError):
        tools.call("declare_budget", budget=3)


def test_a_move_outside_the_declared_class_is_refused_by_the_harness():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    tools.call("extend_best")
    tools.call("extend_best")               # support is now full at max_size 3
    res = tools.call("extend_best")
    assert not res.ok and res.state["n_candidates"] == 0
    assert all(len(r.support_after) <= 3 for r in tools.session.log.records)


def test_nothing_is_taken_after_submit():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    tools.call("submit")
    with pytest.raises(ToolRefused, match="has submitted"):
        tools.call("extend_best")


# -- what the log keeps ------------------------------------------------------

def test_a_discarded_proposal_is_recorded_as_computed_and_not_taken():
    """Breadth is what was evaluated, not what was kept."""
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    sb_calls = len(tools.session.sandbox.transcript)
    res = tools.call("extend_best", keep=False)
    assert res.ok and "discarded" in res.text
    rec = tools.session.log.records[-1]
    assert rec.move.note == "rejected"
    assert rec.n_candidates > 0
    assert len(tools.session.sandbox.transcript) > sb_calls     # it was evaluated
    assert rec.support_after == tools.session.support           # support did not move


def test_a_contradicted_pick_is_reported_to_the_agent_as_rejected_as_declared():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    from quixote.grammar import Grammar
    g = tools.session.grammar
    chosen, _ = g.pick_choice((), Move("pick", statistic="sharpe", among=(0, 1, 2)))
    wrong = next(j for j in (0, 1, 2) if j != chosen[0][0])
    res = tools.call("pick", among=[0, 1, 2], choice=wrong)
    assert res.ok                                   # the run continues
    assert "rejected as declared" in res.state["consistency"]
    assert not tools.session.log.records[-1].replayable


def test_the_submission_is_the_best_pair_after_a_restart():
    """A restart keeps the best pair; the submission must not mix the current
    support with another's score."""
    data, cfg, cls = _fixture(seed=7)
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    best_before = tools.session.best_score
    res = tools.call("restart", trigger="failures_at_least", param=0.0)
    assert res.ok
    support, score = tools.session.submission()
    assert score == best_before
    assert tools.session.grammar.contains(support)


def test_the_agent_submits_exactly_once_through_the_sandbox():
    """Same Searcher ABC as `searchers/llm_agent.py`: run(sandbox) submits once."""
    data, cfg, cls = _fixture()
    sb = _sandbox(data, cfg)
    QuixoteAgent(cls, lambda t: t.call("init")).run(sb)          # no explicit submit
    assert sb.submission is not None
    spec, dist = sb.submission
    assert cls.contains(spec.weights)
    assert dist.mean == pytest.approx(max(e.sharpe for e in sb.transcript))


def test_a_stop_ends_the_search():
    """A stop that fires latches the session: a second stop would put two stops
    in one log, and trigger replay is told how many moves the realized search
    took. Found by the pilot's dry run, before any model-backed run."""
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls))
    tools.call("init")
    tools.call("stop", trigger="best_so_far_above", param=-99.0)
    assert tools.stopped
    for name, kw in (("extend_best", {}), ("init", {}),
                     ("stop", {"trigger": "best_so_far_above", "param": -99.0}),
                     ("restart", {"trigger": "failures_at_least", "param": 0.0})):
        with pytest.raises(ToolRefused, match="has stopped"):
            tools.call(name, **kw)
    stops = [r for r in tools.session.log.records if r.move.kind == "stop"]
    assert len(stops) == 1
    tools.call("predict", mean=0.1, sd=0.2)      # still allowed
    assert tools.call("submit").ok


def test_the_milestone_still_holds_with_the_stop_latch():
    """The latch must not change a policy that stops once, which is every
    scripted policy here."""
    data, cfg, cls = _fixture(seed=2)
    agent = QuixoteAgent(cls, policy_via_tools)
    sb_tools = _sandbox(data, cfg)
    agent.run(sb_tools)
    sb_direct = _sandbox(data, cfg)
    session = Session.on_sandbox(sb_direct, cls, name_prefix="quixote-agent")
    policy_direct(session)
    assert _records(agent.log) == _records(session.log)


def test_the_identity_guard_names_the_cause_it_measured():
    """The guard's message used to assert float accumulation (~1e-12) whichever
    way it failed. On a net-of-cost panel the two paths differ structurally,
    because the base-column basis is not one the class is linear in, and a
    message that blamed float noise would send a reader to the wrong bug."""
    from quixote.replay import IdentityCheck
    small = IdentityCheck(agrees=False, realized_support=((0, 1.0),),
                          replayed_support=((1, 1.0),), realized_score=1.0,
                          replayed_score=1.0 + 1e-13, n_moves_realized=2,
                          n_moves_replayed=2)
    assert "float accumulation" in small.reason() and "STRUCTURAL" not in small.reason()
    big = IdentityCheck(agrees=False, realized_support=((0, 1.0),),
                        replayed_support=((1, 1.0),), realized_score=1.0,
                        replayed_score=9.0, n_moves_realized=2, n_moves_replayed=2)
    assert "STRUCTURAL" in big.reason()
    assert "not one the class is linear in" in big.reason()
    assert "8.000e+00" in big.reason()
