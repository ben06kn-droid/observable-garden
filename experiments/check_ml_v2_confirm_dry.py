"""Checker for the version-2 confirmation's dry run: `check_ml_v2_dry` with this runner's
row counts (a seed task writes 2 rows, a level-0 task 1). Prints no value.

    python -m experiments.check_ml_v2_confirm_dry --dir runs/ml_v2_confirm_dry/2026-10-09
"""
from __future__ import annotations

import sys

from experiments import check_ml_v2_dry as C

C.EXPECTED_ROWS = {"seed": 2, "level0": 1}

if __name__ == "__main__":
    raise SystemExit(C.main(sys.argv[1:]))
