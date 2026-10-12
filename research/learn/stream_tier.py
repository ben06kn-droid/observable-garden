"""The class tier over supplied streams (`prereg/ml-pipeline-exploratory-2026-10-07.md`, a):
a declared pipeline's walk-forward net stream, or a menu of them, priced exactly as a
class whose members are those streams. Existing code end to end: `ClassTable` from the
streams, `null_max` over stationary-bootstrap rows, the class p-value, `confidence()` and
`render()`.

The bootstrap window is the scored days only, and the block length is the class rule
(`select_block_length` on the demeaned base columns), applied to that window. Both are
fixed at registration; this module takes the base columns of the window as an input.
"""
from __future__ import annotations

import numpy as np

ALPHA = 0.05


def table_from_streams(streams: np.ndarray, ppy: float):
    from environments.class_table import ClassTable, canonical
    S = np.atleast_2d(np.asarray(streams, float))
    members = [((i, 1.0),) for i in range(S.shape[0])]
    return ClassTable(streams=S, members=members,
                      index={canonical(m): i for i, m in enumerate(members)},
                      panel_hash="supplied-streams", periods_per_year=float(ppy))


def bootstrap_rows(base_columns: np.ndarray, B: int, seed: int):
    """The class null's rows: block length by the class rule on the demeaned base columns
    of the window, `default_rng(seed)`, one stationary-bootstrap draw per replicate."""
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    bc = np.asarray(base_columns, float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(seed)
    return [stationary_bootstrap_indices(bc.shape[0], L, rng) for _ in range(B)], L


def certify(streams: np.ndarray, base_columns: np.ndarray, ppy: float, B: int, seed: int,
            submitted: int | None = None) -> dict:
    """p, M_b, confidence and the rendered line for the submitted stream (by default the
    best of the menu, as the class tier prices its maximum)."""
    from quixote.confidence import confidence, render
    table = table_from_streams(streams, ppy)
    rows, L = bootstrap_rows(base_columns, B, seed)
    M_b = table.null_max(rows)
    scores = [table.sharpe(((i, 1.0),)) for i in range(table.N)]
    sub = int(np.argmax(scores)) if submitted is None else int(submitted)
    S = scores[sub]
    p = (1 + int(np.sum(M_b >= S))) / (B + 1)
    conf = confidence(S, M_b, ppy=float(ppy), tier="declared stream")
    return {"p": p, "status": "CERTIFIED" if p < ALPHA else "FAIL", "score": S,
            "submitted": sub, "null_max": M_b, "block_length": L, "B": B,
            "confidence": conf, "text": render(conf, certified=p < ALPHA)}
