"""The reader for the agent cell on the ETF recent panel (`prereg/agent-cell-etf-recent.md`,
sections 8-10). Reads `priced.json` (in-sample pricing from committed logs) and `grades.json`
(the host grading) **once**, and writes `read.txt` and `decision.json` to `--out`.

Every interval for R1, R2 and R4 comes from the grader's one stationary bootstrap over holdout
days, applied jointly to every submission (the replicate matrices in grades.json); sessions are
held fixed. R3 is in-sample: its arm-B-against-arm-A interval resamples sessions within arm
(seed 723001). The gate's predictive distribution for the CRPS is F_b = S - M_b + SE_oos * Z_b
with Z_b from default_rng(723002) and SE_oos = sqrt((1 + S^2 / (2 * 252)) / years_oos).

**The primary statistic is the UNWEIGHTED net Sharpe** (registration section 0): R1 against the
unweighted L90, R2's errors and CRPS on the unweighted statistic and nulls. Every W2-weighted
counterpart is printed beside, labelled "recency-weighted, descriptive".

    python -m experiments.read_agent_cell_etf_recent --priced runs/agent_cell_etf_recent/priced.json \\
        --grades runs/etf_recent_grade/<date>/grades.json --out runs/agent_cell_etf_recent/read
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import norm

R1_FLOOR = 0.90                  # registration section 8, R1 (the author, 2026-10-11)
W2 = "recency-weighted, descriptive"
B_SESSIONS = 10_000
SEED_SESSIONS = 723001
SEED_Z = 723002
LIMITS = ["limits: one window (444 rows, one market period); one agent model; the ETFs were chosen in 2026 from "
          "survivors; costs are assumed (5 bps one-way, 50 bps a year borrow); 2025 was inside a window opened once "
          "for other strategies; the second grading is in 2028; the agent model may know these ETFs' history; a rule "
          "search and a look at the model stream are not one declared search."]


def unb64(s: str, shape) -> np.ndarray:
    import base64
    return np.frombuffer(base64.b64decode(s), dtype=np.float32).reshape(shape).astype(float)


def q90(a) -> list[float]:
    return [float(v) for v in np.quantile(np.asarray(a, float), [0.05, 0.95])]


def verdict_interval(lo: float, hi: float, yes: str, no: str) -> str:
    if hi < 0:
        return yes
    if lo > 0:
        return no
    return "not distinguished (the 90% interval covers 0)"


# -- CRPS ---------------------------------------------------------------------------------

def crps_normal(mu, sd, y):
    y = np.asarray(y, float)
    if not sd or sd <= 0:
        return np.abs(mu - y)
    z = (y - mu) / sd
    return sd * (z * (2 * norm.cdf(z) - 1) + 2 * norm.pdf(z) - 1 / np.sqrt(np.pi))


class SampleCRPS:
    """CRPS of a sample distribution at many outcomes, by sorted prefix sums."""
    def __init__(self, s):
        self.s = np.sort(np.asarray(s, float))
        n = self.s.size
        self.n, self.pref = n, np.concatenate([[0.0], np.cumsum(self.s)])
        self.half_e2 = float(np.sum((2 * np.arange(1, n + 1) - n - 1) * self.s) / (n * n))

    def __call__(self, y):
        y = np.asarray(y, float)
        k = np.searchsorted(self.s, y)
        tot = self.pref[-1]
        e1 = (y * k - self.pref[k] + (tot - self.pref[k]) - y * (self.n - k)) / self.n
        return e1 - self.half_e2


def se_oos(S: float, years: float) -> float:
    return float(np.sqrt((1 + S * S / (2 * 252)) / years))


# -- the read -------------------------------------------------------------------------------

def read(priced: dict, grades: dict) -> tuple[str, dict]:
    items = {it["id"]: (j, it) for j, it in enumerate(grades["items"])}
    shape = grades["bootstrap"]["shape"]
    RS = unb64(grades["bootstrap"]["sharpe_b64"], shape)
    RR = unb64(grades["bootstrap"]["net_return_b64"], shape)
    subs = []
    for r in priced["priced"]:
        if r["session"] not in items:
            raise SystemExit(f"REFUSED: session {r['session']} is priced but not graded")
        j, it = items[r["session"]]
        subs.append({**r, "col": j, "realized": it["realized"], "net_return": it["net_return"]})
    n = len(subs)
    years = grades["n_periods"] / 252.0
    arms = {a: [s for s in subs if s["arm"] == a] for a in ("A", "B")}
    nul = {k: np.asarray(v, float) for k, v in priced["nulls"].items()}
    L, dec = [], {}
    L += [f"AGENT CELL ON THE ETF RECENT PANEL: READ ONCE ({grades['label']}); holdout {grades['first_holdout_date']} .. "
          f"{grades['last_date']}, {grades['n_periods']} rows; joint bootstrap B {shape[0]}, block length "
          f"{grades['block_length']}, seed {grades['seed']}",
          "=" * 100,
          f"sessions {priced['n_sessions']}: {n} submissions ({sum(s['kind'] == 'rule' for s in subs)} rules, "
          f"{sum(s['kind'] == 'baseline_model' for s in subs)} model stream), {len(priced['no_submit'])} no_submit; "
          f"arm A {len(arms['A'])}, arm B {len(arms['B'])}", *LIMITS, ""]

    # R1 -- lower bounds
    L.append("R1 lower bounds: the share of submissions with realised >= the unweighted L90 (primary)")
    dec["R1"] = {}
    for tag, grp in (("all", subs), ("arm A", arms["A"]), ("arm B", arms["B"])):
        if not grp:
            continue
        cols = [s["col"] for s in grp]
        l90 = np.array([s["L90"] for s in grp])
        held = np.array([s["realized"] >= s["L90"] for s in grp])
        share_b = (RS[:, cols] >= l90[None, :]).mean(axis=1)
        up95 = float(np.quantile(share_b, 0.95))
        too_high = up95 < R1_FLOOR
        L.append(f"   {tag}: {int(held.sum())} of {len(grp)} ({held.mean():.2f}); one-sided 95% upper end {up95:.2f} "
                 f"(joint bootstrap) -> " + (f"the bounds are TOO HIGH: the share is below the floor {R1_FLOOR:.2f}"
                                              if too_high else
                                              f"consistent with a 90% bound: the share is not below the floor {R1_FLOOR:.2f}"))
        dec["R1"][tag] = {"count": int(held.sum()), "n": len(grp), "share": float(held.mean()), "upper95": up95,
                          "too_high": bool(too_high)}
        held_w = np.array([s["realized"] >= s["L90_w2"] for s in grp])
        L.append(f"      beside ({W2}): at or above the W2 L90 {int(held_w.sum())} of {len(grp)} ({held_w.mean():.2f})")
        dec["R1"][tag]["w2_beside"] = {"count": int(held_w.sum()), "label": W2}

    # R2 -- closeness
    L.append("")
    L.append("R2 closeness: error = realised - predictor; mean signed error and MAE, 90% joint-bootstrap intervals")
    preds = {"raw unweighted (S)": lambda s: s["S"], f"raw weighted (S_w; {W2})": lambda s: s["S_w"],
             "agent's stated mean": lambda s: s["predict"]["mean"],
             "gate point estimate EB (rules)": lambda s: (s["EB"] or {}).get("value")}
    dec["R2"] = {}
    mae_b = {}
    for name, f in preds.items():
        grp = [s for s in subs if f(s) is not None]
        if not grp:
            continue
        cols = [s["col"] for s in grp]
        pv = np.array([f(s) for s in grp], float)
        real = np.array([s["realized"] for s in grp])
        e = real - pv
        eb = RS[:, cols] - pv[None, :]
        mae_b[name] = (cols, np.abs(eb).mean(axis=1), pv)
        L.append(f"   {name} (n {len(grp)}): mean signed error {e.mean():+.3f} {q90(eb.mean(axis=1))}; "
                 f"MAE {np.abs(e).mean():.3f} {q90(np.abs(eb).mean(axis=1))}")
        dec["R2"][name] = {"n": len(grp), "mse": float(e.mean()), "mae": float(np.abs(e).mean())}

    def cmp(a: str, b: str):
        ca, _, pa = mae_b[a]
        cb, _, pb = mae_b[b]
        common = sorted(set(ca) & set(cb))
        ia = [ca.index(c) for c in common]
        ib = [cb.index(c) for c in common]
        d_b = (np.abs(RS[:, common] - pa[ia][None, :]).mean(axis=1) - np.abs(RS[:, common] - pb[ib][None, :]).mean(axis=1))
        lo, hi = q90(d_b)
        v = verdict_interval(lo, hi, f"{a} is CLOSER than {b}", f"{a} is NOT closer than {b}")
        L.append(f"   MAE({a}) - MAE({b}) on {len(common)} common: 90% interval [{lo:+.3f}, {hi:+.3f}] -> {v}")
        dec["R2"][f"{a} vs {b}"] = {"interval": [lo, hi], "verdict": v}

    for a in ("gate point estimate EB (rules)", "agent's stated mean"):
        for b in ("raw unweighted (S)", f"raw weighted (S_w; {W2})"):
            if a in mae_b and b in mae_b:
                cmp(a, b)

    # CRPS: the agent's Normal(mean, sd) against the gate's predictive distribution
    z = np.random.default_rng(SEED_Z).standard_normal(len(nul["class_unw_max"]))
    for version in ("unweighted (primary)", f"weighted ({W2})"):
        rows = []
        for s in subs:
            if version.startswith("unweighted"):
                S, M = s["S"], (nul["class_unw_max"] if s["kind"] == "rule" else nul["model_unw"])
            else:
                S, M = s["S_w"], (nul["class_w2_max"] if s["kind"] == "rule" else nul["model_w2"])
            zz = z[:len(M)] if len(M) <= len(z) else np.random.default_rng(SEED_Z).standard_normal(len(M))
            gate = SampleCRPS(S - M + se_oos(S, years) * zz)
            mu, sd = s["predict"]["mean"], s["predict"]["sd"]
            y = RS[:, s["col"]]
            rows.append((crps_normal(mu, sd, s["realized"]), gate(s["realized"]),
                         crps_normal(mu, sd, y), gate(y)))
        if not rows:
            continue
        ag = np.mean([r[0] for r in rows])
        gt = np.mean([r[1] for r in rows])
        d_b = np.mean([r[2] - r[3] for r in rows], axis=0)
        lo, hi = q90(d_b)
        v = verdict_interval(lo, hi, "the agent's distribution scores BETTER than the gate's",
                             "the gate's distribution scores better than the agent's")
        L.append(f"   CRPS {version} (n {len(rows)}): agent {ag:.3f}, gate {gt:.3f}; agent - gate 90% [{lo:+.3f}, {hi:+.3f}] -> {v}")
        dec["R2"][f"CRPS {version}"] = {"agent": float(ag), "gate": float(gt), "interval": [lo, hi], "verdict": v}

    # R3 -- in-sample only
    L.append("")
    L.append("R3 in-sample only (no holdout value): stated mean and sd against search length, by arm; B against A")
    dec["R3"] = {}
    for arm, grp in arms.items():
        if len(grp) < 2:
            continue
        mv = np.array([s["search"]["moves"] for s in grp], float)
        for k in ("mean", "sd"):
            y = np.array([s["predict"][k] for s in grp], float)
            slope = float(np.polyfit(mv, y, 1)[0]) if mv.std() > 0 else float("nan")
            r = float(np.corrcoef(mv, y)[0, 1]) if mv.std() > 0 and y.std() > 0 else float("nan")
            L.append(f"   arm {arm}: stated {k} on moves: slope {slope:+.4f} per move, correlation {r:+.2f} (n {len(grp)})")
            dec["R3"][f"{arm}_{k}"] = {"slope": slope, "corr": r}
    if arms["A"] and arms["B"]:
        rng = np.random.default_rng(SEED_SESSIONS)
        for k in ("mean", "sd"):
            a = np.array([s["predict"][k] for s in arms["A"]], float)
            b = np.array([s["predict"][k] for s in arms["B"]], float)
            diff = float(b.mean() - a.mean())
            reps = np.array([rng.choice(b, b.size).mean() - rng.choice(a, a.size).mean() for _ in range(B_SESSIONS)])
            lo, hi = q90(reps)
            v = verdict_interval(lo, hi, f"arm B's stated {k} is LOWER than arm A's",
                                 f"arm B's stated {k} is HIGHER than arm A's")
            L.append(f"   B - A, stated {k}: {diff:+.3f}, 90% [{lo:+.3f}, {hi:+.3f}] -> {v}")
            dec["R3"][f"B_minus_A_{k}"] = {"diff": diff, "interval": [lo, hi], "verdict": v}

    # R4 -- money
    L.append("")
    L.append("R4 money")
    cols = [s["col"] for s in subs]
    pos = np.array([s["net_return"] > 0 for s in subs])
    share_b = (RR[:, cols] > 0).mean(axis=1) if cols else np.array([np.nan])
    L.append(f"   positive holdout net return: {int(pos.sum())} of {n} ({pos.mean() if n else float('nan'):.2f}), "
             f"90% {q90(share_b)}")
    dec["R4"] = {"positive": int(pos.sum()), "n": n}
    for bid in ("book_all", "book_A", "book_B"):
        if bid in items:
            it = items[bid][1]
            L.append(f"   {bid}: holdout net Sharpe {it['realized']:+.3f}, 90% [{it['ci90'][0]:+.3f}, {it['ci90'][1]:+.3f}]")
            dec["R4"][bid] = {"realized": it["realized"], "ci90": it["ci90"]}
    return "\n".join(L), dec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--priced", required=True)
    ap.add_argument("--grades", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "read.txt").exists():
        raise SystemExit("read.txt exists; the cell is read once")
    text, dec = read(json.loads(Path(a.priced).read_text()), json.loads(Path(a.grades).read_text()))
    out.mkdir(parents=True, exist_ok=True)
    (out / "read.txt").write_text(text + "\n")
    (out / "decision.json").write_text(json.dumps(dec, indent=1))
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
