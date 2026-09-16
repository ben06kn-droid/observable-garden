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
    got = audit(from_sandbox(w.sandbox, menu_kind=watch_mod.WATCHED_MENU_KIND), B=B_FAST, seed=12)

    assert got.status == expected.status
    assert got.p_value == pytest.approx(expected.p_value)
    assert got.critical_value == pytest.approx(expected.critical_value)
