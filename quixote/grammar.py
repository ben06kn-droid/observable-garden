"""The move grammar, executed by the harness.

The agent names a move; the harness computes it and builds the specification.
That is the point: the log cannot disagree with what ran, because the log IS
what ran. An agent that could construct its own specification could describe it
one way and submit another, and no amount of later checking would catch it.

A support is a tuple of `(feature, sign)` pairs. Signs are carried even for
unsigned classes, where they are all +1, so that `flip` is a real move rather
than a special case, and so one representation serves both class kinds.

Content moves (ROADMAP 7.2): `init`, `extend_best`, `swap_worst`, `flip`,
`refine`. Each is a pure function of (support, data, statistic) -- no randomness,
no hidden state -- which is what lets a bootstrap replicate re-execute it
exactly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from garden.spec_class import SubsetClass

Support = tuple[tuple[int, float], ...]

MOVE_KINDS = ("init", "extend_best", "swap_worst", "flip", "refine")


@dataclass(frozen=True)
class Move:
    """One named move. `kind` is what the agent asked for; everything else is
    what the harness did about it."""
    kind: str
    statistic: str = "sharpe"
    feature: int | None = None          # `flip` names one; others do not
    note: str = ""

    def __post_init__(self):
        if self.kind not in MOVE_KINDS:
            raise ValueError(f"unknown move {self.kind!r}; grammar is {MOVE_KINDS}")
        if self.kind == "flip" and self.feature is None:
            raise ValueError("flip names the feature to flip")
        if self.kind != "flip" and self.feature is not None:
            raise ValueError(f"{self.kind} does not take a feature")


def weights(support: Support, K: int) -> np.ndarray:
    w = np.zeros(K)
    for k, s in support:
        w[k] = float(s)
    return w


class Grammar:
    """Executes moves against a fixed class on a fixed base matrix.

    `signs_allowed` comes from the class, so an unsigned class can never produce
    a -1 and `flip` becomes a no-op there rather than an escape hatch out of the
    declared class.
    """

    def __init__(self, spec_class: SubsetClass, base: np.ndarray,
                 annualization: float = 1.0, score_fn=None):
        """`score_fn(support, statistic) -> float` overrides the built-in
        base-column scorer.

        Two scoring paths exist and they are not bit-identical, for the reason
        `searchers/scripted.py` already records: the sandbox computes a
        portfolio stream from the full (T, M, K) panel, while a replay sums base
        feature columns, and the two accumulate floating point differently. They
        agree to about 1e-12, not exactly.

        So the path is chosen by the caller rather than fixed here. A live search
        passes the sandbox's own scorer, which makes it the *same* computation
        the gate will grade; a replay on resampled columns uses the built-in one,
        which is the only thing available when there is no panel.
        """
        self.spec_class = spec_class
        self.base = np.asarray(base, dtype=float)
        self.K = self.base.shape[1]
        self.annualization = float(annualization)
        self._score_fn = score_fn
        self.signs = (1.0, -1.0) if getattr(spec_class, "signed", False) else (1.0,)
        self.max_size = spec_class.max_size

    # -- statistics --------------------------------------------------------

    def score(self, support: Support, statistic: str = "sharpe") -> float:
        """The statistic library. `stability` is registered by
        `prereg/stability-statistic.md` and is not built here: that item changes
        the engine, and this package does not."""
        if not support:
            return float("-inf")
        if self._score_fn is not None:
            return float(self._score_fn(support, statistic))
        stream = np.zeros(self.base.shape[0])
        for k, s in support:
            stream = stream + self.base[:, k] * s
        if statistic == "sharpe":
            sd = stream.std(ddof=1)
            if sd <= 0:
                return float("-inf")
            return float(stream.mean() / sd * self.annualization)
        raise ValueError(
            f"unknown statistic {statistic!r}; this package implements 'sharpe'. "
            "'stability' is pre-registered and deliberately unbuilt here.")

    # -- moves -------------------------------------------------------------

    def candidates(self, support: Support, move: Move) -> list[tuple[float, Support]]:
        """Every support this move could produce, scored. Enumeration order is
        feature-ascending then sign (+1, -1), fixed so that a tie resolves the
        same way on every replicate."""
        held = {k for k, _ in support}
        free = [k for k in range(self.K) if k not in held]
        out: list[tuple[float, Support]] = []

        if move.kind in ("init", "extend_best"):
            if len(support) >= self.max_size:
                return []
            for j in free:
                for s in self.signs:
                    ns = tuple(support) + ((j, s),)
                    out.append((self.score(ns, move.statistic), ns))
        elif move.kind == "swap_worst":
            for i in range(len(support)):
                for j in free:
                    for s in self.signs:
                        ns = support[:i] + ((j, s),) + support[i+1:]
                        out.append((self.score(ns, move.statistic), ns))
        elif move.kind == "flip":
            if len(self.signs) == 1:
                return []                      # unsigned class: nothing to flip
            idx = [i for i, (k, _) in enumerate(support) if k == move.feature]
            if not idx:
                raise ValueError(f"cannot flip feature {move.feature}: not in the support")
            i = idx[0]
            ns = support[:i] + ((support[i][0], -support[i][1]),) + support[i+1:]
            out.append((self.score(ns, move.statistic), ns))
        elif move.kind == "refine":
            # re-score the current support under a different statistic; the
            # support does not change
            out.append((self.score(support, move.statistic), tuple(support)))
        return out

    def apply(self, support: Support, move: Move) -> tuple[Support, float, int]:
        """Execute `move`. Returns (new support, its score, candidates considered).

        The candidate count is what `effective_breadth` and item 6's bits are
        computed from, so it is returned rather than recomputed later from a
        description of the move.
        """
        cands = self.candidates(support, move)
        if not cands:
            return tuple(support), self.score(support, move.statistic), 0
        best = max(cands, key=lambda c: c[0])
        return best[1], best[0], len(cands)

    def contains(self, support: Support) -> bool:
        return bool(self.spec_class.contains(weights(support, self.K)))
