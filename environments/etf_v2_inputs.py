"""Version 2's real-data inputs for ETF and planted ETF panels
(`prereg/ml-v2-exploratory-2026-10-08.md`, decision 10): block X (market: SPY's real return
column), block V (volume and adjusted close; the ETF data has no taker or trade-count
fields), and the neutrality groups, all from the REAL ETF data at the real rows behind the
pinned P rows, with the warm-up history before them. Built once on the laptop, hashed, and
pinned alongside P; planted panels slice them by date, exactly as P is sliced.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

# Re-pinned 2026-10-08 with groups on market-residual returns (note, design change 1). The
# first pin (etf_v2_inputs.npz, SHA-256 50dec727...6d80, groups on raw returns) is superseded.
PINNED = Path(__file__).resolve().parent.parent / "data" / "pinned" / "etf_v2_inputs_r2.npz"
PINNED_SHA256 = ""                           # set from pin()'s output
WARM = 252 + 1


def build_full():
    """(dates, X (T, M, 10), V (T, M, 2), groups (T, M), V names), on build_etf_panel's
    feature rows (warm-up dropped, last 2 rows dropped)."""
    from data.etf_loader import INSAMPLE_DIR, load_panel
    from environments.real_panel import declared_market
    from learn2 import blocks as Bk
    panel = load_panel(INSAMPLE_DIR)
    tickers = sorted(panel)
    common = sorted(set.intersection(*(set(panel[t][0]) for t in tickers)))
    idx = {t: {d: i for i, d in enumerate(panel[t][0])} for t in tickers}
    P = np.array([[panel[t][1][idx[t][d]] for t in tickers] for d in common])
    Vol = np.array([[panel[t][2][idx[t][d]] for t in tickers] for d in common])
    r = np.vstack([np.full((1, len(tickers)), np.nan), P[1:] / P[:-1] - 1.0])
    r0 = np.nan_to_num(r)
    mkt = declared_market(tickers, r0)
    X = Bk.build_X(r0, mkt)
    V, vnames = Bk.build_V(Vol, P, r0)
    G = Bk.build_groups(r0, mkt)
    T = len(common)
    keep = slice(WARM, T - 2)
    return common[keep], X[keep], V[keep], G[keep], vnames


def pin(path=None) -> str:
    path = Path(path) if path is not None else PINNED
    if path.exists():
        raise SystemExit(f"{path} exists; the pin is written once")
    dates, X, V, G, vnames = build_full()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        np.savez(fh, dates=np.array([d.isoformat() for d in dates]), X=X, V=V, G=G,
                 vnames=np.array(vnames))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path=None, sha256: str | None = None) -> dict:
    path = Path(path) if path is not None else PINNED
    sha256 = PINNED_SHA256 if sha256 is None else sha256
    if not sha256:
        raise SystemExit("no pinned ETF v2 inputs are registered yet")
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise SystemExit(f"pinned ETF v2 inputs {path} missing or not SHA-256 {sha256}; refused")
    z = np.load(path)
    return {"dates": list(z["dates"]), "X": z["X"], "V": z["V"], "G": z["G"],
            "vnames": tuple(z["vnames"])}


def for_segment(segment_panel, pinned: dict | None = None) -> dict:
    """X, V, G rows matching a (planted) segment's dates, in order; refused if any date is
    missing."""
    pinned = pinned or load()
    pos = {d: i for i, d in enumerate(pinned["dates"])}
    want = [d.isoformat() if hasattr(d, "isoformat") else str(d) for d in segment_panel.meta["dates"]]
    if any(d not in pos for d in want):
        raise ValueError("a segment date is not in the pinned v2 inputs")
    ii = np.array([pos[d] for d in want])
    return {"X": pinned["X"][ii], "V": pinned["V"][ii], "G": pinned["G"][ii], "vnames": pinned["vnames"]}
