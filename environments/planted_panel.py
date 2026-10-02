"""7.5's planted panel: real ETF features, a resampled real residual, one planted member.

`prereg/planted-edge.md` registers the construction; this module is it.

- **Features**: the real ETF feature matrix X, rows in calendar order, never resampled.
- **Residual**: E = R - mean_t(R), the segment's real earned-return matrix demeaned per
  asset. A stationary block bootstrap draws **whole rows of E** (every asset on one day
  together), independently of X: row t of a panel pairs `X_t` with `E[idx_t]`.
  **It never resamples joint (X, r) rows.** No real feature-return relation survives.
- **Planted signal**: `r_t = E[idx_t] + c * w*_t`, where `w*` is the planted member's
  own sandbox weight path. `c` is set so the member's **population** net Sharpe equals
  the level; level 0 is `c = 0`, the residual alone.
- **Population Sharpe** of any specification: expectation over standard deviation of
  its per-period net return under this DGP, computed analytically (`population_sharpe`).
  The stationary bootstrap's marginal draw is uniform over the pool, and E is demeaned,
  so `E<w, e> = 0` and `Var<w, e> = w' Sigma w` with `Sigma = E'E / T` (ddof 0) exactly.

Seeds: `SeedSequence(seed).spawn(3)` -> [0] in-sample indices, [1] planted member and
masking permutation, [2] holdout indices. A seed fixes all three, so the levels of one
seed are paired on the same residual draw and the same planted member.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from environments.class_table import members_in_order
from estimator.bootstrap import stationary_bootstrap_indices
from garden.spec_class import SubsetClass

CLS = SubsetClass(max_size=3, signed=True)
IS_END = dt.date(2017, 12, 31)
HO_START, HO_END = dt.date(2018, 1, 1), dt.date(2022, 12, 31)
LEVELS = (0.0, 0.5, 1.0, 1.5)
# select_block_length on the in-sample E, measured 2026-10-01 and registered; fixed
# here rather than recomputed so a change to the selector cannot move the DGP
BLOCK_LENGTH = 7

# THE PINNED FEATURE MATRIX. `environments.real_panel._rank` breaks exact ties with
# numpy's default (unstable) argsort, whose tie order differs between platforms: on
# 2026-10-02 an x86 build (c7a.48xlarge) and the arm64 laptop build differed in
# `ret1_rank` and `drawdown_rank`. So "the real ETF feature matrix" is a FILE, built on
# the laptop (arm64, Python 3.14.2, numpy 2.5.3) -- the X the preflight, the design
# analysis and every smoke used -- and identified by its SHA-256. The generator loads it
# and REFUSES on a missing file or a hash mismatch; there is no rebuild fallback, because
# a rebuild on another platform is a different panel that would pass every other check.
PINNED_X = Path(__file__).resolve().parent.parent / "data" / "pinned" / "etf_features_X.npy"
PINNED_X_SHA256 = "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba"
PINNED_X_SHAPE = (4276, 40, 40)


def pinned_features(path=None, sha256: str = PINNED_X_SHA256,
                    shape: tuple = PINNED_X_SHAPE) -> np.ndarray:
    """The pinned X, or a refusal. Never rebuilds."""
    import hashlib
    path = Path(path) if path is not None else PINNED_X
    if not path.exists():
        raise SystemExit(
            f"pinned feature matrix missing: {path}. It is not rebuilt here, because a "
            "rebuild on another platform breaks rank ties differently and is a different "
            "panel (prereg/planted-edge.md). Copy the pinned file; its SHA-256 is "
            f"{sha256}.")
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != sha256:
        raise SystemExit(f"pinned feature matrix {path} has SHA-256 {got}, not the "
                         f"registered {sha256}. Refused; there is no rebuild fallback.")
    X = np.load(path)
    if tuple(X.shape) != tuple(shape):
        raise SystemExit(f"pinned feature matrix has shape {X.shape}, not {shape}")
    return X


# -- segments and the residual ---------------------------------------------

def cut(panel, mask: np.ndarray):
    """The panel's rows where `mask` holds, in order, every per-row array cut alike."""
    d = np.array(panel.meta["dates"]) if "dates" in panel.meta else None
    return replace(panel, features=panel.features[mask], returns=panel.returns[mask],
                   tradable=panel.tradable[mask], cost_rate=panel.cost_rate[mask],
                   borrow_rate=panel.borrow_rate[mask],
                   session_start=panel.session_start[mask],
                   session_end=panel.session_end[mask], present=panel.present[mask],
                   meta={**panel.meta, **({"dates": list(d[mask])} if d is not None else {})})


