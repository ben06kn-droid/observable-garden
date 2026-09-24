"""The grammar as tools: what an LLM agent is allowed to do in a quixote session.

7.2 item (a). `searchers/llm_agent.py` gives an agent `evaluate` and `submit`,
which means the agent builds its own specification and the harness takes its word
for what it built. That is exactly the arrangement the quixote grammar exists to
replace: here the agent **names a move** and the harness computes it, so the log
cannot disagree with what ran.

**The tool surface, one per grammar move plus the declaration slots:**

| tool | what it does |
|---|---|
| `init` | anchor on the best single feature by the statistic |
| `extend_best` | add the feature that most improves the support |
| `swap_worst` | replace the weakest held feature with the best available |
| `flip` | reverse the sign of one named held feature |
| `refine` | re-fit the held support's signs |
| `pick` | choose among named candidates by a named statistic, with an `else` |
| `stop` | end the search, on a **declared trigger** |
| `restart` | abandon the support for the next anchor, on a declared trigger |
| `pick_prior` | name a specification before anything is evaluated |
| `short_list` | declare up to `cap` specifications before anything is evaluated |
| `declare_budget` | fix the step budget before anything is evaluated |
| `predict` | state the out-of-sample Sharpe the agent expects |
| `submit` | end the run; the submission is the best pair, not the current one |

**Every move is proposed, then accepted or rejected.** `propose` is where the
data is touched and is logged as such; whether the agent keeps the result is a
separate decision and a separate record. The adapter exposes the pair as one tool
call with a `keep` argument rather than two tools, because an agent that proposed
and never resolved would leave the session with a pending move and no record of
the evaluation it caused.

**A stop ends the search.** After a `stop` that fires, only `predict` and
`submit` are taken; every other call is refused. A second stop in one log would
make the realized move count a fiction, and trigger replay is told exactly that
number.

**A meta move without a declared trigger is refused, not logged.** `stop` and
`restart` each take a trigger from `quixote/triggers.py` by name and parameter;
the session stamps it *before* the move executes, so a trigger invented after
seeing the result cannot be passed off as one that fired. This is the same
refusal `SessionLog.refuse_if_late` makes for the declaration slots.

**What the adapter does not do.** It does not talk to a model. `ToolSession` is
the pure, synchronous surface — a dict-in, dict-out call for each tool — and
`QuixoteAgent` is the `Searcher` that drives it. Keeping the model out of this
module is what makes the milestone testable: a scripted policy expressed as tool
calls must reproduce that same policy run directly against a `Session`, bit for
bit (`tests/test_agent_adapter.py`). The MCP wiring that hands these tools to a
model belongs with the prompts in `prereg/agent-on-real-data.md`, not here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np

from quixote.grammar import Move
from quixote.session import Session
from quixote.triggers import PREDICATES, Trigger

# The tools, in the order the pre-registration lists them. A name absent here
# cannot be called: `ToolSession.call` refuses rather than guessing.
CONTENT_TOOLS = ("init", "extend_best", "swap_worst", "flip", "refine", "pick")
META_TOOLS = ("stop", "restart")
SLOT_TOOLS = ("pick_prior", "short_list", "declare_budget", "predict", "submit")
TOOLS = CONTENT_TOOLS + META_TOOLS + SLOT_TOOLS

# A content move may be kept or discarded; a meta move may not, since it is the
# trigger and not the result that licenses it.
REFUSED_WITHOUT_TRIGGER = META_TOOLS


class ToolRefused(Exception):
    """A tool call the harness will not execute. Refusals are part of the
    contract, not errors: an agent that names a move outside the class, a meta
    move with no declared trigger, or a declaration after the first evaluation
    gets one of these and the run continues."""


@dataclass
class ToolResult:
    """What a tool call returns to the agent. Short by design: tool results are
    the only lever on per-turn cost (`searchers/llm_agent.py`), and a result that
    recited the whole support would pay for it on every step."""
    ok: bool
    text: str
    state: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"ok": self.ok, "result": self.text, **self.state})


def _support_text(support) -> str:
    return "[" + ", ".join(f"{k}{'+' if s > 0 else '-'}" for k, s in support) + "]"


class ToolSession:
    """One quixote session behind a tool surface.

    Wraps a `Session` and nothing else: every call routes to the session's own
    methods, so the log this produces is the log a direct caller produces. The
    adapter adds refusals and short text; it adds no state of its own beyond the
    call count.
    """

    def __init__(self, session: Session, short_list_cap: int = 5):
        self.session = session
        self.short_list_cap = short_list_cap
        self.n_calls = 0
        self.submitted = False
        # A stop ends the search. Without this latch an agent can call `stop`
        # twice and the log carries two of them, which is not a search any
        # replicate can reproduce: trigger replay is told how many moves the
        # realized search took, and a second stop makes that number a fiction.
        # Found by the pilot's dry run, before any model-backed run.
        self.stopped = False

    # -- the surface ---------------------------------------------------------

    def call(self, name: str, **kw) -> ToolResult:
        """Route one tool call. Unknown names are refused by name, with the list,
        rather than raising something the agent cannot act on."""
        if name not in TOOLS:
            raise ToolRefused(f"unknown tool {name!r}; the grammar is {list(TOOLS)}")
        if self.submitted:
            raise ToolRefused("this session has submitted; no further moves are taken")
        if self.stopped and name not in ("submit", "predict"):
            raise ToolRefused("this session has stopped; the search is over and only "
                              "`predict` and `submit` remain")
        self.n_calls += 1
        return getattr(self, f"_{name}")(**kw)

    def tool_schemas(self) -> list[dict]:
        """The schema list an MCP server would publish. Built from this module's
        own docstrings and the trigger library, so the surface an agent sees
        cannot drift from the surface this class implements."""
        out = []
        for name in TOOLS:
            fn = getattr(self, f"_{name}")
            out.append({"name": name,
                        "description": (fn.__doc__ or "").strip().split("\n")[0],
                        "meta": name in META_TOOLS})
        return out

    # -- content moves -------------------------------------------------------

    def _move(self, move: Move, keep: bool, trigger=None) -> ToolResult:
        """Propose, then accept or reject. Both outcomes are recorded: the
        candidates were evaluated either way, so both count toward breadth."""
        support, score, n_cand = self.session.propose(move)
        if n_cand == 0:
            self.session.cancel()
            return ToolResult(False, f"{move.kind}: no candidate inside the class",
                              {"n_candidates": 0})
        if keep:
            self.session.accept(trigger=trigger)
            kept = "kept"
        else:
            self.session.reject(trigger=trigger)
            kept = "discarded"
        st = self.session
        return ToolResult(True,
                          f"{move.kind} {kept}: {_support_text(st.support)} "
                          f"sharpe {st.score:.4f} (best {st.best_score:.4f}, "
                          f"{n_cand} candidates)",
                          {"support": list(st.support), "score": st.score,
                           "best": st.best_score, "n_candidates": n_cand})

    def _init(self, statistic: str = "sharpe", keep: bool = True) -> ToolResult:
        """Anchor on the best single feature by the named statistic."""
        return self._move(Move("init", statistic=statistic), keep)

    def _extend_best(self, statistic: str = "sharpe", keep: bool = True) -> ToolResult:
        """Add the one feature that most improves the held support."""
        return self._move(Move("extend_best", statistic=statistic), keep)

    def _swap_worst(self, statistic: str = "sharpe", keep: bool = True) -> ToolResult:
        """Replace the weakest held feature with the best available one."""
        return self._move(Move("swap_worst", statistic=statistic), keep)

    def _flip(self, feature: int, statistic: str = "sharpe",
              keep: bool = True) -> ToolResult:
        """Reverse the sign of one held feature."""
        return self._move(Move("flip", feature=int(feature), statistic=statistic), keep)

    def _refine(self, statistic: str = "sharpe", keep: bool = True) -> ToolResult:
        """Re-fit the signs of the held support without changing which features
        it holds."""
        return self._move(Move("refine", statistic=statistic), keep)

    def _pick(self, among, statistic: str = "sharpe", choice: int | None = None,
              else_statistic: str | None = None, keep: bool = True) -> ToolResult:
        """Choose among named candidates by a named statistic, with an optional
        fallback for when the premise fails on a replicate."""
        move = Move("pick", statistic=statistic, among=tuple(int(j) for j in among),
                    choice=None if choice is None else int(choice),
                    else_statistic=else_statistic)
        res = self._move(move, keep)
        rec = self.session.log.records[-1] if self.session.log.records else None
        if rec is not None and not rec.replayable:
            res.state["consistency"] = "rejected as declared: the choice is not what the rule selects"
        return res

    # -- meta moves ----------------------------------------------------------

    def _trigger(self, trigger: str, param: float,
                 action: str) -> tuple[Trigger, bool, float, float]:
        """Build a declared trigger, evaluate it on the current information set,
        and stamp it — before the move it justifies executes.

        The trigger carries the action it licenses, so a predicate declared for a
        restart cannot be spent on a stop: the record says which move it was for.
        """
        if trigger not in PREDICATES:
            raise ToolRefused(f"unknown trigger {trigger!r}; the library is "
                              f"{list(PREDICATES)}")
        t = Trigger(kind=trigger, param=float(param), action=action)
        fires, value, stamp = self.session.evaluate_trigger(t)
        return t, fires, value, stamp

    def _stop(self, trigger: str, param: float = 0.0) -> ToolResult:
        """End the search because a declared trigger fired."""
        t, fires, value, stamp = self._trigger(trigger, param, "stop")
        if not fires:
            raise ToolRefused(
                f"stop refused: {t.name} does not fire on the current state "
                f"(value {value:.4f}). A meta move is taken because a declared "
                "trigger fired, not because the agent prefers it.")
        self.session.stop(t, value, stamped_at=stamp)
        self.stopped = True
        return ToolResult(True, f"stopped on {t.name} (value {value:.4f})",
                          {"best": self.session.best_score})

    def _restart(self, trigger: str, param: float = 0.0,
                 statistic: str = "sharpe") -> ToolResult:
        """Abandon the current support for the next anchor, on a declared
        trigger. The best pair found so far is kept."""
        t, fires, value, stamp = self._trigger(trigger, param, "restart")
        if not fires:
            raise ToolRefused(
                f"restart refused: {t.name} does not fire on the current state "
                f"(value {value:.4f}).")
        moved = self.session.restart(t, value, stamp, statistic=statistic)
        if not moved:
            return ToolResult(False, "no anchor left; recorded as a stop on exhausted",
                              {"best": self.session.best_score})
        return ToolResult(True,
                          f"restarted on {t.name}: {_support_text(self.session.support)} "
                          f"sharpe {self.session.score:.4f} (best "
                          f"{self.session.best_score:.4f})",
                          {"support": list(self.session.support),
                           "best": self.session.best_score})

    # -- declaration slots ---------------------------------------------------

    def _pick_prior(self, support, reason: str = "") -> ToolResult:
        """Name a specification before anything has been evaluated."""
        s = tuple((int(k), float(sg)) for k, sg in support)
        self.session.pick_prior(s, reason=reason)
        return ToolResult(True, f"prior pick recorded: {_support_text(s)}")

    def _short_list(self, supports) -> ToolResult:
        """Declare up to the registered cap of specifications, before any
        evaluation."""
        ss = tuple(tuple((int(k), float(sg)) for k, sg in s) for s in supports)
        self.session.declare_short_list(ss, cap=self.short_list_cap)
        return ToolResult(True, f"short list of {len(ss)} recorded")

    def _declare_budget(self, budget: int) -> ToolResult:
        """Fix the step budget, before any evaluation."""
        self.session.declare_budget(int(budget))
        return ToolResult(True, f"budget {int(budget)} recorded")

    def _predict(self, mean: float, sd: float = 0.0, note: str = "") -> ToolResult:
        """State the out-of-sample Sharpe the agent expects. Recorded, not used."""
        self.session.predict(float(mean), float(sd), note)
        return ToolResult(True, f"prediction {float(mean):.3f} (sd {float(sd):.3f}) recorded")

    def _submit(self) -> ToolResult:
        """End the run. The submission is the best support and its score, never
        a mix of the current support with another's score."""
        support, score = self.session.submission()
        self.submitted = True
        return ToolResult(True, f"submitted {_support_text(support)} sharpe {score:.4f}",
                          {"support": list(support), "score": score})


