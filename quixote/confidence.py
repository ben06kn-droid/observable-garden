"""Confidence outputs beside a verdict: `prereg/confidence-output.md` (draft).

From one tier's replicates `reps` (the class tier's `M_b`, or the trigger-replay
replicates `N_b` for the audit tier) and the submitted score `S`:

- **deflated confidence** `C0 = 1 - p`, with `p = (1 + #{reps >= S})/(B + 1)`, the same
  Monte Carlo p-value the tier certifies with;
- **lower bounds** `L_g = S - quantile_g(reps)` for g in {0.90, 0.95, 0.99}
  (`np.quantile`, linear, as the stage-1 driver stored its quantiles);
- **confidence curve** `C(s) = 1 - (1 + #{reps >= S - s})/(B + 1)` on the registered
  81-point grid -1.00, -0.95, ..., 3.00, so `C(0) = C0` exactly;
- **horizon readout** `P_H`: `1 - C` read as a distribution over the population Sharpe
  on the grid (mass below the grid on -1.00, above it on 3.00), integrated against the
  probability that an H-year annualised Sharpe estimate is positive under i.i.d.
  returns, `Phi(s sqrt(H) / sqrt(1 + s^2 / (2 ppy)))`.

**What these are and are not.** Confidence statements under stationarity, resting on P7
(inverting the centred class maximum); not posteriors. **`P_H` is a floor ("at least")
only where the panel has an edge**: V3 (`prereg/confidence-output.md`, "V2 read") found
it understates the realized 5-year outcome in every bin at the planted levels, on the
class tier (`afdcb53`) and the replay tier (`de348ea`), but overstates on panels with no
edge from about 0.4 up. None of this enters a verdict's status.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

GRID = np.round(np.linspace(-1.0, 3.0, 81), 2)
# What V3 measured (prereg/confidence-output.md, "V2 read", afdcb53; replay tier de348ea):
# P_H understated the realized 5-year outcome in every bin at the planted levels, on both
# tiers, so there it is a floor. With no edge (level 0) it overstated from about 0.4 up.
PH_LABEL = ("confidence under stationarity (P7); not a posterior. P_H is a FLOOR, 'at "
            "least', only where the panel has an edge: V3 found it understates the realized "
            "5-year outcome in every bin at the planted levels on both tiers, but overstates "
            "with no edge (level 0) from about 0.4 up (V2 read afdcb53; replay tier de348ea)")
GS = (0.90, 0.95, 0.99)
H_DEFAULT = 5


def _conf_at(reps: np.ndarray, bar: float) -> float:
    return 1.0 - (1.0 + float(np.sum(reps >= bar))) / (reps.size + 1.0)


def curve(S: float, reps) -> np.ndarray:
    """`C(s)` on `GRID`."""
    reps = np.asarray(reps, dtype=float)
    srt = np.sort(reps)
    # #{reps >= S - s} = B - #{reps < S - s}
    n_ge = reps.size - np.searchsorted(srt, S - GRID, side="left")
    return 1.0 - (1.0 + n_ge) / (reps.size + 1.0)


def masses(C: np.ndarray) -> np.ndarray:
    """Mass on each grid point, reading `1 - C` as a distribution function."""
    F = 1.0 - np.asarray(C, dtype=float)
    m = np.diff(F, prepend=0.0)                  # F(s_0) below-or-at the first point
    m[-1] += 1.0 - F[-1]                         # mass above the grid onto 3.00
    return m


def horizon(C: np.ndarray, H: float = H_DEFAULT, ppy: float = 252.0) -> float:
    """`P_H`: the stated probability that the H-year realized Sharpe is positive."""
    s = GRID
    p_pos = norm.cdf(s * np.sqrt(H) / np.sqrt(1.0 + s * s / (2.0 * ppy)))
    return float(np.sum(masses(C) * p_pos))


def confidence(S: float, reps, *, H: float = H_DEFAULT, ppy: float = 252.0,
               tier: str = "") -> dict:
    """Every confidence field for one tier, JSON-ready."""
    reps = np.asarray(reps, dtype=float)
    if reps.ndim != 1 or reps.size == 0:
        raise ValueError("reps must be a non-empty vector of replicate statistics")
    C = curve(float(S), reps)
    return {"tier": tier, "B": int(reps.size), "S": float(S),
            "C0": _conf_at(reps, float(S)),
            "L": {f"{g:.2f}": float(S - np.quantile(reps, g)) for g in GS},
            "grid": [float(GRID[0]), float(GRID[1] - GRID[0]), int(GRID.size)],
            "curve": [float(x) for x in C],
            "H": float(H), "P_H": horizon(C, H, ppy),
            "label": PH_LABEL}
