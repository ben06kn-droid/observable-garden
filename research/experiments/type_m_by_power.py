"""Type-M exaggeration as a function of power, oversampled where it matters.

predictive-power's pooled figure (passing results overstate the true Sharpe by 1.84x) is
dominated by high-power cells, because those are the cells that pass. The
gate's type-M warning fires below 20% power, so it needs the exaggeration
measured there, not pooled from elsewhere.

Design: power-vs-signal's regime (rho=0, K=40, M=60, T=600, GridSearch over subsets up
to size 3, argmax submission) at one breadth, N=100, sweeping the target
oracle Sharpe so power moves from near alpha to high. Holding N, rho and T
fixed keeps the null maximum and the Sharpe standard error roughly fixed
across cells, so power moves only with effect size. Each cell draws until it
has MIN_PASSES passing draws or MAX_DRAWS draws. A draw's bootstrap stops as
soon as its exceedance count guarantees p >= alpha; that is exact (same
pass/fail as the full B) and makes failing draws cheap.

Per passing draw: sr_deflated from the full-B bootstrap, the submitted
spec's analytic true Sharpe, and the gate's single-strategy power at a
reference equal to that true Sharpe.

Prediction, stated before running: among passing draws, both the
exaggeration ratio mean(sr_deflated) / mean(true Sharpe) and the absolute
overstatement mean(sr_deflated - true Sharpe) rise monotonically as cell
power falls. A flat or non-monotone curve falsifies scaling the gate's
warning by power.

Usage: python -m experiments.type_m_by_power
"""
from __future__ import annotations

import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, analytic_sharpe, calibrate_sigma, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length
from estimator.metrics import wilson_ci
from garden._engine import null_max_bootstrap
from garden.power import bootstrap_power, critical_value
from searchers.scripted import GridSearch

TARGET_SHARPE_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
N = 100
RHO, K = 0.0, 40
M, T, T_OOS = 60, 600, 300
B, ALPHA, CHUNK = 1500, 0.05, 150
MIN_PASSES, MAX_DRAWS = 200, 8000
SEED0 = 3_000_000
MAX_EXCEED = int(np.sum((1 + np.arange(B + 1)) / (B + 1) < ALPHA)) - 1


def run_draw(target_sharpe: float, seed: int) -> dict:
    template = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=1.0, seed=seed, heterogeneous=True)
    sigma = calibrate_sigma(target_sharpe, template)
    config = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=3, rho=RHO, sigma=sigma, seed=seed, heterogeneous=True)
    ann = np.sqrt(config.periods_per_year)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    GridSearch(subset_sizes=(1, 2, 3), max_trials=N, seed=seed).run(sandbox)
    spec, dist = sandbox.submission
    R = sandbox.returns_matrix()
    j = next(e.call_index for e in sandbox.transcript if np.array_equal(e.spec.weights, spec.weights))
    sr, sr_true = float(dist.mean), float(analytic_sharpe(config, spec.weights))

    L = select_block_length(R - R.mean(axis=0))
    null, tracked, exceed = [], [], 0
    for c in range(B // CHUNK):
        res = null_max_bootstrap(R, B=CHUNK, block_length=L, annualization=ann, seed=seed * 100 + c, track_index=j)
        null.append(res.M_b)
        tracked.append(res.tracked)
        exceed += int(np.sum(res.M_b >= sr))
        if exceed > MAX_EXCEED:
            return {"passed": False, "sr_is": sr, "sr_true": sr_true}
    null, tracked = np.concatenate(null), np.concatenate(tracked)
    return {
        "passed": True, "sr_is": sr, "sr_true": sr_true, "sr_deflated": sr - float(null.mean()),
        "gate_power_at_true": bootstrap_power(tracked, sr_true, critical_value(null, ALPHA)),
    }


def run_cell(target_sharpe: float) -> list[dict]:
    draws, n_pass = [], 0
    while n_pass < MIN_PASSES and len(draws) < MAX_DRAWS:
        d = run_draw(target_sharpe, SEED0 + len(draws))
        draws.append(d)
        n_pass += d["passed"]
    return draws


def run(verbose: bool = True) -> dict:
    results, t0 = {}, time.time()
    for target in TARGET_SHARPE_LEVELS:
        results[target] = run_cell(target)
        if verbose:
            n_pass = sum(d["passed"] for d in results[target])
            print(f"  target={target}: {n_pass} passes / {len(results[target])} draws ({time.time() - t0:.0f}s)")
    return results


def summarize(results: dict, n_boot: int = 4000) -> list[dict]:
    rng = np.random.default_rng(0)
    rows = []
    for target, draws in results.items():
        passed = [d for d in draws if d["passed"]]
        defl = np.array([d["sr_deflated"] for d in passed])
        true = np.array([d["sr_true"] for d in passed])
        idx = rng.integers(len(passed), size=(n_boot, len(passed)))
        ratios = defl[idx].mean(axis=1) / true[idx].mean(axis=1)
        gaps = (defl - true)[idx].mean(axis=1)
        rows.append({
            "target": target, "draws": len(draws), "passes": len(passed),
            "power": len(passed) / len(draws), "power_ci": wilson_ci(len(passed), len(draws)),
            "ratio": defl.mean() / true.mean(), "ratio_ci": tuple(np.percentile(ratios, [2.5, 97.5])),
            "gap": float((defl - true).mean()), "gap_ci": tuple(np.percentile(gaps, [2.5, 97.5])),
            "mean_true_pass": float(true.mean()),
            "gate_power_median": float(np.median([d["gate_power_at_true"] for d in passed])),
        })
    return sorted(rows, key=lambda r: r["power"])


def report(rows: list[dict]) -> None:
    print(f"\nN={N}, rho={RHO}, K={K}, T={T}, B={B}; passing draws only\n")
    print(f"{'target':>6} {'draws':>6} {'passes':>6} {'power (95% CI)':>20} {'true|pass':>9} "
          f"{'ratio (95% CI)':>22} {'gap (95% CI)':>24} {'gate power':>10}")
    for r in rows:
        print(f"{r['target']:>6} {r['draws']:>6} {r['passes']:>6} "
              f"{r['power']:>6.3f} ({r['power_ci'][0]:.3f}-{r['power_ci'][1]:.3f}) {r['mean_true_pass']:>9.3f} "
              f"{r['ratio']:>6.2f} ({r['ratio_ci'][0]:>5.2f}-{r['ratio_ci'][1]:>5.2f}) "
              f"{r['gap']:>+7.3f} ({r['gap_ci'][0]:+.3f} to {r['gap_ci'][1]:+.3f}) {r['gate_power_median']:>10.3f}")
    for key in ("ratio", "gap"):
        values = [r[key] for r in rows]
        monotone = all(a >= b for a, b in zip(values, values[1:]))
        print(f"\n{key} non-increasing as power rises (prediction): {'HOLDS' if monotone else 'FALSIFIED'}")


if __name__ == "__main__":
    results = run()
    rows = summarize(results)
    report(rows)
    with open("figures/type_m_by_power_data.pkl", "wb") as f:
        pickle.dump({"draws": results, "summary": rows}, f)
