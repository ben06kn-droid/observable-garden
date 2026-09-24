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

**Meta-adaptive logs (milestone 3).** A log with a declared budget and stamped
triggers is replayed by `_run_meta`, step for step the loop of
`searchers.meta_adaptive.MetaAdaptive._search`: content moves through the
grammar, meta moves from the declared triggers re-evaluated on the replicate's
own information set. Its trigger mode keeps evaluating the declared triggers past
the realized length (7.1 amendment 6) and, where they say continue, uses **7.1's
registered scripted fill**, imported from `searchers.meta_adaptive`, because the
milestone is that a logged scripted searcher reproduces that searcher's own
three nulls. It is not a choice of fill for an agent's path, which 7.1 decides.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from quixote.grammar import Grammar, Move
from quixote.log import SessionLog
from quixote.triggers import Trigger


@dataclass
class ReplayTrace:
    """Mirrors `searchers.meta_adaptive.Trace` closely enough for
    `estimator.trigger_replay` to consume it."""
    moves: list = field(default_factory=list)
    support: tuple = ()
    score: float = float("-inf")
    policy: str = "logged"
    # whether any step past the realized length took the fill: what
    # quixote.certify reports as engagement, and the condition under which a
    # verdict carries the fill's measured direction
    filled: bool = False

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
        self.budget = log.budget
        self.triggers = [Trigger.from_record(t) for t in log.declared_triggers()]

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

    def _run_meta(self, base: np.ndarray, annualization: float,
                  frozen: list[str] | None = None,
                  meta_steps: int | None = None) -> ReplayTrace:
        """The logged meta-adaptive policy on `base`. `frozen` freezes each
        step's action at the realized one (null 1); `meta_steps` re-evaluates the
        declared triggers for that many steps and fills past them (null 2);
        neither re-evaluates them throughout (null 3)."""
        from searchers.meta_adaptive import MetaAdaptive   # 7.1's scripted fill only

        g = Grammar(self.spec_class, base, annualization)
        K = g.K
        support, best, _ = g.anchor(0, self.statistic)
        support = list(support)
        best_support = list(support)
        failures, last_gain, restarts = 0, float("inf"), 0
        trace = ReplayTrace()

        def score_list(ns):
            return g.score(tuple(ns), self.statistic)

        for step in range(self.budget):
            filling = False
            if frozen is not None:
                if step >= len(frozen):
                    break
                action = frozen[step]
            else:
                # the declared triggers decide at every step, past the realized
                # length too (7.1 amendment 6); past it a continue takes the fill
                state = {"step": step, "best": best, "failures": failures,
                         "last_gain": last_gain, "budget_left": self.budget - step}
                action = "continue"
                for trig in self.triggers:
                    fires, _ = trig.evaluate(state)
                    if fires:
                        action = trig.action
                        break
                filling = meta_steps is not None and step >= meta_steps

            if action == "stop":
                trace.moves.append("stop")
                break
            if action == "restart":
                restarts += 1
                new, _, _ = g.anchor(restarts, self.statistic)
                if new is None:
                    trace.moves.append("stop")
                    break
                support = list(new)
                failures, last_gain = 0, float("inf")
                trace.moves.append("restart")
                continue

            if filling:
                trace.filled = True
                cands = MetaAdaptive._grammar(support, K, score_list)
                chosen = max(cands) if cands else None
                cand_score, cand_support = (chosen[0], chosen[2]) if chosen else (None, None)
            else:
                cs, sc, n = g.apply(tuple(support), Move("extend_best", self.statistic))
                cand_score, cand_support = (sc, list(cs)) if n else (None, None)
            if cand_support is None:
                trace.moves.append("stop")
                break
            last_gain = cand_score - best
            if cand_score > best:
                support, best = list(cand_support), float(cand_score)
                best_support, failures = list(support), 0
            else:
                failures += 1
            trace.moves.append("continue")

        trace.support, trace.score = tuple(best_support), best
        return trace

    def trace(self, base: np.ndarray, annualization: float = 1.0,
              frozen: list[str] | None = None,
              meta_steps: int | None = None) -> ReplayTrace:
        run = self._run_meta if self.log.is_meta() else self._run
        return run(base, annualization, frozen=frozen, meta_steps=meta_steps)

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        """Full policy replay: triggers re-evaluated on this replicate."""
        return self.trace(base_columns, annualization).score

    def replay_fixed_sequence(self, base_columns: np.ndarray, actions: list[str],
                              annualization: float = 1.0) -> float:
        return self.trace(base_columns, annualization, frozen=actions).score

    def replay_triggers(self, base_columns: np.ndarray, n_realized_moves: int,
                        annualization: float = 1.0) -> float:
        return self.trace(base_columns, annualization, meta_steps=n_realized_moves).score


