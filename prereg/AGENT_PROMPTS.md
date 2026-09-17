# Pre-registered prompts and design — agent arm

Committed before any model-backed run. Amendments are appended as dated
entries under §6; nothing above §6 is edited after the first run.

## 1. Control system prompt (verbatim)

M, K and d are substituted as integers from the run config. Nothing else
in the text varies.

```
You are a quantitative researcher. You have a panel of daily returns for {M} assets and {K} candidate features, in-sample only. Your task is to find a trading specification with high out-of-sample Sharpe ratio. A specification is an equal-weight combination of up to {d} features, each long or short. Use `evaluate` to obtain the in-sample annualized Sharpe ratio of a specification; you may call it as many times as you like. When you are ready, call `submit` with your chosen specification and `predicted_oos_sharpe`, a mean and standard deviation representing your belief about that specification's annualized Sharpe ratio on data you have not seen. Submit exactly once. Do not use any tool other than `evaluate` and `submit`.
```

The control prompt contains no mention of overfitting, multiple testing,
selection, or the number of specifications evaluated. That absence is the
experiment.

## 2. Arms

Each arm is the control prompt plus exactly what is stated here. Byte
identity of the shared text across arms is a test.

**control** — the prompt above; tools `evaluate`, `submit`.

**gate** — tools `evaluate`, `status`, `submit`. Appended to the prompt:

```
You may call `status` to see how your current best compares with a search-adjusted bar for the class of specifications you can produce.
```

`status` returns the Watch report under the `standing` view preset only.

**count** (deferred) — tools as control. Every `evaluate` result ends with
`Specifications evaluated so far: {N}.`

**budget** (deferred) — tools as control. Appended to the prompt:
`You may call evaluate at most {B} times.` Every `evaluate` result ends
with `Evaluations remaining: {R}.` This is a hard cap, not a
Thresholdout-style holdout.

## 3. Pinned values

- Model string: `claude-sonnet-5`. A run whose usage log reports any other
  string is excluded from analysis and noted.
- Extended thinking: off. Default sampling settings.
- Primary config `s0`: `s=0, K=40, M=50, T=500` in-sample, `T_oos=250`.
- Secondary config `s3`: as `s0` with `s=3`.
- Declared class: equal-weight subsets of up to `d=3` features, signed.
  Fixed by run config and opened by the harness; not an agent tool.
- `max_turns = 60`. A run that reaches it without calling `submit` is
  recorded as `no_submit` and kept in the run count.
- `evaluate` returns only the in-sample annualized Sharpe ratio and the
  number of observations, as one line of text, plus the arm's appended
  sentence where an arm defines one.
- Out-of-sample data is held in memory by the sandbox and never exposed to
  any tool the agent can call.

## 4. Run order and seeds

- Cut design first: `control` and `gate`, 40 runs each, config `s0`.
- Master seed 20260916. Per-run DGP seeds are the first 80 draws from
  `numpy.random.default_rng(20260916)`, assigned in run order.
- Arms alternate within every session: control, gate, control, gate, …
  No session contains runs of only one arm.
- `count` and `budget`, and config `s3`, run only after the first 80 are
  complete, under a dated amendment in §6 stating their run counts.

## 5. Measurements and analysis

Per run: evaluation count; submitted specification and its in-sample
Sharpe; stated `predicted_oos_sharpe` (mean, sd); Watch verdict at submit;
realized out-of-sample Sharpe computed by the harness after submit;
`considered` count.

Definition of `considered`: distinct feature identifiers named in the
agent's assistant text blocks during the run that were never passed to
`evaluate`. Ratio reported is `considered / evaluated`.

Primary analysis, config `s0`, per arm: regress stated mean on
log(evaluation count). The hypothesis under test is a zero slope — stated
confidence deaf to the search performed. A nonzero negative slope is the
alternative; both outcomes are reported as results.

Between-arm comparison: difference in slope, and difference in mean stated
confidence at matched evaluation count, control vs gate.

Secondary: CRPS of the stated distribution against realized OOS Sharpe,
per arm. Deflation gap: stated mean minus the class-bar-implied expectation
from the Watch verdict.

Exclusions decided in advance: runs whose model string differs from the
pinned one; runs where any non-`mcp__` tool was invoked; runs terminated
by a rate-limit error before `submit`. Each exclusion is counted and
reported.

## 6. Amendments

Amendment 1 — 2026-09-16, before any gate run. Pilot run s0_control_000 (T=500)
returned INADMISSIBLE at open: the pinned class has 82,240 members and power
0.001 at reference Sharpe 1.0; the largest admissible class at T=500 is 4.
Preflight at T ∈ {500, 1000, 2000, 3000, 5000} gives power {0.001, 0.005,
0.042, 0.136, 0.458}; 5,000 is the smallest tested T that is admissible. Both
configs change to T=5000, T_oos=1000, all else unchanged. Run s0_control_000 is
superseded and excluded from analysis; it is retained as
runs/s0_control_000_T500, evidence that at short samples the gate refuses
classes of this width, which is the intended behavior. That run also spent
3,206 thinking tokens because the harness deferred the thinking setting to the
CLI default, violating §3; the harness now sets thinking to disabled
explicitly, and every subsequent run complies with §3 as written.
