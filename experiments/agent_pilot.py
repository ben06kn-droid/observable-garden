"""agent-pilot: 5 model-backed runs on the ADR panel, to shake out the harness.

Pre-registered in `prereg/agent-pilot.md`; prompts and tools in
`prereg/AGENT_PROMPTS_REAL.md`, read at runtime by `experiments/real_prompts.py`.

**This module claims no verdict.** It computes no out-of-sample number, touches
no holdout, and its report says so on its first line. What it measures is
engagement and refusals: moves by type, triggers declared against triggers that
fired, picks accepted against picks contradicted, and the cost of a run.

    python -m experiments.agent_pilot --runs 5
    python -m experiments.agent_pilot --dry-run       # scripted policy, no model

`--dry-run` drives the same tool surface with a scripted policy and no model
call. It is how the harness is exercised without spending the seat, and it is
what the milestone test in `tests/test_agent_adapter.py` already covers for the
adapter; here it also covers the panel, the masking and the report.

The two arms differ in surface, which `AGENT_PROMPTS_REAL.md` §2 records as a
confound for search behaviour and not for the certifier:

- **control** — `evaluate` and `submit`, the agent builds its own specification;
- **replay gate** — the quixote grammar through `quixote/agent_adapter.py`, so
  the harness performs every move and the log is what ran.
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

MODEL = "claude-sonnet-5"          # AGENT_PROMPTS_REAL.md §3, pinned
MAX_TURNS = 60
# Each panel's registered class. The ADR panel is signed subsets of size <= 2
# over K = 22 (prereg/adr-features.md section 3); the ETF panel is depth 3 over
# K = 40, 82,240 members (prereg/agent-on-real-data.md). Attempts 1-4 ran the ADR
# panel at depth 3 by mistake; recorded in prereg/agent-pilot.md amendment 4.
DEPTH = {"adr": 2, "etf": 3}
D = DEPTH["adr"]
SEED = 20260924                    # agent-pilot.md: the first 5 draws
SEED_ETF = 20260925                # amendment 7, the ETF pilot's own block
ARM_PLAN = ("control", "control", "replay gate", "replay gate", "replay gate")
SERVER_NAME = "garden_pilot"
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs" / "agent_pilot"

# agent-pilot.md, "What is measured" 2: the registered refusal kinds. A refusal
# outside this set is rule 1's blocking failure, not a data point.
REFUSAL_KINDS = ("unknown_tool", "trigger_did_not_fire", "unknown_trigger",
                 "declaration_after_evaluation", "outside_class", "after_submit",
                 "after_stop",          # amendment 1, found by the dry run
                 "malformed_arguments",  # amendment 2, found by attempt 1
                 "undeclared_trigger",   # amendment 5, the new rule firing
                 "trigger_is_firing")    # amendment 6, decision (b)


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


# -- the panel, masked -------------------------------------------------------

def masked_panel(which: str = "adr"):
    """The ADR panel with its instruments masked per `AGENT_PROMPTS_REAL.md` §4.

    Two of the four allowed fields are populated from `ADR_HOME`, which is the
    committed home-market table; `sector` and `liquidity_band` are **absent, not
    null**, because this panel does not carry them, which §4 permits explicitly.

    Masking is close to vacuous on this panel and amendment 1 of
    `AGENT_PROMPTS_REAL.md` says why: no tool here exposes an asset label or a
    date at all. It is applied anyway, so the agent-facing metadata and the
    grading map are the same objects they will be on a panel where it bites.
    """
    if which == "etf":
        # In-sample export only: the holdout is not opened by a pilot
        # (amendment 7). ETF tickers are maskable but carry no home market, so
        # only the two fields that apply cross (AGENT_PROMPTS_REAL.md section 4:
        # a field that does not apply is absent, not null).
        from environments.real_panel import build_etf_panel
        panel = build_etf_panel()
        masking = Masking.build(list(panel.assets), {}, seed=SEED_ETF)
        table = build_class_table(panel, SubsetClass(max_size=DEPTH["etf"], signed=True),
                                  "etf")
        return panel, masking, table
    panel = build_adr_panel()
    meta = {}
    for ticker in panel.assets:
        if ticker in ADR_HOME:
            _, tzname, (hh, mm), _ = ADR_HOME[ticker]
            meta[ticker] = {"has_home_market": True,
                            "home_close_et": f"{hh:02d}:{mm:02d} {tzname}"}
    masking = Masking.build(list(panel.assets), meta, seed=SEED)
    # The declared class as stored net streams. `evaluate` becomes a lookup and
    # the replay resamples rows of the same table, so the null prices the
    # statistic the search optimised (`environments/class_table.py`). Built once
    # and cached; the manifest carries the panel hash.
    table = build_class_table(panel, SubsetClass(max_size=D, signed=True), "adr")
    return panel, masking, table


# -- what a run records ------------------------------------------------------

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


def control_tools(sandbox: RealSandbox, rec: RunRecord, K: int):
    """`evaluate` and `submit`: the surface `searchers/llm_agent.py` uses."""
    from claude_agent_sdk import tool

    @tool("evaluate", "In-sample Sharpe, net of costs, of an equal-weight signed "
                      "feature combination.", {"features": list[int], "signs": list[int]})
    async def evaluate(args):
        rec.n_tool_calls += 1
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

def _scripted_control(rec, handlers):
    """`--dry-run`'s control policy: three evaluations and a submission."""
    ev, sub = handlers[0], handlers[1]
    for feats in ([0], [0, 2], [0, 2, 4]):
        asyncio.run(ev.handler({"features": feats, "signs": [1] * len(feats)}))
    asyncio.run(sub.handler({"features": [0, 2], "signs": [1, -1], "mean": 0.5, "sd": 0.5}))


