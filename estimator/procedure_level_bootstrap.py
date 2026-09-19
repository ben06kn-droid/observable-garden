"""The gold-standard, fully general null for adaptive search -- correct for
any searcher by construction, because it bootstraps the PROCEDURE rather
than reconstructing its output from already-logged columns.

estimator/recursive_bootstrap.py needs a searcher's later-round candidates
to be reconstructable from already-logged base columns (true here only
because Specification is linear -- see SCOPE.md). That's a real dependency,
not a detail: for any specification model without that algebraic structure
-- and for an LLM agent in general -- there is nothing in the transcript
that licenses reconstructing a candidate that was never evaluated.

This module sidesteps that entirely by not reconstructing anything. It
nullifies the search's RAW DATA -- circularly shifting r_in in time
relative to x_in, which destroys whatever feature-return relationship
existed while preserving r's own autocorrelation exactly (a circular
permutation preserves a sequence's own second-order structure) and x's
cross-feature correlation exactly (x_in is untouched) -- then re-executes
the searcher's actual run() against B independently nullified sandboxes.
Whatever it selects on each nullified draw is a legitimate sample from the
true null distribution of "what would this search, run exactly as coded,
produce with nothing to find." No reconstruction, no linearity requirement,
adaptive candidate generation included.

The cost: B full re-executions of run() -- every evaluate() call the real
search makes, repeated B times -- instead of B cheap calls to replay(). Use
this to validate the cheap column-level reconstruction agrees where the
reconstruction is available (experiments/procedure_level_validation.py),
and as the fallback where it isn't.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from environments.dgp import DGPData
from environments.sandbox import Sandbox


def circular_shift_nullify(data: DGPData, shift: int) -> DGPData:
    """r_in shifted in time relative to x_in by `shift` periods (circular).
    x_in, x_oos, r_oos, S, beta_full are untouched."""
    return replace(data, r_in=np.roll(data.r_in, shift, axis=0))


def procedure_level_bootstrap(
    data: DGPData,
    searcher_factory,
    B: int = 300,
    periods_per_year: int = 252,
    seed: int | None = None,
) -> np.ndarray:
    """searcher_factory: zero-arg callable returning a fresh Searcher
    instance (fresh per replicate, so no state leaks across replicates).
    Returns M_b: (B,) array of the Sharpe each nullified run submitted."""
    T = data.r_in.shape[0]
    rng = np.random.default_rng(seed)
    M_b = np.empty(B)
    for b in range(B):
        shift = int(rng.integers(1, T))
        nullified = circular_shift_nullify(data, shift)
        sandbox = Sandbox(nullified, periods_per_year=periods_per_year)
        searcher_factory().run(sandbox)
        _, dist = sandbox.submission
        M_b[b] = dist.mean
    return M_b
