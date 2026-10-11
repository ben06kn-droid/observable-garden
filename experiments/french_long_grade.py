"""French long history, B1: the holdout grader (`prereg/french-long-b1-grading.md`, live at
00417de103785335f2b3a4b6860b7e81a1b33135). Runs on the holdout host, by the author.

In this order, refusing on any failure before any holdout value is computed (section 4):
  a. start-up: the registration is an ancestor of HEAD; HEAD equals --expect-head; no tracked
     changes; Linux x86_64; LightGBM 4.7.0 with the Linux library's SHA-256; the learn2 blobs
     are the confirmation's; each cut CSV has its record's SHA-256, and the b1 CSV is
     c380c3ea...0693; every holdout row is dated 1990-01-01 .. 1995-12-31 and none is missing;
  b. reproduction of the in-sample read on the host: (1) X, version 2's X block and the groups
     (both timings, from the b1 cut alone) equal `pins.json`; (2) each object's in-sample
     weighted net Sharpe equals the read to 3 decimals, and the two streams' unweighted net
     Sharpe too; (3) the spanning panel's entry dates equal `pins.json`'s;
  c. no restart: (1) the spanning panel's features on the in-sample rows are bit-identical to
     the in-sample-only build's; (2) each object's positions on the in-sample rows are
     bit-identical between the spanning and in-sample-only runs; (3) each object's net return
     on its first holdout period equals its gross return minus the cost of trading from the
     carried position, to 1e-13; (4) no all-zero feature row in the first 253 holdout rows,
     and a nonzero Sancho position at the first holdout row.
Each check prints one line, passed or not, and no value. Then section 5: per object the
realised UNWEIGHTED net Sharpe over the graded periods with its stationary-bootstrap 90%
interval (B 10,000, one shared resample, the class rule's block length on the holdout's base
columns, seed 719000); held iff realised >= the in-sample weighted L90; and the descriptive
lines. Written to grades.json. **No value is printed.** The reader is
`experiments/read_french_long_grade.py`.

    python -m experiments.french_long_grade --read b1 --insample-cut ~/french_long/b1_insample.cut.json \\
        --holdout-cut ~/french_long/b1_holdout.cut.json --out runs/french_long_b1_grade/<date> \\
        --expect-head <G> --workers 4
"""
from __future__ import annotations

import argparse
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

from experiments import french_long_read as FL

LIVE = "00417de103785335f2b3a4b6860b7e81a1b33135"
B1_CSV_SHA256 = "c380c3eaa578734a4de8c019220b5babce9c2e6adc3f7a6175a68999d4910693"
READ_DIR = Path("runs/french_long_b1/2026-10-11")
HOLDOUT = (dt.date(1990, 1, 1), dt.date(1995, 12, 31))
B = 10_000
SEED = 719000
H = FL.H
MEMBER_INDEX = 54952
OBJECTS = ("stream_d1", "stream_d0", "class_member")
RESULT_KEY = {"stream_d1": "test1_stream_d1", "stream_d0": "test2_stream_d0", "class_member": "test3_class_d1"}
LAG = {"stream_d1": 2, "stream_d0": 1, "class_member": 2}
UNWEIGHTED_LABEL = "unweighted, descriptive, not the rule"


class GradingRefused(RuntimeError):
    pass


# -- inputs -------------------------------------------------------------------------------

def load_holdout(path: Path):
    """The b1-holdout CSV: every row dated in the window, strictly increasing, none missing."""
    dates, names, R = FL.read_csv(path, 19951231)
    if not dates:
        raise GradingRefused("the holdout file has no row")
    if dates[0] < HOLDOUT[0] or dates[-1] > HOLDOUT[1]:
        raise GradingRefused("a holdout row outside 1990-01-01 .. 1995-12-31")
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise GradingRefused("the holdout dates are not strictly increasing")
    if np.isnan(R).any():
        raise GradingRefused("a missing holdout value (it would move an entry date)")
    return dates, names, R


