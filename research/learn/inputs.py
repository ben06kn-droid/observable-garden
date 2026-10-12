"""Shared inputs for every predictor (`prereg/ml-pipeline-exploratory-2026-10-07.md`, Part 2A).

**Alignment.** A panel row's return is the return its positions earn (signal at the close
of t, held from t+1 to t+2), so it is realised two rows later. An input at row t uses
features at rows <= t and row-returns at rows <= t - 2. Nothing here reads a later row:
every rolling quantity is a function of earlier rows only, so changing data after a row
leaves every input up to that row bit-identical (`tests/test_learn_inputs.py`).

A panel is any object with `features` (T, M, K), `returns` (T, M), `cost_rate` (T, M),
`borrow_rate` (T, M) and `periods_per_year`, as `environments.real_panel.RealPanel` has.
"""
from __future__ import annotations

import numpy as np

# The repository's 14 families: complete-linkage clusters at tau 0.8 of the 40 single-feature
# weight paths (6726871). A fixed input.
FAMILIES = ((0, 1), (2, 3), (4, 5, 24, 25), (6, 7), (8, 9, 26, 27, 28, 29), (10, 11, 12, 13),
            (14, 15, 16, 17, 18, 19), (20, 21), (22, 23), (30, 31), (32, 33), (34, 35),
            (36, 37), (38, 39))
NF = len(FAMILIES)
FAMILY_OF = np.empty(40, dtype=int)
for _f, _members in enumerate(FAMILIES):
    FAMILY_OF[list(_members)] = _f
PAIRS = tuple((f, g) for f in range(NF) for g in range(f + 1, NF))     # 91, f < g

LAG = 2                 # a row-return is realised two rows later
SIGMA_ROWS = 63
SIGMA_FLOOR_Q = 0.10
STATE_VOL_ROWS = 63
STATE_SUM_ROWS = 63
STATE_DISP_ROWS = 21
STATE_MIN_HISTORY = 252
STATE_CLIP = 3.0
SMOOTH = 5
YEAR = 252
GAP = 2                 # the embargo, in rows


def cs(x: np.ndarray) -> np.ndarray:
    """Standardise across assets (axis 1) each row: demean, divide by the SD (ddof 0, as
    the repository's `_zscore`). A zero-variance row gives zeros."""
    x = np.asarray(x, float)
    mu = x.mean(axis=1, keepdims=True)
    sd = x.std(axis=1, keepdims=True)
    return np.where(sd > 0, (x - mu) / np.where(sd > 0, sd, 1.0), 0.0)


def zscore_features(features: np.ndarray) -> np.ndarray:
    """z: the 40 features standardised across assets each day."""
    return cs(features)


def family_signals(z: np.ndarray) -> np.ndarray:
    """s_f: each family's mean of its members' z, re-standardised across assets. (T, M, 14)."""
    return cs(np.stack([z[:, :, list(m)].mean(axis=2) for m in FAMILIES], axis=2))


def _lagged(r: np.ndarray, lag: int = LAG) -> np.ndarray:
    """Row t holds r[t - lag]; the first `lag` rows are NaN."""
    out = np.full_like(r, np.nan, dtype=float)
    out[lag:] = r[:-lag]
    return out


def _trailing(x: np.ndarray, w: int, fn) -> np.ndarray:
    """fn over the trailing w rows (inclusive), NaN until full or if any value is NaN."""
    out = np.full(x.shape, np.nan)
    for t in range(w - 1, x.shape[0]):
        blk = x[t - w + 1:t + 1]
        if not np.isnan(blk).any():
            out[t] = fn(blk)
    return out


def sigma(returns: np.ndarray) -> np.ndarray:
    """sigma_i at row t: the SD (ddof 1) of the asset's row-returns at rows t-64..t-2 (63
    rows), floored at that row's cross-sectional 10th percentile. NaN without full history."""
    lr = _lagged(np.asarray(returns, float))
    s = _trailing(lr, SIGMA_ROWS, lambda b: b.std(axis=0, ddof=1))
    floor = np.nanpercentile(np.where(np.isnan(s).all(axis=1, keepdims=True), 0.0, s),
                             100 * SIGMA_FLOOR_Q, axis=1, keepdims=True)
    return np.where(np.isnan(s), np.nan, np.maximum(s, floor))


def valid_rows(returns: np.ndarray) -> np.ndarray:
    """Rows with a full sigma history; the rest are dropped from every fit."""
    return ~np.isnan(sigma(returns)).any(axis=1)


