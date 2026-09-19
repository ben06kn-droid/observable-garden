"""null-calibration found that Adaptive fails null calibration while Honest/Greedy/
GridSearch pass (see README, "Days 7-9"). This isolates why.

Hypothesis: it is specifically the OUTCOME-CONDITIONAL construction of
later-round trials -- round 2's candidates are "the data-chosen best single
feature, plus one more" -- not merely N, not merely correlated trials.
Greedy and GridSearch both choose their trial menu without reference to the
realized outcomes (GridSearch's random subsample is seeded independently of
any Sharpe value); Adaptive's round-2+ menu is a function of which single
won round 0, which is itself a function of the realized null noise.

Control: PseudoAdaptive has the identical round structure and trial count as
Adaptive, but always extends a FIXED anchor feature (index 0) instead of the
data-chosen winner -- removing the outcome-conditional menu construction
while keeping everything else (N, rounds, correlated overlapping subsets)
the same. If PseudoAdaptive is calibrated where Adaptive is not, the
adaptivity itself is the driver.

Usage: python -m experiments.diagnose_adaptive_calibration
"""
from __future__ import annotations

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox, Specification, Distribution
from estimator.bootstrap import deflate
from searchers.base import Searcher
from searchers.scripted import Adaptive, _one_hot_sum


class PseudoAdaptive(Searcher):
    """Same round structure and trial count as Adaptive, but round-2+
    candidates always extend a fixed anchor feature rather than the
    data-chosen round-0 winner."""
    name = "pseudo_adaptive"

    def __init__(self, max_features: int = 3, anchor: int = 0, seed: int = 0):
        super().__init__(seed=seed)
        self.max_features = max_features
        self.anchor = anchor

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features
        for k in range(K):  # log the same N=K singles as Adaptive, for a matched transcript shape
            sandbox.evaluate(Specification(weights=_one_hot_sum(K, [k]), name=f"pa_f{k}"))

        support = [self.anchor]
        remaining = set(range(K)) - {self.anchor}
        best_sharpe = sandbox.evaluate(Specification(weights=_one_hot_sum(K, support), name="pa_anchor")).sharpe

        for _ in range(self.max_features - 1):
            round_best = None
            for k in remaining:
                trial_support = support + [k]
                result = sandbox.evaluate(Specification(weights=_one_hot_sum(K, trial_support), name=f"pa_{trial_support}"))
                if round_best is None or result.sharpe > round_best[1]:
                    round_best = (k, result.sharpe)
            if round_best is None or round_best[1] <= best_sharpe:
                break
            support.append(round_best[0])
            remaining.discard(round_best[0])
            best_sharpe = round_best[1]

        spec = Specification(weights=_one_hot_sum(K, support), name=f"pa_final_{support}")
        sandbox.submit(spec, Distribution.degenerate(best_sharpe))


def run_variant(searcher_factory, n_draws, M, T, K, B, seed0):
    p_values, ns = [], []
    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=200, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        data = generate(config)
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        searcher_factory(seed0 + i).run(sandbox)
        result = deflate(sandbox.returns_matrix(), B=B, seed=seed0 + i)
        p_values.append(result.p_value)
        ns.append(sandbox.returns_matrix().shape[1])
    return np.array(p_values), np.array(ns)


if __name__ == "__main__":
    n_draws, M, T, K, B, seed0 = 80, 80, 800, 30, 1500, 77_000
    variants = {
        "adaptive": lambda s: Adaptive(max_features=3, seed=s),
        "pseudo_adaptive": lambda s: PseudoAdaptive(max_features=3, seed=s),
    }
    print(f"{'variant':<16} {'mean_p':>8} {'frac_p<0.05':>12} {'KS_stat':>9} {'KS_pvalue':>10} {'mean_N':>8}")
    for name, factory in variants.items():
        p, n = run_variant(factory, n_draws, M, T, K, B, seed0)
        stat, ks_p = kstest(p, "uniform")
        print(f"{name:<16} {p.mean():>8.3f} {(p < 0.05).mean():>12.3f} {stat:>9.4f} {ks_p:>10.4f} {n.mean():>8.1f}")
