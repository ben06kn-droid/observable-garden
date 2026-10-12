"""Mechanistic confirmation of why Adaptive fails null-calibration (see README, "Days 7-9",
and diagnose_adaptive_calibration.py for the PseudoAdaptive control that
first isolated adaptivity as the driver).

The claim: the null_max_bootstrap in estimator/bootstrap.py resamples the
OBSERVED transcript's fixed weight vectors -- for Adaptive, that means every
replicate reuses "feature W_orig + feature j" for round 2, where W_orig is
the SPECIFIC feature that won round 1 on the ACTUAL data. A properly
specified null bootstrap of an adaptive procedure must instead let the
round-1 winner be RE-DERIVED from each replicate's own resampled data (Efron
2014, "Estimation and Accuracy after Model Selection", JASA -- the bootstrap
must re-run the selection step, not hold the selected model fixed).

This is checkable directly here because Specification is linear and every
period's noise is shared across specs within a draw: pair(a,b)'s return
series is EXACTLY single(a) + single(b), elementwise (verified to floating
point precision separately). So an "oracle" bootstrap can reconstruct any
hypothetical round-2/3 candidate -- for any hypothetical round-1 winner --
directly from the K single-feature columns already in the transcript,
without needing to re-run the sandbox. Two things to check:

  1. Does the oracle (re-derive-the-winner-each-replicate) bootstrap give a
     LARGER mean_null_max than the naive (fixed-transcript) bootstrap, as
     the theory predicts (naive underestimates the true adaptive null max)?
  2. Does substituting it into null-calibration's null-calibration check restore
     uniformity for Adaptive?

Usage: python -m experiments.verify_selective_inference_theory
"""
from __future__ import annotations

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe, select_block_length, stationary_bootstrap_indices, null_max_bootstrap
from searchers.scripted import Adaptive


def recursive_bootstrap_null_max(
    singles: np.ndarray,       # (T, K) — the K single-feature columns, RAW (not yet demeaned)
    B: int = 1500,
    max_features: int = 3,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> np.ndarray:
    """Re-runs Adaptive's OWN selection rule inside every bootstrap replicate,
    re-deriving each round's winner from that replicate's resampled data,
    instead of reusing the winner observed in the real (unresampled) run."""
    T, K = singles.shape
    S0 = singles - singles.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(S0)
    rng = np.random.default_rng(seed)

    M_b = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        S = S0[idx, :]                                   # (T, K), one joint time resample
        sr_singles = sharpe(S, axis=0, annualization=annualization)
        w = int(np.argmax(sr_singles))
        best_sr = sr_singles[w]
        support_sum = S[:, w].copy()
        remaining = set(range(K)) - {w}

        for _ in range(max_features - 1):
            round_best_sr, round_best_j, round_best_series = -np.inf, None, None
            for j in remaining:
                candidate = support_sum + S[:, j]         # exact pair/triple reconstruction
                sr = sharpe(candidate[:, None], axis=0, annualization=annualization)[0]
                if sr > round_best_sr:
                    round_best_sr, round_best_j, round_best_series = sr, j, candidate
            if round_best_j is None or round_best_sr <= best_sr:
                break
            support_sum, best_sr = round_best_series, round_best_sr
            remaining.discard(round_best_j)

        M_b[b] = best_sr
    return M_b


def compare_single_draw(K=30, M=80, T=800, B=1500, seed=1):
    config = DGPConfig(M=M, T=T, T_oos=200, K=K, s=0, rho=0.3, sigma=1.0, seed=seed)
    data = generate(config)
    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    Adaptive(max_features=3, seed=seed).run(sandbox)
    R = sandbox.returns_matrix()
    sr_sel = float(sharpe(R, axis=0).max())

    naive = null_max_bootstrap(R, B=B, seed=seed)
    singles = R[:, :K]  # round-0 columns are logged first, K of them, by construction
    oracle_M_b = recursive_bootstrap_null_max(singles, B=B, max_features=3, seed=seed)

    p_naive = (1 + np.sum(naive.M_b >= sr_sel)) / (naive.B + 1)
    p_oracle = (1 + np.sum(oracle_M_b >= sr_sel)) / (len(oracle_M_b) + 1)
    print(f"sr_sel={sr_sel:.4f}  naive mean_null_max={naive.mean_null_max:.4f} (p={p_naive:.4f})  "
          f"oracle mean_null_max={oracle_M_b.mean():.4f} (p={p_oracle:.4f})")


def calibration_with_oracle_bootstrap(n_draws=80, K=30, M=80, T=800, B=1500, seed0=88_000):
    p_naive, p_oracle = [], []
    for i in range(n_draws):
        config = DGPConfig(M=M, T=T, T_oos=200, K=K, s=0, rho=0.3, sigma=1.0, seed=seed0 + i)
        data = generate(config)
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        Adaptive(max_features=3, seed=seed0 + i).run(sandbox)
        R = sandbox.returns_matrix()
        sr_sel = float(sharpe(R, axis=0).max())

        naive = null_max_bootstrap(R, B=B, seed=seed0 + i)
        oracle_M_b = recursive_bootstrap_null_max(R[:, :K], B=B, max_features=3, seed=seed0 + i)

        p_naive.append((1 + np.sum(naive.M_b >= sr_sel)) / (naive.B + 1))
        p_oracle.append((1 + np.sum(oracle_M_b >= sr_sel)) / (len(oracle_M_b) + 1))

    p_naive, p_oracle = np.array(p_naive), np.array(p_oracle)
    for name, p in [("naive (fixed transcript)", p_naive), ("oracle (re-derive winner)", p_oracle)]:
        stat, ks_p = kstest(p, "uniform")
        print(f"{name:<28} mean_p={p.mean():.3f} frac_p<0.05={(p < 0.05).mean():.3f} "
              f"KS_stat={stat:.4f} KS_p={ks_p:.4f}")


if __name__ == "__main__":
    print("-- single-draw comparison --")
    compare_single_draw()
    print("\n-- calibration check across draws --")
    calibration_with_oracle_bootstrap()
