"""garden/watch.py: the three contract invariants, plus membership and tier rules.

STEP 0. These are written against the contract and skipped until step 1
implements it. They are the definition of "watch works"; if implementing step 1
requires weakening one of them, that is a contract change and needs saying out
loud, not a quiet edit to the assertion.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Distribution, Sandbox, Specification
from garden import watch as watch_mod
from garden._full_class_engine import full_class_null_max
from garden.power import critical_value
from garden.spec_class import ExplicitClass, SubsetClass

pytestmark = pytest.mark.skipif(
    not getattr(watch_mod, "_IMPLEMENTED", False),
    reason="step 0 is the contract; watch.open/evaluate/submit land in step 1",
)

PPY = 252
ANN = np.sqrt(PPY)
B_FAST = 2000


def sandbox_with(K=6, T=300, seed=0, spec_class=None):
    config = DGPConfig(M=30, T=T, T_oos=100, K=K, s=0, rho=0.3, sigma=1.0, seed=seed)
    return Sandbox(generate(config), periods_per_year=PPY, spec_class=spec_class)


def single(K, k, name=""):
    w = np.zeros(K)
    w[k] = 1.0
    return Specification(weights=w, name=name or f"f{k}")


# -- Invariant 1: evaluate never touches out-of-sample data -------------------

def test_evaluate_never_touches_out_of_sample_data(monkeypatch):
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls)

    def forbidden(*args, **kwargs):
        raise AssertionError("watch.evaluate reached out-of-sample data")

    monkeypatch.setattr(Sandbox, "oos_sharpe_for_grading", forbidden)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=1)
    for k in range(4):
        w.evaluate(single(sb.num_features, k))


# -- Invariant 2: watch's bar equals audit's full-class null ------------------

def test_bar_equals_the_full_class_null_on_the_same_inputs():
    """Watch must not invent a second null. Same engine, same seed, same block
    length, same class -> the identical distribution audit would use."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=7, block_length=3)

    reference, L, _, _ = full_class_null_max(
        sb.base_feature_columns(), cls, B=B_FAST, block_length=3, annualization=ANN, seed=7)
    np.testing.assert_allclose(w.state.bar, reference, rtol=1e-12, atol=0)
    assert w.state.block_length == L == 3
    assert w.state.critical_value == critical_value(reference, w.state.alpha)


# -- Invariant 3: cleared at any step == the final verdict's PASS -------------

