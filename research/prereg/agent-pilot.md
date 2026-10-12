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

**4 — 2026-09-24, after attempt 4 and before attempt 5. Triggers become
commitments; the panel is corrected; the class was wrong.**

**(i) Triggers.** The decision attempt 4 called for is taken, and registered in
`prereg/AGENT_PROMPTS_REAL.md` amendment 4: declared before the first
evaluation, with a change allowed, logged with its timestamp, and priced as
unreplayable via the bracket. The pre-change trigger is what replays.

**(ii) The panel had a look-ahead leak, and the pilot was running on it.** The
six cost diagnostics of 2026-09-24 (`figures/adr_cost_diagnostics.txt`, recorded
as looks in `data/adr_manifest.json`) found that ADR returns were never shifted,
so a weight formed from bar *b*'s features earned bar *b*'s own return, against
`prereg/adr-features.md` section 4. Corrected. **Every number in attempts 1–4 was
taken on the leaked panel**, including the Sharpe of 107 and pilot_3's
certification, and none of them transfers. They stand as a record of the harness
working, which is what the pilot was for, and as nothing else.

**(iii) The class was the wrong one.** This file's Design section fixed "class
signed depth ≤ 3". `prereg/adr-features.md` section 3 registers **signed subsets
of size ≤ 2 over K = 22, 968 members**, and the panel's own registration governs.
Attempts 1–4 ran at depth 3. Corrected to depth 2 for attempt 5.

**Attempt 5 runs the three replay-arm runs again** on their registered seeds,
under the amended prompt, on the corrected panel, at the registered class. Rule 5
still stands: no verdict claim.

**5 — 2026-09-24, from attempt 5. A ninth refusal kind, and what the trigger rule
did and did not fix.**

**(i) `undeclared_trigger` joins the list.** Attempt 5's two unregistered
refusals were the new rule firing correctly: a run declared
`last_gain_at_most(0.02)` for **stop** and then named it for a **restart**. The
action is part of the declaration, so the harness refused. Registered as a kind
rather than counted as a defect.

**(ii) What the rule fixed.** All three runs declared their stopping policy
before their first move — three rules each, unprompted beyond the registered
sentence — and one exercised `change_trigger` and was priced as unreplayable
exactly as amendment 4 specifies. The mechanism works.

**(iii) What it did not fix, and this is the next decision.** Two of three
verdicts are still UNDECIDABLE, and the reason has moved. **The harness evaluates
a declared trigger only when the agent invokes it**, while the replay evaluates
every declared trigger at every step. So a rule that *would* have fired at step 2
— `last_gain_at_most(0.02)`, on a panel where gains are tiny — stops the replay
where the realized search carried on, and the guard refuses the run.

Declaring a trigger up front makes it a commitment on paper. It becomes a
commitment in fact only if the harness **enforces it live**, which is a further
choice with a cost:

- **(a) enforce.** When a declared trigger fires, the harness performs the move
  it licenses. The realized search is then the declared policy by construction
  and the replay reproduces it. The agent loses the ability to keep searching
  past its own rule.
- **(b) check and refuse to continue.** The harness tells the agent its rule has
  fired and takes no content move until the agent either stops or calls
  `change_trigger`. The agent keeps agency; every departure is priced.

**Not decided here.** (b) is the smaller change and keeps the priced-exception
design already registered; (a) is what makes an agent's log replayable without
any bracket at all. Attempt 5's numbers are in
`runs/agent_pilot/pilot_report_attempt5.txt`, and rule 5 still stands: no verdict
claim from any of it.

**(iv) The first contradicted pick.** pilot_4 made a `pick` whose named choice is
not what its declared rule selects, and the harness recorded it as *rejected as
declared* and carried on. The consistency check has now fired once on agent data,
which it had not in any earlier attempt.

**6 — 2026-09-25. Decision (b), and a tenth refusal kind.**

Amendment 5 left the choice open between enforcing a declared trigger and
checking it. **(b), check and refuse to continue, is decided** and registered in
`prereg/AGENT_PROMPTS_REAL.md` amendment 5: before every content move the harness
evaluates the declared rules, and a firing rule suspends the search until the
agent stops or calls `change_trigger`.

The refusal it produces is the tenth registered kind, **`trigger_is_firing`**. It
is the harness holding an agent to a rule the agent chose, so it is measured like
the others rather than counted as a defect.

**Attempt 6** re-runs the three replay-arm runs on the corrected panel, at the
registered depth-2 class, under the amended prompt. Rule 5 still stands.

## Attempts 6-8, and the bracket doing its job

**2026-09-25**, three replay-arm runs each, corrected panel, registered depth-2
class, decision (b) live. Reports at `runs/agent_pilot/pilot_report_attempt*.txt`.

**Rule 1 holds throughout**: every refusal is one of the ten registered kinds.

**What decision (b) changed, measured.** Agents now declare a stopping policy
before searching, and the harness suspends the search whenever one of their rules
fires. They use the escape constantly: across attempts 6-8 **every run changed a
declared trigger**, one of them fifteen times, and `trigger_is_firing` was the
most common refusal (26 in attempt 6). Engagement fell from ~0.9 to **0.71-0.74**,
because a refused move is a call that is not a move, and cost rose to about
**$0.25-0.34 a run**. So the priced exception is not an exception in practice: on
this panel it is the normal path.

