"""Pre-flight check for a model, before any batch run uses it.

    python -m experiments.check_model --model claude-fable-5-1

Answers the two questions that have to be settled on the seat before the first
run with a new model, in one call:

  1. **Availability.** Does the seat serve this model at all, and does it report
     back the exact string the run config pins? AGENT_PROMPTS.md §3 excludes any
     run whose model string differs from the pinned one, so a seat that silently
     substitutes a different model would void every run in the cell.

  2. **Per-turn overhead S.** The input side of a one-turn, no-tool call: every
     token the SDK sends that the experiment did not write. It is paid on every
     turn, so at max_turns=60 it dominates the cost of a run. See
     searchers/README_AGENT.md for the prediction this tests.

One turn, no tools, one-word answer. Costs a few thousand tokens, not a run.

Nothing here touches the sandbox, writes a run directory, or reads a
pre-registration: it is a property of the seat, not of the experiment.
"""
from __future__ import annotations

import argparse
import asyncio

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

from searchers.llm_agent import MODELS

USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens", "output_tokens")


async def probe(model: str) -> int:
    """One turn, no tools. Returns the process exit code."""
    opts = ClaudeAgentOptions(
        model=model,
        system_prompt="You are a test harness. Reply with exactly one word.",
        tools=[],                       # removes the built-in set, not merely refuses it
        setting_sources=[],             # no ~/.claude or project leakage
        thinking={"type": "disabled"},  # pinned for every model (§3)
        max_turns=1,
    )

    models_seen: set[str] = set()
    turn_usage: list[dict] = []
    result: ResultMessage | None = None

    async for msg in query(prompt="Reply with the single word: ok", options=opts):
        if isinstance(msg, AssistantMessage):
            if getattr(msg, "model", None):
                models_seen.add(msg.model)
            if getattr(msg, "usage", None):
                turn_usage.append({k: (msg.usage.get(k) or 0) for k in USAGE_KEYS})
        elif isinstance(msg, ResultMessage):
            result = msg

    if result is None:
        print("no ResultMessage returned; the call did not complete")
        return 1

    mu = result.model_usage or {}
    ru = result.usage or {}
    s = sum((ru.get(k) or 0) for k in USAGE_KEYS[:3])   # input side only

    print(f"requested model   {model}")
    print(f"models reported   {sorted(models_seen) or '(none on assistant messages)'}")
    print(f"model_usage keys  {sorted(mu)}")
    for name, per in mu.items():
        print(f"  {name}: output {per.get('outputTokens')}, "
              f"thinking {per.get('thinkingTokens')}, cost {per.get('costUSD')}")
    print(f"is_error          {getattr(result, 'is_error', None)} "
          f"(subtype {getattr(result, 'subtype', None)}, "
          f"status {getattr(result, 'api_error_status', None)})")
    print()
    print(f"S (per-turn overhead, input side) = {s:,} tokens")
    print(f"  at max_turns=60 that is ~{s * 60:,} input tokens of pure overhead per run")

    ok_name = models_seen == {model} or model in mu
    thinking = sum((p.get("thinkingTokens") or 0) for p in mu.values())
    print()
    print(f"model string matches the pin: {'yes' if ok_name else 'NO'}")
    print(f"thinking tokens spent:        {thinking} "
          f"({'compliant with §3' if thinking == 0 else 'VIOLATES §3'})")
    if s >= 8000:
        print("S >= 8k: the preset system prompt is probably still being sent; "
              "fix before spending a window, every downstream number scales with S.")
    return 0 if (ok_name and thinking == 0 and not getattr(result, "is_error", False)) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, required=True)
    a = ap.parse_args()
    return asyncio.run(probe(a.model))


if __name__ == "__main__":
    raise SystemExit(main())
