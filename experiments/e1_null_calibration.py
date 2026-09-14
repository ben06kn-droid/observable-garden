"""Experiment 1 (spec §4.1): the pass/fail gate for the whole project.

Under a pure-null DGP (s=0, no feature has any predictive power), the
bootstrap's p-value must be ~Uniform(0,1) for every searcher at every trial
budget, regardless of how hard the searcher searched. A correct
null-maximum estimator does not care why a transcript looks the way it
does -- only its observed correlation structure. If GridSearch (large N,
correlated trials) or Adaptive (sequential trials) produce p-values
concentrated near zero, the bootstrap is under-correcting for search
breadth and the method is broken.

Usage:
    python -m experiments.e1_null_calibration --n-draws 500
"""
from __future__ import annotations

import argparse
import time

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import deflate
from searchers.scripted import Honest, Greedy, GridSearch, Adaptive

SEARCHER_FACTORIES = {
    "honest": lambda seed: Honest(seed=seed),
    "greedy": lambda seed: Greedy(seed=seed),
    "gridsearch": lambda seed: GridSearch(subset_sizes=(1, 2, 3), max_trials=1500, seed=seed),
    "adaptive": lambda seed: Adaptive(max_features=3, seed=seed),
}


def run(
    n_draws: int = 100,
    M: int = 100,
    T: int = 1000,
    T_oos: int = 500,
    K: int = 30,
    B: int = 2000,
    seed0: int = 10_000,
    verbose: bool = True,
) -> dict[str, np.ndarray]:
    p_values: dict[str, list[float]] = {name: [] for name in SEARCHER_FACTORIES}
    t0 = time.time()

    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=T_oos, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        data = generate(config)

        for name, factory in SEARCHER_FACTORIES.items():
            sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
            factory(seed0 + i).run(sandbox)
            R = sandbox.returns_matrix()
            result = deflate(R, B=B, seed=seed0 + i)
            p_values[name].append(result.p_value)

        if verbose and (i + 1) % max(1, n_draws // 10) == 0:
            elapsed = time.time() - t0
            print(f"  draw {i+1}/{n_draws}  ({elapsed:.1f}s elapsed)")

    return {name: np.array(vals) for name, vals in p_values.items()}


def report(p_values: dict[str, np.ndarray]) -> dict[str, tuple[float, float]]:
    results = {}
    print(f"\n{'searcher':<12} {'mean N':>8} {'KS stat':>10} {'KS p-value':>12}  verdict")
    for name, p in p_values.items():
        stat, ks_p = kstest(p, "uniform")
        results[name] = (stat, ks_p)
        verdict = "PASS (uniform)" if ks_p > 0.05 else "FAIL (not uniform)"
        print(f"{name:<12} {'':>8} {stat:>10.4f} {ks_p:>12.4f}  {verdict}")
    return results


def plot(p_values: dict[str, np.ndarray], out_path: str = "figures/e1_null_calibration.png") -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="U(0,1) reference")
    for name, p in p_values.items():
        x = np.sort(p)
        y = np.arange(1, len(x) + 1) / len(x)
        ax.step(x, y, where="post", label=name)
    ax.set_xlabel("p-value")
    ax.set_ylabel("empirical CDF")
    ax.set_title("Experiment 1: null calibration (s=0)")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-draws", type=int, default=100)
    parser.add_argument("--M", type=int, default=100)
    parser.add_argument("--T", type=int, default=1000)
    parser.add_argument("--K", type=int, default=30)
    parser.add_argument("--B", type=int, default=2000)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    pvals = run(n_draws=args.n_draws, M=args.M, T=args.T, K=args.K, B=args.B)
    report(pvals)
    if not args.no_plot:
        plot(pvals)
