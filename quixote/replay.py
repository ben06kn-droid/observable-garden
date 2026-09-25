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
    # Does `moves` include the anchor as its first entry? `_run` and `_run_logged`
    # take the anchor inside their loop and record it; `_run_meta` anchors before
    # its loop and does not. `SessionLog.actions()` excludes the anchor, so a
    # comparison has to know which convention the trace uses rather than guess
    # from its length.
    anchored: bool = False
    # Which runner produced this trace. `_run` is 7.1's plain forward selection
    # and speaks a DIFFERENT action vocabulary from a session log: it says "stop"
    # where it declines an extension, while `SessionLog.actions()` calls any
    # proposed extension "continue" whether it was taken or not. Comparing those
    # two directly is comparing different events, so the action comparison is
    # made only where both sides speak the same vocabulary.
    path: str = "run"
    # steps replaced by the best admissible move under local-max or
    # fidelity-driven pricing; zero unless one of those flags is on
    locally_priced: int = 0
    # the support after each step, so a priced step's choice can be audited
    supports: list = field(default_factory=list)

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

    def __init__(self, log: SessionLog, spec_class, statistic: str = "sharpe",
                 locally_priced: frozenset = frozenset()):
        self.log = log
        self.spec_class = spec_class
        self.statistic = statistic
        # Steps that take the best admissible one-step move in every replicate
        # instead of the logged continuation (quixote/pricing.py). Empty by
        # default: nothing is priced this way until 7.3 licenses it.
        #
        # `locally_priced` holds LOG RECORD indices; record 0 is the anchor, and
        # the replay loop's step s is record s + 1. The conversion happens here so
        # a caller never has to know it.
        self.locally_priced = frozenset(locally_priced)
        self._priced_steps = frozenset(i - 1 for i in self.locally_priced if i >= 1)
        self.max_features = spec_class.max_size
        self.name = "logged-policy"
        # A log that declared no budget still needs a bound, or a replicate
        # whose triggers never fire runs away. 7.1's own hard cap is the bound,
        # for the reason it exists: `searchers/meta_adaptive.BUDGET = 12`, "so a
        # replicate can never run away". A declared budget always wins.
        from searchers.meta_adaptive import BUDGET as _DEFAULT_BUDGET
        self.budget = log.budget if log.budget is not None else _DEFAULT_BUDGET
        self.budget_declared = log.budget is not None
        self.triggers = [Trigger.from_record(t) for t in log.declared_triggers()]

    # -- the policy --------------------------------------------------------

    def _run(self, base: np.ndarray, annualization: float,
             frozen: list[str] | None = None,
             meta_steps: int | None = None, score_fn=None) -> ReplayTrace:
        g = Grammar(self.spec_class, base, annualization, score_fn=score_fn)
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
        trace.anchored, trace.path = True, "run"
        return trace

    # -- the interface estimator/trigger_replay consumes -------------------

    def _run_meta(self, base: np.ndarray, annualization: float,
                  frozen: list[str] | None = None,
                  meta_steps: int | None = None, score_fn=None) -> ReplayTrace:
        """The logged meta-adaptive policy on `base`. `frozen` freezes each
        step's action at the realized one (null 1); `meta_steps` re-evaluates the
        declared triggers for that many steps and fills past them (null 2);
        neither re-evaluates them throughout (null 3)."""
        from searchers.meta_adaptive import MetaAdaptive   # 7.1's scripted fill only

        g = Grammar(self.spec_class, base, annualization, score_fn=score_fn)
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

            if filling or step in self._priced_steps:
                trace.filled = trace.filled or filling
                trace.locally_priced += int(step in self._priced_steps)
                # The fill is 7.1's, uncapped, when the scorer is the built-in
                # base-column one: `fixed-sequence-replay` registered and ran it
                # that way, and milestone 3b holds this equal to the scripted
                # searcher's own nulls, replicate for replicate.
                #
                # With a supplied scorer it MUST be capped to the class. A class
                # table has no column for a non-member, so an uncapped fill would
                # ask for a price that does not exist. That is the capped variant
                # 7.1 amendment 4's licence-transfer argument covers, and it is
                # the only setting in which the two fills can differ.
                allow = None if score_fn is None else (lambda ns: g.contains(tuple(ns)))
                cands = MetaAdaptive._grammar(support, K, score_list, allow=allow)
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
            trace.supports.append(tuple(support))

        trace.support, trace.score = tuple(best_support), best
        trace.path = "run_meta"   # anchored before the loop, so moves exclude it
        return trace

    def content_kinds(self) -> tuple:
        """The content moves this log actually made."""
        return tuple(r.move.kind for r in self.log.records
                     if not r.move.is_meta and r.move.note != "rejected")

    def _run_logged(self, base: np.ndarray, annualization: float,
                    frozen: list[str] | None = None,
                    meta_steps: int | None = None, score_fn=None,
                    cap_to_log: bool = False) -> ReplayTrace:
        """Replay the moves the log actually holds, not a greedy forward selection.

        `_run_meta` re-executes 7.1's policy: every continue is an `extend_best`.
        That IS the policy for the scripted searchers `fixed-sequence-replay`
        registered, and milestone 3b holds it equal to them replicate for
        replicate. It is **not** the policy an agent ran: the pilot's logs
        contain `refine` and `swap_worst`, and replaying them as extensions
        produced a search that stopped two features early — which the
        identity-replicate guard correctly refused, at a score gap of 7.42, even
        after the class table had made the *basis* identical.

        So a log whose content moves are not all `extend_best` is replayed move
        by move: the declared triggers still decide **whether** to continue, stop
        or restart on each replicate, and the logged move decides **what** the
        continuation is. Both are functions of the data, which is what makes the
        replay a replay.

        Past the realized length the fill takes over exactly as in `_run_meta`.
        """
        from searchers.meta_adaptive import MetaAdaptive

        g = Grammar(self.spec_class, base, annualization, score_fn=score_fn)
        K = g.K
        moves = [r.move for r in self.log.records
                 if not r.move.is_meta and r.move.note != "rejected"]
        support: tuple = ()
        best, best_support = float("-inf"), ()
        failures, last_gain, restarts = 0, float("inf"), 0
        trace = ReplayTrace()

        def score_list(ns):
            return g.score(tuple(ns), self.statistic)

        # `cap_to_log` bounds the replay at the number of moves the log holds.
        # The commitment check asks whether the search followed its rule WHILE IT
        # RAN: a rule that fires earlier than the log stopped is divergence, but
        # a rule that would have kept going is not something the log contradicts,
        # because an agent may submit at any time. Past the logged moves an
        # uncapped replay takes the fill, which belongs to the bootstrap null and
        # not to a comparison on un-resampled data.
        limit = min(self.budget, len(moves)) if cap_to_log else self.budget
        for step in range(limit):
            filling = False
            if frozen is not None:
                if step >= len(frozen):
                    break
                action = frozen[step]
            else:
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
                new, sc, _ = g.anchor(restarts, self.statistic)
                if new is None:
                    trace.moves.append("stop")
                    break
                support = tuple(new)
                failures, last_gain = 0, float("inf")
                trace.moves.append("restart")
                continue

            if filling or step >= len(moves):
                trace.filled = trace.filled or filling
                cands = MetaAdaptive._grammar(list(support), K, score_list,
                                              allow=lambda ns: g.contains(tuple(ns)))
                chosen = max(cands) if cands else None
                if chosen is None:
                    trace.moves.append("stop")
                    break
                cand_score, cand_support = chosen[0], tuple(chosen[2])
            else:
                cand_support, cand_score, n = g.apply(support, moves[step])
                if n == 0:
                    trace.moves.append("stop")
                    break
                cand_support = tuple(cand_support)

            last_gain = cand_score - best
            support = cand_support
            if cand_score > best:
                best, best_support, failures = float(cand_score), cand_support, 0
            else:
                failures += 1
            trace.moves.append("continue")
            trace.supports.append(support)

        trace.support, trace.score = tuple(best_support), best
        trace.anchored, trace.path = True, "run_logged"
        return trace

    def _runner(self):
        """(runner, anchored, name). One place decides which replay a log takes, so a
        caller building a `frozen` sequence can align it with that runner's step
        convention instead of guessing."""
        kinds = set(self.content_kinds())
        meta_kinds = {r.move.kind for r in self.log.records if r.move.is_meta}
        declared = bool(getattr(self.log, "declared_trigger_records", ()))
        if declared or (kinds - {"extend_best", "init"}):
            return self._run_logged, True, "run_logged"
        if self.log.is_meta():
            return self._run_meta, False, "run_meta"
        if "restart" in meta_kinds:
            return self._run_logged, True, "run_logged"
        return self._run, True, "run"

    def frozen_actions(self) -> list[str]:
        """The realized action sequence, in the step convention of the runner
        this log will take. `SessionLog.actions()` excludes the anchor; a runner
        that takes the anchor inside its loop needs an entry for it, and passing
        the un-aligned list froze the replay one step short of the log."""
        acts = list(self.log.actions())
        return (["continue"] + acts) if self._runner()[1] else acts

    def trace(self, base: np.ndarray, annualization: float = 1.0,
              frozen: list[str] | None = None, meta_steps: int | None = None,
              score_fn=None, cap_to_log: bool = False) -> ReplayTrace:
        """`score_fn` overrides the base-column scorer, which is how a real panel
        is replayed: a class table's scorer returns the same stored net stream the
        live search was scored on (`environments/class_table.py`)."""
        run, _, name = self._runner()
        # by NAME: `self._run_logged is self._run_logged` is False, because each
        # attribute access builds a fresh bound method
        if cap_to_log and name == "run_logged":
            return run(base, annualization, frozen=frozen, meta_steps=meta_steps,
                       score_fn=score_fn, cap_to_log=True)
        return run(base, annualization, frozen=frozen, meta_steps=meta_steps,
                   score_fn=score_fn)

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
    # What this check IS, and what it ran on. The reason is stated from these,
    # never inferred from the size of the gap: a large gap on a table basis and a
    # large gap on a column basis mean different things, and the check knows
    # which it used.
    check: str = "integrity"          # "integrity" | "commitment"
    compared_actions: bool = True
    basis: str = "base columns"       # "class table" when a scorer was supplied

    @property
    def score_gap(self) -> float:
        return abs(self.realized_score - self.replayed_score)

    def reason(self) -> str:
        what = {"integrity": ("Integrity check (fixed-sequence replay: the realized "
                              "meta decisions with the logged content moves)"),
                "commitment": ("Commitment check (the search replayed under the rule "
                               "it committed to)")}[self.check]
        if self.agrees:
            return (f"{what}: PASS on the {self.basis}. The replay reproduces the "
                    f"realized support and score; they differ by {self.score_gap:.2e}."
                    + ("" if self.compared_actions else
                       " Actions were not compared: this log is a plain forward "
                       "selection, whose replay speaks a different action vocabulary."))
        seq = ("" if self.realized_actions == self.replayed_actions else
               f" The meta decisions differ too: replayed {list(self.replayed_actions)} "
               f"against realized {list(self.realized_actions)}.")
        if self.check == "integrity":
            cause = (
                "This is a STRUCTURAL failure. The realized meta decisions were held "
                f"fixed and the logged content moves re-executed on the {self.basis}, "
                "so nothing about the agent's rules is involved: either the basis is "
                "not the one the search was scored on, or the replay engine does not "
                "re-execute what the log holds. The run is not priced.")
        else:
            cause = (
                f"Replayed on the {self.basis} under the committed rule. The search "
                "that ran is not the search that rule describes; where a trigger "
                "change is logged this is expected and is priced in the bracket, and "
                "where none is logged the run is not priced.")
        return (f"{what}: FAIL. Replaying gives support {self.replayed_support} against "
                f"the realized {self.realized_support}.{seq} The realized and replayed "
                f"scores differ by {self.score_gap:.3e}. {cause}")


