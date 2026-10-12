"""7.5 planted-edge: the budget-cap preflight for the unsaturable arm. DESIGN INPUT ONLY.

`prereg/planted-edge.md` registers an agent arm on a class or budget the agent
cannot saturate, so that check 4 (tier power) is not predetermined: an agent that
submits the class maximum makes the replay and class tiers price one statistic
against near-identical nulls (the 7.3 cell, 120 of 120). The registration says to
preflight a **budget cap first**, and to reach for a deeper class only if the cap
leaves the searcher saturating. This is that preflight.

**A prototype, labelled as one.** The planted generator here implements the
registered construction (residual, planted signal, population Sharpe, calibration
of the planted scale) so the preflight has something to run on. The registered
generator is built before the file goes live and must reproduce this one's planted
scale and population Sharpe on these seeds (`prereg/planted-edge.md`, build items).

**The proxy, and why it is not the 7.1 searchers.** The registered scripted
searchers anchor and extend at sign +1, so on a signed class they reach a negative
sign only by `flip`; the agents in 6.5 chose signs in `extend_best` and
`swap_worst`. The proxy therefore runs the agent grammar's own content moves
(`quixote.grammar` semantics, both signs) in the order 6.5's agents most often used:
`init`, `extend_best`, `extend_best`, then `swap_worst` while it improves. A cap of k
moves is a prefix of the uncapped path, so one search gives every cap.

**Saturation** is the proxy's best support equalling the realized class argmax on
that panel, compared canonically (as a set of signed features).

Seeds: design block 640000-640999 (this preflight uses 640000-640019), checked
against every other pre-registration. No rule quantity is computed here.

    python -m experiments.planted_edge_preflight --draws 20 --workers 7
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from environments.class_table import CHUNK, canonical, members_in_order, streams_for
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from garden.spec_class import SubsetClass

CLS = SubsetClass(max_size=3, signed=True)
IS_END = dt.date(2017, 12, 31)
HO_START, HO_END = dt.date(2018, 1, 1), dt.date(2022, 12, 31)
DESIGN_BLOCK = 640000
CAPS = (2, 3, 4, 6, 12)
_CACHE: dict = {}


# -- the planted construction (prototype of the registered one) --------------

def split(panel):
    """In-sample rows (dates <= 2017-12-31) and planted-holdout rows (2018-2022)."""
    d = np.array(panel.meta["dates"])
    is_ = np.array([x <= IS_END for x in d])
    ho = np.array([HO_START <= x <= HO_END for x in d])

    def cut(mask):
        return replace(panel, features=panel.features[mask], returns=panel.returns[mask],
                       tradable=panel.tradable[mask], cost_rate=panel.cost_rate[mask],
                       borrow_rate=panel.borrow_rate[mask],
                       session_start=panel.session_start[mask],
                       session_end=panel.session_end[mask],
                       present=panel.present[mask],
                       meta={**panel.meta, "dates": list(d[mask])})
    return cut(is_), cut(ho)


def residual(panel) -> np.ndarray:
    """E = R - column means of R over the segment: the real (T, M) earned-return
    matrix, demeaned per asset. Rows are resampled jointly, so the cross-section
    of each day travels together."""
    R = np.asarray(panel.returns, dtype=float)
    return R - R.mean(axis=0, keepdims=True)


def member_weights(panel, support) -> np.ndarray:
    K = panel.features.shape[2]
    wf = np.zeros(K)
    for k, s in support:
        wf[k] = s
    return panel.weights_from(panel.features @ wf)


def _cost_borrow(panel, w) -> np.ndarray:
    prev = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    return (np.einsum("tm,tm->t", np.abs(w - prev), panel.cost_rate)
            + np.einsum("tm,tm->t", np.clip(-w, 0, None), panel.borrow_rate))


def population_sharpe(panel, Sigma, w_m, w_star, c) -> float:
    """The member's annualised net Sharpe under the planted process on this
    segment, features fixed and residual rows drawn from the segment's pool:

        d_t   = c * <w_m,t, w*_t> - cost_t - borrow_t        (the deterministic part)
        mean  = mean_t d_t
        var   = mean_t (w_m,t' Sigma w_m,t) + var_t d_t       (Sigma: residual covariance)
    """
    d = c * np.einsum("tm,tm->t", w_m, w_star) - _cost_borrow(panel, w_m)
    v = np.einsum("tm,mn,tn->t", w_m, Sigma, w_m).mean() + d.var()
    return float(d.mean() / np.sqrt(v) * np.sqrt(panel.periods_per_year))


def planted_scale(panel, Sigma, w_star, beta) -> float:
    """c such that the planted member's population net Sharpe equals beta."""
    f = lambda c: population_sharpe(panel, Sigma, w_star, w_star, c) - beta
    hi = 1e-4
    while f(hi) < 0:
        hi *= 2
    return float(brentq(f, 0.0, hi, xtol=1e-14)) if f(0.0) < 0 else 0.0


def planted_member(seed: int, members) -> tuple:
    """One depth-3 member, uniformly, from the panel seed's own child stream."""
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(2)[1])
    d3 = [m for m in members if len(m) == 3]
    return d3[int(rng.integers(len(d3)))]


