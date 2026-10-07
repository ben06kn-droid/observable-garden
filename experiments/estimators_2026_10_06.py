"""Estimators and selection stability, 2026-10-06. EXPLORATORY
(`prereg/estimators-exploratory-2026-10-06.md`).

Design seeds 640150-640249, levels 0, 0.5, 1.0, 1.5, fast kernel, pinned X. One pass
per panel and level gives every member's realized Sharpe S(m), the registered centred
class null (its maximum M_b) and the un-demeaned replicate Sharpes S*_b(m), from the
null's own index draws. Hypothesis-generating; changes no recorded result.

    python -m experiments.estimators_2026_10_06 --out runs/diagnostics/estimators_2026-10-06.txt
    python -m experiments.estimators_2026_10_06 --smoke     # code paths only, no tables
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from experiments import diagnostics_2026_10_06 as dg

SEEDS = range(640150, 640250)
LEVELS = (0.0, 0.5, 1.0, 1.5)
B = 1000
EWI = "extend-while-improving"
ESTS = ("E0", "E2", "EH", "EC", "EB", "EBs")
TAU = 0.8


def level_pass(base, cache, D, inv, seed, d, F0, G, pop, B_, fams):
    """Everything for one (seed, level): returns a small dict."""
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    from experiments.planted_edge import _searchers
    panel = d.in_sample
    T = panel.features.shape[0]
    ppy = float(panel.periods_per_year)
    ann = float(np.sqrt(ppy))
    N = cache.N
    bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(seed)
    C = np.empty((T, B_))
    for b in range(B_):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    F = F0 + d.c * G
    obs = np.empty(N)
    Sstar = np.empty((N, B_), dtype=np.float32)
    M_all = np.full(B_, -np.inf)
    best_val = np.full(B_, -np.inf)
    best_idx = np.zeros(B_, dtype=np.int64)
    for s in range(0, N, CHUNK):
        X = pf.streams(cache, F, s, min(s + CHUNK, N))
        n = len(X)
        obs[s:s + n] = pf._sharpe_rows(X, ann)
        mu = X.mean(axis=1, keepdims=True)
        X0 = X - mu
        A = X0 @ C                                    # the kernel's two products
        Q2 = (X0 * X0) @ C
        mean0 = A / T
        var0 = (Q2 - T * mean0 * mean0) / (T - 1)
        pos = var0 > 0
        rep0 = np.where(pos, mean0 / np.sqrt(np.where(pos, var0, 1.0)), 0.0) * ann
        M_all = np.maximum(M_all, rep0.max(axis=0))
        # un-demeaned: X = X0 + mu, so X@C = A + mu*T and X^2@C = Q2 + 2 mu A + mu^2 T
        XC = A + mu * T
        X2C = Q2 + 2 * mu * A + mu * mu * T
        meanr = XC / T
        varr = (X2C - T * meanr * meanr) / (T - 1)
        posr = varr > 0
        repr_ = np.where(posr, meanr / np.sqrt(np.where(posr, varr, 1.0)), 0.0) * ann
        Sstar[s:s + n] = repr_
        j = repr_.argmax(axis=0)
        v = repr_[j, np.arange(B_)]
        upd = v > best_val
        best_val[upd] = v[upd]
        best_idx[upd] = s + j[upd]
    members = cache.members
    index = cache.index
    K = panel.features.shape[2]
    single_ix = [index[dg.canon(((k, 1.0),))] for k in range(K)]
    srch = next(x for x in _searchers(seed, T, panel.periods_per_year) if x.name == EWI)
    tr = srch._search(K, lambda k: float(obs[single_ix[k]]),
                      lambda sup: float(obs[index[dg.canon(sup)]]))
    ewi_sup, ewi_S, ewi_n = tuple(tr.support), float(tr.score), tr.n_moves
    bs = np.empty(B_)
    for b in range(B_):
        col = Sstar[:, b]
        t2 = srch._search(K, lambda k, col=col: float(col[single_ix[k]]),
                          lambda sup, col=col: float(col[index[dg.canon(sup)]]),
                          meta_steps=ewi_n)
        ib = index[dg.canon(t2.support)]
        bs[b] = float(col[ib]) - obs[ib]
    j = int(np.argmax(obs))
    argmax_sup = members[j]
    meanM = float(M_all.mean())
    bias_B = float(np.mean(best_val - obs[best_idx]))
    bias_Bs = float(bs.mean())

    def ests(S, with_s):
        p = (1 + int(np.sum(M_all >= S))) / (B_ + 1)
        e = {"E0": S, "E2": S - meanM, "EH": 0.5 * S, "EC": S - p * meanM,
             "EB": S - bias_B}
        if with_s:
            e["EBs"] = S - bias_Bs
        return e, p

    jp = int(np.argmax(pop))
    mstar = dg.canon(d.m_star)
    f = np.bincount(best_idx, minlength=N) / B_
    order = np.lexsort((np.arange(N), -f))
    cum = np.cumsum(f[order])
    k90 = int(np.searchsorted(cum, 0.90 - 1e-12) + 1)
    set90 = set(order[:k90].tolist())
    # denoised: highest f, ties to higher realized S, then lower index
    fmax = f.max()
    cand = np.flatnonzero(f == fmax)
    dn = int(cand[np.lexsort((cand, -obs[cand]))[0]])
    # feature and family shares over replicates
    feat = np.zeros(K)
    nfam = max(fams) + 1
    fam = np.zeros(nfam)
    uniq, cnt = np.unique(best_idx, return_counts=True)
    for u, c in zip(uniq, cnt):
        ks = {int(k) for k, _ in members[u]}
        for k in ks:
            feat[k] += c
        for fm in {fams[k] for k in ks}:
            fam[fm] += c
    feat /= B_
    fam /= B_
    star_feats = [int(k) for k, _ in mstar]
    star_fams = sorted({fams[k] for k in star_feats})
    fam_rank = sorted(range(nfam), key=lambda x: (-fam[x], x))
    topk = set(fam_rank[:len(star_fams)])
    top3 = set(fam_rank[:3])

    def ho(sup):
        return float(pp.truth(base, d, sup)["holdout"])

    e_am, p_am = ests(float(obs[j]), False)
    e_ew, p_ew = ests(ewi_S, True)
    return {"level": float(d.beta), "L": L,
            "argmax": {"S": float(obs[j]), "p": p_am, "est": e_am,
                       "in": float(pop[j]), "ho": ho(argmax_sup)},
            "ewi": {"S": ewi_S, "p": p_ew, "est": e_ew, "n": ewi_n,
                    "sup": [list(x) for x in dg.canon(ewi_sup)],
                    "in": float(pop[index[dg.canon(ewi_sup)]]), "ho": ho(ewi_sup)},
            "meanM": meanM, "bias_B": bias_B, "bias_Bs": bias_Bs,
            "pop_mplus": float(pop[jp]), "pop_mstar": float(pop[index[mstar]]),
            "set90": k90, "set90_mplus": jp in set90, "set90_mstar": index[mstar] in set90,
            "f_max": float(fmax), "f_mplus": float(f[jp]), "f_mstar": float(f[index[mstar]]),
            "dn_pop": float(pop[dn]), "dn_is_argmax": dn == j, "dn_is_mplus": dn == jp,
            "star_feat_share": [float(feat[k]) for k in star_feats],
            "star_fam_share": [float(fam[x]) for x in star_fams],
            "star_fams_topk": set(star_fams) == topk,
            "star_fams_in_top3": set(star_fams) <= top3, "n_star_fams": len(star_fams),
            "class_max": float(obs[j])}


def seed_task(args):
    seed, levels, B_, fams = args
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    W = dg._init()
    base, cache, D, inv = W["base"], W["cache"], W["D"], W["inv"]
    t0 = time.time()
    draws = [pp.make_draw(base, seed, lv) for lv in levels]
    for d in draws:
        dg._same_features(base, d)
    E = base.E_is[draws[0].idx_is]
    F0 = np.einsum("tmk,tm->tk", D, E)
    G = np.einsum("tmk,tm->tk", D, draws[0].w_star_is)
    N = cache.N
    Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    for s in range(0, N, CHUNK):
        a = pf.overlap(cache, G, s, min(s + CHUNK, N))
        k = np.asarray(cache.k[s:s + len(a)])
        Ea[s:s + len(a)] = a.mean(axis=1)
        Ea2[s:s + len(a)] = (a * a).mean(axis=1)
        Eak[s:s + len(a)] = (a * k).mean(axis=1)
    ppy = draws[0].in_sample.periods_per_year
    out = []
    for d in draws:
        pop = pp.population_from_moments(Ea, Ea2, Eak, inv, d.c, ppy)
        out.append(level_pass(base, cache, D, inv, seed, d, F0, G, pop, B_, fams))
    return seed, out, time.time() - t0


def power_ok() -> tuple[bool, str]:
    batt = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    lpm = subprocess.run(["pmset", "-g"], capture_output=True, text=True).stdout
    ac = "AC Power" in batt.splitlines()[0]
    low = any(ln.split()[:2] == ["lowpowermode", "1"] for ln in lpm.splitlines())
    return ac and not low, f"{batt.splitlines()[0].strip()}; lowpowermode {int(low)}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--dump", default=None,
                    help="also write one JSON line per (seed, level, submission); added "
                         "after b2e3a40 for the conditional tabulation (addendum 8c933a3). "
                         "The text tables are unchanged by it")
    a = ap.parse_args(argv)
    ok, pw = power_ok()
    if not a.smoke:
        if not a.out:
            raise SystemExit("--out is required")
        if not ok:
            raise SystemExit(f"power: {pw}. The run needs mains and Low Power Mode off.")
    for v in ("OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[v] = "1"
    T0 = time.time()
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    K = 40
    singles = [((k, 1.0),) for k in range(K)]
    Cm = np.empty((K, K))
    for i in range(K):
        Cm[i] = [dg.pair_corr(singles[i], singles[j]) if j >= i else Cm[j, i] for j in range(K)]
    Dm = np.clip(1 - np.abs(Cm), 0, None)
    np.fill_diagonal(Dm, 0)
    lab = fcluster(linkage(squareform(Dm, checks=False), method="complete"),
                   t=1 - TAU, criterion="distance")
    fams = [int(x) - 1 for x in lab]
    for i in range(K):                 # complete linkage: every pair inside >= tau
        for j in range(K):
            if fams[i] == fams[j]:
                assert abs(Cm[i, j]) >= TAU - 1e-12

    # check: the centred null and extend-while-improving reproduce stage 1 on 600000
    rec0 = next(json.loads(ln) for ln in open(dg.STAGE1) if json.loads(ln)["seed"] == 600000)
    _, chk, _ = seed_task((600000, (0.0, 0.5, 1.0, 1.5), B, fams))
    worst, ewi_bad = 0.0, 0
    for r, c in zip(rec0["levels"], chk):
        worst = max(worst, abs(r["class_max"] - c["class_max"]),
                    abs(r["null_max_mean"] - c["meanM"]))
        ew = next(x for x in r["searchers"] if x["searcher"] == EWI)
        ewi_bad += (ew["support"] != c["ewi"]["sup"]) or abs(ew["score"] - c["ewi"]["S"]) > 1e-12
        ewi_bad += abs(ew["truth"]["in_sample"] - c["ewi"]["in"]) > 1e-9
    if worst > 1e-9 or ewi_bad:
        raise SystemExit(f"check failed on 600000: null max |diff| {worst:g}, EWI mismatches {ewi_bad}")

    seeds = list(SEEDS)[:1] if a.smoke else list(SEEDS)
    B_ = 50 if a.smoke else B
    res = {}
    cpu = 0.0
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        for sd, out, secs in ex.map(seed_task, [(s, LEVELS, B_, fams) for s in seeds]):
            res[sd] = out
            cpu += secs

    L: list[str] = []
    P = L.append
    P("Estimators and selection stability, 2026-10-06 — EXPLORATORY "
      "(prereg/estimators-exploratory-2026-10-06.md)")
    P("=" * 96)
    P(f"  design seeds 640150-640249 ({len(seeds)}), levels 0/0.5/1.0/1.5, B = {B_}, fast kernel "
      f"(cache {dg.CACHE_KEY}), pinned X")
    P(f"  power at launch: {pw}")
    P("")
    P("CHECKS")
    P("-" * 96)
    P(f"   stage-1 seed 600000, four levels: class max and centred null mean reproduce the stored "
      f"values (max |diff| {worst:.1e});")
    P("   extend-while-improving's support, score and in-sample SR_pop reproduce the stored ones")
    P(f"   complete-linkage families at tau {TAU}: every pair inside has |corr| >= {TAU} (asserted)")
    groups: dict = {}
    for i, f_ in enumerate(fams):
        groups.setdefault(f_, []).append(i)
    P(f"   {len(groups)} families; multi-feature: " + "; ".join(
        "{" + ",".join(map(str, v)) + "}" for v in sorted(groups.values()) if len(v) > 1))
    P("   check 0 (registered agent prompts): nothing suggesting halving, a haircut or a default "
      "discount (see the note)")
    P("")

    rows = [r for sd in seeds for r in res[sd]]

    def errline(est, tgt):
        e = np.asarray(est, float) - np.asarray(tgt, float)
        return (f"bias {e.mean():+.3f}  MAE {np.abs(e).mean():.3f}  RMSE {np.sqrt((e * e).mean()):.3f}"
                f"  n {e.size}")

    def rmse(est, tgt):
        e = np.asarray(est, float) - np.asarray(tgt, float)
        return float(np.sqrt((e * e).mean()))

    P("2 — POINT ESTIMATES (error = estimate - target)")
    P("-" * 96)
    P("   bias terms: mean class-null max " + dg.qs([r["meanM"] for r in rows]) +
      "\n   EB bias (class argmax on S*)   " + dg.qs([r["bias_B"] for r in rows]) +
      "\n   EBs bias (EWI replay on S*)    " + dg.qs([r["bias_Bs"] for r in rows]))
    best_lines = []
    for sub, name, ests in (("argmax", "realized class argmax", ESTS[:-1]),
                            ("ewi", "extend-while-improving", ESTS)):
        for tgt, tname in (("in", "in-sample SR_pop"), ("ho", "holdout SR_pop")):
            P(f"   {name} — vs {tname}")
            for lv in LEVELS + (None,):
                g = [r for r in rows if lv is None or r["level"] == lv]
                lab_ = dg.lvl(lv) if lv is not None else "all"
                rm = {}
                for e in ests:
                    est = [r[sub]["est"][e] for r in g]
                    tg = [r[sub][tgt] for r in g]
                    rm[e] = rmse(est, tg)
                    P(f"      {lab_:>3}  {e:<3}  {errline(est, tg)}")
                win = min(rm, key=rm.get)
                P(f"      {lab_:>3}  lowest RMSE: {win} ({rm[win]:.3f})")
                best_lines.append((sub, tgt, lv, win, rm))
    P("   lowest RMSE, in-sample target:")
    for sub, tgt, lv, win, rm in best_lines:
        if tgt == "in":
            P(f"      {sub:<7} {dg.lvl(lv) if lv is not None else 'all':>3}  {win:<3}  "
              + "  ".join(f"{e} {v:.3f}" for e, v in rm.items()))
    P("   strictly lower RMSE than both E0 and E2 at all four levels (in-sample target):")
    for sub in ("argmax", "ewi"):
        lv_rm = {lv: rm for s, t, lv, w, rm in best_lines if s == sub and t == "in" and lv is not None}
        beats = [e for e in lv_rm[0.0] if e not in ("E0", "E2")
                 and all(rm[e] < rm["E0"] and rm[e] < rm["E2"] for rm in lv_rm.values())]
        P(f"      {sub:<7} {', '.join(beats) if beats else 'none'}")
    P("")

    P("3 — SELECTION STABILITY (from the un-demeaned replicates' argmax m_b)")
    P("-" * 96)
    for lv in LEVELS:
        g = [r for r in rows if r["level"] == lv]
        P(f"   level {dg.lvl(lv)}")
        P(f"      90% set size            {dg.qsi([r['set90'] for r in g])}")
        P(f"      90% set contains m+     {dg.share([r['set90_mplus'] for r in g])}")
        P(f"      90% set contains m*     {dg.share([r['set90_mstar'] for r in g])}")
        P(f"      f of the top member     {dg.qs([r['f_max'] for r in g])}")
        P(f"      f(m+)                   {dg.qs([r['f_mplus'] for r in g])}")
        P(f"      f(m*)                   {dg.qs([r['f_mstar'] for r in g])}")
        P(f"      m*'s features' shares   {dg.qs([x for r in g for x in r['star_feat_share']])}")
        P(f"      m*'s families' shares   {dg.qs([x for r in g for x in r['star_fam_share']])}")
        P(f"      m*'s families are the top k by share (k = their count): "
          f"{dg.share([r['star_fams_topk'] for r in g])}; all in the top three: "
          f"{dg.share([r['star_fams_in_top3'] for r in g])}; k = 3 on "
          f"{sum(r['n_star_fams'] == 3 for r in g)}/{len(g)}")
        tag = "   [level 0: m+ negative, not a capture]" if lv == 0 else ""
        P(f"      capture, realized argmax  {dg.qs([r['argmax']['in'] / r['pop_mplus'] for r in g])}{tag}")
        P(f"      capture, denoised (max f) {dg.qs([r['dn_pop'] / r['pop_mplus'] for r in g])}{tag}")
        P(f"      SR_pop denoised - argmax  {dg.qs([r['dn_pop'] - r['argmax']['in'] for r in g])}")
        P(f"      denoised higher {dg.share([r['dn_pop'] > r['argmax']['in'] + 1e-12 for r in g])}; "
          f"equal (same member) {dg.share([r['dn_is_argmax'] for r in g])}; "
          f"denoised is m+ {dg.share([r['dn_is_mplus'] for r in g])}")
    P("")
    P(f"wall {time.time() - T0:.0f} s, seed tasks {cpu:.0f} CPU-s, {a.workers} workers; power at "
      f"launch: {pw}")
    text = "\n".join(L)
    if a.smoke:
        print(f"smoke ok: {len(L)} lines built, none printed; wall {time.time() - T0:.0f} s, "
              f"{cpu:.0f} CPU-s for {len(seeds)} seed at B {B_}; power {pw}")
        return 0
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text + "\n")
    if a.dump:
        with open(a.dump, "w") as fh:
            for sd in seeds:
                for r in res[sd]:
                    for name, key in (("class argmax", "argmax"), (EWI, "ewi")):
                        x = r[key]
                        fh.write(json.dumps(
                            {"seed": sd, "level": r["level"], "searcher": name,
                             "score": x["S"], **{e: x["est"].get(e) for e in
                                                 ("E0", "EH", "E2", "EC", "EB", "EBs")},
                             "in_sample": x["in"], "holdout": x["ho"],
                             "p_class": x["p"]}) + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
