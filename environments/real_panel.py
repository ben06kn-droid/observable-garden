"""The two registered real panels, built to their pre-registrations.

Nothing here is invented: every rule below cites the file that fixes it, and the
tests in `tests/test_real_sandbox.py` cite the same lines.

**Daily ETF** (`prereg/agent-on-real-data.md`, `prereg/etf-features.md`,
`prereg/etf-universe.md`)
- features: 20 base signals in cross-sectional z and rank forms, K = 40, strict
  one-day lag;
- execution: signal at the close of day t, position held from the close of t+1
  to the close of t+2;
- costs: 5 bps one-way per unit of turnover, 50 bps a year borrow on short
  notional, charged daily;
- prices: adjusted closes; in-sample ends 2022-12-31 and `data/etf_loader.py`'s
  refusals stand.

**Five-minute ADR** (`prereg/adr-universe.md`, `prereg/adr-features.md` and its
amendment 1)
- session: 09:35-15:55 ET traded, first and last regular bars dropped; features
  use every regular bar from 09:30;
- flat overnight; the first traded bar's return is close over its own open;
- a name's `TRANSITION` bars are not traded and its weight is frozen there;
- a missing regular-session bar carries the price forward, returns zero, holds
  the position and is not re-traded;
- the overnight-gap feature is missing on each name's ex-dividend dates, and on
  UL's 2025-12-08 and 2025-12-09;
- costs: Abdi-Ranaldo on 5-minute bars over the most recent min(60, available)
  sessions before the one being priced and never fewer than 20 (amendment 2),
  floored at max(one cent, 2 bps), plus $0.005 a share a side, so a held name
  pays at least two half-spreads a day;
- no feature is built unless the registration commits are ancestors of HEAD
  (`data/adr_guard.py`).

Both panels present the same thing to a searcher: a (T, M, K) feature array, a
(T, M) realized-return array, and a function from weights to a **net-of-cost**
return stream. Costs are not linear in the weights, so the single-feature
columns are a diagnostic basis, not a basis the class is linear in; the class is
priced as an explicit class of net streams (ROADMAP 7.4).
"""
from __future__ import annotations

import datetime as dt
import gzip
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent

ETF_COST_BPS = 5.0          # one-way, per unit turnover
ETF_BORROW_BPS_YR = 50.0
ETF_DAYS = 252
ADR_FEE_PER_SHARE = 0.005
ADR_SPREAD_MIN = 20         # amendment 2: never fewer than 20 prior sessions
ADR_SPREAD_MAX = 60         # amendment 2: and never more than 60
ADR_SPREAD_SESSIONS = ADR_SPREAD_MAX
ADR_BARS_PER_YEAR = 252 * 76


