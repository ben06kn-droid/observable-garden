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


# -- an inapplicable logged move hands over to the fill, it does not end the run --

def test_an_identity_named_flip_truncates_no_replicate_and_records_handover():
    """`prereg/unfaithful-searchers.md` amendment 6: the certifying null's
    definition completed.

    A move that names a feature by IDENTITY — a `flip` on whatever the realized
    support held — is applicable to the realized data and usually not to a
    bootstrap resample. The replay used to end such a replicate, which made the
    null a distribution of TRUNCATED searches pricing an untruncated statistic:
    biased toward rejection, and measured at 98 of 100 replicates on one searcher.

    Now the fill takes over for the remainder of that replicate under the same
    declared triggers — the same semantics as past-the-log — so a replicate ends
    only by trigger or by budget. `handover_step` records where the log stopped
    being followed.
    """
    import numpy as np

    from environments.sandbox import Sandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    from experiments import unfaithful_searchers as us
    from quixote.grammar import Move
    from quixote.replay import LoggedPolicy
    from quixote.session import Session, TriggerFired
    from quixote.triggers import Trigger

    data, cfg = us.make_panel("s0", 990_000)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=us.CLS)
    sess = Session.on_sandbox(sb, us.CLS, name_prefix="idflip")
    sess.declare_budget(24)
    sess.declare_triggers([Trigger("failures_at_least", 3.0, "stop")])

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

    assert step(Move("init"))
    assert step(Move("extend_best"))
    assert step(Move("extend_best"))
    # THE identity-named move: a feature index read off the realized support
    held = sess.support[0][0]
    assert step(Move("flip", feature=held))

    base = sb.base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))
    lp = LoggedPolicy(sess.log, us.CLS)
    n_content = len([r for r in sess.log.records
                     if not r.move.is_meta and r.move.note != "rejected"])
    realized = lp.trace(base, ann)

    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(990_000)
    ended_inapplicable, handovers = 0, []
    for _ in range(100):
        R = S0[stationary_bootstrap_indices(base.shape[0], L, rng), :]
        t = lp.trace(R, ann, meta_steps=realized.n_moves)
        if t.handover_step is not None:
            handovers.append(t.handover_step)
            # handing over must not shorten the replicate below the logged length:
            # the fill carries it on until a trigger fires or the budget is spent
            assert t.n_moves >= n_content, (t.n_moves, n_content)
            assert t.filled
        # a replicate that stopped at exactly the handover step would be the old
        # truncation behaviour
        if t.handover_step is not None and t.n_moves <= t.handover_step:
            ended_inapplicable += 1

    assert ended_inapplicable == 0
    assert handovers, "the identity-named flip must be inapplicable on some replicate"
    # the handover lands on the flip, which is the fourth content move (index 3)
    assert min(handovers) >= 3
