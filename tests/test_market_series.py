"""The declared market series (`environments.real_panel._etf_base_signals`): the ETF path
passes SPY's column and stays bit-identical to the pinned X; a panel without a declared
market series is an error, with no first-asset fallback."""
import hashlib
import platform

import numpy as np
import pytest

from environments import real_panel as rp


def _synthetic(T=300, M=5, seed=0):
    rng = np.random.default_rng(seed)
    r = 0.01 * rng.standard_normal((T, M))
    logp = np.cumsum(r, axis=0)
    return logp, r


def test_no_declared_market_series_is_an_error():
    logp, r = _synthetic()
    with pytest.raises(ValueError, match="no declared market"):
        rp._etf_base_signals(logp, r, None)
    with pytest.raises(ValueError, match="shape"):
        rp._etf_base_signals(logp, r, r[:-1, 0])
    m = r[:, 0].copy()
    m[7] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        rp._etf_base_signals(logp, r, m)


def test_declared_market_refuses_a_panel_without_its_column():
    _, r = _synthetic()
    with pytest.raises(ValueError, match="no fallback"):
        rp.declared_market(["AAA", "BBB", "CCC", "DDD", "EEE"], r)
    assert np.array_equal(rp.declared_market(["AAA", "SPY", "C", "D", "E"], r), r[:, 1])


def test_beta_and_idvol_regress_on_the_declared_series_not_on_an_asset():
    logp, r = _synthetic()
    mkt = r.mean(axis=1)                                 # e.g. an equal-weighted market
    sig = rp._etf_base_signals(logp, r, mkt)
    t = 280
    a, x = r[t - 251:t + 1], mkt[t - 251:t + 1]
    xc = x - x.mean()
    beta = (xc @ (a - a.mean(axis=0))) / (xc @ xc)
    assert np.allclose(sig["beta252"][t], beta, rtol=1e-12)
    a, x = r[t - 62:t + 1], mkt[t - 62:t + 1]
    xc = x - x.mean()
    b = (xc @ (a - a.mean(axis=0))) / (xc @ xc)
    resid = a - a.mean(axis=0) - np.outer(xc, b)
    assert np.allclose(sig["idvol63"][t], resid.std(axis=0, ddof=1), rtol=1e-12)
    assert np.isnan(sig["beta252"][250]).all() and not np.isnan(sig["beta252"][251]).any()
    # an asset's own column as the market gives that asset beta 1
    sig0 = rp._etf_base_signals(logp, r, r[:, 2])
    assert np.allclose(sig0["beta252"][260:, 2], 1.0)


def test_the_build_span_refuses_prices_without_spy():
    from experiments import grade_real as gr
    dates = [f"2010-01-{d:02d}" for d in range(1, 20)]
    prices = {t: (dates, np.linspace(10, 11, len(dates))) for t in ("AAA", "BBB", "CCC")}
    with pytest.raises(ValueError, match="no fallback"):
        gr.build_span(prices)


@pytest.mark.skipif(platform.machine() != "arm64",
                    reason="the pinned X was built on arm64; another platform breaks rank "
                           "ties differently (prereg/planted-edge.md)")
def test_the_etf_build_with_spy_declared_is_bit_identical_to_the_pinned_x(tmp_path):
    from environments import planted_panel as pp
    try:
        F = rp.build_etf_panel().features
    except (FileNotFoundError, SystemExit) as e:                # no ETF data on this machine
        pytest.skip(f"ETF in-sample data unavailable: {e}")
    f = tmp_path / "x.npy"
    np.save(f, np.ascontiguousarray(F, dtype=np.float64))
    assert hashlib.sha256(f.read_bytes()).hexdigest() == pp.PINNED_X_SHA256
    assert pp.PINNED_X_SHA256.startswith("4b461070") and pp.PINNED_X_SHA256.endswith("b7ba")
