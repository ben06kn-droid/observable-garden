"""ridge_stack and the plain-ridge control (`prereg/ml-pipeline-exploratory-2026-10-07.md`).

ridge_stack is `scratch/ml_stress_test.py`'s stack_w, ported with the resolutions of
2026-10-07, plus:
  - a fourth ridge block S, the 14 s_f times each state (42 columns), scaled by its
    training SD and not re-standardised by day, penalties {1, 3, 10, off};
  - the three states as extra tree inputs;
  - out-of-fold ridge predictions for the stack weights made with penalties chosen
    without the year being predicted (nested leave-one-year-out).
The control is a plain ridge on the 40 z, penalty 1.0. Both share the walk-forward and
the position rule: predictions averaged over five rows, demeaned, unit gross.
"""
from __future__ import annotations

import itertools

import numpy as np

from learn import inputs as I
from learn import trees

BIG = 1e6
NL, NQ, NI, NS = 40, I.NF, len(I.PAIRS), 3 * I.NF
IDX = {"L": np.arange(0, NL), "Q": np.arange(NL, NL + NQ),
       "I": np.arange(NL + NQ, NL + NQ + NI), "S": np.arange(NL + NQ + NI, NL + NQ + NI + NS)}
BLOCKS = ("L", "Q", "I", "S")
GRID = [(a, q, i, s) for a in (0.3, 1, 3) for q in (0.3, 1, 3, BIG) for i in (1, 3, 10, BIG)
        for s in (1, 3, 10, BIG)]                                         # 192


def design(z, sf, st) -> np.ndarray:
    """(T, M, 187): z (40); cs(s_f^2) (14); cs(s_f s_g) (91); s_f * state_k raw (42)."""
    Q = I.cs(sf ** 2)
    Iq = I.cs(np.stack([sf[:, :, f] * sf[:, :, g] for f, g in I.PAIRS], axis=2))
    S = np.concatenate([sf[:, :, [f]] * st[:, None, [k]] for f in range(I.NF) for k in range(3)],
                       axis=2)
    return np.concatenate([z, Q, Iq, S], axis=2)


def pen(al, n, blocks):
    return n * np.concatenate([np.full(len(IDX[b]), a) for b, a in zip(blocks, al)])


class Grams:
    """Per-year Gram matrices of the design over each year's rows, the year's last GAP rows
    and the warm-up rows left out (the embargo, as the stress test)."""

    def __init__(self, Z, y, valid, chunks):
        self.G, self.b, self.n, self.yy, self.s1, self.s2 = [], [], [], [], [], []
        for s, e in chunks:
            rows = np.arange(s, e - I.GAP)
            rows = rows[valid[rows]]
            Zc = Z[rows].reshape(-1, Z.shape[2])
            yc = y[rows].ravel()
            self.G.append(Zc.T @ Zc)
            self.b.append(Zc.T @ yc)
            self.n.append(len(yc))
            self.yy.append(float(yc @ yc))
            self.s1.append(Zc.sum(axis=0))
            self.s2.append((Zc * Zc).sum(axis=0))

    def scale(self, years) -> np.ndarray:
        """1 everywhere except block S: 1 / its SD over the given years' rows."""
        n = sum(self.n[k] for k in years)
        m = sum(self.s1[k] for k in years) / n
        v = sum(self.s2[k] for k in years) / n - m * m
        d = np.ones(len(m))
        sd = np.sqrt(np.maximum(v[IDX["S"]], 0.0))
        d[IDX["S"]] = np.where(sd > 0, 1.0 / np.where(sd > 0, sd, 1.0), 0.0)
        return d


def _solve(Gr, br, idx, D, al, n, blocks):
    Gs = (D[idx, None] * Gr[np.ix_(idx, idx)]) * D[None, idx]
    return D[idx] * np.linalg.solve(Gs + np.diag(pen(al, n, blocks)), D[idx] * br[idx])


def fit(gr: Grams, years, blocks, al=None, grid=None, D=None):
    """Ridge on `years`; with a grid, the block penalties by leave-one-year-out error over
    `years`, from the Gram matrices alone. Returns (columns, weights on raw design, al)."""
    idx = np.concatenate([IDX[k] for k in blocks])
    D = np.ones(sum(len(v) for v in IDX.values())) if D is None else D
    Gt = sum(gr.G[k] for k in years)
    bt = sum(gr.b[k] for k in years)
    nt = sum(gr.n[k] for k in years)
    if grid is not None:
        best = (np.inf, None)
        for cand in grid:
            mse = 0.0
            for k in years:
                w = _solve(Gt - gr.G[k], bt - gr.b[k], idx, D, cand, nt - gr.n[k], blocks)
                Gk = gr.G[k][np.ix_(idx, idx)]
                mse += gr.yy[k] - 2 * w @ gr.b[k][idx] + w @ Gk @ w
            if mse < best[0]:
                best = (mse, cand)
        al = best[1]
    return idx, _solve(Gt, bt, idx, D, al, nt, blocks), al


