# agent-pilot: does the harness survive a model on a real panel?

Committed before any model-backed run on a real panel. **This pre-registration
claims no verdict.** Its two purposes are a harness shake-out and a measurement
of engagement, and its decision rules say what happens next in each case; none of
them licenses a claim about a certifier, a gate or a strategy.

## Why a pilot, and why before 7.3

7.1 reported on 2026-09-24 and licensed the replay tier: trigger replay's
rejection rate was at or below nominal for all six registered searchers, so
`quixote/certify.py` is built on it. What no experiment has done is put a
**model** behind the grammar. Everything upstream of that is scripted policies,
whose every move is a function the harness can re-execute.

The failures a pilot catches are not statistical, which is why running it before
a design that costs a seat window matters:

- an agent that cannot use the grammar at all, or that spends its turns on
  refused moves;
- an agent that never calls `stop` with a trigger, so every run ends at
  `max_turns` and there is no meta move to replay;
- masking making `pick_prior` and `short_list` unusable in practice
  (`AGENT_PROMPTS_REAL.md` §4 records this as the first suspect if engagement is
  zero);
- the adapter refusing something it should allow, or allowing something it should
  refuse, on inputs a model produces and a scripted policy never does;
- per-run token cost far from the $0.268 mean the 661 stored runs give, which is
  what every seat estimate in `ROADMAP.md` rests on.

**7.0 licenses nothing here.** It is measuring power at matched actual size and
the tier order; its rules do not bear on whether a model can drive the grammar.
7.1 licensed the tier this pilot exercises, and that is the only licence the
pilot needs.

## Design

**Panel: the ADR panel of `prereg/adr-universe.md` and `prereg/adr-features.md`**
(K = 22, 18 treated names under the registered fallback, plus the three placebo
controls), masked per `AGENT_PROMPTS_REAL.md` §4. The ETF panel of 6.5 is **not**
used: its holdout exists in exactly two copies and is opened once, and a pilot is
the wrong reason to spend that.

**Runs: 5.** Not 40. A pilot that costs a seat window is not a pilot.

| arm | runs | prompt |
|---|---|---|
| control | 2 | `AGENT_PROMPTS_REAL.md` §2 control |
| replay gate | 3 | `AGENT_PROMPTS_REAL.md` §2 replay gate |

**Fixed before the first run:** `claude-sonnet-5`, thinking off, `max_turns = 60`,
class signed depth ≤ 3, one fixed in-sample panel shared by every run, the
registered ADR cost model (5-minute Abdi–Ranaldo with the `max(1c, 2bps)` floor,
amendment 1 of `adr-features.md`). Seeds: the first 5 draws of
`default_rng(20260924)`, recorded in the run index.

**Recorded per run**, all of it mechanical: the full information-set log, every
tool call and its result, every refusal with its reason, turns used, tokens and
dollars, whether `submit` was reached, the submitted support and its net
in-sample Sharpe, and — for the replay arm — the moves by kind, the triggers
named, and whether the certifying null could be computed at all.

**Not recorded, deliberately:** no out-of-sample number is computed for any pilot
run, and no verdict is issued. The ADR holdout is 7.4's, and a pilot that touched
it would spend a one-shot resource to shake out a harness.

## What is measured

1. **Engagement rate**, per arm: the share of turns that are accepted grammar
   moves, as `fixed-sequence-replay` defines engagement for its searchers.
2. **Refusal rate and reasons**, per arm, by refusal kind: unknown tool, trigger
   did not fire, unknown trigger, declaration after the first evaluation, move
   outside the class, post-submit call.
3. **Meta-move usage**: how many runs call `stop` with a trigger that fires, and
   which triggers.
4. **Declaration usage**: how many runs use `pick_prior` (the replay arm) — the
   number `AGENT_PROMPTS_REAL.md` §4 says to read against masking.
5. **Cost per run**, against the $0.268 stored mean.
6. **Whether the certifying null is computable** for each replay-arm run: does
   the log support trigger replay end to end.

## Decision rules

Every branch below changes what is built or what is registered next. **None
concludes anything about a certifier, a gate or a strategy**, and the report says
so in its first line.

1. **Harness integrity (the only blocking rule).** Every refusal a pilot run
   receives is one of the six registered kinds above, and every accepted move
   appears in the log with the support the harness computed.
   - *Holds:* the harness is sound under model input and 7.3's agent cell may be
     designed against it.
   - *Fails:* an unregistered refusal, or a move accepted but absent from the log,
     is a **defect**. It is fixed, the fix is committed with a test, and the pilot
     is re-run. The failed pilot is reported, not discarded.
