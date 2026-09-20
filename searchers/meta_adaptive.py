"""Meta-adaptive searchers for 7.1: searches whose *meta* choices are data driven.

The distinction 7.1 turns on (ROADMAP 7.1, THEORY.md P4):

- **Content choices** — which feature to extend by — are rules. They are
  functions of the sample, so a bootstrap replicate re-executes them exactly.
- **Meta choices** — when to stop, when to restart, whether to take another move
  at all — were made *after seeing results*. Freezing them at their realized
  positions is the realized-menu error one level up, and stop-when-cleared is
  the winner-anchored case of it.

Each searcher here records both: the move sequence, and the **trigger** behind
every meta choice, as a predicate that can be re-evaluated on a replicate. That
is what makes the trigger-replay null of `estimator/trigger_replay.py` possible,
and what 7.1 measures against fixed-sequence replay and full policy replay.

Every searcher shares one core loop between `run`, `replay` and both replay
forms, for the reason `searchers/scripted.py` gives: two implementations of one
decision rule drift, and the replay nulls are only valid while they agree.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from environments.sandbox import Distribution, Sandbox, Specification
from estimator.bootstrap import sharpe
from searchers.base import Searcher

BUDGET = 12          # hard cap on moves, so a replicate can never run away


def _one_hot_sum(K: int, indices) -> np.ndarray:
    w = np.zeros(K)
    w[list(indices)] = 1.0
    return w


def _column_sharpe(column: np.ndarray, annualization: float = 1.0) -> float:
    return float(sharpe(column[:, None], axis=0, annualization=annualization)[0])


@dataclass
class Move:
    """One step of a search, with the meta decision that preceded it.

    `action` is the meta choice made *before* this move, given everything
    already seen: "continue" takes another extension, "restart" abandons the
    current support for a fresh anchor, "stop" ends the search. `trigger` names
    the predicate that produced it and `trigger_value` is what that predicate
    saw, so a replicate can re-evaluate the same predicate on its own state.
    """
    step: int
    action: str                      # "continue" | "restart" | "stop"
    trigger: str                     # the predicate's name
    trigger_value: float             # what the predicate evaluated to
    support: tuple[int, ...] = ()    # the support after the move ( () if stopped )
    score: float = float("-inf")     # best-so-far after the move


@dataclass
class Trace:
    """A realized search: its moves, its submission, and the policy that made it."""
    moves: list[Move] = field(default_factory=list)
    support: tuple[int, ...] = ()
    score: float = float("-inf")
    policy: str = ""

    @property
    def n_moves(self) -> int:
        return len(self.moves)

    @property
    def stopped_at(self) -> int:
        for m in self.moves:
            if m.action == "stop":
                return m.step
        return len(self.moves)

    def actions(self) -> list[str]:
        return [m.action for m in self.moves]


class MetaAdaptive(Searcher):
    """Base class: the shared search loop, parameterised by a meta decision.

    Subclasses implement `_decide(state) -> (action, trigger_name, value)` and
    nothing else. `mode` selects how meta choices are made during a replay:

    - "policy"  — re-evaluate the policy, which is exact because the policy is
                  code. This is null 3 in 7.1.
    - "trigger" — re-evaluate each declared predicate on the replicate's own
                  state, but only for as many steps as the realized search took;
                  past that, fill greedily. It agrees with "policy" exactly up to
                  the realized length and can diverge after it.
    - "fixed"   — take the realized action at each step regardless of what the
                  replicate sees. This is null 1, the error being measured.
    """
    budget = BUDGET

    def _decide(self, state: dict) -> tuple[str, str, float]:
        raise NotImplementedError

    # -- the continue-move ---------------------------------------------------

    @staticmethod
    def _greedy_extend(support, remaining, support_score):
        """7.1's fill rule: the best available extension. Used when a replicate
        runs past the realized sequence and no declared trigger is left."""
        return max((support_score(support + [j]), j) for j in remaining)

    def _extend(self, support, remaining, support_score):
        """This policy's own continue-move. Greedy extension by default, which
        makes the fill rule and the continuation coincide -- see
        `ExtendBySecondBest` for why that must not be true of every searcher."""
        return self._greedy_extend(support, remaining, support_score)

    # -- the one loop ------------------------------------------------------

    def _search(self, K: int, single: callable, support_score: callable,
                frozen: list[str] | None = None,
                meta_steps: int | None = None) -> Trace:
        """`single(k)` and `support_score(support)` score candidates.

        `frozen` supplies the meta action at each step instead of `_decide`:
        fixed-sequence replay. The realized sequence is the whole search, so when
        it runs out the search is over.

        `meta_steps` caps how many steps consult `_decide` at all. Past it the
        search continues greedily to the budget, which is 7.1's fill rule: a
        replicate that would run past the realized sequence is filled with greedy
        extension rather than truncated, since there is no declared trigger left
        to re-evaluate."""
        scores = np.array([single(k) for k in range(K)])
        order = list(np.argsort(-scores))
        anchor = 0
        support = [int(order[anchor])]
        best = float(scores[order[anchor]])
        trace = Trace(policy=self.name)
        failures, last_gain = 0, float("inf")

        for step in range(self.budget):
            state = {"step": step, "support": tuple(support), "best": best,
                     "failures": failures, "last_gain": last_gain,
                     "n_features": K}
            if frozen is not None:
                if step >= len(frozen):
                    break                       # the realized search ended here
                action = frozen[step]
                trigger, value = "frozen", float("nan")
            elif meta_steps is not None and step >= meta_steps:
                action, trigger, value = "continue", "fill", float("nan")
            else:
                action, trigger, value = self._decide(state)

            if action == "stop":
                trace.moves.append(Move(step, "stop", trigger, value,
                                        tuple(support), best))
                break

            if action == "restart":
                anchor += 1
                if anchor >= K:
                    trace.moves.append(Move(step, "stop", "exhausted", float(anchor),
                                            tuple(support), best))
                    break
                support = [int(order[anchor])]
                failures, last_gain = 0, float("inf")
                trace.moves.append(Move(step, "restart", trigger, value,
                                        tuple(support), best))
                continue

            # continue: extend the current support by one feature. Which feature
            # depends on whether this step is the policy running (its own
            # continue-move) or the fill running past the realized sequence
            # (greedy, by 7.1's rule). For most searchers these are the same
            # function; the point of ExtendBySecondBest is that they are not.
            remaining = [k for k in range(K) if k not in support]
            if not remaining:
                trace.moves.append(Move(step, "stop", "exhausted", 0.0,
                                        tuple(support), best))
                break
            filling = trigger == "fill"
            gain_score, j = (self._greedy_extend(support, remaining, support_score)
                             if filling else
                             self._extend(support, remaining, support_score))
            last_gain = gain_score - best
            if gain_score > best:
                support.append(int(j))
                best = float(gain_score)
                failures = 0
            else:
                failures += 1
            trace.moves.append(Move(step, "continue", trigger, value,
                                    tuple(support), best))

        trace.support, trace.score = tuple(support), best
        return trace

    # -- entry points ------------------------------------------------------

    def _scorers_from_columns(self, base: np.ndarray, annualization: float):
        def single(k):
            return _column_sharpe(base[:, k], annualization)

        def support_score(support):
            return _column_sharpe(base[:, list(support)].sum(axis=1), annualization)

        return single, support_score

    def trace(self, base: np.ndarray, annualization: float = 1.0,
              frozen: list[str] | None = None,
              meta_steps: int | None = None) -> Trace:
        single, support_score = self._scorers_from_columns(base, annualization)
        return self._search(base.shape[1], single, support_score,
                            frozen=frozen, meta_steps=meta_steps)

    def replay(self, base_columns: np.ndarray, annualization: float = 1.0) -> float:
        """Full policy replay: the policy is code, so this is exact."""
        return self.trace(base_columns, annualization).score

    def replay_fixed_sequence(self, base_columns: np.ndarray, actions: list[str],
                              annualization: float = 1.0) -> float:
        """Fixed-sequence replay: meta choices frozen at the realized sequence,
        content rules re-executed. 7.1's null 1."""
        return self.trace(base_columns, annualization, frozen=actions).score

    def replay_triggers(self, base_columns: np.ndarray, n_realized_moves: int,
                        annualization: float = 1.0) -> float:
        """Trigger replay: every meta choice's predicate re-evaluated on this
        replicate. 7.1's null 2.

        A replicate whose predicate fires earlier stops there. One that would run
        past the realized sequence has no further declared trigger, so it is
        filled with greedy extension to the budget.

        The exact invariant, asserted in `tests/test_meta_adaptive.py`: this
        differs from full policy replay **only on replicates whose policy would
        have run past the realized length**. Up to that point the predicates are
        the policy, so the two agree step for step.

        Past it they can differ in two ways. In the **meta** dimension, for any
        searcher: the fill always continues, so a policy that would have stopped
        or restarted there diverges -- `StopWhenCleared` with a short realized
        sequence is the clear case. In the **content** dimension, only for a
        searcher whose continue-move is not greedy extension, since the fill's
        move is greedy by definition; that is what `ExtendBySecondBest` is for.
        """
        return self.trace(base_columns, annualization,
                          meta_steps=n_realized_moves).score

    def run(self, sandbox: Sandbox) -> None:
        K = sandbox.num_features

        def single(k):
            return sandbox.evaluate(Specification(
                weights=_one_hot_sum(K, [k]), name=f"{self.name}_f{k}")).sharpe

        def support_score(support):
            return sandbox.evaluate(Specification(
                weights=_one_hot_sum(K, support),
                name=f"{self.name}_{sorted(support)}")).sharpe

        t = self._search(K, single, support_score)
        self.last_trace = t
        spec = Specification(weights=_one_hot_sum(K, t.support),
                             name=f"{self.name}_{sorted(t.support)}")
        sandbox.submit(spec, Distribution.degenerate(t.score))


