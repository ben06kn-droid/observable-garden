import numpy as np
import pytest

from estimator.metrics import rmse, r_squared


def test_rmse_zero_for_perfect_prediction():
    actual = np.array([1.0, 2.0, 3.0])
    assert rmse(actual, actual) == pytest.approx(0.0)


def test_rmse_known_value():
    pred = np.array([0.0, 0.0])
    actual = np.array([3.0, 4.0])
    assert rmse(pred, actual) == pytest.approx(np.sqrt((9 + 16) / 2))


def test_r_squared_perfect_prediction_is_one():
    actual = np.array([1.0, 2.0, 3.0, 4.0])
    assert r_squared(actual, actual) == pytest.approx(1.0)


def test_r_squared_mean_prediction_is_zero():
    actual = np.array([1.0, 2.0, 3.0, 4.0])
    pred = np.full_like(actual, actual.mean())
    assert r_squared(pred, actual) == pytest.approx(0.0, abs=1e-9)


def test_r_squared_can_be_negative_for_bad_predictor():
    actual = np.array([1.0, 2.0, 3.0, 4.0])
    pred = np.array([10.0, -10.0, 10.0, -10.0])
    assert r_squared(pred, actual) < 0
