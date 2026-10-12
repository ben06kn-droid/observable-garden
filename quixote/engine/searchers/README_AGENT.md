# Agent harness — predicted per-turn overhead

`S` is the harness overhead: everything the SDK sends that the experiment did
not write. It is the input side of a one-turn, no-tool call, and it is paid on
**every** turn, so it dominates a 60-turn run's cost.

## The measurement this replaces

**8.8k tokens per turn**, measured with a hand-maintained `disallowed_tools`
list. That approach refuses the built-in tools but still ships their schemas,
and `allowed_tools` only auto-approves rather than removes. The smoke test's
own revision history reached the same conclusion and switched to `tools=[]`.

## What this harness does instead

| setting | effect |
|---|---|
| `tools=[]` | removes the built-in set outright, schemas included. MCP tools are unaffected — the field governs built-ins only. |
| `system_prompt=<plain str>` | **replaces** the preset. A plain string maps to `--system-prompt`, not `--append-system-prompt`. |
| `setting_sources=[]` | no `~/.claude` or project settings. This is a validity requirement, not hygiene: leaked config would break the byte-identical-prompt guarantee of AGENT_PROMPTS.md §2. |

## Prediction

**S ≈ 1,200–2,000 tokens**, decomposed:

| component | estimate |
|---|---|
| pre-registered control prompt (AGENT_PROMPTS.md §1) | ~250 |
| three MCP tool schemas (`evaluate`, `status`, `submit`) | ~200 |
| irreducible SDK / CLI framing | ~800–1,500 |

Arrived at independently of, and agreeing with, the smoke-test protocol's
sanity figure of ~1,500.

## How the pilot confirms or falsifies it

Run the overhead probe and read the input side of a single turn:

- **S ≈ 1,200–2,000** — prediction holds; a 60-turn run costs roughly
  `60·S` plus the quadratic replay term.
- **S ≥ 8,000** — the preset system prompt is still being sent. `tools=[]` is
  not doing what this file claims, or `system_prompt` is appending rather than
  replacing. Stop and fix before spending a window; every downstream number
  scales with S.
- **S well under 1,000** — better than predicted; record it, since it changes
  how many runs a week the seat absorbs.

## Which usage path is authoritative — settled on pilot run 0

The two accountings disagreed sharply, and they disagree in *opposite
directions* on input and output:

| | assistant_summed | result_usage | authoritative |
|---|---:|---:|:--|
| input | 804k (108 msgs) | 91k | **assistant_summed** — cumulative replayed context |
| output | 500 | 12,052 | **result_usage** |
| cost | — | $0.2065 | **result_usage / model_usage** |
| model string | — | `claude-sonnet-5` | **model_usage / models_seen** |

**Output: `result_usage`.** 500 tokens across 108 messages is 4.6 per message —
below the assistant text blocks alone (~2,021 chars ≈ 505 tokens) before
counting 95 tool calls (~3,769 chars) or 3,206 thinking tokens.
`result_usage.output_tokens` equals `model_usage.outputTokens` exactly and is
what `costUSD` was derived from.

**Input: `assistant_summed`.** 804k is the replayed context summed over every
API response, which is the quantity that consumes a usage window.
`result_usage`'s 91k is the *final* call's context and does not measure replay.
Neither is wrong; they answer different questions.

**The undercount's mechanism is not yet known.** Run 0 logged only the sum, so
it cannot be distinguished from here whether `AssistantMessage.usage` snapshots
`output_tokens` before generation completes, or whether several message objects
share one usage dict. The SDK documents neither. Rather than apply an invented
correction factor, `usage.jsonl` now carries `assistant_usage_raw` — the
unsummed per-message blocks — so the next run settles it by observation.

`usage.jsonl` also records `wall_seconds`, first to last transcript timestamp
(run 0: 182.3 s).

## Extended thinking is on, contrary to the pre-registration

Run 0's `model_usage` reports `thinkingTokens: 3206`, but
`prereg/AGENT_PROMPTS.md` §3 pins extended thinking off.

`ClaudeAgentOptions.thinking` defaults to `None`, which is **not** off — it
defers to the CLI/model default. It is disableable:

```python
ClaudeAgentOptions(..., thinking={"type": "disabled"})
```

(`ThinkingConfigDisabled` is a TypedDict whose sole required key is `type`.)

This is **not applied**: run 0 was executed with thinking on, and disabling it
mid-pilot would make run 0 incomparable with every run after it. Whether to
disable and discard run 0, or to amend §6, is a decision for the owner.

Per-turn cost is dominated by S because tool results are deliberately tiny:
`evaluate` returns one line under 40 tokens excluding an arm's appended
sentence. Results were the only lever left after the prompt and tool set were
fixed, which is why they are as terse as they are.