def test_cleared_matches_the_final_verdict():
    """The running signal must not disagree with the verdict it is predicting."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=3)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=4)

    reports = [w.evaluate(single(sb.num_features, k)) for k in range(sb.num_features)]
    best = max(range(len(reports)), key=lambda i: reports[i].sr_is)
    spec = single(sb.num_features, best)

    verdict = w.submit(spec, Distribution.degenerate(reports[best].sr_is))
    assert reports[best].cleared == (verdict.status == "PASS")
    assert verdict.method == "full_class"
    assert verdict.menu_kind == watch_mod.WATCHED_MENU_KIND


# -- Membership --------------------------------------------------------------

def test_specification_outside_the_class_is_refused():
    cls = SubsetClass(max_size=1)
    sb = sandbox_with(spec_class=cls)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=5)
    w.evaluate(single(sb.num_features, 0))                      # in class
    two = np.zeros(sb.num_features)
    two[[0, 1]] = 1.0                                           # size 2, outside max_size=1
    with pytest.raises(ValueError, match="outside the declared class"):
        w.evaluate(Specification(weights=two, name="pair"))


def test_explicit_class_is_deferred_at_open():
    """Deferred, not excluded. The moment engine takes a SubsetClass and
    membership refusal uses contains(), neither of which ExplicitClass offers --
    but audit already prices explicit classes off class_returns and transcript.py
    already checks them by spec id, so this is a second path to build, not a
    limit of the tier. Refusing at open is the honest interim behaviour; the
    message must point at the deferral rather than imply impossibility."""
    sb = sandbox_with()
    with pytest.raises(ValueError, match="SubsetClass"):
        watch_mod.open(sb, ExplicitClass(), B=100, seed=6)


# -- Admissibility at open ---------------------------------------------------

def test_open_returns_inadmissible_before_any_evaluation():
    """A class too broad to certify anything is refused at open, while the
    design can still be changed, and names a size that would clear the floor.

    This is the case that makes preflight real: the sample is long enough that
    *some* class would work, so the number returned is actionable."""
    sb = sandbox_with(K=40, T=1500)
    wide = SubsetClass(max_size=3)
    w = watch_mod.open(sb, wide, B=500, reference_sharpe=1.0, power_floor=0.50, seed=8)
    assert w.state.status == "INADMISSIBLE"
    assert w.state.admissible_class_size is not None
    assert 1 <= w.state.admissible_class_size < w.state.class_size
    assert any("would clear the floor" in r for r in w.state.reasons)
    # Refused before anything was evaluated.
    assert w.sandbox.returns_matrix().shape[1] == 0


def test_inadmissible_with_no_workable_class_size_says_so():
    """The honest answer when the sample is simply too short: not even one
    pre-specified specification reaches the floor, so no class size is named
    and the reason points at the sample rather than the breadth."""
    sb = sandbox_with(K=40, T=120)
    w = watch_mod.open(sb, SubsetClass(max_size=3), B=200, reference_sharpe=0.5,
                       power_floor=0.90, seed=8)
    assert w.state.status == "INADMISSIBLE"
    assert w.state.admissible_class_size is None
    assert any("Lengthen the sample" in r for r in w.state.reasons)


def test_power_is_measured_against_the_priced_bar():
    """The threshold power is computed against must be the bootstrap critical
    value read off this class's own bar -- the same one `cleared` uses -- not an
    analytic independent-max value. Otherwise the INADMISSIBLE decision at open
    and realized power disagree at every correlation but zero."""
    from garden.power import analytic_power
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, T=400)
    w = watch_mod.open(sb, cls, B=B_FAST, reference_sharpe=1.0, seed=13)
    expected = analytic_power(1.0, w.state.critical_value, w.state.n_periods, PPY)
    assert w.state.power_at_reference == pytest.approx(expected, rel=1e-12)


def test_the_priced_bar_differs_from_the_analytic_one_under_correlation():
    """The test that would have caught the bug. At rho=0 the bootstrap bar and
    the analytic independent-max value nearly coincide, so a power figure built
    on the wrong one still looks right; under correlation the class bar falls
    and they separate."""
    from garden.power import analytic_power, null_max_critical_value
    cls = SubsetClass(max_size=2)
    config = DGPConfig(M=30, T=400, T_oos=100, K=8, s=0, rho=0.6, sigma=1.0, seed=14)
    sb = Sandbox(generate(config), periods_per_year=PPY, spec_class=cls)
    w = watch_mod.open(sb, cls, B=B_FAST, reference_sharpe=1.0, seed=15)

    analytic_c = null_max_critical_value(w.state.class_size, w.state.n_periods, PPY, 0.05, 0.0)
    assert w.state.critical_value < analytic_c          # correlated members lower the bar
    # Power follows the priced bar, so it exceeds what the analytic bar implies.
    assert w.state.power_at_reference > analytic_power(1.0, analytic_c, w.state.n_periods, PPY)


def test_submit_with_no_arguments_audits_the_recorded_submission():
    """Scripted searchers call sandbox.submit() themselves inside run(), so the
    no-argument form is how step 5 gets a watched verdict for them."""
    from searchers.scripted import Greedy
    cls = SubsetClass(max_size=1)
    sb = sandbox_with(spec_class=cls, seed=16)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=17)
    Greedy(seed=16).run(w.sandbox)
    verdict = w.submit()
    assert verdict.method == "full_class"
    assert verdict.menu_kind == watch_mod.WATCHED_MENU_KIND
    assert verdict.status in ("PASS", "FAIL", "INADMISSIBLE", "DEGENERATE")


def test_submit_with_no_arguments_raises_when_nothing_was_submitted():
    cls = SubsetClass(max_size=1)
    sb = sandbox_with(spec_class=cls)
    w = watch_mod.open(sb, cls, B=500, seed=18)
    w.evaluate(single(sb.num_features, 0))
    with pytest.raises(ValueError, match="nothing submitted"):
        w.submit()


# -- Step 2: diagnostics -----------------------------------------------------

def pair(K, a, b, name=""):
    w = np.zeros(K)
    w[[a, b]] = 1.0
    return Specification(weights=w, name=name or f"f{a}+f{b}")


def test_cached_normalized_rank_matches_the_shared_helper():
    """kappa is cached off a base-column Sharpe ordering computed once at open.
    garden does not import searchers (product surface vs experiment
    scaffolding), so the expression is duplicated -- this pins the two together,
    the same arrangement estimator/spa.py uses for garden.power."""
    from searchers.dose_response import normalized_rank
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=20)
    w = watch_mod.open(sb, cls, B=500, seed=21)
    base = sb.base_feature_columns()
    for k in range(sb.num_features):
        assert w._normalized_rank(k) == pytest.approx(normalized_rank(base, k), rel=1e-12)


def test_kappa_is_defined_only_when_extending_a_single_feature_anchor():
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=22)
    K = sb.num_features
    w = watch_mod.open(sb, cls, B=500, seed=23)

    first = w.evaluate(single(K, 0))
    assert first.diagnostics["kappa"] is None
    assert "no anchor" in first.diagnostics["kappa_undefined_reason"]

    # Extends the best-so-far (f0) by exactly one feature -> kappa defined.
    ext = w.evaluate(pair(K, 0, 1))
    assert ext.diagnostics["kappa"] == pytest.approx(w._normalized_rank(0), rel=1e-12)
    assert ext.diagnostics["kappa_undefined_reason"] is None

    # A spec that does not extend the anchor -> undefined, with a reason.
    other = w.evaluate(single(K, 3))
    assert other.diagnostics["kappa"] is None
    assert "exactly one feature" in other.diagnostics["kappa_undefined_reason"]


def spec_from(K, support, name=""):
    w = np.zeros(K)
    w[sorted(support)] = 1.0
    return Specification(weights=w, name=name or "+".join(f"f{i}" for i in sorted(support)))


@pytest.mark.parametrize("seed", [60, 61, 62, 63])
def test_chase_rate_is_one_when_every_candidate_extends_the_best(seed):
    """Known by construction, not by seed. Each step evaluates the best-so-far's
    own support plus one new feature, so the indicator is true every time and
    the rate is exactly 1 regardless of what the data happens to do.

    The earlier version of this test drove a stochastic search and asserted on
    whatever it produced on one seed -- which made it a test of that seed. Same
    discipline as the P5 shortfall fix: assert the construction, not the draw."""
    cls = SubsetClass(max_size=4)
    sb = sandbox_with(K=8, spec_class=cls, seed=seed)
    K = sb.num_features
    w = watch_mod.open(sb, cls, B=300, seed=seed + 1)

    w.evaluate(single(K, 0))
    last = None
    for j in range(1, 7):
        support = set(w._best_support) | {j}
        if len(support) > cls.max_size:
            continue
        last = w.evaluate(spec_from(K, support))
        assert last.diagnostics["chased"] is True

    rates = [r.diagnostics["chase_rate"] for r in w.log if r.diagnostics["chase_rate"] is not None]
    assert rates and all(r == pytest.approx(1.0) for r in rates)

    warning = last.diagnostics["winner_chasing_warning"]
    assert warning is not None
    # Must not read as an instruction to stop: arm 3 measures that behaviour
    # rather than inducing it.
    assert "Nothing about this run is at risk" in warning
    assert "not a reason to stop" in warning


@pytest.mark.parametrize("seed", [70, 71, 72, 73])
def test_random_anchored_search_chases_at_about_one_over_K(seed):
    """A data-independent anchor contains the best-so-far only by coincidence,
    so the rate sits near 1/K and the warning stays silent on every seed."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(K=8, spec_class=cls, seed=seed)
    K = sb.num_features
    w = watch_mod.open(sb, cls, B=300, seed=seed + 1)
    rng = np.random.default_rng(seed)       # anchors drawn independently of the data

    w.evaluate(single(K, int(rng.integers(K))))
    last = None
    for _ in range(12):
        a, b = rng.choice(K, size=2, replace=False)
        last = w.evaluate(spec_from(K, {int(a), int(b)}))

    rate = last.diagnostics["chase_rate"]
    assert rate < watch_mod.CHASE_WARN_THRESHOLD
    assert rate <= 3.0 / K                  # generous band around 1/K
    assert last.diagnostics["winner_chasing_warning"] is None


