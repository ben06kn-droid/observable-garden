"""Adaptive searches over a declared grid of moving-average crossover rules.

Unlike searchers/scripted.py, a rule here is not a weight vector over base columns: its position is the
sign of a difference of two moving averages, so its return stream cannot be written as a linear
combination of other rules' streams. That is the point of E20 (prereg/E20.md) -- the recursive bootstrap
cannot reconstruct candidates in this world, so only the procedure-level null and a declared explicit
class apply.

A search reads columns of an already-computed (T, N) matrix of rule returns, so re-executing it against a
nullified surrogate costs one matrix multiply plus the search's own column reads, not a re-simulation.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_FASTS = (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50)
DEFAULT_SLOWS = (10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 175, 200)
COARSE_STEP = 3


class OffGridError(ValueError):
    """A search proposed a rule outside the declared grid, which would break P3."""


@dataclass(frozen=True)
class CrossoverGrid:
    """The declared class: every (fast, slow, long_only) with fast < slow. Rule order is the column order
    of the return matrix and the order of the class's specification ids."""
    fasts: tuple[int, ...] = DEFAULT_FASTS
    slows: tuple[int, ...] = DEFAULT_SLOWS

    @property
    def rules(self) -> tuple[tuple[int, int, bool], ...]:
        return tuple((f, s, lo) for f in self.fasts for s in self.slows if f < s for lo in (False, True))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(f"ma_{f}_{s}_{'long' if lo else 'ls'}" for f, s, lo in self.rules)

    def index_of(self, rule: tuple[int, int, bool]) -> int:
        try:
            return self.rules.index(rule)
        except ValueError:
            raise OffGridError(f"rule {rule} is not on the declared grid") from None

    def slowest_window(self) -> int:
        return max(self.slows)

    def neighbours(self, index: int) -> list[int]:
        """Rules one step away on the declared grid: adjacent fast, adjacent slow, and the other
        long_only setting. Never leaves the grid, so the class stays closed under refinement."""
        fast, slow, long_only = self.rules[index]
        fi, si = self.fasts.index(fast), self.slows.index(slow)
        out = []
        for f in (self.fasts[max(fi - 1, 0)], self.fasts[min(fi + 1, len(self.fasts) - 1)]):
            for s in (self.slows[max(si - 1, 0)], self.slows[min(si + 1, len(self.slows) - 1)]):
                for lo in (long_only, not long_only):
                    if f < s and (f, s, lo) != (fast, slow, long_only):
                        out.append(self.index_of((f, s, lo)))
        return sorted(set(out))

    def coarse(self, step: int = COARSE_STEP) -> list[int]:
        """The round-1 menu: every `step`-th fast and slow, both long_only settings."""
        return sorted(self.index_of((f, s, lo))
                      for f in self.fasts[::step] for s in self.slows[::step] for lo in (False, True)
                      if f < s)


@dataclass
class SearchResult:
    selected: int                 # column index of the submitted rule
    sharpe: float                 # its Sharpe on the data the search saw
    evaluated: tuple[int, ...]    # every column the search looked at: its realized menu
    anchor: int                   # the rule refinement was built around


def column_sharpes(R: np.ndarray, columns, annualization: float) -> np.ndarray:
    sub = R[:, list(columns)]
    mu, sd = sub.mean(axis=0), sub.std(axis=0, ddof=1)
    return np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), 0.0) * annualization


class AdaptiveCrossover:
    """Evaluate a coarse sub-grid, anchor on one of those results, then refine by evaluating the anchor's
    grid neighbours, keeping the better anchor each round. Submits the best rule it evaluated.

    anchor="winner" builds on the coarse round's best result, the crossover analogue of Adaptive and of
    WinnerAnchor. anchor="loser" builds on its worst, the mirror (searchers/dose_response.py's
    WorstAnchor). Selection is the best evaluated rule either way; only the anchor differs.
    """

    def __init__(self, grid: CrossoverGrid | None = None, anchor: str = "winner", rounds: int = 2,
                 coarse_step: int = COARSE_STEP, blocks: int = 1, seed: int = 0):
        if anchor not in ("winner", "loser"):
            raise ValueError(f"anchor must be 'winner' or 'loser', got {anchor!r}")
        if blocks < 1:
            raise ValueError(f"blocks must be at least 1, got {blocks}")
        self.grid = grid if grid is not None else CrossoverGrid()
        self.anchor_rule = anchor
        self.rounds = rounds
        self.coarse_step = coarse_step
        self.blocks = blocks
        self.seed = seed
        self.name = f"crossover_{anchor}"

    def _neighbours(self, index: int) -> list[int]:
        """Grid neighbours within the index's own block: refinement never crosses to another asset, and
        never leaves the declared grid."""
        width = len(self.grid.rules)
        block, local = divmod(index, width)
        return [block * width + j for j in self.grid.neighbours(local)]

    def run(self, R: np.ndarray, annualization: float = 1.0) -> SearchResult:
        """R: (T, blocks * len(grid.rules)) rule returns, one block of grid columns per asset. Works
        identically on real data and on a nullified surrogate, which is what makes the procedure-level null
        cheap. With blocks > 1 the coarse round spans every asset and refinement stays within whichever
        asset supplied the anchor."""
        width = len(self.grid.rules)
        if R.shape[1] != width * self.blocks:
            raise OffGridError(f"R has {R.shape[1]} columns, the declared grid has {width * self.blocks} "
                               f"({self.blocks} block(s) of {width})")

        coarse = [b * width + c for b in range(self.blocks) for c in self.grid.coarse(self.coarse_step)]
        scores = column_sharpes(R, coarse, annualization)
        evaluated = {c: float(v) for c, v in zip(coarse, scores)}
        anchor = coarse[int(np.argmax(scores) if self.anchor_rule == "winner" else np.argmin(scores))]

        for _ in range(self.rounds):
            fresh = [c for c in self._neighbours(anchor) if c not in evaluated]
            if not fresh:
                break
            for c, v in zip(fresh, column_sharpes(R, fresh, annualization)):
                evaluated[c] = float(v)
            nearby = self._neighbours(anchor) + [anchor]
            anchor = max(nearby, key=lambda c: evaluated[c])

        selected = max(evaluated, key=lambda c: evaluated[c])
        return SearchResult(selected=selected, sharpe=evaluated[selected],
                            evaluated=tuple(sorted(evaluated)), anchor=anchor)