class QuixoteAgent:
    """A `Searcher` that runs a policy over the tool surface.

    Same ABC as `searchers/llm_agent.py`: `run(sandbox)` evaluates through the
    sandbox and submits exactly once, so a quixote run is graded by the same
    harness as every scripted searcher. `policy` is any callable taking the
    `ToolSession` and driving it; a model-backed policy and a scripted one are
    interchangeable here, which is what the milestone test exploits.
    """
    name = "quixote-agent"

    def __init__(self, spec_class, policy, seed: int = 0, short_list_cap: int = 5):
        self.spec_class = spec_class
        self.policy = policy
        self.seed = seed
        self.short_list_cap = short_list_cap
        self.tools: ToolSession | None = None

    def run(self, sandbox) -> None:
        from environments.sandbox import Distribution, Specification

        session = Session.on_sandbox(sandbox, self.spec_class, name_prefix=self.name)
        self.tools = ToolSession(session, short_list_cap=self.short_list_cap)
        self.policy(self.tools)
        if not self.tools.submitted:
            self.tools.call("submit")
        support, score = session.submission()
        spec = Specification(weights=session.submitted_weights(),
                             name=f"{self.name}_{_support_text(support)}")
        sandbox.submit(spec, Distribution.degenerate(float(score)))

    @property
    def log(self):
        return None if self.tools is None else self.tools.session.log
