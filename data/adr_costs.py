"""7.4 spread estimators on 5-minute bars, as registered in prereg/adr-features.md
amendment 1 (A1, A2).

Pure functions of arrays. Nothing here reads a bar from disk, so the ancestor
guard belongs to the entry point that loads the panel, not to this module.

- `abdi_ranaldo` is the primary: for consecutive bars t, t+1 within a session,
  with c the log close and eta the log mid-range (log high + log low) / 2,
  s^2 = max(0, 4 * mean[(c_t - eta_t)(c_t - eta_{t+1})]). Abdi and Ranaldo
  (2017), RFS 30(12) 4437-4480; formula checked against the `bidask` package
  source (CRAN 2.1.5), not the paper's text.
- `roll` is the cross-check: s = 2 * sqrt(max(0, -cov(r_t, r_{t-1}))) over
  within-session log returns. Roll (1984), JF 39(4) 1127-1139. It is not the
  primary because it is the lag-1 autocovariance the lag-1 feature trades on.
- `floored` applies A2's floor, max(one cent / previous close, 2 bps).

Every estimate is a proportional spread in log units (0.0010 = 10 bps). Pairs
never cross a session boundary: each argument is a list of per-session arrays.
"""
from __future__ import annotations

import numpy as np

FLOOR_BPS = 2.0
FLOOR_CENTS = 0.01


def _pairs_ar(high, low, close) -> np.ndarray:
    c = np.log(np.asarray(close, dtype=float))
    eta = (np.log(np.asarray(high, dtype=float)) + np.log(np.asarray(low, dtype=float))) / 2
    return (c[:-1] - eta[:-1]) * (c[:-1] - eta[1:])


def abdi_ranaldo(sessions_high, sessions_low, sessions_close) -> float:
    """Spread from every consecutive-bar pair inside each session. The caller
    passes only the sessions BEFORE the one being priced (A1: the 20 prior)."""
    prods = [_pairs_ar(h, l, c) for h, l, c in zip(sessions_high, sessions_low, sessions_close)
             if len(c) >= 2]
    if not prods:
        return float("nan")
    m = np.concatenate(prods)
    m = m[np.isfinite(m)]
    if m.size == 0:
        return float("nan")
    return float(np.sqrt(max(0.0, 4.0 * m.mean())))


def roll(sessions_close) -> tuple[float, float]:
    """(spread, covariance). The covariance is returned so the readout can count
    how often it is positive, which is when Roll is undefined (spread 0)."""
    r1, r0 = [], []
    for c in sessions_close:
        lc = np.log(np.asarray(c, dtype=float))
        r = np.diff(lc)
        if r.size >= 2:
            r1.append(r[1:])
            r0.append(r[:-1])
    if not r1:
        return float("nan"), float("nan")
    a, b = np.concatenate(r1), np.concatenate(r0)
    cov = float(np.mean(a * b) - a.mean() * b.mean())
    return float(2.0 * np.sqrt(max(0.0, -cov))), cov


def floored(spread: float, prev_close: float) -> float:
    """A2: max(estimate, one cent / previous close, 2 bps)."""
    return float(max(spread, FLOOR_CENTS / prev_close, FLOOR_BPS * 1e-4))