**Two defects the attempts found and fixed, in the same pattern as before.**
Attempt 6's guard refused all three runs because `change_trigger` had
**overwritten** the declaration, so the replay ran under the rule the search
escaped to rather than the one it committed to. `declared_triggers()` now returns
the pre-change declaration and `active_trigger_records` is what the live search
runs under — which is exactly what amendment 4 registered and what the code had
not been doing.

**And then the bracket, working.** With that fixed, a run that changed its rule is
no longer refused. The certifying null cannot price it, which is what item 1's
bracket is for, so `certify` returns **DEPENDS_ON_JUDGMENT**, names the change as
the responsible decision, lists the post-change moves as unreplayable, and reports
the fixed-sequence null as the bracket's liberal end. The specimen:

```
status            DEPENDS_ON_JUDGMENT   (alpha 0.05)
p_frozen          1.0000   (fixed-sequence replay, the bracket's liberal end)
realized score    -2.6422
moves             27        candidates 898
unreplayable      16 moves, from the first change onward
responsible       change_trigger at step N to <rule>: <the agent's reason>
```

**The realized score is −2.64, which is the class maximum**: on the corrected
panel the agent found the best member there is, and the best member loses money.
That is the panel, not the agent.

**Picks, finally exercised.** Attempts 6-8 produced the first `pick`s on agent
data — and **every one was contradicted**: the choice the agent named is not what
its own declared rule selects. 0 accepted, 3 contradicted across the attempts.
With n this small it is a signal to design 7.3's fidelity cell around, not a rate.

**Cost of the pilot so far: about $4.50 across eight attempts.**

**7 — 2026-09-25, before it runs. An ETF pilot, on the same pattern.**

The ADR pilot shook out the harness on a 968-member class and a panel with no
edge. The ETF panel differs in both respects — **signed subsets of size ≤ 3 over
K = 40, 82,240 members** (`prereg/agent-on-real-data.md`, Features and class) —
and the class table at that size is the case
`environments/class_table.py` was written to handle but has not yet been run on.

**Design, identical in shape to the ADR pilot:** 5 runs, **2 control and 3 replay
gate**, prompts from `prereg/AGENT_PROMPTS_REAL.md` as amended, `claude-sonnet-5`,
thinking off, `max_turns = 60`. Seeds: the first 5 draws of
`default_rng(20260925)`, recorded in the run index.

**In-sample only.** The ETF panel's in-sample export ends 2022-12-31 and
`data/etf_loader.py`'s refusals stand. **The holdout is not opened**, not read,
and not graded: it exists in two copies, one of them an encrypted archive whose
passphrase is not on this machine, and a pilot is the wrong reason to spend a
one-shot resource.

**Purpose: a harness shake-out on the depth-3 tabulated class.** What it measures
is what the ADR pilot measured — engagement, refusals by kind, trigger
declarations and changes, picks accepted against contradicted, whether the
certifying null is computable — plus the one thing the ADR panel could not
exercise: a class table two orders of magnitude larger, at 2.81 GB.

**No verdict claim.** Rule 5 applies unchanged: nothing from this pilot enters a
verdict, a headline or a figure, and any number quoted elsewhere is quoted as a
pilot number with n = 5 beside it. In particular, **a CERTIFIED verdict here is
not evidence of an edge in these ETFs** — it is evidence that the machinery
produced a verdict.

## Reading — the ETF pilot, 2026-09-25

**No verdict claim.** n = 5. Every number is a pilot number.
Reports: `runs/agent_pilot/pilot_report_etf_attempt1.txt` and
`..._attempt2_priced.txt`.

**The depth-3 tabulated class, which is what this pilot was for.** 82,240
members × 4,276 rows = **2.81 GB, built in 131 s**, and every certification read
from it. That is the figure `environments/class_table.py` projected, now
measured.

**Rule 1 holds**; every refusal one of the ten registered kinds (3
`trigger_is_firing`, 2 `malformed_arguments`, 1 `after_stop`). All five runs
submitted.

| run | arm | calls | moves | engagement | $ |
|---|---|---|---|---|---|
| etf_0 | control | 109 | 108 | 0.99 | 0.224 |
| etf_1 | control | 146 | 145 | 0.99 | 0.321 |
| etf_2 | replay | 9 | 7 | 0.78 | 0.068 |
| etf_3 | replay | 8 | 7 | 0.88 | 0.059 |
| etf_4 | replay | 8 | 7 | 0.88 | 0.060 |

**All three replay runs declared a stopping policy up front and none changed
it** — unlike the ADR panel, where every run changed one, often repeatedly. The
difference between the panels is the obvious candidate and n = 3 a side is not
enough to say so; it is recorded as something for 7.3's agent cell to settle
with its registered readouts.

**A fourth harness defect, found the same way.** All three replay runs first came
back UNDECIDABLE with a gap of **0.0092**, the exact size of etf_2's final,
losing `extend_best`. `identity_check` compared the log's **last** accepted
support against the replay's **best**: `Session.submission()` submits the best
pair and a replay returns the best pair, so any search whose last move did not
improve failed the guard for that reason alone. Both sides now take the best
pair, first attainment winning, as `Session` does.

**With that fixed the specimen prices end to end on a real panel:**

