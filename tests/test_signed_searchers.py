"""Signed Greedy and Adaptive: 7.0 needs each scripted arm priced against a
class its searcher can actually reach.

`calibration-at-1pct` arm B could not be read because `Greedy` and `Adaptive`
build weights with `_one_hot_sum`, confining them to the 10,700-member unsigned
sublattice while the bar was priced over the 82,240-member signed class. Their
conservatism measured that confinement, not the bootstrap. These tests pin the
two properties that make the signed variants usable as a matched arm: they reach
the signed class, and `run` and `replay` implement one decision rule.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from searchers.scripted import Adaptive, Greedy, SignedAdaptive, SignedGreedy


def _sandbox(K=10, seed=3, spec_class=None):
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=K, s=2, rho=0.0, sigma=1.0, seed=seed)
    return Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year,
                   spec_class=spec_class), cfg


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_signed_greedy_reaches_the_largest_absolute_single_feature_sharpe(seed):
    sb, cfg = _sandbox(seed=seed)
    SignedGreedy(seed=0).run(sb)
    got = float(sb.submission[1].mean)

    base = sb.base_feature_columns()
    ann = np.sqrt(cfg.periods_per_year)
    want = max(float(np.max(base.mean(axis=0) / base.std(axis=0, ddof=1) * ann)),
               float(np.max(-base.mean(axis=0) / base.std(axis=0, ddof=1) * ann)))
    assert got == pytest.approx(want, rel=1e-12)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_signed_searchers_never_come_in_below_their_unsigned_counterparts(seed):
    """The sublattice is contained in the signed class, so a signed search that
    is otherwise the same rule cannot do worse. This is the property that makes
    the confinement argument in arm B's deviation concrete."""
    for signed_cls, plain_cls in ((SignedGreedy, Greedy), (SignedAdaptive, Adaptive)):
        a, _ = _sandbox(seed=seed)
        signed_cls(seed=0).run(a)
        b, _ = _sandbox(seed=seed)
        plain_cls(seed=0).run(b)
        assert float(a.submission[1].mean) >= float(b.submission[1].mean) - 1e-12


@pytest.mark.parametrize("d", [1, 2, 3])
def test_signed_adaptive_submits_inside_the_signed_class_of_its_own_depth(d):
    cls = SubsetClass(max_size=d, signed=True)
    sb, _ = _sandbox(K=8, spec_class=cls)
    SignedAdaptive(max_features=d, seed=0).run(sb)
    w, _ = sb.submission
    assert cls.contains(w.weights)
    assert set(np.unique(w.weights[w.weights != 0])) <= {1.0, -1.0}
    assert int(np.count_nonzero(w.weights)) <= d


def test_unsigned_searchers_stay_in_the_sublattice():
    """The other half of the matching argument: the plain searchers really are
    confined, so pricing them against a signed bar measures the confinement."""
    cls = SubsetClass(max_size=3, signed=False)
    for searcher in (Greedy(seed=0), Adaptive(max_features=3, seed=0)):
        sb, _ = _sandbox(K=8, spec_class=cls)
        searcher.run(sb)
        w, _ = sb.submission
        assert cls.contains(w.weights)
        assert set(np.unique(w.weights[w.weights != 0])) <= {1.0}


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4, 5])
def test_run_and_replay_are_the_same_decision_rule(seed):
    """`replay` is what recursive_bootstrap.py resamples through. If it and
    `run` ever disagree, the recursive tier is silently estimating a different
    searcher's null."""
    for cls, kwargs in ((SignedGreedy, {}), (SignedAdaptive, {"max_features": 3})):
        sb, cfg = _sandbox(seed=seed)
        s = cls(seed=0, **kwargs)
        s.run(sb)
        replayed = s.replay(sb.base_feature_columns(),
                            annualization=np.sqrt(cfg.periods_per_year))
        assert replayed == pytest.approx(float(sb.submission[1].mean), rel=1e-12)


def test_signed_greedy_costs_exactly_two_evaluations_per_feature():
    sb, _ = _sandbox(K=7)
    SignedGreedy(seed=0).run(sb)
    assert sb.returns_matrix().shape[1] == 2 * 7


def test_signed_adaptive_stops_when_an_extension_does_not_help():
    """Forward selection keeps an addition only if it improves, so depth is data
    dependent and bounded by max_features -- not always equal to it."""
    sb, _ = _sandbox(K=8)
    SignedAdaptive(max_features=4, seed=0).run(sb)
    w, _ = sb.submission
    assert 1 <= int(np.count_nonzero(w.weights)) <= 4


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_signed_adaptive_beam_names_the_strongest_feature_either_sign(seed):
    sb, cfg = _sandbox(seed=seed)
    base = sb.base_feature_columns()
    ann = np.sqrt(cfg.periods_per_year)
    beam = SignedAdaptive(max_features=3, seed=0).round1_beam(base, annualization=ann)
    sr = np.abs(base.mean(axis=0) / base.std(axis=0, ddof=1) * ann)
    assert beam == frozenset({int(np.argmax(sr))})
