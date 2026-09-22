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
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from estimator.trigger_replay import NULLS, replay_nulls
from searchers.meta_adaptive import (
    BUDGET, GREEDY_CONTINUATION, INFORMATIVE_FOR_FILL, ExtendBySecondBest,
    ExtendWhileImproving, RestartAfterKFailures, StopWhenCleared,
    SwapWorstWhileImproving)


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
def test_trigger_replay_matches_the_policy_on_the_data_it_was_read_from(searcher):
    base, ann = _base()
    t = searcher.trace(base, ann)
    assert searcher.replay_triggers(base, t.n_moves, ann) == pytest.approx(
        searcher.replay(base, ann), rel=1e-12)


def test_trigger_and_policy_differ_only_in_filled_content():
    """Amendment 6's invariant. The declared triggers are evaluated at every step,
    past the realized length too, so trigger replay takes the policy's meta
    decision wherever its state is the policy's, and the two nulls can differ
    only on a replicate where some step was actually filled.

    (The earlier fill kept moving where a stop policy would have stopped, so
    StopWhenCleared diverged in the meta dimension. That divergence is gone by
    construction, and is what forced rule 3's sign conservative.)"""
    base, ann = _base(K=10, T=600, seed=7)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = select_block_length(S0)
    for s in (StopWhenCleared(bar=0.3), ExtendBySecondBest(min_gain=0.0)):
        realized = s.trace(base, ann)
        n = realized.n_moves
        rng = np.random.default_rng(3)
        seen = 0
        for _ in range(120):
            R = S0[stationary_bootstrap_indices(S0.shape[0], L, rng), :]
            trig, pol = s.trace(R, ann, meta_steps=n), s.trace(R, ann)
            if abs(trig.score - pol.score) > 1e-12:
                assert any(m.filled for m in trig.moves), \
                    f"{s.name}: diverged with no filled step"
                seen += 1
            # the first step past the realized length: same meta decision
            if len(trig.moves) > n and len(pol.moves) > n:
                assert trig.moves[n].action == pol.moves[n].action
        if isinstance(s, ExtendBySecondBest):
            assert seen > 0, "the dominated continuation must diverge somewhere"


def test_trigger_replay_fills_past_the_realized_sequence():
    """A replicate that runs longer than the real search is filled, not truncated:
    its triggers still decide (here the bar is never cleared, so it continues),
    and the fill supplies each continuation."""
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


# -- the fill rule, and the searcher that actually tests it ------------------

def test_the_fourth_searcher_separates_trigger_from_policy_replay():
    """The reason ExtendBySecondBest exists.

    For the other three, trigger replay and policy replay coincide exactly,
    because their continue-move is greedy extension and that is also 7.1's fill
    rule -- so the fill is never actually exercised, and 7.3 cannot exercise it
    either, an agent having no exact policy null to compare against. This
    searcher's continuation is deliberately not greedy, so a replicate running
    past the realized sequence gets a different move from the policy's, and the
    two nulls must differ."""
    base, ann = _base(K=10, T=600, seed=7)
    s = ExtendBySecondBest(min_gain=0.0)
    n = replay_nulls(base, s, B=200, annualization=ann, seed=3)
    assert not np.allclose(n.trigger, n.policy), "nulls 2 and 3 must separate here"
    assert n.kolmogorov_distance("trigger", "policy") > 0.0


def test_greedy_continuation_searchers_separate_only_rarely():
    """The contrast that justifies the fourth searcher. For a greedy-continuation
    searcher the fill can diverge only in the meta dimension, which needs a short
    realized sequence and is therefore occasional; ExtendBySecondBest diverges in
    the content dimension on every filled step."""
    base, ann = _base(K=10, T=600, seed=7)
    rates = {}
    for cls in GREEDY_CONTINUATION:
        s = cls(bar=0.3) if cls is StopWhenCleared else cls()
        n = replay_nulls(base, s, B=120, annualization=ann, seed=3)
        rates[s.name] = float(np.mean(np.abs(n.trigger - n.policy) > 1e-12))
    second = replay_nulls(base, ExtendBySecondBest(min_gain=0.0), B=120,
                          annualization=ann, seed=3)
    second_rate = float(np.mean(np.abs(second.trigger - second.policy) > 1e-12))
    assert max(rates.values()) < 0.05, rates
    assert second_rate > max(rates.values())


