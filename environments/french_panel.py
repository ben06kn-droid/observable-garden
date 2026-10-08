"""The French 49-industry daily panel (draft `prereg/french-panel.md`), built as the ETF
panel is (`environments.real_panel.build_etf_panel`): the registered 40 features (20 base
signals, z and rank), signal at the close of t held from the close of t+1 to the close of
t+2, a 252 + 1 row warm-up, 5 bps one-way and 50 bps/yr borrow (an assumption: industry
portfolios are not directly tradable). The declared market series is the equal-weighted
average of the 49 returns. The price path for the moving-average signals is the
compounded return index, log p_t = sum of log(1 + r) through t.
"""
from __future__ import annotations

import numpy as np

from environments.real_panel import (ETF_BASE, ETF_BORROW_BPS_YR, ETF_COST_BPS, ETF_DAYS,
                                     RealPanel, _etf_base_signals, _rank, _zscore)

WARM = 252 + 1
LAG = 2


def market_series(r: np.ndarray) -> np.ndarray:
    """The declared market: the equal-weighted average of the 49 industry returns."""
    return r.mean(axis=1)


def panel_from_returns(dates, names, r: np.ndarray, name: str = "french49-daily") -> RealPanel:
    T, M = r.shape
    logp = np.cumsum(np.log1p(r), axis=0)
    sig = _etf_base_signals(logp, r, market_series(r))
    feats, fnames = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), _rank(sig[nm])]
        fnames += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)
    earn = np.full_like(r, np.nan)
    earn[:-LAG] = r[LAG:]
    keep = slice(WARM, T - LAG)
    return RealPanel(
        name=name, assets=[f"I{j:02d}" for j in range(M)], feature_names=fnames,
        features=F[keep], returns=np.nan_to_num(earn[keep]),
        tradable=np.ones((T, M), dtype=bool)[keep], periods_per_year=float(ETF_DAYS),
        cost_rate=np.full((T, M), ETF_COST_BPS * 1e-4)[keep],
        borrow_rate=np.full((T, M), ETF_BORROW_BPS_YR * 1e-4 / ETF_DAYS)[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"dates": list(dates[WARM:T - LAG]), "earned_dates": list(dates[WARM + LAG:T]),
              "industries": list(names), "prereg": "prereg/french-panel.md (draft)",
              "timing": "signal at close t; held close t+1 to close t+2",
              "market": "equal-weighted average of the 49 returns",
              "cost_bps_one_way": ETF_COST_BPS, "borrow_bps_yr": ETF_BORROW_BPS_YR,
              "in_sample_end": "2019-12-31"})


def build_french_panel(path=None) -> RealPanel:
    from data.french_loader import INSAMPLE_CSV, load_insample
    dates, names, r = load_insample(path or INSAMPLE_CSV)
    return panel_from_returns(dates, names, r)
