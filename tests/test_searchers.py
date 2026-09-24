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


# -- BudgetedRandom (7.0 amendment 5) ---------------------------------------

def test_budgeted_random_submits_the_best_of_its_budget():
    """`prereg/gate-comparison.md` amendment 5: a fixed budget drawn uniformly
    from the declared class, submitting the best seen."""
    from searchers.scripted import BudgetedRandom
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=12, s=1, rho=0.0, sigma=1.0, seed=0)
    data = generate(cfg)
    for budget in (25, 100):
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
        s = BudgetedRandom(budget=budget, seed=3)
        s.run(sb)
        assert len(sb.transcript) == budget            # one evaluation per draw
        spec, dist = sb.submission
        assert float(dist.mean) == max(e.sharpe for e in sb.transcript)


def test_budgeted_random_stays_inside_the_declared_class():
    """Capped by construction: it samples members of the class, so a sandbox
    holding that class refuses nothing it proposes."""
    from garden.spec_class import SubsetClass
    from searchers.scripted import BudgetedRandom
    cfg = DGPConfig(M=20, T=400, T_oos=100, K=10, s=0, rho=0.0, sigma=1.0, seed=1)
    cls = SubsetClass(max_size=3, signed=True)
    sb = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year, spec_class=cls)
    BudgetedRandom(budget=50, max_size=3, signed=True, seed=5).run(sb)   # no refusal
    for e in sb.transcript:
        assert cls.contains(e.spec.weights)
        assert 1 <= int(np.sum(e.spec.weights != 0)) <= 3


def test_budgeted_random_is_replayable_with_the_same_sample():
    """The sample is a function of the seed, so a replicate re-executes the same
    members: the budget is a property of the searcher, not of the data."""
    from searchers.scripted import BudgetedRandom
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=12, s=1, rho=0.0, sigma=1.0, seed=2)
    data = generate(cfg)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
    s = BudgetedRandom(budget=60, seed=7)
    s.run(sb)
    base = sb.base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))
    # replay on the un-resampled columns reproduces the submitted statistic
    assert s.replay(base, ann) == pytest.approx(float(sb.submission[1].mean), abs=1e-9)
    # and the sample itself does not depend on the data
    assert s._sample(12) == BudgetedRandom(budget=60, seed=7)._sample(12)
    assert s._sample(12) != BudgetedRandom(budget=60, seed=8)._sample(12)


def test_a_bigger_budget_has_less_slack():
    """The point of the searcher: slack falls as the budget rises, so 7.0 has
    three known slack levels."""
    from searchers.scripted import BudgetedRandom
    cfg = DGPConfig(M=20, T=600, T_oos=200, K=12, s=1, rho=0.0, sigma=1.0, seed=4)
    base = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year).base_feature_columns()
    ann = float(np.sqrt(cfg.periods_per_year))
    got = [BudgetedRandom(budget=b, seed=11).replay(base, ann) for b in (25, 100, 400)]
    assert got[0] <= got[1] <= got[2] + 1e-12
