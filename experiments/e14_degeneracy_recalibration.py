"""Recalibrating the gate's degeneracy check against a better definition of a broken bar.

e13 chose support_min=5, tau=0.001 by its pre-registered rule, but its ground
truth ("the verdict changes under fixed studentization") was too narrow. Only
23 transcripts met it, every sensitive candidate caught all 23, and the
tiebreak then chose among candidates that also refused sparse transcripts
whose critical values were sound (368-rule band grid: median inflation 1.01x
the fixed-studentization value). This run fixes the definition, uses fresh
seeds so the new definition is not fitted to e13's data, and enlarges the
populations so the detection target is not 23 cases.

Changes from e13, all fixed before running
  Ground truth. A sparse transcript's bar is BROKEN if (a) its verdict differs
    under fixed studentization, or (b) its critical value divided by the
    fixed-studentization critical value falls outside the central 99% of that
    ratio across this run's dense transcripts. Otherwise it is SOUND.
  Trigger family. Besides the share of all replicates whose argmax entry is
    degenerate ("all"), candidates include that share among the top 10% of
    replicates by null maximum ("top10"), the region that sets the critical
    value at alpha=0.05. The verdict-flip escalation is unchanged.
  Candidates. s_min in {3, 5, 10, 20, 50}; q_min in {0, 0.25};
    share in {all, top10}; tau in {0.001, 0.002, 0.005, 0.01, 0.02, 0.05,
    0.1, 0.25, 0.5}.
  Populations, fresh seeds: D1 3,000, D2 1,500, D3 3,000, D4 1,500 (9,000
    dense); S1 1,000, S2 1,000, S3 200 (same constructions as e13).

Selection rule
  1. Feasible: zero refusals across all 9,000 dense verdicts (95% upper bound
     on the dense false-refusal rate 3/9,000 = 0.033%).
  2. Among feasible candidates that refuse at most 10% of SOUND sparse
     transcripts, maximize the refusal rate on BROKEN ones. Ties: fewer sound
     refusals, then larger tau, "all" before "top10", smaller s_min, smaller
     q_min.
  3. If no such candidate refuses any broken transcript, choose the feasible
     candidate maximizing (broken refusal rate - sound refusal rate), same
     ties. If that maximum is not positive, the check ships switched off: the
     share is still printed, and the gate never refuses on it.

Reported: dense band, broken/sound counts per population, the feasible
frontier, the chosen candidate with Wilson intervals, and its refusals by
population.

Usage: python -m experiments.e14_degeneracy_recalibration [--workers N] [--smoke]
"""
from __future__ import annotations

import argparse
import itertools
import os
import pickle
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from estimator.bootstrap import select_block_length, sharpe, stationary_bootstrap_index_matrix
from estimator.metrics import wilson_ci
from experiments import e13_degeneracy_calibration as e13
from garden.power import critical_value

B, CHUNK, ALPHA = 1000, 64, 0.05
SHARPE_CAP, VARIANCE_FLOOR = 100.0, 1e-10
S_MIN = (3, 5, 10, 20, 50)
Q_MIN = (0.0, 0.25)
SHARE_KINDS = ("all", "top10")
TAU = (0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5)
TOP_FRACTION = 0.10
DENSE_BAND = (0.5, 99.5)
SOUND_REFUSAL_LIMIT = 0.10
SEED_BASE = 9_000_000
SAMPLE_REPLICATES = 50
CANDIDATES = list(itertools.product(S_MIN, Q_MIN))
OUTPUT = "figures/e14_degeneracy_recalibration_data.pkl"

POPULATIONS = {  # name: (kind, transcripts, worker cap for memory)
    "D1": ("dense", 3000, None),
    "D2": ("dense", 1500, None),
    "D3": ("dense", 3000, None),
    "D4": ("dense", 1500, None),
    "S1": ("sparse", 1000, None),
    "S2": ("sparse", 1000, None),
    "S3": ("sparse", 200, 12),
}


def build(name: str, seed: int):
    if name == "D1":
        return e13.dense_ma("null_grid", seed)
    if name == "D2":
        return e13.dense_ma("real_edge", seed)
    if name == "D3":
        return e13.gridsearch(seed)
    if name == "D4":
        return e13.dense_ma("null_grid", seed, t_df=3)
    if name == "S1":
        return e13.sparse_band(e13.S1_RULES, 2520, seed)
    if name == "S2":
        return e13.sparse_band(e13.S2_RULES, 1000, seed)
    return e13.sparse_band(e13.S3_RULES, 1000, seed)


