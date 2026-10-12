"""Diagnostics on 7.5, 2026-10-06. EXPLORATORY (`prereg/diagnostics-2026-10-06.md`).

On data already read: stage 1 (`30ee870`, seeds 600000-600199, extend-while-improving
and the realized class argmax), V2 (`0edab26`, C2 only), the 202 priced agent files
(`06a5284`) and the fidelity presentation log (`09e9235`). Fresh panels only on design
seeds 640100-640149 (E). These generate hypotheses and change no recorded result.

Positions and population Sharpes are recomputed with `environments/planted_fast.py`
on the pinned X; every definition is the pre-registration's.

    python -m experiments.diagnostics_2026_10_06 --out runs/diagnostics/2026-10-06.txt
    python -m experiments.diagnostics_2026_10_06 --smoke      # code paths only, no tables
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from itertools import permutations
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
STAGE1 = REPO / "runs/planted_edge_scripted/draws.jsonl"
V2 = REPO / "runs/confidence_cell/draws.jsonl"
AGENTS = REPO / "runs/planted_agent"
FIDELITY = REPO / "runs/planted_agent_fidelity/fidelity_live_presentations.jsonl"
STAGE1_SEEDS = range(600000, 600200)
DESIGN_SEEDS = range(640100, 640150)
E_LEVELS = (0.0, 1.0, 1.5)
S1_LEVELS = (0.0, 0.5, 1.0, 1.5)
AGENT_LEVELS = (0.0, 1.0, 1.5)
ARMS = ("replay gate", "unsaturable", "replay gate (reasoned pick)", "prior-weighted")
DELTAS = (0.05, 0.10, 0.20)
RHOS = (0.9, 0.8)
TAUS = (0.7, 0.8, 0.9)
B_E = 1000
EWI = "extend-while-improving"
S1_SRC_NAMES = ("S1 extend-while-improving", "S1 class argmax")
CACHE_KEY = "a8c4ecf1ed1b6262"
TOL_POP = 1e-8
TOL_E = 1e-9


def canon(sup):
    from environments.class_table import canonical
    return canonical(tuple((int(k), float(s)) for k, s in sup))


def wvec(sup, K=40):
    w = np.zeros(K)
    for k, s in sup:
        w[int(k)] = float(s)
    return w


def family_matching(S, M, match) -> int:
    """The maximum matching of distinct submission features to distinct m* features.
    Corrected after the run (4d0c7e1): the first version paired a submission shorter
    than m* only with m*'s first features."""
    if len(S) > len(M):
        S, M, match = M, S, (lambda a_, b_, f=match: f(b_, a_))
    best = 0
    for perm in permutations(range(len(M)), len(S)):
        best = max(best, sum(bool(match(S[i], M[p])) for i, p in enumerate(perm)))
    return best


# -- worker state ------------------------------------------------------------------

_W: dict = {}


def _init():
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    if _W:
        return _W
    base = pp.load_base()
    cache = pf.build(base.in_sample, base.members)
    if cache.key != CACHE_KEY:
        raise SystemExit(f"kernel cache key {cache.key}, expected {CACHE_KEY}")
    D = pf.demeaned(base.in_sample)
    Q = np.einsum("tmk,tml->tkl", D, D)
    _W.update(base=base, cache=cache, D=D, Q=Q, inv=pp.invariants_for(base))
    return _W


def _same_features(base, draw):
    a, b = base.in_sample, draw.in_sample
    for f in ("features", "cost_rate", "borrow_rate"):
        if not np.array_equal(np.asarray(getattr(a, f)), np.asarray(getattr(b, f))):
            raise AssertionError(f"rebuilt panel's {f} differ from the base's")


def norm2_all() -> np.ndarray:
    """Sum over days and assets of pos^2, every member, via Q (panel-independent)."""
    W = _init()
    cache, Q = W["cache"], W["Q"]
    T, K, _ = Q.shape
    Qf = Q.reshape(T, K * K)
    N = cache.N
    out = np.empty(N)
    for s in range(0, N, 512):
        mem = cache.members[s:s + 512]
        n = len(mem)
        idx = np.zeros((n, 3), int)
        sg = np.zeros((n, 3))
        for j, m in enumerate(mem):
            for a, (k, v) in enumerate(m):
                idx[j, a], sg[j, a] = int(k), float(v)
        quad = np.zeros((T, n))
        for a in range(3):
            for b in range(3):
                quad += Qf[:, idx[:, a] * K + idx[:, b]] * (sg[:, a] * sg[:, b])[None, :]
        g = np.asarray(cache.g[s:s + n]).T
        out[s:s + n] = np.divide(quad, g * g, out=np.zeros_like(quad), where=g > 0).sum(0)
    return out


def pair_corr(sa, sb) -> float:
    W = _init()
    cache, Q = W["cache"], W["Q"]
    ia, ib = cache.index[canon(sa)], cache.index[canon(sb)]
    ga, gb = np.asarray(cache.g[ia]), np.asarray(cache.g[ib])
    wa, wb = wvec(sa), wvec(sb)

    def dot(w1, g1, w2, g2):
        v = np.einsum("tkl,l->tk", Q, w2) @ w1
        den = g1 * g2
        return float(np.divide(v, den, out=np.zeros_like(v), where=den > 0).sum())
    return dot(wa, ga, wb, gb) / np.sqrt(dot(wa, ga, wa, ga) * dot(wb, gb, wb, gb))


