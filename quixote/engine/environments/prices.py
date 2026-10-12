"""Price paths and moving-average crossover rules: the non-additive world of non-additive-scoring (non-additive-scoring's prereg, f298103).

A rule's position is the sign of a difference of two moving averages of the log price, so its return
stream is not a linear combination of other rules' streams. That breaks the recursive bootstrap's
reconstruction and `estimator.full_class.full_class_matrix`, which is why non-additive-scoring needs the procedure-level
null and a declared explicit class instead.

Positions depend only on the price path. Nullification shifts the *returns* a rule earns relative to the
positions it held, so positions are computed once per path and reused for every surrogate.
"""
from __future__ import annotations

import numpy as np

DAILY_VOL = 0.01
PERIODS_PER_YEAR = 252


def simulate_walk(n_periods: int, rng: np.random.Generator, warmup: int, daily_vol: float = DAILY_VOL) -> np.ndarray:
    """A driftless random walk's daily log returns, length n_periods + warmup. Driftless so that no rule
    has an edge and any rejection is a type-I error."""
    return rng.normal(0.0, daily_vol, n_periods + warmup)


def rule_positions(r: np.ndarray, rules, warmup: int) -> np.ndarray:
    """(n - warmup, len(rules)): the position each rule holds, from the moving averages its own price path
    showed at the previous close. -1, 0 or +1; long-only rules never go short."""
    n = len(r)
    if warmup < max(s for _, s, _ in rules):
        raise ValueError(f"warmup {warmup} is shorter than the slowest window {max(s for _, s, _ in rules)}")
    cum = np.concatenate([[0.0], np.cumsum(np.cumsum(r))])
    ma = {}
    for w in {w for f, s, _ in rules for w in (f, s)}:
        m = np.full(n, np.nan)
        m[w - 1:] = (cum[w:] - cum[:-w]) / w
        ma[w] = m
    P = np.empty((n - warmup, len(rules)))
    for i, (fast, slow, long_only) in enumerate(rules):
        pos = np.sign(ma[fast][warmup - 1:-1] - ma[slow][warmup - 1:-1])
        P[:, i] = np.maximum(pos, 0.0) if long_only else pos
    return P


def forward_returns(r: np.ndarray, warmup: int) -> np.ndarray:
    """The returns a position held at the previous close earns, aligned with rule_positions' rows."""
    return r[warmup:]


def returns_from_positions(P: np.ndarray, fwd: np.ndarray) -> np.ndarray:
    """(T, N) rule returns. fwd is (T,) for one asset or (T, N) when each column's asset differs."""
    return P * (fwd[:, None] if fwd.ndim == 1 else fwd)


def shifted_surrogate(P: np.ndarray, fwd: np.ndarray, shift: int) -> np.ndarray:
    """Positions from the real path, paired with circularly shifted returns: the price world's analogue of
    estimator.procedure_level_bootstrap.circular_shift_nullify. Destroys the signal-return link while
    preserving each series' own autocorrelation exactly."""
    rolled = np.roll(fwd, shift, axis=0)
    return returns_from_positions(P, rolled)


def shift_pool(T: int, exclude: int) -> np.ndarray:
    """Shifts far enough from zero and from T that they do not nearly preserve the real alignment.
    `exclude` should be at least the slowest moving average (non-additive-scoring's prereg, f298103)."""
    if 2 * exclude >= T:
        raise ValueError(f"exclusion window {exclude} leaves no shifts for T={T}")
    return np.arange(exclude, T - exclude + 1)


def draw_shifts(T: int, exclude: int, n_shifts: int, rng: np.random.Generator) -> np.ndarray:
    """Uniformly without replacement from the pool. Evenly spaced shifts were tested before non-additive-scoring ran and
    give a less stable critical value than random draws (non-additive-scoring's prereg, f298103)."""
    pool = shift_pool(T, exclude)
    if n_shifts > len(pool):
        raise ValueError(f"asked for {n_shifts} shifts but the pool holds {len(pool)}")
    return rng.choice(pool, size=n_shifts, replace=False)


def panel(n_assets: int, n_periods: int, rules, warmup: int, rng: np.random.Generator):
    """Independent price paths sharing one rule grid. Returns (P, fwd) with P (T, n_assets * len(rules))
    and fwd (T, n_assets * len(rules)), so every column carries its own asset's returns."""
    positions, forwards = [], []
    for _ in range(n_assets):
        r = simulate_walk(n_periods, rng, warmup)
        positions.append(rule_positions(r, rules, warmup))
        forwards.append(np.repeat(forward_returns(r, warmup)[:, None], len(rules), axis=1))
    return np.hstack(positions), np.hstack(forwards)
