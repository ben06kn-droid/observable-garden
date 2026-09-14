"""Divergence rate: a direct, quantitative measure of candidate-set
instability, complementing (not replacing) the type-I rate a calibration
check reports. For a searcher exposing `round1_beam(base_columns)` (the set
of features that survive round 0 to seed later-round candidate generation
-- searchers/dose_response.py, plus Adaptive/LatticeAdaptive), this asks:
across bootstrap replicates, what fraction of the real transcript's round-1
beam is NOT reproduced when the same selection rule runs on resampled data?

A data-oblivious menu (LatticeAdaptive) has divergence 0 by construction --
its "beam" is always everything. A fully data-dependent one (Adaptive,
beam_width=1) will generally diverge on most replicates, since a different
feature will generically win round 1 under fresh null noise. If naive
bootstrap's type-I inflation tracks divergence rate tightly across every
variant -- dose and structural axes alike -- that identifies the mechanism
quantitatively rather than only demonstrating it exists.
"""
from __future__ import annotations

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices


def divergence_rate(
    base_columns: np.ndarray,
    searcher,
    B: int = 1500,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
) -> float:
    """Mean Jaccard distance between the real round-1 beam and each
    bootstrap replicate's own round-1 beam, over B replicates."""
    base_columns = np.asarray(base_columns, dtype=float)
    T = base_columns.shape[0]
    S0 = base_columns - base_columns.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(S0)
    rng = np.random.default_rng(seed)

    real_beam = searcher.round1_beam(base_columns, annualization=annualization)

    divergences = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        replicate_beam = searcher.round1_beam(S0[idx, :], annualization=annualization)
        union = real_beam | replicate_beam
        inter = real_beam & replicate_beam
        divergences[b] = 1.0 - (len(inter) / len(union) if union else 1.0)

    return float(divergences.mean())


def recursive_bootstrap_and_divergence(
    base_columns: np.ndarray,
    searcher,
    B: int = 1500,
    block_length: int | None = None,
    annualization: float = 1.0,
    seed: int | None = None,
):
    """Combines recursive_bootstrap's null-max replicates and the
    divergence-rate measurement into ONE pass over B replicates -- both
    need "resample base_columns with a stationary bootstrap index," so
    running them separately doubles the resampling cost for no reason.
    Returns (M_b array, mean_divergence)."""
    base_columns = np.asarray(base_columns, dtype=float)
    T = base_columns.shape[0]
    S0 = base_columns - base_columns.mean(axis=0, keepdims=True)
    L = block_length if block_length is not None else select_block_length(S0)
    rng = np.random.default_rng(seed)

    real_beam = searcher.round1_beam(base_columns, annualization=annualization)

    M_b = np.empty(B)
    divergences = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(T, L, rng)
        resampled = S0[idx, :]
        M_b[b] = searcher.replay(resampled, annualization=annualization)
        replicate_beam = searcher.round1_beam(resampled, annualization=annualization)
        union = real_beam | replicate_beam
        inter = real_beam & replicate_beam
        divergences[b] = 1.0 - (len(inter) / len(union) if union else 1.0)

    return M_b, float(divergences.mean())
