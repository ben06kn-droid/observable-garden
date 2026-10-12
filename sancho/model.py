"""Sancho, run under a config (`sancho/config.py`).

`run(inputs, config)` applies every lever and runs the registered pipeline: the base view's
fits for each memory, the variant books at each rate, averaged, regime-gated. With the default
config it is bit-identical to the registered runner (research's
`experiments.binance_design_v2.book_of` under `configure("carried")`; tested).

The learner reads some levers from module constants (`learner.FIRST`, `REFIT`, `WARMUP`,
`MEMORIES`, `TREES`, `NTREE`, `LIGHTGBM`). `run` sets them for the call and restores them after,
so nothing leaks into the next call.
"""
from __future__ import annotations

import contextlib
import time

import numpy as np

from sancho import config as _config
from sancho import learner as Ln
from sancho import views as Vw

BLOCK_ORDER = ("P", "X", "V", "F")


def _need_lightgbm(version: str) -> None:
    try:
        import lightgbm
    except ImportError as e:
        raise RuntimeError(f"Sancho needs LightGBM {version}: install the optional extra "
                           f"`pip install -e '.[sancho]'`") from e
    if lightgbm.__version__ != version:
        raise RuntimeError(f"Sancho needs LightGBM {version}; this environment has {lightgbm.__version__}")


@contextlib.contextmanager
def _levers(v: dict):
    saved = {k: getattr(Ln, k) for k in ("FIRST", "REFIT", "WARMUP", "MEMORIES", "TREES", "NTREE", "LIGHTGBM")}
    try:
        Ln.FIRST = int(v["first_scored_row"])
        Ln.REFIT = int(v["refit_every"])
        Ln.WARMUP = int(v["warmup_rows"])
        Ln.MEMORIES = {"roll252": 252, "roll756": 756, "expand": None, **v["memories"]}
        Ln.TREES = dict(v["trees"]["params"])
        Ln.NTREE = int(v["trees"]["rounds"])
        Ln.LIGHTGBM = str(v["trees"]["lightgbm"])
        yield
    finally:
        for k, x in saved.items():
            setattr(Ln, k, x)


def information(inp: Ln.Inputs, v: dict) -> tuple:
    avail = inp.available
    want = v["information"]
    if want == "all":
        return tuple(avail)
    missing = [b for b in want if b not in avail]
    if missing:
        raise ValueError(f"information {want}: blocks {missing} are not in these inputs (have {avail})")
    return tuple(b for b in BLOCK_ORDER if b in want)


def run(inputs: Ln.Inputs, config: _config.Config | None = None) -> tuple[np.ndarray, int, dict]:
    """(book (T, M), first scored row, meta). meta records the config's SHA-256 and whether it is
    the default."""
    cfg = config or _config.load()
    v = cfg.values
    _need_lightgbm(str(v["trees"]["lightgbm"]))
    grids = {b: tuple(float(x) for x in g) for b, g in v["ridge"]["grids"].items()}
    rates = tuple(float(a) for a in v["rates"])
    memories = tuple(v["memories"])
    h, neutrality, regime = int(v["horizon"]), str(v["neutrality"]), str(v["regime"])
    with _levers(v):
        cache = Vw.FitCache(inputs, grids=grids)
        info = information(inputs, v)
        view = (info, h, neutrality, regime)
        secs = {}
        for mem in memories:
            t0 = time.time()
            cache.get(info, h, neutrality, mem)
            secs[mem] = time.time() - t0
        vb = Vw.view_book(cache, view, rates=rates, memories=memories)
    meta = {"config_sha256": cfg.sha256, "is_default": cfg.is_default, "view": [list(info), h, neutrality, regime],
            "seconds_per_fit": secs}
    return vb["book"], vb["first"], meta