def diagnose(name: str, seed: int) -> dict:
    R, j = build(name, seed)
    T, N = R.shape
    Rd = R - R.mean(axis=0)
    R2 = Rd * Rd
    var_full = Rd.var(axis=0, ddof=1)
    sd_full = np.sqrt(var_full)
    safe_sd = np.where(sd_full > 0, sd_full, 1.0)
    nz = (R != 0).astype(float)
    sr_sel = float(sharpe(R[:, [j]], annualization=e13.ANN)[0])
    L = select_block_length(Rd)
    rng = np.random.default_rng(seed)

    M, M_fixed, tracked, tracked_fixed = (np.empty(B) for _ in range(4))
    arg_support, arg_activity = np.empty(B), np.empty(B)
    flagged_arg = {c: np.empty(B, dtype=bool) for c in CANDIDATES}
    M_excl = {c: np.empty(B) for c in CANDIDATES}
    activity = nz.mean(axis=0)
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
        sr = np.where(live, m1 / np.sqrt(np.where(live, var, 1.0)), 0.0) * e13.ANN
        cap_binds += int(np.sum(np.abs(sr) > SHARPE_CAP))
        sr = np.clip(sr, -SHARPE_CAP, SHARPE_CAP)
        sr_fixed = np.where(sd_full[:, None] > 0, m1 / safe_sd[:, None], 0.0) * e13.ANN
        support = nz.T @ (counts > 0).astype(float)
        q = np.sqrt(var) / safe_sd[:, None]

        a = sr.argmax(axis=0)
        M[sl], tracked[sl] = sr[a, cols], sr[j]
        M_fixed[sl], tracked_fixed[sl] = sr_fixed.max(axis=0), sr_fixed[j]
        arg_support[sl], arg_activity[sl] = support[a, cols], activity[a]
        for s_min, q_min in CANDIDATES:
            flag = (support < s_min) | (q < q_min)
            flagged_arg[(s_min, q_min)][sl] = flag[a, cols]
            M_excl[(s_min, q_min)][sl] = np.where(flag, -np.inf, sr).max(axis=0)

    base = e13.verdict(M, tracked, sr_sel)
    top = M >= np.quantile(M, 1 - TOP_FRACTION)
    return {
        "population": name, "seed": seed, "N": N, "T": T, "base": base,
        "fixed": e13.verdict(M_fixed, tracked_fixed, sr_sel),
        "critical": critical_value(M, ALPHA), "critical_fixed": critical_value(M_fixed, ALPHA),
        "floor_binds": floor_binds, "cap_binds": cap_binds,
        "candidates": {
            cand: {"all": float(flagged_arg[cand].mean()), "top10": float(flagged_arg[cand][top].mean()),
                   "flip": e13.verdict(M_excl[cand], tracked, sr_sel) != base}
            for cand in CANDIDATES
        },
        "arg_support": arg_support[:SAMPLE_REPLICATES], "arg_activity": arg_activity[:SAMPLE_REPLICATES],
    }


def run(counts: dict[str, int], workers: int, verbose: bool = True) -> dict:
    results, t0 = {}, time.time()
    for k, (name, (kind, _, cap)) in enumerate(POPULATIONS.items()):
        seeds = [SEED_BASE + 100_000 * k + i for i in range(counts[name])]
        with ProcessPoolExecutor(max_workers=min(workers, cap or workers)) as pool:
            records = list(pool.map(diagnose, [name] * len(seeds), seeds, chunksize=4))
        results[name] = {"kind": kind, "records": records}
        if verbose:
            print(f"  {name} ({kind}): {len(records)} transcripts ({time.time() - t0:.0f}s)", flush=True)
    return results


def label_ground_truth(results: dict) -> tuple[float, float]:
    dense = [r for p in results.values() if p["kind"] == "dense" for r in p["records"]]
    lo, hi = np.percentile([r["critical"] / r["critical_fixed"] for r in dense], DENSE_BAND)
    for p in results.values():
        for r in p["records"]:
            ratio = r["critical"] / r["critical_fixed"]
            r["ratio"] = ratio
            r["broken"] = p["kind"] == "sparse" and (r["base"] != r["fixed"] or not lo <= ratio <= hi)
    return float(lo), float(hi)


def refused(r: dict, s_min: int, q_min: float, share: str, tau: float) -> bool:
    c = r["candidates"][(s_min, q_min)]
    return c[share] > tau or c["flip"]


def select(results: dict) -> tuple[dict | None, str, list[dict]]:
    dense = [r for p in results.values() if p["kind"] == "dense" for r in p["records"]]
    sparse = [r for p in results.values() if p["kind"] == "sparse" for r in p["records"]]
    broken = [r for r in sparse if r["broken"]]
    sound = [r for r in sparse if not r["broken"]]
    rows = []
    for (s_min, q_min), share, tau in itertools.product(CANDIDATES, SHARE_KINDS, TAU):
        args = (s_min, q_min, share, tau)
        b = sum(refused(r, *args) for r in broken)
        s = sum(refused(r, *args) for r in sound)
        rows.append({
            "s_min": s_min, "q_min": q_min, "share": share, "tau": tau,
            "dense_refusals": sum(refused(r, *args) for r in dense), "n_dense": len(dense),
            "broken_refusals": b, "n_broken": len(broken), "sound_refusals": s, "n_sound": len(sound),
            "tpr": b / len(broken) if broken else 0.0, "fpr": s / len(sound) if sound else 0.0,
        })
    feasible = [r for r in rows if r["dense_refusals"] == 0]

    def ties(r):
        return (r["sound_refusals"], -r["tau"], SHARE_KINDS.index(r["share"]), r["s_min"], r["q_min"])

    within = [r for r in feasible if r["fpr"] <= SOUND_REFUSAL_LIMIT]
    if within and max(r["tpr"] for r in within) > 0:
        best = max(r["tpr"] for r in within)
        return min((r for r in within if r["tpr"] == best), key=ties), "rule 2", rows
    j = max((r["tpr"] - r["fpr"] for r in feasible), default=0.0)
    if j <= 0:
        return None, "rule 3: no candidate separates broken from sound; check ships switched off", rows
    return min((r for r in feasible if r["tpr"] - r["fpr"] == j), key=ties), "rule 3", rows


