"""The 7.1 driver: its nulls are replay_nulls' nulls, and its smoke prints no rules."""
import numpy as np

from estimator.bootstrap import select_block_length
from estimator.trigger_replay import replay_nulls
from experiments import fixed_sequence_replay as fsr
from searchers.meta_adaptive import registered_71


def test_driver_nulls_equal_replay_nulls():
    """Two implementations of one resampling drift unless held equal. Same seed,
    same block length: nulls 1-3 must be array-equal, for every searcher."""
    seed = fsr.SEED0_SMOKE
    base, ann, se = fsr.panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    for s, s_ref in zip(registered_71(seed, se), registered_71(seed, se)):
        s.scoring = s_ref.scoring = "moments"
        realized, n1, n2, n3, engaged = fsr.nulls_for(s, base, S0, L, ann, 6, seed)
        ref = replay_nulls(base, s_ref, B=6, block_length=L, annualization=ann, seed=seed)
        np.testing.assert_array_equal(n1, ref.fixed_sequence, err_msg=s.name)
        np.testing.assert_array_equal(n2, ref.trigger, err_msg=s.name)
        np.testing.assert_array_equal(n3, ref.policy, err_msg=s.name)
        assert realized.score == ref.realized_score
        assert engaged.dtype == bool and engaged.size == 6


def test_smoke_block_is_disjoint_and_cost_report_prints_no_rule_quantity():
    blocks = {"registered": range(fsr.SEED0, fsr.SEED0 + 2000),
              "replication": range(fsr.SEED0_REPLICATION, fsr.SEED0_REPLICATION + 2000),
              "smoke": range(fsr.SEED0_SMOKE, fsr.SEED0_SMOKE + 1000)}
    names = list(blocks)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not set(blocks[a]) & set(blocks[b]), (a, b)
    data = fsr.run(1, fsr.SEED0_SMOKE, 3, None, None)
    text = fsr.cost_report(data)
    for forbidden in ("p_", "reject", "ks", "KS", "differ", "engaged", "rate"):
        assert forbidden not in text, forbidden
    assert "COST ONLY" in text


# -- a log with a restart replays the moves it logged, not the fill ------------

def test_a_logged_restart_does_not_shift_the_replayed_moves():
    """`_run_logged` holds CONTENT moves in one list and counts meta decisions in
    the same step loop. Indexing the moves by the step counter shifted the replay
    by one move per restart: the moves after a restart were the wrong ones, and
    once the index ran past the end the replay silently took the FILL — the best
    admissible move — in place of the move that was logged.

    The symptom was a support disagreement on a search that had not diverged at
    all, so both identity checks refused honest runs whose restart rule fired.
    Checked here on a log built to contain a restart with content moves after it.
    """
    import numpy as np

    from environments.sandbox import Sandbox
    from quixote.grammar import Move
    from quixote.triggers import Trigger
    from quixote.replay import LoggedPolicy, integrity_check
    from quixote.session import Session, TriggerFired
    from experiments import unfaithful_searchers as us

    data, cfg = us.make_panel("s0", 990_000)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
    sess = Session.on_sandbox(sb, us.CLS, name_prefix="r")
    trig = Trigger("failures_at_least", 3.0, "restart")
    sess.declare_budget(24)
    sess.declare_triggers([trig])

    def step(move):
        try:
            _s, _sc, n = sess.propose(move)
        except (TriggerFired, ValueError):
            return False
        if n == 0:
            sess.cancel()
            return False
        sess.accept()
        return True

    step(Move("init"))
    step(Move("extend_best"))
    for _ in range(12):
        if sess.fired_triggers():
            break
        if not step(Move("swap_worst")):
            break
    assert sess.fired_triggers(), "the rule has to fire for this to test anything"
    _f, value, stamp = sess.evaluate_trigger(trig)
    sess.restart(trig, value, stamp)
    # Content moves AFTER the restart: these are the ones the shift corrupted.
    # The sequence has to END on a move the fill would not itself choose, or the
    # test cannot see the bug — a shifted `extend_best` is still an extension,
    # and the fill is the best admissible move, so a run of extensions replays
    # identically whether the index is right or wrong. A `flip` last is the
    # discriminator: it lowers the score, so neither the fill nor a shifted
    # extension reproduces it. Confirmed to fail with the index restored to the
    # step counter, on seeds 990000-990002.
    assert step(Move("extend_best"))
    assert step(Move("extend_best"))
    assert step(Move("flip", feature=sess.support[0][0]))

    kinds = [r.move.kind for r in sess.log.records]
    assert "restart" in kinds and kinds[-1] == "flip"

    base = sb.base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))
    chk = integrity_check(sess.log, us.CLS, base, ann)
    assert chk.agrees, (
        f"replayed {chk.replayed_support} against realized {chk.realized_support}")
    # and the replay did NOT reach for the fill: every step had a logged move
    lp = LoggedPolicy(sess.log, us.CLS)
    trace = lp.trace(base, ann, frozen=lp.frozen_actions())
    assert not trace.filled
    assert trace.support == chk.realized_support
