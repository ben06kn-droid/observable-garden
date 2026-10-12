"""The full-class null: the Reality Check over every specification a declared class contains.

If every specification a search could have produced lies in a class fixed before the search, the
maximum over that class is at least the search's selected value, and the class does not depend on the
data. Running the realized-menu bootstrap (estimator.bootstrap) over the whole class is then valid
however adaptively the search chose what to evaluate. For equal-weight feature subsets of size at most
d, the class can be enumerated from the base columns alone, so a transcript plus a class declaration is
enough: no replay and no re-execution.
"""
from __future__ import annotations

import itertools

import numpy as np


def subsets_up_to(K: int, d: int) -> list[tuple[int, ...]]:
    return [subset for size in range(1, d + 1) for subset in itertools.combinations(range(K), size)]


def full_class_matrix(base_columns: np.ndarray, d: int) -> np.ndarray:
    """(T, number of subsets): one column per feature subset of size 1..d, the sum of its base columns.
    Sums match how Specification weights compose, since Sandbox.evaluate is linear in the weights."""
    base = np.asarray(base_columns, dtype=float)
    K = base.shape[1]
    subsets = subsets_up_to(K, d)
    membership = np.zeros((K, len(subsets)))
    for column, subset in enumerate(subsets):
        membership[list(subset), column] = 1.0
    return base @ membership
