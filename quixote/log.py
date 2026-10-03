"""The information-set log: what the agent could see, and when.

Two things make this more than a transcript.

**Timestamps.** A declaration is only a prior if it preceded the results. The log
records a monotonic timestamp for every entry, so `pick_prior` and item 2's short
list can be *refused* when they arrive late rather than trusted because they were
labelled early.

**Information sets.** Each move records what the agent had seen when it was made
-- the scores it had been shown, not the scores it could have computed. That is
what `pivotal-interrogation` (item 7) rebuilds when it asks the agent to decide
again on a replicate, and it is why the template is fixed here rather than
reconstructed later from a description.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from quixote.grammar import Move, Support


def render_shown(shown) -> str:
    """The canonical rendering of a `shown` payload, used BOTH to build the text
    the agent receives and to reproduce it afterwards.

    One function for both directions is the whole point: the invariant
    `prereg/agent-cell.md` amendment 8 registers is that re-rendering a stored
    `shown` reproduces the payload that was sent, **byte for byte**. If the adapter
    formatted the payload one way and a re-interrogation formatted it another, a
    fidelity measurement would score the agent against numbers it never saw in
    that form.
    """
    return "; ".join(f"{label}={value:.4f}" for label, value in shown)


@dataclass(frozen=True)
class InformationSet:
    """What the agent had been shown before a move. Deliberately not the whole
    sample: it is the answers to queries it actually made.

    `shown` is the **verbatim payload the adapter rendered to the agent at that
    step** (`prereg/agent-cell.md` amendment 8), as `(label, value)` pairs: for a
    `pick`, one pair per candidate with the statistic it was ranked by; for a meta
    move, the trigger state it was evaluated on; for any other content move, the
    state the move was proposed from. `render_shown` turns it back into the text
    that was sent, and the round trip is tested.
    """
    step: int
    support_before: Support
    score_before: float
    shown: tuple[tuple[str, float], ...] = ()   # (label, value) pairs revealed
    n_candidates_seen: int = 0

    def as_context(self) -> dict:
        """The fixed template item 7 rebuilds from: tool calls and results only,
        free-text reasoning stripped. Fixed here so it cannot drift between the
        original session and a re-interrogation."""
        return {"step": self.step,
                "support": [list(p) for p in self.support_before],
                "score": self.score_before,
                "shown": [list(p) for p in self.shown]}


@dataclass
class MoveRecord:
    step: int
    move: Move
    support_after: Support
    score_after: float
    n_candidates: int
    information: InformationSet
    timestamp: float
    # meta-moves carry a declared trigger; content moves do not
    trigger: str | None = None
    trigger_value: float | None = None
    replayable: bool = True
    # milestone 3: the declared trigger as a re-evaluable record (kind, param,
    # action), and when it was stamped -- before the move it justified executed
    trigger_params: dict | None = None
    trigger_stamped_at: float | None = None
    # A `pick` whose named choice is not what its declared rule selects. The
    # HARNESS executed the rule, so the move itself is replayable -- a replicate
    # re-derives the same selection from the same rule. What is contradicted is
    # the agent's STATEMENT about its own choice, which is a fact about the
    # agent, not about the move (decided 2026-09-25).
    contradicted: bool = False


@dataclass
class SessionLog:
    """One search. Append-only by construction: every mutator adds, none edits."""
    records: list[MoveRecord] = field(default_factory=list)
    prior_pick: dict | None = None
    short_list: tuple | None = None
    prediction: dict | None = None
    # The stopping policy, declared before the first evaluation like every other
    # declaration slot, and the log of any later change to it. A trigger named
    # only at the moment of stopping is a description offered afterwards, not a
    # commitment the search ran under: the agent pilot found two runs of three
    # declaring a stop rule their own search does not satisfy
    # (`prereg/agent-pilot.md`). A change is allowed and is a data-dependent
    # decision, so it is logged with its timestamp and priced as unreplayable.
    declared_trigger_records: tuple = ()
    trigger_changes: tuple = ()
    opened_at: float = field(default_factory=time.monotonic)
    first_evaluation_at: float | None = None
    # the step budget a meta-adaptive session runs under; None for a plain search
    budget: int | None = None
    # The close-time self-check (registered 2026-09-28, implemented after 7.3
    # scripted): re-executing this log on the realized data at the moment the
    # session closes, recorded here so a stored run carries its own verdict on
    # whether it can be replayed. None until `Session.close()` runs.
    #
    # Every replay defect found on 2026-09-28 -- an indexing shift, a step bound, a
    # `flip` anchored on the realized support -- was invisible until something
    # replayed a log much later. A check at close catches them while the session
    # that produced them still exists.
    self_check: dict | None = None
    # True for a log opened through `quixote.agent_adapter.ToolSession`, i.e. the
    # AGENT path. Such a log must carry a declared budget: the harness's own turn
    # limit is that budget and is written at session open, so a replay has no
    # business guessing one (`prereg/agent-cell.md` amendment 10).
    agent_driven: bool = False
    # The cap on CONTENT moves a session may make, or None. 7.5's unsaturable arm
    # runs at 3 (`prereg/planted-edge.md`, "The unsaturable arm"); the harness
    # refuses the fourth. Recorded on the log so a stored run says what it ran under.
    content_cap: int | None = None

    # -- append-only ------------------------------------------------------

    def record(self, rec: MoveRecord) -> None:
        self.records.append(rec)
        if self.first_evaluation_at is None:
            self.first_evaluation_at = rec.timestamp

    @property
    def n_moves(self) -> int:
        return len(self.records)

    def moves(self) -> list[Move]:
        return [r.move for r in self.records]

    def kinds(self) -> list[str]:
        return [r.move.kind for r in self.records]

    def is_meta(self) -> bool:
        """A session run under a budget with declared triggers, as opposed to a
        plain forward selection."""
        return self.budget is not None

    def declared_triggers(self) -> list[dict]:
        """The stopping policy a replay re-evaluates.

        The pre-declared set when there is one, which is the registered path.
        A session that declared none falls back to the triggers it stamped in
        use, which is what `fixed-sequence-replay`'s scripted searchers do --
        their policy IS code, so the two coincide -- and what agent logs written
        before the declaration slot existed hold.
        """
        if self.declared_trigger_records:
            return [dict(t) for t in self.declared_trigger_records]
        out = []
        for r in self.records:
            if r.trigger_params is not None and r.trigger_params not in out:
                out.append(r.trigger_params)
        return out

    def actions(self) -> list[str]:
        """The meta decision at each step after the anchor, in the vocabulary of
        `searchers.meta_adaptive`: an extension proposed (taken or not) is
        "continue", and `restart` and `stop` are themselves."""
        out = []
        for r in self.records[1:]:
            k = r.move.kind
            out.append(k if k in ("restart", "stop") else "continue")
        return out

    def unreplayable(self) -> list[MoveRecord]:
        """The decisions item 1's bracket is about."""
        return [r for r in self.records if not r.replayable]

    def contradicted_picks(self) -> list[MoveRecord]:
        """Picks whose named choice is not what their rule selected. Reported,
        and NOT unreplayable: the harness ran the rule."""
        return [r for r in self.records if r.contradicted]

    def total_candidates(self) -> int:
        """Trials actually offered to the agent by the harness. This is a count
        of what was computed, not of what the agent said it considered."""
        return sum(r.n_candidates for r in self.records)

    # -- timestamp discipline ---------------------------------------------

    def refuse_if_late(self, what: str) -> None:
        """A prior declaration must precede every evaluation. Raises rather than
        recording a flag, because a late prior is not a weaker prior -- it is a
        different object, and silently down-weighting it would let the run
        continue under a label it has not earned."""
        if self.first_evaluation_at is not None:
            raise ValueError(
                f"{what} arrived after the first evaluation at "
                f"t={self.first_evaluation_at:.6f}; a declaration made after "
                "seeing results is not a prior and is refused, not discounted")
