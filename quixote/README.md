# Don Quixote

*He had read too many chivalric romances. Give him an inn and he saw a castle;
give him a windmill and he saw a giant.*

That is not a joke about the name. Quixote's failure was not stupidity — it was
a rich prior fitted to sparse data, which is the failure this gate measures. A
backtest that reports a Sharpe of 2.03 against a population ceiling of 1.00 is
not a lie; it is a windmill seen by someone who came expecting giants.

`quixote/` is the **agent-facing** form of the gate in `garden/`. Where `garden`
audits a finished transcript, `quixote` sits inside the search while it happens.

**Status: 7.2 part one.** Everything whose design does not depend on what
`fixed-sequence-replay` (7.1) reports. Several deliberate holes, listed at the
bottom. Nothing here is claimed to be novel; prior art is recorded in the
pre-registrations, and where it has not been searched, that is said.

---

## Why an agent needs a different gate

The declared-class gate prices **trials**: it asks how wide a menu the searcher
could have drawn from, and charges for the width. That works because a scripted
searcher's menu is fixed before it starts.

An agent's is not. It decides what to try *next*, based on what it just saw. Its
menu is a function of the data, which is precisely the condition under which the
Reality Check's correction stops being valid (THEORY.md, P4). Worse, the
interesting part of what an agent does is not the trials at all — it is the
**decisions**: when to stop, when to abandon a line, which of two equally-scored
extensions to take.

So the object to price is the decision, and to price a decision you need to know
what it was and what it could have been. That is what this package records.

---

## The central idea: the harness executes the move

The agent **names** a move. The harness **computes** it.

```python
session.propose(Move("extend_best", statistic="sharpe"))
session.accept()
```

At no point can a caller hand in its own specification. `Grammar.apply` builds
it, from the class, from the data, deterministically. This is the whole
foundation: **the log cannot disagree with what ran, because the log is what
ran.**

An agent that constructed its own specifications could describe one thing and
submit another, and no amount of later checking would catch it — the transcript
would be internally consistent and wrong. Harness execution removes the
possibility rather than auditing for it.

It has a second consequence that matters more for inference: because every move
is a pure function of (support, data, statistic), a bootstrap replicate can
**re-execute it exactly**. A search that can be re-executed can be priced.

---

## The modules

| module | what it holds |
|---|---|
| `grammar.py` | `Move`, `Grammar` — the five content moves and the statistic library |
| `log.py` | `SessionLog`, `MoveRecord`, `InformationSet` — what happened, and what could be seen when |
| `session.py` | `Session` — the harness a searcher drives |
| `drivers.py` | scripted policies expressed as named moves |
| `replay.py` | `LoggedPolicy`, `identity_check` — re-executing a log on fresh data |
| `verdict.py` | `QuixoteVerdict` — the bracket and bits fields |
| `fingerprint.py` | what pins a quixote run to its code |

### `grammar.py`

Five content moves, from ROADMAP 7.2: `init`, `extend_best`, `swap_worst`,
`flip`, `refine`.

A **support** is a tuple of `(feature, sign)` pairs. Signs are carried even for
unsigned classes, where they are all `+1`. That costs a little redundancy and
buys two things: `flip` is a real move rather than a special case, and one
representation serves both class kinds. `Grammar` reads `signed` off the class,
so an unsigned class **cannot** produce a `-1` and `flip` returns no candidates
there — the declared class is enforced by construction, not by checking.

`candidates()` enumerates in a fixed order — feature ascending, then sign
`(+1, -1)` — so a tie resolves identically on every replicate. `apply()` returns
the chosen support, its score, **and the number of candidates considered**. That
count is what `effective_breadth` and item 6's bits are computed from, so it is
returned at the point it is known rather than reconstructed later from a
description of the move.

**The statistic library refuses what it has not built.** `sharpe` is
implemented; `stability` is pre-registered in
`prereg/stability-statistic.md` and raises here, naming itself as deliberately
unbuilt. A silent fallback to Sharpe would be the worst outcome.

