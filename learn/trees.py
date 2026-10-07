"""The small boosted-tree model, fixed (`prereg/ml-pipeline-exploratory-2026-10-07.md`).
LightGBM 4.7.0, pinned by wheel SHA-256 in the note."""
from __future__ import annotations

import numpy as np

TREES = dict(objective="regression", num_leaves=4, max_depth=2, learning_rate=0.1,
             min_data_in_leaf=200, max_bin=63, num_threads=1, deterministic=True,
             force_row_wise=True, verbose=-1, seed=1)
NTREE = 50
PINNED_VERSION = "4.7.0"


def fit(X: np.ndarray, y: np.ndarray):
    import lightgbm as lgb
    if lgb.__version__ != PINNED_VERSION:
        raise RuntimeError(f"LightGBM {lgb.__version__}, not the pinned {PINNED_VERSION}")
    return lgb.train(TREES, lgb.Dataset(np.asarray(X, np.float64), np.asarray(y, np.float64)),
                     num_boost_round=NTREE)


def oof_predictions(X_rows: list[np.ndarray], y_rows: list[np.ndarray], gap: int) -> list:
    """Out-of-fold predictions over a training window given as a list of row blocks (one
    (M, F) array per row, in time order): three blocked folds, `gap` rows removed from the
    training side at each fold edge. Returns one (M,) prediction per row."""
    n = len(X_rows)
    ed = np.linspace(0, n, 4).astype(int)
    out = [None] * n
    for k in range(3):
        keep = [i for i in range(n) if i < ed[k] - gap or i >= ed[k + 1] + gap]
        if not keep:
            continue
        model = fit(np.concatenate([X_rows[i] for i in keep]),
                    np.concatenate([y_rows[i] for i in keep]))
        hold = list(range(ed[k], ed[k + 1]))
        pred = model.predict(np.concatenate([X_rows[i] for i in hold])) if hold else []
        M = X_rows[0].shape[0]
        for j, i in enumerate(hold):
            out[i] = pred[j * M:(j + 1) * M]
    return out