def cut_csv(record: Path, expect_sha: str | None = None) -> tuple[Path, dict]:
    rec = json.loads(Path(record).expanduser().read_text())
    p = Path(record).expanduser().with_name(Path(rec["csv"]).name)
    if not p.exists():
        raise GradingRefused(f"{p.name} is missing")
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    if sha != rec["csv_sha256"] or (expect_sha is not None and sha != expect_sha):
        raise GradingRefused(f"{p.name} is not its cut record's (or the registered) SHA-256")
    return p, rec


# -- objects ------------------------------------------------------------------------------

def member_support(names_features, features: list[str]):
    """The member's ((k, sign), ...) from its signed feature names."""
    idx = {n: k for k, n in enumerate(names_features)}
    return tuple((idx[f[1:]], 1.0 if f[0] == "+" else -1.0) for f in features)


def member_book(panel, support):
    """(positions (T, M), net stream (T,)) of one class member by the read's kernel
    (`environments.planted_fast`): stateless positions D_t w / g_t, the book continuous from
    row 0."""
    import environments.planted_fast as pf
    pf.check_panel(panel)
    D = pf.demeaned(panel)
    Wf = pf.weight_matrix([support], D.shape[2])
    T, M, K = D.shape
    P = (D.reshape(T * M, K) @ Wf).reshape(T, M)
    g = np.abs(P).sum(axis=1)
    pos = np.where((g > 0)[:, None], P / np.where(g > 0, g, 1.0)[:, None], P)
    g2, k = pf._positions_cost(panel, D, Wf)
    num = (pf.feature_returns(panel) @ Wf).T
    s = (np.divide(num, g2, out=np.zeros_like(num), where=g2 > 0) - k)[0]
    return pos, s


