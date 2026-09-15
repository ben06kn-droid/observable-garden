"""Days 4-6 gate (spec §6, tests 2-4), plus test 5 since block-length
selection is already built. Test 1 (uniformity under the null) needs the
scripted searchers and lands with days 7-9."""
import numpy as np
import pytest

from estimator.bootstrap import (
    null_max_bootstrap, deflate, sharpe, stationary_bootstrap_indices, select_block_length,
)
from estimator.deflated_sharpe import deflate_closed_form, expected_max_sharpe_dsr, effective_N

B_FAST = 3000  # smaller than the 10,000 default for fast test iteration


def iid_null_returns(T, N, seed):
    rng = np.random.default_rng(seed)
    return rng.standard_normal((T, N))


# -- Test 2: independent-trial agreement ------------------------------------

def test_independent_trials_bootstrap_matches_closed_form():
    T, N = 1000, 100
    R = iid_null_returns(T, N, seed=0)

    boot = null_max_bootstrap(R, B=B_FAST, block_length=1, seed=1)  # truly iid -> L=1 is correct
    trial_sr = sharpe(R, axis=0)
    var_sr = float(np.var(trial_sr, ddof=1))
    sr_0_closed_form = expected_max_sharpe_dsr(N, var_sr)

    assert boot.mean_null_max == pytest.approx(sr_0_closed_form, rel=0.2)


def test_auto_block_length_recovers_near_one_for_iid_data():
    R = iid_null_returns(2000, 20, seed=2)
    L = select_block_length(R)
    assert L <= 3  # should not find spurious long-range dependence in white noise


# -- Test 3: degenerate search -----------------------------------------------

def test_degenerate_search_n1_deflation_near_zero():
    T = 1000
    R = iid_null_returns(T, 1, seed=3)
    result = deflate(R, B=B_FAST, seed=4)
    tol = 5.0 / np.sqrt(T)
    assert abs(result.mean_null_max) < tol, result.mean_null_max


# -- Test 4: duplicate invariance (the thesis) -------------------------------

def test_duplicate_invariance_bootstrap_stable_closed_form_moves():
    T, N = 1000, 20
    R = iid_null_returns(T, N, seed=5)
    R_dup = np.concatenate([R, R], axis=1)  # 2N columns, exact duplicate pairs
    assert R_dup.shape[1] == 2 * N

    boot_orig = null_max_bootstrap(R, B=B_FAST, seed=6)
    boot_dup = null_max_bootstrap(R_dup, B=B_FAST, seed=6)  # same seed -> same time-index draws

    # The bootstrap must not move: duplicating a trial adds no new information,
    # and joint row resampling means both copies always take identical values.
    assert boot_dup.mean_null_max == pytest.approx(boot_orig.mean_null_max, rel=0.05)

    # The naive closed form (raw trial count) DOES move: it thinks the search
    # doubled in breadth.
    dsr_orig = deflate_closed_form(R, N_mode="raw")
    dsr_dup = deflate_closed_form(R_dup, N_mode="raw")
    assert dsr_dup.sr_0 > dsr_orig.sr_0 * 1.05

    # The eigenvalue-based effective-N correction recovers the true breadth.
    assert effective_N(R_dup) == pytest.approx(effective_N(R), rel=0.1)
    assert effective_N(R_dup) < 1.5 * N  # nowhere near the naive 2N


def test_duplicate_invariance_holds_for_correlated_base_trials():
    # A harder version: base trials are themselves correlated (not iid), via
    # a shared latent factor, before duplication -- still must hold.
    T, N = 1000, 15
    rng = np.random.default_rng(7)
    factor = rng.standard_normal(T)
    R = 0.6 * factor[:, None] + 0.8 * rng.standard_normal((T, N))
    R_dup = np.concatenate([R, R], axis=1)

    boot_orig = null_max_bootstrap(R, B=B_FAST, seed=8)
    boot_dup = null_max_bootstrap(R_dup, B=B_FAST, seed=8)
    assert boot_dup.mean_null_max == pytest.approx(boot_orig.mean_null_max, rel=0.08)


# -- Test 5: block-length sanity ---------------------------------------------

def test_iid_bootstrap_underdeflates_relative_to_auto_block_length():
    T = 2000
    rng = np.random.default_rng(9)
    phi = 0.8
    eps = rng.standard_normal(T)
    x = np.empty(T)
    x[0] = eps[0]
    for t in range(1, T):
        x[t] = phi * x[t - 1] + eps[t]
    R = x[:, None]  # single strongly autocorrelated series

    L_auto = select_block_length(R)
    assert L_auto > 1  # must detect the dependence

    boot_iid = null_max_bootstrap(R, B=B_FAST, block_length=1, seed=10)
    boot_auto = null_max_bootstrap(R, B=B_FAST, block_length=L_auto, seed=10)

    assert boot_iid.mean_null_max < boot_auto.mean_null_max


# -- stationary_bootstrap_indices sanity -------------------------------------

def test_stationary_bootstrap_indices_valid_range_and_length():
    rng = np.random.default_rng(11)
    idx = stationary_bootstrap_indices(T=500, L=10, rng=rng)
    assert idx.shape == (500,)
    assert idx.min() >= 0 and idx.max() < 500


# -- regression: block length with columns that never trade -------------------

def test_block_length_selection_skips_columns_that_never_trade():
    rng = np.random.default_rng(12)
    R = rng.standard_normal((500, 6))
    R[:, 2] = 0.0  # Politis-White is undefined for a constant column and used to crash the median
    assert select_block_length(R) == select_block_length(np.delete(R, 2, axis=1))
    assert select_block_length(np.zeros((100, 3))) == 1


def test_vectorized_stationary_bootstrap_matches_the_reference_sampler():
    from estimator.bootstrap import stationary_bootstrap_index_matrix

    T, L, n = 400, 8, 3000
    ref = np.stack([stationary_bootstrap_indices(T, L, np.random.default_rng(i)) for i in range(n)])
    vec = stationary_bootstrap_index_matrix(T, L, n, np.random.default_rng(99))
    assert vec.shape == (n, T) and vec.min() >= 0 and vec.max() < T

    def continuation(idx):
        return np.mean(idx[:, 1:] == (idx[:, :-1] + 1) % T)

    expected = (1 - 1 / L) + (1 / L) / T  # continue the block, or restart exactly one step ahead
    assert continuation(vec) == pytest.approx(expected, abs=0.005)
    assert continuation(vec) == pytest.approx(continuation(ref), abs=0.005)
    marginal = np.bincount(vec.ravel(), minlength=T) * T / vec.size
    assert np.abs(marginal - 1).max() < 0.35
    assert stationary_bootstrap_index_matrix(T, 1, 5, np.random.default_rng(0)).shape == (5, T)