### `session.py` — and the propose/accept split

The single least obvious design decision in the package.

Forward selection computes the best extension and **keeps it only if it
improves**. Collapsing that into one call would force a choice between two
wrong records: either the evaluation is hidden when the extension is rejected,
or a support is recorded that was never held.

So:

- **`propose(move)`** computes the move and stages it. This is where the data is
  touched.
- **`accept()`** commits it and records the move.
- **`reject()`** discards it and records that the candidates *were computed and
  not taken*.

A rejected proposal still counts its candidates toward breadth. They were
evaluated; the searcher saw them; they are trials.

**Two ways to score, and the caller picks.** `Session.on_sandbox()` scores
through `Sandbox.evaluate`, so every candidate is a logged sandbox trial and the
number the search optimises is bit-for-bit the number the gate will grade. The
default path sums base feature columns, which is the only thing available on a
bootstrap replicate where there is no `(T, M, K)` panel. **The two are not
bit-identical** — the sandbox builds a portfolio stream from the full panel and
the replay sums columns, accumulating floating point differently. They agree to
about 1e-12, for exactly the reason `searchers/scripted.py` already records.

**Timestamps refuse rather than discount.** `pick_prior` and the item 2 short
list raise if they arrive after the first evaluation. A late prior is not a
weaker prior — it is a different object, and silently down-weighting it would
let a run continue under a label it has not earned.

### `replay.py` — and the identity guard

`LoggedPolicy` reads a log back as a policy: the move kinds it proposed and the
triggers it declared, re-executed against a `Grammar` on whatever base matrix it
is handed. If a log cannot be re-run, nothing downstream can price what the
search did.

**`identity_check`** is the guard that makes the two scoring paths safe to mix.
Replay the *un-resampled* data through the base-column path and compare move
sequences against the realized ones. The paths differ at ~1e-12; on a near-tie
that can flip an argmax; and an argmax flipped early in a forward selection
changes every move after it, so the replayed policy would be pricing a search
that never ran.

A run whose own replay disagrees with it is **flagged and not priced**. There is
no defensible way to price such a run.

Measured fire rate: **0 of 300** runs across 150 seeds and two class widths,
median score gap `0.00e+00`, maximum `1.33e-15`. Rare, real, and cheap to check
— which is the case for an always-on guard.

### `verdict.py`

`QuixoteVerdict` carries item 1's bracket (`p_frozen`, `p_upper`) and item 6's
bits, plus a new state **`DEPENDS_ON_JUDGMENT`** with exit code 5, alongside
`garden/cli.py`'s existing 0–4.

**These fields are declared and not computed.** The bracket's ends are licensed
by experiments that have not reported — 7.1 for the lower, 7.3 for the upper —
and filling them in now would assert the thing under test. They are `None`, and
`standard_reasons()` says so rather than leaving a reader to infer it.

Bits carry a permanent reasons line: **descriptive, never entering the
correction.**

### `fingerprint.py`

`quixote` is deliberately **absent** from `experiments.code_state.CODE_PATHS`.
Adding it would move every published fingerprint, and a fingerprint that moves
for a reason unrelated to the runs it pins is worse than none.

Quixote runs record their own, over `QUIXOTE_PATHS` — quixote **plus everything
quixote imports**.

**The dependency constraint is exactly two rules:** nothing imports `quixote`
(a test asserts it across `garden`, `estimator`, `environments`, `searchers` and
`experiments`), and `quixote` stays out of `CODE_PATHS`. Which packages quixote
itself imports is not restricted. Today it imports `garden`, `estimator`,
`environments` and `searchers` — the last for 7.1's registered scripted fill in
the meta replay — and all four are inside `QUIXOTE_PATHS`, because a change in
any of them changes what a quixote run does.

