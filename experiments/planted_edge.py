"""7.5's scripted half: the registered searchers on planted panels, both tiers priced.

`prereg/planted-edge.md`, "Scripted half, first". Per panel seed, all four levels,
paired (one residual draw and one planted member per seed, `environments/planted_panel`):

1. the realized class maximum, and the **class-tier null** -- the class maximum of the
   demeaned net Sharpe on each of B stationary-bootstrap replicates -- in one streamed
   pass over all 82,240 members (no table is materialised: each chunk's streams are
   computed, priced against a (T, B) count matrix, and discarded);
2. the six registered searchers (`searchers.meta_adaptive.registered_71`), class-capped,
   scored on the panel's own net streams;
3. each searcher's **trigger-replay null** (7.1's null 2, the certifying replay null) on
   the SAME B replicates, so a run's two tiers price on identical resamples;
4. population truths (`environments.planted_panel.truth`) for every submission, the
   planted member and the class argmax, and each submission's realized holdout Sharpe.

**The statistic is the sandbox's**, unguarded, as `environments/class_table.py`
explains: mean over standard deviation of the net stream, annualised.

    python -m experiments.planted_edge --smoke 8 --workers 7          # cost only
    python -m experiments.planted_edge --draws 2000 --workers 31      # the registered run

`--smoke` takes the dedicated block 980000-980999, prints and writes **cost only** --
wall time per stage, peak memory -- and no rule quantity (`prereg/README.md`).
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, canonical, streams_for
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from experiments._resume import load_done

SEED0 = 600_000              # registered: 600000-601999
SEED0_SMOKE = 980_000        # smoke and scaling, cost only
B_DEFAULT = 1_000
N_REGISTERED = 2000          # the curve's registered seeds, 600000-601999
ALPHAS = (0.05, 0.01)


def _sharpe_rows(S: np.ndarray, ann: float) -> np.ndarray:
    std = S.std(axis=1, ddof=1)
    return np.where(std > 0, S.mean(axis=1) / np.where(std > 0, std, 1.0), 0.0) * ann


def _sharpe(x: np.ndarray, ann: float) -> float:
    s = float(x.std(ddof=1))
    return float(x.mean() / s * ann) if s > 0 else 0.0


class StreamCache:
    """Net streams by support, for the few specifications scored off the class pass
    (the holdout). A miss at depth d computes every signed extension of the support's
    canonical depth-(d-1) prefix at once, so the batched (n >= 2) kernel is always the
    one used."""

    def __init__(self, panel):
        self.panel = panel
        self.K = panel.features.shape[2]
        self.full: dict = {}

    def get(self, support):
        key = canonical(support)
        if key not in self.full:
            prefix = key[:-1]
            held = {k for k, _ in prefix}
            batch = [prefix + ((j, s),) for j in range(self.K) if j not in held
                     for s in (1.0, -1.0)]
            for sup, x in zip(batch, streams_for(self.panel, batch)):
                self.full[canonical(sup)] = x
        return self.full[key]


def _searchers(seed: int, T: int, ppy: float):
    from searchers.meta_adaptive import registered_71
    se = float(np.sqrt(ppy / T))
    return [s.set_class(pp.CLS) for s in registered_71(seed, se)]


def peak_rss_mb() -> float:
    """`ru_maxrss` is BYTES on macOS and KILOBYTES on Linux."""
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 2**10


def run_level(base, seed: int, beta: float, B: int, inv: dict,
              overlap: tuple | None = None) -> dict:
    """One level of one seed. `overlap` is the seed's (E[a], E[a^2], E[a k]); the
    first level computes it inside its class pass and every later level of the same
    seed reuses it, since positions and w* do not change with the level."""
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

    # 1. the class pass: every member's realized Sharpe and its Sharpe on every
    # replicate, from one streamed pass. The class-tier null is the column maximum;
    # the searchers below read the SAME arrays, so the two tiers of a run price on
    # identical numbers. Streams are discarded chunk by chunk; the (N, B) replicate
    # matrix is kept (82,240 x 1,000 float64, about 660 MB).
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
            # streams_for's streams bit for bit, plus the seed's overlap moments
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

    # 2-3. the searchers, realized and under trigger replay, by lookup
    t0 = time.time()
    single_ix = [index[canonical(((k, 1.0),))] for k in range(K)]
    out_s = []
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
        out_s.append({"searcher": srch.name, "support": sub, "score": score,
                      "n_moves": n,
                      "p_class": (1 + int(np.sum(M_b >= score))) / (B + 1),
                      "p_trigger": (1 + int(np.sum(n2 >= score))) / (B + 1)})
    t["searchers_realized"] = time.time() - t0 - t_null
    t["trigger_nulls"] = t_null
    del rep

    # 4. truths, recovery and the realized holdout. Every member's population Sharpe
    # in closed form from the pass's overlap moments and the run's invariants.
    t0 = time.time()
    pop = pp.population_from_moments(Ea, Ea2, Eak, inv, draw.c, panel.periods_per_year)
    star = canonical(draw.m_star)
    star_set = set(star)
    if beta > 0:
        assert abs(pop[index[star]] - beta) < 1e-8, "closed form disagrees with the scale"
    jp = int(np.argmax(pop))
    plus = canonical(members[jp])

    def overlap(sup, ref):
        cs = set(canonical(sup)) if sup else set()
        need = 2 if len(ref) == 3 else len(ref)
        return len(cs & set(ref)) >= need

    def recovery(sup):
        return {"equals": canonical(sup) == star if sup else False,
                "two_of_three": overlap(sup, star),
                "equals_pop_best": canonical(sup) == plus if sup else False,
                "two_of_three_pop_best": overlap(sup, plus)}

    ho_cache = StreamCache(draw.holdout)
    for r in out_s:
        sup = r["support"]
        r["truth"] = ({"in_sample": float(pop[index[canonical(sup)]]),
                       "holdout": pp.truth(base, draw, sup)["holdout"]} if sup else None)
        r["holdout_realized"] = _sharpe(ho_cache.get(sup), ann) if sup else None
        r.update(recovery(sup))
        r["support"] = [list(p) for p in canonical(sup)] if sup else None
    rec = {"seed": seed, "beta": beta, "c": draw.c,
           "planted": [list(p) for p in star], "block_length_null": L, "B": B,
           "planted_truth": pp.truth(base, draw, draw.m_star),
           "planted_realized": float(obs[index[star]]),
           "class_max": best, "class_argmax": [list(p) for p in canonical(best_m)],
           "class_argmax_truth": pp.truth(base, draw, best_m),
           "class_argmax_recovery": recovery(best_m),
           "null_max_mean": float(M_b.mean()),
           "pop_best": [list(p) for p in plus], "pop_best_sr": float(pop[jp]),
           "pop_n_positive": int((pop > 0).sum()),
           "planted_rank": int((pop > pop[index[star]]).sum()) + 1,
           "null_max_q": {str(a): float(np.quantile(M_b, 1 - a)) for a in ALPHAS},
           "searchers": out_s}
    t["finalise"] = time.time() - t0
    rec["secs"] = t
    rec["_overlap"] = (Ea, Ea2, Eak)
    return rec


def run_seed(payload) -> dict:
    seed, levels, B = payload
    base = pp.load_base()
    inv = pp.invariants_for(base)          # computed once by the parent, loaded here
    t0 = time.time()
    recs, overlap = [], None
    for b in levels:
        r = run_level(base, seed, b, B, inv, overlap)
        overlap = r.pop("_overlap")
        recs.append(r)
    out = {"seed": seed, "levels": recs}
    out["secs"] = time.time() - t0
    out["peak_rss_mb"] = peak_rss_mb()
    from experiments.code_state import platform_info
    out["platform"] = platform_info()
    return out


COST_ONLY = ("seed", "secs", "peak_rss_mb")


def cost_only(rec: dict) -> dict:
    return {"seed": rec["seed"], "secs": rec["secs"], "peak_rss_mb": rec["peak_rss_mb"],
            "stage_secs": [lv["secs"] for lv in rec["levels"]],
            "platform": rec.get("platform")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=2000)
    ap.add_argument("--levels", default=",".join(str(b) for b in pp.LEVELS))
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="runs/planted_edge_scripted")
    ap.add_argument("--price-per-hour", type=float, default=None,
                    help="the instance's on-demand $/h, for the smoke's dollar projection "
                         "(c7a.48xlarge 9.85, c7a.8xlarge 1.64); without it the smoke "
                         "projects hours only")
    ap.add_argument("--projected-workers", type=int, default=None,
                    help="the worker count the registered run will use; default --workers")
    ap.add_argument("--smoke", type=int, default=0,
                    help="N panels on the smoke block 980000+, cost only, no rule quantity")
    a = ap.parse_args(argv)
    levels = [float(x) for x in a.levels.split(",")]

    smoke = a.smoke > 0
    seed0, n = (SEED0_SMOKE, a.smoke) if smoke else (SEED0, a.draws)
    if smoke and n > 1000:
        raise SystemExit("the smoke block is 980000-980999")
    out = Path("runs/_smoke/planted_edge" if smoke else a.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "draws.jsonl"
    done = load_done(path)          # a truncated last line is dropped, its seed redone
    todo = [(seed0 + i, levels, a.B) for i in range(n) if seed0 + i not in done]
    print(f"{'SMOKE (cost only)' if smoke else 'REGISTERED'}: seeds {seed0}-{seed0 + n - 1},"
          f" levels {levels}, B {a.B}, {len(todo)} to run, {len(done)} done", flush=True)

    # the panel-invariant population moments: once per run, in the parent, cached
    ti = time.time()
    pp.invariants_for(pp.load_base())
    t_inv = time.time() - ti
    print(f"  invariant population moments ready in {t_inv:.0f}s (0 if cached)", flush=True)

    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=a.workers) as pool, open(path, "a") as fh:
        futs = [pool.submit(run_seed, p) for p in todo]
        for fut in as_completed(futs):
            rec = fut.result()
            fh.write(json.dumps(cost_only(rec) if smoke else rec, default=str) + "\n")
            fh.flush()
            print(f"  seed {rec['seed']} done in {rec['secs']:.0f}s, "
                  f"peak RSS {rec['peak_rss_mb']:.0f} MB", flush=True)
    wall = time.time() - t0

    if smoke:
        recs = [json.loads(l) for l in path.read_text().splitlines() if l]
        per_seed = np.array([r["secs"] for r in recs])
        stages = {}
        for r in recs:
            for lv in r["stage_secs"]:
                for k, v in lv.items():
                    stages.setdefault(k, []).append(v)
        W = a.projected_workers or a.workers
        # two projections for N_REGISTERED seeds on W workers: mean throughput (every
        # worker always busy), and an upper bound of full rounds each as long as the
        # slowest seed seen
        h_mean = N_REGISTERED * per_seed.mean() / W / 3600
        h_upper = int(np.ceil(N_REGISTERED / W)) * per_seed.max() / 3600
        price = a.price_per_hour
        dollars = ("" if price is None else
                   f" -> ${h_mean * price:.0f} (mean) to ${h_upper * price:.0f} (upper) "
                   f"at ${price:.2f}/h")
        L = ["7.5 scripted half — SMOKE, cost only (no rule quantity is written or shown)",
             "=" * 78,
             f"  panels {len(recs)} (seeds {seed0}-{seed0 + n - 1}), levels {len(levels)}, "
             f"B {a.B}, workers {a.workers}, wall {wall:.0f}s",
             f"  per seed (all levels): mean {per_seed.mean():.0f}s  median "
             f"{np.median(per_seed):.0f}s  max {per_seed.max():.0f}s",
             "  per level, by stage (median s): " + ", ".join(
                 f"{k} {np.median(v):.1f}" for k, v in stages.items()),
             f"  peak RSS per worker: max {max(r['peak_rss_mb'] for r in recs):.0f} MB",
             f"  invariant population moments, once per run: {t_inv:.0f}s this invocation"
             " (0 when the cache already held them)",
             f"  projection for {N_REGISTERED:,} seeds on {W} workers: {h_mean:.2f} h "
             f"(mean throughput) to {h_upper:.2f} h ({int(np.ceil(N_REGISTERED / W))} "
             f"rounds x the slowest seed){dollars}",
             ("  no --price-per-hour given: hours only" if price is None else
              "  re-measure on the registered instance before launch (prereg/README.md, "
              "Sizing)")]
        text = "\n".join(L)
        print("\n" + text)
        (out / "smoke_cost.txt").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
