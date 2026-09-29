"""7.2 part two (a): certifying against the null 7.1 selected.

Trigger replay certifies; fixed-sequence replay is the bracket's lower end;
policy replay is reported. Every verdict whose replicates used the fill carries
the fill's measured direction.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length
from estimator.trigger_replay import replay_nulls
from garden.spec_class import SubsetClass
from quixote.certify import CERTIFYING_NULL, certify, three_nulls
from quixote.drivers import restart_after_k_failures, stop_when_cleared
from quixote.session import Session
from quixote.verdict import EXIT_CODES
from searchers.meta_adaptive import StopWhenCleared


def _run(seed, bar=0.5, s=1, K=10, T=600):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    data = generate(cfg)
    cls = SubsetClass(max_size=K, signed=False)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
    sess = Session.on_sandbox(sb, cls)
    stop_when_cleared(sess, bar=bar)
    return sess, cls, sb.base_feature_columns(), float(np.sqrt(cfg.periods_per_year)), data, cfg


def test_the_three_nulls_match_replay_nulls_replicate_for_replicate():
    """Two implementations of one resampling drift unless held equal. certify's
    loop must give replay_nulls' arrays exactly, for the same seed and block."""
    sess, cls, base, ann, _, _ = _run(3, s=0)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    from quixote.replay import LoggedPolicy
    mine, engaged = three_nulls(sess.log, cls, base, ann, B=64, block_length=L, seed=11)
    ref = replay_nulls(base, LoggedPolicy(sess.log, cls), B=64, block_length=L,
                       annualization=ann, seed=11)
    for which in ("fixed_sequence", "trigger", "policy"):
        np.testing.assert_array_equal(getattr(mine, which), getattr(ref, which), err_msg=which)
    assert mine.realized_score == ref.realized_score
    assert engaged.dtype == bool and engaged.size == 64


def test_the_certifying_null_is_trigger_replay_and_is_bit_identical_to_the_scripted_searcher():
    """The milestone standard: the logged session's certifying null is the
    scripted searcher's own trigger null, array-equal."""
    sess, cls, base, ann, _, _ = _run(4, s=0)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    mine, _ = three_nulls(sess.log, cls, base, ann, B=96, block_length=L, seed=5)
    scripted = replay_nulls(base, StopWhenCleared(bar=0.5), B=96, block_length=L,
                            annualization=ann, seed=5)
    np.testing.assert_array_equal(mine.trigger, scripted.trigger)
    np.testing.assert_array_equal(mine.fixed_sequence, scripted.fixed_sequence)
    np.testing.assert_array_equal(mine.policy, scripted.policy)


def test_a_verdict_names_its_null_reports_the_other_two_and_prices_a_signal():
    sess, cls, base, ann, _, _ = _run(0, bar=0.5, s=2)
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=200, seed=7)
    assert v.certifying_null == CERTIFYING_NULL
    assert v.status in ("CERTIFIED", "FAIL")
    assert 0.0 < v.p_certifying <= 1.0 and 0.0 < v.p_policy <= 1.0
    assert v.p_frozen is not None                    # the bracket's lower end is filled in
    assert v.p_upper is None                         # 7.3 has not licensed the upper end
    assert v.bracket is None and "waits on 7.3" in " ".join(v.standard_reasons())
    assert v.exit_code == EXIT_CODES[v.status]
    assert any("7.1 measured this null at or below nominal" in r for r in v.reasons)


def test_noise_is_not_certified_and_a_real_signal_can_be():
    """Direction, on one fixture each rather than as a sweep: pure noise should
    not clear the bar, and a strong signal should."""
    noise, cls, base, ann, _, _ = _run(1, s=0)
    v_noise = certify(noise.log, cls, base, ann, alpha=0.05, B=300, seed=2)
    assert v_noise.status == "FAIL", v_noise.p_certifying
    strong, cls2, base2, ann2, _, _ = _run(1, s=6)
    v_strong = certify(strong.log, cls2, base2, ann2, alpha=0.05, B=300, seed=2)
    assert v_strong.status == "CERTIFIED", v_strong.p_certifying


def test_every_verdict_that_used_the_fill_carries_its_measured_direction():
    sess, cls, base, ann, _, _ = _run(7, bar=0.3, s=0)
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=300, seed=4)
    # The FILL note specifically. Other reasons mention the fill in passing -- the
    # no-stop-rule notice says the procedure replays to its budget under it -- so
    # the note is selected by what only it carries, not by the word "fill".
    note = [r for r in v.reasons
            if "replicates" in r and ("never used" in r or "of the replay" in r
                                      or "LIBERAL" in r or "engaged" in r)]
    assert note, "a verdict must say what the fill did"
    if v.fill_engaged:
        text = note[0]
        assert "LIBERAL" in text and "1,506 of 1,507" in text
        assert "McNemar p = 1.0000" in text and "untested" in text
        assert f"{v.fill_engaged:,} of {v.fill_replicates:,}" in text
        assert 0 < v.fill_share <= 1
    else:
        assert "never used" in note[0]


