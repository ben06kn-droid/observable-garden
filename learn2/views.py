"""Views, averaged books, streams and the menu tier (note, C, E, F).

A view = (information, horizon, neutrality, regime). Its book is the equal-weight average
of nine variants (trading rate a in {1.0, 0.3, 0.1} x memory in {roll252, roll756,
expand}), each variant's book being new = (1 - a) old + a target from 0 at the view's first
scored row; the average is regime-gated (0 while the regime is off), not rescaled, and
costed once.
"""
from __future__ import annotations

import itertools

import numpy as np

from learn2 import learner as Ln
from learn2 import states as S
from learn2 import timing

RATES = (1.0, 0.3, 0.1)
RATE_GRIDS = {"G1": (1.0, 0.3, 0.1), "G2": (0.5, 0.2, 0.1), "G3": (0.3, 0.1, 0.03)}
HORIZONS = (1, 5, 20)
NEUTRALITY = ("market", "group")
MEMORIES = tuple(Ln.MEMORIES)


def informations(available: tuple) -> list[tuple]:
    out = []
    for n in range(1, len(available) + 1):
        out += list(itertools.combinations(available, n))
    return out


def all_views(available: tuple) -> list[tuple]:
    return [(i, h, n, r) for i in informations(available) for h in HORIZONS for n in NEUTRALITY
            for r in S.REGIMES]


def base_view(available: tuple) -> tuple:
    return (tuple(available), 5, "market", "always")


def target_positions(pred: np.ndarray, neutrality: str, groups: np.ndarray | None,
                     refit_of: np.ndarray) -> np.ndarray:
    """Demeaned (across all, or within the refit row's groups), unit gross; 0 where no
    prediction."""
    T, M = pred.shape
    p = np.nan_to_num(pred)
    if neutrality == "group":
        out = np.zeros_like(p)
        for s0 in np.unique(refit_of[refit_of >= 0]):
            rows = refit_of == s0
            g = groups[s0]
            for lab in np.unique(g):
                m = g == lab
                blk = p[np.ix_(rows, m)]
                out[np.ix_(rows, m)] = blk - blk.mean(axis=1, keepdims=True)
    else:
        out = p - p.mean(axis=1, keepdims=True)
    out[refit_of < 0] = 0.0
    gross = np.abs(out).sum(axis=1, keepdims=True)
    return np.where(gross > 0, out / np.where(gross > 0, gross, 1.0), 0.0)


def rate_book(target: np.ndarray, a: float, first: int) -> np.ndarray:
    book = np.zeros_like(target)
    prev = np.zeros(target.shape[1])
    for t in range(first, target.shape[0]):
        prev = (1 - a) * prev + a * target[t]
        book[t] = prev
    return book


class FitCache:
    """Fits by (information, horizon, neutrality, memory)."""

    def __init__(self, inp: Ln.Inputs, grids: dict | None = None):
        self.inp = inp
        self.grids = grids
        self.fits: dict = {}
        self.targets: dict = {}

    def target(self, info, h, neutrality, memory) -> np.ndarray:
        key = (tuple(info), h, neutrality, memory)
        if key not in self.targets:
            f = self.get(info, h, neutrality, memory)
            self.targets[key] = target_positions(f["pred"], neutrality, self.inp.groups, f["refit_of"])
        return self.targets[key]

    def get(self, info, h, neutrality, memory) -> dict:
        key = (tuple(info), h, neutrality, memory)
        if key not in self.fits:
            self.fits[key] = Ln.fit_cell(self.inp, info, h, neutrality, memory, self.grids)
        return self.fits[key]


def variant_books(cache: FitCache, info, h, neutrality, rates=RATES, memories=MEMORIES) -> dict:
    """{(a, memory): book}, all from the view's first scored row."""
    first = Ln.FIRST + timing.embargo(h, cache.inp.d)
    out = {}
    for mem in memories:
        tgt = cache.target(info, h, neutrality, mem)
        for a in rates:
            out[(a, mem)] = rate_book(tgt, a, first)
    return out


def view_book(cache: FitCache, view: tuple, gates: dict | None = None, rates=RATES,
              memories=MEMORIES) -> dict:
    info, h, neutrality, regime = view
    vb = variant_books(cache, info, h, neutrality, rates, memories)
    book = np.mean(np.stack(list(vb.values())), axis=0)
    if gates is None:
        gates = S.regime_gates(S.market_states(cache.inp.earned, cache.inp.d))
    book = book * gates[regime][:, None]
    first = Ln.FIRST + timing.embargo(h, cache.inp.d)
    keys = list(vb)
    flat = [vb[k][first:].ravel() for k in keys]
    corr = np.corrcoef(np.stack(flat)) if all(f.std() > 0 for f in flat) else None
    # (with fewer memories the correlation matrix is smaller: len(rates) * len(memories))
    return {"book": book, "first": first, "variants": vb, "variant_keys": keys,
            "variant_corr": corr}


def net_stream(book: np.ndarray, inp: Ln.Inputs, rows: np.ndarray) -> np.ndarray:
    """Net return of the book on `rows`, continuous from zero at rows[0]."""
    p = book[rows]
    prev = np.vstack([np.zeros((1, p.shape[1])), p[:-1]])
    gross = (p * inp.earned[rows]).sum(axis=1)
    cost = (np.abs(p - prev) * inp.cost_rate[rows]).sum(axis=1) + \
        (np.clip(-p, 0, None) * inp.borrow_rate[rows]).sum(axis=1)
    return gross - cost


def turnover_stats(book: np.ndarray, inp: Ln.Inputs, rows: np.ndarray) -> dict:
    """Raw and per-unit-gross turnover and cost (note, decision 9)."""
    p = book[rows]
    dw = np.abs(np.diff(p, axis=0)).sum(axis=1)
    gross = np.abs(p).sum(axis=1)
    cost = (np.abs(np.diff(p, axis=0)) * inp.cost_rate[rows][1:]).sum(axis=1)
    return {"turnover_per_row": float(dw.mean()), "mean_gross": float(gross.mean()),
            "turnover_per_unit_gross": float(dw.sum() / gross[1:].sum()) if gross[1:].sum() > 0 else 0.0,
            "cost_per_year": float(cost.mean() * inp.ppy)}


def menu_null(streams: np.ndarray, base_columns: np.ndarray, ppy: float, B: int, seed: int):
    """(M_b, block length): the joint-bootstrap maximum over all views' demeaned streams."""
    from learn import stream_tier
    table = stream_tier.table_from_streams(streams, ppy)
    rows, L = stream_tier.bootstrap_rows(base_columns, B, seed)
    return np.asarray(table.null_max(rows), float), L


def menu_p(streams: np.ndarray, chosen: int, base_columns: np.ndarray, ppy: float, B: int,
           seed: int) -> dict:
    """The menu tier's p for the chosen view: (1 + #{M_b >= its observed Sharpe}) / (B + 1)."""
    s = streams[chosen]
    sd = s.std(ddof=1)
    S_obs = float(s.mean() / sd * np.sqrt(ppy)) if sd > 0 else 0.0
    M_b, L = menu_null(streams, base_columns, ppy, B, seed)
    return {"p": (1 + int(np.sum(M_b >= S_obs))) / (B + 1), "score": S_obs, "block_length": L,
            "null_max": M_b}
