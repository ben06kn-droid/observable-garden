"""The size integral's quadrature against closed forms and against P4' (no data)."""
import numpy as np
import pytest
from scipy.stats import norm

from experiments import size_integral as S


def test_at_K_1_the_process_and_menu_nulls_are_the_normal_cdf():
    for x in (-0.5, 0.7, 1.9):
        assert S.F_P(x, 1, 0.0) == pytest.approx(norm.cdf(x), abs=2e-5)
        assert S.F_C(x, 1, 0.3) == pytest.approx(norm.cdf(x), abs=2e-5)


def test_the_direct_menu_null_equals_the_rank_mixture_p4_prime():
    for K, w, x in ((5, 0.0, 2.0), (6, 0.3, 1.8)):
        assert S.F_C(x, K, w) == pytest.approx(S.rank_mixture(x, K, w), abs=5e-5)


def test_the_winner_null_lies_below_the_menu_null_so_winner_anchoring_is_liberal():
    for K, w in ((10, 0.0), (10, 0.3)):
        x = 2.5
        assert S.F_P(x, K, w) < S.F_C(x, K, w)


def test_against_monte_carlo_at_a_small_cell():
    rng = np.random.default_rng(0)
    K, w, n = 8, 0.3, 400_000
    Z = np.sqrt(w) * rng.standard_normal((n, 1)) + np.sqrt(1 - w) * rng.standard_normal((n, K))
    S_ = -np.sort(-Z, axis=1)
    mp = np.maximum(S_[:, 0], (S_[:, 0] + S_[:, 1]) / np.sqrt(2 + 2 * w))
    x = 2.2
    assert S.F_P(x, K, w) == pytest.approx(np.mean(mp <= x), abs=0.003)