def test_the_signed_distance_reports_direction_not_just_size():
    base, ann = _base(K=10, T=600, seed=7)
    n = replay_nulls(base, ExtendBySecondBest(min_gain=0.0), B=200,
                     annualization=ann, seed=3)
    signed = n.signed_kolmogorov_distance("trigger", "policy")
    unsigned = n.kolmogorov_distance("trigger", "policy")
    assert abs(signed) == pytest.approx(unsigned, rel=1e-12)
    # a null that is stochastically smaller gives a lower bar, hence a smaller
    # p-value: liberal. The sign must agree with the p-values it implies.
    if signed > 0:
        assert n.p_value("trigger") <= n.p_value("policy")
    elif signed < 0:
        assert n.p_value("trigger") >= n.p_value("policy")


def test_the_fill_rule_is_conservative_here():
    """7.1's substantive question, on one sample rather than as a sweep: filling
    with greedy extension gives a null at least as large as the policy's,
    because greedy extension is the best available move and the policy's
    second-best choice cannot beat it. Conservative is the acceptable direction."""
    base, ann = _base(K=10, T=600, seed=7)
    n = replay_nulls(base, ExtendBySecondBest(min_gain=0.0), B=300,
                     annualization=ann, seed=5)
    assert n.trigger.mean() >= n.policy.mean() - 1e-12
    assert n.signed_kolmogorov_distance("trigger", "policy") <= 0.0


# -- the amended fill: best one-step move over the whole content grammar ----

def test_the_fill_ranges_over_extend_swap_and_flip():
    """The fill is no longer greedy extension. It must be able to return a swap
    or a flip, or the amendment is cosmetic."""
    base, ann = _base(K=8, T=400, seed=3)
    s = SwapWorstWhileImproving()
    _, support_score = s._scorers_from_columns(base, ann)
    support = [(0, 1.0), (1, 1.0), (2, 1.0)]
    kinds = {k for _, k, _ in s._grammar(support, 8, support_score)}
    assert kinds == {"extend", "swap", "flip"}
    # a flip really changes the spec rather than being a no-op, which is why
    # supports carry signs at all
    flips = [ns for _, k, ns in s._grammar(support, 8, support_score) if k == "flip"]
    assert any(any(sign < 0 for _, sign in ns) for ns in flips)


def test_the_swap_searcher_separates_trigger_from_policy_replay():
    """On this small fixture (K = 10) swap engages the fill and separates nulls 2
    and 3. At the registered K = 40 it does not (engagement 0 of 2,000 on the
    design block), which is why amendment 6 dropped it from rule 3; this test
    pins only that the machinery can separate them when it engages."""
    base, ann = _base(K=10, T=600, seed=7)
    n = replay_nulls(base, SwapWorstWhileImproving(), B=200, annualization=ann, seed=5)
    differ = np.mean(np.abs(n.trigger - n.policy) > 1e-12)
    assert differ > 0.05, f"nulls 2 and 3 must separate here; differed on {differ:.1%}"
    assert n.kolmogorov_distance("trigger", "policy") > 0.0