@pytest.mark.parametrize("seed", [80, 81])
def test_enumerating_singles_never_chases(seed):
    """Greedy evaluates one single-feature spec after another. No candidate ever
    contains another's support, so the rate is exactly 0 by construction."""
    cls = SubsetClass(max_size=1)
    sb = sandbox_with(K=8, spec_class=cls, seed=seed)
    K = sb.num_features
    w = watch_mod.open(sb, cls, B=300, seed=seed + 1)
    last = None
    for k in range(K):
        last = w.evaluate(single(K, k))
    assert last.diagnostics["chase_rate"] == pytest.approx(0.0)
    assert last.diagnostics["winner_chasing_warning"] is None


def test_kappa_and_chase_rate_are_separate_fields():
    """Different quantities, deliberately sharing neither a name nor a warning:
    kappa is E17-exact and stops being defined once the best-so-far is more than
    one feature; the chase rate is defined at every step and at any depth."""
    cls = SubsetClass(max_size=3)
    sb = sandbox_with(K=8, spec_class=cls, seed=90)
    K = sb.num_features
    w = watch_mod.open(sb, cls, B=300, seed=91)
    w.evaluate(single(K, 0))

    # Depth 2: the anchor is a single feature, so kappa is defined. Note it can
    # be 0.0 -- that means "anchored on the worst-ranked feature", the opposite
    # of winner-chasing -- while `chased` is True, because the candidate did
    # build on the best-so-far. Two different questions, which is the whole
    # reason they are separate fields.
    anchor_before = set(w._best_support)
    assert len(anchor_before) == 1
    r = w.evaluate(spec_from(K, anchor_before | {1}))
    assert r.diagnostics["kappa"] is not None
    assert r.diagnostics["chased"] is True

    # Force an anchor spanning two features, so kappa must retire. Evaluating a
    # pair alone does not guarantee it becomes the best, so drive the state
    # directly rather than assume the draw cooperated.
    w._best_support = frozenset({0, 1})
    deep = w.evaluate(spec_from(K, {0, 1, 2}))
    assert deep.diagnostics["kappa"] is None
    assert "single anchor feature" in deep.diagnostics["kappa_undefined_reason"]
    # The chase rate keeps working at a depth where kappa has no job.
    assert deep.diagnostics["chased"] is True
    assert deep.diagnostics["chase_rate"] is not None


