"""Stress test for the machine-learning pipeline design (sandbox, synthetic stand-in panel).

NOT project evidence. The panel is invented: it has the planted panel's dimensions (3,019 days, 40 assets,
40 features in 14 families) but synthetic features and returns. Because the truth is known, the population
Sharpe of any pipeline's out-of-sample positions is computed exactly, without sampling noise.

What it compares, all walk-forward with a 2-day embargo and annual refits from year 4:
  ridge      linear ridge on the 40 features
  block_cv   ridge on three blocks (40 linear, 14 family quadratics, 91 family pairwise products), one penalty
             per block, chosen by leave-one-year-out inside the training window
  gbm_a      small boosted trees: 50 trees of depth 2, learning rate 0.1, no tuning, refit every second year
  stack_w    block_cv and gbm_a combined with non-negative weights fitted on out-of-fold predictions

Edge shapes (planted as c * positions of the rule, like the project's generator):
  L linear   U quadratic   V absolute value   S saturating   B middle band   G gated   C corner
  P pure product of two features   M linear plus gated

Usage:  python ml_stress_test.py OUT.jsonl  trees|fast  PANELS  L,U,C,P  1.0,1.5,3.0  SEED0  NPROC
Requires numpy and lightgbm. Set OMP_NUM_THREADS=1 when running several processes.
"""
import itertools, json, sys, time, warnings
import numpy as np

warnings.filterwarnings("ignore")
T, N, K = 3019, 40, 40
FAM = [2, 2, 4, 2, 6, 4, 6, 2, 2, 2, 2, 2, 2, 2]
NF = len(FAM)
PAIRS = list(itertools.combinations(range(NF), 2))
COST, GAP = 1e-4, 2      # cost set so a persistent linear rule loses about 0.1-0.2 Sharpe, as on the ETF panel
CH = [(252 * j, 252 * (j + 1)) for j in range(11)] + [(2772, T)]      # yearly chunks
IDX = dict(L=np.arange(0, 40), Q=np.arange(40, 54), I=np.arange(54, 54 + len(PAIRS)))
BIG = 1e6
GRID = [(a, q, i) for a in (0.3, 1, 3) for q in (0.3, 1, 3, BIG) for i in (1, 3, 10, BIG)]
BLOCKS = ("L", "Q", "I")


def ar(rng, rho, shape):
    z = np.empty(shape); z[0] = rng.standard_normal(shape[1])
    e = rng.standard_normal(shape) * np.sqrt(1 - rho ** 2)
    for t in range(1, shape[0]):
        z[t] = rho * z[t - 1] + e[t]
    return z


def make_panel(seed):
    """Features: 14 persistent family factors per asset plus member noise, standardised across assets each day.
    Returns: asset-class factors plus idiosyncratic noise, fat tails, a slow volatility regime. No edge."""
    rng = np.random.default_rng(seed)
    rhos = rng.choice([0.0, 0.8, 0.95, 0.98, 0.99, 0.995], size=NF, p=[0.07, 0.08, 0.15, 0.2, 0.25, 0.25])
    X = np.empty((T, N, K)); fam_of = []; k = 0
    for f, (sz, rho) in enumerate(zip(FAM, rhos)):
        z = ar(rng, rho, (T, N))
        for _ in range(sz):
            X[:, :, k] = z + 0.33 * ar(rng, rho, (T, N)); fam_of.append(f); k += 1
    X -= X.mean(1, keepdims=True); X /= X.std(1, keepdims=True)
    cls = rng.integers(0, 4, N); fv = np.array([0.010, 0.003, 0.009, 0.006, 0.006])
    B = np.zeros((N, 5)); B[np.arange(N), cls] = rng.uniform(0.7, 1.3, N); B[:, 4] = rng.uniform(0.2, 0.6, N)
    idio = rng.uniform(0.003, 0.007, N)
    lv = np.zeros(T)
    for t in range(1, T):
        lv[t] = 0.985 * lv[t - 1] + 0.10 * rng.standard_normal()
    m = np.exp(lv); m /= np.sqrt((m ** 2).mean())
    E = (rng.standard_t(5, (T, 5)) / np.sqrt(5 / 3) * fv @ B.T + rng.standard_t(4, (T, N)) / np.sqrt(2.0) * idio) * m[:, None]
    return dict(X=X, E=E, m2=m ** 2, Sigma0=B @ np.diag(fv ** 2) @ B.T + np.diag(idio ** 2),
                rhos=rhos, fam_of=np.array(fam_of), rng=rng)


def unit(s):
    d = s - s.mean(1, keepdims=True); g = np.abs(d).sum(1, keepdims=True); g[g == 0] = 1
    return d / g