def _positions(pred_rows: np.ndarray) -> np.ndarray:
    return I.unit(I.trailing_mean(pred_rows))


def _nnls2(A, y):
    AtA, Aty = A.T @ A, A.T @ y
    w = np.linalg.solve(AtA, Aty)
    if w.min() < 0:
        c0 = max(Aty[0] / AtA[0, 0], 0.0)
        c1 = max(Aty[1] / AtA[1, 1], 0.0)
        f0 = c0 * Aty[0] - 0.5 * c0 * c0 * AtA[0, 0]
        f1 = c1 * Aty[1] - 0.5 * c1 * c1 * AtA[1, 1]
        w = np.array([c0, 0.0]) if f0 >= f1 else np.array([0.0, c1])
    if w.sum() == 0:
        w = np.array([1.0, 0.0])
    return w


def run(panel, which: str = "ridge_stack", log=None) -> dict:
    """`which` is "ridge_stack" or "control". Positions (T, M), zero outside the scored years."""
    say = log or (lambda s: None)
    X = np.asarray(panel.features, float)
    R = np.asarray(panel.returns, float)
    T, M, _ = X.shape
    z = I.zscore_features(X)
    sf = I.family_signals(z)
    st = I.market_states(R)
    valid = I.valid_rows(R)
    say(f"{which}: warm-up rows dropped from every fit: {int((~valid).sum())}")
    y = I.cs(R)
    Z = design(z, sf, st)
    chunks = I.year_chunks(T)
    gr = Grams(Z, y, valid, chunks)
    first = chunks[I.FIRST_TEST_YEAR][0]
    pred = np.zeros((T, M))
    diags = []
    if which == "control":
        for j in range(I.FIRST_TEST_YEAR, len(chunks)):
            idx, w, _ = fit(gr, list(range(j)), ("L",), al=(1.0,))
            rows = np.arange(*chunks[j])
            pred[rows] = Z[rows][:, :, idx] @ w
    else:
        Xt = np.concatenate([z, np.repeat(st[:, None, :], M, axis=1)], axis=2)
        w2 = np.array([1.0, 0.0])
        booster = None
        for j in range(I.FIRST_TEST_YEAR, len(chunks)):
            yrs = list(range(j))
            D = gr.scale(yrs)
            idx, w, al = fit(gr, yrs, BLOCKS, grid=GRID, D=D)
            rows = np.arange(*chunks[j])
            ridge_pred = Z[rows][:, :, idx] @ w
            if (j - I.FIRST_TEST_YEAR) % 2 == 0:
                s0 = chunks[j][0]
                trd = np.arange(0, s0 - I.GAP)
                trd = trd[valid[trd]]
                booster = trees.fit(Xt[trd].reshape(-1, Xt.shape[2]), y[trd].ravel())
                oof_t = np.concatenate(trees.oof_predictions([Xt[t] for t in trd],
                                                             [y[t] for t in trd], I.GAP))
                # ridge out-of-fold: for each year k, penalties chosen without year k
                oof_r = np.zeros((T, M))
                for k in yrs:
                    others = [q for q in yrs if q != k]
                    Dk = gr.scale(others)
                    ik, wk, _ = fit(gr, others, BLOCKS, grid=GRID, D=Dk)
                    rk = np.arange(*chunks[k])
                    oof_r[rk] = Z[rk][:, :, ik] @ wk
                A = np.stack([oof_r[trd].ravel(), oof_t], axis=1)
                w2 = _nnls2(A, y[trd].ravel())
            tree_pred = booster.predict(Xt[rows].reshape(-1, Xt.shape[2])).reshape(len(rows), M)
            pred[rows] = w2[0] * ridge_pred + w2[1] * tree_pred
            diags.append({"year": j, "penalties": al, "stack_weights": [float(w2[0]),
                                                                        float(w2[1])]})
            say(f"  refit year {j}: block penalties {al}; stack weights "
                f"({w2[0]:.3f}, {w2[1]:.3f})")
    scored = np.arange(first, T)
    pos = np.zeros((T, M))
    pos[scored] = _positions(pred[scored])
    return {"positions": pos, "scored_rows": scored, "diagnostics": diags,
            "warmup_dropped": int((~valid).sum())}
