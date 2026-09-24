"""Offline grading of real-panel submissions. A separate entry point on purpose.

    python -m experiments.grade_real --holdout <plaintext dir> --submissions <json> \
        --sealed-commit <sha>

**The sandbox does not import this and cannot reach it.** `environments/`
contains no reference to this module; a test asserts that. Grading is something
the harness does after a run, on a machine where no agent session is running
(`prereg/agent-on-real-data.md`).

Two refusals before anything is graded:

1. **The sealed-submissions commit must be an ancestor of HEAD.** Grading a
   submission that is not yet committed would let the submission move after the
   holdout was seen.
2. **The holdout path must be plaintext, and not a sealed archive.** This module
   never decrypts: the second copy's passphrase is not on this machine, and
   `openssl enc -d` is the author's step, run on a machine with no agent session.
   The loader's refusals (`.enc`, `.gpg`, `.asc`, anything under `~/Desktop`)
   apply here too.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent


class GradingRefused(RuntimeError):
    """Raised instead of grading against a holdout that should not be read yet."""


def require_sealed_submissions(commit: str, repo: Path = REPO) -> None:
    """The submissions must be committed before the holdout is opened."""
    def git(*a):
        return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True)
    if git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        raise GradingRefused(f"sealed-submissions commit {commit[:8]} is not in this repository")
    if git("merge-base", "--is-ancestor", commit, "HEAD").returncode != 0:
        raise GradingRefused(
            f"sealed-submissions commit {commit[:8]} is not an ancestor of HEAD; the "
            "submissions are not sealed, so the holdout is not opened")
    print(f"grade_real: sealed submissions {commit[:8]} confirmed as an ancestor of HEAD",
          flush=True)


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


def grade(submissions: list[dict], holdout: dict, cost_bps: float = 5.0,
          borrow_bps_yr: float = 50.0, days: int = 252) -> list[dict]:
    """Each submission's holdout Sharpe, gross and net, under the registered
    execution: signal at the close of t, held from the close of t+1 to t+2."""
    from environments.real_panel import ETF_BASE, _etf_base_signals, _rank, _zscore
    tickers = sorted(holdout)
    common = sorted(set.intersection(*(set(holdout[t][0]) for t in tickers)))
    idx = {t: {d: i for i, d in enumerate(holdout[t][0])} for t in tickers}
    P = np.array([[holdout[t][1][idx[t][d]] for t in tickers] for d in common])
    r = np.vstack([np.zeros((1, len(tickers))), P[1:] / P[:-1] - 1.0])
    sig = _etf_base_signals(np.log(P), r, tickers.index("SPY") if "SPY" in tickers else 0)
    cols = []
    for nm in ETF_BASE:
        cols += [_zscore(sig[nm]), _rank(sig[nm])]
    F = np.stack(cols, axis=2)
    earn = np.vstack([r[2:], np.zeros((2, len(tickers)))])

    out = []
    for sub in submissions:
        w = np.asarray(sub["weights"], dtype=float)
        scores = np.nan_to_num(F @ w)
        wt = scores - scores.mean(axis=1, keepdims=True)
        gross = np.abs(wt).sum(axis=1, keepdims=True)
        wt = np.divide(wt, np.where(gross > 0, gross, 1.0))
        prev = np.vstack([np.zeros((1, len(tickers))), wt[:-1]])
        g = np.einsum("tm,tm->t", wt, earn)
        c = np.abs(wt - prev).sum(axis=1) * cost_bps * 1e-4
        b = np.clip(-wt, 0, None).sum(axis=1) * borrow_bps_yr * 1e-4 / days
        net = g - c - b
        ann = np.sqrt(days)
        out.append({"name": sub.get("name", ""),
                    "gross_sharpe": float(g.mean() / g.std(ddof=1) * ann) if g.std() else 0.0,
                    "net_sharpe": float(net.mean() / net.std(ddof=1) * ann) if net.std() else 0.0,
                    "n_periods": int(len(net))})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", required=True, help="a PLAINTEXT holdout directory")
    ap.add_argument("--submissions", required=True, help="JSON: [{name, weights}, ...]")
    ap.add_argument("--sealed-commit", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    require_sealed_submissions(a.sealed_commit)
    rows = grade(json.loads(Path(a.submissions).read_text()), load_holdout(a.holdout))
    text = json.dumps(rows, indent=2)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
