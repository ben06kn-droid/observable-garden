"""Don Quixote, 7.2 part one: the two milestones, and the invariants they rest on.

Milestone 1: a scripted searcher driven through the harness-executed grammar
reproduces `SignedAdaptive`'s submission bit-identically on shared seeds.

Milestone 2: that run's move log, re-executed through `estimator.trigger_replay`,
returns the same null as the searcher's own replay.

If either fails the grammar is not expressive enough to stand in for a searcher,
and nothing obtained through it would mean anything.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from estimator.trigger_replay import replay_nulls
from garden.spec_class import SubsetClass
from quixote.drivers import signed_adaptive
from quixote.grammar import Grammar, Move
from quixote.replay import LoggedPolicy
from quixote.session import Session
from searchers.scripted import SignedAdaptive


def _fixture(seed, K, d, s=2, T=600):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    return generate(cfg), cfg, SubsetClass(max_size=d, signed=True)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("K,d", [(8, 2), (10, 3), (12, 3)])
def test_milestone_1_grammar_reproduces_signed_adaptive_bit_identically(seed, K, d):
    data, cfg, cls = _fixture(seed, K, d)

    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    signed_adaptive(s, max_features=d)

    sb2 = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    ref = SignedAdaptive(max_features=d, seed=0)
    ref.run(sb2)
    spec, dist = sb2.submission

    assert s.submission()[1] == float(dist.mean)        # bit-identical, not approx
    np.testing.assert_array_equal(s.submitted_weights(),
                                  np.asarray(spec.weights, dtype=float))


@pytest.mark.parametrize("seed", [0, 1, 2])
@pytest.mark.parametrize("K,d", [(10, 3), (12, 3)])
def test_milestone_2_the_log_replays_to_the_same_null(seed, K, d):
    data, cfg, cls = _fixture(seed, K, d, s=0)
    ann = float(np.sqrt(cfg.periods_per_year))
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    signed_adaptive(s, max_features=d)
    base = sb.base_feature_columns()

    own = recursive_null_max_bootstrap(
        base, SignedAdaptive(max_features=d, seed=0), B=120, block_length=25,
        annualization=ann, seed=5).M_b
    logged = replay_nulls(base, LoggedPolicy(s.log, cls), B=120, block_length=25,
                          annualization=ann, seed=5).policy
    np.testing.assert_array_equal(own, logged)


# -- the invariants the milestones rest on ----------------------------------

def test_the_harness_executes_the_move_so_the_log_cannot_disagree():
    """There is no path by which a caller supplies its own specification: the
    grammar computes it. That is what makes the log evidence rather than
    testimony."""
    data, cfg, cls = _fixture(0, 10, 3)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    s.propose(Move("extend_best"))
    s.accept()
    rec = s.log.records[0]
    assert rec.support_after == s.support
    assert rec.n_candidates == 2 * 10          # ten features, both signs
    assert s.grammar.contains(rec.support_after)


def test_a_late_prior_is_refused_not_discounted():
    data, cfg, cls = _fixture(0, 8, 2)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    s.pick_prior(((0, 1.0),))                  # before any evaluation: fine
    s.propose(Move("extend_best")); s.accept()
    with pytest.raises(ValueError, match="not a prior and is refused"):
        s.pick_prior(((1, 1.0),))
    with pytest.raises(ValueError, match="not a prior and is refused"):
        s.declare_short_list([((1, 1.0),)])


def test_the_short_list_cap_is_enforced_and_membership_checked():
    data, cfg, cls = _fixture(0, 8, 2)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    with pytest.raises(ValueError, match="cap 5"):
        s.declare_short_list([((i, 1.0),) for i in range(6)])
    with pytest.raises(ValueError, match="outside the declared class"):
        s.declare_short_list([tuple((i, 1.0) for i in range(5))])   # depth 5 > 2


def test_a_rejected_proposal_still_counts_its_candidates():
    """The candidates were computed, so they are trials, even though the support
    did not move. Counting only accepted moves would understate breadth."""
    data, cfg, cls = _fixture(1, 10, 3)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    s.propose(Move("extend_best")); s.accept()
    before = s.support
    s.propose(Move("extend_best")); s.reject()
    assert s.support == before
    assert s.log.records[-1].n_candidates > 0
    assert s.log.records[-1].move.note == "rejected"


def test_an_unsigned_class_can_never_produce_a_negative_sign():
    data, cfg, _ = _fixture(0, 8, 2)
    cls = SubsetClass(max_size=2, signed=False)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    s.propose(Move("extend_best")); s.accept()
    s.propose(Move("extend_best")); s.accept()
    assert all(sign == 1.0 for _, sign in s.support)
    assert s.grammar.candidates(s.support, Move("flip", feature=s.support[0][0])) == []


def test_the_statistic_library_refuses_what_it_has_not_built():
    data, cfg, cls = _fixture(0, 8, 2)
    g = Grammar(cls, Sandbox(data, periods_per_year=cfg.periods_per_year
                             ).base_feature_columns())
    with pytest.raises(ValueError, match="deliberately unbuilt"):
        g.score(((0, 1.0),), statistic="stability")


def test_the_dependency_direction_is_one_way():
    """quixote imports garden and estimator; nothing imports quixote."""
    import pathlib
    for pkg in ("garden", "estimator", "environments", "searchers", "experiments"):
        for f in pathlib.Path(pkg).rglob("*.py"):
            assert "import quixote" not in f.read_text(), f


def test_quixote_is_not_in_code_paths_and_has_its_own_fingerprint():
    from experiments.code_state import CODE_PATHS, code_fingerprint
    from quixote.fingerprint import QUIXOTE_PATHS, quixote_fingerprint
    assert "quixote" not in CODE_PATHS          # no published fingerprint moves
    assert "quixote" in QUIXOTE_PATHS
    assert quixote_fingerprint() != code_fingerprint()
    for dep in ("garden", "estimator"):
        assert dep in QUIXOTE_PATHS             # what quixote imports is inside it


# -- the identity-replicate guard -------------------------------------------

def test_the_identity_guard_passes_a_normal_run():
    data, cfg, cls = _fixture(0, 10, 3, s=0)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    signed_adaptive(s, max_features=3)
    from quixote.replay import identity_check
    c = identity_check(s.log, cls, sb.base_feature_columns(),
                       float(np.sqrt(cfg.periods_per_year)))
    assert c.agrees
    assert c.score_gap < 1e-9          # float accumulation, not a different search
    assert "PASS" in c.reason()


def test_the_identity_guard_catches_a_disagreeing_replay():
    """Constructed rather than waited for. The live and replay paths differ at
    ~1e-12, which flips an argmax only on a near-tie -- rare enough that a test
    cannot rely on finding one, and consequential enough that the guard has to
    be known to work."""
    from dataclasses import replace as dc_replace
    from quixote.replay import identity_check
    data, cfg, cls = _fixture(1, 10, 3, s=0)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    s = Session.on_sandbox(sb, cls)
    signed_adaptive(s, max_features=3)

    # a support the replay will not reproduce, on the last record the guard
    # reads as the submission: the last content move taken (the log now ends in
    # a real `stop` record, which carries no submission)
    i = max(j for j, r in enumerate(s.log.records)
            if not r.move.is_meta and r.move.note != "rejected")
    last = s.log.records[i]
    wrong = tuple((k, -sign) for k, sign in last.support_after)
    s.log.records[i] = dc_replace(last, support_after=wrong)

    c = identity_check(s.log, cls, sb.base_feature_columns(),
                       float(np.sqrt(cfg.periods_per_year)))
    assert not c.agrees
    assert "flagged and not priced" in c.reason()


def test_the_guard_fires_rarely_enough_to_be_usable():
    """Measured, not assumed: if it fired often the whole grammar approach would
    be unusable, and if it never could fire it would be decoration."""
    from quixote.replay import identity_check
    fired = 0
    for seed in range(40):
        data, cfg, cls = _fixture(seed, 12, 3, s=0, T=400)
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
        s = Session.on_sandbox(sb, cls)
        signed_adaptive(s, max_features=3)
        if not identity_check(s.log, cls, sb.base_feature_columns(),
                              float(np.sqrt(cfg.periods_per_year))).agrees:
            fired += 1
    assert fired == 0, f"guard fired on {fired} of 40 clean runs"


# -- milestone 3: restart and stop as grammar moves with declared triggers ----
#
# (a) StopWhenCleared and RestartAfterKFailures, driven through the grammar,
#     reproduce their scripted submissions bit-identically on shared seeds;
# (b) their session logs through estimator/trigger_replay.py return the same
#     three nulls as the scripted searchers' own;
# (c) the identity-replicate guard reproduces the realized sequence, including
#     where it stopped or restarted.

from quixote.drivers import restart_after_k_failures, stop_when_cleared  # noqa: E402
from searchers.meta_adaptive import RestartAfterKFailures, StopWhenCleared  # noqa: E402

META_CASES = [("stop", 0.3), ("stop", 0.8), ("stop", 1e9), ("restart", 1), ("restart", 2)]


def _meta_pair(kind, param):
    """The scripted searcher and its grammar driver, same parameter."""
    if kind == "stop":
        return StopWhenCleared(bar=param), lambda s: stop_when_cleared(s, bar=param)
    return RestartAfterKFailures(k=int(param)), lambda s: restart_after_k_failures(s, k=int(param))


def _meta_fixture(seed, K=10, s=1, T=600):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    # the scripted searchers are bounded only by their budget; an unsigned class
    # as wide as K refuses nothing they can reach, and keeps every sign +1
    return generate(cfg), cfg, SubsetClass(max_size=K, signed=False)


def _drive(kind, param, seed, s=1):
    data, cfg, cls = _meta_fixture(seed, s=s)
    scripted, driver = _meta_pair(kind, param)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
    sess = Session.on_sandbox(sb, cls)
    driver(sess)
    sb2 = Sandbox(data, periods_per_year=cfg.periods_per_year)
    scripted.run(sb2)
    return sess, scripted, sb2, sb, cfg, cls


def test_milestone_3a_grammar_reproduces_the_scripted_submissions_bit_identically():
    seen = {"restart": 0, "stop": 0}
    for kind, param in META_CASES:
        for seed in range(6):
            for s in (0, 2):
                sess, scripted, sb2, _, _, _ = _drive(kind, param, seed, s)
                spec, dist = sb2.submission
                assert sess.submission()[1] == float(dist.mean), (kind, param, seed, s)
                np.testing.assert_array_equal(sess.submitted_weights(),
                                              np.asarray(spec.weights, dtype=float))
                # and the meta decisions are the same, step for step
                assert sess.log.actions() == scripted.last_trace.actions()
                acts = sess.log.actions()
                seen["restart"] += "restart" in acts
                seen["stop"] += "stop" in acts
    assert seen["restart"] >= 10 and seen["stop"] >= 10, seen    # not vacuous


@pytest.mark.parametrize("kind,param", META_CASES)
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_milestone_3b_the_log_replays_to_the_same_three_nulls(kind, param, seed):
    sess, scripted, _, sb, cfg, cls = _drive(kind, param, seed, s=0)
    base = sb.base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))
    fresh, _ = _meta_pair(kind, param)
    own = replay_nulls(base, fresh, B=120, block_length=25, annualization=ann, seed=5)
    logged = replay_nulls(base, LoggedPolicy(sess.log, cls), B=120, block_length=25,
                          annualization=ann, seed=5)
    for which in ("fixed_sequence", "trigger", "policy"):
        np.testing.assert_array_equal(getattr(own, which), getattr(logged, which),
                                      err_msg=which)
    assert own.realized_score == logged.realized_score
    assert own.realized_actions == logged.realized_actions


def test_milestone_3b_is_not_vacuous_the_nulls_separate_somewhere():
    """If nulls 1-3 always coincided, (b) would hold for any replay at all. They
    must differ on some replicate for these searchers, as 7.1 exists to measure."""
    differs = 0
    for kind, param in (("stop", 0.3), ("restart", 1)):
        for seed in range(3):
            sess, _, _, sb, cfg, cls = _drive(kind, param, seed, s=0)
            n = replay_nulls(sb.base_feature_columns(), LoggedPolicy(sess.log, cls), B=120,
                             block_length=25, annualization=float(np.sqrt(cfg.periods_per_year)),
                             seed=5)
            differs += int(np.any(n.fixed_sequence != n.policy))
    assert differs >= 1


def test_milestone_3c_the_identity_guard_reproduces_stops_and_restarts():
    from quixote.replay import identity_check
    seen = {"restart": 0, "stop": 0}
    for kind, param in META_CASES:
        for seed in range(6):
            sess, scripted, _, sb, cfg, cls = _drive(kind, param, seed, s=0)
            c = identity_check(sess.log, cls, sb.base_feature_columns(),
                               float(np.sqrt(cfg.periods_per_year)))
            assert c.agrees, c.reason()
            assert c.realized_actions == c.replayed_actions == tuple(scripted.last_trace.actions())
            seen["restart"] += "restart" in c.realized_actions
            seen["stop"] += "stop" in c.realized_actions
    assert seen["restart"] >= 5 and seen["stop"] >= 5, seen


def test_milestone_3c_the_guard_catches_a_misplaced_restart():
    """Constructed: a restart recorded as an ordinary extension. The support can
    still match, so only the action comparison catches it."""
    from dataclasses import replace as dc_replace
    from quixote.replay import identity_check
    for seed in range(10):
        sess, _, _, sb, cfg, cls = _drive("restart", 1, seed, s=0)
        idx = [i for i, r in enumerate(sess.log.records) if r.move.kind == "restart"]
        if idx:
            break
    assert idx, "no restart in 10 seeds; fixture does not exercise the guard"
    r = sess.log.records[idx[0]]
    sess.log.records[idx[0]] = dc_replace(r, move=Move("extend_best"))
    c = identity_check(sess.log, cls, sb.base_feature_columns(),
                       float(np.sqrt(cfg.periods_per_year)))
    assert not c.agrees
    assert "meta decisions differ" in c.reason()


def test_meta_triggers_are_stamped_before_their_move_and_named_as_scripted():
    sess, scripted, _, _, _, _ = _drive("restart", 1, 0, s=0)
    metas = [r for r in sess.log.records if r.trigger_params is not None]
    assert metas
    for r in metas:
        assert r.trigger_stamped_at is not None and r.trigger_stamped_at <= r.timestamp
    assert {r.trigger for r in metas} == {"failures >= 1"}
    assert sess.log.budget == 12 and sess.log.declared_triggers() == [
        {"kind": "failures_at_least", "param": 1.0, "action": "restart"}]


def test_a_budget_declared_after_the_first_evaluation_is_refused():
    data, cfg, cls = _meta_fixture(0)
    sess = Session.on_sandbox(Sandbox(data, periods_per_year=cfg.periods_per_year), cls)
    sess.propose(Move("init")); sess.accept()
    with pytest.raises(ValueError, match="not a prior and is refused"):
        sess.declare_budget(12)


def test_milestone_3b_the_replay_reads_its_declared_triggers():
    """Guards (b) against passing by accident: re-declare the logged stop bar and
    the policy null must move while the fixed-sequence null, whose actions are
    frozen, must not."""
    from quixote.triggers import Trigger
    sess, _, _, sb, cfg, cls = _drive("stop", 0.3, 0, s=0)
    base, ann = sb.base_feature_columns(), float(np.sqrt(cfg.periods_per_year))
    lp = LoggedPolicy(sess.log, cls)
    as_logged = replay_nulls(base, lp, B=120, block_length=25, annualization=ann, seed=5)
    lp.triggers = [Trigger("best_so_far_above", 0.8, "stop")]
    moved = replay_nulls(base, lp, B=120, block_length=25, annualization=ann, seed=5)
    assert not np.array_equal(as_logged.policy, moved.policy)
    np.testing.assert_array_equal(as_logged.fixed_sequence, moved.fixed_sequence)