2. **Engagement, descriptive, no threshold.** The engagement rate and refusal
   profile are reported per arm.
   - *Engagement is high:* 7.3's agent cell is designed at its registered size.
   - *Engagement is low or refusals dominate:* the **prompt** is the suspect, not
     the model. An amendment to `AGENT_PROMPTS_REAL.md` may add instruction —
     recorded as an amendment, dated, before any further run — and the pilot is
     re-run. A pilot may be re-run; 7.3 may not.
   - *No run calls `stop` with a firing trigger:* the replay tier has no meta move
     to price on agent data, which is reported as a design finding and sends 7.3's
     agent cell back to the drawing board rather than to a bigger n.
3. **Declaration usage against masking.** If no replay-arm run uses `pick_prior`,
   that is reported with `AGENT_PROMPTS_REAL.md` §4's sentence cited: masking is
   the first suspect, and it is **not** evidence that models lack priors.
4. **Cost.** The measured per-run cost is reported beside the $0.268 stored mean.
   If it exceeds it by more than 3×, every seat estimate in `ROADMAP.md` that
   rests on that mean is re-stated before 7.3 is scheduled.
5. **No verdict claim, standing.** No number from this pilot enters a verdict, a
   headline, a figure in the note, or any rate reported as a calibration or a
   power. If a pilot number is quoted anywhere, it is quoted as a pilot number
   with n = 5 beside it.

## Cost

Seat: 5 runs at the stored $0.268 mean, about **$1.35**, which is the point.
Local: the ADR panel build and the grader. No EC2, no holdout access.

## Amendments

Dated entries are appended here.

**1 — 2026-09-24, before any model-backed run. A seventh refusal kind, and the
harness gap that produced it.**

The dry run of `experiments/agent_pilot.py` — scripted policies over the real
tool surface, no model called — found that nothing latched the session after a
`stop`. An agent could call `stop` twice and both would be logged. That is not a
search any replicate can reproduce: trigger replay is told how many moves the
realized search took, and a second stop makes that number a fiction.

`quixote/agent_adapter.py` now latches: after a stop that fires, only `predict`
and `submit` are taken and every other call is refused. **"What is measured" 2's
list of refusal kinds gains a seventh, `after_stop`**, so a run that receives one
is measured rather than counted as rule 1's blocking failure.

This is what the pilot is for, and it was found before the seat was spent rather
than after.

**2 — 2026-09-24, after the first pilot attempt failed rule 1 and before the
re-run. Argument validation is a refusal kind, and the prompt was missing the
statistic library.**

The first attempt (5 runs, $0.60, report kept at
`runs/agent_pilot/pilot_report_attempt1_FAILED.txt`) **failed rule 1** with three
unregistered refusals:

| run | refusal |
|---|---|
| pilot_0 control | `feature 22 is outside 0..21` |
| pilot_1 control | `feature 22 is outside 0..21` |
| pilot_4 replay | `unknown statistic 'in-sample Sharpe with [1+,0+,x]'` |

Neither is a harness defect in the sense rule 1 imagined. Both are the harness
**correctly** refusing a malformed argument, and the registered list of six kinds
simply did not anticipate argument validation at all. The fix is therefore to the
registration, not to the code, and it is recorded here rather than made silently:

- **`malformed_arguments`** joins the list as an eighth kind: an argument the
  harness cannot interpret — a feature index out of range, a repeated feature,
  a sign that is not ±1, a statistic outside the committed library.

**Separately, and this one is a prompt fault.** The replay arm's prompt names the
trigger library explicitly but says only "a statistic you name" for `pick`, so an
agent had no way to know what the statistics are and supplied prose. Rule 2's
branch applies — the prompt is the suspect, not the model — so
`AGENT_PROMPTS_REAL.md` amendment 2 names the library, and the pilot is re-run.
**`pick` was attempted once in five runs and never succeeded**, so the first
attempt measured nothing about picks.

The re-run is a re-run, not a second pilot: the first attempt's report is kept,
its failure is reported, and both are read together.

## Open, to fix before the first pilot run

