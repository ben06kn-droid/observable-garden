"""V2, the confidence calibration cell (`prereg/confidence-output.md`, draft).

Per panel seed, at levels 0, 1.0 and 1.5, on the planted generator and the pinned X,
B = 1,000. Everything below is stage 1's computation (`experiments/planted_edge.run_level`)
plus what the confidence draft needs:

- **V2:** `D = max over all 82,240 members of (realized Sharpe - in-sample population
  Sharpe)`, from the class pass's own realized Sharpes and the closed-form population
  Sharpes. It is set against the class-tier null `M_b`: the quantiles at 0.90, 0.95
  and 0.99, whether `D` is at or under each, and the PIT value `u = #{M_b < D}/B`.
- **V1 and V3, confirmatory on this block:** for the six registered searchers and the
  class argmax, the confidence fields of `quixote.confidence` on the class tier, and,
  for the searchers, on the trigger-replay tier (audit). Also the in-sample and
  holdout population Sharpe, and the realized holdout Sharpe.

**`run_level` is copied, not imported.** `experiments/planted_edge.py` is frozen for
stage 1's replication, and its `run_level` keeps neither the replicate maxima nor the
realized Sharpes. The class pass, the searchers, the trigger nulls and the truths
below are its code. `tests/test_confidence_cell.py` holds every field the two share
equal on a synthetic base.

**The registered run is refused until V2 is live.** A run on 620000-620999 needs the
line `## V2 — LIVE` in the pre-registration. `--smoke` uses this file's own smoke block,
981000-981999, writes cost only, and needs nothing.

    python -m experiments.confidence_cell --smoke 191 --workers 191 --price-per-hour 9.85
    python -m experiments.confidence_cell --draws 1000 --workers 191
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, canonical, streams_for
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from experiments._resume import load_done
from experiments.planted_edge import (StreamCache, _searchers, _sharpe, _sharpe_rows,
                                      peak_rss_mb)
from quixote.confidence import GRID, confidence

SEED0 = 620_000                 # 620000-620999, checked 2026-10-04
N_REGISTERED = 1000
SEED0_SMOKE = 981_000           # this file's own smoke block, 981000-981999
LEVELS = (0.0, 1.0, 1.5)
B_DEFAULT = 1_000
GS = (0.90, 0.95, 0.99)
PREREG = Path(__file__).resolve().parent.parent / "prereg" / "confidence-output.md"
LIVE_MARK = "## V2 — LIVE"


def compact(conf: dict) -> dict:
    """A confidence dict with its curve stored as integer counts `n_ge[k] = #{reps >=
    S - s_k}`, from which `C(s_k) = 1 - (1 + n_ge[k])/(B + 1)` is exact."""
    out = dict(conf)
    C = np.asarray(out.pop("curve"))
    out["n_ge"] = [int(x) for x in np.rint((1.0 - C) * (conf["B"] + 1) - 1)]
    return out


def run_level_conf(base, seed: int, beta: float, B: int, inv: dict,
                   overlap: tuple | None = None) -> dict:
    """`planted_edge.run_level`, plus V2's D and the confidence fields."""
    t = {}
    t0 = time.time()
    draw = pp.make_draw(base, seed, beta)
    panel = draw.in_sample
    T, M, K = panel.features.shape
    ann = float(np.sqrt(panel.periods_per_year))
    from environments.real_sandbox import RealSandbox
    bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(seed)
    rows = [stationary_bootstrap_indices(T, L, rng) for _ in range(B)]
    C = np.empty((T, B))
    for b, r in enumerate(rows):
        C[:, b] = np.bincount(r, minlength=T)
    t["generate"] = time.time() - t0

    # 1. the class pass, as in run_level
    t0 = time.time()
    members = base.members
    index = {canonical(m): i for i, m in enumerate(members)}
    N = len(members)
    obs = np.empty(N)
    rep = np.empty((N, B))
    first = overlap is None
    if first:
        Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    else:
        Ea, Ea2, Eak = overlap
    for s in range(0, N, CHUNK):
        if first:
            X, Ea[s:s + CHUNK], Ea2[s:s + CHUNK], Eak[s:s + CHUNK] = \
                pp.streams_with_overlap(panel, members[s:s + CHUNK], draw.w_star_is)
        else:
            X = streams_for(panel, members[s:s + CHUNK])
        obs[s:s + len(X)] = _sharpe_rows(X, ann)
        X0 = X - X.mean(axis=1, keepdims=True)
        mean = (X0 @ C) / T
        var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
        pos = var > 0
        rep[s:s + len(X)] = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)),
                                     0.0) * ann
    j = int(np.argmax(obs))
    best, best_m = float(obs[j]), members[j]
    M_b = rep.max(axis=0)
    t["class_pass"] = time.time() - t0

    # 2-3. the searchers, realized and under trigger replay, by lookup; the replay
    # replicates are kept for the audit tier's confidence fields
    t0 = time.time()
    single_ix = [index[canonical(((k, 1.0),))] for k in range(K)]
    out_s, n2s = [], []
    t_null = 0.0
    for srch in _searchers(seed, T, panel.periods_per_year):
        tr = srch._search(K, lambda k: float(obs[single_ix[k]]),
                          lambda sup: float(obs[index[canonical(sup)]]))
        sub = tuple(tr.support)
        score = float(tr.score)
        n = tr.n_moves
        t1 = time.time()
        n2 = np.empty(B)
        for b in range(B):
            col = rep[:, b]
            n2[b] = srch._search(K, lambda k, col=col: float(col[single_ix[k]]),
                                 lambda sup, col=col: float(col[index[canonical(sup)]]),
                                 meta_steps=n).score
        t_null += time.time() - t1
        n2s.append(n2)
        out_s.append({"searcher": srch.name, "support": sub, "score": score,
                      "n_moves": n,
                      "p_class": (1 + int(np.sum(M_b >= score))) / (B + 1),
                      "p_trigger": (1 + int(np.sum(n2 >= score))) / (B + 1)})
    t["searchers_realized"] = time.time() - t0 - t_null
    t["trigger_nulls"] = t_null
    del rep

    # 4. truths, as in run_level, and V2's D
    t0 = time.time()
    pop = pp.population_from_moments(Ea, Ea2, Eak, inv, draw.c, panel.periods_per_year)
    star = canonical(draw.m_star)
    if beta > 0:
        assert abs(pop[index[star]] - beta) < 1e-8, "closed form disagrees with the scale"
    jp = int(np.argmax(pop))
    err = obs - pop
    jd = int(np.argmax(err))
    D = float(err[jd])
    v2 = {"D": D, "D_member": [list(p) for p in canonical(members[jd])],
          "u": float(np.sum(M_b < D)) / B,
          "q": {f"{g:.2f}": float(np.quantile(M_b, g)) for g in GS},
          "covered": {f"{g:.2f}": bool(D <= np.quantile(M_b, g)) for g in GS}}

    ppy = float(panel.periods_per_year)
    ho_cache = StreamCache(draw.holdout)
    for r, n2 in zip(out_s, n2s):
        sup = r["support"]
        r["truth"] = ({"in_sample": float(pop[index[canonical(sup)]]),
                       "holdout": pp.truth(base, draw, sup)["holdout"]} if sup else None)
        r["holdout_realized"] = _sharpe(ho_cache.get(sup), ann) if sup else None
        r["conf_class"] = compact(confidence(r["score"], M_b, ppy=ppy,
                                             tier="declared class")) if sup else None
        r["conf_replay"] = compact(confidence(r["score"], n2, ppy=ppy,
                                              tier="trigger replay (audit)")) if sup else None
        r["support"] = [list(p) for p in canonical(sup)] if sup else None
    argmax = {"support": [list(p) for p in canonical(best_m)], "score": best,
              "truth": {"in_sample": float(pop[j]),
                        "holdout": pp.truth(base, draw, best_m)["holdout"]},
              "holdout_realized": _sharpe(ho_cache.get(best_m), ann),
              "conf_class": compact(confidence(best, M_b, ppy=ppy, tier="declared class"))}
    rec = {"seed": seed, "beta": beta, "c": draw.c,
           "planted": [list(p) for p in star], "block_length_null": L, "B": B,
           "class_max": best, "class_argmax": argmax["support"],
           "pop_best": [list(p) for p in canonical(members[jp])],
           "pop_best_sr": float(pop[jp]), "null_max_mean": float(M_b.mean()),
           "v2": v2, "argmax": argmax, "searchers": out_s,
           "grid": [float(GRID[0]), float(GRID[1] - GRID[0]), int(GRID.size)]}
    t["finalise"] = time.time() - t0
    rec["secs"] = t
    rec["_overlap"] = (Ea, Ea2, Eak)
    return rec


