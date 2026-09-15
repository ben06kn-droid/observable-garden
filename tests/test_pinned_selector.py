"""PinnedSelector exists to remove a confound found in
experiments/e10_power_vs_signal_strength.py: a real searcher's submitted
value improves with N, so a power-vs-N sweep with a real searcher measures
search benefit and multiple-testing cost tangled together. These tests
lock in the property that makes PinnedSelector a valid fix: for a FIXED
draw, its submitted Sharpe must not depend on N at all -- only the
transcript size around it should."""
import numpy as np
import pytest

from environments.dgp import DGPConfig, calibrate_sigma, generate
from environments.sandbox import Sandbox
from searchers.diagnostic import PinnedSelector


def make_data(target_sharpe=1.5, seed=7, K=20):
    template = DGPConfig(M=40, T=300, T_oos=100, K=K, s=3, rho=0.0, sigma=1.0, seed=seed, heterogeneous=True)
    sigma = calibrate_sigma(target_sharpe, template)
    config = DGPConfig(M=40, T=300, T_oos=100, K=K, s=3, rho=0.0, sigma=sigma, seed=seed, heterogeneous=True)
    return generate(config), config


def test_submitted_sharpe_is_exactly_N_invariant():
    data, config = make_data()
    pinned = np.zeros(config.K)
    pinned[data.S] = 1.0

    values = []
    for N in [5, 50, 200]:
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        PinnedSelector(pinned_weights=pinned, max_trials=N, seed=7).run(sandbox)
        _, dist = sandbox.submission
        values.append(dist.mean)

    assert values[0] == pytest.approx(values[1], rel=1e-9)
    assert values[1] == pytest.approx(values[2], rel=1e-9)


def test_transcript_size_still_grows_with_N():
    data, config = make_data()
    pinned = np.zeros(config.K)
    pinned[data.S] = 1.0

    sizes = []
    for N in [5, 50, 200]:
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        PinnedSelector(pinned_weights=pinned, max_trials=N, seed=7).run(sandbox)
        sizes.append(len(sandbox.transcript))

    assert sizes[0] < sizes[1] < sizes[2]
    assert sizes == [n + 1 for n in [5, 50, 200]]  # +1 for the pinned spec itself


def test_submitted_spec_is_exactly_the_pinned_weights():
    data, config = make_data()
    pinned = np.zeros(config.K)
    pinned[data.S] = 1.0

    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    PinnedSelector(pinned_weights=pinned, max_trials=50, seed=7).run(sandbox)
    spec, _ = sandbox.submission
    np.testing.assert_array_equal(spec.weights, pinned)
