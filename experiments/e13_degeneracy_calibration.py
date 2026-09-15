"""Calibrating the gate's degeneracy check, with the selection rule fixed before running.

SCOPE.md §11: re-estimating Sharpe in every replicate lets rarely-trading
rules dominate the null maximum. The gate will refuse (status DEGENERATE)
when that happens. This script measures what the check uses on populations
where the right answer is known, and picks the thresholds by a rule written
here before any of it ran.

The check
  An entry (column n, replicate b) is flagged when its resample contains
  fewer than s_min distinct periods with a non-zero return for that column
  (support: the structural property, invariant to position size), or when
  its resampled standard deviation is below q_min times its full-sample
  standard deviation (q: the numerical guard). Only each replicate's argmax
  entry counts (influence conditioning). A transcript is refused when
    (a) the share of replicates whose argmax is flagged exceeds tau, or
    (b) recomputing the verdict with flagged entries excluded from the null
        maximum changes it.
  Every per-replicate Sharpe is floored (variance <= 1e-10 x full-sample
  variance gives 0) and capped at |100| annualized, with counters.

Populations
  Dense, where any refusal is a false refusal (3,000 verdicts):
    D1  362-rule MA-crossover grid, no band filters, 10y random walk, 1,000 seeds
    D2  32-rule MA grid, 10y, one rule with true Sharpe 1.5, 500 seeds
    D3  linear-DGP GridSearch transcripts, N=100, target Sharpe 0.5/1/2, 1,000 draws
    D4  D1's menu on Student-t(3) returns at the same volatility, 500 seeds
  Containing sparse rules, where detection is measured:
    S1  368-rule MA grid with band filters, 10y random walk, 200 seeds
    S2  1,000 rules thinned from the 17,650-rule band-filter grid, 4y, 200 seeds
    S3  10,000 rules thinned from the same grid, 4y, 20 seeds

Ground truth for "degeneracy decided the verdict": the verdict changes when
each replicate's Sharpe divides by the column's full-sample standard
deviation instead of its resampled one (Hansen 2005's fixed studentization,
which cannot collapse). Sparse-population transcripts whose two verdicts
differ are the detection target; those whose verdicts agree are not.

Candidates: s_min in {0, 3, 5, 10, 20, 50}, q_min in {0, 0.1, 0.25, 0.5},
tau in {0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25}.

Selection rule, fixed before running
  1. Feasible: zero refusals across all 3,000 dense verdicts (rule of three:
     a 95% upper bound of 0.1% on the false-refusal rate).
  2. Among feasible candidates, maximize the refusal rate on the detection
     target. Ties: fewest refusals among sparse transcripts whose verdicts
     agree, then larger tau, smaller s_min, smaller q_min.
  3. No gap between populations is required. If the distributions overlap,
     rule 2 still returns the most sensitive candidate with no dense false
     refusals, and its detection rate is reported as it comes out, however
     low. (s_min=0, q_min=0 never flags, so the feasible set is never empty;
     if it is the choice, the check detects nothing and that is the result.)

Also reported: argmax support and q stratified by the argmax column's
full-sample trading frequency, dense and sparse separately, to show whether
the thresholds separate degenerate resamples or merely rare-trading rules;
and floor/cap counters per population.

Resampling uses estimator.bootstrap.stationary_bootstrap_index_matrix, a
vectorized sampler with the same distribution as the per-replicate one. The
switch was made after a first run was stopped for speed, before any of its
results were written or read; the design and selection rule above are
unchanged.

Usage: python -m experiments.e13_degeneracy_calibration
"""
from __future__ import annotations

import itertools
import pickle
import time

import numpy as np

from environments.dgp import DGPConfig, calibrate_sigma, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length, sharpe, stationary_bootstrap_index_matrix
from garden.examples import DAILY_VOL, WARMUP, _menu, _rule_returns, _simulate
from garden.power import bootstrap_p_value, bootstrap_power, critical_value
from searchers.scripted import GridSearch

ANN = np.sqrt(252)
B, CHUNK, ALPHA, REFERENCE, POWER_FLOOR = 1000, 64, 0.05, 1.0, 0.20
SHARPE_CAP, VARIANCE_FLOOR = 100.0, 1e-10
S_MIN = (0, 3, 5, 10, 20, 50)
Q_MIN = (0.0, 0.1, 0.25, 0.5)
TAU = (0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25)
CANDIDATES = list(itertools.product(S_MIN, Q_MIN))
ACTIVITY_BINS = (0.0, 0.01, 0.05, 0.20, 0.50, 1.0001)
BAND_MENU_SEED = 20_000
SAMPLE_REPLICATES = 200


