"""The version-2 learner (note, D): ridge_stack's structure re-implemented, one fit per
(information, horizon, neutrality, memory) cell.

Ridge blocks: L, linear over the active columns; with P active also Q (14 family squares),
I (91 family products) and S (14 families x 3 states, raw, scaled by the training SD).
Penalties by nested out-of-fold error over 3 blocked folds with the embargo at the fold
edges; trees (the registered settings) on the active columns plus the 3 states; a
non-negative stack of the out-of-fold ridge and tree predictions. Walk-forward: first
scored row 756 + h + 1 + d, refit every 252 rows, training rows t <= s - (h + 1 + d), the
memory setting choosing which of them (rolling 252, rolling 756, expanding).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from learn2 import states as S
from learn2 import timing
from learn2.blocks import cs

BIG = 1e6
FIRST = 756
REFIT = 252
WARMUP = 64
MEMORIES = {"roll252": 252, "roll756": 756, "expand": None}
GRIDS = {"L": (0.3, 1.0, 3.0), "Q": (0.3, 1.0, 3.0, BIG), "I": (1.0, 3.0, 10.0, BIG),
         "S": (1.0, 3.0, 10.0, BIG)}
TREES = dict(objective="regression", num_leaves=4, max_depth=2, learning_rate=0.1,
             min_data_in_leaf=200, max_bin=63, num_threads=1, deterministic=True,
             force_row_wise=True, verbose=-1, seed=1)
NTREE = 50
LIGHTGBM = "4.7.0"


def _families():
    from learn.inputs import FAMILIES, PAIRS          # the registered family map (data only)
    return FAMILIES, PAIRS


@dataclass
class Inputs:
    """What a version-2 learner sees on one panel."""
    P: np.ndarray | None                 # (T, M, 40) raw registered features
    earned: np.ndarray                   # (T, M): earned[t] is the return of row t + 1 + d
    cost_rate: np.ndarray
    borrow_rate: np.ndarray
    ppy: float
    d: int
    blocks: dict = field(default_factory=dict)       # "X", "V", "F": (T, M, k), standardised
    groups: np.ndarray | None = None                 # (T, M) labels, -1 before warm

    @property
    def available(self) -> tuple:
        return (("P",) if self.P is not None else ()) + tuple(b for b in ("X", "V", "F") if b in self.blocks)


def from_panel(panel, blocks: dict | None = None, groups=None) -> Inputs:
    return Inputs(P=np.asarray(panel.features, float), earned=np.asarray(panel.returns, float),
                  cost_rate=np.asarray(panel.cost_rate, float),
                  borrow_rate=np.asarray(panel.borrow_rate, float),
                  ppy=float(panel.periods_per_year), d=timing.delay(panel),
                  blocks=dict(blocks or {}), groups=groups)


def tree_fit(X, y):
    import lightgbm as lgb
    if lgb.__version__ != LIGHTGBM:
        raise RuntimeError(f"LightGBM {lgb.__version__}, not {LIGHTGBM}")
    return lgb.train(TREES, lgb.Dataset(np.asarray(X, np.float64), np.asarray(y, np.float64)),
                     num_boost_round=NTREE)


def nnls2(A, y):
    AtA, Aty = A.T @ A, A.T @ y
    try:
        w = np.linalg.solve(AtA, Aty)
    except np.linalg.LinAlgError:
        w = np.array([-1.0, -1.0])
    if w.min() < 0:
        c0 = max(Aty[0] / AtA[0, 0], 0.0) if AtA[0, 0] > 0 else 0.0
        c1 = max(Aty[1] / AtA[1, 1], 0.0) if AtA[1, 1] > 0 else 0.0
        f0 = c0 * Aty[0] - 0.5 * c0 * c0 * AtA[0, 0]
        f1 = c1 * Aty[1] - 0.5 * c1 * c1 * AtA[1, 1]
        w = np.array([c0, 0.0]) if f0 >= f1 else np.array([0.0, c1])
    if w.sum() == 0:
        w = np.array([1.0, 0.0])
    return w


# -- design ---------------------------------------------------------------------------------

def design(inp: Inputs, info: tuple, st: np.ndarray):
    """(Z (T, M, p), blocks {name: column indices}, tree inputs (T, M, q))."""
    parts, idx, k = [], {}, 0
    lin = []
    if "P" in info:
        lin.append(cs(inp.P))
    for b in ("X", "V", "F"):
        if b in info:
            lin.append(inp.blocks[b])
    L = np.concatenate(lin, axis=2)
    parts.append(L)
    idx["L"] = np.arange(k, k + L.shape[2])
    k += L.shape[2]
    T, M = L.shape[:2]
    if "P" in info:
        fam, pairs = _families()
        z = parts[0][:, :, :40]
        sf = cs(np.stack([z[:, :, list(f)].mean(axis=2) for f in fam], axis=2))
        Q = cs(sf ** 2)
        Iq = cs(np.stack([sf[:, :, f] * sf[:, :, g] for f, g in pairs], axis=2))
        Sb = np.concatenate([sf[:, :, [f]] * st[:, None, [j]] for f in range(len(fam)) for j in range(3)],
                            axis=2)
        for name, B in (("Q", Q), ("I", Iq), ("S", Sb)):
            parts.append(B)
            idx[name] = np.arange(k, k + B.shape[2])
            k += B.shape[2]
    Z = np.concatenate(parts, axis=2)
    Xt = np.concatenate([L, np.repeat(st[:, None, :], M, axis=1)], axis=2)
    return Z, idx, Xt


def neutral_target(fwd: np.ndarray, neutrality: str, groups_row: np.ndarray | None) -> np.ndarray:
    """Market: cs(fwd). Group: demeaned within the refit-row groups, divided by the row's
    cross-sectional SD of the group-demeaned values."""
    if neutrality == "market":
        return cs(fwd)
    g = groups_row
    out = np.zeros_like(fwd)
    for lab in np.unique(g):
        m = g == lab
        out[:, m] = fwd[:, m] - np.nanmean(fwd[:, m], axis=1, keepdims=True)
    sd = np.nanstd(out, axis=1, keepdims=True)
    return np.nan_to_num(np.where(sd > 0, out / np.where(sd > 0, sd, 1.0), 0.0))


# -- ridge on Gram matrices -------------------------------------------------------------------

def _gram(Z, y, rows):
    Zc = Z[rows].reshape(-1, Z.shape[2])
    yc = y[rows].ravel()
    return Zc.T @ Zc, Zc.T @ yc, float(yc @ yc), len(yc)


def _pen(al, n, blocks, idx):
    return n * np.concatenate([np.full(len(idx[b]), a) for b, a in zip(blocks, al)])


def _solve(G, b, n, al, blocks, idx, D):
    cols = np.concatenate([idx[k] for k in blocks])
    Dc = D[cols]
    Gs = Dc[:, None] * G[np.ix_(cols, cols)] * Dc[None, :]
    w = np.linalg.solve(Gs + np.diag(_pen(al, n, blocks, idx)), Dc * b[cols])
    return cols, Dc * w


def _mse(w, cols, G, b, yy):
    return yy - 2 * w @ b[cols] + w @ G[np.ix_(cols, cols)] @ w


def _choose(pairs, blocks, idx, D):
    """The grid point with the least total held-out error over (train, test) Gram pairs."""
    import itertools
    grid = list(itertools.product(*(GRIDS[b] for b in blocks)))
    best = (np.inf, None)
    for al in grid:
        tot = 0.0
        for (Gt, bt, _, nt), (Gv, bv, yyv, _) in pairs:
            cols, w = _solve(Gt, bt, nt, al, blocks, idx, D)
            tot += _mse(w, cols, Gv, bv, yyv)
        if tot < best[0]:
            best = (tot, al)
    return best[1]


def _folds(rows: np.ndarray, emb: int):
    """3 contiguous blocks of `rows`; for each, the training rows outside it with the
    embargo removed at its edges."""
    n = len(rows)
    ed = np.linspace(0, n, 4).astype(int)
    out = []
    for k in range(3):
        hold = rows[ed[k]:ed[k + 1]]
        if len(hold) == 0:
            out.append((hold, rows[:0]))
            continue
        lo, hi = hold[0], hold[-1]
        train = rows[((rows < lo - emb) | (rows > hi + emb))]
        out.append((hold, train))
    return out


def _edges(al, blocks) -> list[str]:
    return [b for a, b in zip(al, blocks) if a in (GRIDS[b][0], GRIDS[b][-1])]


# -- the walk-forward -------------------------------------------------------------------------

def fit_cell(inp: Inputs, info: tuple, h: int, neutrality: str, memory: str) -> dict:
    """Predictions (T, M), NaN outside the scored rows; refit rows; edge reports."""
    d = inp.d
    T, M = inp.earned.shape
    emb = timing.embargo(h, d)
    first = FIRST + emb
    st = S.market_states(inp.earned, d)
    Z, idx, Xt = design(inp, info, st)
    blocks = tuple(b for b in ("L", "Q", "I", "S") if b in idx)
    fwd = timing.forward_sum(inp.earned, h)
    pred = np.full((T, M), np.nan)
    refit_of = np.full(T, -1, dtype=int)
    diags = []
    W = MEMORIES[memory]
    for s in range(first, T, REFIT):
        hi = s - emb
        lo = 0 if W is None else max(0, hi - W + 1)
        rows = np.arange(max(lo, WARMUP), hi + 1)
        g_row = inp.groups[s] if (neutrality == "group" and inp.groups is not None) else None
        if neutrality == "group" and (g_row is None or (g_row < 0).any()):
            continue                                  # no groups yet: no fit, no positions
        y = neutral_target(fwd, neutrality, g_row)
        rows = rows[np.isfinite(fwd[rows]).all(axis=1)]
        if len(rows) < 30:
            continue
        # S scaled by its SD over the training rows
        D = np.ones(Z.shape[2])
        if "S" in idx:
            Sc = Z[rows][:, :, idx["S"]].reshape(-1, len(idx["S"]))
            sd = Sc.std(axis=0)
            D[idx["S"]] = np.where(sd > 0, 1.0 / np.where(sd > 0, sd, 1.0), 0.0)
        folds = _folds(rows, emb)
        grams = {}

        def gram(key, rr):
            if key not in grams:
                grams[key] = _gram(Z, y, rr)
            return grams[key]
        outer = [(gram(("tr", k), tr), gram(("ho", k), ho)) for k, (ho, tr) in enumerate(folds)]
        al = _choose(outer, blocks, idx, D)
        # nested out-of-fold ridge predictions, and tree out-of-fold predictions
        oof_r = np.zeros((len(rows), M))
        oof_t = np.zeros((len(rows), M))
        pos = {t: i for i, t in enumerate(rows)}
        for k, (ho, tr) in enumerate(folds):
            if len(ho) == 0 or len(tr) == 0:
                continue
            others = [j for j in range(3) if j != k and len(folds[j][0])]
            inner = []
            for j in others:
                (jo,) = [x for x in others if x != j] or [None]
                if jo is None:
                    continue
                hj = folds[j][0]
                tj = folds[jo][0]
                tj = tj[(tj < hj[0] - emb) | (tj > hj[-1] + emb)]
                if len(tj):
                    inner.append((gram(("in", j, jo), tj), gram(("ho", j), hj)))
            al_k = _choose(inner, blocks, idx, D) if inner else al
            Gt, bt, _, nt = gram(("tr", k), tr)
            cols, w = _solve(Gt, bt, nt, al_k, blocks, idx, D)
            ii = [pos[t] for t in ho]
            oof_r[ii] = Z[ho][:, :, cols] @ w
            bst = tree_fit(Xt[tr].reshape(-1, Xt.shape[2]), y[tr].ravel())
            oof_t[ii] = bst.predict(Xt[ho].reshape(-1, Xt.shape[2])).reshape(len(ho), M)
        w2 = nnls2(np.stack([oof_r.ravel(), oof_t.ravel()], axis=1), y[rows].ravel())
        Gall = gram("all", rows)
        cols, w = _solve(Gall[0], Gall[1], Gall[3], al, blocks, idx, D)
        bst = tree_fit(Xt[rows].reshape(-1, Xt.shape[2]), y[rows].ravel())
        sc = np.arange(s, min(s + REFIT, T))
        pred[sc] = w2[0] * (Z[sc][:, :, cols] @ w) + \
            w2[1] * bst.predict(Xt[sc].reshape(-1, Xt.shape[2])).reshape(len(sc), M)
        refit_of[sc] = s
        diags.append({"refit": int(s), "train_rows": int(len(rows)), "penalties": dict(zip(blocks, al)),
                      "at_edge": _edges(al, blocks), "stack": [float(w2[0]), float(w2[1])]})
    return {"pred": pred, "first": first, "refit_of": refit_of, "diagnostics": diags,
            "info": tuple(info), "h": h, "neutrality": neutrality, "memory": memory}
