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


# -- milestone 3: meta-adaptive policies with declared triggers ---------------

BUDGET = 12          # the scripted searchers' step budget (searchers/meta_adaptive.py)


def meta_search(session: Session, triggers, budget: int = BUDGET,
                statistic: str = "sharpe") -> None:
    """A meta-adaptive search through the grammar, step for step the loop
    `searchers.meta_adaptive.MetaAdaptive._search` runs.

    `init` takes the best single feature as the anchor. Then, for up to `budget`
    steps, the declared triggers are evaluated in order on the information set and
    stamped; the first that fires decides the step (`stop` or `restart`), and if
    none fires the step is a `continue`: `extend_best` is proposed, and accepted
    only if it beats the best seen, rejected otherwise. Each step's record carries
    the trigger that was evaluated and the value it saw -- on a `continue` too,
    since not firing is also a decision a replicate must be able to re-make.
    """
    triggers = list(triggers)
    session.declare_budget(budget)
    _, _, n = session.propose(Move("init", statistic=statistic))
    if n == 0:
        session.cancel()
        return
    session.accept()

    for _ in range(budget):
        decided, value, stamp = triggers[0], None, None
        for trig in triggers:
            fires, value, stamp = session.evaluate_trigger(trig)
            decided = trig
            if fires:
                break
        else:
            fires = False

        if fires and decided.action == "stop":
            session.stop(decided, value, stamped_at=stamp)
            return
        if fires and decided.action == "restart":
            if not session.restart(decided, value, stamped_at=stamp, statistic=statistic):
                return
            continue

        _, cand, n = session.propose(Move("extend_best", statistic=statistic))
        if n == 0:
            session.cancel()
            session.stop("exhausted", 0.0)
            return
        if cand > session.best_score:
            session.accept(decided, value, stamped_at=stamp)
        else:
            session.reject(decided, value, stamped_at=stamp)


def stop_when_cleared(session: Session, bar: float, budget: int = BUDGET) -> None:
    """`searchers.meta_adaptive.StopWhenCleared(bar)` through the grammar."""
    from quixote.triggers import stop_when_cleared as trig
    meta_search(session, [trig(bar)], budget)


def restart_after_k_failures(session: Session, k: int = 2, budget: int = BUDGET) -> None:
    """`searchers.meta_adaptive.RestartAfterKFailures(k)` through the grammar."""
    from quixote.triggers import restart_after_failures as trig
    meta_search(session, [trig(k)], budget)
