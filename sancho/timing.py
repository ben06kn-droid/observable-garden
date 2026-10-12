"""Timing (note, A): feature row t earns the return of row t + 1 + d.

`earned` (T, M) is a panel's `returns`: earned[t] is the return of row t + 1 + d. The row
return known at the close of row t is earned[t - 1 - d]."""
from __future__ import annotations

import numpy as np


def delay(panel) -> int:
    d = int(getattr(panel, "meta", {}).get("delay", 1))
    if d not in (0, 1):
        raise ValueError(f"delay {d} is not 0 or 1")
    return d


def known_returns(earned: np.ndarray, d: int) -> np.ndarray:
    """Row t holds the row return known at the close of t (earned[t-1-d]); NaN before."""
    lag = 1 + d
    out = np.full_like(np.asarray(earned, float), np.nan)
    out[lag:] = earned[:-lag]
    return out


def forward_sum(earned: np.ndarray, h: int) -> np.ndarray:
    """Row t holds sum earned[t .. t+h-1] (the forward h-row return of a position formed
    at t); NaN where it runs past the end."""
    E = np.asarray(earned, float)
    T = E.shape[0]
    c = np.vstack([np.zeros((1,) + E.shape[1:]), np.cumsum(E, axis=0)])
    out = np.full_like(E, np.nan)
    out[:T - h + 1] = c[h:] - c[:-h]
    return out


def embargo(h: int, d: int) -> int:
    return h + 1 + d