def split(panel):
    """(in-sample 2005-2017, planted holdout 2018-2022), both already-open years."""
    d = np.array(panel.meta["dates"])
    return (cut(panel, np.array([x <= IS_END for x in d])),
            cut(panel, np.array([HO_START <= x <= HO_END for x in d])))


def residual(panel) -> np.ndarray:
    R = np.asarray(panel.returns, dtype=float)
    return R - R.mean(axis=0, keepdims=True)


def pool_covariance(E: np.ndarray) -> np.ndarray:
    """`E'E / T`: the exact covariance of one row drawn uniformly from the pool."""
    return (E.T @ E) / E.shape[0]


# -- weights, costs, and the population Sharpe -------------------------------

def member_weights(panel, support) -> np.ndarray:
    K = panel.features.shape[2]
    wf = np.zeros(K)
    for k, s in support:
        wf[int(k)] = float(s)
    return panel.weights_from(panel.features @ wf)


def cost_borrow(panel, w: np.ndarray) -> np.ndarray:
    """Per-period cost plus borrow of a weight path: `RealPanel.net_stream` with the
    return term removed."""
    prev = np.vstack([np.zeros((1, w.shape[1])), w[:-1]])
    return (np.einsum("tm,tm->t", np.abs(w - prev), panel.cost_rate)
            + np.einsum("tm,tm->t", np.clip(-w, 0, None), panel.borrow_rate))


def population_moments(panel, Sigma, w_m, w_star, c) -> tuple[float, float]:
    """(mean, variance) of the member's per-period net return under the DGP.

    d_t = c <w_m,t, w*_t> - cost_t - borrow_t is deterministic given X; the residual
    term has mean 0 and variance w_m,t' Sigma w_m,t; t is uniform over the segment."""
    d = c * np.einsum("tm,tm->t", w_m, w_star) - cost_borrow(panel, w_m)
    v = float(np.einsum("tm,mn,tn->t", w_m, Sigma, w_m).mean() + d.var())
    return float(d.mean()), v


def population_sharpe(panel, Sigma, w_m, w_star, c) -> float:
    m, v = population_moments(panel, Sigma, w_m, w_star, c)
    return m / np.sqrt(v) * np.sqrt(panel.periods_per_year)


