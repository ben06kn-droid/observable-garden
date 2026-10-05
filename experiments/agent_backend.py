"""The model-backed search backend: one session, one arm, one run.

Factored out of `experiments/agent_pilot.py` on 2026-09-29 so that
`experiments/agent_cell.py` drives the **same** machinery rather than a second
copy of it. Two runners sharing a backend is the only way the agent cell's runs
are comparable with the pilot's, and a copy would drift silently.

`agent_pilot.py` is FROZEN at the pilot's behaviour: it imports these names and
adds nothing. New work belongs in `agent_cell.py`.

Nothing here knows which panel it is on. The caller supplies a sandbox, a class,
a prompt and an arm; this module runs the agent against them and records what
happened. That is what lets `s0`, `s3` and `etf` go through one code path.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from environments.class_table import build_class_table
from environments.real_panel import ADR_HOME, build_adr_panel
from environments.real_sandbox import RealSandbox
from environments.sandbox import Distribution, Specification
from experiments.code_state import code_state
from experiments.real_prompts import TOOLS_FOR, read_prompts, system_prompt_for
from garden.spec_class import SubsetClass
from quixote.agent_adapter import ToolRefused, ToolSession
from quixote.session import Session
from quixote.twins import Masking



# Pinned, and shared by every runner that uses this backend.
# `AGENT_PROMPTS_REAL.md` §3: a run whose usage log reports any other model is
# discarded, which `_served_model_assertion` checks per run.
MODEL = "claude-sonnet-5"
MAX_TURNS = 60
SERVER_NAME = "garden_pilot"


# agent-pilot.md, "What is measured" 2: the registered refusal kinds. A refusal
# outside this set is rule 1's blocking failure, not a data point.
REFUSAL_KINDS = ("unknown_tool", "trigger_did_not_fire", "unknown_trigger",
                 "declaration_after_evaluation", "outside_class", "after_submit",
                 "after_stop",          # amendment 1, found by the dry run
                 "malformed_arguments",  # amendment 2, found by attempt 1
                 "undeclared_trigger",   # amendment 5, the new rule firing
                 "trigger_is_firing",    # amendment 6, decision (b)
                 "inapplicable_move")    # amendment 8: well formed, undefined here


def classify_refusal(message: str) -> str:
    """Map a refusal to one of the registered kinds, or to `UNREGISTERED`, which
    rule 1 treats as a defect rather than a measurement."""
    m = message.lower()
    if "unknown tool" in m:
        return "unknown_tool"
    if "does not fire" in m:
        return "trigger_did_not_fire"
    if "unknown trigger" in m:
        return "unknown_trigger"
    if "has submitted" in m:
        return "after_submit"
    if "has stopped" in m:
        return "after_stop"
    # amendment 5: a meta move naming a trigger that was not declared up front,
    # or declared for the other action. The rule working, not a defect.
    if "not declared before the first evaluation" in m:
        return "undeclared_trigger"
    # amendment 6, decision (b): a content move while a declared rule is firing.
    if "has fired" in m:
        return "trigger_is_firing"
    # amendment 8: well-formed arguments, move undefined in this state.
    if "is not defined in this state" in m:
        return "inapplicable_move"
    if "outside the declared class" in m or "leave the declared class" in m:
        return "outside_class"
    # amendment 2: an argument the harness cannot interpret. The harness is
    # refusing correctly; the registered list simply had no kind for it.
    if ("is outside 0.." in m or "unknown statistic" in m or "at most once" in m
            or "signs are +1 or -1" in m or "same length" in m):
        return "malformed_arguments"
    if "refuses" in m and ("late" in m or "after" in m):
        return "declaration_after_evaluation"
    if "already" in m and ("evaluat" in m or "move" in m):
        return "declaration_after_evaluation"
    return "UNREGISTERED"


# -- one run's record --------------------------------------------------------


@dataclass
class RunRecord:
    run_id: str
    arm: str
    seed: int
    events: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    moves: dict = field(default_factory=dict)          # move kind -> count
    triggers_declared: dict = field(default_factory=dict)
    triggers_fired: dict = field(default_factory=dict)
    picks_accepted: int = 0
    picks_contradicted: int = 0
    turns: int = 0
    n_tool_calls: int = 0
    submitted: bool = False
    submitted_support: list | None = None
    submitted_sharpe: float | None = None
    prior_pick: dict | None = None
    prediction: dict | None = None
    triggers_changed: bool = False
    triggers_predeclared: list = field(default_factory=list)
    certifying_null_computable: bool | None = None
    verdict: dict | None = None
    no_submit: bool = False
    credential: str = "unknown"
    # where the run executed (experiments.code_state.platform_info), from 2026-10-02
    platform: dict | None = None
    # Which endpoint answered, and whether the model it served is the pinned one.
    # §3's exclusion rule ("a run whose usage log reports any other string is
    # excluded from analysis and noted") rests on the model STRING; until
    # 2026-09-27 nothing recorded where that string came from, so a run served by
    # a different endpoint that happened to report the right name was
    # indistinguishable from one served by the pinned model.
    endpoint: dict | None = None
    usd: float | None = None
    usage: dict | None = None
    models_seen: list = field(default_factory=list)
    error: str | None = None

    def log(self, kind: str, **fields) -> None:
        self.events.append({"t": time.time(), "kind": kind, **fields})

    def note_refusal(self, tool: str, message: str) -> str:
        kind = classify_refusal(message)
        self.refusals.append({"tool": tool, "kind": kind, "message": message})
        self.log("refusal", tool=tool, refusal_kind=kind, message=message)
        return kind

    @property
    def engagement(self) -> float:
        """Accepted moves as a share of tool calls, the definition
        `fixed-sequence-replay` uses for its searchers."""
        accepted = sum(self.moves.values())
        return accepted / self.n_tool_calls if self.n_tool_calls else 0.0

    def to_json(self) -> dict:
        d = dict(self.__dict__)
        d["engagement"] = self.engagement
        d["unregistered_refusals"] = [r for r in self.refusals if r["kind"] == "UNREGISTERED"]
        return d


# -- the tool surfaces -------------------------------------------------------

def _spec_from(features, signs, K: int, name: str) -> Specification:
    w = np.zeros(K)
    feats = [int(f) for f in features]
    sgn = [int(s) for s in signs] if signs else [1] * len(feats)
    if len(sgn) != len(feats):
        raise ValueError("features and signs must have the same length")
    if len(set(feats)) != len(feats):
        raise ValueError("a feature may appear at most once")
    for f, s in zip(feats, sgn):
        if not 0 <= f < K:
            raise ValueError(f"feature {f} is outside 0..{K - 1}")
        if s not in (1, -1):
            raise ValueError("signs are +1 or -1")
        w[f] = float(s)
    return Specification(weights=w, name=name)


def control_tools(sandbox: RealSandbox, rec: RunRecord, K: int, on_evaluate=None):
    """`evaluate` and `submit`: the surface `searchers/llm_agent.py` uses.

    `on_evaluate`, if given, is called at the start of every `evaluate` call, refused
    or not: the prior-weighted arm uses it to close the short list at the first
    evaluation the agent asks for."""
    from claude_agent_sdk import tool

    @tool("evaluate", "In-sample Sharpe, net of costs, of an equal-weight signed "
                      "feature combination.", {"features": list[int], "signs": list[int]})
    async def evaluate(args):
        rec.n_tool_calls += 1
        if on_evaluate is not None:
            on_evaluate()
        try:
            spec = _spec_from(args.get("features", []), args.get("signs", []), K,
                              f"{rec.run_id}_{rec.n_tool_calls}")
            res = sandbox.evaluate(spec)
        except ValueError as e:
            rec.note_refusal("evaluate", str(e))
            return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
        rec.moves["evaluate"] = rec.moves.get("evaluate", 0) + 1
        text = f"Sharpe {res.sharpe:.3f}, n={res.n_periods}."
        rec.log("tool_result", tool="evaluate", args=args, sharpe=res.sharpe)
        return {"content": [{"type": "text", "text": text}]}

    @tool("submit", "Submit one specification with your predicted out-of-sample Sharpe.",
          {"features": list[int], "signs": list[int], "mean": float, "sd": float})
    async def submit(args):
        rec.n_tool_calls += 1
        if rec.submitted:
            rec.note_refusal("submit", "this session has submitted")
            return {"content": [{"type": "text", "text": "Already submitted."}]}
        try:
            spec = _spec_from(args.get("features", []), args.get("signs", []), K,
                              f"{rec.run_id}_submission")
            mean, sd = float(args["mean"]), float(args.get("sd", 0.0))
        except (ValueError, KeyError, TypeError) as e:
            rec.note_refusal("submit", str(e))
            return {"content": [{"type": "text", "text": f"Rejected: {e}"}]}
        sandbox.submit(spec, Distribution.degenerate(mean) if sd == 0 else
                       Distribution(mean=mean, std=sd))
        rec.submitted = True
        rec.submitted_support = [[int(k), float(spec.weights[k])]
                                 for k in np.nonzero(spec.weights)[0]]
        rec.prediction = {"mean": mean, "sd": sd}
        rec.moves["submit"] = rec.moves.get("submit", 0) + 1
        rec.log("submit", support=rec.submitted_support, mean=mean, sd=sd)
        return {"content": [{"type": "text", "text": "Submitted."}]}

    return [evaluate, submit]


SHORT_LIST_CAP = 5        # prereg/prior-weighted-alpha.md; prereg/planted-edge.md


def prior_weighted_tools(sandbox: RealSandbox, rec: RunRecord, K: int, cls,
                         cap: int = SHORT_LIST_CAP):
    """`short_list`, `evaluate`, `submit`: the prior-weighted arm's registered surface.

    `short_list` may be called **once, before any `evaluate`**, naming up to `cap`
    specifications in the declared class. A second call, a call after any `evaluate`
    (even a refused one), a list over the cap, or a member outside the class is
    refused and logged. The accepted list is written to the run as a `short_list`
    event; `experiments/price_runs.py` prices it.
    """
    from claude_agent_sdk import tool

    state = {"evaluated": False, "declared": False}

    def _closed():
        state["evaluated"] = True

    @tool("short_list", "Before any evaluate call, name up to "
                        f"{cap} specifications you believe in for reasons that do "
                        "not depend on this data.",
          {"supports": list})
    async def short_list(args):
        rec.n_tool_calls += 1
        why = None
        if state["declared"]:
            why = "a short list has already been declared; it is fixed for the session"
        elif state["evaluated"]:
            why = "a short list named after an evaluate call is refused"
        supports = args.get("supports") or []
        specs = []
        if why is None:
            if not 1 <= len(supports) <= cap:
                why = f"a short list names 1 to {cap} specifications, not {len(supports)}"
            else:
                try:
                    for j, sp in enumerate(supports):
                        spec = _spec_from(sp.get("features", []), sp.get("signs", []),
                                          K, f"{rec.run_id}_list_{j}")
                        if not cls.contains(spec.weights):
                            raise ValueError(f"specification {j} is outside the declared class")
                        specs.append([[int(k), float(spec.weights[k])]
                                      for k in np.nonzero(spec.weights)[0]])
                except (ValueError, AttributeError, TypeError) as e:
                    why = str(e)
        if why is not None:
            rec.note_refusal("short_list", why)
            return {"content": [{"type": "text", "text": f"Rejected: {why}"}]}
        state["declared"] = True
        rec.moves["short_list"] = rec.moves.get("short_list", 0) + 1
        rec.log("short_list", supports=specs, cap=cap, before_first_evaluate=True)
        return {"content": [{"type": "text",
                             "text": f"Short list of {len(specs)} recorded."}]}

    evaluate, submit = control_tools(sandbox, rec, K, on_evaluate=_closed)
    return [short_list, evaluate, submit]


def replay_tools(tools: ToolSession, rec: RunRecord, K: int):
    """The quixote grammar. Every move is named, the harness performs it, and a
    refusal is returned to the agent rather than raised at it."""
    from claude_agent_sdk import tool

    def _call(name: str, **kw):
        rec.n_tool_calls += 1
        try:
            res = tools.call(name, **kw)
        except ToolRefused as e:
            rec.note_refusal(name, str(e))
            return {"content": [{"type": "text", "text": f"Refused: {e}"}]}
        except ValueError as e:                   # the session's own refusals
            rec.note_refusal(name, str(e))
            return {"content": [{"type": "text", "text": f"Refused: {e}"}]}
        if res.ok:
            rec.moves[name] = rec.moves.get(name, 0) + 1
        rec.log("tool_result", tool=name, args=kw, text=res.text, ok=res.ok,
                **{k: v for k, v in res.state.items() if k != "support"})
        return {"content": [{"type": "text", "text": res.text}]}

    def _simple(name, description):
        @tool(name, description, {})
        async def fn(args, _n=name):
            return _call(_n)
        return fn

    made = [_simple("init", "Anchor on the best single feature."),
            _simple("extend_best", "Add the feature that most improves what you hold."),
            _simple("swap_worst", "Replace the weakest held feature with the best available."),
            _simple("refine", "Re-fit the signs of what you hold.")]

    @tool("flip", "Reverse the sign of one feature you hold.", {"feature": int})
    async def flip(args):
        return _call("flip", feature=int(args["feature"]))

    @tool("pick", "Choose among candidates you name, by a statistic you name.",
          {"among": list[int], "statistic": str, "choice": int})
    async def pick(args):
        kw = {"among": args.get("among", []),
              "statistic": args.get("statistic", "sharpe")}
        if args.get("choice") is not None:
            kw["choice"] = int(args["choice"])
        out = _call("pick", **kw)
        recs = tools.session.log.records
        if recs and recs[-1].move.kind == "pick":
            if recs[-1].replayable:
                rec.picks_accepted += 1
            else:
                rec.picks_contradicted += 1
        return out

    @tool("stop", "End the search, naming a declared trigger that fires.",
          {"trigger": str, "param": float})
    async def stop(args):
        name, param = str(args.get("trigger", "")), float(args.get("param", 0.0))
        rec.triggers_declared[name] = rec.triggers_declared.get(name, 0) + 1
        out = _call("stop", trigger=name, param=param)
        if rec.moves.get("stop"):
            rec.triggers_fired[name] = rec.triggers_fired.get(name, 0) + 1
        return out

    @tool("restart", "Abandon the current support for the next anchor, on a "
                     "declared trigger.", {"trigger": str, "param": float})
    async def restart(args):
        name, param = str(args.get("trigger", "")), float(args.get("param", 0.0))
        rec.triggers_declared[name] = rec.triggers_declared.get(name, 0) + 1
        out = _call("restart", trigger=name, param=param)
        if rec.moves.get("restart"):
            rec.triggers_fired[name] = rec.triggers_fired.get(name, 0) + 1
        return out

    @tool("declare_triggers", "Fix the stopping rules you will search under, before "
                              "your first move.", {"triggers": list})
    async def declare_triggers(args):
        return _call("declare_triggers", triggers=args.get("triggers", []))

    @tool("change_trigger", "Change a declared stopping rule. Logged, and the rest "
                            "of the run is priced as not replayable.",
          {"trigger": str, "param": float, "action": str, "reason": str})
    async def change_trigger(args):
        out = _call("change_trigger", trigger=str(args.get("trigger", "")),
                    param=float(args.get("param", 0.0)),
                    action=str(args.get("action", "stop")),
                    reason=str(args.get("reason", "")))
        rec.triggers_changed = bool(tools.session.log.trigger_changes)
        return out

    @tool("pick_prior", "Name one specification before your first move, with your "
                        "reason.", {"features": list[int], "signs": list[int], "reason": str})
    async def pick_prior(args):
        support = [[int(f), float(s)] for f, s in
                   zip(args.get("features", []), args.get("signs", []) or
                       [1] * len(args.get("features", [])))]
        out = _call("pick_prior", support=support, reason=str(args.get("reason", "")))
        if tools.session.log.prior_pick:
            rec.prior_pick = {"support": support, "reason": args.get("reason", "")}
        return out

    @tool("predict", "State the out-of-sample Sharpe you expect.",
          {"mean": float, "sd": float, "note": str})
    async def predict(args):
        out = _call("predict", mean=float(args.get("mean", 0.0)),
                    sd=float(args.get("sd", 0.0)), note=str(args.get("note", "")))
        rec.prediction = {"mean": args.get("mean"), "sd": args.get("sd")}
        return out

    @tool("submit", "End the run; the best support you reached is submitted.", {})
    async def submit(args):
        out = _call("submit")
        if tools.submitted:
            support, score = tools.session.submission()
            rec.submitted = True
            rec.submitted_support = [[int(k), float(s)] for k, s in support]
            rec.submitted_sharpe = float(score)
        return out

    return made + [declare_triggers, change_trigger, flip, pick, stop,
                   restart, pick_prior, predict, submit]


# -- one run -----------------------------------------------------------------


CERTIFY_B = 200


def _certify_run(rec: RunRecord, tools: ToolSession, sandbox, cls, table=None) -> None:
    """The in-line path: price the live session's log as the run closes."""
    certify_log(rec, tools.session.log, sandbox, cls, table)


