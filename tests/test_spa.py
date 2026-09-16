"""estimator/spa.py: Hansen (2005)'s test for superior predictive ability."""
import numpy as np
import pytest

from estimator.bootstrap import null_max_bootstrap
from estimator.spa import hansen_kappa, long_run_variance, spa_test


def test_kappa_matches_hansen_closed_form():
    n, q = 50, 0.2
    i = np.arange(1, n)
    expected = ((n - i) / n) * (1 - q) ** i + (i / n) * (1 - q) ** (n - i)
    np.testing.assert_allclose(hansen_kappa(n, q), expected)


def test_long_run_variance_recovers_white_noise_variance():
    # q = 1 kills every lag weight, so omega^2 collapses to the sample variance.
    R = np.random.default_rng(0).standard_normal((500, 4)) * np.array([1.0, 2.0, 0.5, 3.0])
    np.testing.assert_allclose(long_run_variance(R, q=1.0), R.var(axis=0), rtol=1e-10)


def test_long_run_variance_exceeds_sample_variance_under_persistence():
    rng = np.random.default_rng(1)
    e = rng.standard_normal(4000)
    ar = np.zeros(4000)
    for t in range(1, 4000):
        ar[t] = 0.7 * ar[t - 1] + e[t]
    lrv = long_run_variance(ar[:, None], q=1 / 20)[0]
    assert lrv > 2.0 * ar.var()  # positive autocorrelation inflates the long-run variance


def test_p_value_bracket_is_ordered():
    """Hansen's three recentering rules bracket the p-value: the lower rule
    drops hopeless candidates from the null maximum and so cannot be less
    significant than the least favourable configuration."""
    rng = np.random.default_rng(2)
    R = rng.standard_normal((300, 25)) - 0.05  # most candidates genuinely below zero
    R[:, 0] += 0.10
    out = spa_test(R, B=1500, block_length=1, seed=3)
    assert out.p_lower <= out.p_consistent <= out.p_upper


def test_upper_rule_is_the_reality_check_least_favourable_configuration():
    """g_u recenters every column at its own mean, which is exactly what the
    realized-menu bootstrap does. The two need not agree numerically (one
    studentizes with a fixed long-run sigma, the other re-estimates Sharpe per
    replicate), but on a well-behaved dense menu they should agree on the
    verdict at 5%."""
    rng = np.random.default_rng(4)
    R = rng.standard_normal((400, 30)) * 0.01
    out = spa_test(R, B=2000, block_length=1, seed=5)
    boot = null_max_bootstrap(R, B=2000, block_length=1, seed=5)
    sr = R.mean(axis=0) / R.std(axis=0, ddof=1)
    rc_p = (1 + np.sum(boot.M_b >= sr.max())) / (boot.B + 1)
    assert (out.p_upper < 0.05) == (rc_p < 0.05)


def test_hopeless_candidates_cost_the_reality_check_power_but_not_spa():
    """SCOPE.md §6's question. Padding a menu with candidates far below the
    benchmark inflates White's null maximum; Hansen's recentering excludes
    them, so the SPA p-value should move much less."""
    rng = np.random.default_rng(6)
    T = 500
    # A borderline edge, t ~ 2: strong enough to reject alone, weak enough that
    # padding can push it back over 5%. A large edge pins every p-value at 0 and
    # the comparison measures nothing.
    real = rng.standard_normal((T, 1)) * 0.01 + 0.001
    # Below Hansen's threshold -sqrt((omega^2/n) 2 log log n) ~ -0.00086 here, so
    # the consistent rule drops them; White still recenters them at their own
    # means and lets 100 extra zero-mean candidates raise his null maximum.
    padding = rng.standard_normal((T, 100)) * 0.01 - 0.003

    tight = spa_test(real, B=4000, block_length=1, seed=7)
    padded = spa_test(np.hstack([real, padding]), B=4000, block_length=1, seed=7)
    assert padded.p_consistent - tight.p_consistent < 0.05
    # the least favourable rule pays the full price for the same padding
    assert padded.p_upper - tight.p_upper > padded.p_consistent - tight.p_consistent
    assert padded.n_recentered < padded.N  # padding really was excluded


def test_fixed_studentization_survives_a_sparse_menu():
    """SCOPE.md §11. A rule that rarely trades can drive the Reality Check's
    re-estimated Sharpe denominator toward zero inside a resample. SPA's
    denominator is computed once from the full sample, so no replicate can
    collapse it: every bootstrap statistic stays finite."""
    rng = np.random.default_rng(8)
    T = 400
    dense = rng.standard_normal((T, 5)) * 0.01
    sparse = np.zeros((T, 3))
    active = rng.choice(T, size=6, replace=False)  # trades on 6 of 400 days
    sparse[active, :] = rng.standard_normal((6, 3)) * 0.05

    out = spa_test(np.hstack([dense, sparse]), B=500, block_length=1, seed=9)
    assert np.isfinite(out.statistic)
    assert np.all(np.isfinite(out.omega))
    assert 0.0 <= out.p_consistent <= 1.0


def test_zero_variance_columns_are_dropped_not_divided_by():
    rng = np.random.default_rng(10)
    R = np.hstack([rng.standard_normal((200, 4)) * 0.01, np.zeros((200, 2))])
    out = spa_test(R, B=300, block_length=1, seed=11)
    assert np.isfinite(out.statistic)
    assert np.all(np.isneginf(out.t_stats[-2:]))


def test_all_dead_columns_raise():
    with pytest.raises(ValueError, match="zero long-run variance"):
        spa_test(np.zeros((100, 3)), B=50, block_length=1, seed=12)


def test_detects_a_real_edge():
    rng = np.random.default_rng(13)
    R = rng.standard_normal((500, 20)) * 0.01
    R[:, 7] += 0.004  # Sharpe ~0.4 per period
    out = spa_test(R, B=1500, block_length=1, seed=14)
    assert out.p_consistent < 0.05
    assert int(np.argmax(out.t_stats)) == 7


def test_pure_null_is_not_liberal():
    """Type-I at 5% across independent null menus. Not a calibration
    experiment (that is E-series work); a guard that the test is not wildly
    anti-conservative."""
    rejects = 0
    trials = 120
    for s in range(trials):
        rng = np.random.default_rng(1000 + s)
        R = rng.standard_normal((250, 15)) * 0.01
        if spa_test(R, B=400, block_length=1, seed=s).p_consistent < 0.05:
            rejects += 1
    assert rejects / trials < 0.16  # generous; catches a broken null, not fine calibration
