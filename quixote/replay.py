"""Re-executing a logged session on fresh data.

A `LoggedPolicy` is a session log read back as a policy: the move kinds it
proposed and the triggers it declared, re-executed against a Grammar on whatever
base matrix it is handed. That is what makes a log worth keeping -- if the log
cannot be re-run, nothing downstream can price what the search did.

Scoring here uses the **base-column** path, because a bootstrap replicate has
resampled columns and no panel. So a replay agrees with the live sandbox-scored
search to about 1e-12 rather than bit for bit, exactly as
`searchers/scripted.py` records for the same reason.

**What is deliberately not here.** Which of these nulls certifies, the fill
inside an *agent's* path, local-max pricing, and fidelity-driven pricing are all
7.2 part two, and `fixed-sequence-replay` (7.1) decides their design. This module
re-executes; it does not adjudicate.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from quixote.grammar import Grammar, Move
from quixote.log import SessionLog


@dataclass
class ReplayTrace:
    """Mirrors `searchers.meta_adaptive.Trace` closely enough for
    `estimator.trigger_replay` to consume it."""
    moves: list = field(default_factory=list)
    support: tuple = ()
    score: float = float("-inf")
    policy: str = "logged"

    @property
    def n_moves(self) -> int:
        return len(self.moves)

    def actions(self) -> list[str]:
        return [m for m in self.moves]


class LoggedPolicy:
    """A session log, re-executable.

    `max_features` and the statistic come from the class and the log rather than
    being passed again, so a replay cannot silently run a different search from
    the one that was logged.
    """

    def __init__(self, log: SessionLog, spec_class, statistic: str = "sharpe"):
        self.log = log
        self.spec_class = spec_class
        self.statistic = statistic
        self.max_features = spec_class.max_size
        self.name = "logged-policy"
        # the proposed move kinds, stop records excluded
        self._kinds = [r.move.kind for r in log.records if r.move.note != "stop"]

    # -- the policy --------------------------------------------------------

    def _run(self, base: np.ndarray, annualization: float,
             frozen: list[str] | None = None,
             meta_steps: int | None = None) -> ReplayTrace:
        g = Grammar(self.spec_class, base, annualization)
        support: tuple = ()
        score = float("-inf")
        trace = ReplayTrace()

        for step in range(self.max_features):
            cand_support, cand_score, n = g.apply(support, Move("extend_best", self.statistic))
            if n == 0:
                trace.moves.append("stop")
                break
            if step == 0:
                support, score = cand_support, cand_score
                trace.moves.append("accept")
                continue

            if frozen is not None:
                if step >= len(frozen):
                    break
                take = frozen[step] == "accept"
            elif meta_steps is not None and step >= meta_steps:
                take = True                      # the fill: keep extending
            else:
                take = cand_score > score        # the declared trigger, re-evaluated

            if take:
                support, score = cand_support, cand_score
                trace.moves.append("accept")
            else:
                trace.moves.append("stop")
                break

        trace.support, trace.score = support, score
        return trace

    # -- the interface estimator/trigger_replay consumes -------------------

    def trace(self, base: np.ndarray, annualization: float = 1.0,
              frozen: list[str] | None = None,
              meta_steps: int | None = None) -> ReplayTrace:
        return self._run(base, annualization, frozen=frozen, meta_steps=meta_steps)

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        """Full policy replay: triggers re-evaluated on this replicate."""
        return self._run(base_columns, annualization).score

    def replay_fixed_sequence(self, base_columns: np.ndarray, actions: list[str],
                              annualization: float = 1.0) -> float:
        return self._run(base_columns, annualization, frozen=actions).score

    def replay_triggers(self, base_columns: np.ndarray, n_realized_moves: int,
                        annualization: float = 1.0) -> float:
        return self._run(base_columns, annualization, meta_steps=n_realized_moves).score
