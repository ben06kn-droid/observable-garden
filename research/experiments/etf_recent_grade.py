"""The ETF recent panel's holdout grader, for the panel's three objects and every agent-cell
submission, in one host session (`prereg/etf-recent-panel.md`, amendment 2 item 7;
`prereg/agent-cell-etf-recent.md`, section 7). Runs on the holdout host, by the author.

**It refuses until both GRADING (the panel's grading registration) and CELL (the agent cell's
registration) are set to live commits that are ancestors of HEAD.** PANEL is the panel's live
registration.

Inputs, all on the host: the in-sample cut (`insample.cut.json` and its CSVs); the raw fetch
(`~/etf_recent/raw`, with `fetch.json`), from which the holdout rows 2025-01-02 .. the last
fetched session are parsed here and nowhere else; the BOX-ETF read's directory (results.json,
pins.json, precompute/manifest.json); the committed `submissions.json` and `priced.json`,
each pinned by SHA-256 on the command line.

In this order, refusing on any failure before any holdout value is computed (each check prints
one pass/FAIL line and no value):
  a. start-up: the registrations; HEAD; clean tracked tree; Linux x86_64; LightGBM's library;
     the learn2 blobs; the cut's hashes; every holdout session present for every ETF with no
     missing value, checked against the pinned holdout session list written on the host by
     `data.etf_recent_sessions` in `~/venv-fetch` (this module never imports exchange_calendars;
     a gap or a death refuses: the grading registration's section 4); the 2024-12-31 adjusted close in the raw response equals the cut
     CSV's, as text; priced.json names this precompute manifest and this submissions file;
  b. reproduction of the in-sample read on the host: (1) the pins (both timings, from the cut
     alone, rows from 2010-01-04) equal pins.json; (2) each object's in-sample weighted net
     Sharpe on the scored window equals the read to 3 decimals, and the two streams' unweighted
     ones; each rule submission's in-sample unweighted and weighted net Sharpes equal
     priced.json's (`S`, `S_w`) to 3 decimals;
  c. no restart: features on the in-sample rows bit-identical between the spanning and
     in-sample-only builds; every object's and rule submission's positions bit-identical on the
     in-sample rows; the first holdout trade costed from the carried position (1e-13); no
     all-zero feature row in the first 253 holdout rows; a nonzero Sancho position at the first
     holdout row.
Then, per item (the three objects, each submission, and the equal-weight books of all
submissions and of each arm): the realised UNWEIGHTED net Sharpe and the compounded net return
over the holdout; one stationary bootstrap over holdout days applied jointly to every item
(B 10,000; the class rule's block length on the holdout's demeaned base columns; seed 723000),
its 90% intervals, and the replicate matrices (B x items, float32, base64) so the readers
compute every joint interval without the holdout; held iff realised >= L90, where L90 is, for
the three objects, the parent panel's scripted W2-weighted L90 (as registered), and for each
submission the cell's UNWEIGHTED L90 from priced.json (`prereg/agent-cell-etf-recent.md` section
0), with the W2 L90 beside, labelled "recency-weighted, descriptive"; the 2026-only realised
Sharpe beside, descriptive. Written to grades.json. **No value is
printed.**

    python -m experiments.etf_recent_grade --cut ~/etf_recent/insample.cut.json --raw ~/etf_recent/raw \\
        --sessions ~/etf_recent/holdout_sessions.json --sessions-sha <sha> \\
        --read-dir runs/etf_recent/<D> --submissions runs/agent_cell_etf_recent/submissions.json \\
        --submissions-sha <sha> --priced runs/agent_cell_etf_recent/priced.json --priced-sha <sha> \\
        --out runs/etf_recent_grade/<date> --expect-head <G> --workers 4
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from experiments import etf_recent_read as ER
from experiments import french_long_grade as FG

PANEL = "310225cd4932bc18e1c8e2e248cbbb133124a004"
GRADING = "2fd0346cde8903ea431acc2186e7bd5264f2d16a"  # prereg/etf-recent-grading.md, live
CELL = "00c7af167f8ddb9a4874cc29b438926112360fb9"  # prereg/agent-cell-etf-recent.md, live
HOLDOUT_START = dt.date(2025, 1, 2)
Y2026 = dt.date(2026, 1, 1)
B = 10_000
SEED = 723000
LAG = {"stream_d1": 2, "stream_d0": 1, "class_member": 2}
RESULT_KEY = {"stream_d1": "test1_stream_d1", "stream_d0": "test2_stream_d0", "class_member": "test3_class_d1"}
OBJECTS = tuple(LAG)
LABEL_WEAK = "weak: 1.76 years"
OBJECT_L90_LABEL = ("the parent panel's scripted certificate: the W2-weighted L90, as registered "
                    "(prereg/etf-recent-panel.md; this cell does not change it)")
SUBMISSION_L90_LABEL = "unweighted L90 (the cell's primary statistic, prereg/agent-cell-etf-recent.md section 0)"


class GradingRefused(RuntimeError):
    pass


def say(name: str, ok: bool) -> None:
    print(f"check {name}: {'pass' if ok else 'FAIL'}", flush=True)


def refuse_if_failed(checks: dict, what: str) -> None:
    for k, v in checks.items():
        say(f"{what}: {k}", bool(v))
    bad = [k for k, v in checks.items() if v is False]
    if bad:
        raise GradingRefused(f"{what} failed: {', '.join(bad)}; nothing graded")


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# -- the holdout, parsed on the host only ---------------------------------------------------

def load_sessions(path: Path, sha: str, cut: dict) -> tuple[list[dt.date], str]:
    """The holdout session list written on the host by `data.etf_recent_sessions` (in
    `~/venv-fetch`): pinned by SHA-256, from the first session on or after 2025-01-01 to the cut
    record's last fetched session, with the cut record's date-counted holdout rows. The grader never
    imports exchange_calendars (the grading registration, decision 3)."""
    path = Path(path).expanduser()
    if not path.exists() or sha_file(path) != sha:
        raise GradingRefused("the holdout session list is missing or not its pinned SHA-256")
    rec = json.loads(path.read_text())
    days = [dt.date.fromisoformat(s) for s in rec["sessions"]]
    last = dt.date.fromisoformat(cut["last_fetched_session"])
    counts = {e.get("holdout_rows") for t, e in cut["per_ticker"].items() if e.get("included")}
    if (not days or days[0] != HOLDOUT_START or days[-1] != last or rec.get("n") != len(days)
            or any(b <= a for a, b in zip(days, days[1:])) or counts != {len(days)}):
        raise GradingRefused("the holdout session list does not match the cut record "
                             "(first session, last fetched session, or the date-counted holdout rows)")
    return days, sha


def make_holdout(raw_dir: Path, tickers: list[str], want: list[dt.date], cut_dir: Path):
    """(dates, P, Vol) on the session list `want`, from the raw responses (each checked against
    fetch.json). Refuses, for any ETF, a holdout date missing from the fetched rows or a fetched
    holdout date not in the list, a null value, and a 2024-12-31 adjusted close that differs, as
    text, from the cut CSV's."""
    import csv
    from data.etf_recent_cut import NY, parse
    raw_dir = Path(raw_dir)
    fetch = json.loads((raw_dir / "fetch.json").read_text())
    last = want[-1]
    boundary = dt.date(2024, 12, 31)
    P, V = [], []
    for t in tickers:
        f = raw_dir / f"{t}.json"
        if not f.exists() or sha_file(f) != fetch["tickers"][t].get("sha256"):
            raise GradingRefused(f"{t}.json is missing or not its fetch.json SHA-256")
        p = parse(f.read_bytes())
        if p is None:
            raise GradingRefused(f"{t}: no bars in the raw response")
        ts, adj, vol = p
        rows, b_adj = {}, None
        for k, s in enumerate(ts):
            d = dt.datetime.fromtimestamp(int(s), NY).date()
            if d == boundary:
                b_adj = adj[k]
            if HOLDOUT_START <= d <= last and d not in rows:
                rows[d] = (adj[k] if k < len(adj) else None, vol[k] if k < len(vol) else None)
        with open(Path(cut_dir) / f"{t}.csv", newline="") as fh:
            last_row = None
            for last_row in csv.DictReader(fh):
                pass
        if last_row is None or last_row["date"] != boundary.isoformat() or b_adj is None or str(b_adj) != last_row["adjclose"]:
            raise GradingRefused(f"{t}: the raw 2024-12-31 adjusted close is not the cut CSV's (text)")
        extra = sorted(set(rows) - set(want))
        if extra:
            raise GradingRefused(f"{t}: {len(extra)} fetched holdout dates not in the session list, from {extra[0]}")
        miss = [d for d in want if d not in rows or rows[d][0] is None or rows[d][1] is None]
        if miss:
            raise GradingRefused(f"{t}: {len(miss)} holdout sessions missing or null from {miss[0]} (a gap or a death: "
                                 "nothing graded; ask the author)")
        P.append([float(rows[d][0]) for d in want])
        V.append([float(rows[d][1]) for d in want])
    P = np.ascontiguousarray(np.array(P, float).T)
    V = np.ascontiguousarray(np.array(V, float).T)
    if not np.all(np.isfinite(P)) or (P <= 0).any() or not np.all(np.isfinite(V)) or (V < 0).any():
        raise GradingRefused("a non-finite or non-positive holdout value")
    return want, P, V


