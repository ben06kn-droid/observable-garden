"""mv_combine: a penalised mean-variance combination of basis-portfolio returns
(`prereg/ml-pipeline-exploratory-2026-10-07.md`, revision of 2026-10-07, Part 2B).
Designed from theory on 2026-10-07; tested nowhere before this build.

Columns (162), all as net returns under the panel's cost function:
  A  the 14 family signals s_f                  -> basis portfolios
  B  their squares s_f^2                         -> basis portfolios
  C  the 91 products s_f s_g, f < g              -> basis portfolios
  D  42: state_k(t) gross_A_f(t) - |state_k(t)| cost_A_f(t)      (returns only)
  T  the tree portfolio (LightGBM on the 40 z and the three states)

b = (Sigma + diag(gamma))^-1 mu over the training window; one penalty per block,
gamma_b = c trace(Sigma_bb) / (kappa_b^2 T_years), c chosen by leave-one-year-out Sharpe.
Positions: sum_ABC b_j p_j + sum_D b_fk state_k p_Af + b_T p_T, divided by the training
mean gross of the same expression, any day above gross 2 scaled to 2.
"""
from __future__ import annotations

import numpy as np

from learn import inputs as I
from learn import trees

C_GRID = (0.25, 0.5, 1.0, 2.0, 4.0)
KAPPA = {"A": 1.0, "B": 0.5, "C": 0.5, "D": 0.5, "T": 0.5}
BLOCK_SIZES = {"A": I.NF, "B": I.NF, "C": len(I.PAIRS), "D": 3 * I.NF, "T": 1}
BLOCKS = tuple(BLOCK_SIZES)
GROSS_CAP = 2.0


def block_index() -> dict:
    out, s = {}, 0
    for b in BLOCKS:
        out[b] = np.arange(s, s + BLOCK_SIZES[b])
        s += BLOCK_SIZES[b]
    return out


BIDX = block_index()
NCOL = sum(BLOCK_SIZES.values())          # 162


def penalties(Sigma: np.ndarray, c: float, T_years: float) -> np.ndarray:
    g = np.empty(NCOL)
    for b, idx in BIDX.items():
        g[idx] = c * np.trace(Sigma[np.ix_(idx, idx)]) / (KAPPA[b] ** 2 * T_years)
    return g