- **~~The code fingerprint does not yet cover these prompts.~~ Done 2026-09-24,
  before the first pilot run** (`e4d75d4`). `experiments/real_prompts.py` joined
  `CODE_PATHS`, and the design sections of `prereg/AGENT_PROMPTS_REAL.md` joined
  the fingerprint through their own `real_prereg_design_md5()`, kept separate so
  the `prereg_design_md5` field already stored in every run's `config.json`
  keeps meaning what it meant when it was written.

  **The discontinuity, dated.** At HEAD `40a07ef`, with nothing else changed,
  the fingerprint moved

  | | fingerprint |
  |---|---|
  | before the widening | `a270169ae0a687e8` |
  | after the widening, same HEAD | `767ba01dd661a4b4` |
  | at the commit that introduced it (`e4d75d4`) | `e68614f41b8199c0` |

  The first step is the widening alone; the second is the ordinary movement any
  commit to a covered path causes. **A run stored before 2026-09-24 pins a
  narrower set of inputs than one stored after it**, and no stored run is
  retroactively re-fingerprinted.
- **The pilot runner does not exist.** It is `experiments/`-side work: build the
  masked ADR panel, open the class, drive `quixote/agent_adapter.py` for the
  replay arm and the plain surface for control, and store the log, the refusals
  and the cost per run. Nothing about it is registered here beyond what the
  Design and Recorded sections already fix.
- **`searchers/meta_adaptive.py` changed on 2026-09-24** (the class filter now
  runs before the scorer, `761e64d`), which moves the code fingerprint. It is a
  correctness fix with the uncapped path proved unchanged, and it precedes every
  pilot run.


**3 — 2026-09-24, after the second attempt and before the third. `pick` could
not succeed at a full support, and the certifying null cannot price an agent run
on this panel.**

The second attempt (report kept at `runs/agent_pilot/pilot_report_attempt2.txt`)
**passed rule 1** — every refusal was a registered kind — and still exposed two
things rule 1 could not catch, because a registered refusal is a measurement
rather than a failure.

**(i) A defect: `pick` at a full support.** All three replay-arm runs spent a turn
on `outside_class`, and the specification names in those refusals were the
harness's own. `Grammar.pick_candidates` built candidates one feature larger than
the support with no class check, so at a support of size 3 every candidate was
size 4 and the sandbox refused — correctly. `extend_best` has had that guard all
along; `pick` did not. **`pick` therefore could not succeed in any pilot run, and
"picks accepted vs contradicted" measured nothing in either attempt.** Fixed in
`quixote/grammar.py`, with two tests, and the pilot is run a third time so that
measurement is not vacuous.

**(ii) A finding, not a defect: the certifying null is computable but not
priceable on a net-of-cost panel.** All three replay-arm logs replayed without
error, and all three verdicts came back **UNDECIDABLE** on the identity-replicate
guard, with realized-against-replayed score gaps around **7.4** — three orders of
magnitude beyond float accumulation. The cause is structural and is recorded in
`environments/real_sandbox.py` already: `base_feature_columns` is a **diagnostic**
basis, the sandbox scores **net of costs**, and costs are not linear in the
weights, so the replay is not pricing the statistic the search optimised. The
guard is right to refuse.

**What that means for what is registered elsewhere**, stated here and not
quietly:

- **`prereg/agent-on-real-data.md`'s replay arm is conditional** on 7.2 part two
  existing when 6.5 goes live. It exists — and this pilot shows that on a
  net-of-cost real panel it cannot price a run as built. Either the replay path
  gains a cost-aware basis, or 6.5 records the replay arm as deferred for this
  reason rather than for absence.
- **7.3's agent cell** runs on the simulated panel, where the two paths agree to
  ~1e-12, so this does not touch it.
- The guard's message no longer asserts float accumulation whichever way it
  fails: it reports the measured gap and names the structural cause when the gap
  is too large to be float noise.

No number from any attempt enters a verdict; rule 5 stands.

## Reading, 2026-09-24 (attempt 3, the one that stands)

**No verdict is claimed.** n = 5. Every number below is a pilot number.

**Rule 1 — harness integrity: holds.** Every refusal was one of the eight
registered kinds; one `malformed_arguments` (a control-arm run naming feature 22
of 0–21) and nothing else. The `outside_class` refusals that attempt 2 produced
in every replay-arm run are gone, which is what amendment 3's fix predicted.

**Rule 2 — engagement (descriptive).** Every one of the 5 runs submitted.

| run | arm | tool calls | accepted moves | engagement |
|---|---|---|---|---|
| pilot_0 | control | 59 | 59 | 1.00 |
| pilot_1 | control | 40 | 39 | 0.97 |
| pilot_2 | replay | 12 | 11 | 0.92 |
| pilot_3 | replay | 11 | 10 | 0.91 |
| pilot_4 | replay | 11 | 9 | 0.82 |