# -- one preflight draw ------------------------------------------------------

def _base():
    if not _CACHE:
        from environments.real_panel import build_etf_panel
        is_p, _ = split(build_etf_panel())
        E = residual(is_p)
        _CACHE.update(is_p=is_p, E=E, Sigma=np.cov(E, rowvar=False, ddof=1),
                      L=int(select_block_length(E)),
                      members=members_in_order(CLS, is_p.features.shape[2]))
    return _CACHE


def _sharpe_rows(S, ann):
    std = S.std(axis=1, ddof=1)
    return np.where(std > 0, S.mean(axis=1) / np.where(std > 0, std, 1.0), 0.0) * ann


def draw(payload) -> dict:
    seed, beta = payload
    b = _base()
    is_p, E, Sigma, L, members = b["is_p"], b["E"], b["Sigma"], b["L"], b["members"]
    t0 = time.time()
    m_star = planted_member(seed, members)
    w_star = member_weights(is_p, m_star)
    c = planted_scale(is_p, Sigma, w_star, beta)
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(2)[0])
    idx = stationary_bootstrap_indices(E.shape[0], L, rng)
    panel = replace(is_p, returns=E[idx] + c * w_star)
    ann = float(np.sqrt(panel.periods_per_year))

    # the realized class argmax, chunked over all 82,240 members
    best, best_m = -np.inf, None
    for s in range(0, len(members), CHUNK):
        sr = _sharpe_rows(streams_for(panel, members[s:s + CHUNK]), ann)
        j = int(np.argmax(sr))
        if sr[j] > best:
            best, best_m = float(sr[j]), members[s + j]

    # the proxy: init, extend_best, extend_best, then swap_worst while improving
    K = panel.features.shape[2]
    signs = (1.0, -1.0)

    def best_of(cands):
        sr = _sharpe_rows(streams_for(panel, cands), ann) if len(cands) > 1 else \
            _sharpe_rows(streams_for(panel, cands + cands), ann)[:1]
        j = int(np.argmax(sr))
        return cands[j], float(sr[j])

    sup, score = best_of([((k, s),) for k in range(K) for s in signs])
    path = [(sup, score)]
    for _ in range(2):
        held = {k for k, _ in sup}
        sup, score = best_of([sup + ((j, s),) for j in range(K) if j not in held
                              for s in signs])
        path.append((sup, score))
    while len(path) < max(CAPS):
        held = {k for k, _ in sup}
        cands = [sup[:i] + ((j, s),) + sup[i + 1:] for i in range(len(sup))
                 for j in range(K) if j not in held for s in signs]
        ns, nscore = best_of(cands)
        if nscore <= score:
            break
        sup, score = ns, nscore
        path.append((sup, score))

    def best_by(k):
        return max(path[:k], key=lambda p: p[1])

    star_sr = float(_sharpe_rows(streams_for(panel, [m_star, m_star]), ann)[0])
    return {"seed": seed, "beta": beta, "planted": [list(p) for p in m_star],
            "c": c, "pop_sr_planted": population_sharpe(is_p, Sigma, w_star, w_star, c),
            "realized_sr_planted": star_sr, "class_max": best,
            "class_argmax_is_planted": canonical(best_m) == canonical(m_star),
            "moves_used": len(path),
            "saturated_at_cap": {k: canonical(best_by(k)[0]) == canonical(best_m)
                                 for k in CAPS},
            "planted_found_at_cap": {k: canonical(best_by(k)[0]) == canonical(m_star)
                                     for k in CAPS},
            "secs": time.time() - t0, "block_length": L}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--levels", default="1.0,1.5")
    ap.add_argument("--workers", type=int, default=7)
    ap.add_argument("--out", default="runs/planted_edge_preflight.json")
    a = ap.parse_args(argv)
    levels = [float(x) for x in a.levels.split(",")]
    tasks = [(DESIGN_BLOCK + i, b) for b in levels for i in range(a.draws)]
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=a.workers) as pool:
        rows = list(pool.map(draw, tasks))
    Path(a.out).write_text(json.dumps(rows, indent=1, default=str))
    L = ["7.5 planted-edge — BUDGET-CAP PREFLIGHT (design input, prototype generator)",
         "=" * 78,
         f"  design seeds {DESIGN_BLOCK}-{DESIGN_BLOCK + a.draws - 1}, paired across levels;"
         f" block length {rows[0]['block_length']}",
         "  proxy: init, extend_best x2, swap_worst while improving (agent grammar, both"
         " signs); saturated = best support equals the realized class argmax", ""]
    for b in levels:
        rs = [r for r in rows if r["beta"] == b]
        n = len(rs)
        L.append(f"  beta {b}: n {n}; population SR of planted member "
                 f"{np.mean([r['pop_sr_planted'] for r in rs]):.3f} (target {b}); realized "
                 f"in-sample SR mean {np.mean([r['realized_sr_planted'] for r in rs]):.3f}; "
                 f"class max mean {np.mean([r['class_max'] for r in rs]):.3f}; "
                 f"class argmax = planted {sum(r['class_argmax_is_planted'] for r in rs)}/{n}")
        L.append(f"    moves used uncapped: median {np.median([r['moves_used'] for r in rs]):.0f}"
                 f", max {max(r['moves_used'] for r in rs)}")
        for k in CAPS:
            s = sum(r["saturated_at_cap"][k] for r in rs)
            f = sum(r["planted_found_at_cap"][k] for r in rs)
            L.append(f"    cap {k:>2} moves: saturated {s:>2}/{n} = {s / n:.2f}   "
                     f"planted member found {f:>2}/{n}")
        L.append("")
    L.append(f"  per draw: median {np.median([r['secs'] for r in rows]):.0f}s")
    text = "\n".join(L)
    print(text)
    Path(a.out).with_suffix(".txt").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# -- is beta = 0 a global null? ----------------------------------------------

