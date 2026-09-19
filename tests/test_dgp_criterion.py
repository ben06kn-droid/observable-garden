import numpy as np
import pytest

from experiments.dgp_criterion_check import measurement_noise_floor, target_sd


def test_measurement_noise_floor_matches_known_value():
    # T_oos=300, periods_per_year=252 -> sqrt(252/300) ~ 0.9165, the ~0.917
    # figure referenced throughout SCOPE.md/README for the old grid.
    assert measurement_noise_floor(T_oos=300, periods_per_year=252) == pytest.approx(0.9165, abs=1e-3)


def test_measurement_noise_floor_shrinks_with_more_oos_data():
    small = measurement_noise_floor(T_oos=300)
    large = measurement_noise_floor(T_oos=3000)
    assert large < small
    assert large == pytest.approx(small / np.sqrt(10), rel=1e-9)


def test_target_sd_is_nonnegative_and_runs():
    sd = target_sd(n_draws=5, N=10, rho=0.3, heterogeneous=True, seed0=1)
    assert sd >= 0.0
