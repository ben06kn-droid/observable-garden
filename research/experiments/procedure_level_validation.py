"""Validates the cheap recursive column bootstrap (estimator/
recursive_bootstrap.py) against the gold-standard procedure-level bootstrap
(estimator/procedure_level_bootstrap.py) for Adaptive. The column-level
version needs Specification's linearity to reconstruct never-evaluated
candidates; the procedure-level version needs nothing but the ability to
re-run the searcher, so it's correct by construction but B times more
expensive (every evaluate() call the real search makes, repeated B times).

If they agree, the cheap version is earned for cases where the
reconstruction is available. If they disagree, the reconstruction was
hiding something the mechanism-level argument in SCOPE.md missed.

Usage: python -m experiments.procedure_level_validation
"""
from __future__ import annotations

import time

import numpy as np
from scipy.stats import ks_2samp

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe
from estimator.procedure_level_bootstrap import procedure_level_bootstrap
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from searchers.scripted import Adaptive


def compare_one_draw(seed, M=60, T=600, T_oos=200, K=20, B=300, max_features=3):
    config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed)
    data = generate(config)
    ann = np.sqrt(config.periods_per_year)

    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    base_columns = sandbox.base_feature_columns()

    recursive = recursive_null_max_bootstrap(
        base_columns, Adaptive(max_features=max_features, seed=seed), B=B, annualization=ann, seed=seed,
    )
    procedure = procedure_level_bootstrap(
        data, lambda: Adaptive(max_features=max_features, seed=seed), B=B,
        periods_per_year=config.periods_per_year, seed=seed,
    )
    return recursive.M_b, procedure


def run(n_draws=15, seed0=40_000, B=300, **kwargs):
    t0 = time.time()
    means_recursive, means_procedure = [], []
    for i in range(n_draws):
        M_b_recursive, M_b_procedure = compare_one_draw(seed0 + i, B=B, **kwargs)
        means_recursive.append(M_b_recursive.mean())
        means_procedure.append(M_b_procedure.mean())
        stat, p = ks_2samp(M_b_recursive, M_b_procedure)
        print(f"draw {i+1}/{n_draws}  mean_null_max: recursive={M_b_recursive.mean():.4f}  "
              f"procedure={M_b_procedure.mean():.4f}  diff={M_b_recursive.mean()-M_b_procedure.mean():+.4f}  "
              f"2-sample KS p={p:.3f}  ({time.time()-t0:.1f}s elapsed)")

    means_recursive, means_procedure = np.array(means_recursive), np.array(means_procedure)
    diffs = means_recursive - means_procedure
    print(f"\nmean diff (recursive - procedure) across {n_draws} draws: {diffs.mean():+.4f} "
          f"(std {diffs.std(ddof=1):.4f})")


if __name__ == "__main__":
    run()