class StopWhenCleared(MetaAdaptive):
    """Stops the moment the best-so-far clears a bar fixed before the search.

    The winner-anchored case, and the one P4 says is worst: the stopping time is
    a function of the realized maximum, so freezing it at its realized step
    conditions the replicate on an event that has not happened to it.
    """
    name = "stop-when-cleared"

    def __init__(self, bar: float, seed: int = 0):
        super().__init__(seed=seed)
        self.bar = float(bar)

    def _decide(self, state):
        return (("stop" if state["best"] > self.bar else "continue"),
                "best_so_far > bar", state["best"] - self.bar)


class RestartAfterKFailures(MetaAdaptive):
    """Abandons the current support for the next-best anchor after k consecutive
    extensions that did not improve. The restart point is data driven, so the
    realized sequence of restarts is itself a selected object."""
    name = "restart-after-k-failures"

    def __init__(self, k: int = 2, seed: int = 0):
        super().__init__(seed=seed)
        self.k = int(k)

    def _decide(self, state):
        return (("restart" if state["failures"] >= self.k else "continue"),
                f"failures >= {self.k}", float(state["failures"]))


class ExtendWhileImproving(MetaAdaptive):
    """Keeps extending while the last extension gained more than `min_gain`, and
    stops otherwise. The mildest of the three: the trigger looks at an increment
    rather than at the running maximum."""
    name = "extend-while-improving"

    def __init__(self, min_gain: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))


