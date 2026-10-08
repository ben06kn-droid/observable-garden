"""The French 49-industry in-sample loader, and its refusals (draft `prereg/french-panel.md`).

1. **Sealed or quarantined paths** are refused unopened, through
   `data.etf_loader.refuse_sealed_or_quarantined` (`.enc`/`.gpg`/`.asc`, anything under
   `~/Desktop`, where the quarantined zip lives).
2. **Holdout dates.** Any row on or after 2020-01-01 in a file this loader opens refuses
   the whole file. There is no grading flag here: the grading path is not built, and this
   loader never reads the holdout.
"""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import numpy as np

from data.etf_loader import HoldoutRefused, refuse_sealed_or_quarantined

HOLDOUT_START = dt.date(2020, 1, 1)
INSAMPLE_CSV = Path(__file__).resolve().parent / "raw" / "french_insample" / "french49_vw_daily.csv"


def load_insample(path: str | Path = INSAMPLE_CSV) -> tuple[list[dt.date], list[str], np.ndarray]:
    """(dates, industry names, returns in DECIMAL (T, 49)). The file's percent values are
    divided by 100."""
    p = refuse_sealed_or_quarantined(path)
    dates, rows = [], []
    with p.open(newline="") as fh:
        rd = csv.reader(fh)
        cols = next(rd)[1:]
        for row in rd:
            d = dt.date.fromisoformat(row[0])
            if d >= HOLDOUT_START:
                raise HoldoutRefused(
                    f"{p.name} contains {d.isoformat()}, on or after the holdout's first date "
                    f"{HOLDOUT_START.isoformat()}; nothing is loaded from it.")
            dates.append(d)
            rows.append([float(x) for x in row[1:]])
    R = np.asarray(rows, dtype=float) / 100.0
    if R.shape[1] != len(cols) or np.isnan(R).any() or (R <= -0.9999).any():
        raise ValueError(f"{p.name}: malformed or missing values")
    return dates, cols, R