def integrity_check(log: SessionLog, spec_class, base: np.ndarray,
                    annualization: float = 1.0, score_fn=None) -> IdentityCheck:
    """**Does the engine reproduce the log at all?**

    Fixed-sequence replay on the UN-resampled data: the realized meta decisions
    are held at what the log says they were, the logged content moves are
    re-executed, and the result must be the realized support, score and action
    sequence.

    **This must hold on every run**, with or without a trigger change, because it
    involves no rule of the agent's: it asks only whether the basis and the
    engine reproduce what the harness itself recorded. Until 2026-09-25 the
    `certify` path skipped it whenever a change was logged, so a basis or engine
    defect was invisible on any run with one -- the ETF panel's best-against-last
    bug would have been undetectable on all three ADR runs.
    """
    return _compare(log, spec_class, base, annualization, score_fn,
                    check="integrity",
                    frozen=LoggedPolicy(log, spec_class).frozen_actions())


def commitment_check(log: SessionLog, spec_class, base: np.ndarray,
                     annualization: float = 1.0, score_fn=None) -> IdentityCheck:
    """**Did the search follow the rule it committed to?**

    The declared triggers are re-evaluated at every step, as a replicate does.
    A run that changed a trigger is expected to fail here, and that failure is
    what the bracket prices; a run that changed nothing and still fails did not
    search under its own declaration.
    """
    return _compare(log, spec_class, base, annualization, score_fn,
                    check="commitment", frozen=None, cap_to_log=True)