def verdict(null: np.ndarray, draws: np.ndarray, sr: float) -> str:
    if bootstrap_p_value(null, sr) < ALPHA:
        return "PASS"
    return "INADMISSIBLE" if bootstrap_power(draws, REFERENCE, critical_value(null, ALPHA)) < POWER_FLOOR else "FAIL"


def diagnose(R: np.ndarray, j: int, seed: int) -> dict:
    T, N = R.shape
    Rd = R - R.mean(axis=0)
    R2 = Rd * Rd
    var_full = Rd.var(axis=0, ddof=1)
    sd_full = np.sqrt(var_full)
    safe_sd = np.where(sd_full > 0, sd_full, 1.0)
    nz = (R != 0).astype(float)
    activity = nz.mean(axis=0)
    sr_sel = float(sharpe(R[:, [j]], annualization=ANN)[0])
    L = select_block_length(Rd)
    rng = np.random.default_rng(seed)

    M, M_fixed, tracked, tracked_fixed = (np.empty(B) for _ in range(4))
    arg_support, arg_q, arg_activity = np.empty(B), np.empty(B), np.empty(B)
    flagged_arg = {c: np.empty(B, dtype=bool) for c in CANDIDATES}
    M_excl = {c: np.empty(B) for c in CANDIDATES}
    floor_binds = cap_binds = 0
    offsets = T * np.arange(CHUNK)
    for start in range(0, B, CHUNK):
        c = min(CHUNK, B - start)
        cols, sl = np.arange(c), slice(start, start + c)
        idx = stationary_bootstrap_index_matrix(T, L, c, rng)
        counts = np.bincount((idx + offsets[:c, None]).ravel(), minlength=T * c).reshape(c, T).T
        W = counts / T
        m1, m2 = Rd.T @ W, R2.T @ W
        var = np.maximum((m2 - m1 * m1) * (T / (T - 1)), 0.0)
        live = var > VARIANCE_FLOOR * var_full[:, None]
        floor_binds += int(np.sum(~live & (var > 0)))
        sr = np.where(live, m1 / np.sqrt(np.where(live, var, 1.0)), 0.0) * ANN
        cap_binds += int(np.sum(np.abs(sr) > SHARPE_CAP))
        sr = np.clip(sr, -SHARPE_CAP, SHARPE_CAP)
        sr_fixed = np.where(sd_full[:, None] > 0, m1 / safe_sd[:, None], 0.0) * ANN
        support = nz.T @ (counts > 0).astype(float)
        q = np.sqrt(var) / safe_sd[:, None]

        a = sr.argmax(axis=0)
        M[sl], tracked[sl] = sr[a, cols], sr[j]
        M_fixed[sl], tracked_fixed[sl] = sr_fixed.max(axis=0), sr_fixed[j]
        arg_support[sl], arg_q[sl], arg_activity[sl] = support[a, cols], q[a, cols], activity[a]
        for s_min, q_min in CANDIDATES:
            flag = (support < s_min) | (q < q_min)
            flagged_arg[(s_min, q_min)][sl] = flag[a, cols]
            M_excl[(s_min, q_min)][sl] = np.where(flag, -np.inf, sr).max(axis=0)

    base = verdict(M, tracked, sr_sel)
    return {
        "N": N, "T": T, "base": base, "fixed": verdict(M_fixed, tracked_fixed, sr_sel),
        "critical": critical_value(M, ALPHA), "critical_fixed": critical_value(M_fixed, ALPHA),
        "floor_binds": floor_binds, "cap_binds": cap_binds, "submitted_activity": float(activity[j]),
        "candidates": {
            cand: {"share": float(flagged_arg[cand].mean()),
                   "flip": verdict(M_excl[cand], tracked, sr_sel) != base}
            for cand in CANDIDATES
        },
        "arg_support": arg_support[:SAMPLE_REPLICATES], "arg_q": arg_q[:SAMPLE_REPLICATES],
        "arg_activity": arg_activity[:SAMPLE_REPLICATES],
    }


# -- transcript builders -----------------------------------------------------

def _argmax_transcript(R: np.ndarray) -> tuple[np.ndarray, int]:
    return R, int(np.argmax(sharpe(R, axis=0)))


def dense_ma(name: str, seed: int, t_df: int | None = None):
    n_periods, rules, true_rule, true_sharpe = _menu(name)
    rng = np.random.default_rng(seed)
    if t_df is None:
        r = _simulate(n_periods + WARMUP, rng, true_rule, true_sharpe)
    else:
        r = rng.standard_t(t_df, n_periods + WARMUP) / np.sqrt(t_df / (t_df - 2)) * DAILY_VOL
    return _argmax_transcript(_rule_returns(r, rules))


