"""6.4: explicit classes in `watch`.

`watch` priced its bar only with the moment engine, which takes a SubsetClass, so
an agent whose tool grammar emits rules rather than equal-weight feature subsets
could not be watched at all. `garden.audit` already handled explicit classes by
running the Reality Check directly on the supplied streams; watch now takes the
same path.

The three things that have to hold: the bar watch prices at open is the bar audit
prices at submit, membership is refused by id rather than by weight vector, and
nothing a search does moves the bar.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Distribution, Sandbox, Specification
from garden import watch
from garden._engine import null_max_bootstrap
from garden.spec_class import ExplicitClass, SubsetClass


def _fixture(K=6, T=800, seed=2):
    cfg = DGPConfig(M=10, T=T, T_oos=200, K=K, s=1, rho=0.0, sigma=1.0, seed=seed)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year)
    base = sb.base_feature_columns()
    cols = [base[:, k] for k in range(K)] + [base[:, 0] - base[:, 1], base[:, 2] + base[:, 3]]
    ids = [f"rule_single_{k}" for k in range(K)] + ["rule_spread_01", "rule_sum_23"]
    return sb, cfg, np.column_stack(cols), ids


def _open(sb, cr, ids, **kw):
    kw.setdefault("B", 400)
    kw.setdefault("seed", 7)
    kw.setdefault("power_floor", 0.0)
    return watch.open(sb, ExplicitClass(n_members=len(ids)),
                      class_returns=cr, class_ids=ids, **kw)


def test_the_bar_is_the_reality_check_on_the_supplied_streams():
    sb, cfg, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    ref = null_max_bootstrap(cr, B=400, block_length=w.state.block_length,
                             annualization=np.sqrt(cfg.periods_per_year), seed=7)
    np.testing.assert_array_equal(w.state.bar, ref.M_b)
    assert w.state.class_size == len(ids)


def test_the_bar_priced_at_open_is_the_bar_audit_prices_at_submit():
    """The property that makes watch's running standing honest: what the searcher
    is told it must beat is what it is actually judged against."""
    sb, cfg, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    best, best_sr = None, -np.inf
    for k in range(6):
        r = w.evaluate(Specification(weights=np.eye(6)[k], name=f"rule_single_{k}"))
        if r.sr_is > best_sr:
            best, best_sr = k, r.sr_is
    v = w.submit(Specification(weights=np.eye(6)[best], name=f"rule_single_{best}"),
                 Distribution.degenerate(best_sr))
    assert v.critical_value == pytest.approx(w.state.critical_value, rel=1e-12)
    assert v.class_size == len(ids)


def test_membership_is_refused_by_id():
    sb, _, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    with pytest.raises(ValueError, match="not a member of the declared explicit"):
        w.evaluate(Specification(weights=np.eye(6)[0], name="some_other_rule"))
    assert w.state.refused_attempts == 1
    assert w.refused_attempts[0]["spec"] == "some_other_rule"


def test_matching_weights_do_not_buy_membership():
    """Why membership is by id: correlated rules routinely produce near-duplicate
    return streams, so a weight vector that happens to coincide with a member's
    is not evidence that the rule was declared."""
    sb, _, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    # identical weights to rule_single_0, a name that was never declared
    with pytest.raises(ValueError):
        w.evaluate(Specification(weights=np.eye(6)[0], name="rule_single_0_copy"))
    assert w.state.refused_attempts == 1


def test_a_refused_attempt_enters_no_data():
    sb, _, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    with pytest.raises(ValueError):
        w.evaluate(Specification(weights=np.eye(6)[0], name="undeclared"))
    assert sb.returns_matrix().shape[1] == 0


def test_the_bar_does_not_move_however_much_is_evaluated():
    sb, _, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    cv, bar = w.state.critical_value, w.state.bar.copy()
    for k in range(6):
        w.evaluate(Specification(weights=np.eye(6)[k], name=f"rule_single_{k}"))
        w.evaluate(Specification(weights=np.eye(6)[k], name=f"rule_single_{k}"))
    assert w.state.critical_value == cv
    np.testing.assert_array_equal(w.state.bar, bar)


def test_re_evaluating_a_member_is_not_a_second_trial():
    """Explicit transcripts are keyed by spec name and names must be unique, so a
    member seen twice contributes one column. The bar is priced over the class
    either way, so this cannot change the verdict."""
    sb, _, cr, ids = _fixture()
    w = _open(sb, cr, ids)
    for _ in range(3):
        r = w.evaluate(Specification(weights=np.eye(6)[0], name="rule_single_0"))
    v = w.submit(Specification(weights=np.eye(6)[0], name="rule_single_0"),
                 Distribution.degenerate(r.sr_is))
    assert v.status in {"PASS", "FAIL"}
    assert v.critical_value == pytest.approx(w.state.critical_value, rel=1e-12)


@pytest.mark.parametrize("kwargs,match", [
    ({"class_returns": None, "class_ids": None}, "needs class_returns"),
    ({"class_ids": None}, "needs class_returns"),
])
def test_an_explicit_class_without_its_streams_is_refused(kwargs, match):
    sb, _, cr, ids = _fixture()
    args = {"class_returns": cr, "class_ids": ids, **kwargs}
    with pytest.raises(ValueError, match=match):
        watch.open(sb, ExplicitClass(n_members=len(ids)), B=200, seed=0, **args)


def test_duplicate_ids_are_refused():
    sb, _, cr, ids = _fixture()
    bad = list(ids); bad[1] = bad[0]
    with pytest.raises(ValueError, match="must be unique"):
        _open(sb, cr, bad)


def test_a_declared_member_count_is_checked():
    sb, _, cr, ids = _fixture()
    with pytest.raises(ValueError, match="declares 99 members"):
        watch.open(sb, ExplicitClass(n_members=99), class_returns=cr, class_ids=ids,
                   B=200, seed=0, power_floor=0.0)


def test_streams_on_a_different_sample_are_refused():
    sb, _, cr, ids = _fixture()
    with pytest.raises(ValueError, match="periods"):
        _open(sb, cr[:-10], ids)


def test_a_sandbox_enforcing_a_weight_class_cannot_also_be_explicit():
    cfg = DGPConfig(M=10, T=400, T_oos=100, K=6, s=1, rho=0.0, sigma=1.0, seed=2)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year,
                 spec_class=SubsetClass(max_size=2))
    base = sb.base_feature_columns()
    with pytest.raises(ValueError, match="cannot also be an explicit"):
        watch.open(sb, ExplicitClass(n_members=2),
                   class_returns=base[:, :2], class_ids=["a", "b"], B=200, seed=0)


def test_class_streams_are_rejected_for_a_subset_class():
    sb, _, cr, ids = _fixture()
    with pytest.raises(ValueError, match="only meaningful for an ExplicitClass"):
        watch.open(sb, SubsetClass(max_size=2), class_returns=cr, class_ids=ids,
                   B=200, seed=0)


def test_non_finite_streams_are_refused():
    sb, _, cr, ids = _fixture()
    bad = cr.copy(); bad[0, 0] = np.nan
    with pytest.raises(ValueError, match="NaN or inf"):
        _open(sb, bad, ids)


def test_subset_classes_are_untouched_by_the_new_path():
    """Regression: the explicit branch must not change what a SubsetClass does."""
    cfg = DGPConfig(M=10, T=400, T_oos=100, K=6, s=1, rho=0.0, sigma=1.0, seed=5)
    cls = SubsetClass(max_size=2)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year, spec_class=cls)
    w = watch.open(sb, cls, B=200, seed=3, power_floor=0.0)
    assert w.state.class_size == cls.size(6)
    r = w.evaluate(Specification(weights=np.eye(6)[0], name="s0"))
    assert r.in_class
