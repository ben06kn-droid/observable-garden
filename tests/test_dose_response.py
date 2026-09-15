import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe
from estimator.divergence import divergence_rate, beam_entropy
from searchers.dose_response import (
    BeamAdaptive, DepthAdaptive, GumbelAnchored, NeighborAdaptive, RandomAnchor, RankAnchor, WinnerAnchor,
    WorstAnchor, normalized_rank,
)
from searchers.diagnostic import LatticeAdaptive
from searchers.scripted import Adaptive


def make_sandbox(K=15, M=50, T=300, seed=0):
    config = DGPConfig(M=M, T=T, T_oos=100, K=K, s=0, rho=0.3, sigma=1.0, seed=seed)
    data = generate(config)
    return Sandbox(data, periods_per_year=config.periods_per_year), config


@pytest.mark.parametrize("searcher_factory", [
    lambda: BeamAdaptive(beam_width=1, seed=0),
    lambda: BeamAdaptive(beam_width=4, seed=0),
    lambda: BeamAdaptive(beam_width=15, seed=0),  # beam_width == K
    lambda: DepthAdaptive(seed=0),
    lambda: NeighborAdaptive(seed=0),
    lambda: NeighborAdaptive(max_features=2, seed=0),
    lambda: WinnerAnchor(max_features=2, seed=0),
    lambda: RandomAnchor(max_features=2, seed=0),
    lambda: WorstAnchor(max_features=2, seed=0),
    lambda: GumbelAnchored(tau=1.0, seed=0),
    lambda: GumbelAnchored(tau=-2.0, max_features=3, seed=0),
    lambda: RankAnchor(rank=1, seed=0),
    lambda: RankAnchor(rank=3, seed=0),
    lambda: RankAnchor(rank=15, max_features=3, seed=0),
])
def test_replay_matches_run_on_real_data(searcher_factory):
    sandbox, config = make_sandbox()
    searcher = searcher_factory()
    searcher.run(sandbox)
    _, dist = sandbox.submission

    base_columns = sandbox.base_feature_columns()
    replayed = searcher.replay(base_columns, annualization=np.sqrt(config.periods_per_year))
    assert replayed == pytest.approx(dist.mean, rel=1e-6)


def test_neighbor_anchor_is_never_the_round1_winner():
    for seed in range(25):
        sandbox, _ = make_sandbox(K=12, seed=seed)
        base = sandbox.base_feature_columns()
        best_k = int(np.argmax(sharpe(base, axis=0)))
        anchor = NeighborAdaptive(seed=seed)._anchor(12, base, best_k)
        assert anchor != best_k
        others = np.abs(np.corrcoef(base, rowvar=False)[best_k])
        others[best_k] = 0.0
        assert anchor == int(np.argmax(others))


def test_anchor_rules():
    sandbox, _ = make_sandbox(K=12, seed=4)
    base = sandbox.base_feature_columns()
    best_k = int(np.argmax(sharpe(base, axis=0)))
    assert WinnerAnchor(seed=4)._anchor(12, base, best_k) == best_k
    assert WorstAnchor(seed=4)._anchor(12, base, best_k) == int(np.argmin(sharpe(base, axis=0)))
    other, _ = make_sandbox(K=12, seed=99)
    other_base = other.base_feature_columns()
    assert (RandomAnchor(seed=4)._anchor(12, base, best_k)
            == RandomAnchor(seed=4)._anchor(12, other_base, int(np.argmax(sharpe(other_base, axis=0)))))


def test_gumbel_anchor_limits_and_data_independence_at_zero():
    sandbox, _ = make_sandbox(K=12, seed=4)
    base = sandbox.base_feature_columns()
    sr = sharpe(base, axis=0)
    best_k = int(np.argmax(sr))
    assert GumbelAnchored(tau=np.inf, seed=4)._anchor(12, base, best_k) == best_k
    assert GumbelAnchored(tau=-np.inf, seed=4)._anchor(12, base, best_k) == int(np.argmin(sr))
    other = make_sandbox(K=12, seed=99)[0].base_feature_columns()
    assert (GumbelAnchored(tau=0.0, seed=4)._anchor(12, base, best_k)
            == GumbelAnchored(tau=0.0, seed=4)._anchor(12, other, 0))


def test_rank_anchor_sets_the_anchor_rank():
    for seed in range(10):
        base = make_sandbox(K=12, seed=seed)[0].base_feature_columns()
        sr = sharpe(base, axis=0)
        best_k = int(np.argmax(sr))
        order = np.argsort(-sr)
        assert RankAnchor(rank=1, seed=seed)._anchor(12, base, best_k) == best_k
        assert RankAnchor(rank=12, seed=seed)._anchor(12, base, best_k) == int(np.argmin(sr))
        for rank in (2, 3, 5, 10):
            anchor = RankAnchor(rank=rank, seed=seed)._anchor(12, base, best_k)
            assert anchor == int(order[rank - 1]) and anchor != best_k
            assert normalized_rank(base, anchor) == pytest.approx((12 - rank) / 11)


