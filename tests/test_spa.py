"""estimator/spa.py: Hansen (2005)'s test for superior predictive ability."""
import numpy as np
import pytest

from estimator.bootstrap import null_max_bootstrap
from estimator.spa import consistent_keep_mask, hansen_kappa, long_run_variance, spa_test


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
    realized-menu bootstrap does: it is Hansen's mu_hat^u = 0 least favourable
    configuration.

    A note on what this can and cannot assert. The build plan expected SPA-upper
    to *reproduce* null_max_bootstrap's p-value exactly, as a free correctness
    test. It cannot: the two share a recentering but not a statistic. The
    Reality Check here maximises a Sharpe whose denominator is re-estimated
    inside every replicate; SPA-upper maximises a mean studentized by a single
    fixed long-run sigma. They coincide in role, not in arithmetic. Agreement on
    the verdict at 5% over a well-behaved dense menu is the honest version, and
    that difference in denominators is the entire point of SPA for SCOPE.md §11."""
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


def test_hansens_two_threshold_forms_agree():
    """Hansen states the consistent rule studentized in §2.1 and raw in §3.1.
    They are the same rule; this pins the scaling so a stray sqrt(n) or omega
    cannot drift the threshold unnoticed."""
    rng = np.random.default_rng(20)
    for n in (50, 250, 1000):
        dbar = rng.standard_normal(200) * 0.01
        omega = np.abs(rng.standard_normal(200)) * 0.02 + 0.001
        np.testing.assert_array_equal(
            consistent_keep_mask(dbar, omega, n, form="studentized"),
            consistent_keep_mask(dbar, omega, n, form="raw"),
        )


def test_p_value_and_critical_value_agree():
    """garden/power.py guarantees p < alpha and sr > c never disagree at the
    boundary, by building both from the same float expression. SPA inlines
    those functions (estimator cannot import garden without inverting the
    dependency), so this pins the two implementations together."""
    rng = np.random.default_rng(30)
    for trial in range(25):
        R = rng.standard_normal((200, 12)) * 0.01 + rng.uniform(-0.002, 0.002)
        out = spa_test(R, B=400, block_length=1, seed=trial, alpha=0.05)
        for p, c in ((out.p_lower, out.critical_lower),
                     (out.p_consistent, out.critical_consistent),
                     (out.p_upper, out.critical_upper)):
            assert (p < out.alpha) == (out.statistic > c)


def test_inlined_p_value_matches_gardens():
    """The inlined expressions must equal garden.power's, or the comment
    claiming they are character-identical is a lie."""
    from garden.power import bootstrap_p_value, critical_value
    from estimator.spa import _critical_value, _p_value

    rng = np.random.default_rng(31)
    null = rng.standard_normal(500)
    for stat in (-1.0, 0.0, 0.3, 1.0, 2.5):
        assert _p_value(null, stat) == bootstrap_p_value(null, stat)
    for alpha in (0.01, 0.05, 0.10):
        assert _critical_value(null, alpha) == critical_value(null, alpha)


def test_submitted_spec_is_tested_not_the_menu_best():
    """Task: judge the spec actually submitted. The null is the menu maximum
    either way, so naming a sub-maximal submission can only raise the p-value."""
    rng = np.random.default_rng(32)
    R = rng.standard_normal((400, 20)) * 0.01
    R[:, 3] += 0.004          # the menu's best
    R[:, 11] += 0.001         # a weaker spec, the one "submitted"

    best = spa_test(R, B=1500, block_length=1, seed=33)
    sub = spa_test(R, B=1500, block_length=1, seed=33, submitted=11)

    assert best.submitted is None and sub.submitted == 11
    assert int(np.argmax(best.t_stats)) == 3
    # Same null, lower statistic -> weakly larger p-value.
    assert sub.statistic < best.statistic
    assert sub.p_consistent > best.p_consistent
    # The null itself must not have moved: identical critical values.
    assert sub.critical_consistent == pytest.approx(best.critical_consistent, rel=1e-12)


def test_submitting_the_best_matches_the_default():
    """Naming the argmax explicitly must reproduce the default exactly."""
    rng = np.random.default_rng(34)
    R = rng.standard_normal((300, 10)) * 0.01
    R[:, 6] += 0.003
    default = spa_test(R, B=600, block_length=1, seed=35)
    best = int(np.argmax(default.t_stats))
    named = spa_test(R, B=600, block_length=1, seed=35, submitted=best)
    assert named.statistic == pytest.approx(default.statistic, rel=1e-12)
    assert named.p_consistent == pytest.approx(default.p_consistent, rel=1e-12)
    assert named.critical_consistent == pytest.approx(default.critical_consistent, rel=1e-12)


def test_block_length_is_taken_from_the_caller():
    rng = np.random.default_rng(36)
    R = rng.standard_normal((300, 8)) * 0.01
    assert spa_test(R, B=200, block_length=7, seed=37).block_length == 7
    # Default must match the repo-wide convention: chosen on the demeaned matrix.
    from estimator.bootstrap import select_block_length
    expected = select_block_length(R - R.mean(axis=0))
    assert spa_test(R, B=200, seed=37).block_length == expected


def test_submitted_index_out_of_range_raises():
    R = np.random.default_rng(38).standard_normal((100, 4)) * 0.01
    with pytest.raises(ValueError, match="out of range"):
        spa_test(R, B=50, block_length=1, seed=39, submitted=4)


def test_duplicate_invariance():
    """estimator_build_spec.md §6 test 4, carried over to SPA: duplicating every
    column adds no information, and joint row resampling means both copies take
    identical values in every replicate. Under g_c the duplicate also inherits
    the same omega_k and so the same recentering decision, so the property holds
    by construction -- which makes this a real regression test, not a formality."""
    T, N = 1000, 20
    rng = np.random.default_rng(21)
    R = rng.standard_normal((T, N)) * 0.01
    R_dup = np.concatenate([R, R], axis=1)

    once = spa_test(R, B=800, block_length=1, seed=22)
    twice = spa_test(R_dup, B=800, block_length=1, seed=22)

    assert twice.statistic == pytest.approx(once.statistic, rel=1e-12)
    assert twice.p_consistent == pytest.approx(once.p_consistent, abs=0.02)
    assert twice.p_upper == pytest.approx(once.p_upper, abs=0.02)


def test_duplicate_invariance_with_correlated_base_trials():
    """The harder version of the same test: base trials share a latent factor
    before duplication, mirroring test_bootstrap.py's second duplicate test."""
    T, N = 1000, 15
    rng = np.random.default_rng(23)
    factor = rng.standard_normal(T)
    R = 0.6 * factor[:, None] + 0.8 * rng.standard_normal((T, N))
    R_dup = np.concatenate([R, R], axis=1)

    once = spa_test(R, B=800, block_length=1, seed=24)
    twice = spa_test(R_dup, B=800, block_length=1, seed=24)
    assert twice.statistic == pytest.approx(once.statistic, rel=1e-12)
    assert twice.p_consistent == pytest.approx(once.p_consistent, abs=0.03)


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
