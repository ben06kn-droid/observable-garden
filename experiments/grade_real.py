"""Offline grading of real-panel submissions. A separate entry point on purpose.

    python -m experiments.grade_real --insample <dir> --holdout <plaintext dir> \
        --submissions <json> --submissions-sha256 <hex> --sealed-commit <S> \
        --grading-commit <G> --out <grades.json>

**The sandbox does not import this and cannot reach it.** `environments/`
contains no reference to this module; a test asserts that. Grading is something
the harness does after a run, on a machine where no agent session is running
(`prereg/agent-on-real-data.md`, `prereg/holdout-grading.md`).

The refusals run in this order, before any price is read:

1. **Platform pinned.** The features are built on one platform, the holdout host's
   (`PINNED_PLATFORM`). `_rank` breaks exact ties by numpy's unstable sort, which
   orders them differently on x86 and arm64.
2. **The code is the recorded code.** HEAD must equal the grading commit G, with a
   clean tracked tree.
3. **The submissions are sealed.** The sealed-submissions commit S must be an ancestor
   of HEAD, and the submissions file must hash to the recorded SHA-256.
4. **The inputs are the fetched inputs.** Every in-sample and holdout CSV must hash to
   its entry in the single fetch's manifest (`data/etf_manifest.json`), with no file
   missing or extra.
`--preflight` runs refusals 1-4, then reproduces the in-sample scores the agents saw
from the in-sample CSVs alone (`build_etf_panel` on this machine; tolerance 1e-9; runs
containing `ret1_rank` or `drawdown_rank` reported separately), prints the python,
numpy, pandas and scipy versions, and exits. It reads no holdout price.

5. **Plaintext only.** This module never decrypts. The loader's refusals (`.enc`,
   `.gpg`, `.asc`, anything under `~/Desktop`) apply to every path.

The grades file holds, per submission, the gross and net (5, 10 bps) Sharpe and the
**daily gross and net return streams over the graded periods**, with the graded dates
once. Streams are part of "grades". No price is written and no Sharpe is printed.

Then **one feature build over in-sample and holdout together**, exactly
`environments.real_panel.build_etf_panel`'s computation on the concatenated series,
and the grade over the periods whose **earned return** falls inside the window
(registered timing: signal at the close of t, held from the close of t+1 to t+2). The
book is continuous across the in-sample/holdout boundary, so the first graded period's
turnover is measured from the position actually held before it.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import platform as _platform
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
PINNED_PLATFORM = ("Linux", "x86_64")            # the holdout host, i-0886a189b85d4d051
GRADE_START = dt.date(2023, 1, 1)
GRADE_END = dt.date(2025, 12, 31)
COSTS_BPS = (5.0, 10.0)
MANIFEST = REPO / "data" / "etf_manifest.json"


class GradingRefused(RuntimeError):
    """Raised instead of grading against a holdout that should not be read yet."""


# -- the refusals ---------------------------------------------------------------------

def platform_now() -> tuple[str, str]:
    return _platform.system(), _platform.machine()


def require_platform(expected: tuple[str, str] | None = None) -> tuple[str, str]:
    expected = PINNED_PLATFORM if expected is None else expected
    got = platform_now()
    if tuple(got) != tuple(expected):
        raise GradingRefused(f"platform {got} is not the pinned {tuple(expected)}; the "
                             "feature build is platform-dependent and is done on one platform")
    return got


def _git(repo: Path, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)


def require_grading_commit(commit: str, repo: Path = REPO) -> str:
    """HEAD must be the recorded grading commit, with a clean tracked tree."""
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    full = _git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}").stdout.strip()
    if not full or head != full:
        raise GradingRefused(f"HEAD {head[:8]} is not the recorded grading commit "
                             f"{commit[:8]}")
    if _git(repo, "diff", "--quiet", "HEAD").returncode != 0:
        raise GradingRefused("the tracked tree is dirty; grading runs on the recorded "
                             "commit exactly")
    return head


def require_sealed_submissions(commit: str, repo: Path = REPO) -> None:
    """The submissions must be committed before the holdout is opened."""
    if _git(repo, "cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        raise GradingRefused(f"sealed-submissions commit {commit[:8]} is not in this repository")
    if _git(repo, "merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise GradingRefused(
            f"sealed-submissions commit {commit[:8]} is not an ancestor of HEAD; the "
            "submissions are not sealed, so the holdout is not opened")
    print(f"grade_real: sealed submissions {commit[:8]} confirmed as an ancestor of HEAD",
          flush=True)


def sha256_file(p: str | Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def require_file_hash(path: str | Path, expected: str, what: str) -> None:
    got = sha256_file(path)
    if got != expected:
        raise GradingRefused(f"{what} {Path(path).name} hashes to {got[:12]}..., not the "
                             f"recorded {expected[:12]}...")


def require_manifest_hashes(directory: str | Path, kind: str, manifest: dict) -> int:
    """Every CSV in `directory` must equal the manifest's `derived[ticker][kind]`
    SHA-256, and every ticker the manifest lists must be present. Returns the count."""
    from data.etf_loader import refuse_sealed_or_quarantined
    d = refuse_sealed_or_quarantined(directory)
    want = {t: v[kind]["sha256"] for t, v in manifest["derived"].items()}
    have = {p.stem: p for p in sorted(Path(d).glob("*.csv"))}
    missing, extra = sorted(set(want) - set(have)), sorted(set(have) - set(want))
    if missing or extra:
        raise GradingRefused(f"{kind} files differ from the manifest: missing {missing[:5]}, "
                             f"extra {extra[:5]}")
    bad = [t for t, p in have.items() if sha256_file(p) != want[t]]
    if bad:
        raise GradingRefused(f"{len(bad)} {kind} file(s) differ from the manifest's hash "
                             f"(first: {bad[0]})")
    return len(have)


# -- loading ---------------------------------------------------------------------------

def load_holdout(directory: str | Path) -> dict:
    """Plaintext holdout CSVs, after the loader's refusals. Nothing is decrypted."""
    from data.etf_loader import refuse_sealed_or_quarantined
    d = refuse_sealed_or_quarantined(directory)
    out = {}
    for p in sorted(Path(d).glob("*.csv")):
        refuse_sealed_or_quarantined(p)
        dates, adj = [], []
        with p.open(newline="") as fh:
            for row in csv.DictReader(fh):
                dates.append(dt.date.fromisoformat(row["date"]))
                adj.append(float(row["adjclose"]))
        out[p.stem] = (dates, np.array(adj))
    if not out:
        raise GradingRefused(f"no holdout CSVs under {d}")
    return out


