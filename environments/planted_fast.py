"""A cached, factorised class pass for 7.5's planted panels. A new kernel; the
registered drivers are untouched.

**Why it is exact on these panels.** On the planted ETF panel every name is tradable
in every period and nothing is flattened overnight, so `streams_for`'s book carries no
state. A member's position on day t is a function of X and the member alone:

    pos_t(m) = D_t w_m / g_t(m),    D_t = X_t demeaned across names,
                                    g_t(m) = sum over names of |D_t w_m|

so its net stream factorises:

    s_t(m) = w_m . (D_t' r_t) / g_t(m)  -  k_t(m)

where `k_t(m)` is the day's cost plus borrow, which depends on positions only. The
normaliser `g` and the cost path `k` are **the same for every seed and every level**.
They are computed once from the pinned X and kept as two read-only (N, T) tables on
disk. A seed then needs only `F_t = D_t' r_t`, a (T, K) array, and every member's
stream is one matrix product, a division and a subtraction. `streams_for` walks the
3,019 days in a Python loop for every 512 members, which is 96% of a class pass.

**All planted levels from one pass (b).** The levels of one seed share the residual
draw, so `r_t = E[idx_t] + c w*_t` and `F_t(c) = F0_t + c G_t` with `G_t = D_t' w*_t`.
Each level's streams are therefore the closed form `(w . F_t(c))/g - k`. F0 and G are
computed once per seed, and the population overlap moments come from the same `G`.

**What it refuses:** any panel with an untradable period or overnight flattening. Its
book has state, and the factorisation does not hold.

**The cache** (`data/planted_cache/fast_<key>/`, gitignored, so never in git) holds
`g.npy` and `k.npy` (82,240 x 3,019 float64, 1.99 GB each), opened `mmap_mode="r"` and
shared through the page cache. The key hashes the pinned X's SHA-256, the in-sample
panel's own hash (features, returns, costs), the class name and size, and a kernel
version. A different panel or class can never read another's tables. The tables are
written to a private temporary directory and renamed into place, under a lock, so a
reader sees a complete cache or none.

Equivalence against `experiments.planted_edge.run_level` is in
`tests/test_planted_fast.py` (synthetic base) and in a one-off design-seed check.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, _panel_hash, canonical

VERSION = "fast-1"
BUILD_CHUNK = 128
DEFAULT_DIR = Path(__file__).resolve().parent.parent / "data" / "planted_cache"


def check_panel(panel) -> None:
    if not np.asarray(panel.tradable).all():
        raise ValueError("the factorised kernel refuses a panel with untradable periods: "
                         "its book carries state, so positions are not a function of X alone")
    if bool(panel.flat_overnight):
        raise ValueError("the factorised kernel refuses a flat-overnight panel: its book "
                         "carries state across sessions")


def demeaned(panel) -> np.ndarray:
    X = np.asarray(panel.features, dtype=float)
    return X - X.mean(axis=1, keepdims=True)                 # (T, M, K)


def weight_matrix(members, K: int) -> np.ndarray:
    Wf = np.zeros((K, len(members)))
    for j, sup in enumerate(members):
        for k, s in sup:
            Wf[int(k), j] = float(s)
    return Wf


def panel_x_sha256(panel) -> str:
    """SHA-256 of the panel's OWN feature array (float64, C order, raw bytes), recorded in
    the cache manifest. (Manifests written before 2026-10-07 carry `pinned_x_sha256`, the
    ETF pin's file hash, whatever the panel.) The cache key is unchanged."""
    return hashlib.sha256(np.ascontiguousarray(panel.features, dtype=np.float64).tobytes()).hexdigest()


def cache_key(panel, members, name: str) -> str:
    h = hashlib.sha256()
    h.update(pp.PINNED_X_SHA256.encode())
    h.update(_panel_hash(panel).encode())
    h.update(f"{name}|{len(members)}|{VERSION}".encode())
    h.update(json.dumps([list(map(list, m)) for m in members[:64]]).encode())
    return h.hexdigest()[:16]


def _positions_cost(panel, D, Wf):
    """(g, k) for a chunk of members: the normaliser and the daily cost plus borrow,
    (n, T) each, from the stateless book."""
    T, M, K = D.shape
    P = (D.reshape(T * M, K) @ Wf).reshape(T, M, -1).transpose(0, 2, 1)   # (T, n, M)
    g = np.abs(P).sum(axis=2)                                             # (T, n)
    pos = np.where((g > 0)[..., None], P / np.where(g > 0, g, 1.0)[..., None], P)
    prev = np.concatenate([np.zeros((1,) + pos.shape[1:]), pos[:-1]], axis=0)
    cr = np.asarray(panel.cost_rate, float)[:, None, :]
    br = np.asarray(panel.borrow_rate, float)[:, None, :]
    k = (np.abs(pos - prev) * cr).sum(axis=2) + (np.clip(-pos, 0, None) * br).sum(axis=2)
    return g.T.copy(), k.T.copy()


class FastCache:
    """The read-only normaliser and cost tables for one panel and class."""

    def __init__(self, g, k, members, key: str, path: str | None):
        self.g, self.k, self.members, self.key, self.path = g, k, members, key, path
        self.index = {canonical(m): i for i, m in enumerate(members)}

    @property
    def N(self) -> int:
        return int(self.g.shape[0])


def build(panel, members, name: str = "planted-signed-3", cache_dir=None,
          progress=None) -> FastCache:
    """Open the cache, building it once if absent. Concurrent callers build once."""
    import fcntl
    check_panel(panel)
    key = cache_key(panel, members, name)
    root = Path(cache_dir) if cache_dir is not None else DEFAULT_DIR
    root.mkdir(parents=True, exist_ok=True)
    final = root / f"fast_{key}"

    def _open():
        g = np.load(final / "g.npy", mmap_mode="r")
        k = np.load(final / "k.npy", mmap_mode="r")
        return FastCache(g, k, members, key, str(final))

    if (final / "manifest.json").exists():
        return _open()
    with open(root / f"fast_{key}.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (final / "manifest.json").exists():
            return _open()
        tmp = root / f".fast_{key}.{os.getpid()}.tmp"
        tmp.mkdir(parents=True, exist_ok=True)
        T = panel.features.shape[0]
        N = len(members)
        D = demeaned(panel)
        gm = np.lib.format.open_memmap(tmp / "g.npy", mode="w+", dtype=np.float64, shape=(N, T))
        km = np.lib.format.open_memmap(tmp / "k.npy", mode="w+", dtype=np.float64, shape=(N, T))
        t0 = time.time()
        for s in range(0, N, BUILD_CHUNK):
            Wf = weight_matrix(members[s:s + BUILD_CHUNK], D.shape[2])
            gm[s:s + Wf.shape[1]], km[s:s + Wf.shape[1]] = _positions_cost(panel, D, Wf)
            if progress is not None:
                progress(min(s + BUILD_CHUNK, N), N)
        gm.flush(); km.flush()
        del gm, km
        (tmp / "manifest.json").write_text(json.dumps(
            {"key": key, "version": VERSION, "panel_x_sha256": panel_x_sha256(panel),
             "panel_hash": _panel_hash(panel), "class": name, "N": N, "T": T,
             "build_secs": time.time() - t0}, indent=1))
        os.replace(tmp, final)
    return _open()


# -- streams --------------------------------------------------------------------

def feature_returns(panel, returns=None) -> np.ndarray:
    """F_t = D_t' r_t, (T, K)."""
    R = np.asarray(panel.returns if returns is None else returns, float)
    return np.einsum("tmk,tm->tk", demeaned(panel), R)


def streams(cache: FastCache, F: np.ndarray, start: int, stop: int) -> np.ndarray:
    """Net streams (n, T) of members [start, stop) given the day's feature returns F."""
    Wf = weight_matrix(cache.members[start:stop], F.shape[1])
    g = np.asarray(cache.g[start:stop])
    num = (F @ Wf).T                                                   # (n, T)
    gross = np.divide(num, g, out=np.zeros_like(num), where=g > 0)
    return gross - np.asarray(cache.k[start:stop])


def overlap(cache: FastCache, G: np.ndarray, start: int, stop: int) -> np.ndarray:
    """a_t(m) = pos_t(m) . w*_t, (n, T), from G_t = D_t' w*_t."""
    Wf = weight_matrix(cache.members[start:stop], G.shape[1])
    g = np.asarray(cache.g[start:stop])
    num = (G @ Wf).T
    return np.divide(num, g, out=np.zeros_like(num), where=g > 0)


# -- the class pass, and run_level on top of it -----------------------------------

def _sharpe_rows(S, ann):
    std = S.std(axis=1, ddof=1)
    return np.where(std > 0, S.mean(axis=1) / np.where(std > 0, std, 1.0), 0.0) * ann


def class_pass_levels(base, cache: FastCache, seed: int, betas, B: int):
    """For each level: (draw, obs (N,), rep (N, B), L) and the seed's overlap moments,
    from ONE computation of F0 and G per seed (b). Levels share the residual draw;
    that is asserted, not assumed."""
    return class_pass_draws(base, cache, seed, [pp.make_draw(base, seed, b) for b in betas], B)


def class_pass_draws(base, cache: FastCache, seed: int, draws, B: int, summary=None):
    """`class_pass_levels` on draws already made: member draws or planted rules
    (`environments.planted_rules.RuleDraw`), all from one seed's residual draw. With
    `summary`, each level's entry is summary(draw, obs, rep, L) instead of the tuple, so
    the (N, B) replicate array of one level is released before the next is built."""
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    for d in draws[1:]:
        if not np.array_equal(d.idx_is, draws[0].idx_is):
            raise AssertionError("levels of one seed must share the residual draw")
        if not np.array_equal(d.w_star_is, draws[0].w_star_is):
            raise AssertionError("levels of one seed must share the planted positions")
    panel0 = draws[0].in_sample
    check_panel(panel0)
    T = panel0.features.shape[0]
    ann = float(np.sqrt(panel0.periods_per_year))
    E = base.E_is[draws[0].idx_is]
    D = demeaned(panel0)
    F0 = np.einsum("tmk,tm->tk", D, E)
    G = np.einsum("tmk,tm->tk", D, draws[0].w_star_is)
    N = cache.N
    Ea, Ea2, Eak = np.empty(N), np.empty(N), np.empty(N)
    for s in range(0, N, CHUNK):
        a = overlap(cache, G, s, min(s + CHUNK, N))
        k = np.asarray(cache.k[s:s + len(a)])
        Ea[s:s + len(a)] = a.mean(axis=1)
        Ea2[s:s + len(a)] = (a * a).mean(axis=1)
        Eak[s:s + len(a)] = (a * k).mean(axis=1)
    out = []
    for d in draws:
        panel = d.in_sample
        bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
        L = int(select_block_length(bc - bc.mean(axis=0)))
        rng = np.random.default_rng(seed)
        C = np.empty((T, B))
        for b in range(B):
            C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
        F = F0 + d.c * G
        obs = np.empty(N)
        rep = np.empty((N, B))
        for s in range(0, N, CHUNK):
            X = streams(cache, F, s, min(s + CHUNK, N))
            obs[s:s + len(X)] = _sharpe_rows(X, ann)
            X0 = X - X.mean(axis=1, keepdims=True)
            mean = (X0 @ C) / T
            var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
            pos = var > 0
            rep[s:s + len(X)] = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)),
                                         0.0) * ann
        out.append((d, obs, rep, L) if summary is None else summary(d, obs, rep, L))
        del rep
    return out, (Ea, Ea2, Eak)