def band_grid(fasts, slows, bands):
    return [(f, s, b, lo) for f in fasts for s in slows if f < s for b in bands for lo in (False, True)]


S1_RULES = band_grid((1, 2, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50), (10, 20, 30, 50, 75, 100, 125, 150, 200),
                     (0.0, 0.01))
BAND_FULL = band_grid(range(1, 51), range(5, 201, 5), (0.0, 0.0025, 0.005, 0.01, 0.02))


def thinned_band_menu(n: int):
    keep = np.random.default_rng(BAND_MENU_SEED).choice(len(BAND_FULL), n, replace=False)
    return [BAND_FULL[i] for i in np.sort(keep)]


def band_rule_returns(r: np.ndarray, rules) -> np.ndarray:
    n = len(r)
    cum = np.concatenate([[0.0], np.cumsum(np.cumsum(r))])
    ma = {}
    for w in {w for f, s, _, _ in rules for w in (f, s)}:
        m = np.full(n, np.nan)
        m[w - 1:] = (cum[w:] - cum[:-w]) / w
        ma[w] = m
    out = np.empty((n - WARMUP, len(rules)))
    for i, (fast, slow, band, long_only) in enumerate(rules):
        gap = ma[fast][WARMUP - 1:-1] - ma[slow][WARMUP - 1:-1]
        pos = np.where(gap > band, 1.0, np.where(gap < -band, -1.0, 0.0))
        if long_only:
            pos = np.maximum(pos, 0.0)
        out[:, i] = pos * r[WARMUP:]
    return out


def sparse_band(rules, n_periods: int, seed: int):
    r = np.random.default_rng(seed).normal(0.0, DAILY_VOL, n_periods + WARMUP)
    return _argmax_transcript(band_rule_returns(r, rules))


def gridsearch(seed: int):
    target = (0.5, 1.0, 2.0)[seed % 3]
    template = DGPConfig(M=60, T=600, T_oos=300, K=40, s=3, rho=0.0, sigma=1.0, seed=seed, heterogeneous=True)
    config = DGPConfig(M=60, T=600, T_oos=300, K=40, s=3, rho=0.0, sigma=calibrate_sigma(target, template),
                       seed=seed, heterogeneous=True)
    sandbox = Sandbox(generate(config), periods_per_year=config.periods_per_year)
    GridSearch(subset_sizes=(1, 2, 3), max_trials=100, seed=seed).run(sandbox)
    spec, _ = sandbox.submission
    j = next(e.call_index for e in sandbox.transcript if np.array_equal(e.spec.weights, spec.weights))
    return sandbox.returns_matrix(), j


S2_RULES, S3_RULES = thinned_band_menu(1_000), thinned_band_menu(10_000)
POPULATIONS = [
    ("D1", "dense", 1000, lambda s: dense_ma("null_grid", s)),
    ("D2", "dense", 500, lambda s: dense_ma("real_edge", s)),
    ("D3", "dense", 1000, gridsearch),
    ("D4", "dense", 500, lambda s: dense_ma("null_grid", s, t_df=3)),
    ("S1", "sparse", 200, lambda s: sparse_band(S1_RULES, 2520, s)),
    ("S2", "sparse", 200, lambda s: sparse_band(S2_RULES, 1000, s)),
    ("S3", "sparse", 20, lambda s: sparse_band(S3_RULES, 1000, s)),
]


def run(verbose: bool = True) -> dict:
    results, t0 = {}, time.time()
    for k, (name, kind, count, builder) in enumerate(POPULATIONS):
        records = []
        for i in range(count):
            seed = 5_000_000 + 100_000 * k + i
            R, j = builder(seed)
            records.append(diagnose(R, j, seed))
        results[name] = {"kind": kind, "records": records}
        if verbose:
            print(f"  {name} ({kind}): {count} transcripts ({time.time() - t0:.0f}s)")
    return results


# -- selection and report ----------------------------------------------------

def refused(rec: dict, cand, tau: float) -> bool:
    c = rec["candidates"][cand]
    return c["share"] > tau or c["flip"]