The control arm evaluates 40–59 specifications; the replay arm reaches its
submission in 11–12 moves. That gap is the surface, not the model, and
`AGENT_PROMPTS_REAL.md` §2 records it as a confound for search behaviour.

**Meta moves: every replay-arm run stopped on a trigger that fired**, 1 of 1 in
each — `last_gain_at_most` twice, `best_so_far_above` once. The replay tier has a
meta move to price on agent data, which was one of the failures this pilot was
built to catch.

**Declarations: `pick_prior` used in 3 of 3 replay-arm runs.**

**`pick` was used in 0 of 5 runs — and this is now a behavioural result rather
than a harness artifact.** In attempt 1 the prompt did not name the statistic
library; in attempt 2 the harness refused every `pick` at a full support. Both are
fixed. With a named library and a working guard, no run chose to `pick` at all.
So **"picks accepted versus contradicted" is 0–0 for a third time, and the
consistency check is unexercised on agent data.** 7.3's fidelity measurement is
the design that needs picks; if its agent cell wants them, the prompt has to ask
for a reasoned choice rather than merely permit one.

**Cost: $0.104 per run, $0.52 for the five** — 0.4× the $0.268 stored mean, so
rule 4's 3× re-statement does not fire, and every seat estimate resting on that
mean is conservative for this surface.

**Measurement 6 — the certifying null: computable, not priceable.** All three
replay-arm logs replayed without error, and all three verdicts are
**UNDECIDABLE** on the identity-replicate guard. Amendment 3 records the cause and
what it means for 6.5's conditional replay arm; the specimen block is in
`runs/agent_pilot/pilot_report_attempt3.txt`.

**What the three attempts cost in total: $1.64.** The two defects they found
would each have been discovered by 7.3's 160-run agent cell instead.

## What the identity-replicate guard caught, and the fix it forced

**Recorded 2026-09-24, after the third attempt and before any further real-data
run.** This is the pilot's substantive result, and it is a result about the
harness rather than about a certifier.

**What the guard is.** Before pricing anything, `quixote/replay.py` replays the
logged search on the **un-resampled** data and compares. If the replay does not
reproduce the search, there is no defensible way to price it, and the run is
flagged rather than certified.

**What it caught.** All three replay-arm logs, in every attempt: realized support
`((1,+1),(0,+1),(3,+1))` against replayed `((21,-1),(0,+1))`, with the realized
and replayed scores differing by **7.42**. On a simulated panel the two scoring
paths differ by float accumulation at ~1e-12 and a near-tie can flip an argmax.
Here the gap is **three orders of magnitude larger**, and the cause is
structural: `RealSandbox.evaluate` scores **net of costs**, costs are not linear
in the weights, and `base_feature_columns` is therefore a **diagnostic** basis
whose signed sums are not the statistic the search optimised. The guard was
right; the replay was pricing a different quantity.

**Why this was worth a pilot.** Nothing about it is visible on a simulated panel,
and nothing about it would have shown up as an error — the null computed, the
numbers looked like numbers, and only a guard comparing the replay against the
search itself refused them.

**The fix, and what it is not.** `environments/class_table.py` stores the
declared class as a `(T, N)` table of net streams computed once on the panel.
`evaluate` becomes a lookup; a replay resamples **rows** of the same table; a
full-class pass takes the chunked max over the same table. The statistic is then
the same **by construction**, and the guard passes with a score gap of exactly
zero rather than nearly. It is not a change to any null, any rule, or any
threshold: the same trigger-replay null is computed, on the numbers the search
actually saw.

**Cost of the fix, stated:** 3.87 GB for the ADR table and 2.81 GB for the ETF
table at depth 3 (82,240 members), both on disk as memmaps with every member pass
chunked, so resident memory is 149 MB and 17 MB at the registered chunk of 512.

**Milestone.** The guard passes bit-identically on all three pilot replay logs,
and a scripted policy through the tool adapter on a real panel reproduces its
direct `Session` run. Both are tests, not claims.

## Three causes, not one: what it took to make the guard pass

**Recorded 2026-09-24.** The section above named one cause. Fixing it exposed
two more, each of which had been hidden behind the one before it. All three were
found by the same guard, and none of them would have shown up as an error.

**Cause 1 — the basis.** `base_feature_columns` is a diagnostic basis on a
net-of-cost panel, so the replay summed columns and priced a statistic the search
never optimised. Fixed by `environments/class_table.py`: the class is tabulated
once and both sides read it.

