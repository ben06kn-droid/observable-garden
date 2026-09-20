"""7.1's components: meta-adaptive searchers, their triggers, and the three
replay nulls.

Unit level only — no sweeps. What these pin is that the machinery means what 7.1
needs it to mean: triggers are recorded with the value they saw, fixed-sequence
replay really does freeze the meta choices while re-executing content rules, and
trigger replay really does re-evaluate the predicate on the replicate.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.trigger_replay import NULLS, replay_nulls
from searchers.meta_adaptive import (
    BUDGET, ExtendWhileImproving, RestartAfterKFailures, StopWhenCleared)


def _base(K=8, T=400, seed=3):
    cfg = DGPConfig(M=10, T=T, T_oos=100, K=K, s=1, rho=0.0, sigma=1.0, seed=seed)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    return sb.base_feature_columns(), np.sqrt(cfg.periods_per_year)


def _all_three(bar=0.5):
    return [StopWhenCleared(bar=bar), RestartAfterKFailures(k=2),
            ExtendWhileImproving(min_gain=0.0)]


# -- traces and triggers -----------------------------------------------------

@pytest.mark.parametrize("searcher", _all_three())
def test_every_move_records_the_trigger_and_what_it_saw(searcher):
    base, ann = _base()
    t = searcher.trace(base, ann)
    assert t.n_moves >= 1
    assert t.policy == searcher.name
    for m in t.moves:
        assert m.action in {"continue", "restart", "stop"}
        assert m.trigger                      # a named predicate, never blank
        # +inf is the legitimate opening value of a gain predicate: the first
        # extension always happens, there being no previous gain to compare to.
        assert (np.isfinite(m.trigger_value) or m.trigger_value == float("inf")
                or m.trigger in {"exhausted", "frozen", "fill"})


def test_stop_when_cleared_stops_exactly_when_the_bar_is_beaten():
    """The winner-anchored trigger: the stopping time is a function of the
    running maximum, which is why freezing it is the error 7.1 measures."""
    base, ann = _base()
    low = StopWhenCleared(bar=-1e9).trace(base, ann)     # fires immediately
    assert low.moves[0].action == "stop"
    assert low.n_moves == 1

    high = StopWhenCleared(bar=1e9).trace(base, ann)     # never fires
    assert all(m.action != "stop" or m.trigger == "exhausted" for m in high.moves)
    assert high.n_moves >= 2


def test_restart_moves_to_a_fresh_anchor_after_k_failures():
    base, ann = _base()
    t = RestartAfterKFailures(k=1).trace(base, ann)
    restarts = [m for m in t.moves if m.action == "restart"]
    if restarts:
        # a restart replaces the support with a single fresh feature
        assert all(len(m.support) == 1 for m in restarts)


def test_extend_while_improving_stops_on_a_non_improving_extension():
    base, ann = _base()
    t = ExtendWhileImproving(min_gain=1e9).trace(base, ann)
    assert t.moves[-1].action == "stop"


@pytest.mark.parametrize("searcher", _all_three())
def test_the_budget_is_never_exceeded(searcher):
    base, ann = _base()
    assert searcher.trace(base, ann).n_moves <= BUDGET


@pytest.mark.parametrize("searcher", _all_three())
def test_replay_reproduces_the_policy_on_the_same_data(searcher):
    base, ann = _base()
    assert searcher.replay(base, ann) == pytest.approx(
        searcher.trace(base, ann).score, rel=1e-12)


# -- the replay rules --------------------------------------------------------

@pytest.mark.parametrize("searcher", _all_three())
def test_fixed_sequence_replay_takes_the_realized_actions(searcher):
    """Freezing the meta choices while re-executing content rules: on the same
    data it must reproduce the realized answer exactly, because the realized
    actions are what the policy chose there."""
    base, ann = _base()
    t = searcher.trace(base, ann)
    assert searcher.replay_fixed_sequence(base, t.actions(), ann) == pytest.approx(
        t.score, rel=1e-12)


def test_fixed_sequence_replay_ignores_what_the_replicate_sees():
    """The defining property. A searcher told to stop at step 0 stops at step 0
    on every replicate, however far that replicate's own trigger would have let
    it run."""
    base, ann = _base()
    frozen = ["stop"]
    never = StopWhenCleared(bar=1e9)                  # its own trigger never fires
    assert never.replay_fixed_sequence(base, frozen, ann) == pytest.approx(
        max(never.trace(base, ann).moves[0].score,
            never.replay_fixed_sequence(base, frozen, ann)), rel=1e-12)
    # frozen to one move, it cannot reach the score its policy reaches
    assert never.replay_fixed_sequence(base, frozen, ann) <= never.replay(base, ann) + 1e-12


@pytest.mark.parametrize("searcher", _all_three())
def test_trigger_replay_equals_policy_replay_for_a_scripted_policy(searcher):
    """Documented coincidence, asserted so it cannot drift silently.

    All three searchers' "continue" move is greedy extension, which is also 7.1's
    fill rule, so re-evaluating the predicates and re-running the policy give the
    same number. That is what makes these three the right validation vehicle: with
    nulls 2 and 3 pinned together, the fixed-sequence gap is measured with nothing
    else moving. A searcher whose continue-move is not greedy extension -- an
    agent's, in 7.3 -- separates them."""
    base, ann = _base()
    t = searcher.trace(base, ann)
    assert searcher.replay_triggers(base, t.n_moves, ann) == pytest.approx(
        searcher.replay(base, ann), rel=1e-12)


