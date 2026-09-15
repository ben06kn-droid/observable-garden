"""analytic_sharpe generalizes oracle_sharpe_analytic to arbitrary weight
vectors, removing OOS measurement noise from Experiment 2's target. Checked
three ways: (1) reduces exactly to the oracle formula at weights=beta_full,
(2) matches direct simulation for oracle / partial-true / pure-noise
weights, (3) heterogeneous_correlation is a valid correlation matrix with
the properties its docstring claims."""
import numpy as np
import pytest

from environments.dgp import (
    DGPConfig, analytic_sharpe, calibrate_sigma, equicorrelation,
    generate, get_sigma_x, heterogeneous_correlation, oracle_sharpe_analytic,
    true_signal_set,
)


def _simulate_sharpe(config: DGPConfig, weights: np.ndarray, T_sim: int = 200_000, seed: int = 999) -> float:
    """Independent from analytic_sharpe's derivation: brute-force MC over
    the full K-dim feature draw, not the S-restricted shortcut
    oracle_sharpe_simulated uses, so it validates arbitrary weight
    vectors including ones with mass outside S."""
    rng = np.random.default_rng(seed)
    Sigma_x = get_sigma_x(config)
    L = np.linalg.cholesky(Sigma_x)
    beta_full = true_signal_set(config)[1]
    weights = np.asarray(weights, dtype=float)

    total, total_sq, n = 0.0, 0.0, 0
    chunk = 20_000
    remaining = T_sim
    while remaining > 0:
        b = min(chunk, remaining)
        z = rng.standard_normal((b, config.M, config.K))
        x = z @ L.T
        signal = x @ weights
        r = x @ beta_full + rng.normal(0.0, config.sigma, size=(b, config.M))
        R_t = (signal * r).mean(axis=1)
        total += R_t.sum()
        total_sq += (R_t ** 2).sum()
        n += b
        remaining -= b

    mean, var = total / n, total_sq / n - (total / n) ** 2
    sr_period = mean / np.sqrt(var)
    return float(sr_period * np.sqrt(config.periods_per_year))


@pytest.fixture
def config():
    template = DGPConfig(M=60, T=100, T_oos=100, K=15, s=3, rho=0.4, sigma=1.0, seed=42)
    sigma = calibrate_sigma(1.0, template)
    return DGPConfig(M=60, T=100, T_oos=100, K=15, s=3, rho=0.4, sigma=sigma, seed=42)


def test_reduces_exactly_to_oracle_formula(config):
    beta_full = true_signal_set(config)[1]
    assert analytic_sharpe(config, beta_full) == pytest.approx(oracle_sharpe_analytic(config), rel=1e-10)


@pytest.mark.parametrize("case", ["oracle", "two_of_three_true", "one_true_two_noise", "pure_noise"])
def test_matches_simulation(config, case):
    # Tolerance derived, not guessed: per-period SR here is small (annual
    # SR~1 / sqrt(252) ~ 0.06), so Lo (2002)'s SE ~ sqrt(1+SR_period^2/2)/T_sim
    # for the PERIOD-level Sharpe must be scaled by sqrt(periods_per_year)
    # when comparing to the annualized figure -- omitting that scaling is
    # what made an earlier draft of this test fail on ordinary MC noise. A
    # ~3-SE band at T_sim=400k comes out to ~0.05; used directly below.
    S = true_signal_set(config)[0]
    K = config.K
    all_idx = set(range(K))
    noise_idx = sorted(all_idx - set(S.tolist()))

    if case == "oracle":
        support = S.tolist()
    elif case == "two_of_three_true":
        support = S.tolist()[:2]
    elif case == "one_true_two_noise":
        support = [S.tolist()[0]] + noise_idx[:2]
    else:  # pure_noise
        support = noise_idx[:3]

    weights = np.zeros(K)
    weights[support] = 1.0

    analytic = analytic_sharpe(config, weights)
    simulated = _simulate_sharpe(config, weights, T_sim=400_000, seed=999)
    assert analytic == pytest.approx(simulated, abs=0.05), f"{case}: analytic={analytic:.4f} simulated={simulated:.4f}"


def test_heterogeneous_correlation_is_valid_correlation_matrix():
    K = 20
    Sigma = heterogeneous_correlation(K, rho=0.5, seed=1)
    np.testing.assert_allclose(np.diag(Sigma), 1.0)
    np.testing.assert_allclose(Sigma, Sigma.T)
    eigvals = np.linalg.eigvalsh(Sigma)
    assert eigvals.min() >= -1e-8  # PSD


def test_heterogeneous_correlation_is_actually_heterogeneous():
    K = 20
    Sigma = heterogeneous_correlation(K, rho=0.5, seed=1)
    offdiag = Sigma[~np.eye(K, dtype=bool)]
    assert offdiag.std() > 0.01  # not a constant, unlike equicorrelation
    assert offdiag.mean() == pytest.approx(0.5, abs=0.15)  # rho still means ~average correlation


def test_heterogeneous_correlation_rho_zero_is_identity():
    Sigma = heterogeneous_correlation(20, rho=0.0, seed=1)
    np.testing.assert_array_equal(Sigma, np.eye(20))


def test_get_sigma_x_dispatches_on_config_flag():
    config_eq = DGPConfig(K=10, rho=0.3, heterogeneous=False, seed=1)
    config_het = DGPConfig(K=10, rho=0.3, heterogeneous=True, seed=1)
    np.testing.assert_array_equal(get_sigma_x(config_eq), equicorrelation(10, 0.3))
    het = get_sigma_x(config_het)
    assert not np.allclose(het, equicorrelation(10, 0.3))


def test_heterogeneous_generate_still_runs_end_to_end():
    config = DGPConfig(M=20, T=50, T_oos=20, K=10, s=2, rho=0.5, sigma=1.0, seed=3, heterogeneous=True)
    data = generate(config)
    assert data.x_in.shape == (50, 20, 10)
    assert np.all(np.isfinite(data.r_in))
