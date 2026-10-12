"""The French 49-industry LONG-history panel (draft `prereg/french-long-history.md`): the same
registered file, from 1926-07-01, with industries that begin late.

- **Entry, rule (ii):** industry j enters on the first row after which, within the cut, it has
  no missing value. Before that its returns are missing (and treated as absent).
- **Eligibility:** it is in no book until its 253-row warm-up is complete. From entry it
  feeds the market series and its own signals; from entry + 253 rows it may be held. Before
  eligibility, its features are 0, its earned return is 0 and trading it costs nothing, so a
  weight a demeaned book places on it earns and costs nothing, as for a dead Binance contract.
- **Market series:** the equal-weighted average of the industries that have entered.
- **Timing:** lag = 1 + d. lag 2 (d = 1, the French registration's timing): signal at the
  close of t, held from the close of t+1 to the close of t+2. lag 1 (d = 0, NOT
  IMPLEMENTABLE): filled at the close of t, earning t+1.
- **Costs:** 5 bps one-way on the execution row when eligible; 50 bps a year borrow on shorts,
  on eligible earned rows. An assumption (`prereg/french-panel.md`, section e).
"""
from __future__ import annotations

import numpy as np

from environments.french_panel import WARM, _zscore, rank_average
from environments.real_panel import ETF_BASE, ETF_BORROW_BPS_YR, ETF_COST_BPS, ETF_DAYS, RealPanel


def entry_rows(R: np.ndarray) -> np.ndarray:
    """(M,) the first row after which column j has no NaN; T if its last row is missing."""
    T, M = R.shape
    out = np.full(M, T, dtype=int)
    for j in range(M):
        miss = np.flatnonzero(np.isnan(R[:, j]))
        out[j] = 0 if miss.size == 0 else (int(miss[-1]) + 1)
    return out


def long_panel(dates, names, R: np.ndarray, lag: int = 2, name: str = "french49-long") -> tuple[RealPanel, dict]:
    """(panel, info). R is (T, M) daily returns with NaN where the file has a missing code."""
    from environments.binance_panel import signals
    R = np.asarray(R, float)
    T, M = R.shape
    entry = entry_rows(R)
    rows = np.arange(T)[:, None]
    has = rows >= entry[None, :]
    eligible = rows >= (entry + WARM)[None, :]
    rp = np.where(has, np.nan_to_num(R), 0.0)
    sig = signals(rp, has)
    feats, fnames = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), rank_average(sig[nm])]
        fnames += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)
    F[~eligible] = 0.0
    earn = np.zeros_like(rp)
    earn[:-lag] = np.where(eligible[lag:], rp[lag:], 0.0)
    exec_ok = eligible if lag == 1 else np.vstack([eligible[lag - 1:], np.repeat(eligible[-1:], lag - 1, axis=0)])
    held_ok = np.vstack([eligible[lag:], np.zeros((lag, M), bool)])
    keep = slice(WARM, T - lag)
    panel = RealPanel(
        name=name, assets=[f"I{j:02d}" for j in range(M)], feature_names=fnames,
        features=F[keep], returns=earn[keep], tradable=np.ones((T, M), dtype=bool)[keep],
        periods_per_year=float(ETF_DAYS),
        cost_rate=np.where(exec_ok, ETF_COST_BPS * 1e-4, 0.0)[keep],
        borrow_rate=np.where(held_ok, ETF_BORROW_BPS_YR * 1e-4 / ETF_DAYS, 0.0)[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"dates": list(dates[WARM:T - lag]), "earned_dates": list(dates[WARM + lag:T]),
              "industries": list(names), "delay": lag - 1,
              "timing": ("signal at close t; held close t+1 to close t+2" if lag == 2 else
                         "NOT IMPLEMENTABLE: filled at close t; held close t to close t+1"),
              "market": "equal-weighted average of the industries that have entered",
              "cost_bps_one_way": ETF_COST_BPS, "borrow_bps_yr": ETF_BORROW_BPS_YR})
    info = {"entry_row": entry.tolist(), "entry_date": [str(dates[e]) if e < T else None for e in entry],
            "eligible_earned": eligible[WARM + lag:T], "rp": rp, "has": has}
    return panel, info
