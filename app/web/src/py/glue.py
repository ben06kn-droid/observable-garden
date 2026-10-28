"""The Python the gate's Web Worker runs under Pyodide. Nothing here prices anything: it registers
the two stand-ins, reads the search back from its log for drawing, and calls the package's own
`quixote.audit.audit_log`, the function behind `quixote audit`.

- `STANDINS`: which stand-ins were registered. Each registers only when the real package cannot
  be imported, so under Pyodide both go in (arch has no build; scipy is not shipped) and the
  same code on a desktop changes nothing.
- `search_tree(log, panel, class)`: every candidate every logged move scored, rescored through the
  class table (the scorer the audit uses), in the order the harness scored them; a restart's
  candidates are the single features it ranks. Refuses if a kept move does not reproduce the log.
- `run_audit(...)`: the audit, with the progress callback and the first replicates of the null.
"""
import json

import estimator.block_length as _block_length
import estimator.scipy_lite as _scipy_lite

STANDINS = {"arch": _block_length.install_as_arch(), "scipy": _scipy_lite.install_as_scipy()}

import numpy as np  # noqa: E402

from quixote import audit as A  # noqa: E402
from quixote import classes, panel as P  # noqa: E402
from quixote.grammar import Grammar, Move  # noqa: E402
from quixote.run import ReplayMismatch, replay  # noqa: E402

CONTENT = ("init", "extend_best", "swap_worst", "flip", "refine")


def _rule(support, names):
    return " ".join(("+" if s > 0 else "-") + names[int(k)] for k, s in support)


def _support(state_support):
    return tuple((int(k), float(s)) for k, s in state_support)