def test_the_measured_direction_of_the_fill_is_conservative():
    """Recorded, not assumed. On this fixture both non-greedy continuations give
    a negative signed Kolmogorov distance -- trigger's null is stochastically
    larger, a higher bar, a larger p-value, so the fill errs conservatively,
    which is the acceptable direction. On this fixture the swap searcher's margin
    is the smaller. (Amendment 6 reads rule 3 on lookahead, random-extend and
    second-best; swap is inert at K = 40.)"""
    base, ann = _base(K=10, T=600, seed=7)
    margins = {}
    for s in (ExtendBySecondBest(), SwapWorstWhileImproving()):
        n = replay_nulls(base, s, B=200, annualization=ann, seed=5)
        skd = n.signed_kolmogorov_distance("trigger", "policy")
        assert skd < 0.0, f"{s.name}: fill read liberal at {skd:+.4f}"
        assert (n.trigger - n.policy).mean() > 0.0
        margins[s.name] = skd
    assert margins["swap-worst-while-improving"] > margins["second-best-while-improving"]


# -- the optional class cap (amendment 4) -----------------------------------

def _all_five(bar=0.5):
    return [StopWhenCleared(bar=bar), RestartAfterKFailures(k=2),
            ExtendWhileImproving(), ExtendBySecondBest(),
            SwapWorstWhileImproving()]


@pytest.mark.parametrize("searcher", _all_five())
def test_uncapped_is_bit_identical_to_the_registered_behaviour(searcher):
    """`None` must change nothing. 7.1 runs uncapped, so a regression here would
    silently alter the experiment the pre-registration fixed."""
    base, ann = _base(K=12, T=600, seed=5)
    before = searcher.trace(base, ann)
    searcher.set_class(None)
    after = searcher.trace(base, ann)
    assert after.score == before.score          # bit-identical, not approx
    assert after.support == before.support
    assert after.actions() == before.actions()


@pytest.mark.parametrize("d", [1, 2, 3])
@pytest.mark.parametrize("searcher", _all_five())
def test_a_capped_search_never_leaves_the_declared_class(searcher, d):
    from garden.spec_class import SubsetClass
    from searchers.meta_adaptive import _signed_sum
    cls = SubsetClass(max_size=d, signed=True)
    base, ann = _base(K=10, T=600, seed=2)
    searcher.set_class(cls)
    t = searcher.trace(base, ann)
    assert cls.contains(_signed_sum(10, t.support))
    assert len(t.support) <= d
    assert all(m.action in {"continue", "restart", "stop"} for m in t.moves)


def test_the_cap_binds_where_it_should():
    """The cap must actually bind somewhere, or every test above passes
    vacuously. It binds on 7.1's registered configuration and not on the small
    fixtures, which is itself worth pinning: extend-while-improving stops at
    depth 1 on a short noisy panel and runs to depth 5 on the real one."""
    from garden.spec_class import SubsetClass
    cfg = DGPConfig(M=50, T=5000, T_oos=1000, K=40, s=0, rho=0.0, sigma=1.0,
                    seed=300_000)                      # 7.1's registered seed block
    base = Sandbox(generate(cfg),
                   periods_per_year=cfg.periods_per_year).base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))

    free = ExtendWhileImproving().trace(base, ann)
    capped = ExtendWhileImproving().set_class(
        SubsetClass(max_size=3, signed=True)).trace(base, ann)
    assert len(free.support) > 3, "fixture no longer exercises the cap"
    assert len(capped.support) <= 3
    assert capped.score <= free.score + 1e-12


def test_a_capped_replay_refuses_the_same_moves_as_the_capped_run():
    """Amendment 4's licence-transfer argument, as far as code can check it:
    membership depends on the support and the class, not on the data, so the
    restriction applies identically to a replicate."""
    from garden.spec_class import SubsetClass
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    cls = SubsetClass(max_size=2, signed=True)
    base, ann = _base(K=10, T=600, seed=7)
    s = ExtendWhileImproving().set_class(cls)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = select_block_length(S0)
    rng = np.random.default_rng(0)
    for _ in range(25):
        R = S0[stationary_bootstrap_indices(S0.shape[0], L, rng), :]
        t = s.trace(R, ann)
        assert len(t.support) <= 2


# -- the submission matches its claimed score (amendment 5) -------------------

