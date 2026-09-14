"""Searcher ABC. Every searcher runs against the same Sandbox contract
(environments/sandbox.py) — this is also the eventual API for an LLM agent
(spec §3.2, §3.3): no changes to the sandbox or the transcript logging when
swapping the searcher out."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

import numpy as np

from environments.sandbox import Sandbox


class Searcher(ABC):
    name: str = "searcher"

    def __init__(self, seed: int = 0):
        self.seed = seed

    @abstractmethod
    def run(self, sandbox: Sandbox) -> None:
        """Evaluate zero or more Specifications against `sandbox`, then call
        sandbox.submit(...) exactly once."""
        raise NotImplementedError


@runtime_checkable
class Replayable(Protocol):
    """A searcher whose decision rule can be re-derived from a resampled set
    of base return columns, without re-invoking the sandbox. Required for
    estimator/recursive_bootstrap.py: it re-runs a search's OWN selection
    logic inside every bootstrap replicate (Efron 2014's prescription for
    post-selection bootstraps) rather than freezing that selection at its
    value on the real data (see SCOPE.md for why the naive bootstrap fails
    on sequentially-adaptive search and this fixes it)."""

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        """base_columns: (T, K) return columns, one per feature, in the same
        order/orientation as Sandbox.base_feature_columns() -- possibly
        resampled. Returns the Sharpe this searcher's decision rule would
        submit on this data, without touching a Sandbox."""
        ...