def planted(P, typ, beta):
    """Positions of the planted rule and the scale c that gives it population gross Sharpe beta."""
    rng, fam_of = P["rng"], P["fam_of"]
    ok = [k for k in range(K) if P["rhos"][fam_of[k]] >= 0.95]
    a = rng.choice(ok); b = rng.choice([k for k in ok if fam_of[k] != fam_of[a]])
    c3 = rng.choice([k for k in ok if fam_of[k] not in (fam_of[a], fam_of[b])])
    xa, xb, xc = P["X"][:, :, a], P["X"][:, :, b], P["X"][:, :, c3]
    s = {"L": xa, "U": xa ** 2, "V": np.abs(xa), "S": np.tanh(2 * xa), "B": (np.abs(xa) < 0.5).astype(float),
         "G": xa * (xb > 0), "C": ((xa > 0.8) & (xb > 0)).astype(float), "P": xa * xb, "M": xa + xb * (xc > 0)}[typ]
    u = unit(s)
    if beta == 0:
        return u, 0.0
    num = (u * u).sum(1).mean() * 252
    den = np.sqrt((P["m2"] * np.einsum("ti,ij,tj->t", u, P["Sigma0"], u)).mean() * 252)
    return u, beta * den / num


def smooth(f, w):
    if w == 1:
        return f
    c = np.cumsum(f, 0); out = c.copy(); out[w:] = c[w:] - c[:-w]
    return out / np.minimum(np.arange(1, len(f) + 1), w)[:, None]


def score(f, days, P, R, u, c, w=5):
    """Realised and population Sharpe of the positions formed from predictions f (demeaned, unit gross)."""
    p = unit(smooth(f, w))
    pi = (p * R[days]).sum(1)
    to = np.r_[np.abs(p[0]).sum(), np.abs(np.diff(p, axis=0)).sum(1)]
    net = pi - COST * to
    mu = c * (p * u[days]).sum(1)
    vol = np.sqrt((P["m2"][days] * np.einsum("ti,ij,tj->t", p, P["Sigma0"], p)).mean() * 252)
    sr = lambda x: float(x.mean() / x.std() * np.sqrt(252))
    return dict(pop_gross=float(mu.mean() * 252 / vol), pop_net=float((mu.mean() - COST * to.mean()) * 252 / vol),
                real_gross=sr(pi), real_net=sr(net), turnover=float(to.mean()))


def rows(days):
    return (days[:, None] * N + np.arange(N)[None, :]).ravel()


def cs(Z3):
    Z3 = Z3 - Z3.mean(1, keepdims=True); s = Z3.std(1, keepdims=True); s[s == 0] = 1
    return Z3 / s


def design(P):
    X, fam = P["X"], P["fam_of"]
    F = cs(np.stack([X[:, :, fam == f].mean(2) for f in range(NF)], 2))
    Q = cs(F ** 2)
    I = cs(np.stack([F[:, :, i] * F[:, :, j] for i, j in PAIRS], 2))
    return np.concatenate([X.reshape(T * N, K), Q.reshape(T * N, NF), I.reshape(T * N, len(PAIRS))], 1)


def pen(al, n, blocks):
    return n * np.concatenate([np.full(len(IDX[b]), a) for b, a in zip(blocks, al)])


def fit_ridge(G, b, nn, yy, j, blocks, al=None, grid=None):
    """Ridge on chunks 0..j-1 from accumulated Gram matrices. With a grid, block penalties are chosen by
    leave-one-year-out error, computed from the Gram matrices alone."""
    idx = np.concatenate([IDX[k] for k in blocks]); ix = np.ix_(idx, idx)
    Gt = sum(G[:j])[ix]; bt = sum(b[:j])[idx]; nt = sum(nn[:j])
    if grid is not None:
        best = (np.inf, None)
        for cand in grid:
            mse = 0.0
            for k in range(j):
                Gk = G[k][ix]; bk = b[k][idx]
                w = np.linalg.solve(Gt - Gk + np.diag(pen(cand, nt - nn[k], blocks)), bt - bk)
                mse += yy[k] - 2 * w @ bk + w @ Gk @ w
            if mse < best[0]:
                best = (mse, cand)
        al = best[1]
    return idx, np.linalg.solve(Gt + np.diag(pen(al, nt, blocks)), bt), al


TREES = dict(objective="regression", num_leaves=4, max_depth=2, learning_rate=0.1, min_data_in_leaf=200,
             max_bin=63, num_threads=1, deterministic=True, force_row_wise=True, verbose=-1, seed=1)
NTREE = 50