def population_sharpes(panel, Sigma, w_star, c, supports) -> np.ndarray:
    """`population_sharpe` for many members at once, through the batched position
    loop `environments.class_table.streams_for` uses. Equal to the per-member path to
    floating-point accumulation (`tests/test_planted_panel.py`)."""
    T, M, K = panel.features.shape
    n = len(supports)
    Wf = np.zeros((K, n))
    for j, sup in enumerate(supports):
        for k, s in sup:
            Wf[int(k), j] = float(s)
    d = np.empty((n, T))
    q = np.zeros(n)
    held = np.zeros((n, M))
    prev = np.zeros((n, M))
    flat = bool(panel.flat_overnight)
    for t in range(T):
        free = panel.tradable[t]
        if flat and panel.session_start[t]:
            held = np.zeros((n, M))
        target = np.where(free, (panel.features[t] @ Wf).T, 0.0)
        if free.any():
            target = target - target[:, free].mean(axis=1, keepdims=True) * free
            gross = np.abs(target[:, free]).sum(axis=1, keepdims=True)
            nz = gross[:, 0] > 0
            target[nz] = target[nz] / gross[nz]
        new = np.where(free, target, held)
        if flat and panel.session_end[t]:
            new = np.zeros((n, M))
        d[:, t] = (c * (new @ w_star[t])
                   - (np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
                   - (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        q += np.einsum("nm,mk,nk->n", new, Sigma, new)
        held = prev = new
    v = q / T + d.var(axis=1)
    return d.mean(axis=1) / np.sqrt(v) * np.sqrt(panel.periods_per_year)


def planted_scale(panel, Sigma, w_star, beta: float) -> float:
    """c with population Sharpe of the planted member equal to `beta`; 0 at level 0."""
    if beta == 0.0:
        return 0.0
    f = lambda c: population_sharpe(panel, Sigma, w_star, w_star, c) - beta
    hi = 1e-4
    while f(hi) < 0:
        hi *= 2
    return float(brentq(f, 0.0, hi, xtol=1e-14))


# -- seeds -------------------------------------------------------------------

def children(seed: int):
    """[0] in-sample indices, [1] planted member then masking, [2] holdout indices.
    `spawn(3)[i]` equals `spawn(2)[i]` for i < 2, so the preflight's draws carry over."""
    return np.random.SeedSequence(int(seed)).spawn(3)


def planted_member(seed: int, members) -> tuple:
    """Uniform over the class's depth-3 members, from child [1]."""
    rng = np.random.default_rng(children(seed)[1])
    d3 = [m for m in members if len(m) == 3]
    return d3[int(rng.integers(len(d3)))]


def masking_permutation(seed: int, K: int) -> np.ndarray:
    """The agent-facing label permutation: child [1]'s stream after the member draw."""
    from math import comb
    rng = np.random.default_rng(children(seed)[1])
    rng.integers(8 * comb(K, 3))                          # the member draw, consumed
    return rng.permutation(K)


# -- one panel ---------------------------------------------------------------

@dataclass
class Base:
    in_sample: object
    holdout: object
    E_is: np.ndarray
    E_ho: np.ndarray
    Sigma_is: np.ndarray
    Sigma_ho: np.ndarray
    members: list


@lru_cache(maxsize=1)
def load_base() -> Base:
    """The ETF panel with its features REPLACED by the pinned X. Returns, costs and
    dates come from the build (element-wise arithmetic on the same prices, with no
    sort); only the features carry the platform-dependent ties, and they are pinned."""
    from environments.real_panel import build_etf_panel
    panel = build_etf_panel()
    X = pinned_features(shape=panel.features.shape)
    return base_from(replace(panel, features=X))


def base_from(panel) -> Base:
    is_p, ho_p = split(panel)
    E_is, E_ho = residual(is_p), residual(ho_p)
    return Base(is_p, ho_p, E_is, E_ho, pool_covariance(E_is), pool_covariance(E_ho),
                members_in_order(CLS, is_p.features.shape[2]))


@dataclass
class PlantedDraw:
    seed: int
    beta: float
    c: float
    m_star: tuple
    in_sample: object          # RealPanel, planted returns
    holdout: object            # RealPanel, planted returns, same m* and c
    w_star_is: np.ndarray
    w_star_ho: np.ndarray
    idx_is: np.ndarray
    idx_ho: np.ndarray


def make_draw(base: Base, seed: int, beta: float,
              block_length: int = BLOCK_LENGTH) -> PlantedDraw:
    m_star = planted_member(seed, base.members)
    w_is = member_weights(base.in_sample, m_star)
    w_ho = member_weights(base.holdout, m_star)
    c = planted_scale(base.in_sample, base.Sigma_is, w_is, beta)
    ch = children(seed)
    idx_is = stationary_bootstrap_indices(base.E_is.shape[0], block_length,
                                          np.random.default_rng(ch[0]))
    idx_ho = stationary_bootstrap_indices(base.E_ho.shape[0], block_length,
                                          np.random.default_rng(ch[2]))
    return PlantedDraw(
        seed=seed, beta=beta, c=c, m_star=m_star,
        in_sample=replace(base.in_sample, returns=base.E_is[idx_is] + c * w_is),
        holdout=replace(base.holdout, returns=base.E_ho[idx_ho] + c * w_ho),
        w_star_is=w_is, w_star_ho=w_ho, idx_is=idx_is, idx_ho=idx_ho)


def truth(base: Base, draw: PlantedDraw, support) -> dict:
    """A specification's population net Sharpe on both segments under this draw's DGP."""
    return {"in_sample": population_sharpe(base.in_sample, base.Sigma_is,
                                           member_weights(base.in_sample, support),
                                           draw.w_star_is, draw.c),
            "holdout": population_sharpe(base.holdout, base.Sigma_ho,
                                         member_weights(base.holdout, support),
                                         draw.w_star_ho, draw.c)}


# -- every member's population Sharpe, once per seed, in closed form ----------
#
# For member m with weights w_t, overlap a_t = <w_t, w*_t> and cost-plus-borrow k_t:
#     d_t(c) = c a_t - k_t
#     mean(c) = c E[a] - E[k]
#     var(c)  = E[w' Sigma w] + c^2 Var(a) - 2c Cov(a, k) + Var(k)
# (t uniform over the segment, population moments). E[k], E[k^2] and E[w' Sigma w]
# depend only on X, Sigma and the costs: PANEL-INVARIANT, computed once per run.
# E[a], E[a^2] and E[a k] depend on w*, so once per SEED, and they are accumulated
# inside the class pass's own position loop (`streams_with_overlap`). Every level then
# follows in closed form, with no further pass.

def _positions_loop(panel, supports, on_step):
    """`environments.class_table.streams_for`'s position loop, verbatim, calling
    `on_step(t, new, prev)` each period. Kept identical so that anything computed
    beside the streams sees exactly the positions the streams were made from."""
    T, M, K = panel.features.shape
    n = len(supports)
    Wf = np.zeros((K, n))
    for j, sup in enumerate(supports):
        for k, s in sup:
            Wf[int(k), j] = float(s)
    held = np.zeros((n, M))
    prev = np.zeros((n, M))
    flat = bool(panel.flat_overnight)
    for t in range(T):
        free = panel.tradable[t]
        if flat and panel.session_start[t]:
            held = np.zeros((n, M))
        target = np.where(free, (panel.features[t] @ Wf).T, 0.0)
        if free.any():
            target = target - target[:, free].mean(axis=1, keepdims=True) * free
            gross = np.abs(target[:, free]).sum(axis=1, keepdims=True)
            nz = gross[:, 0] > 0
            target[nz] = target[nz] / gross[nz]
        new = np.where(free, target, held)
        if flat and panel.session_end[t]:
            new = np.zeros((n, M))
        on_step(t, new, prev)
        held = prev = new


def invariant_moments(panel, Sigma, supports) -> dict:
    """E[k], E[k^2] and E[w' Sigma w] per member: the panel-invariant moments."""
    n = len(supports)
    Lc = np.linalg.cholesky(Sigma)
    sk, sk2, sq = np.zeros(n), np.zeros(n), np.zeros(n)

    def step(t, new, prev):
        k = ((np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
             + (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        sk[:] += k
        sk2[:] += k * k
        P = new @ Lc
        sq[:] += (P * P).sum(axis=1)

    _positions_loop(panel, supports, step)
    T = panel.features.shape[0]
    return {"Ek": sk / T, "Ek2": sk2 / T, "Eq": sq / T}


def streams_with_overlap(panel, supports, w_star):
    """(streams, E[a], E[a^2], E[a k]) for a batch of members. The streams are
    `streams_for`'s, bit for bit: the same loop and the same expression, evaluated
    in the same order (`tests/test_planted_panel.py`)."""
    T = panel.features.shape[0]
    n = len(supports)
    out = np.empty((n, T))
    sa, sa2, sak = np.zeros(n), np.zeros(n), np.zeros(n)

    def step(t, new, prev):
        gross = (new * panel.returns[t]).sum(axis=1)
        cost = (np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
        borrow = (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1)
        out[:, t] = gross - cost - borrow
        a = new @ w_star[t]
        sa[:] += a
        sa2[:] += a * a
        sak[:] += a * (cost + borrow)

    _positions_loop(panel, supports, step)
    return out, sa / T, sa2 / T, sak / T


def population_from_moments(Ea, Ea2, Eak, inv: dict, c: float, ppy: float) -> np.ndarray:
    """Every member's population Sharpe at planted scale c, in closed form."""
    mean = c * Ea - inv["Ek"]
    var = (inv["Eq"] + c * c * (Ea2 - Ea * Ea) - 2 * c * (Eak - Ea * inv["Ek"])
           + (inv["Ek2"] - inv["Ek"] ** 2))
    return mean / np.sqrt(var) * np.sqrt(ppy)


def invariants_for(base: Base, chunk: int = 512, cache_dir=None) -> dict:
    """The panel-invariant moments for every class member, cached on disk keyed by
    the in-sample panel's hash and Sigma, so a run computes them once and every
    worker loads them."""
    import hashlib
    from pathlib import Path
    from environments.class_table import _panel_hash
    key = hashlib.sha256((_panel_hash(base.in_sample) + CLS.name).encode()
                         + np.ascontiguousarray(base.Sigma_is).tobytes()).hexdigest()[:16]
    d = Path(cache_dir) if cache_dir else Path(__file__).resolve().parent.parent / \
        "data" / "planted_cache"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"invariants_{key}.npz"
    if f.exists():
        z = np.load(f)
        return {k: z[k] for k in ("Ek", "Ek2", "Eq")}
    parts = [invariant_moments(base.in_sample, base.Sigma_is, base.members[s:s + chunk])
             for s in range(0, len(base.members), chunk)]
    inv = {k: np.concatenate([p[k] for p in parts]) for k in ("Ek", "Ek2", "Eq")}
    tmp = f.with_name(f".{f.stem}.{__import__('os').getpid()}.tmp.npz")
    np.savez(tmp, **inv)
    __import__("os").replace(tmp, f)
    return inv
