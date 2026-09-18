"""LLMAgent: one model-driven search against a Watch-wrapped Sandbox.

The agent sees the sandbox only through an in-process MCP server carrying two
or three tools. It never sees out-of-sample data: the sandbox holds it in
memory, no tool exposes it, and the agent runs with an empty working directory
and no built-in file tools, so there is nothing on disk to read either.

Arms are defined in prereg/AGENT_PROMPTS.md, fixed before any run:

    control   evaluate, submit
    gate      evaluate, status, submit          status -> `standing` view only
    count     evaluate, submit                  result carries a running count
    budget    evaluate, submit                  hard cap on evaluate calls

Batch 3 crosses the arms with the model (MODELS). Thinking is pinned disabled
for both, and each run's model string is logged and checked per call against
that run's own assignment.

The declared class is fixed by run config and opened by the harness. It is
deliberately NOT an agent tool: the class must be fixed before anything is
seen, which is the premise the declared-class tier rests on (THEORY.md P3).

Token budget
------------
Tool results are the only lever left on per-turn cost, so `evaluate` returns
one short line -- under 40 tokens excluding an arm's appended sentence. See
README_AGENT.md for the predicted harness overhead and how the pilot confirms
it.

Why `tools=[]` rather than a `disallowed_tools` list
----------------------------------------------------
`allowed_tools` only auto-approves; it does not remove. A hand-maintained
`disallowed_tools` list refuses the built-ins but still ships their schemas,
and it silently rots as the CLI adds tools. `tools=[]` removes the built-in
set outright. MCP tools are unaffected -- that field governs the built-in set
only. `setting_sources=[]` is a validity requirement rather than hygiene:
without it `~/.claude` and project settings leak into a prompt that
AGENT_PROMPTS.md 2 requires to be byte-identical across arms.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    RateLimitEvent,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)
from environments.sandbox import Distribution, Specification
from searchers.base import Searcher

ARMS = ("control", "count", "gate", "budget", "pushed")
# Amendment 4 opened count and budget (seeds 80-319); amendment 7 opened pushed
# for batch 3 (seeds 320-499), with its prompt sentence registered in prereg §2.
LIVE_ARMS = ARMS

# Batch 3's model dimension. Thinking is pinned disabled for both (§3).
MODELS = ("claude-sonnet-5", "claude-fable-5-1")
MODEL_TAGS = {"claude-sonnet-5": "sonnet", "claude-fable-5-1": "fable"}
SERVER_NAME = "garden"
USAGE_KEYS = ("input_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens", "output_tokens")


class RateLimited(RuntimeError):
    """Raised so the runner can stop cleanly rather than retry in a loop."""


class AuthFailed(RuntimeError):
    pass


def tool_names(arm: str) -> list[str]:
    """Fully-qualified MCP tool names for an arm. `status` exists only in gate."""
    names = ["evaluate", "submit"] + (["status"] if arm == "gate" else [])
    return [f"mcp__{SERVER_NAME}__{n}" for n in sorted(names)]


def build_prompt(template: str, M: int, K: int, d: int) -> str:
    """Substitute the three run-config integers into a pre-registered prompt.

    Only M, K and d vary (AGENT_PROMPTS.md 1). Anything else left unsubstituted
    is a mistake, so it raises rather than reaching the model."""
    try:
        out = template.format(M=M, K=K, d=d)
    except (KeyError, IndexError) as e:
        # str.format raises before any post-hoc check could run, so the guard
        # has to live here. A prompt carrying any placeholder beyond M/K/d is a
        # mistake in the pre-registered text, not something to reach the model.
        raise ValueError(
            f"unsubstituted placeholder {e} in the prompt; only M, K and d vary "
            f"(prereg/AGENT_PROMPTS.md §1)"
        ) from None
    if "{" in out and "}" in out:
        raise ValueError(f"unsubstituted placeholder remains in the prompt: {out[:120]!r}")
    return out


def spec_from(features, signs, K: int, name: str = "") -> Specification:
    features = [int(f) for f in features]
    signs = [int(s) for s in signs]
    if len(features) != len(signs):
        raise ValueError(f"features and signs differ in length: {len(features)} vs {len(signs)}")
    if not features:
        raise ValueError("a specification needs at least one feature")
    if len(set(features)) != len(features):
        raise ValueError(f"repeated feature in {features}")
    w = np.zeros(K)
    for f, s in zip(features, signs):
        if not 0 <= f < K:
            raise ValueError(f"feature {f} out of range 0..{K - 1}")
        if s not in (1, -1):
            raise ValueError(f"sign must be 1 or -1, got {s}")
        w[f] = float(s)
    return Specification(weights=w, name=name or "+".join(
        f"{'-' if s < 0 else ''}f{f}" for f, s in zip(features, signs)))


@dataclass
class RunPaths:
    """Per-run artifact directory, created on first write rather than eagerly.

    Two failure modes this is shaped around, both observed:

    * Creating the directory in __post_init__ meant a run that died before its
      first write left an empty shell indistinguishable from a stale one.
    * transcript.jsonl and usage.jsonl are append-mode, so a second run writing
      into an existing directory interleaves its records with the first into a
      file that still parses. That is worse than an overwrite, because nothing
      about the result looks wrong.

    So a directory that already exists with anything in it is a hard error
    naming the path. There is deliberately no force flag: the only correct
    responses are to move the old run or to delete it, and both should be a
    decision rather than a default."""
    root: Path

    def __post_init__(self):
        self.root = Path(self.root)
        if self.root.exists() and any(self.root.iterdir()):
            raise FileExistsError(
                f"run directory already exists and is not empty: {self.root}\n"
                f"transcript.jsonl and usage.jsonl are append-mode, so writing a second "
                f"run here would interleave it with the first rather than replace it. "
                f"Move or delete that directory and run again."
            )

    def path(self, name: str) -> Path:
        return self.root / name

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, obj) -> None:
        self._ensure()
        self.path(name).write_text(json.dumps(obj, indent=2, default=_json_safe))

    def append_jsonl(self, name: str, obj) -> None:
        self._ensure()
        with self.path(name).open("a") as f:
            f.write(json.dumps(obj, default=_json_safe) + "\n")


def _json_safe(x):
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (set, frozenset)):
        return sorted(x)
    return str(x)


@dataclass
class AgentConfig:
    arm: str = "control"
    model: str = "claude-sonnet-5"
    max_turns: int = 60
    budget: int | None = None          # budget arm only
    # Verbatim result templates from prereg §2, injected rather than hardcoded.
    count_result: str = "Specifications evaluated so far: {N}."
    budget_result: str = "Evaluations remaining: {R}."
    system_prompt: str = ""
    M: int = 50
    K: int = 40
    d: int = 3
    run_id: str = "run"
    seed_index: int = 0                # selects the `considered` rule; see _finalize
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.arm not in ARMS:
            raise ValueError(f"arm must be one of {ARMS}, got {self.arm!r}")
        if self.arm == "budget" and self.budget is None:
            raise ValueError("the budget arm needs an explicit evaluate cap")
        if self.model not in MODELS:
            raise ValueError(f"model must be one of {MODELS}, got {self.model!r}")


class LLMAgent(Searcher):
    """One search. Construct, then `run(watch)`.

    Not a drop-in for the scripted Searcher contract: `run` takes a `Watch`
    rather than a `Sandbox`, because the whole point is that every evaluation
    is priced against a bar fixed at open."""
    name = "llm_agent"

    def __init__(self, config: AgentConfig, paths: RunPaths, seed: int = 0):
        super().__init__(seed=seed)
        self.config = config
        self.paths = paths
        self.verdict = None
        self.stated: dict | None = None
        self.submitted_spec: Specification | None = None
        self._watch = None
        self._n_eval = 0
        self._budget_refusals = 0      # (B+1)th call onward; a cap, not a Theta breach
        self._turn_usage: list[dict] = []
        self._turn_usage_raw: list[dict] = []
        self._models_seen: set[str] = set()
        self._rate_limit: dict | None = None
        self._first_ts: float | None = None
        self._last_ts: float | None = None

    # -- transcript ----------------------------------------------------------

    def _log(self, kind: str, **fields) -> None:
        ts = time.time()
        if self._first_ts is None:
            self._first_ts = ts
        self._last_ts = ts
        self.paths.append_jsonl("transcript.jsonl", {"ts": ts, "kind": kind, **fields})

    # -- arm sentence --------------------------------------------------------

    def _arm_sentence(self, report=None) -> str:
        """Appended verbatim to every evaluate result, per AGENT_PROMPTS.md 2.

        The count and budget templates come from the pre-registration via
        AgentConfig, not from literals here: 2 requires byte identity with the
        registered text, which is only enforceable if there is one copy of it.

        """
        if self.config.arm == "count":
            return " " + self.config.count_result.replace("{N}", str(self._n_eval))
        if self.config.arm == "budget":
            left = max(0, self.config.budget - self._n_eval)
            return " " + self.config.budget_result.replace("{R}", str(left))
        if self.config.arm == "pushed":
            # §2 registers this one as prose rather than as a template with a
            # placeholder: "the standing: critical value, best in-sample Sharpe
            # so far, margin, and whether it clears". There is no registered
            # string to substitute into, so the four quantities are composed
            # here and pinned by a test. Margin is taken against the best so
            # far, not the call just made, because the standing is about the
            # best -- as is "whether it clears".
            if report is None:
                return ""
            margin = report.best_so_far - report.critical_value
            return (f" Bar {report.critical_value:.3f}; best {report.best_so_far:.3f}; "
                    f"margin {margin:+.3f}; "
                    f"{'clears' if report.best_so_far_cleared else 'does not clear'}.")
        return ""

    # -- tools ---------------------------------------------------------------

    def _build_tools(self):
        """The SdkMcpTool objects for this arm, in a stable order.

        Kept separate from `_make_server` because `create_sdk_mcp_server`
        returns a plain dict (`{type, name, instance}`) with no way back to the
        tool objects, so a caller that wants to exercise the handlers directly
        -- tests/test_llm_agent.py does -- has nothing to introspect."""
        K = self.config.K
        agent = self

        @tool("evaluate", "In-sample Sharpe of an equal-weight signed feature combination.",
              {"features": list[int], "signs": list[int]})
        async def evaluate(args):
            try:
                spec = spec_from(args.get("features", []), args.get("signs", []), K)
            except ValueError as e:
                agent._log("tool_error", tool="evaluate", args=args, error=str(e))
                return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
            if agent.config.arm == "budget" and agent._n_eval >= agent.config.budget:
                # The (B+1)th call and every one after it. A hard cap, refused by
                # the harness -- not a class violation, so it never reaches Watch
                # and is not counted among refused_attempts. Logged distinctly so
                # the analysis can tell a cap from a Theta breach.
                text = (f"Refused: evaluation budget of {agent.config.budget} is spent. "
                        f"Call submit with your chosen specification.")
                agent._budget_refusals += 1
                agent._log("tool_error", tool="evaluate", args=args, error="budget_exhausted",
                           text=text)
                return {"content": [{"type": "text", "text": text}]}
            try:
                report = agent._watch.evaluate(spec)
            except ValueError as e:
                agent._log("tool_error", tool="evaluate", args=args, error=str(e))
                return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
            agent._n_eval += 1
            # Under 40 tokens excluding the arm sentence: results are the only
            # remaining lever on per-turn cost.
            text = f"Sharpe {report.sr_is:.3f}, n={agent._watch.state.n_periods}."
            text += agent._arm_sentence(report)
            agent._log("tool_result", tool="evaluate", args=args, text=text,
                       sr_is=report.sr_is, n_evaluated=agent._n_eval)
            return {"content": [{"type": "text", "text": text}]}

        @tool("submit", "Submit one specification with your predicted out-of-sample Sharpe.",
              {"features": list[int], "signs": list[int], "mean": float, "sd": float})
        async def submit(args):
            try:
                spec = spec_from(args.get("features", []), args.get("signs", []), K)
                mean, sd = float(args["mean"]), float(args["sd"])
            except (ValueError, KeyError, TypeError) as e:
                agent._log("tool_error", tool="submit", args=args, error=str(e))
                return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
            if agent.submitted_spec is not None:
                return {"content": [{"type": "text", "text": "Already submitted."}]}
            # The watch call goes first and the run is latched only once it has
            # returned. Latching before it inverts the failure: a refused submit
            # left submitted_spec set with no verdict, so every retry hit
            # "Already submitted." above, the agent could never recover, and the
            # harness still graded OOS and exited 0. That silently voided
            # s0_T5000_sonnet_budget20_089, whose first submit named a
            # specification it had never evaluated.
            #
            # A refusal is not a trial -- Watch counts it in refused_attempts and
            # its message is data-independent -- so it is returned to the agent
            # the way `evaluate` returns one, and the agent may submit again.
            try:
                verdict = agent._watch.submit(spec, Distribution(mean=mean, std=sd))
            except ValueError as e:
                agent._log("tool_error", tool="submit", args=args, error=str(e))
                return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
            agent.submitted_spec = spec
            agent.stated = {"mean": mean, "sd": sd}
            agent.verdict = verdict
            agent.paths.write_json("stated.json", agent.stated)
            agent.paths.write_json("verdict.json", agent.verdict.to_dict())
            agent._log("tool_result", tool="submit", args=args, status=agent.verdict.status)
            return {"content": [{"type": "text", "text": "Submitted."}]}

        @tool("status", "Where your current best stands against the search-adjusted bar.",
              {})
        async def status(args):
            r = agent._watch.status()
            text = (f"Best {r.best_so_far:.3f} vs bar {r.critical_value:.3f}; "
                    f"{'clears' if r.best_so_far_cleared else 'does not clear'}.")
            agent._log("tool_result", tool="status", args=args, text=text)
            return {"content": [{"type": "text", "text": text}]}

        return [evaluate, submit] + ([status] if self.config.arm == "gate" else [])

    def _make_server(self):
        return create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0",
                                     tools=self._build_tools())

    # -- options -------------------------------------------------------------

    def _options(self, cwd: Path) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            model=self.config.model,
            system_prompt=self.config.system_prompt,   # plain str => replaces the preset
            tools=[],                                  # removes the built-in set entirely
            setting_sources=[],                        # no ~/.claude or project leakage
            # Explicitly disabled, not left to default. `thinking=None` is not
            # off: it defers to the CLI, and pilot run 0 spent 3,206 thinking
            # tokens against a pre-registration that pins thinking off
            # (AGENT_PROMPTS.md 3). That run is superseded; see amendment 1.
            thinking={"type": "disabled"},
            mcp_servers={SERVER_NAME: self._make_server()},
            allowed_tools=tool_names(self.config.arm),
            max_turns=self.config.max_turns,
            cwd=str(cwd),
        )

    # -- the run -------------------------------------------------------------

    def run(self, watch) -> None:
        self._watch = watch
        asyncio.run(self._run_async())

    async def _run_async(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory(prefix="garden_agent_") as tmp:
            opts = self._options(Path(tmp))
            async with ClaudeSDKClient(options=opts) as client:
                await client.query("Begin.")
                await self._drain(client.receive_response())
        self._finalize()

    async def _drain(self, stream) -> None:
        async for msg in stream:
            if isinstance(msg, RateLimitEvent):
                info = msg.rate_limit_info
                self._rate_limit = {"status": getattr(info, "status", None),
                                    "resets_at": getattr(info, "resets_at", None),
                                    "type": getattr(info, "rate_limit_type", None)}
                self._log("rate_limit", **self._rate_limit)
                if getattr(info, "status", None) == "rejected":
                    raise RateLimited(f"rate limit rejected: {self._rate_limit}")
                continue

            if isinstance(msg, AssistantMessage):
                if getattr(msg, "model", None):
                    self._models_seen.add(msg.model)
                if getattr(msg, "usage", None):
                    self._turn_usage.append({k: (msg.usage.get(k) or 0) for k in USAGE_KEYS})
                    # Kept unsummed as well: the summed output_tokens is known to
                    # undercount (run 0: 500 across 108 messages, against 12,052
                    # from ResultMessage), and the mechanism cannot be diagnosed
                    # from a sum. Raw blocks make the next run diagnosable.
                    self._turn_usage_raw.append(dict(msg.usage))
                for block in msg.content:
                    if isinstance(block, TextBlock):
                        self._log("assistant_text", text=block.text)
                    elif isinstance(block, ToolUseBlock):
                        self._log("tool_use", tool=block.name, id=block.id, input=block.input)
                continue

            if isinstance(msg, ResultMessage):
                self._write_usage(msg)
                if getattr(msg, "is_error", False):
                    status = getattr(msg, "api_error_status", None)
                    subtype = getattr(msg, "subtype", None)
                    detail = {"subtype": subtype, "api_error_status": status,
                              "errors": getattr(msg, "errors", None),
                              "terminal_reason": getattr(msg, "terminal_reason", None)}
                    self._log("result_error", **detail)
                    if status in (401, 403):
                        raise AuthFailed(f"auth failure from the SDK: {detail}")
                    if status == 429 or (subtype and "rate" in str(subtype).lower()):
                        raise RateLimited(f"rate limited: {detail}")

    def _write_usage(self, msg: ResultMessage) -> None:
        """Both accountings, side by side, with which one governs made explicit.

        Settled on run 0 (see searchers/README_AGENT.md):

        * ResultMessage.usage / model_usage is authoritative for **cost**,
          **output tokens** and the **model string**. Its output_tokens matched
          model_usage.outputTokens exactly and is what costUSD was computed
          from.
        * The per-assistant-message sum is authoritative only for **cumulative
          replayed input** -- 804k across 108 messages against ResultMessage's
          91k, which is the final call's context and does not measure the
          replay at all. Its output_tokens undercounts badly (500, below the
          assistant text alone) and must not be used.

        The raw per-message blocks are kept unsummed so the undercount's
        mechanism can be diagnosed from the next run rather than guessed at."""
        summed = {k: sum(t[k] for t in self._turn_usage) for k in USAGE_KEYS}
        result_usage = {k: ((getattr(msg, "usage", None) or {}).get(k) or 0) for k in USAGE_KEYS}
        wall = (self._last_ts - self._first_ts) if (self._first_ts and self._last_ts) else None
        self.paths.append_jsonl("usage.jsonl", {
            "ts": time.time(),
            "wall_seconds": wall,
            "first_ts": self._first_ts,
            "last_ts": self._last_ts,
            "authoritative": {
                "cost": "result_usage / model_usage",
                "output_tokens": "result_usage",
                "model_string": "model_usage keys / models_seen",
                "cumulative_input": "assistant_summed",
                "note": "assistant_summed.output_tokens undercounts; do not use",
            },
            "assistant_summed": summed,
            "assistant_usage_raw": self._turn_usage_raw,
            "assistant_api_calls": len(self._turn_usage),
            "result_usage": result_usage,
            "model_usage": getattr(msg, "model_usage", None),
            "models_seen": sorted(self._models_seen),
            "model_config": self.config.model,
            "total_cost_usd": getattr(msg, "total_cost_usd", None),
            "num_turns": getattr(msg, "num_turns", None),
            "stop_reason": getattr(msg, "stop_reason", None),
            "terminal_reason": getattr(msg, "terminal_reason", None),
            "is_error": getattr(msg, "is_error", None),
            "subtype": getattr(msg, "subtype", None),
            "api_error_status": getattr(msg, "api_error_status", None),
        })

    # Amendment 3 applies to runs after it, i.e. the second batch onward.
    AMENDMENT_3_FIRST_SEED_INDEX = 80

    def _finalize(self) -> None:
        """`considered` is counted here, never by the agent.

        Two definitions, chosen by seed index so already-committed runs keep the
        number they were scored under.

        §5 (seeds 0-79): distinct *feature identifiers* named in assistant text
        and never passed to evaluate. It fired in 0 of 80 runs, because agents
        name a feature in prose and then evaluate it, so nothing qualified.

        Amendment 3 (seeds 80+): distinct *specifications* -- feature sets, not
        single features -- named as candidates in an assistant text block and
        not evaluated within that turn or the next two.

        A turn is not marked in the transcript, so it is defined here as one
        assistant_text block plus the tool calls following it up to the next
        assistant_text. "That turn or the next two" is therefore a forward
        window spanning three assistant-text boundaries. Sets are read as
        bracketed lists, which is how agents overwhelmingly write them (427 of
        604 set mentions in the first batch); the bare `a+b` and `features a, b`
        forms are matched too."""
        import re
        rows = [json.loads(l) for l in
                self.paths.path("transcript.jsonl").read_text().splitlines()]
        amended = self.config.seed_index >= self.AMENDMENT_3_FIRST_SEED_INDEX

        if not amended:
            named: set[int] = set()
            evaluated: set[int] = set()
            for row in rows:
                if row["kind"] == "assistant_text":
                    named.update(int(m) for m in re.findall(r"\bf(\d+)\b", row["text"])
                                 if int(m) < self.config.K)
                elif row["kind"] == "tool_result" and row.get("tool") == "evaluate":
                    evaluated.update(int(f) for f in row.get("args", {}).get("features", []))
            considered = [[f] for f in sorted(named - evaluated)]
            definition = ("distinct feature identifiers named in assistant text blocks and "
                          "never passed to evaluate (prereg/AGENT_PROMPTS.md §5)")
        else:
            considered, definition = self._considered_amendment_3(rows)

        self.paths.write_json("considered.json", {
            "definition": definition,
            "rule": "amendment_3" if amended else "section_5",
            "considered": considered,
            "n_considered": len(considered),
            "n_evaluated_calls": self._n_eval,
            "budget_refusals": self._budget_refusals,
            "ratio": (len(considered) / self._n_eval) if self._n_eval else None,
        })

    def _considered_amendment_3(self, rows: list[dict]) -> tuple[list, str]:
        import re
        K = self.config.K

        def sets_in(text: str) -> set[frozenset[int]]:
            out: set[frozenset[int]] = set()
            for pat in (r"\[\s*(\d+(?:\s*,\s*\d+)+)\s*\]",       # [4, 17, 5]
                        r"\bfeatures?\s+(\d+(?:\s*,\s*\d+)+)",   # features 4, 17
                        r"\b(\d+(?:\s*\+\s*\d+)+)\b"):           # 4+17
                for m in re.findall(pat, text, re.I):
                    ids = [int(x) for x in re.split(r"[,+]", m)]
                    if len(ids) > 1 and all(0 <= i < K for i in ids):
                        out.add(frozenset(ids))
            return out

        # Index every assistant_text block, and the evaluates that follow it.
        boundaries = [i for i, r in enumerate(rows) if r["kind"] == "assistant_text"]
        evaluated_at: list[tuple[int, frozenset[int]]] = [
            (i, frozenset(int(f) for f in r.get("args", {}).get("features", [])))
            for i, r in enumerate(rows)
            if r["kind"] == "tool_result" and r.get("tool") == "evaluate"]

        considered: set[frozenset[int]] = set()
        for n, idx in enumerate(boundaries):
            # Window: this turn plus the next two, i.e. up to the boundary three ahead.
            end = boundaries[n + 3] if n + 3 < len(boundaries) else len(rows)
            in_window = {s for i, s in evaluated_at if idx <= i < end}
            for cand in sets_in(rows[idx]["text"]):
                if cand not in in_window:
                    considered.add(cand)

        return ([sorted(s) for s in sorted(considered, key=lambda s: (len(s), sorted(s)))],
                "distinct specifications (feature sets) named as candidates in an assistant "
                "text block and not evaluated within that turn or the next two "
                "(prereg/AGENT_PROMPTS.md §6, amendment 3)")
