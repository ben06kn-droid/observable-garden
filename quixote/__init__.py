"""Don Quixote: the agent-facing form of the gate.

Named for the knight who had read too many romances and so saw giants where
there were windmills. That is the failure this package measures -- a rich prior
fitted to sparse data -- not a loose analogy to it.

What is here is 7.2 part one: everything whose design does not depend on what
`fixed-sequence-replay` (7.1) reports. The harness executes the moves, so the log
cannot disagree with what ran; the log carries timestamps, so a declaration made
after seeing results can be refused rather than trusted; and the twin generator
and masking exist so a run can be scored against placebo datasets.

Deliberately NOT here, because 7.1 decides them:

- which null certifies (trigger replay against a declared policy),
- the fill inside the agent path,
- local-max pricing as a certifier,
- fidelity-driven pricing,
- the living verdict (item 3), which waits until after the paper.

`Verdict` carries the fields those will populate, stubbed and marked.

Dependency direction is one-way and enforced by test: nothing imports `quixote`,
and `quixote` stays out of `CODE_PATHS`. What quixote itself imports is not
restricted; today that is `garden`, `estimator`, `environments` and `searchers`.
`quixote` is deliberately absent from `experiments.code_state.CODE_PATHS`, so
adding it moves no published fingerprint; quixote runs record their own
fingerprint instead. See `quixote/fingerprint.py`.
"""
from quixote.grammar import Grammar, Move, Support
from quixote.log import InformationSet, MoveRecord, SessionLog
from quixote.verdict import QuixoteVerdict

__all__ = ["Grammar", "Move", "Support", "InformationSet", "MoveRecord",
           "SessionLog", "QuixoteVerdict"]
