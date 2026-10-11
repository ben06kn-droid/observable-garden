"""The ETF recent panel's in-sample read (`prereg/etf-recent-panel.md`, live at
310225cd4932bc18e1c8e2e248cbbb133124a004). Box only (Linux x86_64, the Linux LightGBM pin),
the Sancho fits and the class tier in the same session. Prints no outcome; the reader is
`experiments/read_etf_recent.py`.

Input: the host cut's record (`<dir>/insample.cut.json`) and its sibling directory
`<dir>/insample/` of `<TICKER>.csv` files (`date,adjclose,volume`, 2005-01-03 .. 2024-12-31).
Refused unless: every CSV's SHA-256 and the combined SHA-256 equal the record's; at least 30
ETFs are included (else nothing runs: ask the author); SPY, the declared market, is included;
the files share one date list, starting 2005-01-03 and ending 2024-12-31, with no missing or
non-positive value; no row is dated after 2024-12-31.

The panel is the ETF registrations' (`environments.real_panel.build_etf_panel`, built here from
arrays with the same functions, at either timing): K = 40 features (20 base signals, z and
rank), warm-up 253, simple returns of the adjusted close; d = 1 earns r[t+2] (signal at the
close of t, held from the close of t+1 to the close of t+2), d = 0 earns r[t+1] (NOT
IMPLEMENTABLE); 5 bps one-way per unit of turnover and 50 bps a year borrow on shorts
(50/252 bps a day). Sancho: version 2's base view as confirmed at 97d2519 on ETF panels
(blocks P, X and V; h 5; market-neutral; always; `prereg/ml-v2-confirmation.md` line 23),
the blocks built as `environments.etf_v2_inputs.build_full` (X and the groups on SPY's return
column; V from volume and adjusted close); M2 (rolling 756 and expanding), G3, L {1, 3, 10, 30};
the learner's first scored row 756 (`learn2.learner.FIRST`, the "carried" configuration) plus
the embargo h + 1 + d: feature row 763 at d = 1, 762 at d = 0.

In this order:
  0. pins.json, before any fit or pricing call: the SHA-256 of each CSV and the combined one,
     of X (the 40 features) and of Sancho's inputs (P, X, V and the groups), both timings;
  1. the bit-for-bit repeat: two Sancho fits at d = 1 and two at d = 0 (positions only);
  2. test 1, Sancho at d = 1, the certificate on the WEIGHTED statistic under W2 (h 1,260):
     96% iff p < 0.03, 90% iff p < 0.06;
  3. test 2, Sancho at d = 0, NOT IMPLEMENTABLE: 96% iff p < 0.01, 90% iff p < 0.02;
  4. test 3, the class maximum (82,240 signed members of size <= 3), d = 1, W2: 96% iff
     p < 0.01, 90% iff p < 0.02; the weighted best member and the unweighted best member.
For each test: the weighted L90; the unweighted statistic beside ("unweighted, descriptive, not
the certificate"); for the streams, the performance line and the unweighted net Sharpe at
10 bps one-way beside (descriptive). The test blocks are those of the French long read
(`experiments.french_long_read.stream_block` / `class_block`), called with this panel.
Seeds 721000 (d = 1), 721001 (d = 0), 721002 (class), 721003 (the performance line).

    python -m experiments.etf_recent_read --cut ~/etf_recent/insample.cut.json \\
        --out runs/etf_recent/<date> --expect-head <EXPECT> --wheel ~/WHEEL.whl --workers 4
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REGISTRATION = "310225cd4932bc18e1c8e2e248cbbb133124a004"
FIRST_DATE = dt.date(2005, 1, 3)
LAST_DATE = dt.date(2024, 12, 31)
MIN_ETFS = 30
MARKET = "SPY"
SEED = 721000                       # +0 d = 1, +1 d = 0, +2 class, +3 performance line
ALPHA = {"stream_d1": (0.03, 0.06), "stream_d0": (0.01, 0.02), "class": (0.01, 0.02)}
WARM = 252 + 1
CACHE_NAME = "etf-recent-signed-3"
CACHE_DIR = None                    # the fast kernel's default cache directory


# -- inputs --------------------------------------------------------------------------------

def combined_sha(csv_sha: dict, included: list) -> str:
    return hashlib.sha256("\n".join(f"{t} {csv_sha[t]}" for t in sorted(included)).encode()).hexdigest()


def check_cut(cut_path: Path) -> tuple[dict, list[str], dict]:
    """(record, refusals, {ticker: csv path}). Hashes only; no value is parsed here."""
    rec = json.loads(Path(cut_path).read_text())
    bad, paths = [], {}
    d = Path(cut_path).parent / "insample"
    inc = list(rec.get("included", []))
    if rec.get("registration") != REGISTRATION:
        bad.append("the cut record's registration is not this one")
    if len(inc) != rec.get("n_included") or len(set(inc)) != len(inc):
        bad.append("the cut record's included list and count disagree")
    if len(inc) < MIN_ETFS:
        bad.append(f"{len(inc)} ETFs included, fewer than {MIN_ETFS}: nothing runs; ask the author")
    if MARKET not in inc:
        bad.append(f"{MARKET}, the declared market series, is not included; there is no fallback")
    for t in inc:
        p = d / f"{t}.csv"
        paths[t] = p
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != rec.get("csv_sha256", {}).get(t):
            bad.append(f"{t}.csv is missing or not its cut record's SHA-256")
    if not bad and combined_sha(rec["csv_sha256"], inc) != rec.get("combined_sha256"):
        bad.append("the combined SHA-256 is not the cut record's")
    return rec, bad, paths


def load(paths: dict, last: dt.date | None = None):
    """(dates, tickers, P (T, M) adjusted closes, Vol (T, M)); refuses a late row, a missing or
    non-positive value, or files whose dates differ."""
    last = last or LAST_DATE
    tickers = sorted(paths)
    cols, dates0 = [], None
    for t in tickers:
        ds, px, vo = [], [], []
        with open(paths[t], newline="") as fh:
            for row in csv.DictReader(fh):
                day = dt.date.fromisoformat(row["date"])
                if day > LAST_DATE:
                    raise SystemExit(f"REFUSED: {t}.csv holds a row dated {day}, after 2024-12-31")
                if not row["adjclose"].strip() or not row["volume"].strip():
                    raise SystemExit(f"REFUSED: {t}.csv has a missing value on {day}")
                ds.append(day)
                px.append(float(row["adjclose"]))
                vo.append(float(row["volume"]))
        if dates0 is None:
            dates0 = ds
        elif ds != dates0:
            raise SystemExit(f"REFUSED: {t}.csv's dates differ from {tickers[0]}.csv's")
        cols.append((px, vo))
    if not dates0 or dates0[0] != FIRST_DATE or dates0[-1] != last:
        raise SystemExit(f"REFUSED: the files run {dates0[0] if dates0 else None} .. "
                         f"{dates0[-1] if dates0 else None}, not {FIRST_DATE} .. {last}")
    if any(b <= a for a, b in zip(dates0, dates0[1:])):
        raise SystemExit("REFUSED: the dates are not strictly increasing")
    # row-major (C-contiguous) as `build_etf_panel` builds it: a transposed array gives
    # last-digit differences in the features
    P = np.ascontiguousarray(np.array([c[0] for c in cols], float).T)
    Vol = np.ascontiguousarray(np.array([c[1] for c in cols], float).T)
    if not np.all(np.isfinite(P)) or (P <= 0).any() or not np.all(np.isfinite(Vol)) or (Vol < 0).any():
        raise SystemExit("REFUSED: a missing, non-finite or non-positive value")
    return dates0, tickers, P, Vol


# -- the panel and Sancho's inputs ---------------------------------------------------------

def etf_panel(dates, tickers, P, Vol, lag: int = 2):
    """(panel, blocks). `build_etf_panel`'s construction from arrays, at lag = 1 + d; the
    blocks as `etf_v2_inputs.build_full`. At lag 2 it is `build_etf_panel` exactly."""
    from environments.real_panel import (ETF_BASE, ETF_BORROW_BPS_YR, ETF_COST_BPS, ETF_DAYS, RealPanel,
                                         _etf_base_signals, _rank, _zscore, declared_market)
    from learn2 import blocks as Bk
    tickers = list(tickers)
    P = np.asarray(P, float)
    logp = np.log(P)
    r = np.vstack([np.full((1, len(tickers)), np.nan), P[1:] / P[:-1] - 1.0])
    r0 = np.nan_to_num(r)
    mkt = declared_market(tickers, r0)
    sig = _etf_base_signals(logp, r0, mkt)
    feats, names = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), _rank(sig[nm])]
        names += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)
    T, M = r.shape
    earn = np.full_like(r, np.nan)
    earn[:-lag] = r[lag:]
    keep = slice(WARM, T - lag)
    panel = RealPanel(
        name="etf-recent", assets=tickers, feature_names=names,
        features=F[keep], returns=np.nan_to_num(earn[keep]),
        tradable=np.ones((T, M), dtype=bool)[keep],
        periods_per_year=float(ETF_DAYS),
        cost_rate=np.full((T, M), ETF_COST_BPS * 1e-4)[keep],
        borrow_rate=np.full((T, M), ETF_BORROW_BPS_YR * 1e-4 / ETF_DAYS)[keep],
        session_start=np.zeros(T, dtype=bool)[keep], session_end=np.zeros(T, dtype=bool)[keep],
        flat_overnight=False,
        meta={"dates": list(dates[WARM:T - lag]), "earned_dates": list(dates[WARM + lag:T]),
              "delay": lag - 1, "prereg": "prereg/etf-recent-panel.md",
              "timing": ("signal at close t; held close t+1 to close t+2" if lag == 2 else
                         "NOT IMPLEMENTABLE: filled at close t; held close t to close t+1"),
              "cost_bps_one_way": ETF_COST_BPS, "borrow_bps_yr": ETF_BORROW_BPS_YR})
    X = Bk.build_X(r0, mkt)
    V, vnames = Bk.build_V(np.asarray(Vol, float), P, r0)
    G = Bk.build_groups(r0, mkt)
    return panel, {"X": X[keep], "V": V[keep], "G": G[keep], "vnames": vnames}


def sancho_inputs(dates, tickers, P, Vol, lag: int):
    from learn2 import learner as Ln
    panel, blk = etf_panel(dates, tickers, P, Vol, lag)
    return panel, Ln.from_panel(panel, blocks={"X": blk["X"], "V": blk["V"]}, groups=blk["G"])


def _fit(args):
    dates, tickers, P, Vol, lag = args
    from experiments import binance_design_v2 as D
    D.configure("carried")                           # first scored row 756; M2 = rolling 756, expanding
    panel, inp = sancho_inputs(dates, tickers, P, Vol, lag)
    book, first, meta = D.book_of(inp)
    return lag, book, first, meta["seconds_per_fit"]


def _sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def pin_record(dates, tickers, P, Vol, csv_sha: dict, combined: str) -> dict:
    """Written before any fit or pricing call."""
    rec = {"csv_sha256": dict(csv_sha), "combined_sha256": combined, "tickers": list(tickers),
           "rows": int(P.shape[0]), "first_date": str(dates[0]), "last_date": str(dates[-1])}
    for lag in (2, 1):
        panel, inp = sancho_inputs(dates, tickers, P, Vol, lag)
        rec[f"d{lag - 1}"] = {"X_features_sha256": _sha(panel.features), "X_shape": list(panel.features.shape),
                              "v2_P_sha256": _sha(inp.P), "v2_X_block_sha256": _sha(inp.blocks["X"]),
                              "v2_V_block_sha256": _sha(inp.blocks["V"]), "groups_sha256": _sha(inp.groups),
                              "first_feature_date": str(panel.meta["dates"][0]),
                              "first_earned_date": str(panel.meta["earned_dates"][0])}
    return rec


# -- the read ------------------------------------------------------------------------------

def cost_beside(book, first, inp, ppy) -> dict:
    """The unweighted net Sharpe at 10 bps one-way (borrow unchanged). Descriptive only."""
    from learn2 import views as Vw
    inp10 = dataclasses.replace(inp, cost_rate=np.asarray(inp.cost_rate, float) * 2.0)
    s = Vw.net_stream(book, inp10, np.arange(first, inp.earned.shape[0]))
    sd = float(np.std(s, ddof=1))
    return {"label": "10 bps one-way, unweighted, descriptive",
            "S": float(np.mean(s) / sd * np.sqrt(ppy)) if sd > 0 else 0.0}


def run_read(dates, tickers, P, Vol, members, workers: int = 4, cache_dir=None, cache_name=CACHE_NAME) -> dict:
    from experiments import french_long_read as FL
    t0 = time.time()
    with ProcessPoolExecutor(workers) as ex:
        fits = list(ex.map(_fit, [(dates, tickers, P, Vol, lag) for lag in (2, 2, 1, 1)]))
    by = {}
    for lag, book, first, secs in fits:
        by.setdefault(lag, []).append((book, first, secs))
    same = {f"d{lag - 1}": bool(np.array_equal(v[0][0], v[1][0])) for lag, v in by.items()}
    out = {"repeat_bit_identical": same, "seconds_per_fit": {f"d{l - 1}": v[0][2] for l, v in by.items()}}
    if not all(same.values()):
        out["stopped"] = "two fits differ; nothing priced"
        return out
    for lag, key, al, label, s in ((2, "test1_stream_d1", ALPHA["stream_d1"], "Sancho stream, d = 1", SEED),
                                   (1, "test2_stream_d0", ALPHA["stream_d0"], "Sancho stream, d = 0, NOT IMPLEMENTABLE", SEED + 1)):
        panel, inp = sancho_inputs(dates, tickers, P, Vol, lag)
        book, first, _ = by[lag][0]
        eligible = np.ones_like(inp.earned, dtype=bool)          # no ETF dies in-sample (the cut)
        out[key] = FL.stream_block(panel, inp, book, first, eligible, s, al, label)
        out[key]["first_scored_row"] = int(first)
        out[key]["cost_10bps_beside"] = cost_beside(book, first, inp, inp.ppy)
    panel, _ = sancho_inputs(dates, tickers, P, Vol, 2)
    out["test3_class_d1"] = FL.class_block(panel, members, SEED + 2, ALPHA["class"], cache_dir, cache_name)
    out["seconds"] = time.time() - t0
    return out


# -- refusals and main ---------------------------------------------------------------------

def refusals(expect_head: str, wheel: str | None) -> list[str]:
    import lightgbm
    from experiments import ml_confirm_ridge_stack as C
    from experiments.ml_v2_confirm_2026_10_09 import PINNED_V2
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    bad = []
    if g("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    if f"{platform.system()} {platform.machine()}" != "Linux x86_64":
        bad.append("not Linux x86_64 (the box)")
    if g("rev-parse", "HEAD").stdout.strip() != expect_head:
        bad.append("HEAD is not --expect-head")
    if g("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    lib = Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.so"
    if lightgbm.__version__ != "4.7.0" or not lib.exists() or hashlib.sha256(lib.read_bytes()).hexdigest() != C.LIB_SHA256:
        bad.append("LightGBM is not the Linux pin")
    if not wheel or not Path(wheel).expanduser().exists() or \
            hashlib.sha256(Path(wheel).expanduser().read_bytes()).hexdigest() != C.WHEEL_SHA256:
        bad.append("the wheel is not the Linux pin")
    for f, blob in PINNED_V2.items():
        if f.startswith("learn2/") and g("rev-parse", f"HEAD:{f}").stdout.strip() != blob:
            bad.append(f"{f} is not the confirmation's blob")
    return bad


def members():
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    return members_in_order(CLS, 40)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True, help="the host cut's record, insample.cut.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-head", required=True)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    cut, bad_cut, paths = check_cut(Path(a.cut).expanduser())
    bad += bad_cut
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    if (out / "results.json").exists():
        raise SystemExit("results exist; the read runs once")
    out.mkdir(parents=True, exist_ok=True)
    dates, tickers, P, Vol = load(paths)
    pins = pin_record(dates, tickers, P, Vol, cut["csv_sha256"], cut["combined_sha256"])
    (out / "pins.json").write_text(json.dumps(pins, indent=1))          # before any fit or pricing call
    rec = {"registration": REGISTRATION, "git_head": a.expect_head, "platform": f"{platform.system()} {platform.machine()}",
           "cut": {"combined_sha256": cut["combined_sha256"], "n_included": len(tickers), "included": tickers,
                   "last_fetched_session": cut.get("last_fetched_session")},
           "rows": int(P.shape[0]), "first_date": str(dates[0]), "last_date": str(dates[-1])}
    rec.update(run_read(dates, tickers, P, Vol, members(), workers=a.workers, cache_dir=CACHE_DIR))
    (out / "results.json").write_text(json.dumps(rec, indent=1, default=float))
    print(f"results written to {out / 'results.json'}; no outcome printed")
    return 0 if "stopped" not in rec else 1


if __name__ == "__main__":
    raise SystemExit(main())