def population_sharpes(panel, Sigma, w_star, c, supports) -> np.ndarray:
    """Population net Sharpe of many members at once: `streams_for`'s batched
    position loop, accumulating the deterministic part d_t and w' Sigma w instead
    of a realized stream."""
    T, M, K = panel.features.shape
    n = len(supports)
    Wf = np.zeros((K, n))
    for j, sup in enumerate(supports):
        for k, s in sup:
            Wf[k, j] = s
    d = np.empty((n, T))
    q = np.zeros(n)
    held = np.zeros((n, M))
    prev = np.zeros((n, M))
    for t in range(T):
        free = panel.tradable[t]
        target = np.where(free, (panel.features[t] @ Wf).T, 0.0)
        if free.any():
            target = target - target[:, free].mean(axis=1, keepdims=True) * free
            gross = np.abs(target[:, free]).sum(axis=1, keepdims=True)
            nz = gross[:, 0] > 0
            target[nz] = target[nz] / gross[nz]
        new = np.where(free, target, held)
        d[:, t] = (c * (new @ w_star[t]) - (np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
                   - (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        q += np.einsum("nm,mk,nk->n", new, Sigma, new)
        held = prev = new
    v = q / T + d.var(axis=1)
    return d.mean(axis=1) / np.sqrt(v) * np.sqrt(panel.periods_per_year)


def null_check(seed: int) -> dict:
    """At beta = 0: the largest population net Sharpe over the whole class."""
    b = _base()
    is_p, Sigma, members = b["is_p"], b["Sigma"], b["members"]
    m_star = planted_member(seed, members)
    w_star = member_weights(is_p, m_star)
    c = planted_scale(is_p, Sigma, w_star, 0.0)
    best, best_m, n_pos = -np.inf, None, 0
    for s in range(0, len(members), CHUNK):
        sr = population_sharpes(is_p, Sigma, w_star, c, members[s:s + CHUNK])
        n_pos += int((sr > 0).sum())
        j = int(np.argmax(sr))
        if sr[j] > best:
            best, best_m = float(sr[j]), members[s + j]
    return {"seed": seed, "planted": [list(p) for p in m_star], "c": c,
            "max_population_sr_at_beta0": best, "argmax": [list(p) for p in best_m],
            "members_positive": n_pos}
