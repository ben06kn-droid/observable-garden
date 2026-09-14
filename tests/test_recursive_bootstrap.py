"""replay() must agree with run() on the real (unresampled) data -- that's
the whole basis for trusting the recursive bootstrap's replicates. And the
recursive bootstrap should roughly agree with the naive one for the three
data-oblivious searchers (SCOPE.md), since re-deriving vs freezing a
selection that doesn't depend on the data shouldn't change anything."""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import null_max_bootstrap
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from searchers.scripted import Honest, Greedy, GridSearch, Adaptive


def make_sandbox(K=15, s=0, seed=0, M=50, T=300):
    config = DGPConfig(M=M, T=T, T_oos=100, K=K, s=s, rho=0.3, sigma=1.0, seed=seed)
    data = generate(config)
    return Sandbox(data, periods_per_year=config.periods_per_year), config


@pytest.mark.parametrize("searcher_factory", [
    lambda: Honest(feature_index=2, seed=0),
    lambda: Greedy(seed=0),
    lambda: GridSearch(subset_sizes=(1, 2), max_trials=200, seed=0),
    lambda: Adaptive(max_features=3, seed=0),
])
def test_replay_matches_run_on_real_data(searcher_factory):
    sandbox, config = make_sandbox()
    searcher = searcher_factory()
    searcher.run(sandbox)
    _, dist = sandbox.submission

    base_columns = sandbox.base_feature_columns()
    replayed = searcher.replay(base_columns, annualization=np.sqrt(config.periods_per_year))

    assert replayed == pytest.approx(dist.mean, rel=1e-6)


def test_recursive_bootstrap_agrees_with_naive_for_oblivious_searchers():
    sandbox, config = make_sandbox(K=15, seed=7)
    base_columns = sandbox.base_feature_columns()
    ann = np.sqrt(config.periods_per_year)

    for searcher in [Greedy(seed=7), GridSearch(subset_sizes=(1, 2), max_trials=200, seed=7)]:
        searcher.run(sandbox := make_sandbox(K=15, seed=7)[0])
        R = sandbox.returns_matrix()

        naive = null_max_bootstrap(R, B=1500, annualization=ann, seed=1)
        recursive = recursive_null_max_bootstrap(base_columns, searcher, B=1500, annualization=ann, seed=1)

        assert recursive.mean_null_max == pytest.approx(naive.mean_null_max, rel=0.15)