def sharpe(x, ppy: float = 252.0) -> float:
    """The read's unweighted statistic (`ClassTable._sharpe_of`): mean / sd(ddof 1) * sqrt(ppy)."""
    x = np.asarray(x, float)
    sd = float(x.std(ddof=1))
    return float(x.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0


def wsharpe(x, ppy: float = 252.0) -> float:
    from estimator import recency as Rc
    x = np.asarray(x, float)
    return float(Rc.weighted_sharpe(x, Rc.weights(len(x), H), ppy))


def stream_net(net_fn, book, inp, first: int) -> np.ndarray:
    """The stream over all its rows, from its first scored row, one continuous book."""
    return net_fn(book, inp, np.arange(first, inp.earned.shape[0]))


def default_net(book, inp, rows):
    from learn2 import views as Vw
    return Vw.net_stream(book, inp, rows)


# -- checks -------------------------------------------------------------------------------

def check_pins(host_pins: dict, pins: dict) -> dict:
    """(b1) the host's in-sample pins against `pins.json`."""
    out = {"cut_csv_sha256": host_pins["cut_csv_sha256"] == pins["cut_csv_sha256"]}
    for d in ("d1", "d0"):
        for f in ("X_features_sha256", "X_shape", "v2_X_block_sha256", "groups_sha256"):
            out[f"{d}_{f}"] = host_pins[d][f] == pins[d][f]
    return out


def check_refs(host: dict, refs: dict) -> dict:
    """(b2) the host's in-sample Sharpes against the read, each to 3 decimals."""
    return {k: round(host[k], 3) == round(refs[k], 3) for k in refs}


def book_carried(net_fn, book, inp, first: int, h0: int) -> bool:
    """(c3) the stream's first holdout period: gross minus the cost of trading from the carried
    position. A book restarted from zero at the boundary fails it."""
    s = stream_net(net_fn, book, inp, first)
    p, q = book[h0], book[h0 - 1]
    gross = float(p @ inp.earned[h0])
    cost = float(np.abs(p - q) @ inp.cost_rate[h0] + np.clip(-p, 0, None) @ inp.borrow_rate[h0])
    return bool(abs(s[h0 - first] - (gross - cost)) <= 1e-13)


def say(name: str, ok: bool) -> None:
    print(f"check {name}: {'pass' if ok else 'FAIL'}", flush=True)


def refuse_if_failed(checks: dict, what: str) -> None:
    for k, v in checks.items():
        say(f"{what}: {k}", bool(v))
    bad = [k for k, v in checks.items() if v is False]
    if bad:
        raise GradingRefused(f"{what} failed: {', '.join(bad)}; nothing graded")


# -- the grading --------------------------------------------------------------------------

def fit_all(jobs, workers: int, fit_fn=None):
    fit_fn = fit_fn or FL._fit
    if workers <= 1:
        return [fit_fn(j) for j in jobs]
    with ProcessPoolExecutor(workers) as ex:
        return list(ex.map(fit_fn, jobs))


def grade(dates_in, names, R_in, dates_ho, R_ho, pins: dict, results: dict, paths_in, ref_check=check_refs,
          workers: int = 4, fit_fn=None, net_fn=None, B_: int | None = None) -> dict:
    """Sections 3-5 on the given cuts. Raises GradingRefused before any holdout value on a
    failure. `fit_fn`, `net_fn` and `ref_check` are injectable for tests only; main passes
    the registered ones."""
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    from experiments.french_holdout_grade import curve_at
    net_fn = net_fn or default_net
    t0 = time.time()
    dates_sp = list(dates_in) + list(dates_ho)
    R_sp = np.vstack([R_in, R_ho])
    checks = {}

    # (b1) the in-sample pins, from the b1 cut alone
    host_pins = FL.pin_record(dates_in, names, R_in, paths_in)
    checks["b1"] = check_pins(host_pins, pins)
    refuse_if_failed(checks["b1"], "b1 pins")

    # the panels and the four Sancho fits
    P = {}
    for where, (d, R) in {"in": (dates_in, R_in), "sp": (dates_sp, R_sp)}.items():
        for lag in (2, 1):
            P[(where, lag)] = FL.sancho_inputs(d, names, R, lag)
    jobs = [(dates_in, names, R_in, 2), (dates_in, names, R_in, 1), (dates_sp, names, R_sp, 2), (dates_sp, names, R_sp, 1)]
    fits = fit_all(jobs, workers, fit_fn)
    F = {("in", 2): fits[0], ("in", 1): fits[1], ("sp", 2): fits[2], ("sp", 1): fits[3]}
    h0 = {lag: P[("in", lag)][0].features.shape[0] for lag in (2, 1)}       # first holdout row
    n_ho = len(dates_ho)

    books, streams_in, streams_sp, firsts = {}, {}, {}, {}
    for obj in ("stream_d1", "stream_d0"):
        lag = LAG[obj]
        for where in ("in", "sp"):
            panel, info, inp = P[(where, lag)]
            _, book, first, _ = F[(where, lag)]
            b = np.where(info["eligible_earned"], book, 0.0)
            books[(obj, where)] = b
            firsts[(obj, where)] = first
            s = stream_net(net_fn, b, inp, first)
            (streams_in if where == "in" else streams_sp)[obj] = s
    pin_ = P[("in", 2)][0]
    support = member_support(pin_.feature_names, results["test3_class_d1"]["weighted_W2"]["best_member"]["features"])
    for where in ("in", "sp"):
        pos, s = member_book(P[(where, 2)][0], support)
        books[("class_member", where)] = pos
        (streams_in if where == "in" else streams_sp)["class_member"] = s
        firsts[("class_member", where)] = 0

    # (b2) the in-sample Sharpes, from the in-sample-only runs
    ppy = float(pin_.periods_per_year)
    host = {f"{o}_weighted": wsharpe(streams_in[o], ppy) for o in OBJECTS}
    host.update({f"{o}_unweighted": sharpe(streams_in[o], ppy) for o in ("stream_d1", "stream_d0")})
    refs = {f"{o}_weighted": results[RESULT_KEY[o]]["weighted_W2"]["S"] for o in OBJECTS}
    refs.update({f"{o}_unweighted": results[RESULT_KEY[o]]["unweighted"]["S"] for o in ("stream_d1", "stream_d0")})
    checks["b2"] = ref_check(host, refs)
    refuse_if_failed(checks["b2"], "b2 in-sample Sharpes (3 decimals)")

    # (b3) entry dates
    checks["b3"] = {f"d{lag - 1}_entry_dates": dict(zip(names, P[("sp", lag)][1]["entry_date"])) == pins[f"d{lag - 1}"]["entry_dates"]
                    for lag in (2, 1)}
    refuse_if_failed(checks["b3"], "b3 entry dates")

    # (c1-c4) no restart
    c = {}
    for lag in (2, 1):
        pi, ps = P[("in", lag)][0], P[("sp", lag)][0]
        c[f"c1_features_identical_d{lag - 1}"] = bool(np.array_equal(pi.features, ps.features[:h0[lag]]))
        c[f"c4_holdout_features_warm_d{lag - 1}"] = bool(not np.any(np.all(ps.features[h0[lag]:h0[lag] + 253] == 0, axis=(1, 2))))
    for o in OBJECTS:
        lag = LAG[o]
        bi, bs = books[(o, "in")], books[(o, "sp")]
        c[f"c2_positions_identical_{o}"] = bool(np.array_equal(bi, bs[:bi.shape[0]]))
        c[f"c2_first_scored_row_same_{o}"] = firsts[(o, "in")] == firsts[(o, "sp")]
        if o == "class_member":
            ps = P[("sp", 2)][0]
            s = streams_sp[o]
            p, q = bs[h0[lag]], bs[h0[lag] - 1]
            gross = float(p @ np.asarray(ps.returns, float)[h0[lag]])
            cost = float(np.abs(p - q) @ np.asarray(ps.cost_rate, float)[h0[lag]]
                         + np.clip(-p, 0, None) @ np.asarray(ps.borrow_rate, float)[h0[lag]])
            c[f"c3_book_carried_{o}"] = bool(abs(s[h0[lag]] - (gross - cost)) <= 1e-13)
        else:
            inp = P[("sp", lag)][2]
            c[f"c3_book_carried_{o}"] = book_carried(net_fn, bs, inp, firsts[(o, "sp")], h0[lag])
            c[f"c4_position_at_boundary_{o}"] = bool(np.abs(bs[h0[lag]]).sum() > 0)
    checks["c"] = c
    refuse_if_failed(c, "c no restart")

    # section 5: the graded quantity, and the descriptive lines
    ho = {}
    for o in OBJECTS:
        lag = LAG[o]
        s = streams_sp[o]
        ho[o] = s[h0[lag] - firsts[(o, "sp")]:]
        if len(ho[o]) != n_ho:
            raise GradingRefused(f"{o}: {len(ho[o])} graded periods, not {n_ho}")
    ps = P[("sp", 2)][0]
    bc = np.asarray(RealSandbox(ps, spec_class=CLS).base_feature_columns(), float)[h0[2]:]
    L = int(select_block_length(bc - bc.mean(axis=0)))
    Bn = B if B_ is None else B_
    rng = np.random.default_rng(SEED)
    idx = [stationary_bootstrap_indices(n_ho, L, rng) for _ in range(Bn)]
    objects = {}
    for o in OBJECTS:
        r = results[RESULT_KEY[o]]
        w = r["weighted_W2"]
        x = ho[o]
        S = sharpe(x, ppy)
        reps = np.array([sharpe(x[i], ppy) for i in idx])
        lo, hi = (float(v) for v in np.quantile(reps, [0.05, 0.95]))
        L90 = float(w["L90"])
        C, clipped = curve_at(w["confidence"], S)
        rec = {"test": r["test"], "certified": w["certified"], "L90_weighted": L90, "realized": S,
               "ci90": [lo, hi], "held": bool(S >= L90),
               "descriptive": {"realized_minus_L90": S - L90, "ci90_minus_L90": [lo - L90, hi - L90],
                               "C_at_realized": C, "C_clipped": clipped}}
        if o != "class_member":
            Lu = float(r["unweighted"]["L90"])
            rec["descriptive"]["unweighted"] = {"label": UNWEIGHTED_LABEL, "L90_unweighted": Lu,
                                                "realized_minus_L90_unweighted": S - Lu}
        else:
            rec["member"] = {"index": MEMBER_INDEX, "features": w["best_member"]["features"]}
        objects[o] = rec
    ed = ps.meta["earned_dates"]
    return {"registration": LIVE, "read": "b1", "checks": checks, "n_periods": n_ho,
            "first_holdout_date": str(ed[h0[2]]), "last_date": str(ed[-1]),
            "block_length": L, "B": Bn, "seed": SEED, "objects": objects,
            "fit_seconds": {f"{w}_d{lag - 1}": F[(w, lag)][3] for (w, lag) in F}, "seconds": time.time() - t0}


# -- refusals and main ----------------------------------------------------------------------

def refusals(expect_head: str) -> list[str]:
    bad = [b for b in FL.refusals(expect_head, None) if "wheel" not in b]      # no wheel on the host; the library's SHA-256 is checked
    if subprocess.run(["git", "merge-base", "--is-ancestor", LIVE, "HEAD"], capture_output=True).returncode != 0:
        bad.append(f"the registration {LIVE} is not an ancestor of HEAD")
    return bad


def versions() -> dict:
    import lightgbm
    import scipy
    return {"python": sys.version.split()[0], "numpy": np.__version__, "scipy": scipy.__version__,
            "lightgbm": lightgbm.__version__, "platform": f"{platform.system()} {platform.machine()}"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", required=True, choices=["b1"])
    ap.add_argument("--insample-cut", required=True)
    ap.add_argument("--holdout-cut", required=True)
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
        p_in, rec_in = cut_csv(a.insample_cut, B1_CSV_SHA256)
        p_ho, rec_ho = cut_csv(a.holdout_cut)
        say("a cut CSVs against their records", True)
        dates_in, names, R_in = FL.load("b1", [p_in])
        dates_ho, names_ho, R_ho = load_holdout(p_ho)
        if names_ho != names:
            raise GradingRefused("the holdout's industries are not the in-sample's")
        if dates_ho[0] <= dates_in[-1]:
            raise GradingRefused("the holdout does not follow the in-sample")
        say("a holdout rows in the window, none missing", True)
        pins = json.loads((READ_DIR / "pins.json").read_text())
        if pins["cut_csv_sha256"] != {p_in.name: B1_CSV_SHA256}:
            raise GradingRefused("pins.json does not name the b1 cut")
        results = json.loads((READ_DIR / "results.json").read_text())
        if results["test3_class_d1"]["weighted_W2"]["best_member"]["index"] != MEMBER_INDEX:
            raise GradingRefused("results.json's weighted best member is not index 54952")
        g = grade(dates_in, names, R_in, dates_ho, R_ho, pins, results, [p_in], workers=a.workers)
    except GradingRefused as e:
        raise SystemExit(f"REFUSED: {e}")
    g.update({"git_head": a.expect_head, "holdout_csv_sha256": rec_ho["csv_sha256"], "holdout_rows": len(dates_ho),
              "holdout_cut_record": {k: rec_ho[k] for k in ("cut", "window", "rows", "first_date", "last_date")},
              "insample_csv_sha256": rec_in["csv_sha256"], "versions": versions()})
    out.mkdir(parents=True, exist_ok=True)
    (out / "grades.json").write_text(json.dumps(g, indent=1, default=float))
    print(f"grades written to {out / 'grades.json'}; no value printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
