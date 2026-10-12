"""Run your own agent through the harness.

**The adapter interface.** An agent is any object with one method:

    class Agent(Protocol):
        def next_move(self, view: View) -> dict: ...

`view` is what the harness shows: the tools, the result of the last call (or the refusal
text), the current and best support, and the session's information set (failures, last gain,
best). The agent returns one tool call, a dict like `{"tool": "extend_best"}` or
`{"tool": "stop", "trigger": "last_gain_at_most", "param": 0.0}`. **The agent names a move;
the harness computes it and logs it.** An agent never hands in its own specification, so the
log cannot disagree with what ran.

The tools are the grammar's (`quixote/agent_adapter.py`): `declare_triggers`,
`declare_budget`, `pick_prior`, `short_list` (declarations, only before the first
evaluation), `init`, `extend_best`, `swap_worst`, `flip`, `refine`, `pick` (content moves),
`stop` and `restart` (only on a declared trigger that fires), `change_trigger`, `predict`
and `submit`. A refused call is not an error: its text comes back in `view.last` and the
run continues.

`run_session` hashes the panel and the class files and writes both hashes into the log
**before the first evaluation**, prints the class's size and bar, then drives the agent
until it submits (or the move budget runs out, when the harness submits the best pair).
The log is what `quixote audit` prices.
"""
from __future__ import annotations

import importlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

LOG_FORMAT = "quixote-log/1"


@dataclass
class View:
    step: int
    tools: tuple
    last: dict | None                      # {"ok", "text", "state"} or {"refused": text}
    support: list
    best_support: list
    best: float | None
    info: dict
    n_features: int
    feature_names: list
    class_name: str
    max_moves: int
    submitted: bool = False


class Agent(Protocol):
    def next_move(self, view: View) -> dict: ...


def load_agent(spec: str):
    """`MODULE:ATTR` -> an agent instance (ATTR may be a class or a factory)."""
    mod, _, attr = spec.partition(":")
    if not mod or not attr:
        raise ValueError(f"agent must be MODULE:ATTR, not {spec!r}")
    import os
    import sys
    if os.getcwd() not in sys.path:                  # agents usually live in the user's own project
        sys.path.insert(0, os.getcwd())
    obj = getattr(importlib.import_module(mod), attr)
    if isinstance(obj, type) or (callable(obj) and not hasattr(obj, "next_move")):
        return obj()                                  # a class or a factory
    return obj


@dataclass
class Harness:
    """The session, its sandbox and its class table, built the same way for a live run and
    for an audit's replay, so the two cannot drift apart."""
    panel_arrays: dict
    lc: object
    panel: object = None
    table: object = None
    sandbox: object = None
    tools: object = None

    def open(self, max_moves: int):
        from environments.real_sandbox import RealSandbox
        from quixote.agent_adapter import ToolSession
        from quixote.classes import table_for
        from quixote.session import Session
        self.panel, self.table = table_for(self.lc, self.panel_arrays)
        self.sandbox = RealSandbox(self.panel, spec_class=self.lc.spec_class, class_table=self.table)
        session = Session.on_sandbox(self.sandbox, self.lc.spec_class, name_prefix="quixote")
        self.tools = ToolSession(session, max_turns=max_moves)
        return self

    def call(self, tool: str, args: dict) -> dict:
        from quixote.agent_adapter import ToolRefused
        try:
            r = self.tools.call(tool, **args)
            return {"ok": bool(r.ok), "text": r.text, "state": _jsonable(r.state)}
        except ToolRefused as e:
            return {"refused": str(e)}
        except (TypeError, ValueError) as e:
            return {"refused": f"{tool}: {e}"}

    def view(self, step: int, last, max_moves: int) -> View:
        from quixote.agent_adapter import TOOLS
        st = self.tools.session
        info = {k: (None if v is None else (bool(v) if isinstance(v, bool) else float(v)))
                for k, v in st.info_state().items()}
        return View(step=step, tools=TOOLS, last=last, support=_jsonable(list(st.support)),
                    best_support=_jsonable(list(st.best_support)),
                    best=None if st.best_score == float("-inf") else float(st.best_score),
                    info=info, n_features=int(self.panel.features.shape[2]),
                    feature_names=list(self.panel.feature_names),
                    class_name=self.lc.spec_class.name, max_moves=max_moves,
                    submitted=self.tools.submitted)


def _jsonable(x):
    import numpy as np
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.floating, float)):
        v = float(x)
        return None if v != v or v in (float("inf"), float("-inf")) else v
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def run_session(agent, panel_path, class_path, out_path, *, seed: int = 0, max_moves: int = 60,
                alpha: float = 0.05, B_bar: int = 500, echo=print) -> dict:
    from quixote import classes, panel as P
    panel_path, class_path, out_path = Path(panel_path), Path(class_path), Path(out_path)
    arrays = P.read(panel_path)
    lc = classes.load(class_path, arrays, alpha=alpha, B=B_bar, seed=seed)
    if lc.kind != "subsets":
        raise classes.ClassError("the harness searches a subsets class; a streams class is audited "
                                 "as a transcript (garden audit)")
    echo(lc.describe())
    log = {"format": LOG_FORMAT, "panel_file": panel_path.name, "panel_sha256": P.sha256(panel_path),
           "class_file": class_path.name, "class_sha256": lc.sha256, "class_name": lc.spec_class.name,
           "class_size": lc.size, "class_bar": lc.bar, "alpha": alpha, "seed": seed, "max_moves": max_moves,
           "agent": f"{type(agent).__module__}.{type(agent).__qualname__}",
           "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "calls": []}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(log, indent=1))          # the hashes, before any evaluation
    h = Harness(arrays, lc).open(max_moves)
    last = None
    for step in range(4 * max_moves + 20):                   # refusals do not use the budget
        if h.tools.submitted:
            break
        move = dict(agent.next_move(h.view(step, last, max_moves)) or {})
        tool = move.pop("tool", None)
        if tool is None:
            last = {"refused": "a move is a dict with a 'tool' key"}
            log["calls"].append({"tool": None, "args": _jsonable(move), **last})
            continue
        last = h.call(tool, move)
        log["calls"].append({"tool": tool, "args": _jsonable(move), **last})
    if not h.tools.submitted:                                # the harness submits the best pair
        last = h.call("submit", {})
        log["calls"].append({"tool": "submit", "args": {}, "by": "harness", **last})
    support, score = h.tools.session.submission()
    log.update({"submitted": {"support": _jsonable(list(support)), "score": float(score)},
                "n_moves": int(h.tools.session.log.n_moves),
                "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    out_path.write_text(json.dumps(log, indent=1))
    return log


def replay(log: dict, panel_arrays: dict, lc) -> "Harness":
    """Re-execute a log's calls through a fresh harness. The harness is deterministic, so a log
    that it wrote reproduces call for call; `quixote audit` refuses one that does not."""
    h = Harness(panel_arrays, lc).open(int(log.get("max_moves", 60)))
    for i, c in enumerate(log["calls"]):
        if c.get("tool") is None:
            continue
        got = h.call(c["tool"], dict(c.get("args") or {}))
        want = {k: c[k] for k in ("ok", "text", "refused") if k in c}
        have = {k: got[k] for k in ("ok", "text", "refused") if k in got}
        if want != have:
            raise ReplayMismatch(f"call {i} ({c['tool']}) does not reproduce: logged {want}, got {have}")
    return h


class ReplayMismatch(RuntimeError):
    pass


__all__ = ["Agent", "View", "run_session", "replay", "load_agent", "ReplayMismatch", "LOG_FORMAT", "asdict"]
