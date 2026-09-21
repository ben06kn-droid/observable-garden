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


@dataclass(frozen=True)
class InformationSet:
    """What the agent had been shown before a move. Deliberately not the whole
    sample: it is the answers to queries it actually made."""
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


@dataclass
class SessionLog:
    """One search. Append-only by construction: every mutator adds, none edits."""
    records: list[MoveRecord] = field(default_factory=list)
    prior_pick: dict | None = None
    short_list: tuple | None = None
    prediction: dict | None = None
    opened_at: float = field(default_factory=time.monotonic)
    first_evaluation_at: float | None = None
    # the step budget a meta-adaptive session runs under; None for a plain search
    budget: int | None = None

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
        """Every distinct trigger the session stamped, in order of first use.
        Together they are the declared policy a replay re-evaluates."""
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