@dataclass
class RealPanel:
    """features (T, M, K), returns (T, M), and the rules for turning weights into
    a net stream. `tradable` is False where a name may not be traded in a period
    (ADR `TRANSITION` and missing bars); its weight is then frozen."""
    name: str
    assets: list[str]
    feature_names: list[str]
    features: np.ndarray
    returns: np.ndarray
    tradable: np.ndarray
    periods_per_year: float
    cost_rate: np.ndarray          # (T, M) charge per unit of |weight change|
    borrow_rate: np.ndarray        # (T, M) charge per unit of short weight held
    session_start: np.ndarray      # (T,) True on the first traded period of a session
    session_end: np.ndarray        # (T,) True on the last traded period of a session
    flat_overnight: bool
    # a bar that exists in the data. `tradable` is False both where a bar is
    # missing and where it is a TRANSITION bar; only the first has no return.
    present: np.ndarray | None = None
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.present is None:
            self.present = np.ones_like(self.tradable)

    @property
    def shape(self):
        return self.features.shape

    def weights_from(self, scores: np.ndarray) -> np.ndarray:
        """Dollar-neutral, gross 1, over the names tradable in that period. A
        frozen name keeps the weight it had; the rest are re-scaled so the book
        stays neutral at gross 1."""
        T, M = scores.shape
        w = np.zeros((T, M))
        held = np.zeros(M)
        for t in range(T):
            free = self.tradable[t]
            if self.flat_overnight and self.session_start[t]:
                held = np.zeros(M)                   # every session opens flat
            target = np.where(free, scores[t], 0.0)
            if free.any():
                target = target - target[free].mean() * free
                gross = np.abs(target[free]).sum()
                if gross > 0:
                    target = target / gross
            new = np.where(free, target, held)       # frozen names keep their weight
            if self.flat_overnight and self.session_end[t]:
                new = np.zeros(M)                    # and closes flat
            w[t] = new
            held = new
        return w

    def net_stream(self, weights: np.ndarray) -> np.ndarray:
        """The registered execution: the weight formed at t earns the next
        period's return, pays turnover both ways and borrow on shorts."""
        w = np.asarray(weights, dtype=float)
        prev = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
        gross_r = np.einsum("tm,tm->t", w, self.returns)
        turnover = np.abs(w - prev)
        costs = np.einsum("tm,tm->t", turnover, self.cost_rate)
        borrow = np.einsum("tm,tm->t", np.clip(-w, 0, None), self.borrow_rate)
        return gross_r - costs - borrow

    def stream_for_scores(self, scores: np.ndarray) -> np.ndarray:
        return self.net_stream(self.weights_from(scores))

    def scores_for_weights(self, feature_weights: np.ndarray) -> np.ndarray:
        """A specification's cross-sectional score: the signed sum of its
        features, which are already standardised cross-sectionally."""
        return self.features @ np.asarray(feature_weights, dtype=float)


# -- shared feature helpers --------------------------------------------------

