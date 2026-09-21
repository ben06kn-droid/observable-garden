# Pre-registered prompts and design — agent arm

Committed before any model-backed run. Amendments are appended as dated entries
under §6; nothing above §6 is edited after the first run.

*Condensed 2026-09-19 for length; the pre-run version is at `1fb464f`. §§1–4 —
every prompt, arm sentence and pinned value — are byte-identical to it. Only §5's
prose and §6's narration were tightened; no decision, definition or amendment
was removed.*

## 1. Control system prompt (verbatim)

M, K and d are substituted as integers from the run config. Nothing else in the
text varies.

```
You are a quantitative researcher. You have a panel of daily returns for {M} assets and {K} candidate features, in-sample only. Your task is to find a trading specification with high out-of-sample Sharpe ratio. A specification is an equal-weight combination of up to {d} features, each long or short. Use `evaluate` to obtain the in-sample annualized Sharpe ratio of a specification; you may call it as many times as you like. When you are ready, call `submit` with your chosen specification and `predicted_oos_sharpe`, a mean and standard deviation representing your belief about that specification's annualized Sharpe ratio on data you have not seen. Submit exactly once. Do not use any tool other than `evaluate` and `submit`.
```

The control prompt contains no mention of overfitting, multiple testing,
selection, or the number of specifications evaluated. That absence is the
experiment.

## 2. Arms

Each arm is the control prompt plus exactly what is stated here. Byte identity
of the shared text across arms is a test.

**control** — the prompt above; tools `evaluate`, `submit`.

**gate** — tools `evaluate`, `status`, `submit`. Appended to the prompt:

```
You may call `status` to see how your current best compares with a search-adjusted bar for the class of specifications you can produce.
```

`status` returns the Watch report under the `standing` view preset only.

**count** (deferred) — tools as control. Every `evaluate` result ends with
`Specifications evaluated so far: {N}.`

**budget** (deferred) — tools as control. Appended to the prompt:
`You may call evaluate at most {B} times.` Every `evaluate` result ends with
`Evaluations remaining: {R}.` This is a hard cap, not a Thresholdout-style
holdout.

**pushed** — tools as control. Appended to the prompt:

```
Each evaluate result also reports how your current best compares with a search-adjusted bar for the class of specifications you can produce.
```

Every `evaluate` result ends with the standing: critical value, best in-sample
Sharpe so far, margin, and whether it clears.

## 3. Pinned values

- Model string: `claude-sonnet-5`. A run whose usage log reports any other
  string is excluded from analysis and noted.
- Extended thinking: off. Default sampling settings.
- Primary config `s0`: `s=0, K=40, M=50, T=500` in-sample, `T_oos=250`.
- Secondary config `s3`: as `s0` with `s=3`.
- Declared class: equal-weight subsets of up to `d=3` features, signed. Fixed by
  run config and opened by the harness; not an agent tool.
- `max_turns = 60`. A run that reaches it without calling `submit` is recorded
  as `no_submit` and kept in the run count.
- `evaluate` returns only the in-sample annualized Sharpe ratio and the number
  of observations, as one line of text, plus the arm's appended sentence where
  an arm defines one.
- Out-of-sample data is held in memory by the sandbox and never exposed to any
  tool the agent can call.

## 4. Run order and seeds

- Cut design first: `control` and `gate`, 40 runs each, config `s0`.
- Master seed 20260916. Per-run DGP seeds are the first 80 draws from
  `numpy.random.default_rng(20260916)`, assigned in run order.
- Arms alternate within every session: control, gate, control, gate, … No
  session contains runs of only one arm.
- `count` and `budget`, and config `s3`, run only after the first 80 are
  complete, under a dated amendment in §6 stating their run counts.

## 5. Measurements and analysis

Per run: evaluation count; submitted specification and its in-sample Sharpe;
stated `predicted_oos_sharpe` (mean, sd); Watch verdict at submit; realized
out-of-sample Sharpe computed by the harness after submit; `considered` count.

**`considered`**: distinct feature identifiers named in the agent's assistant
text blocks during the run that were never passed to `evaluate`. Reported as
`considered / evaluated`. (Redefined by amendment 3.)