def corr_with(ref_sup, norm2) -> np.ndarray:
    """Weight-path correlation of every member with one reference member."""
    import environments.planted_fast as pf
    W = _init()
    cache, Q = W["cache"], W["Q"]
    ir = cache.index[canon(ref_sup)]
    gr = np.asarray(cache.g[ir])
    V = np.einsum("tkl,l->tk", Q, wvec(ref_sup))
    V = np.divide(V, gr[:, None], out=np.zeros_like(V), where=gr[:, None] > 0)
    N = cache.N
    num = np.empty(N)
    for s in range(0, N, 512):
        e = min(s + 512, N)
        num[s:e] = pf.overlap(cache, V, s, e).sum(axis=1)
    return num / np.sqrt(norm2 * norm2[ir])


def panel_task(args):
    """Population Sharpes and the B1 sets for one seed's levels."""
    seed, levels, interest, norm2 = args
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    W = _init()
    base, cache, D, inv = W["base"], W["cache"], W["D"], W["inv"]
    t0 = time.time()
    draws = {lv: pp.make_draw(base, seed, lv) for lv in levels}
    for d in draws.values():
        _same_features(base, d)
    d0 = draws[levels[0]]
    G = np.einsum("tmk,tm->tk", D, d0.w_star_is)
    N = cache.N
    Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    for s in range(0, N, CHUNK):
        a = pf.overlap(cache, G, s, min(s + CHUNK, N))
        k = np.asarray(cache.k[s:s + len(a)])
        Ea[s:s + len(a)] = a.mean(axis=1)
        Ea2[s:s + len(a)] = (a * a).mean(axis=1)
        Eak[s:s + len(a)] = (a * k).mean(axis=1)
    ppy = d0.in_sample.periods_per_year
    pops = {lv: pp.population_from_moments(Ea, Ea2, Eak, inv, draws[lv].c, ppy)
            for lv in levels}
    corr_cache: dict = {}
    out = {}
    for lv in levels:
        pop = pops[lv]
        jp = int(np.argmax(pop))
        mplus = cache.members[jp]
        if jp not in corr_cache:
            corr_cache[jp] = corr_with(mplus, norm2)
        cr = corr_cache[jp]
        mstar = canon(draws[lv].m_star)
        sets = {f"S{d:.2f}": pop >= pop[jp] - d for d in DELTAS}
        sets.update({f"R{r:.1f}": cr >= r for r in RHOS})
        sups = {canon(s) for s in interest.get(lv, [])} | {mstar}
        info = {}
        for sp in sups:
            i = cache.index[sp]
            info[sp] = {"pop": float(pop[i]), "corr_mplus": float(cr[i]),
                        "in": {k: bool(v[i]) for k, v in sets.items()}}
        out[lv] = {"mplus": [list(p) for p in mplus], "pop_mplus": float(pop[jp]),
                   "mstar": [list(p) for p in mstar], "c": draws[lv].c,
                   "sizes": {k: int(v.sum()) for k, v in sets.items()}, "info": info}
    return seed, out, time.time() - t0


def e_task(args):
    """The class null on one seed's levels, reduced chunk by chunk (E)."""
    seed, levels, B = args
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    W = _init()
    base, cache, D = W["base"], W["cache"], W["D"]
    t0 = time.time()
    draws = [pp.make_draw(base, seed, b) for b in levels]
    for d in draws:
        _same_features(base, d)
    panel0 = draws[0].in_sample
    T = panel0.features.shape[0]
    ppy = float(panel0.periods_per_year)
    ann = float(np.sqrt(ppy))
    E = base.E_is[draws[0].idx_is]
    F0 = np.einsum("tmk,tm->tk", D, E)
    G = np.einsum("tmk,tm->tk", D, draws[0].w_star_is)
    N = cache.N
    res = {}
    for d in draws:
        bc = np.asarray(RealSandbox(d.in_sample, spec_class=pp.CLS).base_feature_columns(),
                        float)
        L = int(select_block_length(bc - bc.mean(axis=0)))
        rng = np.random.default_rng(seed)
        C = np.empty((T, B))
        for b in range(B):
            C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
        F = F0 + d.c * G
        M_all = np.full(B, -np.inf)
        M_sub = np.full(B, -np.inf)
        n1 = n2 = n_sub = 0
        cmax = -np.inf
        for s in range(0, N, CHUNK):
            X = pf.streams(cache, F, s, min(s + CHUNK, N))
            obs = pf._sharpe_rows(X, ann)
            X0 = X - X.mean(axis=1, keepdims=True)
            mean = (X0 @ C) / T
            var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
            pos = var > 0
            rep = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
            se = np.sqrt((1 + (obs / ann) ** 2 / 2) / T) * ann
            n1 += int((obs < -se).sum())
            n2 += int((obs < -2 * se).sum())
            keep = obs >= -2 * se
            n_sub += int(keep.sum())
            M_all = np.maximum(M_all, rep.max(axis=0))
            if keep.any():
                M_sub = np.maximum(M_sub, rep[keep].max(axis=0))
            cmax = max(cmax, float(obs.max()))
        res[float(d.beta)] = {"class_max": cmax, "null_max_mean": float(M_all.mean()),
                              "q95_all": float(np.quantile(M_all, 0.95)),
                              "q95_sub": float(np.quantile(M_sub, 0.95)),
                              "share_1se": n1 / N, "share_2se": n2 / N, "n_sub": n_sub,
                              "L": L}
    return seed, res, time.time() - t0


# -- formatting --------------------------------------------------------------------

