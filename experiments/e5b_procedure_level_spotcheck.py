"""Procedure-level (gold-standard) validation spot-check for the dose-
response sweep (experiments/e5_dose_response.py). Not run for all 7
variants -- LatticeAdaptive's menu is provably data-oblivious (naive and
recursive are mathematically identical for it, as for Greedy/GridSearch;
see SCOPE.md section 1), so a reconstruction-free check adds nothing there.
Adaptive (k=1) was already validated this way at n=500
(experiments/e4_adaptive_n500.py vs the original oracle bootstrap). This
spot-checks the genuinely new points: BeamAdaptive(4), BeamAdaptive(2), and
NeighborAdaptive -- one from the dose axis' middle, one near its data-
dependent end, and the structural variant with a different selection rule.

Usage: python -m experiments.e5b_procedure_level_spotcheck
"""
from __future__ import annotations

import time

import numpy as np
from scipy.stats import ks_2samp

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.procedure_level_bootstrap import procedure_level_bootstrap
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from searchers.dose_response import BeamAdaptive, NeighborAdaptive

VARIANTS = {
    "beam4": lambda seed: BeamAdaptive(beam_width=4, max_features=3, seed=seed),
    "beam2": lambda seed: BeamAdaptive(beam_width=2, max_features=3, seed=seed),
    "neighbor_adaptive": lambda seed: NeighborAdaptive(max_features=3, seed=seed),
}


def run(n_draws=15, M=50, T=500, T_oos=200, K=20, B=300, seed0=60_000):
    t0 = time.time()
    for name, factory in VARIANTS.items():
        diffs = []
        for i in range(n_draws):
            config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
            data = generate(config)
            ann = np.sqrt(config.periods_per_year)

            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            base_columns = sandbox.base_feature_columns()
            recursive = recursive_null_max_bootstrap(
                base_columns, factory(seed0 + i), B=B, annualization=ann, seed=seed0 + i,
            )
            procedure = procedure_level_bootstrap(
                data, lambda: factory(seed0 + i), B=B, periods_per_year=config.periods_per_year, seed=seed0 + i,
            )
            diffs.append(recursive.mean_null_max - procedure.mean())

        diffs = np.array(diffs)
        print(f"{name:<20} n={n_draws}  mean diff (recursive-procedure) = {diffs.mean():+.4f} "
              f"(SD {diffs.std(ddof=1):.4f})  ({time.time()-t0:.1f}s elapsed)")


if __name__ == "__main__":
    run()
