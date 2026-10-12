"""Version 2 (`learn2`), on synthetic arrays only."""
import numpy as np
import pytest

from learn2 import blocks as Bk
from learn2 import learner as Ln
from learn2 import leak as Lk
from learn2 import states as S
from learn2 import timing
from learn2 import views as Vw


def _inputs(T=1150, M=12, seed=3, d=1, with_p=True):
    rng = np.random.default_rng(seed)
    P = rng.standard_normal((T, M, 40)) if with_p else None
    earned = 0.01 * rng.standard_normal((T, M))
    if with_p:
        earned += 0.002 * np.vstack([P[1:, :, 4], np.zeros((1, M))])       # an edge in row t's P
    r = timing.known_returns(earned, d)
    X = Bk.build_X(np.nan_to_num(r), np.nan_to_num(r).mean(axis=1))
    G = Bk.build_groups(np.nan_to_num(r))
    return Ln.Inputs(P=P, earned=earned, cost_rate=np.full((T, M), 5e-4),
                     borrow_rate=np.full((T, M), 0.5e-2 / 252), ppy=252.0, d=d,
                     blocks={"X": X}, groups=G)


# -- timing and states -----------------------------------------------------------------------

def test_timing_known_returns_forward_sums_and_embargo():
    e = np.arange(20, dtype=float)[:, None] * np.ones((1, 2))
    assert np.isnan(timing.known_returns(e, 1)[:2]).all() and timing.known_returns(e, 1)[5, 0] == 3.0
    assert timing.known_returns(e, 0)[5, 0] == 4.0
    f = timing.forward_sum(e, 5)
    assert f[0, 0] == 0 + 1 + 2 + 3 + 4 and np.isnan(f[16:]).all() and not np.isnan(f[15]).any()
    assert timing.embargo(5, 1) == 7 and timing.embargo(1, 0) == 2


def test_states_equal_version_1_at_d1_and_regimes_are_off_until_warm():
    from learn import inputs as I
    r = 0.01 * np.random.default_rng(0).standard_normal((700, 8))
    st = S.market_states(r, 1)
    assert np.array_equal(st, I.market_states(r))
    g = S.regime_gates(st)
    assert set(g) == set(S.REGIMES) and g["always"].all()
    cold = st[:, 0] == 0
    assert not g["vol_high"][cold].any() and not g["vol_low"][cold].any()
    assert np.array_equal(g["vol_high"] | g["vol_low"], ~cold)


# -- blocks -----------------------------------------------------------------------------------

def test_block_X_is_finite_zero_until_warm_sign_invariant_and_leak_free():
    rng = np.random.default_rng(1)
    r = 0.01 * rng.standard_normal((400, 10))
    m = r.mean(axis=1)
    X = Bk.build_X(r, m)
    assert X.shape == (400, 10, 10) and np.isfinite(X).all()
    assert np.all(X[:251] == 0) and np.any(X[251] != 0)
    res = Lk.leak_block(Bk.build_X, (r, m), (300, 350))
    assert all(x["identical_up_to_t"] and x["changed_after_t"] for x in res)
    # beta x market column is beta_i * m_t standardised
    t = 300
    R, x = r[t - 251:t + 1], m[t - 251:t + 1]
    xc = x - x.mean()
    beta = (xc @ (R - R.mean(axis=0))) / (xc @ xc)
    assert np.allclose(X[t, :, 0], Bk.cs((beta * m[t])[None, :, None])[0, :, 0])


def test_block_V_columns_follow_the_fields_and_are_leak_free():
    rng = np.random.default_rng(2)
    T, M = 120, 6
    vol = np.exp(rng.standard_normal((T, M)))
    price = 10 + np.cumsum(rng.standard_normal((T, M)), axis=0) ** 2
    r = 0.01 * rng.standard_normal((T, M))
    V, names = Bk.build_V(vol, price, r)
    assert names == ("logvol_ratio", "amihud21") and V.shape == (T, M, 2)
    V5, n5 = Bk.build_V(vol, price, r, taker=vol * 0.6, count=vol * 3)
    assert n5 == Bk.V_NAMES and V5.shape[2] == 5
    res = Lk.leak_block(lambda v: Bk.build_V(v, price, r), (vol,), (60, 90))
    assert all(x["identical_up_to_t"] for x in res)
    F = Bk.build_F(0.0001 * rng.standard_normal((T, M)))
    assert F.shape == (T, M, 3) and np.isfinite(F).all()