def certify_log(rec: RunRecord, log, sandbox, cls, table=None,
                B: int | None = None) -> None:
    """Can trigger replay be computed from this run's log at all?

    Takes the LOG, not the live session, so `experiments/price_runs.py` prices a
    run rebuilt from its committed file through this same function. One function
    is what makes deferred pricing and in-line pricing the same computation rather
    than two copies that are hoped to agree.

    **What it prices on this panel, stated rather than assumed.** `certify` works
    from `base_feature_columns`, which `environments/real_sandbox.py` documents as
    a **diagnostic** basis and not one the class is linear in: costs are not
    linear in the weights, so the replayed statistic is not the net statistic the
    search actually optimised. The verdict below is therefore a **specimen of the
    machinery**, not a certification of this run, and says so in its own reasons.
    """
    from quixote.certify import certify
    base = sandbox.base_feature_columns()
    ann = float(np.sqrt(sandbox.periods_per_year))
    try:
        v = certify(log, cls, base, ann, alpha=0.05,
                    B=CERTIFY_B if B is None else int(B),
                    seed=rec.seed, table=table)
    except Exception as e:
        rec.certifying_null_computable = False
        rec.log("certify_error", error=f"{type(e).__name__}: {e}")
        return
    rec.certifying_null_computable = True
    rec.verdict = {"status": v.status, "alpha": v.alpha, "p_certifying": v.p_certifying,
                   "p_frozen": v.p_frozen, "p_policy": v.p_policy,
                   "realized_score": v.realized_score, "n_moves": v.n_moves,
                   "n_candidates": v.n_candidates, "fill_engaged": v.fill_engaged,
                   "handover_replicates": v.handover_replicates,
                   "handover_share": v.handover_share,
                   "fill_replicates": v.fill_replicates,
                   "unreplayable_decisions": list(v.unreplayable_decisions),
                   "certifying_null": v.certifying_null,
                   "B": CERTIFY_B if B is None else int(B),
                   "confidence": v.confidence_replay,
                   "reasons": list(v.reasons),
                   "basis": ("class table (stored net streams)" if table is not None
                             else "base_feature_columns (DIAGNOSTIC on this panel)"),
                   "basis_caveat": (
                       "Priced from the class table: evaluate() and every replicate read "
                       "the same stored net streams, so the null prices the statistic the "
                       "search optimised. B is small because this asks whether the null "
                       "is computable end to end, not what its p-value is; rule 5 forbids "
                       "the number entering anything."
                       if table is not None else
                       "Computed from base_feature_columns, a DIAGNOSTIC basis on this "
                       "panel: costs are not linear in the weights, so this prices a "
                       "different statistic from the net one the search optimised. A "
                       "specimen of the machinery, not a certification of this run.")}
    rec.log("verdict", **{k: v for k, v in rec.verdict.items() if k != "reasons"})