def select(results: dict) -> tuple[dict, list[dict]]:
    dense = [r for p in results.values() if p["kind"] == "dense" for r in p["records"]]
    sparse = [r for p in results.values() if p["kind"] == "sparse" for r in p["records"]]
    target = [r for r in sparse if r["base"] != r["fixed"]]
    agree = [r for r in sparse if r["base"] == r["fixed"]]
    rows = []
    for (s_min, q_min), tau in itertools.product(CANDIDATES, TAU):
        cand = (s_min, q_min)
        detected = sum(refused(r, cand, tau) for r in target)
        rows.append({
            "s_min": s_min, "q_min": q_min, "tau": tau,
            "dense_refusals": sum(refused(r, cand, tau) for r in dense), "n_dense": len(dense),
            "detected": detected, "n_target": len(target),
            "detection_rate": detected / len(target) if target else 0.0,
            "agree_refusals": sum(refused(r, cand, tau) for r in agree), "n_agree": len(agree),
        })
    feasible = [r for r in rows if r["dense_refusals"] == 0]
    chosen = min(feasible, key=lambda r: (-r["detection_rate"], r["agree_refusals"], -r["tau"], r["s_min"], r["q_min"]))
    return chosen, rows


def report(results: dict) -> dict:
    print(f"\nB={B}, alpha={ALPHA}, reference Sharpe {REFERENCE}, power floor {POWER_FLOOR}\n")
    print(f"{'pop':>4} {'n':>5} {'PASS':>5} {'FAIL':>5} {'INADM':>5} {'disagree w/ fixed':>17} "
          f"{'critical range':>16} {'floor binds':>11} {'cap binds':>9} {'min submitted activity':>22}")
    for name, p in results.items():
        recs = p["records"]
        status = [r["base"] for r in recs]
        crit = np.array([r["critical"] for r in recs])
        print(f"{name:>4} {len(recs):>5} {status.count('PASS'):>5} {status.count('FAIL'):>5} "
              f"{status.count('INADMISSIBLE'):>5} {np.mean([r['base'] != r['fixed'] for r in recs]):>17.3f} "
              f"{crit.min():>7.2f}-{crit.max():<8.2f} {sum(r['floor_binds'] for r in recs):>11} "
              f"{sum(r['cap_binds'] for r in recs):>9} {min(r['submitted_activity'] for r in recs):>22.3f}")

    print("\nArgmax entries by the argmax column's trading frequency (first "
          f"{SAMPLE_REPLICATES} replicates per transcript)")
    print(f"{'kind':>6} {'activity':>12} {'entries':>8} {'support p1':>10} {'support p50':>11} {'q p1':>6} {'q p50':>6}")
    for kind in ("dense", "sparse"):
        recs = [r for p in results.values() if p["kind"] == kind for r in p["records"]]
        act = np.concatenate([r["arg_activity"] for r in recs])
        sup = np.concatenate([r["arg_support"] for r in recs])
        q = np.concatenate([r["arg_q"] for r in recs])
        for lo, hi in zip(ACTIVITY_BINS, ACTIVITY_BINS[1:]):
            m = (act >= lo) & (act < hi)
            if m.any():
                print(f"{kind:>6} {lo:>5.0%}-{min(hi, 1):<5.0%} {m.sum():>8} {np.percentile(sup[m], 1):>10.0f} "
                      f"{np.percentile(sup[m], 50):>11.0f} {np.percentile(q[m], 1):>6.2f} {np.percentile(q[m], 50):>6.2f}")

    chosen, rows = select(results)
    print("\nMost sensitive candidates with zero dense refusals:")
    feasible = sorted((r for r in rows if r["dense_refusals"] == 0),
                      key=lambda r: (-r["detection_rate"], r["agree_refusals"], -r["tau"], r["s_min"], r["q_min"]))
    print(f"{'s_min':>5} {'q_min':>5} {'tau':>6} {'detected':>12} {'agree refused':>14}")
    for r in feasible[:10]:
        print(f"{r['s_min']:>5} {r['q_min']:>5} {r['tau']:>6} {r['detected']:>5}/{r['n_target']:<6} "
              f"{r['agree_refusals']:>6}/{r['n_agree']:<7}")
    ub = 3 / chosen["n_dense"]
    print(f"\nCHOSEN by the pre-registered rule: s_min={chosen['s_min']}, q_min={chosen['q_min']}, tau={chosen['tau']}")
    print(f"  dense false refusals: 0/{chosen['n_dense']} (95% upper bound {ub:.2%})")
    print(f"  detection on sparse transcripts whose verdict flips under fixed studentization: "
          f"{chosen['detected']}/{chosen['n_target']} ({chosen['detection_rate']:.1%})")
    print(f"  refusals on sparse transcripts whose verdicts agree: {chosen['agree_refusals']}/{chosen['n_agree']}")
    return {"chosen": chosen, "rows": rows}


if __name__ == "__main__":
    results = run()
    selection = report(results)
    with open("figures/e13_degeneracy_calibration_data.pkl", "wb") as f:
        pickle.dump({"results": results, "selection": selection}, f)
