"""Declared specification classes: every specification a search could have produced.

A class is written as a string and parsed through a small registry, so more classes can be added later.
One is registered, the class THEORY.md's P3 and P5 cover and the only one that can be enumerated from
base returns:

    subsets:max_size=d              unit weights on 1..d features, summed (weights in {0, 1})
    subsets:max_size=d,signs=both   unit weights of either sign (weights in {-1, 0, 1})

"none" declares no class. The weight convention is the sum, matching Specification weights built by the
searchers (a mean would be a different class, although Sharpe ratios are identical under both).
"""
from __future__ import annotations

import itertools
import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

WEIGHT_TOLERANCE = 1e-12


@dataclass(frozen=True)
class SubsetClass:
    max_size: int
    signed: bool = False

    @property
    def name(self) -> str:
        return f"subsets:max_size={self.max_size}" + (",signs=both" if self.signed else "")

    def contains(self, weights) -> bool:
        w = np.asarray(weights, dtype=float)
        active = np.abs(w) > WEIGHT_TOLERANCE
        if not 1 <= int(active.sum()) <= self.max_size:
            return False
        if not np.all(np.abs(np.abs(w[active]) - 1.0) <= WEIGHT_TOLERANCE):
            return False
        return self.signed or bool(np.all(w[active] > 0))

    def size(self, K: int) -> int:
        return sum(math.comb(K, m) * (2 ** m if self.signed else 1) for m in range(1, min(self.max_size, K) + 1))

    def members(self, K: int, m: int) -> tuple[np.ndarray, np.ndarray]:
        """Every member with exactly m features: (feature indices, signs), both of shape (n, m)."""
        idx = np.array(list(itertools.combinations(range(K), m)), dtype=np.int64).reshape(-1, m)
        if not self.signed:
            return idx, np.ones(idx.shape)
        patterns = np.array(list(itertools.product((1.0, -1.0), repeat=m)))
        return np.repeat(idx, len(patterns), axis=0), np.tile(patterns, (len(idx), 1))


def _subsets(params: dict[str, str]) -> SubsetClass:
    unknown = set(params) - {"max_size", "signs"}
    if unknown:
        raise ValueError(f"unknown subsets parameter(s): {', '.join(sorted(unknown))}")
    if "max_size" not in params:
        raise ValueError("subsets needs max_size, e.g. subsets:max_size=3")
    try:
        max_size = int(params["max_size"])
    except ValueError:
        raise ValueError(f"max_size must be an integer, got {params['max_size']!r}") from None
    if max_size < 1:
        raise ValueError("max_size must be at least 1")
    signs = params.get("signs", "positive")
    if signs not in ("positive", "both"):
        raise ValueError(f'signs must be "positive" or "both", got {signs!r}')
    return SubsetClass(max_size=max_size, signed=signs == "both")


REGISTRY: dict[str, Callable[[dict[str, str]], SubsetClass]] = {"subsets": _subsets}


def parse(spec: str) -> SubsetClass | None:
    spec = spec.strip()
    if spec == "none":
        return None
    kind, _, rest = spec.partition(":")
    if kind not in REGISTRY:
        raise ValueError(f"unknown specification class {kind!r}; registered: none, {', '.join(REGISTRY)}")
    params = {}
    for item in filter(None, rest.split(",")):
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError(f"malformed class parameter {item!r}")
        params[key.strip()] = value.strip()
    return REGISTRY[kind](params)
