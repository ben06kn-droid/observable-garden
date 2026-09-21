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