def load_span(insample_dir: str | Path, holdout_dir: str | Path) -> dict:
    """In-sample (through the in-sample loader and its refusals) followed by holdout,
    per ticker. Same tickers; every holdout date after the last in-sample date."""
    from data.etf_loader import load_panel
    ins = load_panel(insample_dir)
    ho = load_holdout(holdout_dir)
    if set(ins) != set(ho):
        raise GradingRefused(f"tickers differ: in-sample only {sorted(set(ins) - set(ho))[:5]}, "
                             f"holdout only {sorted(set(ho) - set(ins))[:5]}")
    out = {}
    for t in ins:
        d0, a0 = ins[t][0], list(ins[t][1])
        d1, a1 = ho[t][0], list(ho[t][1])
        if d0 and d1 and min(d1) <= max(d0):
            raise GradingRefused(f"{t}: holdout dates overlap the in-sample dates")
        out[t] = (list(d0) + list(d1), np.array(a0 + a1, dtype=float))
    return out


# -- one feature build, and the grade ---------------------------------------------------

def build_span(prices: dict):
    """`build_etf_panel`'s computation over the whole span, untrimmed:
    (dates, tickers, F (T, M, 40), earn (T, M) with NaN where undefined)."""
    from environments.real_panel import ETF_BASE, _etf_base_signals, _rank, _zscore, declared_market
    tickers = sorted(prices)
    common = sorted(set.intersection(*(set(prices[t][0]) for t in tickers)))
    idx = {t: {d: i for i, d in enumerate(prices[t][0])} for t in tickers}
    P = np.array([[prices[t][1][idx[t][d]] for t in tickers] for d in common])
    logp = np.log(P)
    r = np.vstack([np.full((1, len(tickers)), np.nan), P[1:] / P[:-1] - 1.0])
    r0 = np.nan_to_num(r)
    sig = _etf_base_signals(logp, r0, declared_market(tickers, r0))
    feats = []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), _rank(sig[nm])]
    F = np.stack(feats, axis=2)
    earn = np.full_like(r, np.nan)
    earn[:-2] = r[2:]
    return common, tickers, F, earn


