"""Searcher ABC. Every searcher runs against the same Sandbox contract
(environments/sandbox.py) — this is also the eventual API for an LLM agent
(spec §3.2, §3.3): no changes to the sandbox or the transcript logging when
swapping the searcher out."""
from __future__ import annotations

from abc import ABC, abstractmethod

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