def _served_model_assertion(rec: RunRecord) -> dict:
    """Which endpoint answered, and whether it served the pinned model.

    `prereg/AGENT_PROMPTS_REAL.md` §3 pins the model string and excludes a run
    that reports any other, and every run checks that string. What nothing
    recorded until 2026-09-27 is **where the string came from**: a run served by
    some other endpoint that reported the pinned name would have passed the check
    and been indistinguishable from a genuine one.

    So the endpoint is recorded and the assertion is made explicit:

    - `base_url` — whatever `ANTHROPIC_BASE_URL` names, or `"default"` when it is
      unset, which is the public API;
    - `auth` — which credential variable was present, by NAME only. **No key, no
      prefix and no length is recorded**, on the same rule the ADR key is handled
      under: read it, never write it anywhere;
    - `models_reported` — the distinct model strings the assistant messages
      carried;
    - `served_is_pinned` — whether that set is exactly the pinned model, which is
      the assertion §3's exclusion rule actually needs;
    - `agrees_with_prereg` — the two conditions together.

    A run where `served_is_pinned` is false is excluded from analysis and noted,
    which is §3's rule unchanged; what is new is that the reason is now visible.
    """
    import os

    base = os.environ.get("ANTHROPIC_BASE_URL") or "default"
    auth = [name for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                              "CLAUDE_CODE_OAUTH_TOKEN")
            if os.environ.get(name)]
    reported = sorted(rec.models_seen)
    served_is_pinned = reported == [MODEL]
    # "no model was called" is not the same fact as "a different model answered",
    # and a dry run is the first case. Both fail the assertion; only the second is
    # a run §3 excludes from analysis.
    status = ("ok" if served_is_pinned else
              "no model called" if not reported else "mismatch")
    return {"base_url": base,
            "auth": auth,                       # names only, never values
            "models_reported": reported,
            "pinned_model": MODEL,
            "served_is_pinned": served_is_pinned,
            "status": status,
            "agrees_with_prereg": bool(served_is_pinned and reported),
            "note": ("§3 excludes a run whose usage log reports any other model "
                     "string; this field records which endpoint the string came "
                     "from, which the check alone did not.")}


