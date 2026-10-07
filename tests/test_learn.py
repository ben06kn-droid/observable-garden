"""The learned predictors, on synthetic arrays only (`prereg/ml-pipeline-exploratory-2026-10-07.md`).

A small panel: 1,300 rows (five 252-row years and a short sixth, so three scored years),
12 assets, 40 features. No project data.
"""
import numpy as np
import pytest

from learn import inputs as I
from learn import leak, mv_combine, ridge_stack, stream_tier, trees


def _panel(T=1300, M=12, K=40, seed=3):
    rng = np.random.default_rng(seed)
    F = rng.standard_normal((T, M, K))
    R = 0.01 * rng.standard_normal((T, M)) + 0.002 * F[:, :, 4] * F[:, :, 9]
    return leak.Arrays(F, R, np.full((T, M), 5e-4), np.full((T, M), 0.5e-2 / 252), 252.0)


@pytest.fixture(scope="module")
def panel():
    return _panel()


# -- inputs and alignment ----------------------------------------------------------

def test_sigma_uses_returns_two_rows_back_and_needs_63_of_them(panel):
    sig = I.sigma(panel.returns)
    assert np.isnan(sig[:64]).all() and not np.isnan(sig[64:]).any()
    R2 = panel.returns.copy()
    R2[200:] += 1.0                                   # returns at rows >= 200 changed
    assert np.array_equal(I.sigma(R2)[:202], sig[:202], equal_nan=True)   # rows <= 201 use rows <= 199
    raw = panel.returns[100 - 64:100 - 1].std(axis=0, ddof=1)     # rows t-64..t-2 for t = 100
    assert np.allclose(sig[100], np.maximum(raw, np.percentile(raw, 10)), rtol=1e-12)


def test_states_are_zero_until_252_rows_of_history_and_clipped(panel):
    st = I.market_states(panel.returns)
    assert st.shape == (1300, 3)
    first_vol = 64                                    # first row with a 63-row lagged window
    assert np.all(st[:first_vol + 251, 0] == 0)
    assert np.abs(st).max() <= 3.0 and np.any(st[first_vol + 251:, 0] != 0)


def test_family_signals_follow_the_repository_map(panel):
    z = I.zscore_features(panel.features)
    s = I.family_signals(z)
    assert s.shape[2] == 14 and len(I.PAIRS) == 91
    assert sorted(k for f in I.FAMILIES for k in f) == list(range(40))
    raw = z[:, :, list(I.FAMILIES[2])].mean(axis=2)
    assert np.allclose(s[:, :, 2], I.cs(raw))


def test_basis_portfolio_is_unit_gross_and_demeaned(panel):
    sig = I.sigma(panel.returns)
    p = I.basis_portfolio(panel.features[:, :, 0], sig)
    g = np.abs(p[100:]).sum(axis=1)
    assert np.allclose(g, 1.0) and np.allclose(p[100:].sum(axis=1), 0.0, atol=1e-12)


# -- mv_combine -----------------------------------------------------------------------

def test_one_column_without_penalty_weights_mean_over_variance():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 500)
    mu, S = r.mean(), np.var(r, ddof=1)
    b = mv_combine.weights(np.array([mu]), np.array([[S]]), np.array([0.0]))
    assert b[0] == pytest.approx(mu / S, rel=1e-12)


def test_block_D_is_the_registered_formula(panel):
    cols = mv_combine.columns(panel, True)
    st, g, c = cols["st"], cols["gross"][:14], cols["cost"][:14]
    D = cols["netD"]
    assert D.shape == (42, panel.returns.shape[0])
    for f, k in ((0, 0), (5, 2), (13, 1)):
        assert np.allclose(D[3 * f + k], st[:, k] * g[f] - np.abs(st[:, k]) * c[f])


@pytest.fixture(scope="module")
def mv_on(panel):
    return mv_combine.run(panel, risk_sizing=True)


def test_mv_combine_training_gross_is_one_and_daily_gross_is_capped(mv_on):
    for d in mv_on["diagnostics"]:
        assert d["train_mean_gross"] == pytest.approx(1.0, abs=1e-12)
        assert d["c"] in mv_combine.C_GRID
    pos = mv_on["positions"][mv_on["scored_rows"]]
    assert np.abs(pos).sum(axis=1).max() <= 2.0 + 1e-12
    assert mv_on["warmup_dropped"] == 64


def test_mv_combine_diagnostics_carry_effective_parameters_by_block_and_by_c(mv_on):
    d = mv_on["diagnostics"][0]
    eff = d["effective"]
    assert eff["total"] == pytest.approx(sum(eff[b] for b in mv_combine.BLOCKS))
    assert 0 < eff["total"] < mv_combine.NCOL
    assert set(d["effective_by_c"]) == set(mv_combine.C_GRID)
    tot = [d["effective_by_c"][c]["total"] for c in mv_combine.C_GRID]
    assert all(a >= b for a, b in zip(tot, tot[1:]))        # more penalty, fewer parameters


# -- the leak test, every predictor ---------------------------------------------------

@pytest.mark.parametrize("name,run", [
    ("mv_combine risk on", lambda p: mv_combine.run(p, True)),
    ("mv_combine risk off", lambda p: mv_combine.run(p, False)),
    ("ridge_stack", lambda p: ridge_stack.run(p, "ridge_stack")),
    ("control", lambda p: ridge_stack.run(p, "control")),
])
def test_positions_up_to_d_do_not_see_anything_after_d(panel, name, run):
    rows = [500, 800, 1010, 1100]           # inside training and inside scored years
    res = leak.leak_test(run, panel, rows, seed=7)
    assert all(r["identical_up_to_d"] for r in res), (name, res)
    assert any(r["changed_after_d"] for r in res), name      # the test can see a change


# -- trees ------------------------------------------------------------------------------

def test_two_tree_fits_with_the_registered_settings_are_bit_identical():
    rng = np.random.default_rng(1)
    X = rng.standard_normal((5000, 43))
    y = X[:, 3] * (X[:, 7] > 0) + rng.standard_normal(5000)
    a = trees.fit(X, y).predict(X)
    b = trees.fit(X, y).predict(X)
    assert np.array_equal(a, b)
    import lightgbm
    assert lightgbm.__version__ == trees.PINNED_VERSION == "4.7.0"


# -- the supplied-streams tier -----------------------------------------------------------

def test_supplied_streams_go_through_the_class_table_null_and_confidence():
    rng = np.random.default_rng(2)
    T = 900
    s = rng.normal(0.0008, 0.01, T)
    base_cols = rng.standard_normal((T, 6))
    out = stream_tier.certify(s[None, :], base_cols, 252.0, B=200, seed=11)
    assert out["confidence"]["C0"] == pytest.approx(1 - out["p"], abs=0)
    assert out["score"] == pytest.approx(I.sharpe(s, 252.0), rel=1e-9)
    # one stream: the null maximum is that stream's demeaned replicate Sharpe
    rows, _ = stream_tier.bootstrap_rows(base_cols, 200, 11)
    s0 = s - s.mean()
    direct = [s0[r].mean() / s0[r].std(ddof=1) * np.sqrt(252) for r in rows[:5]]
    assert np.allclose(out["null_max"][:5], direct, rtol=1e-9)
    assert "confidence (declared stream)" in out["text"]
