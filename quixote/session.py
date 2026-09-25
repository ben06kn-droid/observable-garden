"""The harness that drives a search through the grammar.

A `Session` owns the grammar, the log and the class. A driver -- a scripted
policy now, an agent later -- names moves; the session executes them, records
what was shown and when, and refuses anything outside the declared class.

Nothing here chooses a null or a certifier. That is 7.2 part two, and
`fixed-sequence-replay` (7.1) decides its design.
"""
from __future__ import annotations

import time

import numpy as np

from quixote.grammar import Grammar, Move, Support, weights
from quixote.log import InformationSet, MoveRecord, SessionLog
from quixote.triggers import Trigger


class TriggerFired(Exception):
    """A declared trigger fires on the current state, so no content move is
    taken until the agent stops or changes it (decision (b), 2026-09-25).

    Not an error: it is the harness holding the agent to a rule the agent chose,
    and it carries the trigger and the value so the agent can act on it.
    """

    def __init__(self, trigger, value: float):
        self.trigger, self.value = trigger, float(value)
        super().__init__(
            f"your declared rule {trigger.name} has fired (value {value:.4f}). "
            f"It licenses a {trigger.action}. Take that move, or call "
            "change_trigger to search under a different rule -- which is logged "
            "and prices the rest of the run as unreplayable.")