def test_shadow_and_class_p_values_are_reported_separately():
    """Both are reported against their own nulls and never differenced: the gap
    mixes the realized-menu test's liberality with the class test's
    conservatism, both same-signed, so it would overstate the first."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=28)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=29)
    r = w.evaluate(single(sb.num_features, 0))
    for key in ("shadow_p_value", "class_p_value"):
        assert 0.0 < r.diagnostics[key] <= 1.0
    assert not any("gap" in k for k in r.diagnostics)


def test_status_filters_to_agent_view_while_the_log_keeps_everything():
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=30)
    w = watch_mod.open(sb, cls, B=500, seed=31, agent_view="shadow")
    w.evaluate(single(sb.num_features, 0))

    seen = w.status().diagnostics
    assert set(seen) == {"shadow_p_value", "class_p_value"}
    assert set(w.log[-1].diagnostics) == set(watch_mod.DIAGNOSTIC_KEYS)


def test_standing_view_exposes_no_diagnostics_at_all():
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=32)
    w = watch_mod.open(sb, cls, B=500, seed=33)          # default: "standing"
    w.evaluate(single(sb.num_features, 0))
    assert w.status().diagnostics == {}
    assert w.status().cleared in (True, False)           # the gate itself is still visible


def test_agent_view_does_not_change_what_is_computed():
    """The guarantee that makes the split safe: two runs differing only in what
    the searcher can see must produce identical logs. Otherwise the choice of
    view would change the measured run, which is exactly the confound the split
    exists to prevent."""
    cls = SubsetClass(max_size=2)
    logs = []
    for view in ("standing", "full"):
        sb = sandbox_with(spec_class=cls, seed=34)
        w = watch_mod.open(sb, cls, B=500, seed=35, agent_view=view)
        for k in range(4):
            w.evaluate(single(sb.num_features, k))
        logs.append([r.diagnostics for r in w.log])
    for a, b in zip(*logs):
        assert a == b


def test_unknown_agent_view_is_refused():
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls)
    with pytest.raises(ValueError, match="unknown agent_view"):
        watch_mod.open(sb, cls, B=200, seed=36, agent_view="coaching")


def test_consider_counts_distinct_identifiers():
    """Latent forking. Irrelevant to validity under the declared tier -- the bar
    already covers every member, evaluated or not -- but the count is the only
    direct measure of how far the logged trial count sits below the true one."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls, seed=37)
    w = watch_mod.open(sb, cls, B=500, seed=38)
    w.consider(["a", "b", "a"])
    w.consider("c")
    r = w.evaluate(single(sb.num_features, 0))
    assert r.diagnostics["considered"] == 3
    assert r.diagnostics["evaluated"] == 1
    assert r.diagnostics["considered_ratio"] == pytest.approx(3.0)