def _drive_model(arm, rec, handlers, panel, sandbox, K, prompt: str | None = None,
                 depth: int | None = None) -> None:
    """One model-backed run. Everything pinned is read from the
    pre-registration; nothing about the arm is decided here.

    `prompt` lets a caller supply a prompt it has already built -- the orientation
    arm's carries a rendered table, which only the caller can produce. Left None
    the prompt is built here exactly as before, so `agent_pilot.py` is unchanged.
    """
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                                  ResultMessage, TextBlock, ToolUseBlock,
                                  create_sdk_mcp_server)

    if prompt is None:
        prompt = system_prompt_for(arm, sandbox.num_assets, K,
                                   D if depth is None else depth, read_prompts())
    rec.log("system_prompt", sha=__import__("hashlib").sha256(prompt.encode()).hexdigest()[:16],
            chars=len(prompt))
    server = create_sdk_mcp_server(name=SERVER_NAME, version="1.0.0", tools=handlers)
    allowed = [f"mcp__{SERVER_NAME}__{h.name}" for h in handlers]

    async def go():
        import tempfile
        with tempfile.TemporaryDirectory(prefix="garden_pilot_") as tmp:
            opts = ClaudeAgentOptions(
                model=MODEL, system_prompt=prompt, tools=[], setting_sources=[],
                thinking={"type": "disabled"},
                mcp_servers={SERVER_NAME: server}, allowed_tools=allowed,
                max_turns=MAX_TURNS, cwd=tmp)
            async with ClaudeSDKClient(options=opts) as client:
                await client.query("Begin.")
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        rec.turns += 1
                        if getattr(msg, "model", None):
                            if msg.model not in rec.models_seen:
                                rec.models_seen.append(msg.model)
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                rec.log("assistant_text", text=block.text)
                            elif isinstance(block, ToolUseBlock):
                                rec.log("tool_use", tool=block.name, input=block.input)
                    elif isinstance(msg, ResultMessage):
                        rec.usd = getattr(msg, "total_cost_usd", None)
                        rec.usage = dict(getattr(msg, "usage", {}) or {})
                        if getattr(msg, "is_error", False):
                            detail = str(getattr(msg, "subtype", "error"))
                            # A run that reaches max_turns without submitting is
                            # `no_submit`: a recorded OUTCOME kept in the run
                            # count, exactly as the synthetic harness records it
                            # (AGENT_PROMPTS.md section 3), not an error. Under
                            # decision (b) a `trigger_is_firing` refusal consumes
                            # a turn by design, so the turn budget is spent on
                            # the harness holding the agent to its own rule.
                            if "max_turns" in detail:
                                rec.no_submit = True
                                rec.log("no_submit", detail=detail)
                            else:
                                rec.error = detail
                                rec.log("result_error", detail=detail)

    try:
        asyncio.run(go())
    except Exception as e:                        # a failed run is reported, not hidden
        rec.error = f"{type(e).__name__}: {e}"
        rec.log("run_error", error=rec.error)


# -- the report --------------------------------------------------------------


def _num(x) -> str:
    """An UNDECIDABLE verdict prices nothing, so its p-values are absent rather
    than zero, and the report must say absent."""
    return "not priced" if x is None else f"{x:.4f}"