WARM = 252 + 1        # build_etf_panel's warm-up: the longest lookback


def feature_sha256(F: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(F, dtype=np.float64).tobytes()).hexdigest()


def grade_span(submissions: list[dict], dates, F, earn, start: dt.date, end: dt.date,
               costs_bps=COSTS_BPS, borrow_bps_yr: float = 50.0, days: int = 252) -> list[dict]:
    """Each submission's Sharpe over the periods t whose earned return, dated
    dates[t + 2], lies in [start, end]. Positions are formed at every t from the warm-up
    on, so the first graded period's turnover is from the position actually held."""
    T = len(dates)
    graded = np.array([WARM <= t <= T - 3 and start <= dates[t + 2] <= end
                       for t in range(T)])
    if not graded.any():
        raise GradingRefused(f"no period earns a return inside {start}..{end}")
    t0 = WARM
    ann = np.sqrt(days)
    out = []
    for sub in submissions:
        w = np.asarray(sub["weights"], dtype=float)
        scores = np.nan_to_num(F[t0:] @ w)
        wt = scores - scores.mean(axis=1, keepdims=True)
        gross = np.abs(wt).sum(axis=1, keepdims=True)
        wt = np.where(gross > 0, wt / np.where(gross > 0, gross, 1.0), wt)
        prev = np.vstack([np.zeros((1, wt.shape[1])), wt[:-1]])
        e = np.nan_to_num(earn[t0:])
        g = np.einsum("tm,tm->t", wt, e)
        turn = np.abs(wt - prev).sum(axis=1)
        borrow = np.clip(-wt, 0, None).sum(axis=1) * borrow_bps_yr * 1e-4 / days
        m = graded[t0:]

        def sharpe(x):
            x = x[m]
            sd = x.std(ddof=1)
            return float(x.mean() / sd * ann) if sd > 0 else 0.0
        row = {"name": sub.get("name", ""), "gross_sharpe": sharpe(g),
               "n_periods": int(m.sum()),
               "first_earned": dates[int(np.flatnonzero(graded)[0]) + 2].isoformat(),
               "last_earned": dates[int(np.flatnonzero(graded)[-1]) + 2].isoformat(),
               "stream": {"gross": [float(x) for x in g[m]]}}
        for c in costs_bps:
            net = g - turn * c * 1e-4 - borrow
            row[f"net_sharpe_{c:g}bps"] = sharpe(net)
            row["stream"][f"net_{c:g}bps"] = [float(x) for x in net[m]]
        out.append(row)
    return out


def graded_dates(dates, start: dt.date, end: dt.date) -> list[str]:
    """The earned-return dates of the graded periods, in order (the streams' index)."""
    T = len(dates)
    return [dates[t + 2].isoformat() for t in range(T)
            if WARM <= t <= T - 3 and start <= dates[t + 2] <= end]


