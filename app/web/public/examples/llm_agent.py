"""An LLM agent adapter: a model names moves through tool calls; the harness runs them.

The Anthropic SDK is an optional dependency (`pip install -e .[agent]`) and the API key is
read from the environment (`ANTHROPIC_API_KEY`); nothing here stores or prints it. The model is
`QUIXOTE_MODEL` if set, else `claude-sonnet-5`.

    export ANTHROPIC_API_KEY=...
    quixote run --agent examples.llm_agent:Agent --panel examples/data/tiny_panel.npz \\
        --class examples/class.json --out my_session.json
    quixote audit my_session.json --panel examples/data/tiny_panel.npz --class examples/class.json

Each turn the model sees the harness's last result and must answer with exactly one tool call;
this adapter returns that call as the move. It never sees a return series, a p-value or the
class's bar: only what the harness shows.
"""
from __future__ import annotations

import json
import os

SYSTEM = (
    "You search for a trading rule on a panel of assets. A rule is an equal-weight combination of "
    "up to the class's maximum number of the panel's features, each long or short. You do not build "
    "rules: you name a move and the harness performs it and reports what happened. Before your first "
    "evaluation, declare the stopping rule you will search under (declare_triggers). Stop only when a "
    "declared rule fires. Finish with predict (the out-of-sample Sharpe you expect, mean and sd) and "
    "submit. Call exactly one tool per turn.")

_NUM = {"type": "number"}
SCHEMAS = {
    "declare_triggers": {"triggers": {"type": "array", "items": {"type": "object", "properties": {
        "trigger": {"type": "string", "enum": ["best_so_far_above", "failures_at_least", "last_gain_at_most"]},
        "param": _NUM, "action": {"type": "string", "enum": ["stop", "restart"]}},
        "required": ["trigger", "param"]}}},
    "init": {}, "extend_best": {}, "swap_worst": {}, "refine": {},
    "flip": {"feature": {"type": "integer"}},
    "stop": {"trigger": {"type": "string"}, "param": _NUM},
    "restart": {"trigger": {"type": "string"}, "param": _NUM},
    "predict": {"mean": _NUM, "sd": _NUM, "note": {"type": "string"}},
    "submit": {},
}


class Agent:
    """`next_move(view) -> dict` (the adapter interface), backed by a model."""

    def __init__(self, model: str | None = None, max_tokens: int = 512):
        try:
            import anthropic                                   # optional dependency
        except ImportError:
            raise RuntimeError("examples.llm_agent needs the Anthropic SDK: pip install -e .[agent]") from None
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("set ANTHROPIC_API_KEY in the environment to run the LLM agent")
        self.client = anthropic.Anthropic()                    # reads the key from the environment
        self.model = model or os.environ.get("QUIXOTE_MODEL", "claude-sonnet-5")
        self.max_tokens = max_tokens
        self.messages: list = []
        self.pending: str | None = None
        self.tools = [{"name": n, "description": f"the harness's `{n}` move",
                       "input_schema": {"type": "object", "properties": p,
                                        "required": [k for k in p if k != "note"]}}
                      for n, p in SCHEMAS.items()]

    def _observe(self, view) -> str:
        return json.dumps({"step": view.step, "features": view.feature_names, "class": view.class_name,
                           "last": view.last, "support": view.support, "best": view.best,
                           "info": view.info, "max_moves": view.max_moves})

    def next_move(self, view) -> dict:
        obs = self._observe(view)
        if self.pending is None:
            self.messages.append({"role": "user", "content": obs})
        else:                                                   # the harness's answer to the last call
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": self.pending, "content": obs}]})
        resp = self.client.messages.create(model=self.model, max_tokens=self.max_tokens, system=SYSTEM,
                                           tools=self.tools, tool_choice={"type": "any"},
                                           messages=self.messages)
        call = next(b for b in resp.content if getattr(b, "type", "") == "tool_use")
        self.messages.append({"role": "assistant", "content": resp.content})
        self.pending = call.id
        return {"tool": call.name, **dict(call.input or {})}
