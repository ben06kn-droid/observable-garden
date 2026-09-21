"""Scripted drivers: policies expressed as named moves.

These exist to prove the grammar can express a searcher whose answer is already
known, before any agent is let near it. Milestone 1 is that
`signed_adaptive(session, d)` reproduces `searchers.scripted.SignedAdaptive`'s
submission **bit-identically** on the same base matrix.

If a scripted policy cannot be expressed in the grammar, the grammar is too
narrow and no agent result obtained through it would mean anything.
"""
from __future__ import annotations

from quixote.grammar import Move
from quixote.session import Session


def signed_adaptive(session: Session, max_features: int = 3,
                    statistic: str = "sharpe") -> None:
    """Forward selection over the declared class, each candidate tried at both
    signs, keeping an extension only if it improves.

    The move sequence is: one `extend_best` taken unconditionally (there is
    nothing to improve on), then `extend_best` proposed and accepted while it
    improves. The stop carries its trigger, because when to stop is a meta
    decision and `fixed-sequence-replay` is about exactly those.
    """
    _, score, n = session.propose(Move("extend_best", statistic=statistic))
    if n == 0:
        return
    session.accept()

    for _ in range(max_features - 1):
        before = session.score
        _, cand, n = session.propose(Move("extend_best", statistic=statistic))
        if n == 0:
            session.reject()
            session.stop(trigger="class exhausted", trigger_value=0.0)
            return
        if cand > before:
            session.accept(trigger=f"gain > 0", trigger_value=cand - before)
        else:
            session.reject(trigger="gain > 0", trigger_value=cand - before)
            session.stop(trigger="gain > 0", trigger_value=cand - before)
            return
    session.stop(trigger="budget reached", trigger_value=float(max_features))
