"""The calibration anchor: a searcher that submits the class maximum.

`calibration-at-1pct` arm B could not answer its own question because both its
searchers submit well below the declared class maximum, which P2 predicts will
be conservative — so the measured conservatism said nothing about whether the
bootstrap tail is resolved. A searcher submitting the maximum itself is the
control that separates the two: its p-value is uniform if and only if the
bootstrap reproduces the null of that maximum.

These tests pin the two things that has to be true for that argument to hold:
the closed-form maximum really is the maximum, and the value the sandbox grades
is the same number.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden._full_class_engine import full_class_observed_max
from garden.spec_class import SubsetClass
from searchers.diagnostic import ExhaustiveClass
from searchers.scripted import Adaptive, Greedy


def brute_force_max(base, spec_class, annualization=1.0):
    """Enumerate the class and score every member directly. Only tractable at
    small K, which is why the closed form exists."""
    base = np.asarray(base, dtype=float)
    K = base.shape[1]
    best = -np.inf
    for m in range(1, min(spec_class.max_size, K) + 1):
        idx, signs = spec_class.members(K, m)
        for i in range(len(idx)):
            stream = (base[:, idx[i]] * signs[i]).sum(axis=1)
            best = max(best, float(stream.mean() / stream.std(ddof=1) * annualization))
    return best


@pytest.mark.parametrize("K,d,signed", [(8, 2, True), (8, 2, False),
                                        (10, 3, True), (6, 3, False)])
def test_closed_form_matches_brute_force(K, d, signed):
    base = np.random.default_rng(K * 10 + d).standard_normal((400, K)) * 0.01
    cls = SubsetClass(max_size=d, signed=signed)
    got, _, _, _ = full_class_observed_max(base, cls, annualization=np.sqrt(252))
    assert got == pytest.approx(brute_force_max(base, cls, np.sqrt(252)), rel=1e-12)


def test_the_returned_weights_are_the_argmax_and_lie_in_the_class():
    base = np.random.default_rng(7).standard_normal((400, 9)) * 0.01
    cls = SubsetClass(max_size=3, signed=True)
    best, w, _, _ = full_class_observed_max(base, cls, annualization=np.sqrt(252))
    assert cls.contains(w)
    stream = base @ w
    assert stream.mean() / stream.std(ddof=1) * np.sqrt(252) == pytest.approx(best, rel=1e-12)


def _sandbox(K=10, seed=3):
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    return generate(cfg), cfg


def test_the_sandbox_grades_the_submission_at_the_class_maximum():
    """A class member's return stream is a signed sum of base columns, so the
    portfolio Sharpe the sandbox computes and the closed form must agree. If
    they ever diverge the anchor is not anchoring anything."""
    data, cfg = _sandbox()
    cls = SubsetClass(max_size=3, signed=True)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    ExhaustiveClass(cls, seed=0).run(sb)

    _, dist = sb.submission
    expected, _, _, _ = full_class_observed_max(
        sb.base_feature_columns(), cls, annualization=np.sqrt(cfg.periods_per_year))
    assert float(dist.mean) == pytest.approx(expected, rel=1e-10)


def test_it_logs_one_evaluation_not_the_whole_class():
    data, cfg = _sandbox()
    cls = SubsetClass(max_size=3, signed=True)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    ExhaustiveClass(cls, seed=0).run(sb)
    assert sb.returns_matrix().shape[1] == 1


def test_no_other_searcher_beats_the_anchor():
    """P2, measured rather than assumed: Greedy and Adaptive submit at most the
    class maximum. This is the whole reason their p-values are conservative and
    the anchor's are not."""
    data, cfg = _sandbox()
    cls = SubsetClass(max_size=3, signed=True)
    ann = np.sqrt(cfg.periods_per_year)

    sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    ExhaustiveClass(cls, seed=0).run(sb)
    anchor = float(sb.submission[1].mean)

    for searcher in (Greedy(seed=0), Adaptive(max_features=3, seed=0)):
        s = Sandbox(data, periods_per_year=cfg.periods_per_year)
        searcher.run(s)
        assert float(s.submission[1].mean) <= anchor + 1e-12


def test_unsigned_searchers_fall_short_of_a_signed_bar():
    """Why arm B's conservatism is partly its own design: Greedy and Adaptive
    build weights with _one_hot_sum, which is unsigned, so they are confined to
    the unsigned sublattice while the bar is priced over the signed class."""
    data, cfg = _sandbox(K=10)
    ann = np.sqrt(cfg.periods_per_year)
    base = Sandbox(data, periods_per_year=cfg.periods_per_year).base_feature_columns()
    signed, _, _, _ = full_class_observed_max(base, SubsetClass(max_size=3, signed=True), ann)
    unsigned, _, _, _ = full_class_observed_max(base, SubsetClass(max_size=3, signed=False), ann)
    assert signed >= unsigned
    assert SubsetClass(max_size=3, signed=True).size(10) > SubsetClass(max_size=3, signed=False).size(10)


def test_the_observed_statistic_matches_the_replicate_statistic():
    """The confirmation the brute-force check did not give: the observed max and
    the replicate max must be the same function of a return stream, not merely
    both "a Sharpe". Feeding the null engine an identity resample must reproduce
    the observed path's variance exactly -- same ddof, same T/(T-1), same
    annualization, same guards."""
    from garden._full_class_engine import _quadratic
    rng = np.random.default_rng(11)
    T, K = 400, 6
    base = rng.standard_normal((T, K)) * 0.01
    cls = SubsetClass(max_size=2, signed=True)
    dm = base - base.mean(axis=0)
    full_second = np.atleast_2d(np.cov(dm, rowvar=False, ddof=1))[:, :, None]

    idx, signs = cls.members(K, 2)
    var_observed = _quadratic(full_second, idx, signs)[:, 0]

    W = np.full((T, 1), 1.0 / T)                       # the identity resample
    second = np.stack([(dm * W[:, [0]]).T @ dm], axis=2)
    num = np.einsum("nm,nmc->nc", signs, (dm.T @ W)[idx])
    var_replicate = np.maximum(
        (_quadratic(second, idx, signs) - num * num) * (T / (T - 1)), 0.0)[:, 0]

    np.testing.assert_allclose(var_observed, var_replicate, rtol=1e-12)