def _scripted_replay(rec, handlers):
    """`--dry-run`'s replay policy: a prior, an anchor, two extensions, a stop
    that does not fire, a stop that does, and a submission. It deliberately
    exercises a refusal."""
    by = {h.name: h for h in handlers}
    asyncio.run(by["declare_triggers"].handler(
        {"triggers": [{"trigger": "best_so_far_above", "param": -99.0,
                       "action": "stop"}]}))
    asyncio.run(by["pick_prior"].handler({"features": [1], "signs": [1],
                                          "reason": "dry run"}))
    asyncio.run(by["init"].handler({}))
    asyncio.run(by["extend_best"].handler({}))
    asyncio.run(by["stop"].handler({"trigger": "best_so_far_above", "param": 1e9}))
    asyncio.run(by["stop"].handler({"trigger": "best_so_far_above", "param": -99.0}))
    asyncio.run(by["submit"].handler({}))


def run_one(arm: str, seed: int, panel, masking, index: int,
            dry_run: bool = False, table=None, panel_name: str = "adr") -> RunRecord:
    cls = SubsetClass(max_size=DEPTH[panel_name], signed=True)
    sandbox = RealSandbox(panel, spec_class=cls, class_table=table)
    K = sandbox.num_features
    rec = RunRecord(run_id=f"pilot_{panel_name}_{index}_{arm.replace(' ', '_')}_{seed}",
                    arm=arm, seed=seed)
    rec.log("start", arm=arm, seed=seed, K=K, M=sandbox.num_assets,
            T=sandbox.num_periods, masked_labels=sorted(masking.labels.values()))

    if arm == "control":
        handlers = control_tools(sandbox, rec, K)
        tools = None
    else:
        session = Session.on_sandbox(sandbox, cls, name_prefix=rec.run_id)
        tools = ToolSession(session)
        handlers = replay_tools(tools, rec, K)

    if dry_run:
        (_scripted_control if arm == "control" else _scripted_replay)(rec, handlers)
    else:
        _drive_model(arm, rec, handlers, panel, sandbox, K)

    if tools is not None:
        rec.triggers_predeclared = [dict(t) for t in tools.session.log.declared_trigger_records]
        rec.triggers_changed = bool(tools.session.log.trigger_changes)
        _certify_run(rec, tools, sandbox, cls, table)
        rec.log("session_log", records=[
            {"step": r.step, "kind": r.move.kind, "support": list(r.support_after),
             "score": r.score_after, "n_candidates": r.n_candidates,
             "trigger": r.trigger, "trigger_value": r.trigger_value,
             "replayable": r.replayable} for r in tools.session.log.records])
        if not rec.submitted:
            support, score = tools.session.submission()
            rec.submitted_support = [[int(k), float(s)] for k, s in support]
            rec.submitted_sharpe = float(score)
    elif rec.submitted and sandbox.submission is not None:
        rec.submitted_sharpe = float(max((e.sharpe for e in sandbox.transcript),
                                         default=float("nan")))
    rec.log("end", submitted=rec.submitted, engagement=rec.engagement)
    return rec


