"""The scripted twin cell (`prereg/twin-calibration.md`, the planted-panel amendment).

Per panel seed, at level 0 and one planted level (`environments/planted_panel.py`):
the real panel and **K = 19 twins under each of `joint_time_permutation` and
`block_permutation`** (`quixote/twins.py`) — 39 return matrices per level — each
priced by the **class tier** (the certifying tier by the 2026-09-30 tier rule), and each
of the six registered scripted searchers, class-capped, run on every matrix. The twin
p-value is the registered rank,

    p = (1 + #{twins k with p_k <= p_real}) / (K + 1),

with ties counted against the real run, as registered.

**A twin here permutes the rows of the panel's return matrix against X, which stays in
calendar order.** Positions are a function of X alone, so every member's cost and
borrow path is identical in the real panel and in all its twins, and one position loop
per chunk serves all 39 matrices (`streams_multi`). Each matrix is priced by the same
function: its own null block length from its own depth-1 (+) streams, its own B
replicates from `default_rng(panel seed)` — so the procedure applied to the real panel
and to a twin is one procedure, which exchangeability needs.

    python -m experiments.planted_twins --smoke 2 --workers 2      # cost only
    python -m experiments.planted_twins --draws N --workers 31     # the registered run

`--smoke` takes the dedicated block 985000-985999 and writes cost only.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, canonical
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from experiments.planted_edge import _searchers, _sharpe_rows, peak_rss_mb
from quixote.twins import K_FOR_ALPHA, twin_p_value, twins

SEED0 = 650_000
SEED0_SMOKE = 985_000
K = K_FOR_ALPHA[0.05]            # 19, registered
B_DEFAULT = 1_000
CONSTRUCTIONS = ("joint_time_permutation", "block_permutation")
PRICE_PER_HOUR = 9.85 / 6


def streams_multi(panel, supports, R_stack: np.ndarray) -> np.ndarray:
    """(J, n, T) net streams of `supports` against J return matrices at once.
    `R_stack` is (T, M, J). Positions, costs and borrow are computed once."""
    T = panel.features.shape[0]
    J = R_stack.shape[2]
    n = len(supports)
    out = np.empty((J, n, T))

    def step(t, new, prev):
        k = ((np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
             + (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        out[:, :, t] = (new @ R_stack[t]).T - k

    pp._positions_loop(panel, supports, step)
    return out


def _count_matrix(T, L, B, seed):
    rng = np.random.default_rng(seed)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    return C


def run_level(base, seed: int, beta: float, B: int) -> dict:
    t = {}
    t0 = time.time()
    draw = pp.make_draw(base, seed, beta)
    panel = draw.in_sample
    T, M, Kf = panel.features.shape
    ann = float(np.sqrt(panel.periods_per_year))
    # children [0..2] are the panel's own (pp.children); [3] and [4] are the twins'
    ch = np.random.SeedSequence(int(seed)).spawn(5)
    R0 = panel.returns
    mats = [R0]
    for c, cs in zip(CONSTRUCTIONS, (ch[3], ch[4])):
        mats += twins(R0, K, seed=cs, construction=c)
    J = len(mats)                                      # 1 + 2K = 39
    R_stack = np.stack(mats, axis=2)                   # (T, M, J)
    members = base.members
    N = len(members)
    index = {canonical(m): i for i, m in enumerate(members)}
    t["generate"] = time.time() - t0

    t0 = time.time()
    obs = np.empty((J, N))
    M_b = np.full((J, B), -np.inf)
    Cs, Ls, lag1 = None, None, None
    singles = [index[canonical(((k, 1.0),))] for k in range(Kf)]
    for s in range(0, N, CHUNK):
        X = streams_multi(panel, members[s:s + CHUNK], R_stack)       # (J, n, T)
        if Cs is None:
            # each matrix's own null block length, from its own depth-1 (+) streams;
            # the singles all sit in the first chunk
            assert max(singles) < CHUNK
            Ls = []
            for j in range(J):
                bc = X[j][singles].T
                Ls.append(int(select_block_length(bc - bc.mean(axis=0))))
            Cs = [_count_matrix(T, L, B, seed) for L in Ls]
            x0 = X[0] - X[0].mean(axis=1, keepdims=True)
            num = (x0[:, 1:] * x0[:, :-1]).sum(axis=1)
            den = (x0 * x0).sum(axis=1)
            lag1 = float(np.median(np.where(den > 0, num / np.where(den > 0, den, 1), 0)))
        for j in range(J):
            Xj = X[j]
            obs[j, s:s + len(Xj)] = _sharpe_rows(Xj, ann)
            X0 = Xj - Xj.mean(axis=1, keepdims=True)
            mean = (X0 @ Cs[j]) / T
            var = ((X0 * X0) @ Cs[j] - T * mean * mean) / (T - 1)
            pos = var > 0
            null = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
            M_b[j] = np.maximum(M_b[j], null.max(axis=0))
    t["class_pass"] = time.time() - t0

    t0 = time.time()
    single_ix = singles
    out = []
    for srch in _searchers(seed, T, panel.periods_per_year):
        p, score, sub = np.empty(J), np.empty(J), None
        for j in range(J):
            o = obs[j]
            tr = srch._search(Kf, lambda k, o=o: float(o[single_ix[k]]),
                              lambda sup, o=o: float(o[index[canonical(sup)]]))
            score[j] = tr.score
            p[j] = (1 + int(np.sum(M_b[j] >= tr.score))) / (B + 1)
            if j == 0:
                sub = canonical(tuple(tr.support))
        rec = {"searcher": srch.name, "support": [list(q) for q in sub],
               "score_real": float(score[0]), "p_class_real": float(p[0]),
               "truth_in_sample": pp.truth(base, draw, sub)["in_sample"]}
        for c_i, c in enumerate(CONSTRUCTIONS):
            pk = p[1 + c_i * K: 1 + (c_i + 1) * K]
            rec[f"p_twin_{c}"] = twin_p_value(p[0], pk)
            rec[f"ties_{c}"] = int(np.sum(pk == p[0]))
        out.append(rec)
    t["searchers"] = time.time() - t0
    return {"seed": seed, "beta": beta, "c": draw.c, "block_lengths": Ls,
            "median_lag1_autocorr_real": lag1, "searchers": out, "secs": t}


def run_seed(payload) -> dict:
    seed, levels, B = payload
    base = pp.load_base()
    t0 = time.time()
    out = {"seed": seed, "levels": [run_level(base, seed, b, B) for b in levels]}
    out["secs"] = time.time() - t0
    out["cpu_secs"] = time.process_time()             # unaffected by sleep
    out["peak_rss_mb"] = peak_rss_mb()
    return out


def cost_only(rec: dict) -> dict:
    return {"seed": rec["seed"], "secs": rec["secs"], "cpu_secs": rec.get("cpu_secs"),
            "peak_rss_mb": rec["peak_rss_mb"],
            "stage_secs": [lv["secs"] for lv in rec["levels"]]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=0)
    ap.add_argument("--planted", type=float, default=None,
                    help="the planted level: stage 1's nearest-the-bar, once fixed")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="runs/planted_twins")
    ap.add_argument("--smoke", type=int, default=0)
    a = ap.parse_args(argv)
    smoke = a.smoke > 0
    if smoke:
        planted = 1.0 if a.planted is None else a.planted   # cost does not depend on it
        seed0, n = SEED0_SMOKE, a.smoke
    else:
        if a.planted is None:
            raise SystemExit("--planted is required: stage 1's nearest-the-bar, fixed by "
                             "dated commit before this cell is live")
        planted, seed0, n = a.planted, SEED0, a.draws
    levels = [0.0, planted]
    out = Path("runs/_smoke/planted_twins" if smoke else a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "draws.jsonl"
    done = {json.loads(l)["seed"] for l in path.read_text().splitlines() if l} \
        if path.exists() else set()
    todo = [(seed0 + i, levels, a.B) for i in range(n) if seed0 + i not in done]
    print(f"{'SMOKE (cost only)' if smoke else 'REGISTERED'}: seeds {seed0}-{seed0 + n - 1}, "
          f"levels {levels}, K {K} x {len(CONSTRUCTIONS)}, B {a.B}, {len(todo)} to run",
          flush=True)
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
        stages = {}
        for r in recs:
            for lv in r["stage_secs"]:
                for k, v in lv.items():
                    stages.setdefault(k, []).append(v)
        L = ["scripted twin cell — SMOKE, cost only (no rule quantity is written or shown)",
             "=" * 78,
             f"  panels {len(recs)} (seeds {seed0}-{seed0 + n - 1}), 2 levels, "
             f"{1 + 2 * K} return matrices per level, B {a.B}, workers {a.workers}, "
             f"wall {wall:.0f}s",
             f"  per seed (both levels): mean {per.mean():.0f}s wall  max {per.max():.0f}s; "
             f"CPU {np.mean([r['cpu_secs'] for r in recs]):.0f}s per worker process",
             "  per level, by stage (median s): " + ", ".join(
                 f"{k} {np.median(v):.1f}" for k, v in stages.items()),
             f"  peak RSS per worker: max {max(r['peak_rss_mb'] for r in recs):.0f} MB",
             f"  CPU-seconds per panel: {per.mean():.0f} (this machine, {a.workers} workers)"]
        text = "\n".join(L)
        print("\n" + text)
        (out / "smoke_cost.txt").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
