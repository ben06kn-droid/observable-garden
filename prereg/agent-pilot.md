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