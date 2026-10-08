"""The Binance USDT-margined perpetual panel (draft `prereg/binance-panel.md`), on 4h bars
(the draft's panel) or on UTC daily bars (`daily_spec`, the exploratory alternative).

Rows are bars indexed by open time (UTC). Built as the daily equity panels are: the
registered 40 features with lookbacks in ROWS, AVERAGE ranks for exact ties, signal at the
close of bar t held from the close of t+1 to the close of t+2, a 252 + 1 row warm-up.
Periods per year: 2,190 on 4h bars (6 a day x 365), 365 on daily bars.

**Signals are price-only; earned returns include funding** (author, 2026-10-08). The
signals, and the market series they use, come from close-to-close price returns; the
earned return adds funding.

**Earned return.** r_t = close_t / close_{t-1} - 1 - F_t, where F_t is the sum of the funding
rates with open_t < calc_time <= open_t + 4h. A positive rate is paid by longs and received
by shorts (Binance's convention), so a long earns -F_t and a short (negative weight) earns
+F_t through the same w * r. A funding event at a bar boundary falls in the bar that ENDS
there: the position held over that bar is the one held at the funding time, and the
rebalance at that close comes after it.

**Gaps and delistings.** A bar with no row, or with zero trades, while a contract is live,
is a gap: its close is carried forward (return 0 apart from funding), and it stays tradable
and costed. Rows missing from a monthly file may be filled from the archive's checksummed
DAILY files (`{SYM}_{bar}_fill.csv`, written by `data.fetch_binance_fill` only where the
daily files agree with the monthly file on overlapping bars); a fill never overrides a
monthly row. A contract is DEAD from the bar after its last traded bar if it never trades
again in-sample, or if its next trade comes only after a silence of `relist_gap` bars (30
days; treated as a new contract, which is not entered). The last traded bar's return is
earned in full by any position held over it; every later bar earns 0, with funding 0 and
cost 0, so any weight on a dead contract is idle capital. No tradable mask is used, so
positions remain a function of X alone (the fast kernel's requirement).

**A dead contract's features.** From its death bar on, every one of its 20 base signals is
set to NaN before the cross-sectional transforms, so it drops out of that row's z-score and
rank statistics and both its z and its rank are exactly 0 (the transforms zero a missing
value). Any +/-inf in a signal (a zero volatility in a ratio) is set to NaN first. So its
features are finite and deterministic: all 40 are 0. **The weight a strategy can place on
it is not zero:** both a class member and ridge_stack demean their scores across all
contracts, so a dead contract with score 0 receives minus the row's mean score, divided by
the row's gross. It is idle capital, earning and costing nothing.

**Market series:** the equal-weighted average of the LIVE contracts' price returns each bar.
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

from dataclasses import dataclass

BAR_MS = 4 * 3600 * 1000
PPY = 6 * 365                                   # 2,190
WARM = 252 + 1
LAG = 2
FIRST_SCORED_OPEN = dt.datetime(2022, 1, 1, tzinfo=dt.timezone.utc)
LAST_INSAMPLE_OPEN = dt.datetime(2025, 3, 31, 20, tzinfo=dt.timezone.utc)
HOLDOUT_START_MS = int(dt.datetime(2025, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
RELIST_GAP = 180                                # 30 days of 4h bars


@dataclass(frozen=True)
class BarSpec:
    """`bar` is the archive interval; the grid runs from `start` (or, if None, from the
    warm-up before `first_scored`) to `last_open`, every `ms`."""
    bar: str
    ms: int
    ppy: int
    first_scored: dt.datetime | None
    start: dt.datetime | None
    last_open: dt.datetime
    relist_gap: int


FOUR_H = BarSpec("4h", BAR_MS, PPY, FIRST_SCORED_OPEN, None, LAST_INSAMPLE_OPEN, RELIST_GAP)


def daily_spec(first_month: str) -> BarSpec:
    """UTC daily bars from the first day of `first_month` (the month after formation) to
    2025-03-31. The 253-row warm-up lies INSIDE that span: the first scored bar is the
    256th."""
    y, m = map(int, first_month.split("-"))
    return BarSpec("1d", 86_400_000, 365, None, dt.datetime(y, m, 1, tzinfo=dt.timezone.utc),
                   dt.datetime(2025, 3, 31, tzinfo=dt.timezone.utc), 30)
COST_BPS = 10.0                                 # proposed: taker 5 + slippage 5 (draft, section f)
REPO = Path(__file__).resolve().parent.parent
INSAMPLE_DIR = REPO / "data" / "raw" / "binance_insample"
PINNED_X = REPO / "data" / "pinned" / "binance_X.npy"
PINNED_X_SHA256 = ""                            # set from pin_features' output


def _ms(d: dt.datetime) -> int:
    return int(d.timestamp() * 1000)


def grid(spec: BarSpec = FOUR_H) -> np.ndarray:
    """Open times (ms) from the grid start to the last in-sample bar."""
    if spec.start is None:
        first_feature = _ms(spec.first_scored) - LAG * spec.ms
        start = first_feature - WARM * spec.ms
    else:
        start = _ms(spec.start)
    return np.arange(start, _ms(spec.last_open) + 1, spec.ms, dtype=np.int64)


def load_symbol(sym: str, directory: Path = INSAMPLE_DIR, bar: str = "4h"):
    """(klines rows, funding rows) from the derived in-sample CSVs, with any checksummed
    daily-file fill for rows the monthly file lacks; refuses any row on or after 2025-04-01
    and any sealed or quarantined path."""
    from data.etf_loader import HoldoutRefused, refuse_sealed_or_quarantined
    kl, fr, fill = [], [], []
    files = [(f"{sym}_{bar}.csv", kl), (f"{sym}_funding.csv", fr)]
    if (Path(directory) / f"{sym}_{bar}_fill.csv").exists():
        files.append((f"{sym}_{bar}_fill.csv", fill))
    for name, out in files:
        conv = ((lambda r: [int(r[0]), float(r[1]), float(r[2])]) if out is fr else
                (lambda r: [int(r[0])] + [float(x) for x in r[1:7]] + [int(r[7])]))
        p = refuse_sealed_or_quarantined(Path(directory) / name)
        with p.open(newline="") as fh:
            rd = csv.reader(fh)
            next(rd)
            for row in rd:
                v = conv(row)
                if v[0] >= HOLDOUT_START_MS:
                    raise HoldoutRefused(f"{p.name} holds a row on or after 2025-04-01; nothing loaded")
                out.append(v)
    have = {r[0] for r in kl}
    kl += [r for r in fill if r[0] not in have]
    return kl, fr


def align(times: np.ndarray, kl: list, fr: list, relist_gap: int = RELIST_GAP) -> dict:
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
        long_gap = np.flatnonzero(runs > relist_gap)
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
    step = int(times[1] - times[0]) if T > 1 else BAR_MS
    funding = np.zeros(T)
    for t_calc, _hrs, rate in fr:
        # the bar t with open_t < calc_time <= open_t + 4h
        i = int(np.searchsorted(times, t_calc, side="left")) - 1
        if 0 <= i < T and t_calc <= times[i] + step:
            funding[i] += rate
    gaps = int(np.sum(~traded[: dead if dead is not None else T]))
    return {"close": close, "traded": traded, "funding": funding, "dead": dead, "gap_bars": gaps}


def returns_from(aligned: list[dict], T: int):
    """(earned r (T, M) with funding, price-only r (T, M), alive (T, M))."""
    M = len(aligned)
    r = np.zeros((T, M))
    rp = np.zeros((T, M))
    alive = np.ones((T, M), bool)
    for j, a in enumerate(aligned):
        c = a["close"]
        rp[1:, j] = c[1:] / c[:-1] - 1.0
        r[:, j] = rp[:, j] - a["funding"]
        if a["dead"] is not None:
            alive[a["dead"]:, j] = False
            r[a["dead"]:, j] = 0.0
            rp[a["dead"]:, j] = 0.0
    return r, rp, alive


def signals(rp: np.ndarray, alive: np.ndarray) -> dict:
    """The 20 base signals from PRICE returns, with the live-average market; a dead
    contract's signals are NaN from its death bar, and any +/-inf is NaN."""
    live_n = alive.sum(axis=1)
    market = np.where(live_n > 0, (rp * alive).sum(axis=1) / np.maximum(live_n, 1), 0.0)
    logp = np.cumsum(np.log1p(rp), axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        sig = _etf_base_signals(logp, rp, market)
    for k in sig:
        x = np.where(np.isfinite(sig[k]), sig[k], np.nan)
        sig[k] = np.where(alive, x, np.nan)
    return sig


def panel_from_arrays(times, symbols, r, alive, rp=None, spec: BarSpec = FOUR_H,
                      name=None) -> RealPanel:
    T, M = r.shape
    rp = r if rp is None else rp
    sig = signals(rp, alive)
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
        name=name or f"binance-usdtm-{spec.bar}", assets=[f"C{j:02d}" for j in range(M)],
        feature_names=fnames, features=F[keep], returns=np.nan_to_num(earn[keep]),
        tradable=np.ones((T, M), dtype=bool)[keep], periods_per_year=float(spec.ppy),
        cost_rate=cost[keep], borrow_rate=np.zeros((T, M))[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"open_times": [to_iso(t) for t in times[WARM:T - LAG]],
              "earned_opens": [to_iso(t) for t in times[WARM + LAG:T]],
              "symbols": list(symbols), "alive_earned": alive[WARM + LAG:T].tolist(),
              "prereg": "prereg/binance-panel.md (draft)", "ppy": spec.ppy, "bar": spec.bar,
              "timing": "signal at close of bar t; held close t+1 to close t+2",
              "cost_bps_one_way": COST_BPS, "borrow": "none (funding in returns)"})


def build_binance_panel(symbols=None, directory: Path = INSAMPLE_DIR, pinned: bool = True,
                        with_info: bool = False, spec: BarSpec = FOUR_H):
    import json
    from dataclasses import replace
    if symbols is None:
        symbols = json.loads((REPO / "data" / "binance_manifest.json").read_text())["universe"]
    times = grid(spec)
    al = [align(times, *load_symbol(s, directory, spec.bar), relist_gap=spec.relist_gap)
          for s in symbols]
    r, rp, alive = returns_from(al, len(times))
    panel = panel_from_arrays(times, symbols, r, alive, rp=rp, spec=spec)
    if pinned:
        panel = replace(panel, features=pinned_features())
    if with_info:
        return panel, {s: {"dead_bar": a["dead"], "gap_bars": a["gap_bars"],
                           "alive_earned": alive[WARM + LAG:, j].tolist()}
                       for j, (s, a) in enumerate(zip(symbols, al))}
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
