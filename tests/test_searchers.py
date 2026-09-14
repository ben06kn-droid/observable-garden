import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from searchers.scripted import Honest, Greedy, GridSearch, Adaptive


def make_sandbox(K=15, s=0, seed=0):
    config = DGPConfig(M=50, T=300, T_oos=100, K=K, s=s, rho=0.2, sigma=1.0, seed=seed)
    data = generate(config)
    return Sandbox(data, periods_per_year=config.periods_per_year), config


@pytest.mark.parametrize("searcher_cls,expected_max_n", [
    (Honest, 1),
    (Greedy, 15),
])
def test_trial_count_exact(searcher_cls, expected_max_n):
    sandbox, config = make_sandbox()
    searcher_cls(seed=0).run(sandbox)
    assert len(sandbox.transcript) == expected_max_n
    assert sandbox.submission is not None


def test_gridsearch_respects_max_trials_cap():
    sandbox, config = make_sandbox(K=15)
    GridSearch(subset_sizes=(1, 2, 3), max_trials=100, seed=0).run(sandbox)
    assert len(sandbox.transcript) == 100
    assert sandbox.submission is not None


def test_gridsearch_uncapped_matches_combinatorial_count():
    sandbox, config = make_sandbox(K=8)
    from math import comb
    expected = comb(8, 1) + comb(8, 2)
    GridSearch(subset_sizes=(1, 2), max_trials=None, seed=0).run(sandbox)
    assert len(sandbox.transcript) == expected


def test_adaptive_trial_count_bounded_and_sequential():
    sandbox, config = make_sandbox(K=15)
    Adaptive(max_features=3, seed=0).run(sandbox)
    # K singles, then up to (max_features-1) rounds each trying <=K-1 remaining features
    assert 15 <= len(sandbox.transcript) <= 15 + 2 * 14
    assert sandbox.submission is not None


def test_all_searchers_log_full_return_streams_never_leak_oos():
    sandbox, config = make_sandbox(K=10, s=2)
    Greedy(seed=0).run(sandbox)
    R = sandbox.returns_matrix()
    assert R.shape == (config.T, 10)
    # every logged stream has real in-sample length, not the OOS length
    for entry in sandbox.transcript:
        assert entry.return_stream.shape == (config.T,)


def test_best_submitted_spec_matches_best_logged_sharpe():
    sandbox, config = make_sandbox(K=15)
    Greedy(seed=0).run(sandbox)
    spec, dist = sandbox.submission
    best_logged = max(e.sharpe for e in sandbox.transcript)
    assert dist.mean == pytest.approx(best_logged)
