"""Closed-form deflated Sharpe ratio: DSR-L in López de Prado & Porcu (2025)'s
terms, the original location benchmark of Bailey & López de Prado (2014). Kept
as the baseline the bootstrap search null is measured against (spec §1.2, §4.2).

    SR_0 = sqrt(Var[SR_n]) * [ (1-gamma)*Phi^-1(1-1/N) + gamma*Phi^-1(1-1/(N*e)) ]

Var[SR_n] is estimated, per the original paper, as the cross-sectional
variance of the N trial Sharpes themselves — under the null every trial has
zero true edge, so their spread is a proxy for the sampling variance of the
Sharpe estimator. N is either the raw trial count or an eigenvalue-based
"effective" trial count; both are provided since the spec's whole point is
that raw N over-deflates under correlated trials.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from estimator.bootstrap import sharpe

EULER_GAMMA = np.euler_gamma


def expected_max_sharpe_dsr(N: float, var_sr: float) -> float:
    """Extreme-value approximation to E[max of N iid N(0, var_sr)] draws."""
    if N <= 1 or var_sr <= 0:
        return 0.0
    a = (1 - EULER_GAMMA) * norm.ppf(1 - 1.0 / N)
    b = EULER_GAMMA * norm.ppf(1 - 1.0 / (N * np.e))
    return float(np.sqrt(var_sr) * (a + b))


def effective_N(R: np.ndarray) -> float:
    """Participation-ratio effective number of independent trials from the
    eigenvalues of the trial correlation matrix: N_eff = N^2 / sum(eig^2),
    since trace(corr) = N always. N_eff = N when trials are orthogonal,
    shrinks toward 1 as trials collapse onto a single direction (e.g. exact
    duplicates)."""
    T, N = R.shape
    if N <= 1:
        return float(N)
    corr = np.corrcoef(R, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)  # a constant column has undefined correlation
    eigvals = np.linalg.eigvalsh(corr)
    eigvals = np.clip(eigvals, 0, None)  # numerical noise can give tiny negatives
    return float(N ** 2 / np.sum(eigvals ** 2))


@dataclass
class DSRResult:
    sr_sel: float
    sr_deflated: float
    sr_0: float
    var_sr: float
    N_used: float
    N_mode: str


def deflate_closed_form(
    R: np.ndarray,
    sr_sel: float | None = None,
    annualization: float = 1.0,
    N_mode: str = "raw",
) -> DSRResult:
    """N_mode: 'raw' uses the literal trial count; 'effective' uses the
    eigenvalue-based effective count (spec §4.2's third predictor)."""
    R = np.asarray(R, dtype=float)
    trial_sr = sharpe(R, axis=0, annualization=annualization)
    if sr_sel is None:
        sr_sel = float(trial_sr.max())

    var_sr = float(np.var(trial_sr, ddof=1)) if R.shape[1] > 1 else 0.0
    N_used = R.shape[1] if N_mode == "raw" else effective_N(R)
    if N_mode not in ("raw", "effective"):
        raise ValueError("N_mode must be 'raw' or 'effective'")

    sr_0 = expected_max_sharpe_dsr(N_used, var_sr)
    return DSRResult(
        sr_sel=sr_sel, sr_deflated=sr_sel - sr_0, sr_0=sr_0,
        var_sr=var_sr, N_used=N_used, N_mode=N_mode,
    )