class ExtendBySecondBest(MetaAdaptive):
    """Continues by adding the **second**-best available extension, not the best.

    Its reason for existing is narrow and structural. For the other three
    searchers the continue-move *is* greedy extension, which is also 7.1's fill
    rule, so past the realized sequence the fill can only diverge from the policy
    in the meta dimension -- when the policy would have stopped or restarted
    there. That happens occasionally and only when the realized sequence is
    short, so it exercises the fill's **content** choice not at all. 7.3 cannot
    exercise it either: an agent has no exact policy null to compare a filled
    trigger replay against.

    Without this searcher the fill's content rule would go into the gate
    untested. Its continuation is deliberately not greedy, so **every** filled
    step adds a different feature from the one the policy would have added.
    Nulls 2 and 3 then separate systematically rather than occasionally, and the
    signed Kolmogorov distance between them says which way the fill errs.

    The meta trigger is the mildest one -- extend while improving -- so that what
    separates the nulls is the continue-move and nothing else.
    """
    name = "second-best-while-improving"

    def __init__(self, min_gain: float = 0.0, seed: int = 0):
        super().__init__(seed=seed)
        self.min_gain = float(min_gain)

    def _decide(self, state):
        gain = state["last_gain"]
        return (("stop" if gain <= self.min_gain else "continue"),
                f"last_gain > {self.min_gain}", float(gain))

    def _extend(self, support, remaining, support_score):
        ranked = sorted(((support_score(support + [j]), j) for j in remaining),
                        reverse=True)
        return ranked[1] if len(ranked) > 1 else ranked[0]


# The three whose continue-move is greedy extension. They are the clean
# measurement of the fixed-sequence gap, because nulls 2 and 3 coincide for them
# and nothing but the freezing moves. ExtendBySecondBest is deliberately not one
# of them.
GREEDY_CONTINUATION = (StopWhenCleared, RestartAfterKFailures, ExtendWhileImproving)
SEARCHERS = GREEDY_CONTINUATION + (ExtendBySecondBest,)