class Session:
    def __init__(self, spec_class, base: np.ndarray, annualization: float = 1.0,
                 score_fn=None):
        self.grammar = Grammar(spec_class, base, annualization, score_fn=score_fn)
        self.log = SessionLog()
        self.support: Support = ()
        self.score: float = float("-inf")
        self._pending = None
        # The information set triggers are evaluated on. `best` and its support
        # are tracked apart from the current support, because a restart replaces
        # the support without resetting the best (fixed-sequence-replay
        # amendment 5): the submission is the best pair, never a mix of the two.
        self.best_score: float = float("-inf")
        self.best_support: Support = ()
        self.failures: int = 0
        self.last_gain: float = float("inf")
        self.n_restarts: int = 0

    @classmethod
    def on_sandbox(cls, sandbox, spec_class, name_prefix: str = "quixote"):
        """A session that scores through the sandbox, so every candidate the
        grammar considers is a logged trial and the number the search optimises
        is the number the gate will grade -- bit for bit, not to tolerance."""
        from environments.sandbox import Specification
        from quixote.grammar import weights as _w

        base = sandbox.base_feature_columns()
        K = base.shape[1]
        counter = {"n": 0}

        def score_fn(support, statistic="sharpe"):
            if statistic != "sharpe":
                raise ValueError(
                    f"unknown statistic {statistic!r}; sandbox scoring is Sharpe. "
                    "'stability' is pre-registered and deliberately unbuilt here.")
            counter["n"] += 1
            spec = Specification(weights=_w(tuple(support), K),
                                 name=f"{name_prefix}_{counter['n']}")
            return sandbox.evaluate(spec).sharpe

        self = cls(spec_class, base, float(np.sqrt(sandbox.periods_per_year)),
                   score_fn=score_fn)
        self.sandbox = sandbox
        return self

    # -- declarations, before any evaluation ------------------------------

    def pick_prior(self, support: Support, reason: str = "") -> None:
        """A specification named before anything has been evaluated."""
        self.log.refuse_if_late("pick_prior")
        if not self.grammar.contains(support):
            raise ValueError("pick_prior names a specification outside the declared class")
        self.log.prior_pick = {"support": tuple(support), "reason": reason,
                               "timestamp": time.monotonic()}

    def declare_short_list(self, supports, cap: int = 5) -> None:
        """Item 2's slot. The cap is registered in
        `prereg/prior-weighted-alpha.md` at 5; it is a parameter here so the
        pre-registration and not the code fixes it."""
        self.log.refuse_if_late("short list")
        supports = tuple(tuple(s) for s in supports)
        if len(supports) > cap:
            raise ValueError(f"short list holds {len(supports)} > cap {cap}")
        for s in supports:
            if not self.grammar.contains(s):
                raise ValueError("short list names a specification outside the declared class")
        self.log.short_list = supports

    def declare_triggers(self, triggers) -> None:
        """The stopping policy, fixed before the first evaluation.

        A declared trigger is a **commitment the search runs under**, which is
        what makes replaying it a replay. Declared at the moment of stopping it
        is a description offered afterwards, and the two are indistinguishable in
        a log unless the harness separates them: the agent pilot found two runs
        of three whose stated stop rule, applied as a rule, would have ended
        their search eight moves early (`prereg/agent-pilot.md`).

        Refused after the first evaluation, on the same grounds as the short list
        and the prior pick. `change_trigger` is the licensed way to change one.
        """
        self.log.refuse_if_late("triggers")
        recs = []
        for t in triggers:
            rec = t.as_record() if isinstance(t, Trigger) else dict(t)
            Trigger.from_record(rec)                     # refuse an unknown one now
            recs.append(rec)
        self.log.declared_trigger_records = tuple(recs)

    def change_trigger(self, trigger, reason: str = "") -> None:
        """Replace the declared stopping policy mid-search.

        **Allowed, logged, and priced — but priced by the VERDICT, not here.**
        The change is a decision taken after seeing results, so the trigger in
        force before it is what replays. Whether that costs anything depends on
        whether the change **bound**: if the committed rule reproduces the
        realized search, the change changed nothing and there is nothing to
        bracket. The log cannot know that — the commitment check measures it —
        so the log records the change as a fact and `quixote/certify.py` decides
        what it costs (seat run `pilot_adr_2`: five changes, commitment passing
        at a gap of 0.0, and 27 moves tagged unreplayable for nothing).
        """
        rec = trigger.as_record() if isinstance(trigger, Trigger) else dict(trigger)
        Trigger.from_record(rec)
        # `declared_trigger_records` is NOT touched: it is the pre-change
        # declaration, and the pre-change trigger is what replays. The change
        # lives beside it, and `active_trigger_records` is what the live search
        # runs under.
        self.log.trigger_changes = self.log.trigger_changes + (
            {"trigger": rec, "reason": reason, "at_step": self.log.n_moves,
             "timestamp": time.monotonic()},)

    @property
    def triggers_changed(self) -> bool:
        return bool(self.log.trigger_changes)

    @property
    def active_trigger_records(self) -> list:
        """What the search is running under NOW: the declaration, with each
        change applied over the action it replaces.

        Distinct from `log.declared_triggers()`, which is the pre-change
        declaration and is what a replay re-evaluates. Keeping the two apart is
        the whole content of the priced exception: the run is replayed under the
        rule it committed to, and everything after a change is bracketed.
        """
        active = {r.get("action", "stop"): dict(r)
                  for r in self.log.declared_trigger_records}
        for ch in self.log.trigger_changes:
            rec = dict(ch["trigger"])
            active[rec.get("action", "stop")] = rec
        return list(active.values())

    def fired_triggers(self) -> list:
        """Every declared trigger that fires on the current information set.

        A declared trigger is a commitment, so the harness **checks it before
        every content move** rather than only when the agent asks. Attempt 5 of
        `prereg/agent-pilot.md` is why: declaring a rule up front made it a
        commitment on paper, but the harness still evaluated it only on demand,
        so a rule that would have fired at step 2 stopped the replay where the
        realized search carried on, and the guard refused two runs of three.
        """
        state = self.info_state()
        out = []
        for rec in self.active_trigger_records:
            trig = Trigger.from_record(rec)
            fires, value = trig.evaluate(state)
            if fires:
                out.append((trig, float(value)))
        return out

    def declare_budget(self, budget: int) -> None:
        """The step budget of a meta-adaptive session. Declared before any
        evaluation: a budget chosen after seeing results is itself a meta
        decision, and is refused rather than logged as a prior."""
        self.log.refuse_if_late("budget")
        self.log.budget = int(budget)

    # -- the information set and triggers -----------------------------------

    @property
    def steps_taken(self) -> int:
        """Steps after the anchor, counted as the scripted searchers count them."""
        return max(0, self.log.n_moves - 1)

    def info_state(self) -> dict:
        budget = self.log.budget
        return {"step": self.steps_taken, "best": self.best_score,
                "failures": self.failures, "last_gain": self.last_gain,
                "budget_left": None if budget is None else budget - self.steps_taken}

    def evaluate_trigger(self, trigger: Trigger) -> tuple[bool, float, float]:
        """Evaluate a declared trigger on the current information set and stamp
        it. Returns (fires, value seen, stamp). The stamp is taken here, before any
        move it justifies executes, and travels into that move's record."""
        fires, value = trigger.evaluate(self.info_state())
        return bool(fires), float(value), time.monotonic()

    # -- the search -------------------------------------------------------

    def propose(self, move: Move, shown: tuple = ()) -> tuple[Support, float, int]:
        """Compute a move without committing it, and log the evaluation.

        Proposing is where the data is touched, so it is logged; accepting is a
        decision, so it is recorded separately. Forward selection needs exactly
        this split -- it computes the best extension and keeps it only if it
        improves -- and collapsing the two would either hide an evaluation that
        happened or record a support that was never held.
        """
        # (b), decided 2026-09-25: when a declared trigger fires the harness
        # announces it and takes no content move until the agent stops or calls
        # `change_trigger`. The agent keeps its agency and every departure from
        # its own rule is priced, rather than the rule being enforced silently.
        if not move.is_meta:
            fired = self.fired_triggers()
            if fired:
                trig, value = fired[0]
                raise TriggerFired(trig, value)
        new_support, new_score, n_cand = self.grammar.apply(self.support, move)
        if not self.grammar.contains(new_support):
            raise ValueError(
                f"{move.kind} would leave the declared class; the harness refuses "
                "rather than taking the run off-tier")
        # The consistency check, at the moment of the move and free: the harness
        # computed the rule's selection in order to execute it, so comparing it
        # with the choice the agent named costs one comparison
        # (quixote/consistency.py).
        #
        # **Harness execution means the rule decides.** What runs is the rule's
        # selection, so a replicate re-derives it and the move is REPLAYABLE. The
        # contradiction is a fact about the agent's STATEMENT, recorded on the
        # record and reported in the verdict; it is not a reason to call a move
        # the harness itself computed unreplayable (decided 2026-09-25, inverting
        # the earlier flag).
        consistent = True
        if move.kind == "pick" and move.choice is not None:
            held = {k for k, _ in self.support}
            added = [k for k, _ in new_support if k not in held]
            consistent = bool(added) and added[0] == move.choice
        self._pending = (move, new_support, new_score, n_cand, tuple(shown), consistent)
        return new_support, new_score, n_cand

    def accept(self, trigger: str | Trigger | None = None,
               trigger_value: float | None = None, replayable: bool = True,
               stamped_at: float | None = None) -> float:
        """Commit the pending proposal and record it."""
        if self._pending is None:
            raise ValueError("nothing proposed to accept")
        move, support, score, n_cand, shown, consistent = self._pending
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score, shown=shown,
                              n_candidates_seen=n_cand)
        self.support, self.score = support, score
        self.last_gain = score - self.best_score
        if score > self.best_score:
            self.best_score, self.best_support, self.failures = score, support, 0
        else:
            self.failures += 1
        name, params = _trigger_fields(trigger)
        self.log.record(MoveRecord(
            step=info.step, move=move, support_after=support, score_after=score,
            n_candidates=n_cand, information=info, timestamp=time.monotonic(),
            trigger=name, trigger_value=trigger_value,
            replayable=replayable,
            contradicted=not consistent,
            trigger_params=params, trigger_stamped_at=stamped_at))
        self._pending = None
        return score

    def cancel(self) -> None:
        """Drop a proposal that produced no candidates. Nothing was computed, so
        nothing is recorded; the caller records the stop that follows."""
        if self._pending is None or self._pending[3] != 0:
            raise ValueError("cancel is only for a proposal with no candidates")
        self._pending = None

    def reject(self, trigger: str | Trigger | None = None,
               trigger_value: float | None = None,
               stamped_at: float | None = None) -> None:
        """Discard the pending proposal, recording that it was computed and not
        taken. The candidates were evaluated, so they count toward breadth even
        though the support did not move."""
        if self._pending is None:
            raise ValueError("nothing proposed to reject")
        move, support, score, n_cand, shown, consistent = self._pending
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score, shown=shown,
                              n_candidates_seen=n_cand)
        self.last_gain = score - self.best_score
        self.failures += 1
        name, params = _trigger_fields(trigger)
        self.log.record(MoveRecord(
            step=info.step, move=Move(kind=move.kind, statistic=move.statistic,
                                      feature=move.feature, note="rejected"),
            support_after=self.support, score_after=self.score,
            n_candidates=n_cand, information=info, timestamp=time.monotonic(),
            trigger=name, trigger_value=trigger_value,
            replayable=True, contradicted=not consistent,
            trigger_params=params, trigger_stamped_at=stamped_at))
        self._pending = None

    def stop(self, trigger: str | Trigger, trigger_value: float,
             replayable: bool = True, stamped_at: float | None = None) -> None:
        """The `stop` meta move. It changes no support, so it is recorded with a
        zero candidate count, its declared trigger, and when that trigger was
        stamped."""
        if self._pending is not None:
            raise ValueError("resolve the pending proposal before stopping")
        stamped_at = time.monotonic() if stamped_at is None else stamped_at
        self._require_declared(trigger, "stop")
        name, params = _trigger_fields(trigger)
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score)
        self.log.record(MoveRecord(
            step=info.step, move=Move("stop"),
            support_after=self.support, score_after=self.score, n_candidates=0,
            information=info, timestamp=time.monotonic(), trigger=name,
            trigger_value=trigger_value, replayable=replayable,
            trigger_params=params, trigger_stamped_at=stamped_at))

    def restart(self, trigger: Trigger, trigger_value: float,
                stamped_at: float, statistic: str = "sharpe") -> bool:
        """The `restart` meta move: abandon the current support for the next
        anchor in the ranking of single features. The best score and its support
        are kept -- a restart changes where the search goes next, not what it has
        already found. Past the last anchor there is nowhere to go, and the move
        is recorded as a stop on the harness's own `exhausted` trigger, as the
        scripted searchers do. Returns whether the restart happened."""
        if self._pending is not None:
            raise ValueError("resolve the pending proposal before restarting")
        self._require_declared(trigger, "restart")
        rank = self.n_restarts + 1
        new_support, new_score, n_cand = self.grammar.anchor(rank, statistic)
        if new_support is None:
            self.stop("exhausted", float(rank), stamped_at=stamped_at)
            return False
        name, params = _trigger_fields(trigger)
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score, n_candidates_seen=n_cand)
        self.support, self.score = new_support, new_score
        self.failures, self.last_gain = 0, float("inf")
        self.n_restarts = rank
        self.log.record(MoveRecord(
            step=info.step, move=Move("restart", statistic=statistic),
            support_after=new_support, score_after=new_score, n_candidates=n_cand,
            information=info, timestamp=time.monotonic(), trigger=name,
            trigger_value=trigger_value, trigger_params=params,
            trigger_stamped_at=stamped_at))
        return True

    def _require_declared(self, trigger, kind: str) -> None:
        """A meta move may only fire a trigger that was declared up front.

        The harness's own conditions (`exhausted`) are not declarations and pass
        through. A session that declared nothing is the pre-amendment path and is
        left alone, so scripted searchers and older logs are unaffected.
        """
        if not self.log.declared_trigger_records or not isinstance(trigger, Trigger):
            return
        if trigger.as_record() not in self.active_trigger_records:
            raise ValueError(
                f"{kind} names {trigger.name!r}, which was not declared before the "
                "first evaluation. Declare it up front, or call change_trigger, "
                "which logs the change and prices the rest of the run as "
                "unreplayable.")

    # -- the prediction slot ----------------------------------------------

    def predict(self, mean: float, sd: float = 0.0, note: str = "") -> None:
        """What the agent thinks the out-of-sample Sharpe will be. Recorded, not
        used: the agent arm's registered analysis regresses stated confidence on
        what the search absorbed, and this is the stated side of that."""
        self.log.prediction = {"mean": float(mean), "sd": float(sd),
                               "note": note, "timestamp": time.monotonic()}

    def submission(self) -> tuple[Support, float]:
        """The best support seen and its score. For a search that only ever
        accepts improvements this is the current support; after a restart it is
        not, and reporting the current one would pair one support's weights with
        another's score."""
        return self.best_support, self.best_score

    def submitted_weights(self) -> np.ndarray:
        return weights(self.best_support, self.grammar.K)


def _trigger_fields(trigger) -> tuple[str | None, dict | None]:
    """A trigger is logged by name, and -- when it is a declared library trigger
    rather than a harness condition like `exhausted` -- by its re-evaluable
    record."""
    if isinstance(trigger, Trigger):
        return trigger.name, trigger.as_record()
    return trigger, None