def test_the_fast_cluster_rule_equals_the_literal_rule_and_groups_have_3_or_more():
    rng = np.random.default_rng(0)
    for _ in range(60):
        M = int(rng.integers(6, 25))
        D = 1 - np.corrcoef(rng.standard_normal((40, M)).T)
        a, b = Bk.cluster(D), Bk.cluster_bruteforce(D)
        assert np.array_equal(a, b)
        sizes = np.bincount(a)
        assert sizes.min() >= 3 or len(sizes) == 1
        assert a[0] == 0                                   # numbered by smallest asset index
    r = 0.01 * rng.standard_normal((300, 12))
    res = Lk.leak_block(Bk.build_groups, (r,), (270,))
    assert all(x["identical_up_to_t"] for x in res)
    assert (Bk.build_groups(r)[:251] == -1).all()


# -- learner and views ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def inp():
    return _inputs()


@pytest.fixture(scope="module")
def cache(inp):
    return Vw.FitCache(inp)


def test_a_fit_respects_the_embargo_and_reports_edges(inp, cache):
    f = cache.get(("P", "X"), 5, "market", "roll252")
    emb = timing.embargo(5, 1)
    assert f["first"] == 756 + emb
    assert np.isnan(f["pred"][:f["first"]]).all() and not np.isnan(f["pred"][f["first"]:]).any()
    for dg in f["diagnostics"]:
        assert dg["train_rows"] <= 252 and set(dg["penalties"]) == {"L", "Q", "I", "S"}
        assert all(b in dg["penalties"] for b in dg["at_edge"])
        assert min(dg["stack"]) >= 0
    g = cache.get(("X",), 1, "market", "expand")
    assert set(g["diagnostics"][0]["penalties"]) == {"L"}


def test_fits_repeat_bit_for_bit(inp):
    a = Ln.fit_cell(inp, ("P",), 1, "group", "roll756")
    b = Ln.fit_cell(inp, ("P",), 1, "group", "roll756")
    assert np.array_equal(a["pred"], b["pred"], equal_nan=True)


def test_group_positions_are_demeaned_within_groups_and_unit_gross(inp, cache):
    f = cache.get(("X",), 1, "group", "roll252")
    tgt = Vw.target_positions(f["pred"], "group", inp.groups, f["refit_of"])
    t = f["first"] + 3
    g = inp.groups[f["refit_of"][t]]
    for lab in np.unique(g):
        assert abs(tgt[t, g == lab].sum()) < 1e-12
    assert np.abs(tgt[t]).sum() == pytest.approx(1.0)


def test_the_view_book_averages_nine_variants_gates_and_is_not_rescaled(inp, cache):
    v = (("X",), 1, "market", "vol_high")
    vb = Vw.view_book(cache, v)
    assert len(vb["variants"]) == 9 and vb["variant_corr"].shape == (9, 9)
    gates = S.regime_gates(S.market_states(inp.earned, inp.d))
    avg = np.mean(np.stack(list(vb["variants"].values())), axis=0)
    assert np.array_equal(vb["book"], avg * gates["vol_high"][:, None])
    assert np.all(vb["book"][~gates["vol_high"]] == 0)
    assert np.abs(avg).sum(axis=1).max() <= 1 + 1e-12
    # a rate of 0.3 is the stated recursion
    a03 = vb["variants"][(0.3, "roll252")]
    a10 = vb["variants"][(1.0, "roll252")]
    t = vb["first"] + 4
    assert np.allclose(a03[t], 0.7 * a03[t - 1] + 0.3 * a10[t])


def test_view_positions_do_not_see_anything_after_t(inp):
    def book(i):
        return Vw.view_book(Vw.FitCache(i), (("P", "X"), 5, "group", "mkt_up"))["book"]
    res = Lk.leak_view(book, inp, (800, 1000), seed=4)
    assert all(r["identical_up_to_t"] for r in res), res
    assert any(r["changed_after_t"] for r in res)