def identity_check(log: SessionLog, spec_class, base: np.ndarray,
                   annualization: float = 1.0, score_fn=None) -> IdentityCheck:
    """The commitment check, under its historical name."""
    return commitment_check(log, spec_class, base, annualization, score_fn)


def _compare(log: SessionLog, spec_class, base: np.ndarray,
             annualization: float, score_fn, check: str,
             frozen: list[str] | None, cap_to_log: bool = False) -> IdentityCheck:
    """Replay `log` on `base` itself -- no resampling -- and compare.

    The realized submission is the best accepted support: the last record whose
    move was a content move that was taken. For a plain forward selection that is
    the last support held; after a restart it is not, and the current support is
    never what was submitted. For a meta log the step-by-step actions are
    compared as well, so the guard covers where the search stopped or restarted.
    """
    taken = [r for r in log.records
             if not r.move.is_meta and r.move.note != "rejected"]
    # The BEST accepted pair, not the last one. `Session.submission()` submits
    # the best support and its score, and a replay returns the same; comparing
    # the log's LAST support against the replay's BEST compares two different
    # objects, and any search whose final move did not improve fails the guard
    # for that reason alone. The ETF pilot's first run is the case: its last
    # `extend_best` lost 0.0092, so its last support was never its submission.
    #
    # First attainment wins, because `Session` replaces the best only on a strict
    # improvement.
    best_i = None
    for i, r in enumerate(taken):
        if best_i is None or r.score_after > taken[best_i].score_after:
            best_i = i
    realized_support = taken[best_i].support_after if taken else ()
    realized_score = taken[best_i].score_after if taken else float("-inf")
    t = LoggedPolicy(log, spec_class).trace(base, annualization, frozen=frozen,
                                           score_fn=score_fn, cap_to_log=cap_to_log)
    same_support = tuple(t.support) == tuple(realized_support)

    # The ACTION SEQUENCE is compared on every log, not only on a budgeted one.
    # A search that stopped in a different place is a different search even when
    # it happens to submit the same pair, and until 2026-09-25 an agent log -
    # which declares no budget, so `is_meta()` is False - skipped this
    # comparison entirely.
    #
    # `_run` says "accept" where a log says "continue"; the vocabularies are
    # normalised rather than one of them being taken as canonical.
    def norm(seq):
        out = ["continue" if a == "accept" else a for a in seq]
        # A log ends with an explicit `stop` record; a replay that runs out of
        # support or budget simply ends. Both mean "the search stopped here", so
        # a single TRAILING stop is dropped from each side. A stop anywhere else
        # is a real difference and survives: it is a replay that stopped early.
        if out and out[-1] == "stop":
            out.pop()
        return tuple(out)

    # `log.actions()` excludes the anchor; a trace that recorded one drops it.
    replayed = list(t.moves)[1:] if t.anchored else list(t.moves)
    # Recorded RAW, compared NORMALISED: the record keeps the stop the log
    # holds (milestone 3c reads it), while the comparison treats "ended here"
    # and "stopped here" as the same stopping point.
    realized_actions, replayed_actions = tuple(log.actions()), tuple(replayed)
    # Compared where the two sides share a vocabulary: an agent log (`run_logged`)
    # and a meta log (`run_meta`). A plain forward-selection log replayed by 7.1's
    # `_run` is compared on support and score alone, and that is stated rather
    # than silently skipped.
    compare_actions = t.path in ("run_logged", "run_meta")
    agrees = same_support and (not compare_actions
                               or norm(realized_actions) == norm(replayed_actions))
    n_real = sum(1 for a in realized_actions if a == "continue")
    n_rep = sum(1 for a in replayed_actions if a == "continue")
    return IdentityCheck(
        check=check,
        compared_actions=compare_actions,
        basis="class table" if score_fn is not None else "base columns",
        agrees=agrees,
        realized_support=tuple(realized_support), replayed_support=tuple(t.support),
        realized_score=float(realized_score), replayed_score=float(t.score),
        n_moves_realized=n_real, n_moves_replayed=n_rep,
        realized_actions=realized_actions, replayed_actions=replayed_actions)
