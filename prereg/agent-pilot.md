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

None yet. Dated entries are appended here.