def run(task):
    seed, typ, beta, which = task
    t0 = time.time(); P = make_panel(seed); u, c = planted(P, typ, beta)
    R = P["E"] + c * u
    y = R - R.mean(1, keepdims=True); y = (y / y.std(1, keepdims=True)).ravel()
    Z = design(P); Xr = P["X"].reshape(T * N, K).astype(np.float32)
    G, b, nn, yy = [], [], [], []
    for s, e in CH:                      # each year's Gram matrix leaves out its last GAP days: the embargo
        r = rows(np.arange(s, e - GAP)); Zc = Z[r]; yc = y[r]
        G.append(Zc.T @ Zc); b.append(Zc.T @ yc); nn.append(len(r)); yy.append(yc @ yc)
    res = dict(seed=seed, typ=typ, beta=beta, oracle=score(u, np.arange(T), P, R, u, c, 1))
    preds = dict(ridge=[], block_cv=[]); days = []; wts = []; picks = []
    trees = which == "trees"
    if trees:
        import lightgbm as lgb
        preds.update(gbm_a=[], stack_w=[])
    for j in range(3, 12):
        te = np.arange(*CH[j]); rt = rows(te); days.append(te)
        idx, w, _ = fit_ridge(G, b, nn, yy, j, ("L",), (1.0,))
        preds["ridge"].append((Z[rt][:, idx] @ w).reshape(len(te), N))
        idx, w, al = fit_ridge(G, b, nn, yy, j, BLOCKS, grid=GRID); picks.append(al)
        preds["block_cv"].append((Z[rt][:, idx] @ w).reshape(len(te), N))
        if trees and (j - 3) % 2 == 0:
            trd = np.arange(0, CH[j][0] - GAP); tr = rows(trd)
            booster = lgb.train(TREES, lgb.Dataset(Xr[tr], y[tr]), num_boost_round=NTREE)
            oof_t = np.empty(len(tr)); ed = np.linspace(0, len(trd), 4).astype(int)
            for k in range(3):           # trees: three blocked folds inside the training window
                inn = np.r_[trd[:max(ed[k] - GAP, 0)], trd[min(ed[k + 1] + GAP, len(trd)):]]
                bk = lgb.train(TREES, lgb.Dataset(Xr[rows(inn)], y[rows(inn)]), num_boost_round=NTREE)
                oof_t[ed[k] * N:ed[k + 1] * N] = bk.predict(Xr[rows(trd[ed[k]:ed[k + 1]])])
            ix = np.ix_(idx, idx); Gt = sum(G[:j])[ix]; bt = sum(b[:j])[idx]; ntot = sum(nn[:j])
            oof_r = np.zeros(len(tr))
            for k in range(j):           # ridge: leave one year out
                wk = np.linalg.solve(Gt - G[k][ix] + np.diag(pen(al, ntot - nn[k], BLOCKS)), bt - b[k][idx])
                s_, e_ = CH[k]; e_ = min(e_, CH[j][0] - GAP)
                oof_r[s_ * N:e_ * N] = Z[s_ * N:e_ * N][:, idx] @ wk
            A = np.stack([oof_r, oof_t], 1); AtA = A.T @ A; Aty = A.T @ y[tr]
            w2 = np.linalg.solve(AtA, Aty)
            if w2.min() < 0:             # two-column non-negative least squares
                c0 = max(Aty[0] / AtA[0, 0], 0.0); c1 = max(Aty[1] / AtA[1, 1], 0.0)
                f0 = c0 * Aty[0] - 0.5 * c0 * c0 * AtA[0, 0]; f1 = c1 * Aty[1] - 0.5 * c1 * c1 * AtA[1, 1]
                w2 = np.array([c0, 0.0]) if f0 >= f1 else np.array([0.0, c1])
            if w2.sum() == 0:
                w2 = np.array([1.0, 0.0])
            wts.append([float(w2[0]), float(w2[1])])
        if trees:
            tp = booster.predict(Xr[rt]).reshape(len(te), N)
            preds["gbm_a"].append(tp)
            preds["stack_w"].append(w2[0] * preds["block_cv"][-1] + w2[1] * tp)
    days = np.concatenate(days)
    for name, pl in preds.items():
        res[name] = score(np.concatenate(pl), days, P, R, u, c, 5)
    res.update(block_penalties=picks, stack_weights=wts, seconds=time.time() - t0)
    return res


if __name__ == "__main__":
    from multiprocessing import Pool
    out, which, npanel = sys.argv[1], sys.argv[2], int(sys.argv[3])
    typs = sys.argv[4].split(","); betas = [float(x) for x in sys.argv[5].split(",")]
    base, nproc = int(sys.argv[6]), int(sys.argv[7])
    tasks = [(base + i, t, bb, which) for t in typs for bb in betas for i in range(npanel)]
    with Pool(nproc) as pool, open(out, "w") as fh:
        for r in pool.imap_unordered(run, tasks):
            fh.write(json.dumps(r) + "\n"); fh.flush()
