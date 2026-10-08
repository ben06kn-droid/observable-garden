"""The Binance USDT-margined perpetual panel, 4h bars (draft `prereg/binance-panel.md`).

Rows are 4h bars indexed by open time (UTC), every bar from the warm-up start to the last
in-sample bar (open 2025-03-31 20:00). Built as the daily panels are: the registered 40
features with lookbacks in ROWS, AVERAGE ranks for exact ties, signal at the close of bar t
held from the close of t+1 to the close of t+2, a 252 + 1 row warm-up, periods per year
2,190 (6 bars a day x 365).

**Returns.** r_t = close_t / close_{t-1} - 1 - F_t, where F_t is the sum of the funding
rates with open_t < calc_time <= open_t + 4h. A positive rate is paid by longs and received
by shorts (Binance's convention), so a long earns -F_t and a short (negative weight) earns
+F_t through the same w * r. A funding event at a bar boundary falls in the bar that ENDS
there: the position held over that bar is the one held at the funding time, and the
rebalance at that close comes after it.

**Gaps and delistings.** A bar with no row, or with zero trades, while a contract is live,
is a gap: its close is carried forward (return 0 apart from funding), and it stays tradable
and costed. A contract is DEAD from the bar after its last traded bar if it never trades
again in-sample, or if its next trade comes only after a run of `RELIST_GAP` no-trade bars
(treated as a new contract, which is not entered). A dead contract stays in the panel with
return 0, funding 0 and cost 0: any weight on it is idle capital. No tradable mask is used,
so positions remain a function of X alone (the fast kernel's requirement).

**Market series:** the equal-weighted average of the LIVE contracts' returns each bar.
**Costs:** `COST_BPS` one-way per unit of turnover on live contracts; no borrow (shorts pay
or receive funding instead).
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
from pathlib import Path

import numpy as np

from environments.french_panel import rank_average
from environments.real_panel import ETF_BASE, RealPanel, _etf_base_signals, _zscore

BAR_MS = 4 * 3600 * 1000
PPY = 6 * 365                                   # 2,190
WARM = 252 + 1
LAG = 2
FIRST_SCORED_OPEN = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)
LAST_INSAMPLE_OPEN = dt.datetime(2025, 3, 31, 20, tzinfo=dt.timezone.utc)
HOLDOUT_START_MS = int(dt.datetime(2025, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
RELIST_GAP = 180                                # 30 days of 4h bars
COST_BPS = 10.0                                 # proposed: taker 5 + slippage 5 (draft, section f)
REPO = Path(__file__).resolve().parent.parent
INSAMPLE_DIR = REPO / "data" / "raw" / "binance_insample"
PINNED_X = REPO / "data" / "pinned" / "binance_X.npy"
PINNED_X_SHA256 = ""                            # set from pin_features' output


def _ms(d: dt.datetime) -> int:
    return int(d.timestamp() * 1000)


def grid() -> np.ndarray:
    """Open times (ms) from the warm-up start to the last in-sample bar."""
    first_feature = _ms(FIRST_SCORED_OPEN) - LAG * BAR_MS
    start = first_feature - WARM * BAR_MS
    return np.arange(start, _ms(LAST_INSAMPLE_OPEN) + 1, BAR_MS, dtype=np.int64)


def load_symbol(sym: str, directory: Path = INSAMPLE_DIR):
    """(klines rows, funding rows) from the derived in-sample CSVs, refusing any row on or
    after 2025-04-01 and any sealed or quarantined path."""
    from data.etf_loader import HoldoutRefused, refuse_sealed_or_quarantined
    kl, fr = [], []
    for name, out, conv in ((f"{sym}_4h.csv", kl, lambda r: [int(r[0])] + [float(x) for x in r[1:7]] + [int(r[7])]),
                            (f"{sym}_funding.csv", fr, lambda r: [int(r[0]), float(r[1]), float(r[2])])):
        p = refuse_sealed_or_quarantined(Path(directory) / name)
        with p.open(newline="") as fh:
            rd = csv.reader(fh)
            next(rd)
            for row in rd:
                v = conv(row)
                if v[0] >= HOLDOUT_START_MS:
                    raise HoldoutRefused(f"{p.name} holds a row on or after 2025-04-01; nothing loaded")
                out.append(v)
    return kl, fr


def align(times: np.ndarray, kl: list, fr: list) -> dict:
    """One contract on the grid: closes (carried over gaps), traded flags, funding per bar,
    and the first dead bar (or None)."""
    T = len(times)
    pos = {t: i for i, t in enumerate(times.tolist())}
    close = np.full(T, np.nan)
    traded = np.zeros(T, bool)
    for r in kl:
        i = pos.get(r[0])
        if i is None:
            continue
        close[i] = r[4]
        traded[i] = r[7] > 0 and r[5] > 0
    # death: the bar after the last trade, or the start of a no-trade run >= RELIST_GAP
    idx = np.flatnonzero(traded)
    dead = None
    if idx.size == 0:
        dead = 0
    else:
        runs = np.diff(idx)
        long_gap = np.flatnonzero(runs > RELIST_GAP)
        if long_gap.size:
            dead = int(idx[long_gap[0]]) + 1
        elif idx[-1] < T - 1:
            dead = int(idx[-1]) + 1
    # carry closes forward over gaps
    last = np.nan
    for i in range(T):
        if np.isnan(close[i]):
            close[i] = last
        last = close[i]
    if np.isnan(close).any():
        raise ValueError("no kline row at the warm-up start: the contract is not on the grid from bar 0")
    funding = np.zeros(T)
    for t_calc, _hrs, rate in fr:
        # the bar t with open_t < calc_time <= open_t + 4h
        i = int(np.searchsorted(times, t_calc, side="left")) - 1
        if 0 <= i < T:
            funding[i] += rate
    gaps = int(np.sum(~traded[: dead if dead is not None else T]))
    return {"close": close, "traded": traded, "funding": funding, "dead": dead, "gap_bars": gaps}


def returns_from(aligned: list[dict], T: int):
    """(r (T, M) with funding, alive (T, M))."""
    M = len(aligned)
    r = np.zeros((T, M))
    alive = np.ones((T, M), bool)
    for j, a in enumerate(aligned):
        c = a["close"]
        r[1:, j] = c[1:] / c[:-1] - 1.0 - a["funding"][1:]
        r[0, j] = -a["funding"][0]
        if a["dead"] is not None:
            alive[a["dead"]:, j] = False
            r[a["dead"]:, j] = 0.0
    return r, alive


def panel_from_arrays(times, symbols, r, alive, name="binance-usdtm-4h") -> RealPanel:
    T, M = r.shape
    live_n = alive.sum(axis=1)
    market = np.where(live_n > 0, (r * alive).sum(axis=1) / np.maximum(live_n, 1), 0.0)
    logp = np.cumsum(np.log1p(r), axis=0)
    sig = _etf_base_signals(logp, r, market)
    feats, fnames = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), rank_average(sig[nm])]
        fnames += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)
    earn = np.full_like(r, np.nan)
    earn[:-LAG] = r[LAG:]
    keep = slice(WARM, T - LAG)
    # the trade decided at the close of bar t executes at the close of bar t+1: it is costed
    # iff bar t+1 is live (after a delisting the position is settled; changing it is free)
    exec_live = np.vstack([alive[1:], alive[-1:]])
    cost = np.where(exec_live, COST_BPS * 1e-4, 0.0)
    to_iso = lambda t: dt.datetime.fromtimestamp(int(t) / 1000, dt.timezone.utc).isoformat()
    return RealPanel(
        name=name, assets=[f"C{j:02d}" for j in range(M)], feature_names=fnames,
        features=F[keep], returns=np.nan_to_num(earn[keep]),
        tradable=np.ones((T, M), dtype=bool)[keep], periods_per_year=float(PPY),
        cost_rate=cost[keep], borrow_rate=np.zeros((T, M))[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"open_times": [to_iso(t) for t in times[WARM:T - LAG]],
              "earned_opens": [to_iso(t) for t in times[WARM + LAG:T]],
              "symbols": list(symbols), "alive_earned": alive[WARM + LAG:T].tolist(),
              "prereg": "prereg/binance-panel.md (draft)", "ppy": PPY,
              "timing": "signal at close of bar t; held close t+1 to close t+2",
              "cost_bps_one_way": COST_BPS, "borrow": "none (funding in returns)"})


def build_binance_panel(symbols=None, directory: Path = INSAMPLE_DIR, pinned: bool = True,
                        with_info: bool = False):
    import json
    from dataclasses import replace
    if symbols is None:
        symbols = json.loads((REPO / "data" / "binance_manifest.json").read_text())["universe"]
    times = grid()
    al = [align(times, *load_symbol(s, directory)) for s in symbols]
    r, alive = returns_from(al, len(times))
    panel = panel_from_arrays(times, symbols, r, alive)
    if pinned:
        panel = replace(panel, features=pinned_features())
    if with_info:
        return panel, {s: {"dead_bar": a["dead"], "gap_bars": a["gap_bars"]} for s, a in zip(symbols, al)}
    return panel


def pinned_features(path=None, sha256: str | None = None) -> np.ndarray:
    path = Path(path) if path is not None else PINNED_X
    sha256 = PINNED_X_SHA256 if sha256 is None else sha256
    if not sha256:
        raise SystemExit("no pinned Binance X is registered yet")
    if not path.exists():
        raise SystemExit(f"pinned Binance X missing: {path}; it is not rebuilt here")
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha256:
        raise SystemExit(f"pinned Binance X has SHA-256 {got}, not {sha256}; refused")
    return np.load(path)


def pin_features(path=None) -> str:
    path = Path(path) if path is not None else PINNED_X
    if path.exists():
        raise SystemExit(f"{path} exists; the pin is written once")
    p = build_binance_panel(pinned=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, np.ascontiguousarray(p.features, dtype=np.float64))
    return hashlib.sha256(path.read_bytes()).hexdigest()