def _zscore(x: np.ndarray) -> np.ndarray:
    """Cross-sectional z, per period. Zero variance gives zeros, and an
    all-missing period (the warm-up rows, which are dropped later) gives zeros
    rather than a warning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # all-NaN warm-up rows
        mu = np.nanmean(x, axis=1, keepdims=True)
        sd = np.nanstd(x, axis=1, ddof=0, keepdims=True)
    out = np.where(sd > 0, (x - mu) / np.where(sd > 0, sd, 1.0), 0.0)
    return np.nan_to_num(out)


def _rank(x: np.ndarray) -> np.ndarray:
    """Cross-sectional rank per period, mapped to [-1, 1]. NaN ranks last and is
    then zeroed, as `prereg/etf-features.md` requires of a missing value."""
    T, M = x.shape
    out = np.zeros((T, M))
    for t in range(T):
        row = x[t]
        ok = ~np.isnan(row)
        n = int(ok.sum())
        if n < 2:
            continue
        order = np.argsort(np.argsort(row[ok]))
        out[t, ok] = 2.0 * order / (n - 1) - 1.0
    return out


def _roll(a: np.ndarray, w: int, fn) -> np.ndarray:
    """Trailing window of length w over axis 0, NaN until full."""
    T, M = a.shape
    out = np.full((T, M), np.nan)
    for t in range(w - 1, T):
        out[t] = fn(a[t - w + 1:t + 1])
    return out


# -- the daily ETF panel -----------------------------------------------------

ETF_BASE = ["ret1", "mom5", "mom21", "mom63", "mom126", "mom252", "mom12_1",
            "vol21", "vol63", "vol252", "volmom63", "volmom252",
            "ma50", "ma200", "ma_spread", "drawdown", "beta252", "idvol63",
            "skew63", "maxret21"]


def _etf_base_signals(logp: np.ndarray, r: np.ndarray, spy: int) -> dict:
    """`prereg/etf-features.md`'s twenty base signals, each from data through the
    close of t."""
    T, M = r.shape
    cum = np.cumsum(np.nan_to_num(r), axis=0)

    def mom(k):
        out = np.full((T, M), np.nan)
        out[k:] = cum[k:] - cum[:-k]
        return out

    sig = {"ret1": r.copy(), "mom5": mom(5), "mom21": mom(21), "mom63": mom(63),
           "mom126": mom(126), "mom252": mom(252)}
    m12_1 = np.full((T, M), np.nan)
    m12_1[252:] = cum[231:-21] - cum[:-252]          # t-251..t-21
    sig["mom12_1"] = m12_1
    for w in (21, 63, 252):
        sig[f"vol{w}"] = _roll(r, w, lambda a: a.std(axis=0, ddof=1))
    sig["volmom63"] = sig["mom63"] / sig["vol63"]
    sig["volmom252"] = sig["mom252"] / sig["vol252"]
    for w in (50, 200):
        sig[f"ma{w}"] = logp - _roll(logp, w, lambda a: a.mean(axis=0))
    sig["ma_spread"] = _roll(logp, 50, lambda a: a.mean(axis=0)) - \
        _roll(logp, 200, lambda a: a.mean(axis=0))
    sig["drawdown"] = logp - _roll(logp, 252, lambda a: a.max(axis=0))
    mkt = r[:, spy]

    def _beta(a):
        x = a[:, spy]
        xc = x - x.mean()
        denom = float(xc @ xc)
        return (xc @ (a - a.mean(axis=0))) / denom if denom > 0 else np.zeros(a.shape[1])

    sig["beta252"] = _roll(r, 252, _beta)

    def _idvol(a):
        x = a[:, spy]
        xc = x - x.mean()
        denom = float(xc @ xc)
        b = (xc @ (a - a.mean(axis=0))) / denom if denom > 0 else np.zeros(a.shape[1])
        resid = a - a.mean(axis=0) - np.outer(xc, b)
        return resid.std(axis=0, ddof=1)

    sig["idvol63"] = _roll(r, 63, _idvol)

    def _skew(a):
        c = a - a.mean(axis=0)
        s = a.std(axis=0, ddof=0)
        return np.where(s > 0, (c ** 3).mean(axis=0) / np.where(s > 0, s, 1.0) ** 3, 0.0)

    sig["skew63"] = _roll(r, 63, _skew)
    sig["maxret21"] = _roll(r, 21, lambda a: a.max(axis=0))
    _ = mkt
    return sig


def build_etf_panel(directory=None) -> RealPanel:
    """The in-sample daily ETF panel. Reads only through `data/etf_loader.py`, so
    the holdout's refusals apply (`prereg/agent-on-real-data.md`)."""
    from data.etf_loader import INSAMPLE_DIR, load_panel
    panel = load_panel(directory or INSAMPLE_DIR)
    tickers = sorted(panel)
    common = sorted(set.intersection(*(set(panel[t][0]) for t in tickers)))
    idx = {t: {d: i for i, d in enumerate(panel[t][0])} for t in tickers}
    P = np.array([[panel[t][1][idx[t][d]] for t in tickers] for d in common])
    logp = np.log(P)
    r = np.vstack([np.full((1, len(tickers)), np.nan), P[1:] / P[:-1] - 1.0])
    spy = tickers.index("SPY") if "SPY" in tickers else 0
    sig = _etf_base_signals(logp, np.nan_to_num(r), spy)

    feats, names = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), _rank(sig[nm])]
        names += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)                          # (T, M, 40)

    # the registered timing: the weight formed at the close of t is held from the
    # close of t+1 to the close of t+2, so it earns r[t+2]
    T = len(common)
    earn = np.full_like(r, np.nan)
    earn[:-2] = r[2:]
    warm = 252 + 1                                       # the longest lookback
    keep = slice(warm, T - 2)
    n_assets = len(tickers)
    return RealPanel(
        name="etf-daily", assets=tickers, feature_names=names,
        features=F[keep], returns=np.nan_to_num(earn[keep]),
        tradable=np.ones((T, n_assets), dtype=bool)[keep],
        periods_per_year=float(ETF_DAYS),
        cost_rate=np.full((T, n_assets), ETF_COST_BPS * 1e-4)[keep],
        borrow_rate=np.full((T, n_assets), ETF_BORROW_BPS_YR * 1e-4 / ETF_DAYS)[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"dates": common[warm:T - 2], "prereg": "prereg/agent-on-real-data.md",
              "timing": "signal at close t; held close t+1 to close t+2",
              "cost_bps_one_way": ETF_COST_BPS, "borrow_bps_yr": ETF_BORROW_BPS_YR,
              "in_sample_end": "2022-12-31"})


