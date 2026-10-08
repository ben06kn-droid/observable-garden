"""Market states and regimes (note, C): version 1's three states (vol, sum, dispersion) from
the panel's own equal-weighted market, with lag 1 + d; each regime splits a state at its
expanding median (rows <= t) and is off until the state is warm (non-zero)."""
from __future__ import annotations

import numpy as np

STATE_VOL_ROWS, STATE_SUM_ROWS, STATE_DISP_ROWS = 63, 63, 21
STATE_MIN_HISTORY, STATE_CLIP = 252, 3.0
REGIMES = ("always", "vol_high", "vol_low", "mkt_up", "mkt_down", "disp_high", "disp_low")


def _lagged(x: np.ndarray, lag: int) -> np.ndarray:
    out = np.full_like(x, np.nan, dtype=float)
    out[lag:] = x[:-lag]
    return out


def _trailing(x: np.ndarray, w: int, fn) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    for t in range(w - 1, x.shape[0]):
        blk = x[t - w + 1:t + 1]
        if not np.isnan(blk).any():
            out[t] = fn(blk)
    return out


def _expanding_standardise(x: np.ndarray) -> np.ndarray:
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


def market_states(earned: np.ndarray, d: int) -> np.ndarray:
    """(T, 3). With d = 1 this is `learn.inputs.market_states` exactly (tested)."""
    r = np.asarray(earned, float)
    lag = 1 + d
    m = _lagged(r.mean(axis=1), lag)
    disp = _lagged(r.std(axis=1), lag)
    vol = _trailing(m, STATE_VOL_ROWS, lambda b: b.std(ddof=1))
    tot = _trailing(m, STATE_SUM_ROWS, lambda b: b.sum())
    dsp = _trailing(disp, STATE_DISP_ROWS, lambda b: b.mean())
    return np.stack([_expanding_standardise(vol), _expanding_standardise(tot),
                     _expanding_standardise(dsp)], axis=1)


def _above_median(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(high, warm): x_t above the expanding median of the warm values at rows <= t."""
    import bisect
    T = len(x)
    high = np.zeros(T, bool)
    warm = x != 0
    hist: list[float] = []
    for t in range(T):
        if not warm[t]:
            continue
        bisect.insort(hist, float(x[t]))
        n = len(hist)
        med = hist[n // 2] if n % 2 else 0.5 * (hist[n // 2 - 1] + hist[n // 2])
        high[t] = x[t] > med
    return high, warm


def regime_gates(states: np.ndarray) -> dict:
    """{regime: (T,) bool on/off}; every gated regime is off until its state is warm."""
    gates = {"always": np.ones(states.shape[0], bool)}
    for k, name in enumerate(("vol", "mkt", "disp")):
        high, warm = _above_median(states[:, k])
        hi_name, lo_name = (("mkt_up", "mkt_down") if name == "mkt" else (f"{name}_high", f"{name}_low"))
        gates[hi_name] = high & warm
        gates[lo_name] = ~high & warm
    return gates
