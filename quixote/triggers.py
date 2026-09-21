"""Declared triggers: the predicates behind `restart` and `stop`.

A meta move is only replayable if the reason it was taken can be re-evaluated on
a replicate. So a trigger is not free text: it is a named predicate from this
fixed library, with its parameter, over the information set the harness keeps
(best so far, moves since the last improvement, the last gain, budget left). The
session evaluates it and stamps the name, the parameter and the value it saw
**before** the move executes, so the log cannot record a reason chosen after the
fact.

The names are the strings `searchers/meta_adaptive.py` records, so a scripted
searcher and its grammar-driven twin log the same trigger.

Nothing here decides what a trigger replay certifies, or what fills a replicate
that runs past the declared triggers. Both are 7.2 part two, decided by 7.1.
"""
from __future__ import annotations

from dataclasses import dataclass

ACTIONS = ("stop", "restart")


@dataclass(frozen=True)
class Trigger:
    """`kind` names the predicate; `param` is its one parameter; `action` is the
    meta move taken when it fires."""
    kind: str
    param: float
    action: str

    def __post_init__(self):
        if self.kind not in PREDICATES:
            raise ValueError(f"unknown trigger {self.kind!r}; the library is {tuple(PREDICATES)}")
        if self.action not in ACTIONS:
            raise ValueError(f"trigger action must be one of {ACTIONS}")

    @property
    def name(self) -> str:
        return PREDICATES[self.kind][0](self.param)

    def evaluate(self, state: dict) -> tuple[bool, float]:
        """(fires, value seen), on the information set `state`."""
        return PREDICATES[self.kind][1](state, self.param)

    def as_record(self) -> dict:
        return {"kind": self.kind, "param": self.param, "action": self.action}

    @classmethod
    def from_record(cls, rec: dict) -> "Trigger":
        return cls(rec["kind"], rec["param"], rec["action"])


# kind -> (name(param), predicate(state, param) -> (fires, value))
PREDICATES = {
    # stop once the best seen beats a bar fixed before the search
    "best_so_far_above": (lambda p: "best_so_far > bar",
                          lambda st, p: (st["best"] > p, st["best"] - p)),
    # restart after k consecutive non-improving extensions
    "failures_at_least": (lambda p: f"failures >= {int(p)}",
                          lambda st, p: (st["failures"] >= int(p), float(st["failures"]))),
    # stop once the last extension gained no more than min_gain
    "last_gain_at_most": (lambda p: f"last_gain > {p}",
                          lambda st, p: (st["last_gain"] <= p, float(st["last_gain"]))),
}


def stop_when_cleared(bar: float) -> Trigger:
    return Trigger("best_so_far_above", float(bar), "stop")


def restart_after_failures(k: int) -> Trigger:
    return Trigger("failures_at_least", float(int(k)), "restart")


def stop_unless_improving(min_gain: float = 0.0) -> Trigger:
    return Trigger("last_gain_at_most", float(min_gain), "stop")
