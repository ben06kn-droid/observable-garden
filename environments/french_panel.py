"""The French 49-industry daily panel (draft `prereg/french-panel.md`), built as the ETF
panel is (`environments.real_panel.build_etf_panel`): the registered 40 features (20 base
signals, z and rank), signal at the close of t held from the close of t+1 to the close of
t+2, a 252 + 1 row warm-up, 5 bps one-way and 50 bps/yr borrow (an assumption: industry
portfolios are not directly tradable). The declared market series is the equal-weighted
average of the 49 returns. The price path for the moving-average signals is the
compounded return index, log p_t = sum of log(1 + r) through t.

**This panel's rank features use AVERAGE ranks for exact ties** (`rank_average`), its own
feature definition: the data are quantised to 0.01%, so exact ties are common, and the ETF
builder's `_rank` breaks them by sort order. The ETF path is unchanged.

**X is pinned**, as the ETF X is: `build_french_panel` loads `data/pinned/french49_X.npy`
and refuses it unless its SHA-256 is `PINNED_X_SHA256`; there is no rebuild fallback.
`pin_features` writes the pin once.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from environments.real_panel import (ETF_BASE, ETF_BORROW_BPS_YR, ETF_COST_BPS, ETF_DAYS,
                                     RealPanel, _etf_base_signals, _zscore)

WARM = 252 + 1
LAG = 2
PINNED_X = Path(__file__).resolve().parent.parent / "data" / "pinned" / "french49_X.npy"
PINNED_X_SHA256 = "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc"  # arm64, numpy 2.5.3
PINNED_X_SHAPE = (2516, 49, 40)


def rank_average(x: np.ndarray) -> np.ndarray:
    """Cross-sectional rank per period mapped to [-1, 1], exact ties taking their AVERAGE
    rank; NaN is zeroed and a period with fewer than 2 values is all zero, as `_rank`."""
    from scipy.stats import rankdata
    T, M = x.shape
    out = np.zeros((T, M))
    for t in range(T):
        row = x[t]
        ok = ~np.isnan(row)
        n = int(ok.sum())
        if n < 2:
            continue
        out[t, ok] = 2.0 * (rankdata(row[ok], method="average") - 1.0) / (n - 1) - 1.0
    return out


def market_series(r: np.ndarray) -> np.ndarray:
    """The declared market: the equal-weighted average of the 49 industry returns."""
    return r.mean(axis=1)


def panel_from_returns(dates, names, r: np.ndarray, name: str = "french49-daily") -> RealPanel:
    T, M = r.shape
    logp = np.cumsum(np.log1p(r), axis=0)
    sig = _etf_base_signals(logp, r, market_series(r))
    feats, fnames = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), rank_average(sig[nm])]
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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pinned_features(path=None, sha256: str | None = None, shape=PINNED_X_SHAPE) -> np.ndarray:
    """The pinned X, or a refusal. Never rebuilds."""
    path = Path(path) if path is not None else PINNED_X
    sha256 = PINNED_X_SHA256 if sha256 is None else sha256
    if not sha256:
        raise SystemExit("no pinned French X is registered yet (PINNED_X_SHA256 is empty)")
    if not path.exists():
        raise SystemExit(f"pinned French X missing: {path}; it is not rebuilt here")
    got = _file_sha256(path)
    if got != sha256:
        raise SystemExit(f"pinned French X {path} has SHA-256 {got}, not {sha256}; refused")
    X = np.load(path)
    if tuple(X.shape) != tuple(shape):
        raise SystemExit(f"pinned French X has shape {X.shape}, not {shape}")
    return X


def pin_features(path=None) -> str:
    """Build X from the in-sample CSV and write it once; returns the file's SHA-256."""
    path = Path(path) if path is not None else PINNED_X
    if path.exists():
        raise SystemExit(f"{path} exists; the pin is written once")
    p = build_french_panel(pinned=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, np.ascontiguousarray(p.features, dtype=np.float64))
    return _file_sha256(path)


def build_french_panel(path=None, pinned: bool = True) -> RealPanel:
    """The panel. With `pinned` (the default) its features ARE the pinned X, refused on a
    hash or shape mismatch; returns, costs and dates come from the in-sample CSV."""
    from dataclasses import replace
    from data.french_loader import INSAMPLE_CSV, load_insample
    dates, names, r = load_insample(path or INSAMPLE_CSV)
    panel = panel_from_returns(dates, names, r)
    if pinned:
        panel = replace(panel, features=pinned_features())
    return panel
