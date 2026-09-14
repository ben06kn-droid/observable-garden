import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.metrics import wilson_ci, type1_rate, ks_critical_value
from estimator.procedure_level_bootstrap import circular_shift_nullify, procedure_level_bootstrap
from searchers.diagnostic import LatticeAdaptive
from searchers.scripted import Adaptive


def test_circular_shift_preserves_x_changes_r():
    config = DGPConfig(M=20, T=50, T_oos=20, K=8, s=0, rho=0.2, sigma=1.0, seed=1)
    data = generate(config)
    nullified = circular_shift_nullify(data, shift=5)

    np.testing.assert_array_equal(nullified.x_in, data.x_in)
    np.testing.assert_array_equal(nullified.r_in, np.roll(data.r_in, 5, axis=0))
    assert not np.array_equal(nullified.r_in, data.r_in)
    # circular shift preserves the multiset of values exactly
    np.testing.assert_allclose(np.sort(nullified.r_in, axis=0), np.sort(data.r_in, axis=0))


def test_procedure_level_bootstrap_runs_and_returns_B_values():
    config = DGPConfig(M=20, T=100, T_oos=30, K=8, s=0, rho=0.2, sigma=1.0, seed=2)
    data = generate(config)
    M_b = procedure_level_bootstrap(
        data, lambda: Adaptive(max_features=3, seed=2), B=15, periods_per_year=config.periods_per_year, seed=1,
    )
    assert M_b.shape == (15,)
    assert np.all(np.isfinite(M_b))


def test_lattice_adaptive_evaluates_full_lattice():
    from math import comb
    config = DGPConfig(M=20, T=100, T_oos=30, K=8, s=0, rho=0.2, sigma=1.0, seed=3)
    data = generate(config)
    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    LatticeAdaptive(max_features=3, seed=3).run(sandbox)
    expected = comb(8, 1) + comb(8, 2) + comb(8, 3)
    assert len(sandbox.transcript) == expected
    assert sandbox.submission is not None


def test_lattice_adaptive_replay_matches_run():
    config = DGPConfig(M=20, T=100, T_oos=30, K=8, s=0, rho=0.2, sigma=1.0, seed=4)
    data = generate(config)
    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    searcher = LatticeAdaptive(max_features=3, seed=4)
    searcher.run(sandbox)
    _, dist = sandbox.submission

    replayed = searcher.replay(sandbox.base_feature_columns(), annualization=np.sqrt(config.periods_per_year))
    assert replayed == pytest.approx(dist.mean, rel=1e-6)


def test_wilson_ci_contains_point_estimate_and_widens_at_boundary():
    lo, hi = wilson_ci(successes=10, n=200, confidence=0.95)
    assert lo < 10 / 200 < hi
    lo0, hi0 = wilson_ci(successes=0, n=200, confidence=0.95)
    assert lo0 == pytest.approx(0.0, abs=1e-9)
    assert hi0 > 0


def test_type1_rate_reports_rate_and_ci():
    rng = np.random.default_rng(0)
    p_values = rng.uniform(size=500)  # well-calibrated by construction
    rate, lo, hi = type1_rate(p_values, alpha=0.05)
    assert lo <= rate <= hi
    assert lo < 0.10  # should be consistent with the nominal 0.05


def test_ks_critical_value_matches_known_scale():
    # asymptotic critical value ~ 1.36/sqrt(n) at alpha=0.05
    assert ks_critical_value(200, alpha=0.05) == pytest.approx(1.36 / np.sqrt(200), rel=1e-6)