def search_tree(log_path, panel_path, class_path):
    log = json.loads(open(log_path).read())
    arrays = P.read(panel_path)
    lc = classes.load(class_path, arrays, compute_bar=False)
    try:
        h = replay(log, arrays, lc)
    except ReplayMismatch as e:
        raise A.AuditRefused(f"the log does not re-execute: {e}") from None
    base = h.sandbox.base_feature_columns()
    g = Grammar(lc.spec_class, base, float(np.sqrt(h.panel.periods_per_year)), score_fn=h.table.scorer(None))
    names = [str(x) for x in h.panel.feature_names]
    support, stem, moves = (), 0, []
    for i, c in enumerate(log["calls"]):
        tool, st = c.get("tool"), c.get("state") or {}
        if not c.get("ok"):
            continue
        if tool in CONTENT:
            move = Move(tool, statistic=(c.get("args") or {}).get("statistic", "sharpe"),
                        feature=(c.get("args") or {}).get("feature"))
            cands = g.candidates(() if tool == "init" else support, move)
            best = max(range(len(cands)), key=lambda j: cands[j][0])
            kept = " kept:" in c["text"]
            if kept and (cands[best][1] != _support(st["support"]) or cands[best][0] != st["score"]):
                raise A.AuditRefused(f"call {i} ({tool}) does not rescore to what the log records")
            moves.append({"kind": tool, "stem": stem, "from_ground": tool == "init", "call": i, "text": c["text"],
                          "candidates": [{"rule": _rule(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": best, "kept": kept})
            if kept:
                support = cands[best][1]
        elif tool == "restart":
            stem += 1
            cands = [(g.score(((k, 1.0),)), ((k, 1.0),)) for k in range(len(names))]
            new = _support(st["support"])
            moves.append({"kind": "restart", "stem": stem, "from_ground": True, "call": i, "text": c["text"],
                          "candidates": [{"rule": _rule(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": [ns for _, ns in cands].index(new), "kept": True})
            support = new
    return json.dumps({"feature_names": names, "moves": moves,
                       "evaluations": sum(len(m["candidates"]) for m in moves),
                       "stems": 1 + max((m["stem"] for m in moves), default=0),
                       "panel_shape": [int(x) for x in arrays["returns"].shape] + [int(arrays["features"].shape[2])]})


def run_audit(log_path, panel_path, class_path, B, seed, replicate_paths, progress):
    """The package's audit. Returns {"result": AuditResult.to_dict()} or {"refused": message}."""
    try:
        r = A.audit_log(log_path, panel_path, class_path, B=int(B), seed=int(seed),
                        progress=(lambda stage, done, total: progress(stage, int(done), int(total))),
                        replicate_paths=int(replicate_paths))
    except A.AuditRefused as e:
        return json.dumps({"refused": str(e)})
    d = r.to_dict()
    paths = d.pop("replicate_paths", None)
    if paths is not None:
        names = None
        try:
            names = [str(x) for x in P.read(panel_path)["feature_names"]]
        except Exception:
            pass
        for p in paths:
            for s in p["steps"]:
                if names:
                    s["rule"] = _rule(s["support"], names)
    return json.dumps({"result": d, "replicate_paths": paths})


# ---- the full run (phase 4): the visitor's model as the agent, in the browser ---------------------
#
# `inspect_inputs(panel, class)` reads both with the package's own loaders (np.load with
# allow_pickle=False inside quixote.panel.read) before any key is used, and returns what the page
# shows: the class's description, its kind and size, the panel's shape, and the class table's
# memory (members x rows x 8 bytes, the float64 streams `classes.table_for` builds). A package error
# comes back as {"error": its message}, word for word.
#
# `run_agent(...)` drives `quixote.run.run_session`, the function behind `quixote run`, with an
# agent whose next_move asks the model. The model is reached through `call_model(body) -> reply`, a
# JavaScript function the worker passes in (a synchronous request to the provider, made in the
# worker; the key never enters Python). The prompt and the tool schemas are the ones
# examples/llm_agent.py uses (its file is served as a checked copy and executed here for SYSTEM and
# SCHEMAS); the request differs from that adapter only where the current models require it:
# tool_choice "auto" with one tool call per turn (forced tool use is refused by Claude Opus 5.5 and
# Sonnet 5.5), a max_tokens with room for the model's thinking, and the thinking blocks passed back
# unchanged. Other providers get the same prompt and tools translated into their request shape
# (`SHAPES`, below: `opts["provider"]` picks one). The log `run_session` writes is the CLI's
# quixote-log/1 whichever provider ran, so `quixote audit` reads it unchanged.


def inspect_inputs(panel_path, class_path):
    try:
        arrays = P.read(panel_path)
        lc = classes.load(class_path, arrays, compute_bar=False)
    except (P.PanelError, classes.ClassError, ValueError, OSError) as e:
        return json.dumps({"error": str(e)})
    T, M = (int(x) for x in arrays["returns"].shape)
    K = int(arrays["features"].shape[2])
    out = {"kind": lc.kind, "size": int(lc.size), "rows": T, "assets": M, "features": K,
           "class_name": lc.spec_class.name if lc.spec_class is not None else "",
           "describe": lc.describe(), "panel_sha256": P.sha256(panel_path), "class_sha256": lc.sha256,
           "table_bytes": int(lc.size) * T * 8}
    if lc.kind != "subsets":
        out["error"] = ("the harness searches a subsets class; a streams class is audited as a transcript "
                        "(garden audit)")
    return json.dumps(out)


class StopRun(Exception):
    """The model's provider refused or failed: the run ends, with no result."""


def _agent_module(path):
    ns = {"__name__": "examples_llm_agent"}
    exec(compile(open(path).read(), path, "exec"), ns)
    return ns


def agent_prompt(agent_path):
    """The CLI adapter's system prompt and tool schemas, for the page to show."""
    ns = _agent_module(agent_path)
    return json.dumps({"system": ns["SYSTEM"], "schemas": ns["SCHEMAS"]})


# ---- the request shapes: one adapter per shape a provider speaks ------------------------------------
#
# Each shape builds the next request from the observation (`request(obs) -> body`) and reads the reply
# (`read(reply) -> turn`): the usage, the model that served it, and at most one tool call. The model's
# own turn goes back into the history unchanged (thinking blocks, reasoning items and reasoning
# details included), less any tool call after the first: the harness takes one move per turn.
#   anthropic   the Messages API (Anthropic), as examples/llm_agent.py sends it
#   responses   the Responses API (OpenAI: its flagship models take tools only there)
#   chat        chat completions (OpenRouter, and a local OpenAI-compatible server)


def _tool_defs(schemas):
    return [(n, f"the harness's `{n}` move",
             {"type": "object", "properties": p, "required": [k for k in p if k != "note"]})
            for n, p in schemas.items()]


def _declined(detail):
    raise StopRun(f"the model declined to continue{f' ({detail})' if detail else ''}")


def _provider_error(reply):
    """A failure inside a 200 reply (OpenRouter reports an upstream failure this way), word for word."""
    e = reply.get("error")
    if e:
        msg = e.get("message") if isinstance(e, dict) else str(e)
        raise StopRun(f"The provider reported an error: {msg}")


def _args(raw):
    try:
        a = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}                 # not JSON: the harness refuses the move for its missing arguments
    return a if isinstance(a, dict) else {}


class AnthropicShape:
    def __init__(self, system, schemas, opts):
        self.system, self.model, self.effort = system, opts["model"], opts.get("effort")
        self.max_tokens = int(opts.get("max_tokens", 16000))
        self.fallbacks = bool(opts.get("fallbacks", True))
        self.tools = [{"name": n, "description": d, "input_schema": s} for n, d, s in _tool_defs(schemas)]
        self.messages, self.pending = [], None

    def request(self, obs):
        if self.pending is None:
            self.messages.append({"role": "user", "content": obs})
        else:                     # the harness's answer to the last call
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": self.pending, "content": obs}]})
        body = {"model": self.model, "max_tokens": self.max_tokens, "system": self.system, "tools": self.tools,
                "tool_choice": {"type": "auto", "disable_parallel_tool_use": True}, "messages": self.messages}
        if self.effort:
            body["output_config"] = {"effort": self.effort}
        if self.fallbacks:
            body["fallbacks"] = "default"
        return body

    def read(self, reply):
        u = reply.get("usage") or {}
        usage = {k: int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens")}
        if reply.get("stop_reason") == "refusal":
            return {"usage": usage, "refused": (reply.get("stop_details") or {}).get("category")}
        content = reply.get("content") or []
        self.messages.append({"role": "assistant", "content": content})   # thinking blocks included, unchanged
        call = next((b for b in content if b.get("type") == "tool_use"), None)
        self.pending = call["id"] if call else None
        return {"usage": usage, "model": reply.get("model"), "stop_reason": reply.get("stop_reason"),
                "text": " ".join(b.get("text", "") for b in content if b.get("type") == "text").strip(),
                "call": (call["name"], dict(call.get("input") or {})) if call else None}


class ResponsesShape:
    """OpenAI's Responses API, stateless: store false, the reasoning items sent back encrypted."""

    def __init__(self, system, schemas, opts):
        self.system, self.model, self.effort = system, opts["model"], opts.get("effort")
        self.max_tokens = int(opts.get("max_tokens", 16000))
        self.tools = [{"type": "function", "name": n, "description": d, "parameters": s, "strict": False}
                      for n, d, s in _tool_defs(schemas)]
        self.items, self.pending = [], None

    def request(self, obs):
        if self.pending is None:
            self.items.append({"role": "user", "content": obs})
        else:
            self.items.append({"type": "function_call_output", "call_id": self.pending, "output": obs})
        body = {"model": self.model, "instructions": self.system, "input": self.items, "tools": self.tools,
                "tool_choice": "auto", "parallel_tool_calls": False, "max_output_tokens": self.max_tokens,
                "store": False, "include": ["reasoning.encrypted_content"]}
        if self.effort:
            body["reasoning"] = {"effort": self.effort}
        return body

    def read(self, reply):
        _provider_error(reply)
        u = reply.get("usage") or {}
        usage = {"input_tokens": int(u.get("input_tokens") or 0), "output_tokens": int(u.get("output_tokens") or 0),
                 "cache_read_input_tokens": int((u.get("input_tokens_details") or {}).get("cached_tokens") or 0)}
        output = reply.get("output") or []
        parts = [c for o in output if o.get("type") == "message" for c in (o.get("content") or [])]
        refusal = next((c.get("refusal") for c in parts if c.get("type") == "refusal"), None)
        if refusal is not None:
            return {"usage": usage, "refused": str(refusal)[:200]}
        calls = [o for o in output if o.get("type") == "function_call"]
        self.items.extend(o for o in output if o.get("type") != "function_call" or o is calls[0])
        call = calls[0] if calls else None
        self.pending = call["call_id"] if call else None
        reason = reply.get("status")
        if reply.get("incomplete_details"):
            reason = f"{reason}: {reply['incomplete_details'].get('reason')}"
        return {"usage": usage, "model": reply.get("model"), "stop_reason": reason,
                "text": " ".join(c.get("text", "") for c in parts if c.get("type") == "output_text").strip(),
                "call": (call["name"], _args(call.get("arguments"))) if call else None}


class ChatShape:
    """Chat completions. OpenRouter takes tool_choice, parallel_tool_calls and `reasoning`; a local server
    is sent only what Ollama documents (`tools`, `reasoning`), its default tool choice being auto."""

    def __init__(self, system, schemas, opts):
        self.model, self.effort, self.local = opts["model"], opts.get("effort"), opts.get("provider") == "local"
        self.max_tokens = None if self.local else int(opts.get("max_tokens", 16000))
        self.tools = [{"type": "function", "function": {"name": n, "description": d, "parameters": s}}
                      for n, d, s in _tool_defs(schemas)]
        self.messages, self.pending = [{"role": "system", "content": system}], None

    def request(self, obs):
        if self.pending is None:
            self.messages.append({"role": "user", "content": obs})
        else:
            self.messages.append({"role": "tool", "tool_call_id": self.pending, "content": obs})
        body = {"model": self.model, "messages": self.messages, "tools": self.tools}
        if not self.local:
            body.update(tool_choice="auto", parallel_tool_calls=False)
        if self.max_tokens:
            body["max_tokens"] = self.max_tokens
        if self.effort:
            body["reasoning"] = {"effort": self.effort}
        return body

    def read(self, reply):
        _provider_error(reply)
        u = reply.get("usage") or {}
        usage = {"input_tokens": int(u.get("prompt_tokens") or 0), "output_tokens": int(u.get("completion_tokens") or 0),
                 "cache_read_input_tokens": int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)}
        choice = (reply.get("choices") or [{}])[0]
        msg = dict(choice.get("message") or {"role": "assistant", "content": ""})
        if msg.get("refusal"):
            return {"usage": usage, "refused": str(msg["refusal"])[:200]}
        calls = msg.get("tool_calls") or []
        if calls:
            msg["tool_calls"] = calls[:1]
        self.messages.append(msg)                # reasoning details included, unchanged
        call = calls[0] if calls else None
        self.pending = call.get("id") if call else None
        fn = (call or {}).get("function") or {}
        return {"usage": usage, "model": reply.get("model"), "stop_reason": choice.get("finish_reason"),
                "text": (msg.get("content") or "").strip() if isinstance(msg.get("content"), str) else "",
                "call": (fn.get("name"), _args(fn.get("arguments"))) if call else None}


SHAPES = {"anthropic": AnthropicShape, "openai": ResponsesShape, "openrouter": ChatShape, "local": ChatShape}


class ModelAgent:
    """next_move(view) -> dict, backed by the visitor's model (the adapter interface)."""

    def __init__(self, agent_path, opts, call_model, on_event, paths=None):
        ns = _agent_module(agent_path)
        self.paths, self.calls, self.last_move = paths, [], None   # for drawing the tree as it grows
        self.system = opts.get("system") or ns["SYSTEM"]
        self.shape = SHAPES[opts.get("provider", "anthropic")](self.system, ns["SCHEMAS"], opts)
        self.call_model, self.on_event = call_model, on_event
        self.usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "requests": 0}

    def _observe(self, view):     # what examples/llm_agent.py shows the model, field for field
        return json.dumps({"step": view.step, "features": view.feature_names, "class": view.class_name,
                           "last": view.last, "support": view.support, "best": view.best,
                           "info": view.info, "max_moves": view.max_moves})

    def next_move(self, view):
        if view.last is not None:
            self.on_event(json.dumps({"type": "result", "last": view.last}))
            if self.last_move is not None:     # the call as run_session logs it, for the growing tree
                tool, args = self.last_move
                self.calls.append({"tool": tool, "args": args, **view.last})
                if tool in CONTENT + ("restart",) and view.last.get("ok") and self.paths:
                    self._tree()
        body = self.shape.request(self._observe(view))
        reply = json.loads(self.call_model(json.dumps(body)))
        turn = self.shape.read(reply)
        for k, v in turn["usage"].items():
            self.usage[k] += v
        self.usage["requests"] += 1
        if "refused" in turn:
            _declined(turn["refused"])
        self.on_event(json.dumps({"type": "usage", "usage": self.usage, "model": turn.get("model")}))
        if turn["call"] is None:  # no tool named: the harness logs it as a refused move and asks again
            self.last_move = (None, {})
            self.on_event(json.dumps({"type": "move", "tool": None, "args": {}, "text": turn["text"][:400],
                                      "stop_reason": turn.get("stop_reason")}))
            return {}
        name, args = turn["call"]
        self.last_move = (name, args)
        self.on_event(json.dumps({"type": "move", "tool": name, "args": args, "text": turn["text"][:400]}))
        return {"tool": name, **args}


    def _tree(self):
        """The search so far, drawn from a partial log (the header run_session wrote, the calls so far)."""
        out, panel, cls = self.paths
        try:
            head = json.loads(open(out).read())
            head["calls"] = self.calls
            part = out + ".part"
            open(part, "w").write(json.dumps(head))
            self.on_event(json.dumps({"type": "tree", "tree": json.loads(search_tree(part, panel, cls))}))
        except Exception:          # the drawing is decoration on the run; the run never depends on it
            pass


ModelAgent.__module__ = "browser"      # the log's "agent" field: browser.ModelAgent


def run_agent(agent_path, panel_path, class_path, out_path, opts_json, call_model, on_event):
    """The run. Returns {"log": quixote-log, "usage": ...} or {"stopped": message}."""
    from quixote import run as R
    opts = json.loads(opts_json)
    agent = ModelAgent(agent_path, opts, call_model, on_event, (out_path, panel_path, class_path))
    try:
        log = R.run_session(agent, panel_path, class_path, out_path, seed=int(opts.get("seed", 0)),
                            max_moves=int(opts["max_moves"]), echo=lambda *_: None)
    except StopRun as e:
        return json.dumps({"stopped": str(e), "usage": agent.usage})
    return json.dumps({"log": log, "usage": agent.usage})