def weights(mu: np.ndarray, Sigma: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    return np.linalg.solve(Sigma + np.diag(gamma), mu)


def moments(R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return R.mean(axis=0), np.cov(R, rowvar=False, ddof=1).reshape(R.shape[1], R.shape[1])


def effective_parameters(Sigma: np.ndarray, gamma: np.ndarray) -> dict:
    H = Sigma @ np.linalg.inv(Sigma + np.diag(gamma))
    d = np.diag(H)
    return {"total": float(d.sum()), **{b: float(d[idx].sum()) for b, idx in BIDX.items()}}


def choose_c(R: np.ndarray, years: list[np.ndarray], ppy: float) -> tuple[float, dict]:
    """Leave-one-year-out: for each c, fit without year y, rescale to unit training
    variance, apply to y; the c with the highest Sharpe of the concatenated held-out series
    wins, ties to the larger c."""
    score = {}
    for c in C_GRID:
        held = []
        for y in years:
            keep = np.ones(R.shape[0], bool)
            keep[y] = False
            mu, S = moments(R[keep])
            b = weights(mu, S, penalties(S, c, keep.sum() / ppy))
            v = float(b @ S @ b)
            if v > 0:
                b = b / np.sqrt(v)
            held.append(R[y] @ b)
        score[c] = I.sharpe(np.concatenate(held), ppy)
    best = max(C_GRID, key=lambda c: (score[c], c))
    return best, score


def block_D(states: np.ndarray, gross_A: np.ndarray, cost_A: np.ndarray) -> np.ndarray:
    """(42, T): for family f and state k, state_k(t) gross_A_f(t) - |state_k(t)| cost_A_f(t),
    ordered f-major."""
    return np.stack([states[:, k] * gross_A[f] - np.abs(states[:, k]) * cost_A[f]
                     for f in range(I.NF) for k in range(3)])


def columns(panel, risk_sizing: bool = True) -> dict:
    """Everything the fits share: inputs, the 119 basis portfolios and their gross and cost,
    block D, the tree inputs and target."""
    X = np.asarray(panel.features, float)
    R = np.asarray(panel.returns, float)
    cr, br = np.asarray(panel.cost_rate, float), np.asarray(panel.borrow_rate, float)
    T, M, _ = X.shape
    z = I.zscore_features(X)
    s = I.family_signals(z)
    st = I.market_states(R)
    sig = I.sigma(R)
    valid = ~np.isnan(sig).any(axis=1)
    sig_used = sig if risk_sizing else None
    sigs = [s[:, :, f] for f in range(I.NF)] + [s[:, :, f] ** 2 for f in range(I.NF)] + \
        [s[:, :, f] * s[:, :, g] for f, g in I.PAIRS]
    port = np.stack([I.basis_portfolio(g, sig_used) for g in sigs])          # (119, T, M)
    gross = np.einsum("jtm,tm->jt", port, R)
    cost = np.stack([I.cost_of(p, cr, br) for p in port])
    Xt = np.concatenate([z, np.repeat(st[:, None, :], M, axis=1)], axis=2)
    yt = I.cs(np.where(np.isnan(sig), 0.0, R / np.where(np.isnan(sig), 1.0, sig)))
    return {"R": R, "cr": cr, "br": br, "T": T, "M": M, "z": z, "st": st, "sig": sig,
            "valid": valid, "sig_used": sig_used, "port": port, "gross": gross, "cost": cost,
            "netABC": gross - cost, "netD": block_D(st, gross[:I.NF], cost[:I.NF]),
            "Xt": Xt, "yt": yt}


def run(panel, risk_sizing: bool = True, log=None) -> dict:
    """Walk-forward mv_combine on a panel. Returns positions (T, M) (zero outside the
    scored years), the scored rows, the per-refit diagnostics and the warm-up count."""
    say = log or (lambda s: None)
    ppy = float(panel.periods_per_year)
    cols = columns(panel, risk_sizing)
    R, cr, br, T, M = cols["R"], cols["cr"], cols["br"], cols["T"], cols["M"]
    st, valid, sig_used, port = cols["st"], cols["valid"], cols["sig_used"], cols["port"]
    netABC, netD, Xt, yt = cols["netABC"], cols["netD"], cols["Xt"], cols["yt"]
    A = BIDX["A"]
    say(f"mv_combine: warm-up rows dropped from every fit: {int((~valid).sum())}")
    predT = np.zeros((T, M))

    chunks = I.year_chunks(T)
    pos = np.zeros((T, M))
    diags = []
    booster = None
    for j in range(I.FIRST_TEST_YEAR, len(chunks)):
        s0, e0 = chunks[j]
        train = np.arange(0, s0 - I.GAP)
        train = train[valid[train]]
        if (j - I.FIRST_TEST_YEAR) % 2 == 0:                     # tree refit every second year
            booster = trees.fit(Xt[train].reshape(-1, Xt.shape[2]), yt[train].ravel())
            oof = trees.oof_predictions([Xt[t] for t in train], [yt[t] for t in train], I.GAP)
            predT[:] = 0.0
            for t, p in zip(train, oof):
                predT[t] = p
            rest = np.arange(s0 - I.GAP, T)
            predT[rest] = booster.predict(Xt[rest].reshape(-1, Xt.shape[2])).reshape(len(rest), M)
        else:
            rest = np.arange(s0, T)          # the booster's realised OOS rows extend the series
        pT = I.basis_portfolio(predT, sig_used)
        netT = I.gross_of(pT, R) - I.cost_of(pT, cr, br)
        Rall = np.vstack([netABC, netD, netT[None, :]]).T                        # (T, 162)
        Rtr = Rall[train]
        T_years = len(train) / ppy
        years = [np.flatnonzero((train >= a) & (train < b)) for a, b in chunks[:j]]
        years = [y for y in years if len(y)]
        c, held = choose_c(Rtr, years, ppy)
        mu, Sg = moments(Rtr)
        gam = penalties(Sg, c, T_years)
        b = weights(mu, Sg, gam)

        def expression(rows):
            P = np.tensordot(b[A], port[:I.NF][:, rows], axes=1) \
                + np.tensordot(b[BIDX["B"]], port[I.NF:2 * I.NF][:, rows], axes=1) \
                + np.tensordot(b[BIDX["C"]], port[2 * I.NF:][:, rows], axes=1)
            bD = b[BIDX["D"]].reshape(I.NF, 3)
            P = P + np.einsum("fk,tk,ftm->tm", bD, st[rows], port[:I.NF][:, rows])
            return P + b[BIDX["T"]][0] * pT[rows]
        Ptr = expression(train)
        G = float(np.abs(Ptr).sum(axis=1).mean())
        test = np.arange(s0, e0)
        P = expression(test) / G if G > 0 else expression(test) * 0.0
        g = np.abs(P).sum(axis=1, keepdims=True)
        P = np.where(g > GROSS_CAP, P * (GROSS_CAP / np.where(g > 0, g, 1.0)), P)
        pos[test] = P
        sr = I.sharpe(Rtr @ b, ppy)
        eff = effective_parameters(Sg, gam)
        eff_by_c = {cc: effective_parameters(Sg, penalties(Sg, cc, T_years)) for cc in C_GRID}
        d = {"year": j, "c": c, "held_out_sharpe_by_c": held, "effective": eff,
             "effective_by_c": eff_by_c, "train_sharpe": sr,
             "sic": sr - eff["total"] / (T_years * sr) if sr != 0 else float("nan"),
             "T_years": T_years, "G": G, "train_rows": int(len(train)),
             "train_mean_gross": float(np.abs(Ptr / G).sum(axis=1).mean()) if G > 0 else 0.0}
        diags.append(d)
        say(f"  refit year {j}: c {c}; effective parameters {eff['total']:.2f} ("
            + ", ".join(f"{k} {eff[k]:.2f}" for k in BLOCKS) + f"); training Sharpe {sr:.3f}; "
            f"Sharpe - eff/(T_years Sharpe) {d['sic']:.3f}")
    scored = np.arange(chunks[I.FIRST_TEST_YEAR][0], T)
    return {"positions": pos, "scored_rows": scored, "diagnostics": diags,
            "warmup_dropped": int((~valid).sum())}
