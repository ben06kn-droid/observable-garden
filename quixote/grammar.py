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

Meta moves (milestone 3): `restart` and `stop`. Neither is chosen by the grammar;
each is taken because a declared trigger fired (`quixote/triggers.py`), and the
session stamps the trigger before the move executes. `restart` is still a pure
function of the data: it moves to the next anchor in the ranking of single
features by the statistic, and the rank is the harness's own restart count, so a
replicate re-derives it rather than copying it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from estimator.bootstrap import sharpe as _sharpe
from garden.spec_class import SubsetClass

Support = tuple[tuple[int, float], ...]

CONTENT_KINDS = ("init", "extend_best", "swap_worst", "flip", "refine", "pick")
META_KINDS = ("restart", "stop")
MOVE_KINDS = CONTENT_KINDS + META_KINDS


@dataclass(frozen=True)
class Move:
    """One named move. `kind` is what the agent asked for; everything else is
    what the harness did about it."""
    kind: str
    statistic: str = "sharpe"
    feature: int | None = None          # `flip` names one; others do not
    note: str = ""
    # `pick` only: the candidate features the rule ranges over, the statistic to
    # fall back on when the premise fails on a replicate, and the choice the
    # agent says the rule makes (checked by quixote/consistency.py)
    among: tuple = ()
    else_statistic: str | None = None
    choice: int | None = None

    def __post_init__(self):
        if self.kind not in MOVE_KINDS:
            raise ValueError(f"unknown move {self.kind!r}; grammar is {MOVE_KINDS}")
        if self.kind == "flip" and self.feature is None:
            raise ValueError("flip names the feature to flip")
        if self.kind not in ("flip", "pick") and self.feature is not None:
            raise ValueError(f"{self.kind} does not take a feature")
        if self.kind != "pick" and (self.among or self.else_statistic or self.choice is not None):
            raise ValueError(f"{self.kind} takes no among/else/choice; only pick does")
        if self.kind == "pick" and not self.among:
            raise ValueError("pick names the candidate set it ranges over")

    @property
    def is_meta(self) -> bool:
        return self.kind in META_KINDS


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
            # The estimator's own Sharpe, guards included, so a replay scores
            # exactly as the scripted searchers do rather than agreeing with
            # them only away from degenerate streams.
            return float(_sharpe(stream[:, None], axis=0,
                                 annualization=self.annualization)[0])
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
        elif move.kind == "pick":
            # every candidate the rule ranged over is a trial and is counted;
            # which one it selects is `pick_choice` below
            for _, ns in self.pick_candidates(support, move):
                out.append((self.score(ns, "sharpe"), ns))
        elif move.kind == "refine":
            # re-score the current support under a different statistic; the
            # support does not change
            out.append((self.score(support, move.statistic), tuple(support)))
        return out

    def stream(self, support: Support) -> np.ndarray:
        """The support's base-column stream. Statistics other than Sharpe are
        computed from this in both the live and replay paths, so a reason means
        the same thing in each."""
        out = np.zeros(self.base.shape[0])
        for k, s in support:
            out = out + self.base[:, k] * s
        return out

    def pick_candidates(self, support: Support, move: Move) -> list:
        """(value, support) for each candidate in `among`, by the named
        statistic. A candidate already held is not a candidate, and **a candidate
        outside the declared class is not a candidate either**.

        The class check comes before the statistic, not after. `extend_best`
        already returns nothing at a full support; `pick` did not, so at a full
        support every candidate it built was one feature too large and the
        harness asked the sandbox to score a specification the class forbids.
        The sandbox refused — correctly — and the agent's `pick` could never
        succeed. Found by the second attempt of `prereg/agent-pilot.md`, where
        every replay-arm run spent a turn on exactly that refusal.
        """
        from quixote.statistics import evaluate as stat_of
        held = {k for k, _ in support}
        best_stream = self.stream(support) if support else None
        out = []
        for j in move.among:
            if j in held:
                continue
            for sign in self.signs:
                ns = tuple(support) + ((int(j), sign),)
                if not self.contains(ns):
                    continue
                v = stat_of(move.statistic, self.stream(ns), self.annualization, best_stream)
                out.append((v, ns))
        return out

    def anchor(self, rank: int, statistic: str = "sharpe") -> tuple[Support | None, float, int]:
        """The `rank`-th single feature by `statistic`, at sign +1: what `init`
        takes at rank 0 and each `restart` takes at the next rank. Ranked with
        `np.argsort(-scores)`, the same call `searchers.meta_adaptive` makes, so
        ties resolve identically. Returns (None, -inf, K) past the last feature."""
        scores = np.array([self.score(((k, 1.0),), statistic) for k in range(self.K)])
        order = np.argsort(-scores)
        if rank >= self.K:
            return None, float("-inf"), self.K
        k = int(order[rank])
        return ((k, 1.0),), float(scores[k]), self.K

    def pick_choice(self, support: Support, move: Move) -> tuple[Support | None, str]:
        """What the declared rule selects, and under which statistic. If the
        statistic is undefined for every candidate -- the premise failing on this
        replicate -- the `else` statistic decides; without one the harness falls
        back to Sharpe (ROADMAP 7.2)."""
        import math

        from quixote.statistics import better
        cands = self.pick_candidates(support, move)
        name = move.statistic
        if cands and all(math.isnan(v) for v, _ in cands):
            name = move.else_statistic or "sharpe"
            cands = self.pick_candidates(support, Move("pick", statistic=name,
                                                       among=move.among))
        best = None
        for v, ns in cands:
            if best is None or better(name, v, best[0]):
                best = (v, ns)
        return (best[1] if best else None), name

    def apply(self, support: Support, move: Move) -> tuple[Support, float, int]:
        """Execute `move`. Returns (new support, its score, candidates considered).

        The candidate count is what `effective_breadth` and item 6's bits are
        computed from, so it is returned rather than recomputed later from a
        description of the move.
        """
        cands = self.candidates(support, move)
        if not cands:
            stat = "sharpe" if move.kind == "pick" else move.statistic
            return tuple(support), self.score(support, stat), 0
        if move.kind == "pick":
            chosen, _ = self.pick_choice(support, move)
            if chosen is None:
                return tuple(support), self.score(support, "sharpe"), len(cands)
            return chosen, self.score(chosen, "sharpe"), len(cands)
        best = max(cands, key=lambda c: c[0])
        return best[1], best[0], len(cands)

    def contains(self, support: Support) -> bool:
        return bool(self.spec_class.contains(weights(support, self.K)))