def grade(submissions, insample_dir, holdout_dir, start=GRADE_START, end=GRADE_END):
    """One build over in-sample and holdout, then the grade. Returns (rows, meta)."""
    dates, tickers, F, earn = build_span(load_span(insample_dir, holdout_dir))
    rows = grade_span(submissions, dates, F, earn, start, end)
    meta = {"feature_matrix_sha256": feature_sha256(F), "T": len(dates),
            "assets": len(tickers), "span": [dates[0].isoformat(), dates[-1].isoformat()],
            "window": [start.isoformat(), end.isoformat()],
            "graded_dates": graded_dates(dates, start, end)}
    return rows, meta


# -- the preflight's in-sample reproduction ------------------------------------------------

REPRO_TOL = 1e-9
# the runs that store the in-sample score the agent saw (`submitted_sharpe`)
SCORE_DIRS = ("runs/etf_replay", "runs/etf_orientation")
TIE_FEATURES = ("ret1", "drawdown")       # their _rank columns break exact ties by platform


def versions_line() -> str:
    import numpy, pandas, scipy
    return (f"python {_platform.python_version()}, numpy {numpy.__version__}, "
            f"pandas {pandas.__version__}, scipy {scipy.__version__}")


def panel_net_scores(panel, weights: dict, cost_bps: float = 5.0,
                     borrow_bps_yr: float = 50.0, days: int = 252) -> dict:
    """The in-sample net score of each weight vector on `build_etf_panel`'s panel, with the
    panel's execution and costs (the computation `grade_span` uses, on the panel)."""
    ann = np.sqrt(days)
    out = {}
    for name, w in weights.items():
        scores = np.nan_to_num(panel.features @ np.asarray(w, float))
        wt = scores - scores.mean(axis=1, keepdims=True)
        gross = np.abs(wt).sum(axis=1, keepdims=True)
        wt = np.where(gross > 0, wt / np.where(gross > 0, gross, 1.0), wt)
        prev = np.vstack([np.zeros((1, wt.shape[1])), wt[:-1]])
        g = np.einsum("tm,tm->t", wt, panel.returns)
        net = (g - np.abs(wt - prev).sum(axis=1) * cost_bps * 1e-4
               - np.clip(-wt, 0, None).sum(axis=1) * borrow_bps_yr * 1e-4 / days)
        sd = net.std(ddof=1)
        out[name] = float(net.mean() / sd * ann) if sd > 0 else 0.0
    return out


def insample_reproduction(insample_dir, repo: Path | None = None) -> dict:
    """Build the in-sample panel with `build_etf_panel` from the in-sample CSVs on this
    machine, recompute every stored agent-seen score, and require agreement to REPRO_TOL.
    Runs containing a tie-sensitive rank feature are reported separately and never fail.
    The stored scores come from the committed run files (the sealed submissions carry
    names and weights only). Nothing under the holdout directory is touched."""
    from environments.real_panel import ETF_BASE, build_etf_panel
    from quixote.grammar import weights as grammar_weights
    repo = REPO if repo is None else repo
    tie_cols = {2 * i + 1 for i, nm in enumerate(ETF_BASE) if nm in TIE_FEATURES}
    stored, wts, tied = {}, {}, set()
    for d in SCORE_DIRS:
        for p in sorted((Path(repo) / d).glob("cell_*.json")):
            x = json.loads(p.read_text())
            sup = x.get("submitted_support")
            if not sup or x.get("submitted_sharpe") is None:
                continue
            support = tuple((int(k), float(v)) for k, v in sup)
            stored[x["run_id"]] = float(x["submitted_sharpe"])
            wts[x["run_id"]] = [float(v) for v in grammar_weights(support, 40)]
            if any(k in tie_cols for k, _ in support):
                tied.add(x["run_id"])
    if not stored:
        raise GradingRefused("no run stores the in-sample score its agent saw; the "
                             "in-sample reproduction has nothing to compare")
    got = panel_net_scores(build_etf_panel(insample_dir), wts)
    diffs = {n: abs(got[n] - stored[n]) for n in stored}
    main = {n: d for n, d in diffs.items() if n not in tied}
    worst = max(main.values()) if main else 0.0
    if worst > REPRO_TOL:
        bad = max(main, key=main.get)
        raise GradingRefused(f"in-sample reproduction failed: {bad} differs by {worst:.2e} "
                             f"(> {REPRO_TOL:g}) from the score its agent saw")
    return {"compared": len(main), "max_diff": worst,
            "tie_affected": {n: diffs[n] for n in sorted(tied)}}


