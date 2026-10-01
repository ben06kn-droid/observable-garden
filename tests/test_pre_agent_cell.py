"""The pre-agent-cell list: declaration-order tie-break, close-time self-check,
and the refusal of a restart under a firing stop rule.

All three were registered on 2026-09-28/29 in `quixote/README.md` and `ROADMAP.md`
to land after 7.3 scripted and before 6.5's agent cell. Item 1 (CERTIFIED attaches
to the submitted specification) is tested in `tests/test_quixote_certify.py`; item
4 (move completeness) in `tests/test_move_completeness.py`.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from quixote.grammar import Move
from quixote.session import Session, TriggerFired
from quixote.triggers import Trigger


def _session(seed=5, K=10, s=0):
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    cls = SubsetClass(max_size=K, signed=True)
    return Session.on_sandbox(sb, cls), sb, cls, float(np.sqrt(cfg.periods_per_year))


def _take(sess, move):
    try:
        _s, _sc, n = sess.propose(move)
    except (TriggerFired, ValueError):
        return False
    if n == 0:
        sess.cancel()
        return False
    sess.accept()
    return True


def _drive_until_fired(sess, limit=12):
    for _ in range(limit):
        if sess.fired_triggers():
            return True
        if not _take(sess, Move("swap_worst")):
            break
    return bool(sess.fired_triggers())


# -- item 2: co-firing rules resolve by declaration order ---------------------

def test_co_firing_rules_resolve_by_declaration_order():
    """Two rules sharing a predicate fire together. Before this the choice between
    them lived in the POLICY, so the committed rule set did not determine the
    action and the commitment replay rightly refused the run -- which is why 7.3's
    faithful arm needed two searchers rather than one
    (`prereg/unfaithful-searchers.md` amendment 3)."""
    sess, _sb, _cls, _ann = _session()
    stop_first = Trigger("failures_at_least", 2.0, "stop")
    restart_second = Trigger("failures_at_least", 2.0, "restart")
    sess.declare_budget(20)
    sess.declare_triggers([stop_first, restart_second])
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    assert _drive_until_fired(sess), "the shared predicate must fire"

    fired = sess.fired_triggers()
    assert len(fired) == 2, "both rules share a predicate, so both fire"
    resolved = sess.resolved_trigger()
    assert resolved.action == "stop", "the FIRST declared rule wins the tie"
    assert resolved.as_record() == fired[0][0].as_record()


def test_the_session_and_the_replay_resolve_a_tie_the_same_way():
    """The tie-break is only worth anything if the replay agrees with it: the
    whole point is to make the action a function of the DECLARATION, which a
    replay can reproduce."""
    from quixote.replay import LoggedPolicy

    sess, sb, cls, ann = _session()
    sess.declare_budget(20)
    sess.declare_triggers([Trigger("failures_at_least", 2.0, "stop"),
                           Trigger("failures_at_least", 2.0, "restart")])
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    _drive_until_fired(sess)
    resolved = sess.resolved_trigger()

    lp = LoggedPolicy(sess.log, cls)
    assert lp.triggers, "the replay must hold the declared rules"
    assert lp.triggers[0].action == resolved.action
    assert lp.triggers[0].as_record() == resolved.as_record()


# -- item 5: a restart under a firing stop rule is refused --------------------

def test_a_restart_while_a_stop_rule_fires_is_refused():
    """A firing stop rule means stop; continuing past it is a change of rule and
    must be declared as one. Before this, a searcher could restart straight
    through a firing stop and the only trace was the committed-rule replay
    disagreeing later -- how the ETF pilot's run 2 read UNDECIDABLE."""
    sess, _sb, _cls, _ann = _session()
    stop_rule = Trigger("failures_at_least", 2.0, "stop")
    restart_rule = Trigger("failures_at_least", 9.0, "restart")
    sess.declare_budget(20)
    sess.declare_triggers([stop_rule, restart_rule])
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    assert _drive_until_fired(sess)
    assert sess.resolved_trigger().action == "stop"

    _f, value, stamp = sess.evaluate_trigger(restart_rule)
    with pytest.raises(ValueError, match="restart refused"):
        sess.restart(restart_rule, value, stamp)


def test_the_legitimate_path_stays_open_change_the_rule_then_restart():
    """The refusal must not be a dead end: changing the rule on the record lifts
    the firing stop, and the restart then proceeds. A rule that is changed is
    logged and priced -- which is the point, rather than a silent divergence."""
    sess, _sb, _cls, _ann = _session()
    stop_rule = Trigger("failures_at_least", 2.0, "stop")
    restart_rule = Trigger("failures_at_least", 9.0, "restart")
    sess.declare_budget(20)
    sess.declare_triggers([stop_rule, restart_rule])
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    assert _drive_until_fired(sess)

    # change the STOP rule to one that cannot fire, on the record
    sess.change_trigger(Trigger("failures_at_least", 1e9, "stop"),
                        reason="continuing past the stop, declared as a change")
    assert sess.log.trigger_changes, "the change must be logged"
    assert not any(t.action == "stop" for t, _ in sess.fired_triggers())

    _f, value, stamp = sess.evaluate_trigger(restart_rule)
    # now permitted: no stop rule is firing
    sess.restart(restart_rule, value, stamp)
    assert any(r.move.kind == "restart" for r in sess.log.records)


def test_a_session_that_declared_nothing_is_left_alone():
    """The pre-amendment path: scripted searchers and older logs declare no
    triggers and must be unaffected by either rule."""
    sess, _sb, _cls, _ann = _session()
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    assert sess.resolved_trigger() is None
    assert sess.fired_triggers() == []


