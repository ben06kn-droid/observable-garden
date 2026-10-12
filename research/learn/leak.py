"""The leak test (`prereg/ml-pipeline-exploratory-2026-10-07.md`, d): for several random
rows d, replace every feature and return after row d; the positions at rows <= d must be
bit-identical."""
from __future__ import annotations

import dataclasses

import numpy as np


@dataclasses.dataclass
class Arrays:
    features: np.ndarray
    returns: np.ndarray
    cost_rate: np.ndarray
    borrow_rate: np.ndarray
    periods_per_year: float


def perturb_after(panel, d: int, rng) -> Arrays:
    F = np.array(panel.features, float, copy=True)
    R = np.array(panel.returns, float, copy=True)
    F[d + 1:] = rng.standard_normal(F[d + 1:].shape)
    R[d + 1:] = rng.standard_normal(R[d + 1:].shape) * 0.02
    return Arrays(F, R, np.asarray(panel.cost_rate, float), np.asarray(panel.borrow_rate, float),
                  float(panel.periods_per_year))


def leak_test(run, panel, rows_d, seed: int = 0) -> list[dict]:
    """`run(panel)` returns a dict with "positions" (T, M). Each d: positions at rows <= d
    with and without the change after d, compared bit for bit."""
    base = run(panel)["positions"]
    rng = np.random.default_rng(seed)
    out = []
    for d in rows_d:
        alt = run(perturb_after(panel, int(d), rng))["positions"]
        same = bool(np.array_equal(base[:d + 1], alt[:d + 1]))
        changed_after = bool(not np.array_equal(base[d + 1:], alt[d + 1:]))
        out.append({"d": int(d), "identical_up_to_d": same, "changed_after_d": changed_after})
    return out
