"""The reader for 6.5 holdout grading (`prereg/holdout-grading.md`). It prints readouts
(1)-(4), in order, and nothing else.

Inputs:
- the grades file R that `experiments/grade_real.py` writes: per submission, Sharpe and
  daily gross and net streams over the graded days;
- the step-0 re-priced records (`price_runs --reprice-to`): the class tier at
  B = 1,000 with confidence fields and the class-null maxima, and the replay verdict
  where one exists;
- the 80 run files, for arm and the agent's stated mean and sd.

**Every interval comes from one joint stationary block bootstrap over the graded days**:
mean block length 9 (6.5's gate on this panel), B = 10,000, seed 690000. The same
resampled days apply to every stream. sr_deflated's Z_b come from default_rng(690001).

    python -m experiments.holdout_grading_read --grades <R.json> \\
        --repriced runs/etf_repriced_b1000 --runs runs/etf_control runs/etf_declared_class \\
        runs/etf_replay runs/etf_orientation
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import norm

BLOCK_LENGTH = 9            # prereg/agent-on-real-data.md: the gate's stationary bootstrap
B_BOOT = 10_000
SEED_BOOT = 690_000
SEED_Z = 690_001
DAYS = 252
ANN = np.sqrt(DAYS)
ARMS = {"control": "control", "declared-class gate": "declared-class gate",
        "replay gate": "replay gate", "orientation": "orientation"}


# -- the joint bootstrap ------------------------------------------------------------

def bootstrap_counts(T: int, B: int = B_BOOT, L: int = BLOCK_LENGTH,
                     seed: int = SEED_BOOT) -> np.ndarray:
    """(T, B) counts: how often each graded day appears in each replicate. One draw of
    day indices per replicate, shared by every stream."""
    from estimator.bootstrap import stationary_bootstrap_indices
    rng = np.random.default_rng(seed)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    return C


def sharpe(x: np.ndarray) -> np.ndarray:
    """Annualised Sharpe of each row (ddof 1)."""
    x = np.atleast_2d(np.asarray(x, float))
    sd = x.std(axis=1, ddof=1)
    return np.where(sd > 0, x.mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0) * ANN


def boot_sharpes(X: np.ndarray, C: np.ndarray) -> np.ndarray:
    """(n, B) Sharpe of each stream on each joint replicate (from the counts)."""
    T = X.shape[1]
    m = (X @ C) / T
    v = ((X * X) @ C - T * m * m) / (T - 1)
    pos = v > 0
    return np.where(pos, m / np.sqrt(np.where(pos, v, 1.0)), 0.0) * ANN


def pct(a, q):
    return float(np.percentile(a, q))


# -- CRPS -----------------------------------------------------------------------------

def crps_normal(mu, sd, y):
    if not sd or sd <= 0:
        return abs(mu - y)
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


def crps_sample(s, y):
    s = np.sort(np.asarray(s, float))
    n = s.size
    e1 = np.abs(s - y).mean()
    e2 = 2 * np.sum((2 * np.arange(1, n + 1) - n - 1) * s) / (n * n)
    return float(e1 - 0.5 * e2)


def crps_curve(curve, y):
    from quixote.confidence import GRID, masses
    m = masses(np.asarray(curve, float))
    return float((m * np.abs(GRID - y)).sum()
                 - 0.5 * (m[:, None] * m[None, :] * np.abs(GRID[:, None] - GRID[None, :])).sum())


# -- loading ----------------------------------------------------------------------------

def load(grades_path, repriced_root, run_dirs):
    g = json.loads(Path(grades_path).read_text())
    rec = {}
    for p in Path(repriced_root).rglob("cell_*.json"):
        r = json.loads(p.read_text())
        rec[r["run_id"]] = r
    runs = {}
    for d in run_dirs:
        for p in Path(d).glob("cell_*.json"):
            x = json.loads(p.read_text())
            if x.get("submitted_support"):
                runs[x["run_id"]] = x
    rows = []
    for s in g["grades"]:
        name = s["name"]
        if name not in rec or name not in runs:
            raise SystemExit(f"{name}: missing its re-priced record or its run file")
        rows.append({"name": name, "grade": s, "rec": rec[name], "run": runs[name]})
    return g, rows


def _rank_feature_runs(rows):
    """Submissions using ret1_rank or drawdown_rank (exact ties on x86 differ)."""
    from environments.real_panel import ETF_BASE
    idx = {2 * i + 1 for i, nm in enumerate(ETF_BASE) if nm in ("ret1", "drawdown")}
    return [r["name"] for r in rows
            if any(int(k) in idx for k, _ in r["run"]["submitted_support"])]


# -- the read ---------------------------------------------------------------------------

def read(g, rows, B=B_BOOT) -> str:
    L: list[str] = []
    P = L.append
    names = [r["name"] for r in rows]
    arm = np.array([r["run"].get("arm", "") for r in rows])
    S = {k: np.array([r["grade"]["stream"][k] for r in rows]) for k in
         ("gross", "net_5bps", "net_10bps")}
    T = S["net_5bps"].shape[1]
    C = bootstrap_counts(T, B)
    real = {k: sharpe(v) for k, v in S.items()}
    boot = {k: boot_sharpes(v, C) for k, v in S.items()}
    years = T / DAYS
    cp = [r["rec"]["class_p"] for r in rows]

    # (1) registered by 6.5
    P("(1) REGISTERED BY 6.5")
    sup = [r["rec"]["superseded"] for r in rows]
    n_pass = sum(1 for s in sup if (s.get("class_p") or {}).get("status") == "CERTIFIED"
                 or (s.get("verdict") or {}).get("status") == "CERTIFIED")
    P(f"   PASS against FAIL: {'no PASS' if n_pass == 0 else f'{n_pass} PASS'} "
      f"(the registered B = 200 results); {len(rows) - n_pass} FAIL")
    fail = np.array([not ((s.get("class_p") or {}).get("status") == "CERTIFIED"
                          or (s.get("verdict") or {}).get("status") == "CERTIFIED")
                     for s in sup])
    P("   FAIL side, median holdout Sharpe [95% joint bootstrap over days]:")
    for a in [None] + sorted(set(arm)):
        sel = fail & ((arm == a) if a else True)
        if not sel.any():
            continue
        parts = []
        for k, lab in (("gross", "gross"), ("net_5bps", "net 5"), ("net_10bps", "net 10")):
            med = float(np.median(real[k][sel]))
            bm = np.median(boot[k][sel], axis=0)
            parts.append(f"{lab} {med:+.3f} [{pct(bm, 2.5):+.3f}, {pct(bm, 97.5):+.3f}]")
        P(f"      {a or 'pooled':<20} n {int(sel.sum()):2d}  " + "  ".join(parts))
    z = np.random.default_rng(SEED_Z).standard_normal(len(cp[0]["null_max_draws"]))
    cover, lo_hi, below, above = [], [], 0, 0
    for i, c in enumerate(cp):
        M = np.asarray(c["null_max_draws"], float)
        point = c["submitted_score"] - M.mean()
        se = np.sqrt((1 + point * point / 2) / years)
        F = c["submitted_score"] - M + se * z[:M.size]
        lo, hi = pct(F, 2.5), pct(F, 97.5)
        lo_hi.append((lo, hi, F))
        y = real["net_5bps"][i]
        cover.append(lo <= y <= hi)
        below += y < lo
        above += y > hi
    cov_b = np.mean([[lo <= boot["net_5bps"][i, b] <= hi for b in range(B)]
                     for i, (lo, hi, _) in enumerate(lo_hi)], axis=0)
    P(f"   sr_deflated 95% predictive interval (class tier, exact from the stored M_b): "
      f"covers {sum(cover)}/{len(cover)} = {np.mean(cover):.3f} "
      f"[{pct(cov_b, 2.5):.3f}, {pct(cov_b, 97.5):.3f}]; below {below}, above {above} "
      "(net 5 bps); the replay gate's is not computed (its draws are not stored)")

    # (2) H1
    P("(2) H1 — THE GATE'S LOWER BOUNDS AGAINST REALIZED")
    Lb = {g_: np.array([c["confidence"]["L"][g_] for c in cp]) for g_ in ("0.90", "0.95", "0.99")}
    stat = float(np.mean(real["net_5bps"] - Lb["0.90"]))
    sb = (boot["net_5bps"] - Lb["0.90"][:, None]).mean(axis=0)
    up = pct(sb, 95)
    P(f"   mean(realized net 5 bps - L_0.90) over {len(rows)} = {stat:+.4f}; one-sided 95% "
      f"upper end {up:+.4f} -> {'FAILS LOW: the bounds overstate on this holdout' if up < 0 else 'holds: not shown to overstate on this holdout'}")
    for k, lab in (("gross", "gross"), ("net_5bps", "net 5 bps"), ("net_10bps", "net 10 bps")):
        P(f"   share covered, {lab:<10} " + "  ".join(
            f"L_{g_} {int(np.sum(real[k] >= Lb[g_]))}/{len(rows)}" for g_ in Lb) + "  (no rule)")
    rp = [(i, r["rec"]["verdict"]["confidence"]) for i, r in enumerate(rows)
          if (r["rec"].get("verdict") or {}).get("confidence")]
    if rp:
        cov = sum(real["net_5bps"][i] >= c["L"]["0.90"] for i, c in rp)
        P(f"   replay tier L_0.90, net 5 bps: {cov}/{len(rp)} covered (no rule; on this "
          "panel the replay verdict is a specimen)")
    else:
        P("   replay tier: no run carries replay-tier confidence")

    # (3) H2
    P("(3) H2 — THE AGENTS' STATED EXPECTATIONS AGAINST REALIZED")
    mu = np.array([(r["run"].get("prediction") or {}).get("mean") for r in rows], dtype=object)
    sd = np.array([(r["run"].get("prediction") or {}).get("sd") for r in rows], dtype=object)
    has = np.array([m is not None for m in mu])
    muf = np.array([float(m) if m is not None else np.nan for m in mu])
    d = muf[has] - real["net_5bps"][has]
    db = (muf[has][:, None] - boot["net_5bps"][has]).mean(axis=0)
    lo = pct(db, 5)
    P(f"   mean(mu - realized net 5 bps) over {int(has.sum())} = {d.mean():+.4f}; one-sided "
      f"95% lower end {lo:+.4f} -> {'FAILS HIGH: the stated expectations overstate on this holdout' if lo > 0 else 'holds: not shown to overstate on this holdout'}")
    for a in sorted(set(arm)):
        sel = has & (arm == a)
        if sel.any():
            P(f"      {a:<20} n {int(sel.sum()):2d}  mean d {np.mean(muf[sel] - real['net_5bps'][sel]):+.4f}")
    ys = real["net_5bps"]
    c_ag = [crps_normal(muf[i], float(sd[i]) if sd[i] is not None else 0.0, ys[i])
            for i in range(len(rows)) if has[i]]
    c_cl = [crps_curve(cp[i]["confidence"]["curve"], ys[i]) for i in range(len(rows)) if has[i]]
    c_sd = [crps_sample(lo_hi[i][2], ys[i]) for i in range(len(rows)) if has[i]]
    P(f"   CRPS, mean over {len(c_ag)} (lower is better): agent normal(mu, sd) "
      f"{np.mean(c_ag):.4f}; class-tier confidence curve {np.mean(c_cl):.4f}; sr_deflated "
      f"predictive {np.mean(c_sd):.4f}")
    P("   per run: name | arm | mu | L_0.90 | S - mean(M_b) | realized net 5 bps")
    for i, r in enumerate(rows):
        m_ = f"{muf[i]:+.3f}" if has[i] else "   n/a"
        point = cp[i]["submitted_score"] - float(np.mean(cp[i]["null_max_draws"]))
        P(f"      {names[i]} | {arm[i]} | {m_} | {Lb['0.90'][i]:+.3f} | {point:+.3f} | "
          f"{ys[i]:+.3f}")

    # (4) descriptive
    P("(4) DESCRIPTIVE")
    C0 = np.array([c["confidence"]["C0"] for c in cp])
    PH = np.array([c["confidence"]["P_H"] for c in cp])
    pos = (ys > 0).astype(float)
    P(f"   stored C0 mean {C0.mean():.3f}; stored P_5 mean {PH.mean():.3f} against realized "
      f"> 0 on {int(pos.sum())}/{len(pos)}, Brier {np.mean((PH - pos) ** 2):.4f} (P_5 is shown "
      "beside certified verdicts only; none here is certified; read as the stored field)")
    for a in sorted(set(arm)):
        sel = arm == a
        P(f"   {a:<20} median gross {np.median(real['gross'][sel]):+.3f}  net 5 "
          f"{np.median(real['net_5bps'][sel]):+.3f}  net 10 {np.median(real['net_10bps'][sel]):+.3f}")
    ties = _rank_feature_runs(rows)
    P("   tie note (ret1_rank or drawdown_rank, whose exact ties break differently on x86): "
      + (", ".join(ties) if ties else "none"))
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grades", required=True)
    ap.add_argument("--repriced", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    g, rows = load(a.grades, a.repriced, a.runs)
    text = read(g, rows)
    print(text)
    if a.out:
        Path(a.out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
