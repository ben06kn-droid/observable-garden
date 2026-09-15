"""Checks that the Sharpe guards added for SCOPE.md §11 (variance floor, Sharpe
cap) never changed an output in the experiments behind this project's
published numbers.

Re-runs an experiment at its published size with estimator.bootstrap's guard
counters reset, then reports them. `variance_floor` and `sharpe_cap` must stay
at zero; if either binds, a published number came from a replicate with a
degenerate column. `zero_variance` counts exact-zero variances, which the
estimator already mapped to Sharpe 0 before the guards existed. The floor
applies where a full-sample variance is known (the naive bootstrap); the cap
applies everywhere, including recursive-bootstrap replays. Where saved results
exist on disk, p-values are also compared exactly.

Usage: python -m experiments.verify_sharpe_guards {e1,e1_recursive,e4,e9,e11}
"""
from __future__ import annotations

import pickle
import sys
import time

import numpy as np

from estimator import bootstrap


def _e1():
    from experiments.e1_null_calibration import run
    return run(n_draws=200, verbose=False), None


def _e1_recursive():
    from experiments.e1_recursive_calibration import run
    return run(n_draws=200, verbose=False), None


def _e4():
    from experiments.e4_adaptive_n500 import run
    return run(verbose=False), None


def _e9():
    from experiments.e9_predictive_power_v2 import run
    return run(verbose=False), "figures/e9_predictive_power_v2_data.pkl"


def _e11():
    from experiments.e11_power_vs_N_pinned import run
    return run(verbose=False), "figures/e11_power_pinned_data.pkl"


EXPERIMENTS = {"e1": _e1, "e1_recursive": _e1_recursive, "e4": _e4, "e9": _e9, "e11": _e11}


def main(name: str) -> int:
    bootstrap.reset_guard_counts()
    t0 = time.time()
    result, saved_path = EXPERIMENTS[name]()
    counts = dict(bootstrap.GUARD_COUNTS)
    print(f"{name}: guard counters {counts} ({time.time() - t0:.0f}s)")
    if saved_path is not None:
        with open(saved_path, "rb") as f:
            saved = pickle.load(f)
        identical = all(np.array_equal(result[k]["p_value"], saved[k]["p_value"]) for k in saved)
        print(f"{name}: p-values identical to {saved_path}: {identical}")
    bound = counts["variance_floor"] or counts["sharpe_cap"]
    print(f"{name}: " + ("GUARD BOUND: a published number used a degenerate replicate" if bound
                         else "variance floor and Sharpe cap never bound"))
    return 1 if bound else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