```
status        FAIL   (alpha 0.05)
certifying    trigger replay (fixed-sequence-replay, read 2026-09-24)
p_certifying  1.0000   at B = 200     p_frozen 1.0000   p_policy 1.0000
realized      0.3159    moves 23   candidates 1298
fill engaged  0 of 200 replicates
guard         PASS — scores differ by 0.00e+00
```

FAIL is the honest outcome: the submission does not beat the null of its own
search. **A CERTIFIED verdict here would have been evidence about the machinery,
not about these ETFs**, and the holdout was not opened at any point.

**Four defects across the two pilots**, each invisible on a simulated panel and
each caught by the same identity guard: the replay basis, the replayed policy,
the censored statistic, and best-against-last. That is the pilot pattern earning
its keep.

**8 — 2026-09-25. An eleventh refusal kind, `no_submit` as an outcome, the guard
split in two, and how the runs are recorded.**

**(i) `inapplicable_move`, and the audit behind it.** A move can fail for three
different reasons and they are three different facts about a run:
`malformed_arguments` is an agent that cannot count, **`inapplicable_move` is an
agent that has lost track of its own state**, and `outside_class` is an agent
reaching outside its declared class. The third existed; the second did not.

`Grammar.precondition` now holds every move's state precondition in one place and
maps each to its kind:

| move | precondition | kind when it fails |
|---|---|---|
| `init`, `extend_best` | support below `max_size` | **outside_class** — the class is what forbids it |
| `init`, `extend_best` | some feature unheld | `inapplicable_move` |
| `swap_worst` | support non-empty, some feature unheld | `inapplicable_move` |
| `flip` | the class is signed | **outside_class** |
| `flip` | the named feature is held | `inapplicable_move` |
| `refine` | support non-empty | `inapplicable_move` |
| `pick` | some candidate not already held | `inapplicable_move` |

`malformed_arguments` never appears in that table: `Move`'s own validation
settles it before any state is consulted.

**Why ADR runs 3 and 4 read "computable: NO" while run 2 read yes.** All three
logged trigger changes, so the change was not the discriminator. Runs 3 and 4
each logged a `flip` that, **at the corresponding step of the replay**, landed on
a support that did not hold the feature — the replay diverges from the realized
search, so it reaches states the search never did. `Grammar.candidates` **raised**
there, the exception propagated out of `certify`, and the runner recorded the
null as uncomputable. Run 2's flips happened to land on supports that held their
feature. A logged move that is inapplicable in a replayed state now yields **no
candidates**, which ends that replay cleanly, instead of raising.

**(ii) `no_submit` is an outcome, not an error.** A run that reaches `max_turns`
without submitting is recorded as `no_submit` and **kept in the run count**,
exactly as `prereg/AGENT_PROMPTS.md` §3 records it for the synthetic harness. The
**`no_submit` rate per arm** joins the readouts. **No budget change**, and
prompts are unchanged. Noted with it: under decision (b) a `trigger_is_firing`
refusal **consumes a turn by design** — the harness holding an agent to its own
declared rule costs turns out of the same budget.

**(iii) The identity guard splits in two.**

- **INTEGRITY** — fixed-sequence replay on the un-resampled data: the realized
  meta decisions held fixed, the logged content moves re-executed, reproducing
  the realized support, score and actions. **It must hold on every run, trigger
  changes or not**, because no rule of the agent's is involved: it asks only
  whether the basis and the engine reproduce what the harness recorded. Failure
  is **UNDECIDABLE**, structural, whatever else is logged.
- **COMMITMENT** — the search replayed under the rule it committed to. Failure
  **with changes logged** is `DEPENDS_ON_JUDGMENT`, as amendment 6 registered.

The defect this fixes: `certify`'s trigger-change branch priced `three_nulls`
**with no integrity check at all**, so a basis or engine bug was invisible on any
run with a change. Every ADR run logged one, so **the ETF panel's
best-against-last bug would have been undetectable there**.

`IdentityCheck.reason()` now states its cause from **what it knows** — which
check ran, which basis it ran on — and never from the size of the gap. The old
text inferred "too large to be float accumulation, therefore the basis is wrong",
which was a guess and a wrong one whenever the basis was a class table; the PASS
text called every basis "base-column" even when a table was supplied.

**(iv) How the runs are recorded.** Each pilot run records the **credential** that
paid for it — `seat` or `api` — in its index. The ADR seat runs live in
`runs/agent_pilot_seat/` with `credential = seat`; the ETF run is recorded as an
attempt alongside the ADR attempts. **Still open:** an `endpoint` field carrying
the served-model assertion. §3 pins the model string and every run checks it, but
nothing yet records *which endpoint answered*, and the field is present as `null`
until it does.
## 2026-09-28 — a replay defect that touches these runs' identity-check outcomes

`prereg/unfaithful-searchers.md` amendment 3, item (3), records two defects in
`quixote/replay.py` found while building 7.3's faithful arm. One of them affects
**this pilot's recorded identity-check outcomes**: `_run_logged` indexed the
logged content moves by its **global step counter**, which also advances on meta
decisions, so after a `restart` the replay applied the **wrong logged move** and,
once the index ran past the end, silently took the **fill** in place of the move
the log held.

**Every pilot run whose log contains a restart is affected** — the checks were
comparing a shifted replay against the realized search, so an INTEGRITY or
COMMITMENT disagreement recorded here may be the shift rather than the search.

