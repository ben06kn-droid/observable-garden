"""Declared specification classes: every specification a search could have produced.

A class is written as a string and parsed through a small registry, so more classes can be added later.
One is registered, the class THEORY.md's P3 and P5 cover and the only one that can be enumerated from
base returns:

    subsets:max_size=d              unit weights on 1..d features, summed (weights in {0, 1})
    subsets:max_size=d,signs=both   unit weights of either sign (weights in {-1, 0, 1})

"none" declares no class. The weight convention is the sum, matching Specification weights built by the
searchers (a mean would be a different class, although Sharpe ratios are identical under both).

A second kind covers classes that cannot be built from base returns at all, such as the crossover rules
of non-additive-scoring's prereg, f298103, whose positions are signs of moving-average differences rather than weight vectors:

    explicit                        the supplier hands over every member's return stream directly
    explicit:members=M              the same, asserting the class holds exactly M members

Membership there is by specification id, not by weight vector, so ExplicitClass has no contains(weights):
garden/transcript.py checks that every logged spec_id appears among the supplied class_ids and that each
logged return column matches its class column. This is the Sullivan-Timmermann-White setup, and it is
only as good as the declaration: a class assembled after seeing results is snooping, which is what
spec_class_source records.
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


@dataclass(frozen=True)
class ExplicitClass:
    """A class supplied as return streams rather than described algebraically. `n_members` is an optional
    assertion checked against the supplied columns."""
    n_members: int | None = None

    @property
    def name(self) -> str:
        return "explicit" if self.n_members is None else f"explicit:members={self.n_members}"

    def size(self, K: int | None = None) -> int | None:
        """The class's size comes from the supplied columns, not from a feature count."""
        return self.n_members


@dataclass(frozen=True)
class ClassLadder:
    """Nested classes Theta_1 subset Theta_2 subset ... declared together, up front.

    The bar is priced once, over the union (the largest level), so climbing the
    ladder changes nothing about what the search is held to. A searcher can work
    a small class first and expand later without the critical value moving. The
    benefit is computational and organizational, never statistical.

    Not a registry class, and deliberately not parseable from a string: a
    transcript records the *union*, because the union is what the declaration
    means for inference. garden/watch.py keeps the level structure as its own
    layer. See its `open` for why the sandbox is handed `union` rather than the
    ladder itself."""
    levels: tuple[SubsetClass, ...]

    def __post_init__(self):
        if len(self.levels) < 2:
            raise ValueError("a ladder needs at least two levels; use the class itself otherwise")
        for lower, upper in zip(self.levels, self.levels[1:]):
            if lower == upper:
                raise ValueError(f"ladder levels must be strictly nested; {lower.name} repeats")
            if not _nested(lower, upper):
                raise ValueError(
                    f"ladder levels must be nested: {lower.name} is not contained in {upper.name}"
                )

    @property
    def name(self) -> str:
        return " < ".join(level.name for level in self.levels)

    @property
    def union(self) -> SubsetClass:
        """The largest level. Every member of every level lies in it, so it is
        what the null maximum is taken over and what a transcript declares."""
        return self.levels[-1]

    def size(self, K: int) -> int:
        return self.union.size(K)

    def contains(self, weights) -> bool:
        return self.union.contains(weights)

    def level_of(self, weights) -> int | None:
        """Index of the smallest level holding these weights, or None if the
        specification lies outside the ladder entirely."""
        for i, level in enumerate(self.levels):
            if level.contains(weights):
                return i
        return None


def _nested(lower: SubsetClass, upper: SubsetClass) -> bool:
    """Is every member of `lower` also a member of `upper`?

    A subset class is fixed by two knobs: how many features a member may carry,
    and whether negative weights are allowed. Widening either can only add
    members, so containment is the conjunction of the two comparisons."""
    if lower.max_size > upper.max_size:
        return False
    return upper.signed or not lower.signed


def _explicit(params: dict[str, str]) -> ExplicitClass:
    unknown = set(params) - {"members"}
    if unknown:
        raise ValueError(f"unknown explicit parameter(s): {', '.join(sorted(unknown))}")
    if "members" not in params:
        return ExplicitClass()
    try:
        members = int(params["members"])
    except ValueError:
        raise ValueError(f"members must be an integer, got {params['members']!r}") from None
    if members < 1:
        raise ValueError("members must be at least 1")
    return ExplicitClass(n_members=members)


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


REGISTRY: dict[str, Callable[[dict[str, str]], SubsetClass | ExplicitClass]] = {
    "subsets": _subsets, "explicit": _explicit,
}


def parse(spec: str) -> SubsetClass | ExplicitClass | None:
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