def test_open_refuses_a_sandbox_enforcing_a_different_class():
    """The tier's premise is that the class was fixed before the search. If the
    sandbox is enforcing one class and watch is asked to price another, the two
    disagree about what Theta is and the run has no standing."""
    sb = sandbox_with(spec_class=SubsetClass(max_size=1))
    with pytest.raises(ValueError, match="enforces"):
        watch_mod.open(sb, SubsetClass(max_size=3), B=100, seed=10)


# -- The bar is fixed --------------------------------------------------------

def test_the_class_null_and_critical_value_do_not_move():
    """The property that makes unlimited querying safe: nothing inside Theta
    changes the null. Without this, watch would be a leaderboard and the
    adaptive-query literature would price it.

    Scope, deliberately narrow: this asserts on the class null and its critical
    value ONLY. Step 2's diagnostics are *supposed* to move as columns
    accumulate -- the shadow realized-menu p-value drifting liberal is the whole
    point of reporting it -- so this test must never be broadened to "nothing in
    the state changed", or step 2 would have to weaken it."""
    cls = SubsetClass(max_size=2)
    sb = sandbox_with(spec_class=cls)
    w = watch_mod.open(sb, cls, B=B_FAST, seed=9)
    before_c, before_bar = w.state.critical_value, w.state.bar.copy()
    for k in range(sb.num_features):
        w.evaluate(single(sb.num_features, k))
    assert w.state.critical_value == before_c
    np.testing.assert_array_equal(w.state.bar, before_bar)


# -- Watch changes nothing about the verdict ---------------------------------

def test_watched_greedy_reproduces_the_unwatched_verdict():
    """Watch is instrumentation. A scripted search under watch must get exactly
    the verdict it would have got with the same declared class and no watch."""
    from garden.audit import audit
    from garden.transcript import from_sandbox
    from searchers.scripted import Greedy

    cls = SubsetClass(max_size=1)
    plain = sandbox_with(spec_class=cls, seed=11)
    Greedy(seed=11).run(plain)
    expected = audit(from_sandbox(plain, menu_kind=watch_mod.WATCHED_MENU_KIND), B=B_FAST, seed=12)

    watched = sandbox_with(spec_class=cls, seed=11)
    w = watch_mod.open(watched, cls, B=B_FAST, seed=12)
    Greedy(seed=11).run(w.sandbox)
    # Through watch's own submit path, which is what step 5 will use.
    got = w.submit()

    assert got.status == expected.status
    assert got.p_value == pytest.approx(expected.p_value)
    assert got.critical_value == pytest.approx(expected.critical_value)
