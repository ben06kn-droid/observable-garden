# Exclusions, aborted runs, and the irregular runs that were kept

**No run was excluded by the pre-registered categories.** `AGENT_PROMPTS.md` §5
fixes three — a reported model string differing from the run's own assigned
model, a non-MCP tool call, and a rate limit before submit — and across all
sixteen cells the count is zero for each. The analysis set is 661 runs.

## Kept, with a defect recorded

These are reported in the integrity block rather than dropped, because each
defect is in the record of a run rather than in its result.

| run | what happened |
|---|---|
| `s0_T5000_sonnet_count_200` | ended without submitting. §3 keeps such a run in the count: it carries no stated belief and no verdict, so it enters every *n* and no statistic. |
| `s3_T5000_sonnet_gate_548` | the same. |
| `s0_T5000_sonnet_budget20_089` | void under amendment 5 — finished but was never graded. Seed 500 is its replacement, which is why b2 holds 241 runs rather than 240. |
| `s0_T5000_sonnet_count_314` | `config.json` is missing: two runners overlapped on that row and one parked the directory the other was writing into. Identity is recovered from the directory name; fingerprint, worker and preflight power are unrecorded and shown as such. The results themselves are intact. |
| `s3_T5000_opus_control_599` | no `usage.jsonl`, so no reported model string to check against §5's pin — a rate limit on a trailing turn. The model is the one `config.json` assigns. `error.json` records the failure and is archived with the run. Retained, not excluded: §5 excludes a run whose reported string *differs* from the pin, and silence is a different condition. |

## Not in any batch

- **`s0_control_000_T500`** — superseded by amendment 1, which moved the arm to
  T=5000. Excluded by prefix rather than by judgement: it does not match
  `s0_T5000_`/`s3_T5000_`, so no analysis has ever read it. Kept on disk as
  evidence; it is not archived into a batch, because it belongs to none.
- **`_aborted/`** — runs stopped mid-flight, mostly where two runners collided
  on a row or a batch was halted. The b5 Fable arm (seeds 581+) was allocated by
  amendment 12 and aborted, so b5 holds Opus only.
- **`_excluded/`** — `s0_T5000_count_000_smoke`, a seed-0 smoke test of the count
  arm run while implementing it, outside amendment 4's allocation of seeds
  80–319.
- **`_logs/`, `_logs_batch2/`** — runner logs, never tracked.

None of these four is data, and none is ever read by the analysis.
