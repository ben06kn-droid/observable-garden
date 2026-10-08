"""Leak tests for version 2 (note, G): positions up to row t must be bit-identical when
every input after row t is replaced."""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from learn2.learner import Inputs


def perturb_after(inp: Inputs, t: int, rng: np.random.Generator) -> Inputs:
    def noisy(a):
        a = np.array(a, copy=True)
        a[t + 1:] = rng.standard_normal(a[t + 1:].shape) * (np.nanstd(a) + 1e-3)
        return a
    groups = None
    if inp.groups is not None:
        groups = inp.groups.copy()
        groups[t + 1:] = rng.integers(0, 5, size=groups[t + 1:].shape)
    return replace(inp, P=noisy(inp.P) if inp.P is not None else None, earned=noisy(inp.earned),
                   blocks={k: noisy(v) for k, v in inp.blocks.items()}, groups=groups)


def leak_view(book_fn, inp: Inputs, rows_t, seed: int = 0) -> list[dict]:
    """`book_fn(inputs) -> (T, M) book`. For each t: rows <= t identical, and some row
    after t changed (the test can see a change)."""
    base = book_fn(inp)
    rng = np.random.default_rng(seed)
    out = []
    for t in rows_t:
        alt = book_fn(perturb_after(inp, int(t), rng))
        out.append({"t": int(t), "identical_up_to_t": bool(np.array_equal(base[:t + 1], alt[:t + 1])),
                    "changed_after_t": bool(not np.array_equal(base[t + 1:], alt[t + 1:]))})
    return out


def leak_block(build, args: tuple, rows_t, seed: int = 0, which: int = 0) -> list[dict]:
    """A block builder: `build(*args)` with args[which] (a (T, ...) array) replaced after t;
    the output's rows <= t must be identical."""
    base = build(*args)
    base = base[0] if isinstance(base, tuple) else base
    rng = np.random.default_rng(seed)
    out = []
    for t in rows_t:
        a = list(args)
        x = np.array(a[which], dtype=float, copy=True)
        x[t + 1:] = np.abs(rng.standard_normal(x[t + 1:].shape)) + 0.5
        a[which] = x
        alt = build(*a)
        alt = alt[0] if isinstance(alt, tuple) else alt
        out.append({"t": int(t), "identical_up_to_t": bool(np.array_equal(base[:t + 1], alt[:t + 1])),
                    "changed_after_t": bool(not np.array_equal(base[t + 1:], alt[t + 1:]))})
    return out
