"""estimator/full_class.py: the enumerated class for the full-class null."""
import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap
from estimator.full_class import full_class_matrix
from searchers.dose_response import WinnerAnchor
from searchers.scripted import Adaptive


def test_class_sizes():
    base = np.random.default_rng(0).standard_normal((100, 20))
    assert full_class_matrix(base, 2).shape == (100, 210)
    assert full_class_matrix(base, 3).shape == (100, 1350)


def test_class_contains_every_column_an_adaptive_search_logs():
    for searcher in (Adaptive(max_features=3, seed=2), WinnerAnchor(max_features=2, seed=2)):
        config = DGPConfig(M=30, T=200, T_oos=50, K=10, s=0, rho=0.3, sigma=1.0, seed=2)
        sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
        searcher.run(sandbox)
        logged = sandbox.returns_matrix()
        cls = full_class_matrix(sandbox.base_feature_columns(), 3)
        for j in range(logged.shape[1]):
            assert np.min(np.max(np.abs(cls - logged[:, [j]]), axis=0)) < 1e-10


def test_duplicate_columns_leave_the_null_maximum_unchanged():
    base = np.random.default_rng(3).standard_normal((300, 8))
    cls = full_class_matrix(base, 2)
    once = null_max_bootstrap(cls, B=200, block_length=1, seed=4).M_b
    twice = null_max_bootstrap(np.concatenate([cls, cls], axis=1), B=200, block_length=1, seed=4).M_b
    np.testing.assert_array_equal(once, twice)
