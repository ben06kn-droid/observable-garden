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

Per-turn cost is dominated by S because tool results are deliberately tiny:
`evaluate` returns one line under 40 tokens excluding an arm's appended
sentence. Results were the only lever left after the prompt and tool set were
fixed, which is why they are as terse as they are.