**Primary analysis**, config `s0`, per arm: regress stated mean on
log(evaluation count). The hypothesis under test is a zero slope — stated
confidence deaf to the search performed. A nonzero negative slope is the
alternative; both outcomes are reported as results.

**Between-arm**: difference in slope, and difference in mean stated confidence
at matched evaluation count, control against gate.

**Secondary**: CRPS of the stated distribution against realized OOS Sharpe, per
arm. Deflation gap: stated mean minus the class-bar-implied expectation from the
Watch verdict.

**Exclusions, decided in advance**: runs whose model string differs from the
pinned one; runs where any non-`mcp__` tool was invoked; runs terminated by a
rate-limit error before `submit`. Each exclusion is counted and reported.

## 6. Amendments

**1 — 2026-09-16**, before any gate run. Pilot `s0_control_000` (T=500) returned
INADMISSIBLE at open: the pinned class has 82,240 members and power 0.001 at
reference Sharpe 1.0. Preflight at T ∈ {500, 1000, 2000, 3000, 5000} gives power
{0.001, 0.005, 0.042, 0.136, 0.458}, so 5,000 is the smallest tested admissible
T. Both configs change to T=5000, T_oos=1000; all else unchanged. The pilot is
superseded and excluded, retained as `runs/s0_control_000_T500` — evidence that
at short samples the gate refuses classes of this width, which is the intended
behavior. It also spent 3,206 thinking tokens because the harness deferred to
the CLI default, violating §3; the harness now sets thinking disabled
explicitly.

*(No Amendment 2 was issued. The numbering jumps from 1 to 3; nothing has been
removed from this log.)*

**3 — 2026-09-17.** §5's `considered` definition fired in 0 of 80 runs: agents
name a feature in prose and then evaluate it, so nothing qualifies. Reported as
such for seeds 0–79. For subsequent batches, `considered` is redefined as
distinct *specifications* (feature sets, not single features) named as
candidates in an assistant text block and not evaluated within that turn or the
next two. Applies only to runs after this amendment.

**4 — 2026-09-17.** Batch 2, 240 runs, seeds 80–319: s0 count 40; s0 budget 60
at B ∈ {20, 60, 180}, 20 each; s3 control 40 and gate 40; s0 control 30 and gate
30 as replication. Budget arm's primary analysis: stated mean regressed on
assigned log(B), the pre-registered deafness test with the exposure randomized.
s3 analysis: as §5, plus PASS rate against the preflight power at reference.
Rotation across all blocks within every session.

**5 — 2026-09-17.** Seed 89 (s0 budget-20) is void: a harness defect latched the
submission before the watch could refuse an unevaluated specification, and the
run was graded without a verdict. Fixed at `d0d7841`; the run is retained as
evidence. Replacement appended as seed 500, same cell, since seeds 320–499 are
allocated to batch 3. Runs 80–90 and 91+ ran under different harness
fingerprints, recorded per run; the change is the fix plus exclusion-rule and
analyzer corrections, none of which alter any prompt, tool or treatment text.

**6 — 2026-09-17.** Runs may execute in parallel workers within a usage window;
'session' in amendment 4 means the window, and rows are assigned round-robin
within block so each worker also rotates across all cells. No prompt, tool or
treatment text changes. Worker index and harness fingerprint recorded per run.

**7 — 2026-09-17.** Batch 3: {control, gate, pushed} × {claude-sonnet-5,
claude-fable-5-1} on s0, 30 runs per cell, 180 runs, seeds 320–499. Primary
analysis per §5 within each cell; between-model comparison of deflation gap and
evaluation count is exploratory. Thinking disabled for both models; model string
checked per call.

**8 — 2026-09-18.** The final rows of batch 2 ran under the batch-3 merge
(fingerprint change, §1–§5 md5 unchanged); recorded per run.