**Cause 2 — the policy.** `LoggedPolicy` replayed **7.1's** policy, whose every
continuation is an `extend_best`. The pilot's agents ran
`init → extend → extend → refine → swap_worst → swap_worst → refine → stop`.
Replaying that as a forward selection is replaying a different search, and the
guard was right to refuse it even after the basis was identical. Fixed by
`LoggedPolicy._run_logged`, which replays the moves the log holds: **the declared
triggers still decide whether to continue, stop or restart on each replicate; the
logged move decides what the continuation is.** A log whose content moves are all
`extend_best` still takes 7.1's registered path unchanged, so milestone 3b is
untouched.

**Cause 3 — the estimator's guards, on this panel.**
`estimator/bootstrap.sharpe` censors `|Sharpe|` at `SHARPE_CAP = 100` annualised.
That guard is right for a simulated panel at Sharpe ≈ 1. The ADR panel's
registered annualisation is **5-minute bars — `periods_per_year = 19,152`** — and
the live search reaches **Sharpe 107**, so every good candidate came back as
exactly **100.0** and the replay priced a **censored** statistic. The table now
scores the sandbox's own uncensored statistic.

**This one is 7.4's to decide, not the pilot's.** A panel on which the registered
annualisation puts ordinary specifications above the estimator's cap has a
collision between two registered choices, and it is recorded here rather than
resolved: either the ADR annualisation is reported differently, or the cap is
raised for that panel, or the cap is accepted and every ADR figure is understood
as censored. **Nothing in this pilot depends on which**, because the pilot prices
nothing and claims nothing; 7.4 does, and it should settle this before it runs.

**Milestone, met:** with all three fixed, the identity-replicate guard passes on
the pilot's own move sequence with a score gap of **exactly 0.0**, and a scripted
policy through the tool adapter on a real panel reproduces its direct `Session`
run — both as tests (`tests/test_class_table.py`).

## Attempt 4: the replay arm re-run after the fix, and what is left

**2026-09-24.** Only the three replay-arm runs were re-run, on their registered
seeds and the same prompts, against the tabulated class
(`runs/agent_pilot/pilot_report_attempt4_priced.txt`). Rule 1 holds: no refusals
of any kind.

**One run certified, two did not, and the difference is not the harness.**

| run | declared stop trigger | verdict |
|---|---|---|
| pilot_3 | `last_gain > 0.0` | **CERTIFIED**, p = 0.0050 at B = 200 |
| pilot_2 | `best_so_far > 100` | UNDECIDABLE on the guard |
| pilot_4 | `best_so_far > 100` | UNDECIDABLE on the guard |

pilot_3's rule describes its search: it stops when a move gains nothing, which is
what it did, so replaying the rule reproduces the run and the guard passes with a
score gap of **exactly 0.0**.

pilot_2 and pilot_4 declared `best_so_far > 100`. Their best passed 100 at the
**second move** (106.98) and both kept searching to the tenth. Replayed as a
rule — which is what a declared trigger is — that predicate stops the search
eight moves early, so the replay is not the search and the guard refuses it. The
remaining score gap is 0.44, the difference between what the search reached and
what its own stated rule would have reached.

**This is the gate working, not failing.** The trigger was declared at the moment
of stopping rather than before searching, so it is a description offered
afterwards, not a commitment the search was run under. Nothing distinguishes
those two in a log unless the harness makes it so.

**The design decision this raises, registered as open rather than taken here:**

- **(a) declare triggers before searching**, as `pick_prior`, `short_list` and
  `declare_budget` already must be, with `SessionLog.refuse_if_late` refusing a
  late one. A stop would then have to name a trigger already on record. This
  makes every agent log replayable by construction and narrows what an agent may
  do.
- **(b) allow late declaration and price it as unreplayable** — the bracket
  (`prereg/bracketed-verdicts.md`), with the run dropping to the class tier.
  This keeps the agent free and makes the cost explicit in the verdict.

**7.2 or 7.3 chooses; this pilot does not**, and neither option is implied by
anything measured here. What the pilot establishes is that the choice exists and
that it is load-bearing: **two of three agent runs declared a stop rule their own
search does not satisfy.** With n = 3, that frequency is a signal to design
against, not a rate.

**Picks: still 0 of 3.** Amendment 3 of `AGENT_PROMPTS_REAL.md` registers the
reasoned-pick arm for 7.3's fidelity cell in response.

**Cost: $0.094 per run, $0.28 for the three. Four attempts in total: $1.92.**