def qs(x) -> str:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    if x.size == 0:
        return "n 0"
    q = np.percentile(x, [25, 50, 75])
    return f"n {x.size:4d}  q25 {q[0]:+.3f}  med {q[1]:+.3f}  q75 {q[2]:+.3f}"


def qsi(x) -> str:
    x = np.asarray(x, float)
    if x.size == 0:
        return "n 0"
    q = np.percentile(x, [25, 50, 75])
    return f"n {x.size:4d}  q25 {q[0]:.0f}  med {q[1]:.0f}  q75 {q[2]:.0f}"


def share(b) -> str:
    b = list(b)
    return f"{sum(b)}/{len(b)} = {sum(b) / len(b):.3f}" if b else "n 0"


def lsq(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    if x.size < 2 or np.ptp(x) == 0:
        return float("nan"), float("nan")
    b, a = np.polyfit(x, y, 1)
    return a, b


def errs(est, tgt) -> str:
    e = np.asarray(est, float) - np.asarray(tgt, float)
    if e.size == 0:
        return "n 0"
    q = np.percentile(e, [25, 50, 75])
    return (f"n {e.size:4d}  bias {e.mean():+.3f}  MAE {np.abs(e).mean():.3f}  "
            f"RMSE {np.sqrt((e * e).mean()):.3f}  err q25 {q[0]:+.3f} med {q[1]:+.3f} "
            f"q75 {q[2]:+.3f}")


def lvl(x) -> str:
    return f"{x:.1f}"


# -- loading -----------------------------------------------------------------------

def load_stage1(smoke):
    rows = []
    seeds = set(list(STAGE1_SEEDS)[:1] if smoke else STAGE1_SEEDS)
    for ln in open(STAGE1):
        r = json.loads(ln)
        if r["seed"] in seeds:
            rows.append(r)
    assert len(rows) == len(seeds)
    return rows


def load_agents(smoke):
    runs = []
    for f in sorted(glob.glob(str(AGENTS / "*.json"))):
        d = json.load(open(f))
        runs.append(d)
    assert len(runs) == 202
    if smoke:
        runs = [r for r in runs if r["seed"] == 630000]
    return runs


# -- main --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--smoke", action="store_true",
                    help="one seed per source and B = 50 for E; builds the tables but "
                         "prints none")
    a = ap.parse_args(argv)
    if not a.smoke and not a.out:
        raise SystemExit("--out is required for the run")
    for v in ("OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS",
              "MKL_NUM_THREADS"):
        os.environ[v] = "1"
    T0 = time.time()
    L: list[str] = []
    P = L.append
    from quixote import confidence as cf
    from scipy.stats import norm as N01

    W = _init()
    base, cache, D = W["base"], W["cache"], W["D"]
    K = D.shape[2]
    P("Diagnostics on 7.5, 2026-10-06 — EXPLORATORY (prereg/diagnostics-2026-10-06.md)")
    P("=" * 96)
    P("  On data already read: stage 1 30ee870 (seeds 600000-600199), V2 0edab26 (C2 only), "
      "agents 06a5284, fidelity 09e9235;")
    P("  fresh panels on design seeds 640100-640149 only (E). Hypothesis-generating; "
      "changes no recorded result.")
    P(f"  kernel environments/planted_fast.py, cache {cache.key}; quartiles are numpy "
      "linear 25/50/75; 'n' counts rows")
    P("")

    # ---- checks on the geometry ----
    norm2 = norm2_all()
    for sup in (cache.members[0], cache.members[1000], cache.members[50000],
                cache.members[82239]):
        i = cache.index[canon(sup)]
        g = np.asarray(cache.g[i])
        pos = np.einsum("tmk,k->tm", D, wvec(sup))
        pos = np.where((g > 0)[:, None], pos / np.where(g > 0, g, 1)[:, None], pos)
        assert np.abs(pos.sum(axis=1)).max() < 1e-12, "positions do not sum to zero"
        assert abs((pos * pos).sum() - norm2[i]) < 1e-9 * max(1, norm2[i]), "norm2"
    P("CHECKS")
    P("-" * 96)
    P("   every day's positions sum to zero across assets (checked on 4 members): the pooled "
      "mean is 0, Pearson = cosine")
    P("   sum of pos^2 via Q equals the direct sum on those members (1e-9)")

    # ---- inputs ----
    s1 = load_stage1(a.smoke)
    runs = load_agents(a.smoke)
    for r in runs:
        r["_level"] = float(r["planted_truth"]["level"])
        r["_sub"] = (r["planted_truth"].get("submitted_support_true")
                     if r.get("submitted") else None)
        # S, the in-sample realized score: planted_truth's (prior-weighted runs leave
        # submitted_sharpe empty); checked against submitted_sharpe where both exist
        r["_S"] = r["planted_truth"].get("submitted_realized")

    dS = [abs(r["_S"] - r["submitted_sharpe"]) for r in runs
          if r["_sub"] and r.get("submitted_sharpe") is not None]
    assert max(dS) < 1e-12, max(dS)

    # ---- E's code against stage 1's stored null ----
    s1_600000 = next(json.loads(ln) for ln in open(STAGE1)
                     if json.loads(ln)["seed"] == 600000)
    _, ev, _ = e_task((600000, S1_LEVELS, B_E))
    worst = 0.0
    for rec in s1_600000["levels"]:
        e = ev[float(rec["beta"])]
        worst = max(worst, abs(e["class_max"] - rec["class_max"]),
                    abs(e["null_max_mean"] - rec["null_max_mean"]),
                    abs(e["q95_all"] - rec["null_max_q"]["0.05"]))
    if worst > TOL_E:
        raise SystemExit(f"E's replicate code differs from stage 1's stored null by {worst:g} "
                         "on seed 600000; stopped before E")
    P(f"   E's replicate code on stage-1 seed 600000, four levels: class_max, null_max_mean "
      f"and q95 reproduce the stored values, max |diff| {worst:.2e}")

    # ---- panel tasks ----
    interest: dict = defaultdict(lambda: defaultdict(list))
    for r in s1:
        for rec in r["levels"]:
            lv = float(rec["beta"])
            ewi = next(x for x in rec["searchers"] if x["searcher"] == EWI)
            for sup in (ewi["support"], rec["class_argmax"], rec["pop_best"]):
                if sup:
                    interest[r["seed"]][lv].append(sup)
    for r in runs:
        pt = r["planted_truth"]
        for sup in (r["_sub"], pt["class_argmax"], pt["pop_best"]):
            if sup:
                interest[r["seed"]][r["_level"]].append(sup)
    tasks = []
    for r in s1:
        tasks.append((r["seed"], S1_LEVELS, dict(interest[r["seed"]]), norm2))
    for sd in sorted({r["seed"] for r in runs}):
        tasks.append((sd, AGENT_LEVELS, dict(interest[sd]), norm2))
    e_seeds = list(DESIGN_SEEDS)[:1] if a.smoke else list(DESIGN_SEEDS)
    B = 50 if a.smoke else B_E
    panels: dict = {}
    eres: dict = {}
    t_panel = t_e = 0.0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        fe = [ex.submit(e_task, (sd, E_LEVELS, B)) for sd in e_seeds]
        fp = [ex.submit(panel_task, t) for t in tasks]
        for f in fp:
            sd, out, secs = f.result()
            panels[sd] = out
            t_panel += secs
        for f in fe:
            sd, out, secs = f.result()
            eres[sd] = out
            t_e += secs

    # ---- check the recomputed truths ----
    worst_pop, mplus_bad, n_chk = 0.0, 0, 0
    for r in s1:
        for rec in r["levels"]:
            lv = float(rec["beta"])
            pn = panels[r["seed"]][lv]
            ewi = next(x for x in rec["searchers"] if x["searcher"] == EWI)
            pairs = [(rec["pop_best_sr"], pn["pop_mplus"])]
            if ewi["support"]:
                pairs.append((ewi["truth"]["in_sample"], pn["info"][canon(ewi["support"])]["pop"]))
            pairs.append((rec["class_argmax_truth"]["in_sample"],
                          pn["info"][canon(rec["class_argmax"])]["pop"]))
            for st, rc in pairs:
                worst_pop = max(worst_pop, abs(st - rc))
                n_chk += 1
            mplus_bad += canon(rec["pop_best"]) != canon(pn["mplus"])
    for r in runs:
        pn = panels[r["seed"]][r["_level"]]
        pt = r["planted_truth"]
        pairs = [(pt["pop_best_sr"], pn["pop_mplus"])]
        if r["_sub"]:
            pairs.append((pt["submitted_truth"]["in_sample"], pn["info"][canon(r["_sub"])]["pop"]))
        for st, rc in pairs:
            worst_pop = max(worst_pop, abs(st - rc))
            n_chk += 1
        mplus_bad += canon(pt["pop_best"]) != canon(pn["mplus"])
    if worst_pop > TOL_POP:
        raise SystemExit(f"recomputed SR_pop differs from the stored by {worst_pop:g}")
    P(f"   S = planted_truth.submitted_realized; equals submitted_sharpe on the {len(dS)} runs "
      f"that store both (max |diff| {max(dS):.1e})")
    P(f"   recomputed SR_pop against {n_chk} stored values: max |diff| {worst_pop:.2e}; "
      f"m+ differs from the stored pop_best on {mplus_bad} panel-rows")
    P("")

    def pn_of(seed, lv):
        return panels[seed][lv]

    # ---- rows: one per (source, level) submission ----
    # stage 1: sources "S1 extend-while-improving" and "S1 class argmax"
    S1_SRC = S1_SRC_NAMES
    rows = []          # dict(source, level, seed, sub, reg2of3, reg2of3_plus, ...)
    for r in s1:
        for rec in r["levels"]:
            lv = float(rec["beta"])
            ewi = next(x for x in rec["searchers"] if x["searcher"] == EWI)
            for src, sup, rcv in ((S1_SRC[0], ewi["support"],
                                   {k: ewi[k] for k in ("two_of_three", "two_of_three_pop_best")}),
                                  (S1_SRC[1], rec["class_argmax"],
                                   rec["class_argmax_recovery"])):
                rows.append({"source": src, "level": lv, "seed": r["seed"], "sub": sup,
                             "argmax": rec["class_argmax"], "mstar": rec["planted"],
                             "r2": rcv["two_of_three"], "r2p": rcv["two_of_three_pop_best"]})
    for r in runs:
        pt = r["planted_truth"]
        rows.append({"source": r["arm"], "level": r["_level"], "seed": r["seed"],
                     "sub": r["_sub"], "argmax": pt["class_argmax"], "mstar": pt["planted"],
                     "r2": pt["submitted_recovery"]["two_of_three"] if r["_sub"] else None,
                     "r2p": pt["submitted_recovery"]["two_of_three_pop_best"] if r["_sub"] else None,
                     "run": r})
    SOURCES = S1_SRC + ARMS
    no_sub = Counter((x["source"], x["level"]) for x in rows if not x["sub"])

    def groups():
        for src in SOURCES:
            lvls = S1_LEVELS if src in S1_SRC else AGENT_LEVELS
            for lv in lvls:
                g = [x for x in rows if x["source"] == src and x["level"] == lv and x["sub"]]
                if g or no_sub.get((src, lv)):
                    yield src, lv, g

    P("Rows: stage 1 = 200 panels per level, one row per source; agents = runs with a "
      "submission (without: " + (", ".join(f"{s} {lvl(l)}: {n}" for (s, l), n in
                                           sorted(no_sub.items())) or "none") + ")")
    P("")

    # ---- A1 ----
    P("A1 — EDGE CAPTURE: SR_pop(x) / SR_pop(m+)   (level 0: m+ negative, ratio not a capture)")
    P("-" * 96)
    for src, lv, g in groups():
        def cap(sup, x):
            pn = pn_of(x["seed"], lv)
            return pn["info"][canon(sup)]["pop"] / pn["pop_mplus"]
        tag = "  [level 0: not a capture]" if lv == 0 else ""
        P(f"   {src:<28} {lvl(lv)}  submission           {qs([cap(x['sub'], x) for x in g])}{tag}")
        if src not in S1_SRC:
            for hit in (True, False):
                gg = [x for x in g if x["r2p"] is hit]
                P(f"   {'':<28} {lvl(lv)}    2-of-3 vs m+ {'hit ' if hit else 'miss'}  "
                  f"{qs([cap(x['sub'], x) for x in gg])}")
    P("   per panel (once per seed and level):")
    for name, seeds, lvls in (("stage 1 panels", [r["seed"] for r in s1], S1_LEVELS),
                              ("agent panels", sorted({r["seed"] for r in runs}), AGENT_LEVELS)):
        for lv in lvls:
            am, ms = [], []
            for sd in seeds:
                pn = pn_of(sd, lv)
                src_rows = [x for x in rows if x["seed"] == sd and x["level"] == lv]
                if not src_rows:
                    continue
                am.append(pn["info"][canon(src_rows[0]["argmax"])]["pop"] / pn["pop_mplus"])
                ms.append(pn["info"][canon(pn["mstar"])]["pop"] / pn["pop_mplus"])
            tag = "  [level 0: not a capture]" if lv == 0 else ""
            P(f"   {name:<28} {lvl(lv)}  realized class argmax {qs(am)}{tag}")
            P(f"   {'':<28} {lvl(lv)}  m*                    {qs(ms)}{tag}")
    P("")

    # ---- A2 ----
    P("A2 — POSITION OVERLAP: weight-path correlation with m* and with m+, by signed "
      "features shared")
    P("-" * 96)
    corr_star: dict = {}

    def cstar(sup, mstar):
        k = (canon(sup), canon(mstar))
        if k not in corr_star:
            corr_star[k] = pair_corr(sup, mstar)
        return corr_star[k]

    def shared(a_, b_):
        return len(set(canon(a_)) & set(canon(b_)))

    for src, lv, g in groups():
        for ref in ("m*", "m+"):
            for k in range(4):
                vals = []
                for x in g:
                    pn = pn_of(x["seed"], lv)
                    refsup = x["mstar"] if ref == "m*" else pn["mplus"]
                    if shared(x["sub"], refsup) != k:
                        continue
                    vals.append(cstar(x["sub"], refsup) if ref == "m*"
                                else pn["info"][canon(x["sub"])]["corr_mplus"])
                P(f"   {src:<28} {lvl(lv)}  vs {ref}  shared {k}  {qs(vals)}")
    P("")

    # ---- A3 ----
    P("A3 — FEATURE FAMILIES: 40 x 40 weight-path correlations of single-feature members "
      "(panel-independent)")
    P("-" * 96)
    singles = [((k, 1.0),) for k in range(K)]
    Cm = np.empty((K, K))
    for i in range(K):
        Cm[i] = [pair_corr(singles[i], singles[j]) if j >= i else Cm[j, i] for j in range(K)]
    P("        " + "".join(f"{j:>5d}" for j in range(K)))
    for i in range(K):
        P(f"   {i:>3d}  " + "".join(f"{Cm[i, j]:>5.2f}"[-5:] for j in range(K)))
    off = Cm[np.triu_indices(K, 1)]
    P(f"   off-diagonal |corr|: {qs(np.abs(off))}; max {np.abs(off).max():.3f}")

    def families(tau):
        lab = list(range(K))

        def find(i):
            while lab[i] != i:
                lab[i] = lab[lab[i]]
                i = lab[i]
            return i
        for i in range(K):
            for j in range(i + 1, K):
                if abs(Cm[i, j]) >= tau:
                    lab[find(i)] = find(j)
        fam = [find(i) for i in range(K)]
        return fam

    fams = {t: families(t) for t in TAUS}
    for t in TAUS:
        groups_t = defaultdict(list)
        for i, f in enumerate(fams[t]):
            groups_t[f].append(i)
        multi = sorted([v for v in groups_t.values() if len(v) > 1], key=lambda v: v[0])
        P(f"   tau {t:.1f}{' (primary)' if t == 0.8 else ''}: {len(groups_t)} families; "
          f"multi-feature: " + ("; ".join("{" + ",".join(map(str, v)) + "}" for v in multi)
                                or "none"))

    def fam_hit(sub, mstar, tau):
        fam = fams[tau]
        S = list(canon(sub))
        M = list(canon(mstar))

        def match(a_, b_):
            (k, s), (j, t) = a_, b_
            return fam[k] == fam[j] and s * t * np.sign(Cm[k, j]) > 0
        return family_matching(S, M, match) >= 2

    P("   recovery against m*: registered two-of-three, beside family-level two-of-three")
    for src, lv, g in groups():
        reg = [bool(x["r2"]) for x in g]
        fam_s = "  ".join(f"tau {t:.1f} {share([fam_hit(x['sub'], x['mstar'], t) for x in g])}"
                          for t in TAUS)
        P(f"   {src:<28} {lvl(lv)}  registered {share(reg)}   {fam_s}")
    P("")

    # ---- B1 ----
    P("B1 — IDENTIFIABILITY: members near m+ (S_d: SR_pop >= SR_pop(m+) - d; R_r: "
      "weight-path corr with m+ >= r; each includes m+)")
    P("-" * 96)
    SETS = [f"S{d:.2f}" for d in DELTAS] + [f"R{r:.1f}" for r in RHOS]
    for name, seeds, lvls in (("stage 1 panels", [r["seed"] for r in s1], S1_LEVELS),
                              ("agent panels", sorted({r["seed"] for r in runs}), AGENT_LEVELS)):
        for lv in lvls:
            for st in SETS:
                sizes = [pn_of(sd, lv)["sizes"][st] for sd in seeds]
                ms = [pn_of(sd, lv)["info"][canon(pn_of(sd, lv)["mstar"])]["in"][st]
                      for sd in seeds]
                P(f"   {name:<16} {lvl(lv)}  {st:<6} size {qsi(sizes)}   m* in it {share(ms)}")
    P("   submissions in each set:")
    for src, lv, g in groups():
        parts = []
        for st in SETS:
            parts.append(f"{st} " + share([pn_of(x['seed'], lv)['info'][canon(x['sub'])]['in'][st]
                                           for x in g]))
        P(f"   {src:<28} {lvl(lv)}  " + "  ".join(parts))
    P("")

    # ---- B2 ----
    P("B2 — SHORTFALL: noise = SR_pop(m+) - SR_pop(realized argmax); search = "
      "SR_pop(realized argmax) - SR_pop(submission)")
    P("-" * 96)
    for src, lv, g in groups():
        nz, sr = [], []
        for x in g:
            pn = pn_of(x["seed"], lv)
            pa = pn["info"][canon(x["argmax"])]["pop"]
            nz.append(pn["pop_mplus"] - pa)
            sr.append(pa - pn["info"][canon(x["sub"])]["pop"])
        P(f"   {src:<28} {lvl(lv)}  noise  {qs(nz)}  mean {np.mean(nz):+.3f}")
        P(f"   {'':<28} {lvl(lv)}  search {qs(sr)}  mean {np.mean(sr):+.3f}")
    P("")

    # ---- agent-only quantities ----
    def truth_of(r):
        return pn_of(r["seed"], r["_level"])["info"][canon(r["_sub"])]["pop"]

    def pred(r):
        p = r.get("prediction") or {}
        return p.get("mean"), p.get("sd")

    sub_runs = [r for r in runs if r["_sub"]]

    def by_arm_level():
        for arm in ARMS:
            for lv in AGENT_LEVELS + (None,):
                g = [r for r in sub_runs if r["arm"] == arm and (lv is None or r["_level"] == lv)]
                if g:
                    yield arm, lv, g

    # ---- C1 ----
    P("C1 — STATED MEAN mu against the in-sample realized score S, and against truth "
      "(agents; 'all' = pooled over levels)")
    P("-" * 96)
    for arm, lv, g in by_arm_level():
        g = [r for r in g if pred(r)[0] is not None]
        mu = np.array([pred(r)[0] for r in g], float)
        S = np.array([r["_S"] for r in g], float)
        tr = np.array([truth_of(r) for r in g], float)
        a0, b0 = lsq(S, mu)
        _, bt = lsq(tr, mu)
        P(f"   {arm:<28} {lvl(lv) if lv is not None else 'all'}  mu/S {qs(mu / S)}   "
          f"mu = {a0:+.3f} + {b0:+.3f} S   slope on truth {bt:+.3f}")
    P("")

    # ---- C2 ----
    def ngeq_from_curve(conf):
        B_ = int(conf["B"])
        if "n_ge" in conf:
            return np.asarray(conf["n_ge"], float), B_
        Cc = np.asarray(conf["curve"], float)
        return np.round((1 - Cc) * (B_ + 1) - 1), B_

    def replay_mean(conf, S):
        nge, B_ = ngeq_from_curve(conf)
        x = S - cf.GRID
        tot = nge[0] * x[0]
        tot += ((nge[1:] - nge[:-1]) * (x[1:] + x[:-1]) / 2).sum()
        tot += (B_ - nge[-1]) * x[-1]
        ends = bool(nge[0] > 0 or B_ - nge[-1] > 0)
        return tot / B_, ends

    P("C2 — ESTIMATES OF THE TRUE SHARPE: error = estimate - target; E0 = S, E1 = S - mean(replay "
      "null), E2 = S - mean(class null), E3 = mu")
    P("-" * 96)
    P("   class-null mean: stored null_max_mean (exact). Replay-null mean: from the stored "
      "curve (agents: verdict.confidence.curve,")
    P("   n_ge = round((1-C)(B+1)-1); V2: conf_replay.n_ge), replicates between grid points at "
      "the midpoint (<= 0.025 each),")
    P("   at or above S+1 at S+1, below S-3 at S-3. E1 only where the verdict carries "
      "replay-tier confidence.")
    ends_n = 0
    for arm, lv, g in by_arm_level():
        if lv is None:
            continue
        S = np.array([r["_S"] for r in g], float)
        tin = np.array([truth_of(r) for r in g], float)
        tho = np.array([r["planted_truth"]["submitted_truth"]["holdout"] for r in g], float)
        e2 = S - np.array([r["class_p"]["null_max_mean"] for r in g], float)
        gm = [(i, r) for i, r in enumerate(g) if pred(r)[0] is not None]
        sub = [(i, r) for i, r in enumerate(g)
               if (r.get("verdict") or {}).get("confidence")]
        e1 = []
        for i, r in sub:
            m, ends = replay_mean(r["verdict"]["confidence"], S[i])
            e1.append(S[i] - m)
            ends_n += ends
        ix = [i for i, _ in sub]
        im = [i for i, _ in gm]
        e3 = np.array([pred(r)[0] for _, r in gm], float)
        for tname, tg in (("truth", tin), ("holdout SR_pop", tho)):
            P(f"   {arm:<28} {lvl(lv)}  vs {tname:<15} E0 {errs(S, tg)}")
            P(f"   {'':<28} {'':3}     {'':<15} E2 {errs(e2, tg)}")
            P(f"   {'':<28} {'':3}     {'':<15} E3 {errs(e3, tg[im])}")
            P(f"   {'':<28} {'':3}     {'':<15} E1 {errs(e1, tg[ix])}   (replay subset)")
            P(f"   {'':<28} {'':3}     {'':<15} E0 {errs(S[ix], tg[ix])}   (E0 on the replay subset)")
    v2rows = defaultdict(lambda: defaultdict(list))
    v2_lines = open(V2).read().splitlines()
    if a.smoke:
        v2_lines = v2_lines[:2]
    for ln in v2_lines:
        r = json.loads(ln)
        for rec in r["levels"]:
            lv = float(rec["beta"])
            for x in rec["searchers"]:
                if not x["support"]:
                    continue
                m, ends = replay_mean(x["conf_replay"], x["score"])
                ends_n += ends
                v2rows[x["searcher"]][lv].append(
                    (x["score"], x["score"] - m, x["score"] - rec["null_max_mean"],
                     x["truth"]["in_sample"], x["truth"]["holdout"]))
    for srch in v2rows:
        for lv in sorted(v2rows[srch]):
            A = np.array(v2rows[srch][lv], float)
            for tname, col in (("truth", 3), ("holdout SR_pop", 4)):
                P(f"   V2 {srch:<25} {lvl(lv)}  vs {tname:<15} E0 {errs(A[:, 0], A[:, col])}")
                P(f"   {'':<28} {'':3}     {'':<15} E1 {errs(A[:, 1], A[:, col])}")
                P(f"   {'':<28} {'':3}     {'':<15} E2 {errs(A[:, 2], A[:, col])}")
    P(f"   rows with replay-null mass at either end of the grid (approximation clipped): {ends_n}")
    P("   (V2 truths are the stored ones; agent truths recomputed and checked above)")
    P("")

    # ---- C3 ----
    G_ = cf.GRID

    def crps_normal(mu, sd, y):
        z = (y - mu) / sd
        return sd * (z * (2 * N01.cdf(z) - 1) + 2 * N01.pdf(z) - 1 / np.sqrt(np.pi))

    def crps_disc(curve, y):
        m = cf.masses(np.asarray(curve, float))
        return float((m * np.abs(G_ - y)).sum()
                     - 0.5 * (m[:, None] * m[None, :] * np.abs(G_[:, None] - G_[None, :])).sum())

    P("C3 — CRPS (lower is better): agent normal(mu, sd) beside the gate's curve read as a "
      "distribution on the grid")
    P("-" * 96)
    sd_bad = 0
    for arm, lv, g in by_arm_level():
        if lv is None:
            continue
        for tname, tget in (("truth", truth_of),
                            ("realized holdout", lambda r: r["planted_truth"]["submitted_holdout_realized"])):
            ag = [crps_normal(*pred(r), tget(r)) for r in g
                  if pred(r)[0] is not None and (pred(r)[1] or 0) > 0]
            cl = [crps_disc(r["class_p"]["confidence"]["curve"], tget(r)) for r in g]
            rp_runs = [r for r in g if (r.get("verdict") or {}).get("confidence")]
            rp = [crps_disc(r["verdict"]["confidence"]["curve"], tget(r)) for r in rp_runs]
            ag_rp = [crps_normal(*pred(r), tget(r)) for r in rp_runs
                     if pred(r)[0] is not None and (pred(r)[1] or 0) > 0]
            P(f"   {arm:<28} {lvl(lv)}  vs {tname:<16} agent  {qs(ag)}  mean {np.mean(ag):.3f}")
            P(f"   {'':<28} {'':3}     {'':<16} class  {qs(cl)}  mean {np.mean(cl):.3f}")
            if rp:
                P(f"   {'':<28} {'':3}     {'':<16} replay {qs(rp)}  mean {np.mean(rp):.3f}"
                  f"   agent on that subset mean {np.mean(ag_rp):.3f} (n {len(ag_rp)})")
            else:
                P(f"   {'':<28} {'':3}     {'':<16} replay n 0")
        sd_bad += sum(1 for r in g if pred(r)[0] is not None and not (pred(r)[1] or 0) > 0)
    P(f"   runs excluded for sd <= 0: {sd_bad}")
    P("")

    # ---- D1 ----
    P("D1 — TRIGGER CHANGES (from each run's trigger_changes event; loosened = fires on "
      "fewer states)")
    P("-" * 96)
    LOOSE_UP = {"best_so_far_above": True, "failures_at_least": True, "last_gain_at_most": False}
    for arm in ARMS:
        for lv in AGENT_LEVELS:
            g = [r for r in runs if r["arm"] == arm and r["_level"] == lv]
            if not g:
                continue
            n_ch, first, steps, kinds = 0, [], [], Counter()
            flag_no_event = 0
            for r in g:
                ev = [e for e in r["events"] if e["kind"] == "trigger_changes"]
                ch = ev[0]["changes"] if ev else []
                if r.get("triggers_changed") and not ch:
                    flag_no_event += 1
                if not ch:
                    continue
                n_ch += 1
                state = {t["kind"]: t for t in (r.get("triggers_predeclared") or [])}
                first.append(ch[0]["at_step"])
                for c in ch:
                    t = c["trigger"]
                    steps.append(c["at_step"])
                    prev = state.get(t["kind"])
                    if prev is None:
                        d = "new"
                    else:
                        p0, p1 = float(prev["param"]), float(t["param"])
                        pdir = "up" if p1 > p0 else "down" if p1 < p0 else "same"
                        act = "same action" if prev["action"] == t["action"] else \
                            f"action {prev['action']}->{t['action']}"
                        if pdir == "same" or t["kind"] not in LOOSE_UP:
                            lt = "-"
                        else:
                            lt = "loosened" if (pdir == "up") == LOOSE_UP[t["kind"]] else "tightened"
                        d = f"param {pdir}, {act}, {lt}"
                    kinds[(t["kind"], d)] += 1
                    state[t["kind"]] = t
            P(f"   {arm:<28} {lvl(lv)}  runs changing {n_ch}/{len(g)}; changes {len(steps)}"
              + (f"; flagged without an event {flag_no_event}" if flag_no_event else ""))
            if n_ch:
                P(f"   {'':<28} {'':3}  first change at_step {qs(first)}")
                P(f"   {'':<28} {'':3}  every change at_step {qs(steps)}")
                for (k, d), n in sorted(kinds.items()):
                    P(f"   {'':<28} {'':3}    {n:3d}  {k}: {d}")
    P("")

    # ---- D2 ----
    P("D2 — STOP FIDELITY per level (agreement = answer == predicted)")
    P("-" * 96)
    pres = [json.loads(ln) for ln in open(FIDELITY)]
    stops = [p for p in pres if p["kind"] == "stop"]
    tot_ag = sum(1 for p in stops if p["answer"] is not None and p["answer"] == p["predicted"])
    if not a.smoke:
        assert (tot_ag, len(stops)) == (335, 580), (tot_ag, len(stops))
    for lv in sorted({float(p["level"]) for p in stops}):
        g = [p for p in stops if float(p["level"]) == lv]
        ag = sum(1 for p in g if p["answer"] is not None and p["answer"] == p["predicted"])
        dec = len({(p["run_id"], p["step"]) for p in g})
        pairs = Counter((p["predicted"], p["answer"]) for p in g
                        if not (p["answer"] is not None and p["answer"] == p["predicted"]))
        P(f"   level {lvl(lv)}: agreed {ag}/{len(g)} = {ag / len(g):.3f}; decisions {dec}")
        lab = {("stop", "continue"): "continued where the rule said stop",
               ("stop", "restart"): "restarted where the rule said stop",
               ("continue", "stop"): "stopped where the rule said continue"}
        for (pr, an), n in sorted(pairs.items(), key=lambda kv: -kv[1]):
            P(f"      {n:4d}  {lab.get((pr, an), f'predicted {pr}, answered {an}')}")
    P(f"   total: agreed {tot_ag}/{len(stops)} (fidelity_read: 335/580)")
    P("")

    # ---- E ----
    P(f"E — CONSERVATISM OF THE CLASS NULL, seeds 640100-640149, B = {B}. "
      "PREVIEW, NO VALIDITY CLAIM")
    P("-" * 96)
    P("   SE = sqrt((1 + SR_p^2/2)/T) * sqrt(ppy), SR_p = obs/sqrt(ppy), T = 3019 (Lo 2002, "
      "i.i.d.)")
    for lv in E_LEVELS:
        e = [eres[sd][lv] for sd in e_seeds]
        P(f"   level {lvl(lv)}  E1 share obs < -1 SE   {qs([x['share_1se'] for x in e])}")
        P(f"              E1 share obs < -2 SE   {qs([x['share_2se'] for x in e])}")
        P(f"              E2 q95 null max, all members            {qs([x['q95_all'] for x in e])}")
        P(f"              E2 q95 null max, obs >= -2 SE only      {qs([x['q95_sub'] for x in e])}")
        P(f"              E2 difference (all - restricted)        "
          f"{qs([x['q95_all'] - x['q95_sub'] for x in e])}")
        P(f"              restricted set size                     {qsi([x['n_sub'] for x in e])}")
    P("")
    P(f"wall {time.time() - T0:.0f} s (panel tasks {t_panel:.0f} CPU-s, E tasks {t_e:.0f} CPU-s); "
      "laptop on battery in Low Power Mode, not a cost measurement")
    text = "\n".join(L)
    if a.smoke:
        print(f"smoke ok: {len(L)} lines built, none printed; wall {time.time() - T0:.0f} s, "
              f"panel {t_panel:.0f} CPU-s ({len(tasks)} tasks), E {t_e:.0f} CPU-s "
              f"({len(e_seeds)} seed, B {B})")
        return 0
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