`code_fingerprint()` gained an optional `paths` argument to make this possible
without widening `CODE_PATHS`. One related change did move the fingerprint —
adding `quixote` to pyproject's `packages` list, since `pyproject.toml` is itself
in `CODE_PATHS`. That is recorded as amendment 14 in `prereg/AGENT_PROMPTS.md`,
with the reason: packaging only, no behavioural change, and stored runs keep
their recorded fingerprints per amendment 13.

---

## The three milestones

The first two were required before building further, and both came out **bit-identical**
rather than merely close.

**Milestone 1 — the grammar can express a known searcher.** A scripted driver
naming moves through the harness reproduces `SignedAdaptive`'s submission on
80 of 80 configurations across 20 seeds and four class shapes: identical Sharpe
*and* identical weights.

This did not work first time. The first attempt matched weights everywhere but
differed in the Sharpe's last bits on 16 of 36 cells — two implementations of
one statistic, the exact drift `searchers/scripted.py` warns about. The fix was
the scoring-path parameter above, not a tolerance.

**Milestone 2 — the log replays to the same null.** The session log, read back
as a `LoggedPolicy` and run through `estimator/trigger_replay.py`, returns a null
**equal** to `SignedAdaptive`'s own recursive replay null — difference
`0.00e+00` across eight cells. Predicted ~1e-12; exact because both paths sum
base columns in the same order.

If either had failed, the grammar would be too narrow to stand in for a searcher
and nothing obtained through it would mean anything.

**Milestone 3 — meta moves replay too.** `restart` and `stop` are grammar moves,
each taken because a declared trigger fired: a named predicate from
`quixote/triggers.py` with its parameter, stamped with the value it saw **before**
the move executes. The session tracks the information set the triggers read
(best so far with its support, failures, last gain, budget), and the submission
is the best pair, never the current support. Against the scripted
`StopWhenCleared` and `RestartAfterKFailures`:

- (a) the grammar-driven submission is **bit-identical** in Sharpe and weights,
  and the step-by-step actions match, on 60 cases (five trigger settings × six
  seeds × two signal levels), 24 with restarts and 24 with stops;
- (b) the log through `estimator/trigger_replay.py` returns the **same three
  nulls** (fixed-sequence, trigger, policy), realized score and realized actions,
  array-equal, in all 15 cells tested; re-declaring the logged stop bar moves the
  policy null and leaves the frozen one alone, so the replay is reading the
  triggers and not merely agreeing;
- (c) the identity-replicate guard compares the action sequence as well as the
  support, reproduces every realized stop and restart, and catches a constructed
  restart recorded as an extension.

Two things this needed first. `MetaAdaptive` itself reported the current support
with the global best score after a restart, and was fixed before this milestone
(7.1 amendment 5). And the grammar's base-column Sharpe now calls
`estimator.bootstrap.sharpe`, guards included, so a replay scores exactly as the
scripted searchers do rather than agreeing away from degenerate streams.

The trigger null's fill past the realized length is **7.1's registered scripted
fill**, imported from `searchers.meta_adaptive`, because (b) is about reproducing
that searcher's own null. It is not a choice of fill for an agent's path.

---

## Deliberately not built

These wait on `fixed-sequence-replay` (7.1), which decides their design. Building
them now would mean guessing, and the guess is the thing under test.

- **which null certifies** — trigger replay against a declared policy
- **the fill inside the agent path**
- **local-max pricing as a certifier** — 7.3's conjecture
- **fidelity-driven pricing**
- **the living verdict** (item 3), which waits until after the paper

Still to come in part one, in order: the **real-data sandbox** (panel loader, no-out-of-sample variant,
offline grading), the **consistency check**, `pick`, and the **twin generator with
identifier masking**.

---

## Reading order

`ROADMAP.md` Phase 7 for where this sits and what gates what.
`prereg/bracketed-verdicts.md`, `prereg/bits-of-selection.md` and
`prereg/twin-calibration.md` for the fields the verdict carries.
`tests/test_quixote_milestones.py` for what is actually guaranteed.