# agent-pilot.md, "What is measured" 6. B is small on purpose: this asks whether
# the null is COMPUTABLE from an agent's log end to end, not what its p-value is,
# and rule 5 forbids the number entering anything.
CERTIFY_B = 200


def _certify_run(rec: RunRecord, tools: ToolSession, sandbox, cls, table=None) -> None:
    """Can trigger replay be computed from this run's log at all?

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
        v = certify(tools.session.log, cls, base, ann, alpha=0.05, B=CERTIFY_B,
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
                   "fill_replicates": v.fill_replicates,
                   "unreplayable_decisions": list(v.unreplayable_decisions),
                   "certifying_null": v.certifying_null, "B": CERTIFY_B,
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


def _drive_model(arm, rec, handlers, panel, sandbox, K) -> None:
    """One model-backed run. Everything pinned is read from the
    pre-registration; nothing about the arm is decided here."""
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                                  ResultMessage, TextBlock, ToolUseBlock,
                                  create_sdk_mcp_server)

    prompt = system_prompt_for(arm, sandbox.num_assets, K, D, read_prompts())
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
                            rec.error = str(getattr(msg, "subtype", "error"))
                            rec.log("result_error", detail=rec.error)

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


def report(records: list[RunRecord], dry_run: bool) -> str:
    L = ["agent-pilot — HARNESS SHAKE-OUT AND ENGAGEMENT ONLY. NO VERDICT CLAIM.",
         "=" * 78,
         "prereg/agent-pilot.md rule 5: no number here enters a verdict, a headline or",
         "a figure, and any number quoted elsewhere is quoted as a pilot number with",
         f"n = {len(records)} beside it.",
         "" if not dry_run else "*** DRY RUN: scripted policies, no model was called. ***", ""]

    unregistered = [(r.run_id, x) for r in records for x in r.refusals
                    if x["kind"] == "UNREGISTERED"]
    L += ["RULE 1 — harness integrity (the only blocking rule)", "-" * 78]
    if unregistered:
        L.append(f"  FAILS: {len(unregistered)} unregistered refusal(s); each is a defect")
        for run_id, x in unregistered[:10]:
            L.append(f"    {run_id}: [{x['tool']}] {x['message'][:90]}")
    else:
        L.append(f"  holds: every refusal is one of the {len(REFUSAL_KINDS)} registered kinds")
    L.append("")

    L += ["ENGAGEMENT, per run", "-" * 78,
          f"  {'run':<34}{'arm':<13}{'calls':>6}{'moves':>7}{'engag':>8}{'sub':>5}{'$':>8}"]
    for r in records:
        L.append(f"  {r.run_id:<34}{r.arm:<13}{r.n_tool_calls:>6}"
                 f"{sum(r.moves.values()):>7}{r.engagement:>8.2f}"
                 f"{'yes' if r.submitted else 'NO':>5}"
                 f"{(f'{r.usd:.3f}' if r.usd is not None else '-'):>8}")
    L.append("")

    L += ["MOVES BY TYPE", "-" * 78]
    for r in records:
        moves = ", ".join(f"{k} {v}" for k, v in sorted(r.moves.items())) or "none"
        L.append(f"  {r.run_id}: {moves}")
    L += ["", "TRIGGERS: declared vs fired", "-" * 78]
    for r in records:
        if not r.triggers_declared:
            L.append(f"  {r.run_id}: none declared")
            continue
        parts = [f"{k} {r.triggers_fired.get(k, 0)}/{v}"
                 for k, v in sorted(r.triggers_declared.items())]
        L.append(f"  {r.run_id}: " + ", ".join(parts))
    L += ["", "TRIGGERS DECLARED UP FRONT, AND CHANGES", "-" * 78]
    for r in records:
        if r.arm == "control":
            continue
        decl = ", ".join(f"{t['kind']}({t['param']:g})->{t['action']}"
                         for t in r.triggers_predeclared) or "none declared"
        L.append(f"  {r.run_id}: {decl}"
                 + ("   CHANGED (priced as unreplayable)" if r.triggers_changed else ""))
    L += ["", "PICKS: accepted vs contradicted (rejected as declared)", "-" * 78]
    for r in records:
        L.append(f"  {r.run_id}: {r.picks_accepted} accepted, "
                 f"{r.picks_contradicted} contradicted")
    L += ["", "REFUSALS by kind", "-" * 78]
    kinds: dict = {}
    for r in records:
        for x in r.refusals:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    L.append("  " + (", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "none"))

    L += ["", "DECLARATIONS", "-" * 78,
          f"  pick_prior used in {sum(1 for r in records if r.prior_pick)} of "
          f"{sum(1 for r in records if r.arm != 'control')} replay-arm runs",
          "  (AGENT_PROMPTS_REAL.md amendment 1: on the ADR panel a zero here is NOT",
          "   evidence about masking — no tool exposes an asset label or a date)"]

    replay = [r for r in records if r.arm != "control"]
    L += ["", "CERTIFYING NULL — computable from the log, end to end?", "-" * 78]
    for r in replay:
        L.append(f"  {r.run_id}: "
                 + {True: "yes", False: "NO", None: "not attempted"}[r.certifying_null_computable])
    specimen = next((r for r in replay if r.verdict), None)
    if specimen:
        v = specimen.verdict
        L += ["", f"SPECIMEN VERDICT BLOCK — {specimen.run_id}", "-" * 78,
              f"  status            {v['status']}   (alpha {v['alpha']})",
              f"  certifying null   {v['certifying_null']}",
              f"  p_certifying      {_num(v['p_certifying'])}   at B = {v['B']}",
              f"  p_frozen          {_num(v['p_frozen'])}   (fixed-sequence replay, the "
              "bracket's liberal end)",
              f"  p_policy          {_num(v['p_policy'])}",
              f"  realized score    {_num(v['realized_score'])}",
              f"  moves             {v['n_moves']}   candidates {v['n_candidates']}",
              f"  fill engaged      {v['fill_engaged']} of {v['fill_replicates']} replicates",
              f"  unreplayable      {v['unreplayable_decisions'] or 'none'}",
              "  CAVEAT: " + v["basis_caveat"]]
        for reason in v["reasons"]:
            L.append(f"    - {reason}")

    costs = [r.usd for r in records if r.usd is not None]
    if costs:
        L += ["", "COST", "-" * 78,
              f"  mean ${np.mean(costs):.3f} per run against the $0.268 stored mean "
              f"({np.mean(costs) / 0.268:.1f}x), total ${np.sum(costs):.2f}"]
    errs = [(r.run_id, r.error) for r in records if r.error]
    if errs:
        L += ["", "ERRORS", "-" * 78] + [f"  {i}: {e}" for i, e in errs]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--panel", default="adr", choices=("adr", "etf"))
    ap.add_argument("--arms", default="all", choices=("all", "replay", "control"),
                    help="re-run only one arm's runs, keeping their registered seeds")
    ap.add_argument("--out", default=str(RUNS_ROOT))
    a = ap.parse_args(argv)

    global D
    D = DEPTH[a.panel]
    seeds = [int(s) for s in np.random.default_rng(
        SEED_ETF if a.panel == "etf" else SEED).integers(0, 2**31 - 1, size=5)]
    panel, masking, table = masked_panel(a.panel)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    wanted = {"all": set(ARM_PLAN),
              "replay": {"replay gate"}, "control": {"control"}}[a.arms]
    records = []
    for i in range(min(a.runs, len(ARM_PLAN))):
        if ARM_PLAN[i] not in wanted:
            continue
        rec = run_one(ARM_PLAN[i], seeds[i], panel, masking, i, dry_run=a.dry_run,
                      table=table, panel_name=a.panel)
        records.append(rec)
        (out / f"{rec.run_id}.json").write_text(json.dumps(rec.to_json(), indent=1,
                                                          default=str))
        print(f"  run {i} ({rec.arm}) done: {rec.n_tool_calls} calls, "
              f"engagement {rec.engagement:.2f}"
              + (f", ${rec.usd:.3f}" if rec.usd else ""), flush=True)

    text = report(records, a.dry_run)
    print("\n" + text, flush=True)
    tag = (f"_{a.panel}" + ("_dry" if a.dry_run else "")
           + ("" if a.arms == "all" else f"_{a.arms}"))
    (out / f"pilot_report{tag}.txt").write_text(text)
    (out / f"pilot_index{tag}.json").write_text(json.dumps(
        {"seeds": seeds, "arms": list(ARM_PLAN[:a.runs]), "model": MODEL,
         "max_turns": MAX_TURNS, "code_state": code_state(), "arms_run": a.arms,
         "panel": a.panel, "depth": DEPTH[a.panel],
         "class_table": {"path": table.path, "N": table.N, "T": table.T,
                         "panel_hash": table.panel_hash},
         "masked_labels": masking.labels, "dry_run": a.dry_run}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
