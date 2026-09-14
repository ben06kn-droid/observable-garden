"""Days 1-3 gate: the oracle's closed-form Sharpe must match a Monte Carlo
simulation of the same DGP. If these disagree, nothing built on top of the
oracle (deflation targets, decay curves) can be trusted."""
import numpy as np
import pytest

from environments.dgp import (
    DGPConfig, equicorrelation, generate, oracle_sharpe_analytic,
    oracle_sharpe_simulated, calibrate_sigma, true_signal_set, signal_variance,
)

T_SIM = 200_000  # smaller than the paper's 10^6 for fast test iteration
TOL = 0.03        # relative tolerance; Monte Carlo noise at T_SIM=2e5


@pytest.mark.parametrize("rho", [0.0, 0.3, 0.7])
@pytest.mark.parametrize("sigma", [1.0, 5.0])
def test_analytic_matches_simulated(rho, sigma):
    config = DGPConfig(M=200, K=60, s=3, rho=rho, sigma=sigma, seed=0)
    analytic = oracle_sharpe_analytic(config)
    simulated = oracle_sharpe_simulated(config, T_sim=T_SIM, use_cache=False)
    assert simulated == pytest.approx(analytic, rel=TOL), (
        f"analytic={analytic:.4f} simulated={simulated:.4f} rho={rho} sigma={sigma}"
    )


def test_fat_tails_same_variance_matches_analytic():
    # The closed form only uses E[eps]=0, E[eps^2]=sigma^2, independence from
    # the signal — it should hold under Student-t noise scaled to variance
    # sigma^2 just as well as under Gaussian noise.
    config = DGPConfig(M=200, K=60, s=3, rho=0.3, sigma=3.0, fat_tails=True, t_dof=5.0, seed=1)
    analytic = oracle_sharpe_analytic(config)
    simulated = oracle_sharpe_simulated(config, T_sim=T_SIM, use_cache=False)
    assert simulated == pytest.approx(analytic, rel=TOL)


def test_zero_correlation_reduces_to_sum_of_squares():
    config = DGPConfig(K=60, s=3, rho=0.0, seed=0)
    S, beta_full = true_signal_set(config)
    v_s = signal_variance(config, S, beta_full)
    assert v_s == pytest.approx(np.sum(config.beta_values() ** 2))


def test_calibrate_sigma_round_trips():
    config = DGPConfig(M=200, K=60, s=3, rho=0.2, seed=0)
    target = 1.5
    sigma = calibrate_sigma(target, config)
    calibrated_config = DGPConfig(**{**config.__dict__, "sigma": sigma})
    assert oracle_sharpe_analytic(calibrated_config) == pytest.approx(target, rel=1e-6)


def test_calibrate_sigma_infeasible_raises():
    config = DGPConfig(M=5, K=10, s=1, rho=0.0, seed=0)
    with pytest.raises(ValueError):
        calibrate_sigma(target_annual_sharpe=50.0, config=config)  # absurd target


def test_equicorrelation_psd_boundary():
    K = 10
    min_rho = -1.0 / (K - 1)
    Sigma = equicorrelation(K, min_rho)
    eigvals = np.linalg.eigvalsh(Sigma)
    assert eigvals.min() >= -1e-8
    with pytest.raises(ValueError):
        equicorrelation(K, min_rho - 0.01)


def test_generate_shapes_and_signal_set():
    config = DGPConfig(M=20, T=100, T_oos=50, K=15, s=3, seed=0)
    data = generate(config)
    assert data.x_in.shape == (100, 20, 15)
    assert data.r_in.shape == (100, 20)
    assert data.x_oos.shape == (50, 20, 15)
    assert data.r_oos.shape == (50, 20)
    assert data.S.shape == (3,)
    assert np.count_nonzero(data.beta_full) == 3
    assert set(data.S) == set(np.flatnonzero(data.beta_full))


def test_generate_is_deterministic_given_seed():
    config = DGPConfig(M=10, T=50, T_oos=20, K=10, s=2, seed=42)
    d1 = generate(config)
    d2 = generate(config)
    np.testing.assert_array_equal(d1.x_in, d2.x_in)
    np.testing.assert_array_equal(d1.r_in, d2.r_in)
    np.testing.assert_array_equal(d1.S, d2.S)