def run_levels(base, cache: FastCache, seed: int, betas, B: int, inv: dict) -> list:
    """`planted_edge.run_level`'s records for every level of one seed, from the fast
    pass. The searchers, trigger nulls and truths are run_level's code."""
    from experiments.planted_edge import ALPHAS, StreamCache, _searchers, _sharpe
    passes, (Ea, Ea2, Eak) = class_pass_levels(base, cache, seed, betas, B)
    members = base.members
    index = {canonical(m): i for i, m in enumerate(members)}
    recs = []
    for d, obs, rep, L in passes:
        t0 = time.time()
        panel = d.in_sample
        T, M, K = panel.features.shape
        ann = float(np.sqrt(panel.periods_per_year))
        j = int(np.argmax(obs))
        best, best_m = float(obs[j]), members[j]
        M_b = rep.max(axis=0)
        single_ix = [index[canonical(((k, 1.0),))] for k in range(K)]
        out_s = []
        for srch in _searchers(seed, T, panel.periods_per_year):
            tr = srch._search(K, lambda k: float(obs[single_ix[k]]),
                              lambda sup: float(obs[index[canonical(sup)]]))
            sub, score, n = tuple(tr.support), float(tr.score), tr.n_moves
            n2 = np.empty(B)
            for b in range(B):
                col = rep[:, b]
                n2[b] = srch._search(K, lambda k, col=col: float(col[single_ix[k]]),
                                     lambda sup, col=col: float(col[index[canonical(sup)]]),
                                     meta_steps=n).score
            out_s.append({"searcher": srch.name, "support": sub, "score": score,
                          "n_moves": n,
                          "p_class": (1 + int(np.sum(M_b >= score))) / (B + 1),
                          "p_trigger": (1 + int(np.sum(n2 >= score))) / (B + 1)})
        pop = pp.population_from_moments(Ea, Ea2, Eak, inv, d.c, panel.periods_per_year)
        star = canonical(d.m_star)
        jp = int(np.argmax(pop))
        ho = StreamCache(d.holdout)
        for r in out_s:
            sup = r["support"]
            r["truth"] = ({"in_sample": float(pop[index[canonical(sup)]]),
                           "holdout": pp.truth(base, d, sup)["holdout"]} if sup else None)
            r["holdout_realized"] = _sharpe(ho.get(sup), ann) if sup else None
            r["support"] = [list(p) for p in canonical(sup)] if sup else None
        recs.append({"seed": seed, "beta": d.beta, "c": d.c,
                     "planted": [list(p) for p in star], "block_length_null": L, "B": B,
                     "class_max": best, "class_argmax": [list(p) for p in canonical(best_m)],
                     "null_max_mean": float(M_b.mean()),
                     "pop_best": [list(p) for p in canonical(members[jp])],
                     "pop_best_sr": float(pop[jp]),
                     "planted_rank": int((pop > pop[index[star]]).sum()) + 1,
                     "null_max_q": {str(a): float(np.quantile(M_b, 1 - a)) for a in ALPHAS},
                     "searchers": out_s, "secs": time.time() - t0})
    return recs