# -- the five-minute ADR panel ----------------------------------------------

# (MIC, tz, end of continuous trading local, TRANSITION bars) per
# prereg/adr-universe.md's per-name table, as amended 2026-09-21.
ADR_HOME = {
    "ASML": ("XAMS", "Europe/Amsterdam", (17, 30), 2), "SAP": ("XETR", "Europe/Berlin", (17, 30), 2),
    "STM": ("XPAR", "Europe/Paris", (17, 30), 2), "NOK": ("XHEL", "Europe/Helsinki", (18, 25), 1),
    "ERIC": ("XSTO", "Europe/Stockholm", (17, 25), 1), "LOGI": ("XSWX", "Europe/Zurich", (17, 20), 2),
    "NVS": ("XSWX", "Europe/Zurich", (17, 20), 2), "AZN": ("XLON", "Europe/London", (16, 30), 2),
    "SNY": ("XPAR", "Europe/Paris", (17, 30), 2), "NVO": ("XCSE", "Europe/Copenhagen", (16, 55), 1),
    "HSBC": ("XLON", "Europe/London", (16, 30), 2), "BCS": ("XLON", "Europe/London", (16, 30), 2),
    "UL": ("XLON", "Europe/London", (16, 30), 2), "DEO": ("XLON", "Europe/London", (16, 30), 2),
    "TTE": ("XPAR", "Europe/Paris", (17, 30), 2), "SHEL": ("XLON", "Europe/London", (16, 30), 2),
    "BP": ("XLON", "Europe/London", (16, 30), 2), "RIO": ("XLON", "Europe/London", (16, 30), 2),
}
# The placebo controls' benchmarks, from the same registered table. They are not
# in ADR_TREATED and are never searched; they exist for the placebo comparison.
ADR_CONTROL_BENCH = {"ARM": "SOXX", "NXPI": "SOXX", "SPOT": "XLC"}
ADR_BENCH = {"ASML": "SOXX", "SAP": "XLK", "STM": "SOXX", "NOK": "XLK", "ERIC": "XLK",
             "LOGI": "XLK", "NVS": "XLV", "AZN": "XLV", "SNY": "XLV", "NVO": "XLV",
             "HSBC": "XLF", "BCS": "XLF", "UL": "XLP", "DEO": "XLP", "TTE": "XLE",
             "SHEL": "XLE", "BP": "XLE", "RIO": "XLB", **ADR_CONTROL_BENCH}
ADR_TREATED = list(ADR_HOME)
ADR_EXTRA_EXCLUSIONS = {"UL": ["2025-12-08", "2025-12-09"]}   # amendment 1 A4
ADR_BASE = ["ret1", "ret3", "ret6", "ret12", "rel1", "rel3", "rel6", "rel12",
            "gap", "vwap_dist", "relvol"]
SESSION_OPEN, FIRST_TRADED, LAST_TRADED = (9, 30), (9, 35), (15, 50)


def _read_bars(ticker: str, raw=None):
    """One ticker's 5-minute bars as (ET datetimes, open, high, low, close, volume)."""
    from zoneinfo import ZoneInfo
    raw = Path(raw) if raw else REPO / "data" / "raw"
    et = ZoneInfo("America/New_York")
    ts, o, h, l, c, v = [], [], [], [], [], []
    with gzip.open(raw / f"{ticker}_5min_adj.csv.gz", "rt") as fh:
        next(fh)
        for line in fh:
            f = line.rstrip("\n").split(",")
            ts.append(dt.datetime.fromtimestamp(int(f[0]) / 1000, dt.timezone.utc).astimezone(et))
            o.append(float(f[1])); h.append(float(f[2])); l.append(float(f[3]))
            c.append(float(f[4])); v.append(float(f[5]))
    return ts, np.array(o), np.array(h), np.array(l), np.array(c), np.array(v)