# -- streams --------------------------------------------------------------------------------

def sharpe(x, ppy: float = 252.0) -> float:
    return FG.sharpe(x, ppy)


def wsharpe(x, ppy: float = 252.0) -> float:
    return FG.wsharpe(x, ppy)


def compounded(x) -> float:
    return float(np.prod(1.0 + np.asarray(x, float)) - 1.0)


def fit_all(jobs, workers: int, fit_fn=None):
    fit_fn = fit_fn or ER._fit
    if workers <= 1:
        return [fit_fn(j) for j in jobs]
    with ProcessPoolExecutor(workers) as ex:
        return list(ex.map(fit_fn, jobs))


def b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.float32).tobytes()).decode()


def unb64(s: str, shape) -> np.ndarray:
    return np.frombuffer(base64.b64decode(s), dtype=np.float32).reshape(shape)


# -- the grading --------------------------------------------------------------------------

def grade(dates_in, tickers, P_in, V_in, n_dropped, cut: dict, dates_ho, P_ho, V_ho, pins: dict, results: dict,
          priced: dict, submissions: dict, workers: int = 4, fit_fn=None, net_fn=None, B_: int | None = None) -> dict:
    """Sections b, c and the quantities. Raises GradingRefused before any holdout value on a
    failure. `fit_fn` and `net_fn` are injectable for tests only."""
    from environments.class_table import canonical
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    net_fn = net_fn or FG.default_net
    t0 = time.time()
    dates_sp = list(dates_in) + list(dates_ho)
    P_sp, V_sp = np.vstack([P_in, P_ho]), np.vstack([V_in, V_ho])

    # (b1) the in-sample pins, from the cut alone
    hp = ER.pin_record(dates_in, tickers, P_in, V_in, cut["csv_sha256"], cut["combined_sha256"], n_dropped)
    b1 = {k: hp[k] == pins.get(k) for k in ("combined_sha256", "first_row_used", "rows_dropped_before", "rows")}
    for d in ("d1", "d0"):
        for f in ("X_features_sha256", "X_shape", "v2_P_sha256", "v2_X_block_sha256", "v2_V_block_sha256", "groups_sha256"):
            b1[f"{d}_{f}"] = hp[d][f] == pins[d][f]
    refuse_if_failed(b1, "b1 pins")

    # panels and the four Sancho fits
    PI = {}
    for where, (d, P, V) in {"in": (dates_in, P_in, V_in), "sp": (dates_sp, P_sp, V_sp)}.items():
        for lag in (2, 1):
            PI[(where, lag)] = ER.sancho_inputs(d, tickers, P, V, lag)
    jobs = [(dates_in, tickers, P_in, V_in, 2), (dates_in, tickers, P_in, V_in, 1),
            (dates_sp, tickers, P_sp, V_sp, 2), (dates_sp, tickers, P_sp, V_sp, 1)]
    fits = fit_all(jobs, workers, fit_fn)
    F = {("in", 2): fits[0], ("in", 1): fits[1], ("sp", 2): fits[2], ("sp", 1): fits[3]}
    h0 = {lag: PI[("in", lag)][0].features.shape[0] for lag in (2, 1)}
    n_ho = len(dates_ho)
    ppy = float(PI[("in", 2)][0].periods_per_year)

    books, s_in, s_sp, first = {}, {}, {}, {}
    for o in ("stream_d1", "stream_d0"):
        lag = LAG[o]
        for where in ("in", "sp"):
            _, book, f0, _ = F[(where, lag)]
            books[(o, where)], first[(o, where)] = book, f0
            s = net_fn(book, PI[(where, lag)][1], np.arange(f0, PI[(where, lag)][1].earned.shape[0]))
            (s_in if where == "in" else s_sp)[o] = s
    # the class member and every distinct rule submission: the read's kernel
    rules = {}
    bm = results["test3_class_d1"]["weighted_W2"]["best_member"]
    obj_support = canonical(bm["support"]) if "support" in bm else \
        canonical(FG.member_support(PI[("in", 2)][0].feature_names, bm["features"]))
    rules["class_member"] = obj_support
    for s in submissions["submissions"]:
        if s["kind"] == "rule":
            rules[f"rule:{canonical(s['support'])}"] = canonical(s["support"])
    for name, sup in rules.items():
        for where in ("in", "sp"):
            pos, s = FG.member_book(PI[(where, 2)][0], sup)
            books[(name, where)], first[(name, where)] = pos, 0
            (s_in if where == "in" else s_sp)[name] = s

    # (b2) in-sample Sharpes on the scored window
    idx = {lag: ER.scored_index(PI[("in", lag)][0]) for lag in (2, 1)}
    host, refs = {}, {}
    for o in OBJECTS:
        lag = LAG[o]
        x = s_in[o][idx[lag] - first[(o, "in")]]
        host[f"{o}_weighted"] = wsharpe(x, ppy)
        refs[f"{o}_weighted"] = results[RESULT_KEY[o]]["weighted_W2"]["S"]
        if o != "class_member":
            host[f"{o}_unweighted"] = sharpe(x, ppy)
            refs[f"{o}_unweighted"] = results[RESULT_KEY[o]]["unweighted"]["S"]
    pr = {r["session"]: r for r in priced["priced"]}
    for s in submissions["submissions"]:
        if s["kind"] == "rule":
            name = f"rule:{canonical(s['support'])}"
            host[f"{s['session']}_weighted"] = wsharpe(s_in[name][idx[2]], ppy)
            refs[f"{s['session']}_weighted"] = pr[s["session"]]["S_w"]
            host[f"{s['session']}_unweighted"] = sharpe(s_in[name][idx[2]], ppy)
            refs[f"{s['session']}_unweighted"] = pr[s["session"]]["S"]
    refuse_if_failed(FG.check_refs(host, refs), "b2 in-sample Sharpes (3 decimals)")

    # (c) no restart
    c = {}
    for lag in (2, 1):
        pi_, ps_ = PI[("in", lag)][0], PI[("sp", lag)][0]
        c[f"c1_features_identical_d{lag - 1}"] = bool(np.array_equal(pi_.features, ps_.features[:h0[lag]]))
        c[f"c4_holdout_features_warm_d{lag - 1}"] = bool(not np.any(np.all(ps_.features[h0[lag]:h0[lag] + 253] == 0, axis=(1, 2))))
    for name in ["stream_d1", "stream_d0", *rules]:
        lag = LAG.get(name, 2)
        bi, bs = books[(name, "in")], books[(name, "sp")]
        c[f"c2_positions_identical_{name}"] = bool(np.array_equal(bi, bs[:bi.shape[0]]))
        if name in ("stream_d1", "stream_d0"):
            c[f"c2_first_scored_row_same_{name}"] = first[(name, "in")] == first[(name, "sp")]
            c[f"c3_book_carried_{name}"] = FG.book_carried(net_fn, bs, PI[("sp", lag)][1], first[(name, "sp")], h0[lag])
            c[f"c4_position_at_boundary_{name}"] = bool(np.abs(bs[h0[lag]]).sum() > 0)
        else:
            ps_ = PI[("sp", 2)][0]
            p, q = bs[h0[2]], bs[h0[2] - 1]
            gross = float(p @ np.asarray(ps_.returns, float)[h0[2]])
            cost = float(np.abs(p - q) @ np.asarray(ps_.cost_rate, float)[h0[2]]
                         + np.clip(-p, 0, None) @ np.asarray(ps_.borrow_rate, float)[h0[2]])
            c[f"c3_book_carried_{name}"] = bool(abs(s_sp[name][h0[2]] - (gross - cost)) <= 1e-13)
    refuse_if_failed(c, "c no restart")

    # the holdout streams
    ho = {}
    for name in ["stream_d1", "stream_d0", *rules]:
        lag = LAG.get(name, 2)
        ho[name] = s_sp[name][h0[lag] - first[(name, "sp")]:]
        if len(ho[name]) != n_ho:
            raise GradingRefused(f"{name}: {len(ho[name])} holdout periods, not {n_ho}")

    # the items, in order: objects, submissions, books
    items = []
    for o in OBJECTS:
        r = results[RESULT_KEY[o]]
        items.append({"id": o, "type": "object", "test": r["test"], "certified": r["weighted_W2"]["certified"],
                      "L90": float(r["weighted_W2"]["L90"]), "L90_weighted": float(r["weighted_W2"]["L90"]),
                      "L90_statistic": OBJECT_L90_LABEL, "x": ho[o]})
    for s in submissions["submissions"]:
        if s["kind"] not in ("rule", "baseline_model"):
            raise GradingRefused(f"session {s['session']}: unknown submission kind {s['kind']!r}")
        x = ho["stream_d1"] if s["kind"] == "baseline_model" else ho[f"rule:{canonical(s['support'])}"]
        items.append({"id": s["session"], "type": "submission", "arm": s["arm"], "kind": s["kind"],
                      "L90": float(pr[s["session"]]["L90"]), "L90_statistic": SUBMISSION_L90_LABEL,
                      "L90_w2": float(pr[s["session"]]["L90_w2"]), "L90_w2_label": "recency-weighted, descriptive",
                      "x": x})
    subs_x = [it["x"] for it in items if it["type"] == "submission"]
    if subs_x:
        items.append({"id": "book_all", "type": "book", "x": np.mean(subs_x, axis=0)})
        for arm in ("A", "B"):
            xs = [it["x"] for it in items if it.get("arm") == arm]
            if xs:
                items.append({"id": f"book_{arm}", "type": "book", "arm": arm, "x": np.mean(xs, axis=0)})

    ps_ = PI[("sp", 2)][0]
    bc = np.asarray(RealSandbox(ps_, spec_class=CLS).base_feature_columns(), float)[h0[2]:]
    L = int(select_block_length(bc - bc.mean(axis=0)))
    Bn = B if B_ is None else B_
    rng = np.random.default_rng(SEED)
    draws = [stationary_bootstrap_indices(n_ho, L, rng) for _ in range(Bn)]
    ed = ps_.meta["earned_dates"][h0[2]:]
    in26 = np.array([d >= Y2026 for d in ed])
    RS = np.empty((Bn, len(items)), np.float32)
    RR = np.empty((Bn, len(items)), np.float32)
    out_items = []
    for j, it in enumerate(items):
        x = np.asarray(it.pop("x"), float)
        S = sharpe(x, ppy)
        RS[:, j] = [sharpe(x[i], ppy) for i in draws]
        RR[:, j] = [compounded(x[i]) for i in draws]
        lo, hi = (float(v) for v in np.quantile(RS[:, j], [0.05, 0.95]))
        rec = {**it, "realized": S, "net_return": compounded(x), "ci90": [lo, hi],
               "net_return_ci90": [float(v) for v in np.quantile(RR[:, j], [0.05, 0.95])],
               "only_2026": {"label": "2026-only, descriptive, never deciding", "rows": int(in26.sum()),
                             "realized": sharpe(x[in26], ppy) if in26.sum() >= 2 else None}}
        if "L90" in rec:
            rec["held"] = bool(S >= rec["L90"])
        if "L90_w2" in rec:
            rec["held_w2"] = {"held": bool(S >= rec["L90_w2"]), "label": "recency-weighted, descriptive"}
        out_items.append(rec)
    return {"registrations": {"panel": PANEL, "grading": GRADING, "cell": CELL}, "label": LABEL_WEAK,
            "checks": {"b1": b1, "c": c}, "n_periods": n_ho, "first_holdout_date": str(ed[0]),
            "last_date": str(ed[-1]), "block_length": L, "B": Bn, "seed": SEED, "items": out_items,
            "bootstrap": {"shape": [Bn, len(items)], "dtype": "float32", "item_ids": [i["id"] for i in out_items],
                          "sharpe_b64": b64(RS), "net_return_b64": b64(RR)},
            "fit_seconds": {f"{w}_d{lag - 1}": F[(w, lag)][3] for (w, lag) in F}, "seconds": time.time() - t0}