# -- the identity-replicate guard -------------------------------------------

@dataclass
class IdentityCheck:
    """Did the replay path reproduce the live path on the UN-resampled data?

    The live search scores through the sandbox's panel; a replay scores by
    summing base columns. They agree to about 1e-12, not exactly. On a near-tie
    that difference can flip an argmax, and a flipped argmax early in a forward
    selection changes every move after it -- so the replayed policy would be
    pricing a search that never ran.

    The guard is cheap and exact: replay the identity resample and compare move
    sequences. A run that fails is **flagged and not priced**, because there is
    no defensible way to price a search whose own replay disagrees with it.
    """
    agrees: bool
    realized_support: tuple
    replayed_support: tuple
    realized_score: float
    replayed_score: float
    n_moves_realized: int
    n_moves_replayed: int
    # milestone 3: the step-by-step meta decisions, compared for meta logs, so a
    # replay that stops or restarts at a different step fails even if it lands
    # on the same support
    realized_actions: tuple = ()
    replayed_actions: tuple = ()

    @property
    def score_gap(self) -> float:
        return abs(self.realized_score - self.replayed_score)

    def reason(self) -> str:
        if self.agrees:
            return (f"Identity-replicate guard: PASS. The base-column replay "
                    f"reproduces the realized support; scores differ by "
                    f"{self.score_gap:.2e}, which is float accumulation and not "
                    "a different search.")
        seq = ("" if self.realized_actions == self.replayed_actions else
               f" The meta decisions differ too: replayed {list(self.replayed_actions)} "
               f"against realized {list(self.realized_actions)}.")
        return ("Identity-replicate guard: FAIL. Replaying the un-resampled data "
                f"gives support {self.replayed_support} against the realized "
                f"{self.realized_support}.{seq} The two scoring paths differ at ~1e-12 "
                "and that has flipped an argmax, so every later move priced a "
                "search that did not run. This run is flagged and not priced.")


def identity_check(log: SessionLog, spec_class, base: np.ndarray,
                   annualization: float = 1.0) -> IdentityCheck:
    """Replay `log` on `base` itself -- no resampling -- and compare.

    The realized submission is the best accepted support: the last record whose
    move was a content move that was taken. For a plain forward selection that is
    the last support held; after a restart it is not, and the current support is
    never what was submitted. For a meta log the step-by-step actions are
    compared as well, so the guard covers where the search stopped or restarted.
    """
    taken = [r for r in log.records
             if not r.move.is_meta and r.move.note != "rejected"]
    realized_support = taken[-1].support_after if taken else ()
    realized_score = taken[-1].score_after if taken else float("-inf")
    t = LoggedPolicy(log, spec_class).trace(base, annualization)
    same_support = tuple(t.support) == tuple(realized_support)
    if log.is_meta():
        realized_actions, replayed_actions = tuple(log.actions()), tuple(t.moves)
        agrees = same_support and realized_actions == replayed_actions
        n_real = sum(1 for a in realized_actions if a == "continue")
        n_rep = sum(1 for a in replayed_actions if a == "continue")
    else:
        realized_actions = replayed_actions = ()
        agrees = same_support
        n_real = len(taken)
        n_rep = sum(1 for m in t.moves if m == "accept")
    return IdentityCheck(
        agrees=agrees,
        realized_support=tuple(realized_support), replayed_support=tuple(t.support),
        realized_score=float(realized_score), replayed_score=float(t.score),
        n_moves_realized=n_real, n_moves_replayed=n_rep,
        realized_actions=realized_actions, replayed_actions=replayed_actions)