def _regular(ts, *arrays):
    """Regular-session bars only: bar starts in [09:30, 16:00) ET."""
    keep = [i for i, t in enumerate(ts)
            if (t.hour, t.minute) >= SESSION_OPEN and t.hour < 16]
    return [ts[i] for i in keep], *(a[keep] for a in arrays)


def _ex_dates() -> dict:
    """Ex-dividend dates per name, from the download manifests, plus amendment
    1 A4's two UL dates."""
    import json
    out = {}
    for man in ("adr_manifest.json", "adr_fallback_manifest.json"):
        p = REPO / "data" / man
        if not p.exists():
            continue
        for tk, divs in json.loads(p.read_text()).get("dividends", {}).items():
            out.setdefault(tk, set()).update(d["ex_dividend_date"] for d in divs)
    for tk, extra in ADR_EXTRA_EXCLUSIONS.items():
        out.setdefault(tk, set()).update(extra)
    return out


def build_adr_panel(raw=None, names=None, require_guard: bool = True) -> RealPanel:
    """The treated 5-minute ADR panel. Refuses to build unless the registration
    commits are ancestors of HEAD (`data/adr_guard.py`), since that is what
    licenses opening a bar at all."""
    if require_guard:
        from data.adr_guard import require_registered_features
        require_registered_features(quiet=True)
    from zoneinfo import ZoneInfo
    from data.adr_costs import abdi_ranaldo, floored

    names = list(names or ADR_TREATED)
    ex = _ex_dates()
    per_name, sessions = {}, None
    for tk in names + sorted(set(ADR_BENCH[t] for t in names)):
        ts, o, h, l, c, v = _regular(*_read_bars(tk, raw))
        by_session: dict = {}
        for i, t in enumerate(ts):
            by_session.setdefault(t.date(), []).append(i)
        per_name[tk] = {"ts": ts, "o": o, "h": h, "l": l, "c": c, "v": v, "sess": by_session}
        s = set(by_session)
        sessions = s if sessions is None else (sessions & s)
    sessions = sorted(sessions)

    grid = [(9, 30 + 5 * k) for k in range(6)] + \
           [(h, m) for h in range(10, 16) for m in range(0, 60, 5)]
    grid = [(h + m // 60, m % 60) for h, m in grid]
    traded = [g for g in grid if FIRST_TRADED <= g <= LAST_TRADED]   # 09:35..15:50
    M, K = len(names), 2 * len(ADR_BASE)
    T = len(sessions) * len(traded)
    F = np.zeros((T, M, K))
    R = np.zeros((T, M))
    TRADE = np.zeros((T, M), dtype=bool)
    PRESENT = np.zeros((T, M), dtype=bool)
    COST = np.zeros((T, M))
    start_flag = np.zeros(T, dtype=bool)
    end_flag = np.zeros(T, dtype=bool)
    for j in range(len(sessions)):
        start_flag[j * len(traded)] = True
        end_flag[(j + 1) * len(traded) - 1] = True

    base_cols = {nm: np.zeros((T, M)) for nm in ADR_BASE}
    base_cols["gap"] = np.full((T, M), np.nan)   # NaN until a session sets it
    home_open = np.zeros((T, M), dtype=bool)
    home_closed = np.zeros((T, M), dtype=bool)

    for mi, tk in enumerate(names):
        d = per_name[tk]
        bench = per_name[ADR_BENCH[tk]]
        # The placebo controls have no home market, and the pre-registration says
        # what to do about it: "Controls take XAMS's boundary (11:30 ET, 12:30 ET
        # in clock-mismatch weeks) as a pseudo-close, so every specification is
        # defined on them and every home-close prediction can fail there"
        # (prereg/adr-features.md section 2). Amsterdam's own entry supplies it,
        # so the clock-mismatch weeks follow from the same zoneinfo conversion
        # rather than being written down twice.
        mic, tzname, (hh, mm), n_trans = ADR_HOME.get(tk, ADR_HOME["ASML"])
        tz, et = ZoneInfo(tzname), ZoneInfo("America/New_York")

        def bar_start_for(day, g):
            return dt.datetime.combine(day, dt.time(*g), et)
        hi_by_session, lo_by_session, cl_by_session, prev_close = [], [], [], None
        for si, day in enumerate(sessions):
            idx = d["sess"][day]
            bars = {(d["ts"][i].hour, d["ts"][i].minute): i for i in idx}
            bidx = {(bench["ts"][i].hour, bench["ts"][i].minute): i
                    for i in bench["sess"].get(day, [])}
            hi_by_session.append(d["h"][idx]); lo_by_session.append(d["l"][idx])
            cl_by_session.append(d["c"][idx])

            # the home boundary in ET for this session, and the TRANSITION bars
            cont = dt.datetime.combine(day, dt.time(hh, mm), tz).astimezone(et)
            trans_end = cont + dt.timedelta(minutes=5 * n_trans)

            # spread for this session: Abdi-Ranaldo over the most recent
            # min(60, available) sessions strictly before it, never fewer than 20
            # (amendment 2). Session si itself never contributes.
            lo_s = max(0, si - ADR_SPREAD_MAX)
            enough = (si - lo_s) >= ADR_SPREAD_MIN
            s_hat = abdi_ranaldo(hi_by_session[lo_s:si], lo_by_session[lo_s:si],
                                 cl_by_session[lo_s:si]) if enough else float("nan")
            ref_close = prev_close if prev_close else float(d["c"][idx[0]])
            s_hat = floored(0.0 if not np.isfinite(s_hat) else s_hat, ref_close)
            fee = ADR_FEE_PER_SHARE / ref_close

            # session VWAP and the volume profile need every regular bar
            closes = {g: d["c"][bars[g]] for g in grid if g in bars}
            open_price = d["o"][bars[SESSION_OPEN]] if SESSION_OPEN in bars else None
            vw_num = vw_den = 0.0
            gap = np.nan
            if SESSION_OPEN in bars and prev_close:
                gap = np.log(d["o"][bars[SESSION_OPEN]] / prev_close)
            if day.isoformat() in ex.get(tk, ()):      # A4 / section 5: no gap on ex-dates
                gap = np.nan
            last_price = prev_close
            for bi, g in enumerate(grid):
                if g in bars:
                    i = bars[g]
                    vw_num += d["v"][i] * (d["c"][i] if np.isnan(d["l"][i]) else
                                           (d["h"][i] + d["l"][i] + d["c"][i]) / 3)
                    vw_den += d["v"][i]
                if g not in traded:
                    continue
                t_row = si * len(traded) + traded.index(g)
                present = g in bars
                in_transition = cont <= bar_start_for(day, g) < trans_end
                # TRANSITION bars are not traded (prereg/adr-universe.md), and a
                # missing bar is held rather than traded (adr-features.md s4)
                TRADE[t_row, mi] = present and not in_transition
                PRESENT[t_row, mi] = present
                COST[t_row, mi] = s_hat / 2 + fee
                bar_start = bar_start_for(day, g)
                bar_end = bar_start + dt.timedelta(minutes=5)
                home_open[t_row, mi] = bar_end <= cont
                home_closed[t_row, mi] = bar_start >= trans_end
                if not present:                         # missing bar: carry, hold, zero
                    R[t_row, mi] = 0.0
                    continue
                i = bars[g]
                price = d["c"][i]
                # the first traded bar's return is close over its own open
                if traded.index(g) == 0:
                    R[t_row, mi] = price / d["o"][i] - 1.0
                elif last_price:
                    R[t_row, mi] = price / last_price - 1.0
                last_price = price
                # features, from data through the close of this bar
                def lag(k):
                    j = grid.index(g) - k
                    ref = closes.get(grid[j]) if j >= 0 else open_price
                    return np.log(price / ref) if ref else 0.0
                for k, nm in ((1, "ret1"), (3, "ret3"), (6, "ret6"), (12, "ret12")):
                    base_cols[nm][t_row, mi] = lag(k)
                if g in bidx:
                    bp = bench["c"][bidx[g]]
                    bcl = {gg: bench["c"][bidx[gg]] for gg in grid if gg in bidx}
                    bopen = bench["o"][bidx[SESSION_OPEN]] if SESSION_OPEN in bidx else None
                    def blag(k):
                        j = grid.index(g) - k
                        ref = bcl.get(grid[j]) if j >= 0 else bopen
                        return np.log(bp / ref) if ref else 0.0
                    for k, nm in ((1, "rel1"), (3, "rel3"), (6, "rel6"), (12, "rel12")):
                        base_cols[nm][t_row, mi] = lag(k) - blag(k)
                base_cols["gap"][t_row, mi] = gap        # NaN on ex-dates: zeroed AFTER scoring
                if vw_den > 0:
                    base_cols["vwap_dist"][t_row, mi] = np.log(price / (vw_num / vw_den))
            prev_close = float(d["c"][idx[-1]]) if idx else prev_close

    # THE REGISTERED EXECUTION: "Signal at the close of bar b, position held over
    # bar b+1" (prereg/adr-features.md section 4). R[t] is bar t's OWN return, so
    # the weight formed from features at row t must earn R[t+1], exactly as the
    # ETF panel shifts `earn[:-2] = r[2:]` for its own registered timing.
    #
    # Without this shift a specification loading +ret1 earned the return of the
    # very bar its signal was computed from. That is a look-ahead leak, and it is
    # what the six cost diagnostics of 2026-09-24 found: the class maximum lost
    # its whole edge under one extra bar of lag (107.4 -> -2.9, the same member
    # -97.4), and the placebo controls scored HIGHER than the treated panel.
    # The last row has no successor and is dropped by `keep`.
    EARN = np.zeros_like(R)
    EARN[:-1] = R[1:]

    # relative volume: this bar against the same bar-of-day over the previous 20
    # sessions; the warm-up is dropped below rather than filled
    nb = len(traded)
    for mi, tk in enumerate(names):
        d = per_name[tk]
        vol = np.zeros((len(sessions), nb))
        for si, day in enumerate(sessions):
            bars = {(d["ts"][i].hour, d["ts"][i].minute): i for i in d["sess"][day]}
            for bi, g in enumerate(traded):
                vol[si, bi] = d["v"][bars[g]] if g in bars else np.nan
        for si in range(len(sessions)):
            if si < 20:
                continue
            ref = np.nanmean(vol[si - 20:si], axis=0)
            with np.errstate(divide="ignore", invalid="ignore"):
                rv = np.log(np.where(ref > 0, vol[si] / np.where(ref > 0, ref, 1.0), 1.0))
            base_cols["relvol"][si * nb:(si + 1) * nb, mi] = np.nan_to_num(rv)

    names_out = []
    for bi, nm in enumerate(ADR_BASE):
        z = _zscore(base_cols[nm])
        F[:, :, 2 * bi] = z * home_open
        F[:, :, 2 * bi + 1] = z * home_closed
        names_out += [f"{nm}_home_open", f"{nm}_home_closed"]

    warm = 20 * nb                     # the volume feature's 20-session warm-up
    keep = slice(warm, T)
    return RealPanel(
        name="adr-5min", assets=names, feature_names=names_out,
        features=F[keep], returns=EARN[keep], tradable=TRADE[keep], present=PRESENT[keep],
        periods_per_year=float(ADR_BARS_PER_YEAR),
        cost_rate=COST[keep], borrow_rate=np.zeros((T, M))[keep],
        session_start=start_flag[keep], session_end=end_flag[keep],
        flat_overnight=True,
        meta={"sessions": sessions[20:], "bars_per_session": nb,
              "prereg": "prereg/adr-features.md (amendment 1)",
              "traded_window": "09:35-15:50 bar starts, first and last regular bars dropped",
              "spread_sessions_min": ADR_SPREAD_MIN, "spread_sessions_max": ADR_SPREAD_MAX, "fee_per_share": ADR_FEE_PER_SHARE,
              "ex_dates": {k: sorted(v) for k, v in ex.items()}})