# -- item 3: the close-time self-check ---------------------------------------

def test_close_records_a_self_check_in_the_log():
    """Every replay defect found on 2026-09-28 was invisible until something
    replayed a log much later. A check at close catches them while the session
    that produced them still exists, and recording it in the log means a stored
    run carries its own verdict on whether it can be replayed."""
    sess, _sb, _cls, _ann = _session()
    sess.declare_triggers([Trigger("failures_at_least", 3.0, "stop")])
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    _take(sess, Move("refine"))
    assert sess.log.self_check is None, "nothing is recorded before close"

    out = sess.close()
    assert sess.log.self_check is out
    assert out["replayable"] is True, out["reason"]
    assert out["check"] == "integrity"
    assert out["error"] is None
    assert out["realized_score"] == pytest.approx(out["replayed_score"], abs=1e-9)


def test_close_is_idempotent_and_never_raises():
    """Closing twice recomputes rather than accumulating, and a failing
    self-check is RECORDED, not raised: refusing to close would destroy the very
    log a reader needs to diagnose it."""
    sess, _sb, _cls, _ann = _session()
    _take(sess, Move("init"))
    _take(sess, Move("extend_best"))
    first = sess.close()
    second = sess.close()
    assert first == second
    assert sess.log.self_check == second

    # a log the check cannot handle is recorded as unreplayable, not raised
    broken, _sb2, _cls2, _ann2 = _session(seed=6)
    _take(broken, Move("init"))
    broken.grammar = None                        # force the check to fail
    out = broken.close()
    assert out["replayable"] is False
    assert out["error"] is not None
    assert "self-check itself failed" in out["reason"]


# -- the two trigger evaluators must agree on every registered predicate -------

def test_session_and_replay_evaluate_every_registered_predicate_identically():
    """The defect this pins: `active_trigger_records` keyed by ACTION alone, so three
    declared stop rules collapsed to the last one. The live session then ran under one
    rule while `LoggedPolicy` replayed all three, the two evaluators disagreed on the
    same state, and the commitment check reported a divergence the agent had not made
    -- 15 runs of the 7.3 agent cell, 8 of 20 on the s3 orientation arm.

    A declared rule that is never evaluated is not a declaration, so this walks a
    SHARED trace and requires the two evaluators to fire identically at every step,
    for every predicate in the registered library.
    """
    from quixote.replay import LoggedPolicy
    from quixote.triggers import PREDICATES, Trigger

    sess, _sb, _cls, _ann = _session(seed=41)
    cls = SubsetClass(max_size=10, signed=True)

    # one rule per registered predicate, all sharing the `stop` action -- the case
    # that collapsed. Parameters chosen so each can fire somewhere on a real trace.
    declared = [Trigger("best_so_far_above", 0.2, "stop"),
                Trigger("failures_at_least", 2.0, "stop"),
                Trigger("last_gain_at_most", 0.01, "stop")]
    assert {t.kind for t in declared} == set(PREDICATES), (
        f"the registered library is {sorted(PREDICATES)}; this test must cover all of "
        "it, or a new predicate can be dropped by the live evaluator unnoticed")

    sess.declare_budget(24)
    sess.declare_triggers(declared)
    # the live evaluator must hold every declared rule, not one per action
    assert len(sess.active_trigger_records) == len(declared)

    lp = LoggedPolicy(sess.log, cls)
    assert len(lp.triggers) == len(declared)
    assert ({(t.kind, t.param, t.action) for t in lp.triggers}
            == {(t.kind, t.param, t.action) for t in declared})

    # and on a SHARED state, both sides fire the same set
    for state in ({"step": 0, "best": -float("inf"), "failures": 0,
                   "last_gain": float("inf"), "budget_left": 24},
                  {"step": 3, "best": 0.5, "failures": 0, "last_gain": 0.2,
                   "budget_left": 21},
                  {"step": 4, "best": 0.5, "failures": 1, "last_gain": 0.0,
                   "budget_left": 20},
                  {"step": 5, "best": 0.1, "failures": 2, "last_gain": 0.3,
                   "budget_left": 19}):
        live = {(Trigger.from_record(r).kind, Trigger.from_record(r).action)
                for r in sess.active_trigger_records
                if Trigger.from_record(r).evaluate(state)[0]}
        replayed = {(t.kind, t.action) for t in lp.triggers if t.evaluate(state)[0]}
        assert live == replayed, (state, live, replayed)


def test_a_change_trigger_replaces_only_the_rule_it_names():
    """Keying by (kind, action) keeps `change_trigger` a REPLACEMENT rather than an
    addition, while leaving the other declared rules standing -- which is what
    "replace the rule I named" means once more than one rule is declared."""
    from quixote.triggers import Trigger

    sess, _sb, _cls, _ann = _session(seed=42)
    sess.declare_budget(24)
    sess.declare_triggers([Trigger("best_so_far_above", 1.2, "stop"),
                           Trigger("last_gain_at_most", 0.02, "stop")])
    sess.change_trigger(Trigger("last_gain_at_most", -1e9, "stop"), reason="t")

    recs = {(r["kind"], r["param"]) for r in sess.active_trigger_records}
    assert ("best_so_far_above", 1.2) in recs          # untouched
    assert ("last_gain_at_most", -1e9) in recs         # replaced
    assert ("last_gain_at_most", 0.02) not in recs     # and not duplicated
    assert len(sess.active_trigger_records) == 2
