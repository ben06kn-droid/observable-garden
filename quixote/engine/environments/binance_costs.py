"""The Binance per-contract cost rule (draft `prereg/binance-panel.md`; scoped at `8ef590a`,
adjusted by the author on 2026-10-09).

cost per unit of turnover = FEE + max(half-spread estimate, FLOOR), where:
- FEE is 5 bps. This is an ASSUMPTION: Binance USD-M futures' published base-tier taker
  fee, 0.05%. It is not measured, and no fee schedule is fetched.
- The half-spread estimate for contract i in month m is half of the EDGE spread estimate
  (Ardia, Guidotti and Kroencke 2024, doi:10.1016/j.jfineco.2024.103916). It is computed
  from contract i's 4h bars that OPEN in the 30 days before month m starts, so every bar
  used has closed before the month begins. It is re-estimated monthly and applied to
  every trade executed in month m. It is NaN with fewer than MIN_BARS traded bars.
- A month with no estimate for a contract takes that month's cross-sectional median over
  the contracts that have one.
- FLOOR is 1 bp.
- A dead contract costs nothing after its exit (the panel's mask, decision B1).

The fallback estimator, used only if the book-ticker check finds EDGE clearly biased, is
Abdi and Ranaldo (2017, doi:10.1093/rfs/hhx084) on the same bars and window.
"""
from __future__ import annotations

import datetime as dt

import numpy as np

FEE = 5e-4
FLOOR = 1e-4
WINDOW_DAYS = 30
MIN_BARS = 90


def edge(o, h, l, c) -> float:
    """EDGE spread estimate (a proportion; the full spread) from one contract's bars, in
    time order. NaN entries are missing bars. Follows the authors' reference
    implementation."""
    o, h, l, c = (np.log(np.asarray(x, float)) for x in (o, h, l, c))
    m = (h + l) / 2.0
    h1, l1, c1, m1 = h[:-1], l[:-1], c[:-1], m[:-1]
    o, h, l, c, m = o[1:], h[1:], l[1:], c[1:], m[1:]
    r1, r2, r3, r4, r5 = m - o, o - m1, m - c1, c1 - m1, o - c1
    nan = lambda *a: np.any([np.isnan(x) for x in a], axis=0)
    tau = np.where(nan(h, l, c1), np.nan, ((h != l) | (l != c1)).astype(float))
    po1 = tau * np.where(nan(o, h), np.nan, (o != h).astype(float))
    po2 = tau * np.where(nan(o, l), np.nan, (o != l).astype(float))
    pc1 = tau * np.where(nan(c1, h1), np.nan, (c1 != h1).astype(float))
    pc2 = tau * np.where(nan(c1, l1), np.nan, (c1 != l1).astype(float))
    with np.errstate(invalid="ignore", divide="ignore"):
        pt = np.nanmean(tau)
        po = np.nanmean(po1) + np.nanmean(po2)
        pc = np.nanmean(pc1) + np.nanmean(pc2)
        if np.nansum(tau) < 2 or po == 0 or pc == 0 or not np.isfinite(pt):
            return float("nan")
        d1 = r1 - np.nanmean(r1) / pt * tau
        d3 = r3 - np.nanmean(r3) / pt * tau
        d5 = r5 - np.nanmean(r5) / pt * tau
        x1 = -4.0 / po * d1 * r2 + -4.0 / pc * d3 * r4
        x2 = -4.0 / po * d1 * r5 + -4.0 / pc * d5 * r4
        e1, e2 = np.nanmean(x1), np.nanmean(x2)
        v1 = np.nanmean(x1 ** 2) - e1 ** 2
        v2 = np.nanmean(x2 ** 2) - e2 ** 2
        vt = v1 + v2
        s2 = (v2 * e1 + v1 * e2) / vt if vt > 0 else (e1 + e2) / 2.0
    return float(np.sqrt(abs(s2)))


def abdi_ranaldo(h, l, c) -> float:
    """Abdi-Ranaldo close-high-low spread estimate (a proportion; the full spread), the
    window-average form: s = sqrt(max(4 mean[(c_t - eta_t)(c_t - eta_{t+1})], 0))."""
    h, l, c = (np.log(np.asarray(x, float)) for x in (h, l, c))
    eta = (h + l) / 2.0
    v = (c[:-1] - eta[:-1]) * (c[:-1] - eta[1:])
    v = v[np.isfinite(v)]
    if v.size < 2:
        return float("nan")
    return float(np.sqrt(max(4.0 * v.mean(), 0.0)))


def month_starts(times_ms: np.ndarray) -> list[int]:
    t0 = dt.datetime.fromtimestamp(int(times_ms[0]) / 1000, dt.timezone.utc)
    t1 = dt.datetime.fromtimestamp(int(times_ms[-1]) / 1000, dt.timezone.utc)
    y, m = t0.year, t0.month
    out = []
    while (y, m) <= (t1.year, t1.month):
        out.append(int(dt.datetime(y, m, 1, tzinfo=dt.timezone.utc).timestamp() * 1000))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def monthly_half_spreads(times_ms, O, H, L, C, traded, estimator: str = "edge") -> tuple[list[int], np.ndarray]:
    """(month starts, (n_months, M) half-spread estimates, NaN where none), each from the
    bars opening in the 30 days before its month starts. Untraded bars are missing."""
    times_ms = np.asarray(times_ms, np.int64)
    starts = month_starts(times_ms)
    M = O.shape[1]
    out = np.full((len(starts), M), np.nan)
    for k, s in enumerate(starts):
        sel = (times_ms >= s - WINDOW_DAYS * 86_400_000) & (times_ms < s)
        for j in range(M):
            tr = traded[sel, j]
            if tr.sum() < MIN_BARS:
                continue
            o, h, l, c = (np.where(tr, X[sel, j], np.nan) for X in (O, H, L, C))
            sp = edge(o, h, l, c) if estimator == "edge" else abdi_ranaldo(h, l, c)
            out[k, j] = sp / 2.0
    return starts, out


def fill_months(hs: np.ndarray) -> np.ndarray:
    """A month's missing estimates take that month's cross-sectional median."""
    out = hs.copy()
    for k in range(out.shape[0]):
        row = out[k]
        if np.isfinite(row).any():
            row[~np.isfinite(row)] = np.nanmedian(row)
    return out


def cost_rates(times_ms, starts, hs_filled, alive, warm: int, lag: int) -> np.ndarray:
    """The panel's (rows, M) cost rate: row k's trade executes at grid bar warm + k + lag - 1
    (the next bar's close at lag 2, d = 1; the same bar's close at lag 1, d = 0); its
    month's half-spread, floored, plus the fee; 0 where the execution bar is dead. A month
    with no estimate at all (before any history) takes FEE + FLOOR."""
    times_ms = np.asarray(times_ms, np.int64)
    T = len(times_ms)
    rows = np.arange(warm, T - lag)
    ex = rows + (lag - 1)
    k = np.searchsorted(np.asarray(starts, np.int64), times_ms[ex], side="right") - 1
    hs = hs_filled[k]
    rate = FEE + np.maximum(np.where(np.isfinite(hs), hs, 0.0), FLOOR)
    return np.where(np.asarray(alive)[ex], rate, 0.0)