def run_grading(insample, holdout, submissions, submissions_sha256, sealed_commit,
                grading_commit, manifest_path, out, window=(GRADE_START, GRADE_END),
                expected_platform=None, repo: Path | None = None,
                preflight: bool = False, reproduce_insample=None) -> dict:
    """The grading path, in its registered order. `main` calls it with the registered
    window and the pinned platform; only a rehearsal passes anything else, and says so."""
    repo = REPO if repo is None else repo
    plat = require_platform(expected_platform)
    head = require_grading_commit(grading_commit, repo)
    require_sealed_submissions(sealed_commit, repo)
    require_file_hash(submissions, submissions_sha256, "submissions file")
    manifest = json.loads(Path(manifest_path).read_text())
    n_in = require_manifest_hashes(insample, "insample", manifest)
    n_ho = require_manifest_hashes(holdout, "holdout", manifest)
    print(f"grade_real: platform {plat}; HEAD {head[:8]} = grading commit, clean; "
          f"submissions hash ok; {n_in} in-sample and {n_ho} holdout files match the "
          "manifest", flush=True)
    if preflight:
        rep = insample_reproduction(reproduce_insample or insample, repo)
        print(f"grade_real: in-sample reproduction: {rep['compared']} compared, max |diff| "
              f"{rep['max_diff']:.2e} (tolerance {REPRO_TOL:g}); tie-affected reported "
              f"separately: {rep['tie_affected'] or 'none'}", flush=True)
        print(f"grade_real: versions: {versions_line()}", flush=True)
        print("grade_real: PREFLIGHT ok — every guard passed; no holdout price was read and "
              "nothing was graded", flush=True)
        return {"preflight": True, "platform": list(plat), "grading_commit": head,
                "reproduction": rep}
    subs = json.loads(Path(submissions).read_text())
    rows, meta = grade(subs, insample, holdout, *window)
    result = {"grades": rows, **meta, "platform": list(plat), "grading_commit": head,
              "sealed_commit": sealed_commit, "submissions_sha256": submissions_sha256}
    Path(out).write_text(json.dumps(result, indent=1) + "\n")
    print(f"grade_real: {len(rows)} submissions graded over {meta['window'][0]}.."
          f"{meta['window'][1]}; feature matrix {meta['feature_matrix_sha256'][:16]}... "
          f"(T {meta['T']}, {meta['assets']} assets); written to {out} unread", flush=True)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--insample", required=True)
    ap.add_argument("--holdout", required=True, help="a PLAINTEXT holdout directory")
    ap.add_argument("--submissions", required=True, help="JSON: [{name, weights}, ...]")
    ap.add_argument("--submissions-sha256", required=True)
    ap.add_argument("--sealed-commit", required=True)
    ap.add_argument("--grading-commit", required=True)
    ap.add_argument("--manifest", default=str(MANIFEST))
    ap.add_argument("--out", default=None)
    ap.add_argument("--preflight", action="store_true",
                    help="run every guard (platform, commit, ancestor, submissions hash, "
                         "content hashes) and exit before any price is read")
    a = ap.parse_args(argv)
    if not a.preflight and not a.out:
        ap.error("--out is required unless --preflight")
    run_grading(a.insample, a.holdout, a.submissions, a.submissions_sha256,
                a.sealed_commit, a.grading_commit, a.manifest, a.out,
                preflight=a.preflight)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