# -- refusals and main ----------------------------------------------------------------------

def refusals(expect_head: str) -> list[str]:
    bad = [b for b in ER.refusals(expect_head, None) if "wheel" not in b]    # no wheel on the host
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    for name, c in (("the panel's grading registration (GRADING)", GRADING), ("the agent cell (CELL)", CELL)):
        if not c:
            bad.append(f"{name} is not live (unset)")
        elif g("merge-base", "--is-ancestor", c, "HEAD").returncode:
            bad.append(f"{name} {c} is not an ancestor of HEAD")
    return bad


def versions() -> dict:
    import lightgbm
    import scipy
    return {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "lightgbm": lightgbm.__version__, "platform": f"{platform.system()} {platform.machine()}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cut", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--sessions", required=True, help="the holdout session list (data.etf_recent_sessions)")
    ap.add_argument("--sessions-sha", required=True)
    ap.add_argument("--read-dir", required=True)
    ap.add_argument("--submissions", required=True)
    ap.add_argument("--submissions-sha", required=True)
    ap.add_argument("--priced", required=True)
    ap.add_argument("--priced-sha", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-head", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head)
    for b in bad:
        say(f"a start-up: {b}", False)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    say("a start-up", True)
    out = Path(a.out)
    if (out / "grades.json").exists():
        raise SystemExit("grades exist; grading happens once")
    try:
        cut, bad_cut, paths = ER.check_cut(Path(a.cut).expanduser())
        if bad_cut:
            raise GradingRefused("; ".join(bad_cut))
        say("a cut CSVs against their record", True)
        sub_p, pr_p, rd = Path(a.submissions), Path(a.priced), Path(a.read_dir)
        if sha_file(sub_p) != a.submissions_sha or sha_file(pr_p) != a.priced_sha:
            raise GradingRefused("submissions.json or priced.json is not its pinned SHA-256")
        submissions, priced = json.loads(sub_p.read_text()), json.loads(pr_p.read_text())
        if priced.get("submissions_sha256") != a.submissions_sha:
            raise GradingRefused("priced.json was not made from this submissions.json")
        if priced.get("precompute_manifest_sha256") != sha_file(rd / "precompute" / "manifest.json"):
            raise GradingRefused("priced.json was not made from this read's precompute")
        say("a submissions and pricing pinned", True)
        dates_in, tickers, P_in, V_in, n_dropped = ER.load_from(paths)
        want, sessions_sha = load_sessions(Path(a.sessions), a.sessions_sha, cut)
        say("a holdout session list pinned and matching the cut record", True)
        dates_ho, P_ho, V_ho = make_holdout(Path(a.raw).expanduser(), tickers, want,
                                            Path(a.cut).expanduser().parent / "insample")
        say("a holdout sessions complete, none missing; boundary close matches", True)
        pins = json.loads((rd / "pins.json").read_text())
        results = json.loads((rd / "results.json").read_text())
        g = grade(dates_in, tickers, P_in, V_in, n_dropped, cut, dates_ho, P_ho, V_ho, pins, results, priced,
                  submissions, workers=a.workers)
    except GradingRefused as e:
        raise SystemExit(f"REFUSED: {e}")
    g.update({"git_head": a.expect_head, "submissions_sha256": a.submissions_sha, "priced_sha256": a.priced_sha,
              "holdout_sessions_sha256": a.sessions_sha,
              "cut_combined_sha256": cut["combined_sha256"], "versions": versions()})
    out.mkdir(parents=True, exist_ok=True)
    (out / "grades.json").write_text(json.dumps(g, indent=1, default=float))
    print(f"grades written to {out / 'grades.json'}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