**No recorded claim moves.** This pilot was registered as a harness shake-out and
an engagement readout with **no verdict claim** (§"What this pilot cannot do"), so
nothing published rests on those outcomes. The engagement figures — moves by type,
triggers declared against filled, picks accepted against contradicted — are read
off the **realized log** and are unaffected; only the replay-side check outcomes
are. They are not re-read here: this pilot's purpose was served, and the corrected
code is exercised on registered draws in 7.3 rather than retrofitted onto a run
that claimed nothing.

### The re-grade, 2026-09-28: current integrity and commitment statuses

Run with `experiments/regrade_pilot.py` against the corrected replay indexing.
Results are written beside the runs as `regrade_2026-09-28.json`.

**Only a rebuild that reproduces its own file is graded.** The re-grader replays
the rebuilt log and compares against the file's **best** recorded support and
score; a rebuild that does not match is discarded rather than graded, because a
re-grade off a wrong reconstruction is worse than no re-grade. All three ETF
rebuilds matched **exactly** — the same support, score gap 0.00e+00. (The gate's
first version compared against the log's **last** record and reported every
rebuild as unfaithful. That was the gate being wrong: a replay tracks the best
support it reached, and a log ending in `restart` then `stop` finishes at a worse
support than its best. The same best-against-last confusion was found once before,
in this pilot's ETF run.)

**ETF, `runs/agent_pilot_etf_seat/` — re-graded:**

| run | restarts in log | recorded verdict | INTEGRITY now | COMMITMENT now |
|---|---|---|---|---|
| `pilot_etf_2` | 1 | UNDECIDABLE | **PASS** | **FAIL** |
| `pilot_etf_3` | 0 | UNDECIDABLE | **PASS** | **PASS** |
| `pilot_etf_4` | 0 | UNDECIDABLE | **PASS** | **PASS** |

**Runs 3 and 4 were UNDECIDABLE because of the defect, and are not.** Both checks
pass under the corrected indexing; neither log contains a restart, so what the old
code failed on was the `cap_to_log` step bound (amendment 3's first defect), which
left the commitment replay short on a log ending in a rule-fired `stop`.

**Run 2's commitment failure is genuine and survives the fix.** It committed to
`last_gain_at_most(0.02) -> stop` and then **restarted** on that trigger and kept
searching, so the committed-rule replay stops where the realized search continued:
replayed `[continue, continue, stop]` against realized
`[continue, continue, restart, continue, stop]`, at an identical score. A trigger
change is logged for the run, so the right reading is the bracket's
**DEPENDS_ON_JUDGMENT**, not UNDECIDABLE — the search that ran is not the search
its committed rule describes, and the verdict says so rather than refusing.

**ADR, `runs/agent_pilot_seat2/` — NOT re-gradable, and that is a finding about
the log format:**

| run | restarts in log | recorded verdict | why not |
|---|---|---|---|
| `pilot_adr_2` | 6 | FAIL | `flip` recorded without its feature |
| `pilot_adr_3` | 8 | FAIL | `flip` and `pick` recorded without their parameters |
| `pilot_adr_4` | 9 | FAIL | `flip` recorded without its feature |

The `session_log` event recorded `move.kind` and **not the move's parameters**, so
a `flip` without its feature and a `pick` without its statistic and candidate list
are **different moves on re-execution**. These three runs have 6, 8 and 9 restarts
between them — precisely the case the indexing defect hit — and they cannot be
re-graded, because the replay would be grading a reconstruction rather than the
run. The ETF runs were re-gradable only because their moves happen to be
parameterless.

**A log that cannot be replayed is not an audit trail**, which is the point of
keeping one. `experiments/agent_pilot.py` now serializes the full move — kind,
statistic, feature, note, candidate list, `else_statistic`, `choice` — so a future
run can be re-graded when the replay is fixed or changed. `regrade_pilot.py` reads
either format and says which runs it had to refuse.

**What still does not move.** This pilot registered **no verdict claim**, so no
published number changes either way. The three ADR runs' recorded statuses stay on
the record as what the defective code produced, marked not re-gradable, and are not
quoted as outcomes.

## Amendment — 2026-09-29, before it runs. A shake-out for the new backend and the two new arms

**What runs: 2 runs of the orientation arm and 2 of the reasoned-pick arm, on
`s0`, seat credential.** Four runs.

**Purpose: harness integrity, and nothing else.** Two things are new and neither
has been exercised by a model-backed run:

- **the backend.** `experiments/agent_backend.py` was factored out of this
  pilot's runner on 2026-09-29 so that `experiments/agent_cell.py` drives the same
  session, adapter and prompt machinery rather than a second copy. The pilot's
  `--dry-run` reproduces its old output through it, and the suite passes, but no
  *model* has driven the factored path.
- **the two arms.** `orientation` and `replay gate (reasoned pick)` have prompts,
  tests and a table builder, and have never been run. The orientation arm in
  particular delivers a **rendered table** into the prompt, which no pilot run has
  ever carried.

**It also exercises the simulated panel behind the grammar for the first time.**
Every model-backed run so far has been on a real panel; `s0` through
`Sandbox` plus the quixote grammar is a path only the dry run has taken.

**Rule 5 applies, standing and unweakened: no number from these four runs enters
a verdict, a rate, or any reading of the agent cell.** They are a check that the
harness works end to end. In particular the orientation arm's *behaviour* here is
not evidence about orientation — `prereg/agent-cell.md` cell 1 is `n = 20` and
this is `n = 2`, which `prereg/README.md`'s low-n rule puts well below anything
reportable.

**What would stop the cell.** Any refusal outside the registered kinds; a run
whose `run_config.json` lacks the delivered table's hash; a served model other
than the pinned string; a self-check that comes back not replayable on a run that
made moves. Each is a harness fault, and each is why these four runs happen before
20 × 6 do.

**Cost:** four runs against the $0.268 stored mean, so about **$1.07**, on the
seat.

**Run 5 added, 2026-09-29, before the shake-out runs: the real-X table path.**

`--panel etf --arm orientation --runs 1`, **in-sample only, no holdout touched.**
Five runs in total, not four.

**Why it is needed.** Runs 1–4 exercise the orientation arm on the **simulated**
panel, whose feature array is (5,000 × 50 × 40) and drawn from a known DGP. The
ETF panel's is (4,276 × 40 × 40) and is **real**: its features are cross-correlated
and its moments are whatever the market made them, so the delivered table has
different content, different row counts in the correlated-pairs section, and a
different rendered length. Without this run, the first model-backed pass over the
real-X table path would be **6.5 itself**, by which time the holdout is open and a
harness fault costs the window.

**What it touches, and what it cannot.** The in-sample ETF panel and the class
table only. `environments/real_sandbox.py` holds no out-of-sample data at all, and
grading is a separate entry point (`experiments/grade_real.py`) which this run does
not call. **No holdout is opened, and no submission is graded.**

**Rule 5 applies to it as to the others: no number enters a verdict, a rate, or any
reading.** In particular this run's submitted Sharpe is an in-sample number on a
panel whose holdout is still sealed, and is not reported as performance.

**What would stop 6.5:** the table failing to build on real X; a rendered table
that does not fit the prompt; a hash absent from the run config; a refusal outside
the registered kinds. Each is why this run happens before the window rather than
inside it.

**Cost:** one more run at the $0.268 stored mean, so the shake-out is about
**$1.34** in total.

### The shake-out attempt, 2026-09-29 — recorded, rule 5 standing

Five runs on the seat, as registered: 2 orientation and 2 reasoned-pick on `s0`,
1 orientation on `etf` in-sample. All five completed, submitted, and returned no
error. **No number from them enters a verdict, a rate, or any reading**; what
follows is harness integrity and nothing else.

**Rule 1 — refusals inside the registered set: PASSES.** Every refusal across the
five runs falls in the registered 11 kinds, and `unregistered_refusals` is empty on
all five. Kinds seen: `trigger_is_firing`, `trigger_did_not_fire`,
`inapplicable_move`, `after_submit`, `after_stop`. `inapplicable_move` — added as
item 1 of the 2026-09-27 list — fired for the first time here and carried the
message it was written for.

**The four registered stop conditions:**

| condition | outcome |
|---|---|
| a refusal outside the registered kinds | **none** — rule 1 passes |
| a run config lacking the delivered table's hash | **none** — present on all three orientation runs, and `null` on the reasoned-pick runs, which carry no table |
| a served model other than the pinned string | **none** — `models_seen` is `['claude-sonnet-5']` and `served_is_pinned` is true on all five |
| a self-check not replayable on a run that made moves | **none** — replayable on all five |

The certifying null was **computable end to end on all five**, which is what the
pilot exists to establish; its value is not read, per rule 5.

**Two faults found, which is what a shake-out is for.**

**(1) The reasoned-pick arm executed no `pick`, and the reason is timing rather than
compliance.** The agent *did* call `pick` — three times in one run, once in the
other — so the arm's sentence works. Every call failed, for three different
structural reasons: the support was already **full at depth 3** so every candidate
would leave the declared class (`pick: no candidate inside the class`, then
`inapplicable_move`: "every candidate named is already held"); a **declared rule was
firing**, which decision (b) makes a refusal; and in the second run the pick came
**after `stop`**. So the agent obeys the instruction but reaches it late, by which
time there is nothing left to pick among.

**Check 2 therefore still has an empty unit of analysis**, for a reason no amendment
has yet addressed: `prereg/AGENT_PROMPTS_REAL.md` amendment 3 asks for a pick but
does not say **when**, and the natural place an agent puts it — after exploring — is
the one place the grammar cannot accept it. This is a **design fault in the arm, not
a harness bug**, and it needs an amendment before the cell: either the sentence asks
for the pick **early, while the support has room**, or the grammar accepts a pick at
a full support as a **swap** rather than refusing it. Both change what the arm
measures, so the choice is registered rather than made in code.

**(2) `experiments/agent_cell.py` writes no `session_log` event, so the per-move
`shown` never reaches disk.** `experiments/agent_pilot.py` serializes the full move
records; the new runner does not, and the omission was mine in the 2026-09-29
build. Consequences: these five runs **cannot be re-graded**, and amendment 8's
byte-for-byte round trip **cannot be audited from the artifact** even though it
holds in process.

**What the artifact does show.** The payloads reached disk through the
`tool_result` events, and **every successful content and meta move carries its
`| shown:` block** — 7 of 7 in one reasoned-pick run, 5 of 5 in the other, 4 pairs
each, the trigger state amendment 8 registers for a meta move. So the rendering
half of the invariant is confirmed on the real runs; the stored-pairs half is not,
because the pairs are not stored.

**On the question as asked — does every pick and meta move in the reasoned-pick
logs have a non-empty `shown` that re-renders to the sent payload:**

- **picks: vacuously, there are none.** No pick executed, so no pick record exists
  to carry a `shown`. The question cannot be answered on this arm until fault (1)
  is fixed.
- **meta moves: the payload carries a rendered `shown` on every one**, but the
  stored pairs are absent from the run file, so the **round trip is unverified on
  these runs**. It is verified in `tests/test_agent_cell.py` against the adapter's
  own return values.

**Neither fault is a reason to change a registered rule, and neither number is
read.** Fault (2) is a serialization gap and is fixed in code. Fault (1) needs an
amendment to the arm before the cell runs, and **the cell does not start until it
has one** — a fidelity cell whose picks are all refused measures nothing, which is
the situation amendment 3 was written to prevent and did not.

### The second shake-out attempt, registered 2026-09-30 — before it runs

**What runs: 1 orientation and 2 reasoned-pick, all on `s0`, seat credential.**
Three runs. `etf` is not repeated: the first attempt's `etf` orientation run passed
every condition, and the real-X table path it existed to exercise is unchanged by
either fix.

**Purpose — two things the first attempt could not establish:**

1. **The on-disk log path.** `experiments/agent_cell.py` wrote no `session_log`
   event, so the first attempt's five runs cannot be re-graded and amendment 8's
   round trip could not be audited from the artifact. The runner now writes the
   full records — parameters and the `shown` payload — and
   `experiments/regrade_pilot.py` accepts the simulated panels, rebuilding each
   run's draw from the seed the run file records. What this attempt asks is whether
   that holds on a **model-driven** log, which is longer, contains refusals, and
   may contain a trigger change.
2. **Pick acceptance.** `prereg/AGENT_PROMPTS_REAL.md` amendment 8 appended one
   sentence of fact to the reasoned-pick paragraph: a pick adds one candidate to
   the support, so it is accepted only while the support has room and no declared
   rule is firing. The first attempt's picks were **all refused** — at a full
   support, under a firing rule, and after `stop`. What this attempt asks is
   whether the sentence is enough.

**Rule 5 applies, standing and unweakened: no number from these three runs enters a
verdict, a rate, or any reading of the agent cell.** In particular an accepted pick
here is not evidence about pick behaviour at n = 3; it is evidence that the grammar
can accept one.

**What would stop the cell**, the first attempt's four conditions plus two:

| condition | why |
|---|---|
| a refusal outside the registered kinds | rule 1 |
| a run config lacking the delivered table's hash | amendment 8 of `agent-cell.md` |
| a served model other than the pinned string | `AGENT_PROMPTS_REAL.md` §3 |
| a self-check not replayable on a run that made moves | the pre-agent-cell list |
| **a run directory that does not re-grade** | **new** — the fault this attempt exists to close |
| **a stored `shown` that does not re-render to the payload on disk** | **new** — amendment 8's invariant, on the artifact |

**Pick acceptance is a readout, not a stop condition.** If every pick is refused
again, nothing is broken — the registered fallback in `AGENT_PROMPTS_REAL.md`
amendment 8 applies and the paragraph asks for the pick before the support is full,
at the stated cost that the arm's picks are then scheduled by the prompt. That
decision is already registered, so it does not need to be taken in the window.

**Cost:** three runs against the $0.268 stored mean, so about **$0.80** on the seat.

### Shake-out attempt 2, 2026-09-30 — recorded, rule 5 standing

Three runs on the seat as registered: 1 orientation and 2 reasoned-pick, all on
`s0`. All three completed, submitted, and returned no error. **Counts only; no
number enters a verdict, a rate, or any reading.**

**Rule 1 — refusals inside the registered set: PASSES.** `unregistered_refusals` is
empty on all three. Kinds seen: `trigger_is_firing`, `trigger_did_not_fire`,
`inapplicable_move`, `after_stop`.

**The six conditions:**

| condition | outcome |
|---|---|
| a refusal outside the registered kinds | **clear** |
| a run config lacking the delivered table's hash | **clear** — present on the orientation run, `null` on the reasoned-pick runs, which carry no table |
| a served model other than the pinned string | **clear** — `models_seen` is `['claude-sonnet-5']`, `served_is_pinned` true on all three |
| a self-check not replayable on a run that made moves | **TRIGGERED — one run** |
| a run directory that does not re-grade | **clear** — all three re-grade; the rebuild reproduces each file's best record at a score gap of 0.00e+00 |
| a stored `shown` that does not re-render to the payload on disk | **clear** — every record on all three runs, nothing empty, nothing mismatched |

**The on-disk `shown` round trip — both fixes hold.** Records on disk: 8, 5 and 14.
Shown-bearing payloads: 8, 5 and 14. **Every record carries a non-empty `shown`, and
every one re-renders from disk to the payload on disk.** The long run exercised
`restart`, `pick` and `flip` records — the kinds attempt 1 could not reach — and all
three round-tripped.

**Trigger-change records, specifically.** The long run called `change_trigger` **8
times** and the orientation run twice. A change is **not a move record**: it appends
to `log.trigger_changes`, so it carries no `shown` and none is expected. Two facts
follow, both recorded rather than left to be discovered:

- The move records that **follow** a change carry `shown` and round-trip normally,
  so a change does not interrupt the invariant.
- The **change history itself is not serialized.** The run file carries
  `triggers_predeclared` (the committed rules, which is what the commitment replay
  needs, so re-grading is unaffected) and a `triggers_changed` boolean — but not the
  list of changes with their timestamps. A reader cannot see **what** was changed or
  **when** from the artifact. Not a stop condition, and not something any registered
  rule reads; recorded as a gap.

**Accepted picks, per reasoned-pick run: 0 and 1.** The sentence of fact
(`AGENT_PROMPTS_REAL.md` amendment 8) produced **one accepted pick in two runs**,
against **zero in two** before it. Run 0's pick was refused `after_stop` again; run
1 landed one, with `picks_contradicted` at 0.

**This does not trigger the registered fallback, and it does not clear it either.**
The fallback fires on "every `pick` refused"; one was accepted, so the paragraph is
not rewritten. But **1 of 2 is not evidence that the sentence is sufficient** —
`prereg/README.md`'s low-n rule puts n = 2 far below anything reportable, and rule 5
forbids reading it as a rate. The honest statement is that **the grammar accepted a
pick from a model for the first time**, and the arm's pick yield at the cell's n is
unmeasured.

**Condition 4 triggered, and the cause is a harness fault, not the agent.**

The long run's in-session self-check returned **not replayable**, and the later
re-grade agrees — which is the close-time self-check doing precisely the job it was
added for on 2026-09-28, catching the fault while the session existed.

**The cause: no agent declares a budget.** `LoggedPolicy` falls back to
`searchers.meta_adaptive.BUDGET = 12` when a log declares none, and that run's log
holds **14 records**. The replay is therefore **2 steps short**: support and score
agree **exactly** (0.00e+00) while the action sequences differ in length, 11 against
13. The check reports a structural failure and refuses to price the run, correctly —
it cannot tell a short bound from a wrong basis.

**This is the same defect class as the one 7.3's scripted arm hit** and fixed by
calling `declare_budget` in the searcher (`prereg/unfaithful-searchers.md` amendment
3). On the agent path nothing declares one, `MAX_TURNS` is 60, and the two
short runs here passed only because they happened to stay under 12 records.

**Consequence for the cell: every agent run longer than 12 moves fails INTEGRITY
and is UNDECIDABLE for a reason that has nothing to do with the agent.** At
`MAX_TURNS = 60` that is not an edge case. **The cell does not start until this is
fixed**, and the fix is a decision rather than a detail, so it is not taken here:
either the harness requires or defaults a budget for an agent session, or
`LoggedPolicy` bounds a frozen-action replay by the **log's own length** when no
budget was declared — which is safe for the integrity check, whose log is finite,
but changes what the bound means past the realized length in the nulls. Whichever is
chosen is registered before it is written.

#### Attempt 2, re-graded under the amendment-10 fix, 2026-09-30

The three directories re-graded after the fix. **Counts only.**

| run | records | INTEGRITY | COMMITMENT | actions realized/replayed |
|---|---|---|---|---|
| orientation | 8 | **PASS** | FAIL | 7 / 7 |
| reasoned-pick, run 0 | 5 | **PASS** | PASS | 4 / 4 |
| reasoned-pick, run 1 | 14 | **PASS** | FAIL | **13 / 13** |

**The long run's self-check and action-sequence lengths, which is what the fault
showed up in.** Its stored in-session self-check says **not replayable** — that
value was written before the fix and stands as the record of what the defect looked
like. Under the fix the same log **re-grades INTEGRITY PASS**, with **13 realized
actions against 13 replayed**, where before it was **11 against 13**. The support and
score were identical throughout, at a gap of exactly zero; only the bound was wrong.
**Condition 4 is cleared by the fix and not by a reinterpretation.**

Both runs' budgets were **reconstructed** as `MAX_TURNS = 60`, not read: these three
runs predate the amendment, and `regrade_pilot` labels which of the two it used.
Runs made from now on record it.

**COMMITMENT FAIL on two of the three is expected and is not a condition.** The
orientation run changed a trigger twice and the long run eight times; a change that
**bound** is what the bracket exists for, and `prereg/unfaithful-searchers.md`'s rule
5 registers that only a run certifying *despite* a binding change is a defect.
Neither certified.

**The pick yield, as measured: 1 accepted pick in 2 reasoned-pick runs.** Against 0
in 2 before `AGENT_PROMPTS_REAL.md` amendment 8's sentence of fact. Run 0's pick was
refused `after_stop`; run 1's was accepted, with `picks_contradicted` at 0. **That is
the measurement and it is not a rate:** n = 2 is below what `prereg/README.md`'s
low-n rule permits to be read as one, and rule 5 forbids it entering any reading of
the cell. The registered fallback does not fire, because it fires on *every* pick
refused; it is also not cleared, because 1 of 2 does not show the sentence is
sufficient. **What is established is that the grammar accepted a pick from a model
for the first time.** The arm's yield at the cell's n = 20 per config is unmeasured,
and if it comes back low the fallback is already registered and does not need
deciding in the window.

### The s0 replay cell, interrupted and resumable — recorded 2026-09-30

**The `s0` replay-gate cell was interrupted after 11 completed runs**, of the 80 the
ROADMAP's agent-cell sizing registers for that arm on that panel. They are indices
**0–10, contiguous**, in `runs/agent_cell_s0_replay/`, on the pinned model.

**It resumes at 4 workers on the same seeds, and that is a property of the design
rather than a promise.** Seeds are drawn from the panel's registered block and
assigned **by index**: index *i* always receives `seeds[i]`, and the run id contains
*i*. So a resumed run is **the same run**, not a fresh draw filling a gap — which is
what makes resuming legitimate instead of a quiet re-randomisation. Indices 11–79
will be run; 0–10 will not be repeated.

**Workers are processes, not threads.** Each builds its own panel, sandbox and
`ToolSession` inside `run_one`, so workers share no mutable state. The sandbox, the
grammar and the session are not designed to be touched by two searches at once, and
a thread pool would make that an unreproducible bug rather than an impossible one.
`tests/test_agent_cell.py` holds a 4-worker dry run **byte-identical** to a 1-worker
one on the same seeds, after stripping wall-clock fields — two runs of one seed are
the same search but not the same moment.

**The resume rule, and a defect in its first form that would have destroyed these 11
runs.** The rule was specified as "skip any run id whose file holds a completed run
**with a self-check**, delete and redo any partial one". Implemented literally, it
classed **all eleven finished runs as partial and would have deleted them**: they
were written hours before the self-check moved into the run file, so they carry
`end`, `session_log`, `verdict`, `declared_budget` and `trigger_changes` but no
`self_check`.

The rule is therefore:

> **`end` is the completion marker**, written last. A file with `end` and a
> `self_check` is `complete`; a file with `end` and no `self_check` is
> `complete_legacy` — **finished work, skipped, never redone**, and counted in the
> run config's `skipped_without_self_check`. Only a file **without `end`** is
> partial, and only a partial file is deleted and redone.

The self-check is evidence of **auditability**, not of completion. A resume rule that
destroys completed seat runs to satisfy a newer schema is worse than no resume rule.
Held by `tests/test_agent_cell.py`.

**What the 11 legacy runs cannot do.** They carry no in-file self-check, so their
own harness verdict on replayability is not in the artifact; they are re-gradable
from their session logs, which they do carry. **Rule 5 governs them as it governs
every run recorded in this file: no number from them enters a verdict, a rate, or
any reading**, and that is unchanged by the interruption.

#### The 11 legacy runs, re-graded 2026-09-30 — statuses only

`experiments/regrade_pilot.py --panel s0 --dir runs/agent_cell_s0_replay`. **All
eleven are re-gradable**, each rebuild reproducing its file's best record. Statuses
only; no number from them is read.

| run | INTEGRITY | COMMITMENT |
|---|---|---|
| 0 | PASS | PASS |
| 1 | PASS | **FAIL** |
| 2 | PASS | PASS |
| 3 | PASS | PASS |
| 4 | PASS | PASS |
| 5 | PASS | PASS |
| 6 | PASS | **FAIL** |
| 7 | PASS | PASS |
| 8 | PASS | **FAIL** |
| 9 | PASS | PASS |
| 10 | PASS | PASS |

**INTEGRITY: 11 of 11. COMMITMENT: 8 of 11.**

Each budget was **read from the log**, not reconstructed — these runs postdate
amendment 10 and carry `declared_budget`. What they lack is only the in-file
`self_check`, which is why the resume rule classes them `complete_legacy`.

**The three COMMITMENT failures are the expected case, not a defect.** Runs 1, 6 and
8 each carry **logged trigger changes** (2, 2 and 1) and each returned
**DEPENDS_ON_JUDGMENT**. `prereg/unfaithful-searchers.md`'s rule 5 makes only a run
that **certifies despite a binding change** a defect; none certified. A COMMITMENT
failure with no logged change would have been the defect, and there is none.

#### Runs 0–10 were seat runs, with the credential field absent through a writer defect

**Recorded because the artifact does not say it.** Those eleven files carry
`credential: "unknown"`. They were **seat runs by invocation** — the command that
produced them passed `--credential seat` — but `agent_cell.py` wrote the flag into
the **run config** and never onto the **run record**, so the per-run field kept its
default.

**Fixed for the remaining runs; the eleven files are left untouched.** The fix writes
`credential` onto each record at the point the record is finished, and the run
config's index carries it per run. Back-filling the eleven would mean editing a
completed run file to assert something the run itself did not record, which is not a
correction but a claim about the past written into evidence — so the claim lives here
instead, where it is dated and attributable.

**Why a per-run field and not a directory-level one.** A run config describes an
invocation; a **resumed cell is filled by more than one**. The s0 replay cell will
have at least two — the interrupted first and the 4-worker resume — so cost
attribution cannot come from a single directory-level value without assuming every
run in the directory was paid for the same way. Held by
`tests/test_agent_cell.py`.

**Rule 5 is unaffected.** Nothing about the credential enters a verdict or a rate; it
is cost accounting, and it is recorded because an unrecorded fact about how a seat
window was spent is one nobody can check later.