def _every_searcher():
    return [StopWhenCleared(bar=0.5), RestartAfterKFailures(k=1), RestartAfterKFailures(k=2),
            ExtendWhileImproving(min_gain=0.0), ExtendBySecondBest(min_gain=0.0),
            SwapWorstWhileImproving(min_gain=0.0)]


def test_claimed_score_is_the_submitted_supports_own_on_the_replay_path():
    """fixed-sequence-replay amendment 5. After a restart the search keeps the
    global best score; the reported support must be the one that earned it.
    Exact, because the claim and the recomputation are the same function of the
    same base columns. Restarts must actually occur, or the test is vacuous."""
    from searchers.meta_adaptive import _column_sharpe
    restarts = 0
    for seed in range(12):
        base, ann = _base(K=10, T=600, seed=seed)
        for s in _every_searcher():
            t = s.trace(base, ann)
            restarts += "restart" in t.actions()
            stream = sum(base[:, k] * g for k, g in t.support)
            assert _column_sharpe(stream, ann) == t.score, (s.name, seed, t.actions())
    assert restarts >= 10, f"only {restarts} runs restarted; the fixture is not exercising the fix"


def test_claimed_score_is_the_submitted_supports_own_on_the_live_path():
    """The same claim through run(): the Sharpe submitted equals a fresh sandbox's
    evaluation of the submitted weights. Both come from the sandbox's own scorer
    on identical weights, so equality is exact."""
    from environments.sandbox import Specification
    restarts = 0
    for seed in range(6):
        cfg = DGPConfig(M=10, T=600, T_oos=100, K=10, s=1, rho=0.0, sigma=1.0, seed=seed)
        data = generate(cfg)
        for s in _every_searcher():
            sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
            s.run(sb)
            restarts += "restart" in s.last_trace.actions()
            spec, dist = sb.submission
            fresh = Sandbox(data, periods_per_year=cfg.periods_per_year)
            got = fresh.evaluate(Specification(weights=np.asarray(spec.weights, dtype=float),
                                               name="recheck")).sharpe
            assert got == float(dist.mean), (s.name, seed)
    assert restarts >= 5


# -- the moment scorer: equivalence with the column path (amendment 6 sizing) --

def test_moment_scoring_matches_column_scoring_on_the_design_block():
    """The fast scorer computes each replicate's mean vector and covariance once
    and scores every candidate from them. It must reproduce the column path:
    identical actions -- realized and on every replicate, in all three nulls --
    and values within 1e-10, for all six registered searchers at the registered
    configuration (K = 40, M = 50, T = 5,000), on design seeds only."""
    from searchers.meta_adaptive import registered_71
    for seed in (960000, 960001):
        cfg = DGPConfig(M=50, T=5000, T_oos=1000, K=40, s=0, rho=0.0, sigma=1.0, seed=seed)
        base = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year).base_feature_columns()
        ann = float(np.sqrt(cfg.periods_per_year))
        se = float(np.sqrt(cfg.periods_per_year / cfg.T))
        S0 = base - base.mean(axis=0, keepdims=True)
        L = select_block_length(S0)
        for slow, fast in zip(registered_71(seed, se), registered_71(seed, se)):
            fast.scoring = "moments"
            rs, rf = slow.trace(base, ann), fast.trace(base, ann)
            assert rs.actions() == rf.actions(), slow.name
            assert abs(rs.score - rf.score) < 1e-10, slow.name
            acts, n = rs.actions(), rs.n_moves
            rng = np.random.default_rng(seed)
            for _ in range(3):
                R = S0[stationary_bootstrap_indices(S0.shape[0], L, rng), :]
                for kw in ({}, {"meta_steps": n}, {"frozen": acts}):
                    a, b = slow.trace(R, ann, **kw), fast.trace(R, ann, **kw)
                    assert a.actions() == b.actions(), (slow.name, kw)
                    assert a.support == b.support, (slow.name, kw)
                    assert abs(a.score - b.score) < 1e-10, (slow.name, kw, a.score - b.score)