def test_rank_anchor_rejects_ranks_outside_the_features():
    base = make_sandbox(K=12, seed=4)[0].base_feature_columns()
    with pytest.raises(ValueError):
        RankAnchor(rank=0)
    with pytest.raises(ValueError):
        RankAnchor(rank=13)._anchor(12, base, 0)


def test_rank_one_and_last_match_winner_and_worst_anchor():
    for rule, rank in ((WinnerAnchor, 1), (WorstAnchor, 15)):
        sandbox1, _ = make_sandbox(seed=7)
        sandbox2, _ = make_sandbox(seed=7)
        rule(max_features=2, seed=7).run(sandbox1)
        RankAnchor(rank=rank, max_features=2, seed=7).run(sandbox2)
        assert sandbox1.submission[1].mean == pytest.approx(sandbox2.submission[1].mean, rel=1e-12)


def test_gumbel_coupling_rises_with_tau():
    base = make_sandbox(K=12, seed=4)[0].base_feature_columns()
    best_k = int(np.argmax(sharpe(base, axis=0)))
    kappa = [np.mean([normalized_rank(base, GumbelAnchored(tau=tau, seed=s)._anchor(12, base, best_k))
                      for s in range(400)])
             for tau in (-2.0, 0.0, 2.0)]
    assert kappa[0] < 0.4 < kappa[1] < 0.6 < kappa[2]


def test_normalized_rank_endpoints():
    base = make_sandbox(K=12, seed=4)[0].base_feature_columns()
    sr = sharpe(base, axis=0)
    assert normalized_rank(base, int(np.argmax(sr))) == 1.0
    assert normalized_rank(base, int(np.argmin(sr))) == 0.0


def test_winner_anchor_matches_adaptive():
    sandbox1, _ = make_sandbox(seed=6)
    sandbox2, _ = make_sandbox(seed=6)
    WinnerAnchor(max_features=3, seed=6).run(sandbox1)
    Adaptive(max_features=3, seed=6).run(sandbox2)
    assert sandbox1.submission[1].mean == pytest.approx(sandbox2.submission[1].mean, rel=1e-9)


def test_beam_width_1_matches_adaptive():
    sandbox1, config = make_sandbox(seed=5)
    sandbox2, _ = make_sandbox(seed=5)
    BeamAdaptive(beam_width=1, seed=5).run(sandbox1)
    Adaptive(max_features=3, seed=5).run(sandbox2)
    assert sandbox1.submission[1].mean == pytest.approx(sandbox2.submission[1].mean, rel=1e-9)


def test_beam_width_grows_monotonically_toward_full_lattice_optimum():
    # Larger beam width should never do WORSE than a smaller one (it's a
    # strict superset of what a smaller beam considers at every round).
    sandbox_k, config = make_sandbox(K=12, seed=7)
    base_columns = sandbox_k.base_feature_columns()
    ann = np.sqrt(config.periods_per_year)
    sharpes = []
    for k in [1, 2, 4, 12]:
        sb, _ = make_sandbox(K=12, seed=7)
        BeamAdaptive(beam_width=k, seed=7).run(sb)
        sharpes.append(sb.submission[1].mean)
    assert all(sharpes[i] <= sharpes[i + 1] + 1e-9 for i in range(len(sharpes) - 1))


@pytest.mark.parametrize("searcher_factory,expect_zero", [
    (lambda: LatticeAdaptive(seed=0), True),
    (lambda: Adaptive(max_features=3, seed=0), False),
])
def test_divergence_rate_bounds(searcher_factory, expect_zero):
    sandbox, config = make_sandbox(K=10, seed=9)
    base_columns = sandbox.base_feature_columns()
    rate = divergence_rate(base_columns, searcher_factory(), B=200, seed=1)
    assert 0.0 <= rate <= 1.0
    if expect_zero:
        assert rate == 0.0
    else:
        assert rate > 0.0


def test_beam_entropy_zero_for_oblivious_menu_positive_otherwise():
    sandbox, config = make_sandbox(K=10, seed=9)
    base_columns = sandbox.base_feature_columns()
    h_lattice = beam_entropy(base_columns, LatticeAdaptive(seed=9), B=200, seed=1)
    h_adaptive = beam_entropy(base_columns, Adaptive(max_features=3, seed=9), B=200, seed=1)
    assert h_lattice == 0.0
    assert h_adaptive > 0.0


def test_round1_beam_sizes():
    sandbox, config = make_sandbox(K=10, seed=3)
    base_columns = sandbox.base_feature_columns()
    assert len(Adaptive(max_features=3, seed=3).round1_beam(base_columns)) == 1
    assert len(LatticeAdaptive(seed=3).round1_beam(base_columns)) == 10
    assert len(BeamAdaptive(beam_width=4, seed=3).round1_beam(base_columns)) == 4
    assert len(NeighborAdaptive(seed=3).round1_beam(base_columns)) == 1
