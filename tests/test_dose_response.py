import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.divergence import divergence_rate, beam_entropy
from searchers.dose_response import BeamAdaptive, DepthAdaptive, NeighborAdaptive
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
])
def test_replay_matches_run_on_real_data(searcher_factory):
    sandbox, config = make_sandbox()
    searcher = searcher_factory()
    searcher.run(sandbox)
    _, dist = sandbox.submission

    base_columns = sandbox.base_feature_columns()
    replayed = searcher.replay(base_columns, annualization=np.sqrt(config.periods_per_year))
    assert replayed == pytest.approx(dist.mean, rel=1e-6)


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