def _expanding_standardise(x: np.ndarray) -> np.ndarray:
    """(x_t - mean(x_<=t)) / sd(x_<=t) over the valid history, zero until 252 valid values,
    clipped to [-3, 3]."""
    out = np.zeros_like(x)
    n = s1 = s2 = 0.0
    for t in range(x.shape[0]):
        v = x[t]
        if np.isnan(v):
            continue
        n += 1
        s1 += v
        s2 += v * v
        if n >= STATE_MIN_HISTORY:
            mu = s1 / n
            var = max(s2 / n - mu * mu, 0.0)
            sd = np.sqrt(var * n / (n - 1)) if n > 1 else 0.0
            out[t] = 0.0 if sd == 0 else float(np.clip((v - mu) / sd, -STATE_CLIP, STATE_CLIP))
    return out


def market_states(returns: np.ndarray) -> np.ndarray:
    """(T, 3): volatility, sum and dispersion states from the equal-weighted market
    row-return, all at rows <= t-2. Each standardised by an expanding window, zero until
    252 rows of history, clipped to [-3, 3]."""
    r = np.asarray(returns, float)
    m = _lagged(r.mean(axis=1)[:, None])[:, 0]
    disp = _lagged(r.std(axis=1)[:, None])[:, 0]
    vol = _trailing(m[:, None], STATE_VOL_ROWS, lambda b: b.std(axis=0, ddof=1))[:, 0]
    tot = _trailing(m[:, None], STATE_SUM_ROWS, lambda b: b.sum(axis=0))[:, 0]
    dsp = _trailing(disp[:, None], STATE_DISP_ROWS, lambda b: b.mean(axis=0))[:, 0]
    return np.stack([_expanding_standardise(vol), _expanding_standardise(tot),
                     _expanding_standardise(dsp)], axis=1)


def unit(p: np.ndarray) -> np.ndarray:
    """Demeaned across assets, scaled to unit gross; a zero row stays zero."""
    d = p - p.mean(axis=1, keepdims=True)
    g = np.abs(d).sum(axis=1, keepdims=True)
    return np.where(g > 0, d / np.where(g > 0, g, 1.0), 0.0)


def rescale_gross(p: np.ndarray) -> np.ndarray:
    g = np.abs(p).sum(axis=1, keepdims=True)
    return np.where(g > 0, p / np.where(g > 0, g, 1.0), 0.0)


def trailing_mean(x: np.ndarray, w: int = SMOOTH) -> np.ndarray:
    """Mean over rows t-w+1..t (fewer at the start), row by row: no later row enters."""
    c = np.cumsum(x, axis=0)
    out = c.copy()
    out[w:] = c[w:] - c[:-w]
    return out / np.minimum(np.arange(1, x.shape[0] + 1), w).reshape((-1,) + (1,) * (x.ndim - 1))


def basis_portfolio(signal: np.ndarray, sig: np.ndarray | None) -> np.ndarray:
    """Weights signal / sigma (risk sizing on) or signal (off), demeaned, unit gross; then
    the average of the last five rows' portfolios, rescaled to unit gross. Rows without a
    sigma give a zero portfolio (they are dropped from every fit)."""
    raw = np.asarray(signal, float)
    if sig is not None:
        raw = np.where(np.isnan(sig), 0.0, raw / np.where(np.isnan(sig), 1.0, sig))
    return rescale_gross(trailing_mean(unit(raw)))


def cost_of(p: np.ndarray, cost_rate: np.ndarray, borrow_rate: np.ndarray) -> np.ndarray:
    """The panel's own cost function: |p_t - p_(t-1)| . cost_rate + short . borrow_rate,
    with p_(-1) = 0 (as `environments.planted_panel.cost_borrow`)."""
    prev = np.vstack([np.zeros((1, p.shape[1])), p[:-1]])
    return (np.einsum("tm,tm->t", np.abs(p - prev), cost_rate)
            + np.einsum("tm,tm->t", np.clip(-p, 0, None), borrow_rate))


def gross_of(p: np.ndarray, returns: np.ndarray) -> np.ndarray:
    return np.einsum("tm,tm->t", p, returns)


def year_chunks(T: int) -> list[tuple[int, int]]:
    """252-row years; the remainder joins as a last, shorter year (3,019 rows: 11 + 247)."""
    n = T // YEAR
    ch = [(YEAR * j, YEAR * (j + 1)) for j in range(n)]
    if T > YEAR * n:
        ch.append((YEAR * n, T))
    return ch


FIRST_TEST_YEAR = 3     # three years of training; positions from year four


def sharpe(x: np.ndarray, ppy: float) -> float:
    x = np.asarray(x, float)
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0


def net_stream(positions: np.ndarray, panel, rows: np.ndarray) -> np.ndarray:
    """The certified stream: net return of the positions on `rows`, under the panel's cost
    function, the book continuous from zero at the first row."""
    p = positions[rows]
    return (gross_of(p, np.asarray(panel.returns, float)[rows])
            - cost_of(p, np.asarray(panel.cost_rate, float)[rows],
                      np.asarray(panel.borrow_rate, float)[rows]))