def test_the_menu_tier_with_one_view_equals_the_supplied_streams_tier():
    from learn import stream_tier
    rng = np.random.default_rng(5)
    s = rng.normal(0.0008, 0.01, 900)
    bc = rng.standard_normal((900, 6))
    a = Vw.menu_p(s[None, :], 0, bc, 252.0, 300, 17)
    b = stream_tier.certify(s[None, :], bc, 252.0, 300, 17)
    assert a["p"] == b["p"] and a["score"] == pytest.approx(b["score"], rel=1e-12)
    two = Vw.menu_p(np.stack([s, rng.normal(0, 0.01, 900)]), 0, bc, 252.0, 300, 17)
    assert two["p"] >= a["p"]                                        # a bigger menu, a higher bar


def test_the_view_count_and_base_view():
    av = ("P", "X", "V")
    assert len(Vw.informations(av)) == 7 and len(Vw.all_views(av)) == 294
    assert Vw.base_view(av) == (("P", "X", "V"), 5, "market", "always")


def test_turnover_is_reported_raw_and_per_unit_gross():
    inp = _inputs(T=40, M=4, with_p=False)
    book = np.zeros((40, 4))
    book[10:] = [0.25, -0.25, 0.1, -0.1]
    book[20:] = [0.1, -0.1, 0.25, -0.25]
    st = Vw.turnover_stats(book, inp, np.arange(5, 40))
    assert st["turnover_per_unit_gross"] == pytest.approx((0.7 + 0.6) / (0.7 * 30))
    assert st["mean_gross"] == pytest.approx(0.7 * 30 / 35)


def test_groups_on_market_residuals_use_one_window_beta():
    rng = np.random.default_rng(7)
    T, M = 300, 9
    m = 0.01 * rng.standard_normal(T)
    r = np.outer(m, np.linspace(0.5, 1.5, M)) + 0.01 * rng.standard_normal((T, M))
    G = Bk.build_groups(r, m)
    t = 280
    R, x = r[t - 251:t + 1], m[t - 251:t + 1]
    xc = x - x.mean()
    beta = (xc @ (R - R.mean(axis=0))) / (xc @ xc)
    E = R - np.outer(x, beta)
    sd = E.std(axis=0, ddof=1)
    Z = (E - E.mean(axis=0)) / sd
    C = Z.T @ Z / 251
    np.fill_diagonal(C, 1.0)
    assert np.array_equal(G[t], Bk.cluster(1.0 - C))
    res = Lk.leak_block(lambda rr: Bk.build_groups(rr, m), (r,), (270,))
    assert all(x_["identical_up_to_t"] for x_ in res)


def test_rate_grids_change_books_not_fits(inp, cache):
    v = (("X",), 1, "market", "always")
    a = Vw.view_book(cache, v, rates=Vw.RATE_GRIDS["G1"])
    b = Vw.view_book(cache, v, rates=Vw.RATE_GRIDS["G3"])
    assert set(k[0] for k in b["variants"]) == {0.3, 0.1, 0.03}
    assert np.array_equal(a["variants"][(0.3, "roll252")], b["variants"][(0.3, "roll252")])
    assert not np.array_equal(a["book"], b["book"])


def test_a_penalty_grid_override_is_used_and_reported(inp):
    g = {"L": (1.0, 3.0, 10.0, 30.0)}
    f = Ln.fit_cell(inp, ("P",), 5, "market", "roll252", grids=g)
    for d in f["diagnostics"]:
        assert d["penalties"]["L"] in g["L"]
        assert ("L" in d["at_edge"]) == (d["penalties"]["L"] in (1.0, 30.0))
    cache = Vw.FitCache(inp, grids=g)
    assert cache.get(("P",), 5, "market", "roll252")["diagnostics"] == f["diagnostics"]


def test_memory_set_m2_averages_six_variants_from_the_same_fits(inp, cache):
    v = (("X",), 1, "market", "always")
    m1 = Vw.view_book(cache, v, rates=Vw.RATE_GRIDS["G3"])
    m2 = Vw.view_book(cache, v, rates=Vw.RATE_GRIDS["G3"], memories=("roll756", "expand"))
    assert len(m2["variants"]) == 6 and all(k[1] != "roll252" for k in m2["variants"])
    assert np.array_equal(m2["variants"][(0.1, "expand")], m1["variants"][(0.1, "expand")])
    assert np.allclose(m2["book"], np.mean(np.stack(list(m2["variants"].values())), axis=0))
