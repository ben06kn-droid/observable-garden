"""7.5's planted generator (`environments/planted_panel.py`), on a small synthetic panel."""
import datetime as dt

import numpy as np
import pytest

from environments import planted_panel as pp
from environments.real_panel import RealPanel
from estimator.bootstrap import stationary_bootstrap_indices


def _panel(T=600, M=8, K=5, seed=0):
    rng = np.random.default_rng(seed)
    d0 = dt.date(2016, 6, 1)
    dates = [d0 + dt.timedelta(days=int(i * 1.6)) for i in range(T)]
    return RealPanel(
        name="synthetic", assets=[f"A{i}" for i in range(M)],
        feature_names=[f"f{k}" for k in range(K)],
        features=rng.normal(size=(T, M, K)), returns=rng.normal(size=(T, M)) * 0.01,
        tradable=np.ones((T, M), dtype=bool), periods_per_year=252,
        cost_rate=np.full((T, M), 0.0005), borrow_rate=np.full((T, M), 0.00002),
        session_start=np.zeros(T, dtype=bool), session_end=np.zeros(T, dtype=bool),
        flat_overnight=False, meta={"dates": dates})


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel())


def test_the_split_is_in_sample_to_2017_and_holdout_2018_on(base):
    assert max(base.in_sample.meta["dates"]) <= dt.date(2017, 12, 31)
    assert min(base.holdout.meta["dates"]) >= dt.date(2018, 1, 1)


def test_features_are_never_resampled_and_stay_in_calendar_order(base):
    """The registered statement: return blocks are resampled independently of X, and
    X keeps its order. Not joint (X, r) rows."""
    for seed in (1, 2, 3):
        d = pp.make_draw(base, seed, 1.0)
        assert np.array_equal(d.in_sample.features, base.in_sample.features)
        assert np.array_equal(d.holdout.features, base.holdout.features)
        # the residual rows ARE resampled
        assert not np.array_equal(d.idx_is, np.arange(len(d.idx_is)))


def test_levels_of_one_seed_are_paired_on_the_residual_and_the_member(base):
    draws = [pp.make_draw(base, 11, b) for b in pp.LEVELS]
    for d in draws[1:]:
        assert d.m_star == draws[0].m_star
        assert np.array_equal(d.idx_is, draws[0].idx_is)
        assert np.array_equal(d.idx_ho, draws[0].idx_ho)
        np.testing.assert_allclose(d.in_sample.returns - draws[0].in_sample.returns,
                                   d.c * d.w_star_is, atol=1e-15)


def test_level_zero_is_the_residual_alone(base):
    d = pp.make_draw(base, 5, 0.0)
    assert d.c == 0.0
    assert np.array_equal(d.in_sample.returns, base.E_is[d.idx_is])


def test_the_planted_scale_hits_its_population_sharpe(base):
    m = pp.planted_member(3, base.members)
    w = pp.member_weights(base.in_sample, m)
    for beta in (0.5, 1.0, 1.5):
        c = pp.planted_scale(base.in_sample, base.Sigma_is, w, beta)
        assert pp.population_sharpe(base.in_sample, base.Sigma_is, w, w, c) == \
            pytest.approx(beta, abs=1e-9)


def test_population_moments_are_the_dgps_own_by_monte_carlo(base):
    """Averaged over many residual draws, the realized per-period mean and variance
    of a member's net stream converge to the analytic population moments."""
    m = pp.planted_member(4, base.members)
    w = pp.member_weights(base.in_sample, m)
    c = pp.planted_scale(base.in_sample, base.Sigma_is, w, 1.0)
    mu, var = pp.population_moments(base.in_sample, base.Sigma_is, w, w, c)
    rng = np.random.default_rng(0)
    T = base.E_is.shape[0]
    means, sq = [], []
    for _ in range(4000):
        idx = stationary_bootstrap_indices(T, pp.BLOCK_LENGTH, rng)
        from dataclasses import replace
        x = replace(base.in_sample, returns=base.E_is[idx] + c * w).net_stream(w)
        means.append(x.mean())
        sq.append((x ** 2).mean())
    m_hat = np.mean(means)
    v_hat = np.mean(sq) - m_hat ** 2
    assert m_hat == pytest.approx(mu, rel=0.03)
    assert v_hat == pytest.approx(var, rel=0.01)


def test_batched_population_sharpes_equal_the_per_member_path(base):
    m = pp.planted_member(6, base.members)
    w = pp.member_weights(base.in_sample, m)
    c = pp.planted_scale(base.in_sample, base.Sigma_is, w, 1.0)
    sups = base.members[:20]
    batch = pp.population_sharpes(base.in_sample, base.Sigma_is, w, c, sups)
    one = [pp.population_sharpe(base.in_sample, base.Sigma_is,
                                pp.member_weights(base.in_sample, s), w, c) for s in sups]
    np.testing.assert_allclose(batch, one, rtol=1e-10)


def test_level_zero_is_a_null_for_every_member(base):
    """c = 0: zero gross edge and positive cost, so every population Sharpe is < 0."""
    w = pp.member_weights(base.in_sample, base.members[0])
    sr = pp.population_sharpes(base.in_sample, base.Sigma_is, w, 0.0, base.members)
    assert (sr < 0).all()


def test_seed_children_carry_over_from_the_preflight():
    for seed in (640000, 640007):
        a = np.random.SeedSequence(seed).spawn(2)
        b = pp.children(seed)
        for i in range(2):
            assert np.array_equal(a[i].generate_state(4), b[i].generate_state(4))


def test_the_masking_permutation_follows_the_member_draw():
    p1, p2 = pp.masking_permutation(9, 40), pp.masking_permutation(10, 40)
    assert sorted(p1) == list(range(40)) and not np.array_equal(p1, p2)


ETF = pytest.mark.skipif(
    not (__import__("pathlib").Path(__file__).resolve().parent.parent
         / "data" / "raw" / "etf_insample").exists(), reason="ETF in-sample data absent")


@ETF
def test_the_registered_generator_reproduces_the_preflights_scale():
    """The preflight (`runs/planted_edge_preflight.json`) used the prototype with a
    ddof = 1 covariance; the registered definition is ddof = 0. Same member, and the
    scale agrees to the 1/T the definitions differ by."""
    import json
    base = pp.load_base()
    assert base.in_sample.features.shape[0] == 3019
    pre = {(r["seed"], r["beta"]): r for r in json.loads(
        open("runs/planted_edge_preflight.json").read())}
    for seed in (640000, 640001):
        d = pp.make_draw(base, seed, 1.0)
        r = pre[(seed, 1.0)]
        assert [list(p) for p in d.m_star] == r["planted"]
        assert d.c == pytest.approx(r["c"], rel=2.0 / 3019)
