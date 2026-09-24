"""Don Quixote: the agent-facing form of the gate.

Named for the knight who had read too many romances and so saw giants where
there were windmills. That is the failure this package measures -- a rich prior
fitted to sparse data -- not a loose analogy to it.

What is here is 7.2 part one: everything whose design does not depend on what
`fixed-sequence-replay` (7.1) reports. The harness executes the moves, so the log
cannot disagree with what ran; the log carries timestamps, so a declaration made
after seeing results can be refused rather than trusted; and the twin generator
and masking exist so a run can be scored against placebo datasets.

**7.1 has reported (2026-09-24), so two of these are now decided and built:**

- **which null certifies: trigger replay** (`quixote/certify.py`). Its rejection
  rate came in at or below nominal for all six registered searchers, so it is
  valid to certify with; the rates sit under nominal as P2 predicts, and no
  exactness is claimed.
- **the fill**: the best one-step content move over extend, swap and flip, with
  the declared triggers still evaluated at every filled step. 7.1 measured its
  direction as liberal against a width-2 beam and conservative against
  continuations it dominates, with no verdict moved, so every verdict whose
  replicates used it says so.

**Built but not licensed** (`quixote/pricing.py`): local-max pricing and
fidelity-driven pricing, both behind flags that default to off. Both rest on the
conjecture that anchoring later moves on a local maximum is conservative, which
7.3 tests and which has not reported, so a verdict that used either says it is
unlicensed and names what would license it.

**Part one is complete.** The consistency check (`quixote/consistency.py`),
`pick` with its statistic library and `else` branch (`quixote/statistics.py`,
the grammar's `pick` move), and the twin generator with identifier masking
(`quixote/twins.py`) are built and tested. Two things are deliberately absent
from them and say so: **IC**, because it needs the panel a replicate does not
have, and **sequential twin stopping**, because Besag & Clifford's two open
checks are unresolved.

Still deliberately NOT here: the living verdict (item 3), which waits until
after the paper.

`Verdict` carries the fields those will populate, stubbed and marked.

Dependency direction is one-way and enforced by test: nothing imports `quixote`,
and `quixote` stays out of `CODE_PATHS`. What quixote itself imports is not
restricted; today that is `garden`, `estimator`, `environments` and `searchers`.
`quixote` is deliberately absent from `experiments.code_state.CODE_PATHS`, so
adding it moves no published fingerprint; quixote runs record their own
fingerprint instead. See `quixote/fingerprint.py`.
"""
from quixote.certify import CERTIFYING_NULL, certify, three_nulls
from quixote.consistency import check_picks
from quixote.pricing import PricingOptions
from quixote.statistics import STATISTICS
from quixote.twins import Masking, twin_p_value, twins
from quixote.grammar import Grammar, Move, Support
from quixote.log import InformationSet, MoveRecord, SessionLog
from quixote.verdict import QuixoteVerdict

__all__ = ["Grammar", "Move", "Support", "InformationSet", "MoveRecord",
           "SessionLog", "QuixoteVerdict", "certify", "three_nulls",
           "CERTIFYING_NULL", "PricingOptions", "check_picks", "STATISTICS",
           "twins", "twin_p_value", "Masking"]