def test_a_run_with_no_fill_says_so():
    """A searcher that runs to the budget never engages the fill, and its verdict
    says that rather than carrying the liberal-direction note."""
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=10, s=0, rho=0.0, sigma=1.0, seed=2)
    cls = SubsetClass(max_size=10, signed=False)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    sess = Session.on_sandbox(sb, cls)
    restart_after_k_failures(sess, k=2)              # no stop trigger: always at budget
    v = certify(sess.log, cls, sb.base_feature_columns(),
                float(np.sqrt(cfg.periods_per_year)), alpha=0.05, B=200, seed=1)
    assert v.fill_engaged == 0
    assert any("never used" in r for r in v.reasons)


def test_a_run_whose_replay_disagrees_with_itself_is_not_priced():
    from dataclasses import replace as dc_replace
    sess, cls, base, ann, _, _ = _run(5, s=0)
    i = max(j for j, r in enumerate(sess.log.records)
            if not r.move.is_meta and r.move.note != "rejected")
    r = sess.log.records[i]
    sess.log.records[i] = dc_replace(r, support_after=tuple((k, -g) for k, g in r.support_after))
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=50, seed=0)
    assert v.status == "UNDECIDABLE"
    assert v.p_certifying is None and "not priced" in " ".join(v.reasons).lower()


# -- pre-agent-cell item 1: CERTIFIED attaches to the submitted specification --

def test_certified_attaches_to_the_submission_with_the_procedure_line_beside_it():
    """Registered 2026-09-28 in `quixote/README.md`, implemented after 7.3 scripted.

    The verdict used to price what the REPLAY reaches — the declared procedure on
    the realized data — while a reader quotes what the searcher SUBMITTED. Those
    coincide whenever the search ended under its own declared rule and not
    otherwise, so `p_certifying` is now the submitted specification's p-value and
    the procedure's own is reported beside it as `p_procedure`.
    """
    sess, cls, base, ann, _, _ = _run(7, bar=0.3, s=0)
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=200, seed=4)
    assert v.p_certifying is not None and v.p_procedure is not None
    assert v.submitted_score is not None
    # the status follows the SUBMITTED p, not the procedure's
    assert v.status == ("CERTIFIED" if v.p_certifying < v.alpha else "FAIL")
    # both are priced against the same null, so both are valid p-values
    for p in (v.p_certifying, v.p_procedure):
        assert 0.0 < p <= 1.0
    assert any("SUBMITTED specification" in r for r in v.reasons)


def test_a_declaration_with_no_stop_rule_is_named_in_the_verdict():
    """The same item's third part. A procedure with no stop rule has no end of its
    own: its replay runs to the declared budget under the fill, so it prices a
    LONGER search than the submission. A reader must be told that rather than left
    to infer it from two p-values that disagree."""
    sess, cls, base, ann, _, _ = _run(7, bar=0.3, s=0)
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=200, seed=4)
    assert v.declares_stop_rule is False, "this fixture declares no stop rule"
    assert any("NO STOP RULE" in r for r in v.reasons)
    # and the notice is absent when a stop rule IS declared
    from quixote.grammar import Move
    from quixote.session import Session, TriggerFired
    from quixote.triggers import Trigger
    from environments.sandbox import Sandbox
    sess2, cls2, base2, ann2, data2, cfg2 = _run(7, bar=0.3, s=0)
    sb2 = Sandbox(data2, periods_per_year=cfg2.periods_per_year)
    s2 = Session.on_sandbox(sb2, cls2, name_prefix="stoprule")
    s2.declare_triggers([Trigger("failures_at_least", 2.0, "stop")])
    for mv in (Move("init"), Move("extend_best"), Move("extend_best")):
        try:
            _s, _sc, n = s2.propose(mv)
        except (TriggerFired, ValueError):
            break
        s2.accept() if n else s2.cancel()
    v2 = certify(s2.log, cls2, base2, ann2, alpha=0.05, B=100, seed=5)
    assert v2.declares_stop_rule is True
    assert not any("NO STOP RULE" in r for r in v2.reasons)


def test_the_verdict_block_carries_the_hand_over_share():
    """Registered 2026-09-29: a per-run line. The fill share says how often the
    null left the log; the hand-over share says how often it had no choice, which
    is a property of the searcher's own moves and changes how the null reads."""
    sess, cls, base, ann, _, _ = _run(7, bar=0.3, s=0)
    v = certify(sess.log, cls, base, ann, alpha=0.05, B=200, seed=4)
    assert v.handover_replicates is not None
    assert 0 <= v.handover_replicates <= v.fill_replicates
    assert v.handover_share == v.handover_replicates / v.fill_replicates
