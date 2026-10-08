"""Input blocks X, V, F and the neutrality groups (note, B and "Change"). Each uses rows
<= t only and is standardised across assets each row (missing -> 0).

Inputs are ROW returns r (T, M): r[t] is the return of row t, known at its close."""
from __future__ import annotations

import numpy as np

WIN = 252
SHORT = 21
N_GROUPS = 5
MIN_GROUP = 3
X_NAMES = ("beta_mkt_1", "beta_mkt_5") + tuple(f"pc{k}_{n}" for k in (1, 2, 3) for n in (1, 5)) + \
          ("resid_1", "resid_5")
V_NAMES = ("logvol_ratio", "taker_last", "taker_mean21", "count_ratio", "amihud21")
F_NAMES = ("fund_last", "fund_mean21", "fund_change")


def cs(x: np.ndarray) -> np.ndarray:
    """Cross-sectional z-score per row (and per column for 3-D input); NaN and +/-inf -> 0."""
    x = np.where(np.isfinite(x), x, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu = np.nanmean(x, axis=1, keepdims=True)
        sd = np.nanstd(x, axis=1, keepdims=True)
        z = np.where(sd > 0, (x - mu) / np.where(sd > 0, sd, 1.0), 0.0)
    return np.nan_to_num(z)


def _sum5(x: np.ndarray, t: int) -> np.ndarray:
    return x[max(0, t - 4):t + 1].sum(axis=0)


def build_X(r: np.ndarray, market: np.ndarray) -> np.ndarray:
    """(T, M, 10), standardised. Zero until the 252-row window is full."""
    r = np.nan_to_num(np.asarray(r, float))
    m = np.nan_to_num(np.asarray(market, float))
    T, M = r.shape
    out = np.zeros((T, M, 10))
    for t in range(WIN - 1, T):
        R = r[t - WIN + 1:t + 1]
        x = m[t - WIN + 1:t + 1]
        xc = x - x.mean()
        vx = float(xc @ xc)
        beta = (xc @ (R - R.mean(axis=0))) / vx if vx > 0 else np.zeros(M)
        mu, sd = R.mean(axis=0), R.std(axis=0, ddof=1)
        live = sd > 0
        Zs = np.zeros_like(R)
        Zs[:, live] = (R[:, live] - mu[live]) / sd[live]
        C = (Zs.T @ Zs) / (WIN - 1)
        np.fill_diagonal(C, np.where(live, 1.0, 0.0))
        w, V = np.linalg.eigh(C)
        V = V[:, np.argsort(-w, kind="stable")][:, :3]
        zt = np.zeros(M)
        zt[live] = (r[t, live] - mu[live]) / sd[live]
        z5 = np.zeros(M)
        R5 = r[max(0, t - 4):t + 1]
        z5[live] = ((R5[:, live] - mu[live]) / sd[live]).sum(axis=0)
        cols = [beta * m[t], beta * _sum5(m, t)]
        for k in range(3):
            v = V[:, k]
            cols += [v * float(v @ zt), v * float(v @ z5)]
        resid = r[t] - beta * m[t]
        resid5 = _sum5(r, t) - beta * _sum5(m, t)
        cols += [resid, resid5]
        out[t] = np.stack(cols, axis=1)
    return cs(out)


def _trail_mean(x: np.ndarray, w: int) -> np.ndarray:
    """Mean over rows t-w+1..t, NaN until full."""
    c = np.vstack([np.zeros((1,) + x.shape[1:]), np.cumsum(x, axis=0)])
    out = np.full_like(x, np.nan, dtype=float)
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def build_V(volume, price, r, taker=None, count=None) -> tuple[np.ndarray, tuple]:
    """(T, M, k) standardised, and the column names the fields allow (note, B)."""
    cols, names = [], []
    with np.errstate(divide="ignore", invalid="ignore"):
        if volume is not None:
            v = np.asarray(volume, float)
            cols.append(np.log(v) - np.log(_trail_mean(v, SHORT)))
            names.append("logvol_ratio")
        if taker is not None and volume is not None:
            share = np.asarray(taker, float) / np.asarray(volume, float) - 0.5
            cols += [share, _trail_mean(np.nan_to_num(share), SHORT)]
            names += ["taker_last", "taker_mean21"]
        if count is not None:
            n = np.asarray(count, float)
            cols.append(np.log(n) - np.log(_trail_mean(n, SHORT)))
            names.append("count_ratio")
        if volume is not None and price is not None:
            dv = np.asarray(price, float) * np.asarray(volume, float)
            ill = np.abs(np.asarray(r, float)) / dv
            cols.append(_trail_mean(np.where(np.isfinite(ill), ill, 0.0), SHORT))
            names.append("amihud21")
    if not cols:
        return None, ()
    return cs(np.stack(cols, axis=2)), tuple(names)


def build_F(funding: np.ndarray) -> np.ndarray:
    """(T, M, 3) from the funding rate known at each row (T, M)."""
    f = np.nan_to_num(np.asarray(funding, float))
    ch = np.zeros_like(f)
    ch[1:] = f[1:] - f[:-1]
    return cs(np.stack([f, _trail_mean(f, SHORT), ch], axis=2))


# -- neutrality groups -------------------------------------------------------------------

def cluster_bruteforce(dist: np.ndarray, k: int = N_GROUPS, min_size: int = MIN_GROUP) -> np.ndarray:
    """The note's rule written literally (average of pairwise distances recomputed at each
    step). Slow; the reference `cluster` is tested against."""
    M = dist.shape[0]
    cl = {i: [i] for i in range(M)}

    def avg(a, b):
        return float(dist[np.ix_(cl[a], cl[b])].mean())

    while len(cl) > k:
        ids = sorted(cl)
        best = min((avg(ids[x], ids[y]), ids[x], ids[y])
                   for x in range(len(ids)) for y in range(x + 1, len(ids)))
        _, a, b = best
        cl[a] = sorted(cl[a] + cl.pop(b))
    while True:
        small = sorted((c for c in cl if len(cl[c]) < min_size), key=lambda c: (len(cl[c]), c))
        if not small or len(cl) == 1:
            break
        s = small[0]
        tgt = min((c for c in cl if c != s), key=lambda c: (avg(s, c), c))
        merged = sorted(cl[s] + cl[tgt])
        del cl[s], cl[tgt]
        cl[merged[0]] = merged
    labels = np.empty(M, dtype=int)
    for g, c in enumerate(sorted(cl)):
        labels[cl[c]] = g
    return labels


def cluster(dist: np.ndarray, k: int = N_GROUPS, min_size: int = MIN_GROUP) -> np.ndarray:
    """The note's exact rule, with average-linkage distances kept by the Lance-Williams
    update (the size-weighted mean, equal to the mean of the pairwise distances). A
    cluster's id is its smallest asset index; `argmin` over the upper triangle in row-major
    order gives the lexicographically smallest (smaller id, larger id) among ties."""
    M = dist.shape[0]
    D = np.array(dist, dtype=float)
    np.fill_diagonal(D, np.inf)
    size = np.ones(M)
    active = np.ones(M, bool)
    members = {i: [i] for i in range(M)}

    def merge(a, b):                        # a < b; b joins a
        na, nb = size[a], size[b]
        row = (na * D[a] + nb * D[b]) / (na + nb)
        D[a, :] = row
        D[:, a] = row
        D[a, a] = np.inf
        D[b, :] = np.inf
        D[:, b] = np.inf
        size[a] = na + nb
        active[b] = False
        members[a] = sorted(members[a] + members.pop(b))

    tri = np.triu(np.ones((M, M), bool), 1)
    while active.sum() > k:
        Dm = np.where(tri & active[:, None] & active[None, :], D, np.inf)
        a, b = np.unravel_index(int(np.argmin(Dm)), Dm.shape)
        merge(int(a), int(b))
    while True:
        ids = [i for i in range(M) if active[i]]
        small = sorted((c for c in ids if size[c] < min_size), key=lambda c: (size[c], c))
        if not small or len(ids) == 1:
            break
        s = small[0]
        tgt = min((c for c in ids if c != s), key=lambda c: (D[s, c], c))
        a, b = min(s, tgt), max(s, tgt)
        merge(a, b)
    labels = np.empty(M, dtype=int)
    for g, c in enumerate(i for i in range(M) if active[i]):
        labels[members[c]] = g
    return labels


def build_groups(r: np.ndarray) -> np.ndarray:
    """(T, M) group labels from the trailing 252-row correlation of row returns r; -1
    before the window is full."""
    r = np.nan_to_num(np.asarray(r, float))
    T, M = r.shape
    out = np.full((T, M), -1, dtype=int)
    for t in range(WIN - 1, T):
        R = r[t - WIN + 1:t + 1]
        sd = R.std(axis=0, ddof=1)
        live = sd > 0
        Zs = np.zeros_like(R)
        Zs[:, live] = (R[:, live] - R[:, live].mean(axis=0)) / sd[live]
        C = (Zs.T @ Zs) / (WIN - 1)
        C[~live, :] = 0.0
        C[:, ~live] = 0.0
        np.fill_diagonal(C, 1.0)
        out[t] = cluster(1.0 - C)
    return out