def report(results: dict) -> dict:
    lo, hi = label_ground_truth(results)
    print(f"\nB={B}, alpha={ALPHA}; dense central 99% of critical / fixed-studentization critical: [{lo:.3f}, {hi:.3f}]\n")
    print(f"{'pop':>4} {'n':>5} {'PASS':>5} {'FAIL':>5} {'INADM':>5} {'broken':>7} {'ratio p50':>9} {'ratio p95':>9} "
          f"{'floor binds':>11} {'cap binds':>9}")
    for name, p in results.items():
        recs = p["records"]
        status = [r["base"] for r in recs]
        ratio = np.array([r["ratio"] for r in recs])
        print(f"{name:>4} {len(recs):>5} {status.count('PASS'):>5} {status.count('FAIL'):>5} "
              f"{status.count('INADMISSIBLE'):>5} {sum(r['broken'] for r in recs):>7} {np.median(ratio):>9.3f} "
              f"{np.percentile(ratio, 95):>9.3f} {sum(r['floor_binds'] for r in recs):>11} "
              f"{sum(r['cap_binds'] for r in recs):>9}")

    chosen, rule, rows = select(results)
    feasible = sorted((r for r in rows if r["dense_refusals"] == 0), key=lambda r: (-r["tpr"], r["fpr"]))
    print("\nFeasible frontier (zero dense refusals), best detection first:")
    print(f"{'s_min':>5} {'q_min':>5} {'share':>6} {'tau':>6} {'broken refused':>15} {'sound refused':>14}")
    seen = set()
    for r in feasible:
        key = (r["broken_refusals"], r["sound_refusals"])
        if key in seen:
            continue
        seen.add(key)
        print(f"{r['s_min']:>5} {r['q_min']:>5} {r['share']:>6} {r['tau']:>6} "
              f"{r['broken_refusals']:>6}/{r['n_broken']:<8} {r['sound_refusals']:>5}/{r['n_sound']:<8}")
        if len(seen) >= 25:
            break

    print(f"\nCHOSEN ({rule})")
    if chosen is not None:
        tpr_ci = wilson_ci(chosen["broken_refusals"], chosen["n_broken"])
        fpr_ci = wilson_ci(chosen["sound_refusals"], chosen["n_sound"])
        print(f"  s_min={chosen['s_min']}, q_min={chosen['q_min']}, share={chosen['share']}, tau={chosen['tau']}")
        print(f"  dense refusals: 0/{chosen['n_dense']} (95% upper bound {3 / chosen['n_dense']:.3%})")
        print(f"  broken refused: {chosen['broken_refusals']}/{chosen['n_broken']} ({chosen['tpr']:.1%}, "
              f"95% CI {tpr_ci[0]:.1%}-{tpr_ci[1]:.1%})")
        print(f"  sound refused:  {chosen['sound_refusals']}/{chosen['n_sound']} ({chosen['fpr']:.1%}, "
              f"95% CI {fpr_ci[0]:.1%}-{fpr_ci[1]:.1%})")
        args = (chosen["s_min"], chosen["q_min"], chosen["share"], chosen["tau"])
        for name, p in results.items():
            if p["kind"] != "sparse":
                continue
            recs = p["records"]
            nb = sum(r["broken"] for r in recs)
            print(f"  {name}: broken refused {sum(refused(r, *args) for r in recs if r['broken'])}/{nb}, "
                  f"sound refused {sum(refused(r, *args) for r in recs if not r['broken'])}/{len(recs) - nb}")
    return {"dense_band": (lo, hi), "chosen": chosen, "rule": rule, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=os.cpu_count())
    parser.add_argument("--smoke", action="store_true", help="3 transcripts per population, nothing saved")
    args = parser.parse_args()
    counts = {name: (3 if args.smoke else n) for name, (_, n, _) in POPULATIONS.items()}
    results = run(counts, args.workers)
    selection = report(results)
    if not args.smoke:
        with open(OUTPUT, "wb") as f:
            pickle.dump({"results": results, "selection": selection}, f)


if __name__ == "__main__":
    main()
