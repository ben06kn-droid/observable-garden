import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from experiments.e19c_feature_count import first_features
from searchers.dose_response import WinnerAnchor


def test_slice_gives_the_first_k_base_columns_of_the_full_draw():
    config = DGPConfig(M=20, T=200, T_oos=50, K=30, s=0, rho=0.3, sigma=1.0, seed=3)
    full = generate(config)
    whole = Sandbox(full, periods_per_year=config.periods_per_year).base_feature_columns()
    for K in (5, 12, 30):
        sliced = Sandbox(first_features(full, K), periods_per_year=config.periods_per_year)
        assert sliced.num_features == K
        np.testing.assert_array_equal(sliced.base_feature_columns(), whole[:, :K])


def test_search_on_a_slice_runs_and_replays():
    config = DGPConfig(M=20, T=200, T_oos=50, K=30, s=0, rho=0.3, sigma=1.0, seed=4)
    sandbox = Sandbox(first_features(generate(config), 10), periods_per_year=config.periods_per_year)
    searcher = WinnerAnchor(max_features=2, seed=4)
    searcher.run(sandbox)
    replayed = searcher.replay(sandbox.base_feature_columns(), annualization=np.sqrt(config.periods_per_year))
    assert replayed == pytest.approx(sandbox.submission[1].mean, rel=1e-6)


def test_slicing_refuses_draws_with_signal():
    config = DGPConfig(M=20, T=200, T_oos=50, K=30, s=3, rho=0.3, sigma=1.0, seed=5)
    with pytest.raises(ValueError):
        first_features(generate(config), 10)
