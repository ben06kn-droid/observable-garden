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


class Session:
    def __init__(self, spec_class, base: np.ndarray, annualization: float = 1.0,
                 score_fn=None):
        self.grammar = Grammar(spec_class, base, annualization, score_fn=score_fn)
        self.log = SessionLog()
        self.support: Support = ()
        self.score: float = float("-inf")
        self._pending = None

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

    # -- the search -------------------------------------------------------

    def propose(self, move: Move, shown: tuple = ()) -> tuple[Support, float, int]:
        """Compute a move without committing it, and log the evaluation.

        Proposing is where the data is touched, so it is logged; accepting is a
        decision, so it is recorded separately. Forward selection needs exactly
        this split -- it computes the best extension and keeps it only if it
        improves -- and collapsing the two would either hide an evaluation that
        happened or record a support that was never held.
        """
        new_support, new_score, n_cand = self.grammar.apply(self.support, move)
        if not self.grammar.contains(new_support):
            raise ValueError(
                f"{move.kind} would leave the declared class; the harness refuses "
                "rather than taking the run off-tier")
        self._pending = (move, new_support, new_score, n_cand, tuple(shown))
        return new_support, new_score, n_cand

    def accept(self, trigger: str | None = None, trigger_value: float | None = None,
               replayable: bool = True) -> float:
        """Commit the pending proposal and record it."""
        if self._pending is None:
            raise ValueError("nothing proposed to accept")
        move, support, score, n_cand, shown = self._pending
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score, shown=shown,
                              n_candidates_seen=n_cand)
        self.support, self.score = support, score
        self.log.record(MoveRecord(
            step=info.step, move=move, support_after=support, score_after=score,
            n_candidates=n_cand, information=info, timestamp=time.monotonic(),
            trigger=trigger, trigger_value=trigger_value, replayable=replayable))
        self._pending = None
        return score

    def reject(self, trigger: str | None = None,
               trigger_value: float | None = None) -> None:
        """Discard the pending proposal, recording that it was computed and not
        taken. The candidates were evaluated, so they count toward breadth even
        though the support did not move."""
        if self._pending is None:
            raise ValueError("nothing proposed to reject")
        move, support, score, n_cand, shown = self._pending
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score, shown=shown,
                              n_candidates_seen=n_cand)
        self.log.record(MoveRecord(
            step=info.step, move=Move(kind=move.kind, statistic=move.statistic,
                                      feature=move.feature, note="rejected"),
            support_after=self.support, score_after=self.score,
            n_candidates=n_cand, information=info, timestamp=time.monotonic(),
            trigger=trigger, trigger_value=trigger_value, replayable=True))
        self._pending = None

    def stop(self, trigger: str, trigger_value: float,
             replayable: bool = True) -> None:
        """A meta-move. It changes no support, so it is recorded with a zero
        candidate count and its declared trigger."""
        info = InformationSet(step=self.log.n_moves, support_before=self.support,
                              score_before=self.score)
        self.log.record(MoveRecord(
            step=info.step, move=Move(kind="refine", note="stop"),
            support_after=self.support, score_after=self.score, n_candidates=0,
            information=info, timestamp=time.monotonic(), trigger=trigger,
            trigger_value=trigger_value, replayable=replayable))

    # -- the prediction slot ----------------------------------------------

    def predict(self, mean: float, sd: float = 0.0, note: str = "") -> None:
        """What the agent thinks the out-of-sample Sharpe will be. Recorded, not
        used: the agent arm's registered analysis regresses stated confidence on
        what the search absorbed, and this is the stated side of that."""
        self.log.prediction = {"mean": float(mean), "sd": float(sd),
                               "note": note, "timestamp": time.monotonic()}

    def submission(self) -> tuple[Support, float]:
        return self.support, self.score

    def submitted_weights(self) -> np.ndarray:
        return weights(self.support, self.grammar.K)