def run_seed(payload) -> dict:
    seed, levels, B = payload
    base = pp.load_base()
    inv = pp.invariants_for(base)
    t0, c0 = time.time(), time.process_time()
    recs, overlap = [], None
    for b in levels:
        r = run_level_conf(base, seed, b, B, inv, overlap)
        overlap = r.pop("_overlap")
        recs.append(r)
    from experiments.code_state import platform_info
    return {"seed": seed, "levels": recs, "secs": time.time() - t0,
            "cpu_secs": time.process_time() - c0, "peak_rss_mb": peak_rss_mb(),
            "platform": platform_info()}


def cost_only(rec: dict) -> dict:
    return {"seed": rec["seed"], "secs": rec["secs"], "cpu_secs": rec["cpu_secs"],
            "peak_rss_mb": rec["peak_rss_mb"],
            "stage_secs": [lv["secs"] for lv in rec["levels"]],
            "platform": rec.get("platform")}


def require_live(path: Path = PREREG) -> None:
    if LIVE_MARK not in path.read_text():
        raise SystemExit(f"V2 is not live: {path.name} has no '{LIVE_MARK}' section. "
                         "Only --smoke runs before the live commit.")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=N_REGISTERED)
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="runs/confidence_cell")
    ap.add_argument("--smoke", type=int, default=0,
                    help="N panels on 981000+, cost only, no rule quantity")
    ap.add_argument("--price-per-hour", type=float, default=None)
    ap.add_argument("--projected-workers", type=int, default=None)
    a = ap.parse_args(argv)
    smoke = a.smoke > 0
    if smoke and a.smoke > 1000:
        raise SystemExit("the smoke block is 981000-981999")
    if not smoke:
        require_live()
        if a.draws != N_REGISTERED or a.B != B_DEFAULT:
            raise SystemExit(f"the registered run is {N_REGISTERED} seeds at B = {B_DEFAULT}")
    seed0, n = (SEED0_SMOKE, a.smoke) if smoke else (SEED0, a.draws)
    out = Path("runs/_smoke/confidence_cell" if smoke else a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "draws.jsonl"
    done = load_done(path)
    todo = [(seed0 + i, list(LEVELS), a.B) for i in range(n) if seed0 + i not in done]
    print(f"{'SMOKE (cost only)' if smoke else 'REGISTERED'}: seeds {seed0}-{seed0 + n - 1}, "
          f"levels {list(LEVELS)}, B {a.B}, {len(todo)} to run, {len(done)} done", flush=True)
    ti = time.time()
    pp.invariants_for(pp.load_base())
    print(f"  invariant population moments ready in {time.time() - ti:.0f}s", flush=True)

    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=a.workers) as pool, open(path, "a") as fh:
        for fut in as_completed([pool.submit(run_seed, p) for p in todo]):
            rec = fut.result()
            fh.write(json.dumps(cost_only(rec) if smoke else rec, default=str) + "\n")
            fh.flush()
            print(f"  seed {rec['seed']} done in {rec['secs']:.0f}s, "
                  f"peak RSS {rec['peak_rss_mb']:.0f} MB", flush=True)
    wall = time.time() - t0

    if smoke:
        recs = [json.loads(l) for l in path.read_text().splitlines() if l]
        per = np.array([r["secs"] for r in recs])
        W = a.projected_workers or a.workers
        h_mean = N_REGISTERED * per.mean() / W / 3600
        h_up = int(np.ceil(N_REGISTERED / W)) * per.max() / 3600
        price = a.price_per_hour
        L = ["confidence cell (V2) — SMOKE, cost only (no rule quantity is written or shown)",
             "=" * 78,
             f"  panels {len(recs)}, levels {list(LEVELS)}, B {a.B}, workers {a.workers}, "
             f"wall {wall:.0f}s",
             f"  per seed: wall mean {per.mean():.0f}s  median {np.median(per):.0f}s  "
             f"max {per.max():.0f}s; peak RSS max "
             f"{max(r['peak_rss_mb'] for r in recs):.0f} MB",
             f"  projection for {N_REGISTERED} seeds on {W} workers: {h_mean:.2f} h (mean "
             f"throughput) to {h_up:.2f} h (upper)"
             + ("" if price is None else
                f" -> ${h_mean * price:.0f} to ${h_up * price:.0f} at ${price:.2f}/h")]
        text = "\n".join(L)
        print("\n" + text)
        (out / "smoke_cost.txt").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