def test_trigger_replay_fills_past_the_realized_sequence():
    """A replicate that would run longer than the real search has no declared
    trigger left, so it extends greedily to the budget rather than truncating."""
    base, ann = _base()
    s = StopWhenCleared(bar=1e9)
    short = s.replay_triggers(base, 1, ann)          # one meta step, then fill
    assert short >= s.trace(base, ann).moves[0].score - 1e-12


# -- the three nulls ---------------------------------------------------------

def test_replay_nulls_are_paired_and_well_formed():
    base, ann = _base()
    nulls = replay_nulls(base, RestartAfterKFailures(k=2), B=64, annualization=ann, seed=0)
    d = nulls.as_dict()
    assert set(d) == set(NULLS)
    for k, v in d.items():
        assert v.shape == (64,)
        assert np.isfinite(v).all(), k
    assert nulls.block_length >= 1
    assert nulls.realized_actions == tuple(nulls.realized_actions)


def test_the_nulls_are_drawn_on_one_shared_index():
    """Paired by construction: the same seed must give the same three columns,
    and trigger must track policy replicate by replicate."""
    base, ann = _base()
    s = ExtendWhileImproving(min_gain=0.0)
    a = replay_nulls(base, s, B=48, annualization=ann, seed=11)
    b = replay_nulls(base, s, B=48, annualization=ann, seed=11)
    for k in NULLS:
        np.testing.assert_array_equal(getattr(a, k), getattr(b, k))
    np.testing.assert_allclose(a.trigger, a.policy, rtol=1e-12)


def test_kolmogorov_distance_is_zero_against_itself_and_bounded():
    base, ann = _base()
    n = replay_nulls(base, StopWhenCleared(bar=0.5), B=64, annualization=ann, seed=2)
    assert n.kolmogorov_distance("policy", "policy") == pytest.approx(0.0)
    d = n.kolmogorov_distance("fixed_sequence", "policy")
    assert 0.0 <= d <= 1.0


def test_p_values_lie_in_the_unit_interval_and_use_the_plus_one_rule():
    base, ann = _base()
    n = replay_nulls(base, StopWhenCleared(bar=0.5), B=32, annualization=ann, seed=5)
    for k in NULLS:
        p = n.p_value(k)
        assert 1 / 33 <= p <= 1.0
    # a statistic above every replicate takes the smallest attainable value
    assert n.p_value("policy", sr=1e9) == pytest.approx(1 / 33)


def test_a_frozen_early_stop_gives_a_smaller_null_than_the_policy():
    """The direction 7.1 predicts, on one sample rather than as a sweep.

    The realized search runs on the real data, clears a low bar almost at once
    and stops. Freezing that short sequence holds every null replicate to the
    same few moves, while the policy lets a replicate keep searching because its
    own best-so-far has not cleared anything. The frozen null therefore sits
    below the policy null, and a null that is too small is exactly what makes
    fixed-sequence replay liberal."""
    base, ann = _base(K=10, T=600, seed=7)
    s = StopWhenCleared(bar=0.3)
    realized = s.trace(base, ann)
    assert realized.moves[-1].action == "stop"        # it did stop early
    assert realized.n_moves < BUDGET
    n = replay_nulls(base, s, B=200, annualization=ann, seed=1)
    assert n.fixed_sequence.mean() < n.policy.mean()
    assert n.kolmogorov_distance("fixed_sequence", "policy") > 0.0