**9 — 2026-09-18.** Config s3's noise scale σ is recalibrated from 1.0 to
194.406790, setting the oracle's annualized Sharpe to 1.0 at M=50, K=40, s=3,
ρ=0. At σ=1 the s3 oracle is 73.4847: 28 of the 80 runs at seeds 84–319
submitted the true feature set at that ceiling against a class bar of 1.02, so
s3 as run measured a condition in which the signal exceeds the search correction
about seventyfold. Those 80 runs are retained and analysed under σ=1, never
pooled with the new value; the two are separable by seed and by the σ in each
run's `config.json`. The correction itself is unaffected, the class bar being a
ratio: at the two σ the watch opens with the same class size and, to bootstrap
noise, the same critical value (1.0241 against 1.0231) and power at reference
(0.4574 against 0.4590). Batch 4 re-runs s3: {control, gate} on
claude-sonnet-5, 40 per arm, 80 runs, seeds 501–580, arms strictly alternating.
The per-run seed draw extends from 520 to 581 values; §4's construction is
unchanged and every earlier draw is byte-identical.

**10 — 2026-09-18.** Batch 4's first four completed rows (seeds 501, 503, 505,
507 — the first row of each of four workers, all control) ran under fingerprint
`3e3af01a`, the remainder under `62ea4bfa`. The only difference is
`analyze_agent.py`, which no run reads. Same cell, pooled.

**11 — 2026-09-18.** Batch 5: config s3 under the recalibrated σ, {control,
gate} × claude-fable-5-1, 40 runs per arm, 80 runs, seeds 581–660, arms strictly
alternating. Thinking disabled; model string checked per call. The per-run seed
draw extends from 581 to 661 values; §4's construction is unchanged, every
earlier draw is byte-identical, and no seed in 581–660 repeats one already
drawn. Schedule: `experiments/schedule_80_s3_fable.txt`, generated by
`experiments/make_schedule.py`. Comparison with batch 4's Sonnet cells at the
same σ is exploratory and carries no error control: PASS rate, deflation gap,
evaluation count, and the haircut — the coefficient on submitted in-sample
Sharpe in the joint regression of stated mean on that and log(evaluation count).

**12 — 2026-09-18.** Batch 5 as specified in amendment 11 was rejected at its
first row on every worker: the seat's Fable allowance was exhausted by batch 3
and resets 2026-09-30. Batch 5 runs instead on claude-opus-5, same design, same
seeds 581–660, thinking disabled; the Fable version is deferred to the reset
date unchanged, on the same seeds, so the two are paired by DGP draw. Four
parked directories in `runs/_aborted/` hold no model output.

**13 — 2026-09-20.** `garden/_full_class_engine.py` gains
`full_class_observed_max`, for `calibration-at-1pct`'s arm D. `garden/` is inside
`code_state.CODE_PATHS`, so the harness fingerprint moves; no batch was in
flight. The addition is a new function and changes no existing code path, so the
bar any stored run was graded against is unaltered.

**Stored agent runs are not re-scored under the new fingerprint.** Every run in
`runs/` keeps the verdict it was given, computed by the engine as it stood at
that run's recorded fingerprint. Re-scoring them would silently replace
pre-registered results with numbers from code written afterwards, which is the
thing the fingerprint exists to make visible. Any future re-scoring is a new
experiment with its own pre-registration.

**14 — 2026-09-21.** `pyproject.toml` gains `quixote` in its `packages` list, for
the Don Quixote build. **`pyproject.toml` is inside `code_state.CODE_PATHS`, so
the harness fingerprint moves.** No batch was in flight.

The change is **packaging only**: it tells the build backend which directories to
install, and alters no import, no estimator, no bar and no verdict. `quixote` is
itself deliberately **outside** `CODE_PATHS`, and nothing in `garden`,
`estimator`, `environments` or `searchers` imports it — a test asserts that
direction — so no existing code path can reach it.

This resolves a conflict between two instructions that could not both hold: keep
quixote out of `CODE_PATHS` so no fingerprint moves, and add quixote to
pyproject's package list. The packages list is itself hashed, so the second moves
the fingerprint however the first is honoured. The conflict is recorded rather
than resolved silently, and the packaging need won.

**Amendment 13's rule applies unchanged:** every run in `runs/` keeps the verdict
it was given, at the fingerprint recorded for it. Nothing is re-scored.

Quixote runs do not use this fingerprint at all. They record their own, over
`quixote` plus everything quixote imports, via `quixote/fingerprint.py`;
`code_fingerprint` gained an optional `paths` argument so that is possible
without widening `CODE_PATHS` further.
