"""7.5 build item 7: the unsaturable arm's cap of 3 content moves, in the harness.

`prereg/planted-edge.md`: `init`, `extend_best`, `swap_worst`, `flip`, `refine` and
`pick` each count one; `declare_triggers`, `stop`, `restart`, `pick_prior`, `predict`
and `submit` do not. **The fourth content move is refused by the harness**, before
anything is computed.
"""
import pytest

from garden.spec_class import SubsetClass
from quixote.agent_adapter import CONTENT_TOOLS, ToolRefused, ToolSession
from quixote.session import Session
from tests.test_agent_adapter import _fixture, _sandbox

CAP = 3


def _tools(cap=CAP, K=8):
    data, cfg, _ = _fixture(K=K)
    cls = SubsetClass(max_size=3, signed=True)        # the planted arm's class
    sandbox = _sandbox(data, cfg)
    tools = ToolSession(Session.on_sandbox(sandbox, cls), max_turns=60, content_cap=cap)
    # a stop rule that does not fire, so no content move is held by a firing trigger
    tools.call("declare_triggers", triggers=[
        {"trigger": "failures_at_least", "param": 99, "action": "stop"}])
    return tools, sandbox


def _three(tools):
    tools.call("init")
    tools.call("extend_best")
    tools.call("extend_best", keep=False)          # discarded still counts


def _fourth_args(tools, kind):
    held = tools.session.support
    return {"init": {}, "extend_best": {}, "swap_worst": {}, "refine": {},
            "flip": {"feature": held[0][0]},
            "pick": {"among": [k for k in range(8) if k not in {h for h, _ in held}][:3]},
            }[kind]


@pytest.mark.parametrize("kind", CONTENT_TOOLS)
def test_the_fourth_content_move_is_refused_whatever_it_is(kind):
    tools, sandbox = _tools()
    _three(tools)
    assert tools.n_content == CAP
    n_records = len(tools.session.log.records)
    n_evals = len(sandbox.transcript)
    with pytest.raises(ToolRefused, match=r"cap of 3 content moves"):
        tools.call(kind, **_fourth_args(tools, kind))
    # refused BEFORE anything was computed or recorded
    assert len(tools.session.log.records) == n_records
    assert len(sandbox.transcript) == n_evals
    assert tools.n_content == CAP


def test_the_third_is_allowed_and_the_cap_is_on_the_log():
    tools, _ = _tools()
    tools.call("init")
    tools.call("extend_best")
    assert tools.n_content == 2
    tools.call("extend_best")
    assert tools.n_content == 3
    assert tools.session.log.content_cap == CAP


def test_a_move_refused_before_evaluation_does_not_count():
    tools, _ = _tools()
    tools.call("init")
    with pytest.raises(ToolRefused, match="not defined in this state"):
        tools.call("flip", feature=7 if tools.session.support[0][0] != 7 else 6)
    assert tools.n_content == 1
    tools.call("extend_best")
    tools.call("extend_best")
    assert tools.n_content == 3


def test_the_non_content_tools_remain_after_the_cap():
    tools, _ = _tools()
    _three(tools)
    tools.call("change_trigger", trigger="failures_at_least", param=0, action="stop")
    tools.call("stop", trigger="failures_at_least", param=0)
    tools.call("predict", mean=0.3, sd=0.1)
    res = tools.call("submit")
    assert res.ok and tools.submitted


def test_restart_does_not_count():
    tools, _ = _tools()
    tools.call("init")
    tools.call("change_trigger", trigger="failures_at_least", param=0, action="restart")
    tools.call("restart", trigger="failures_at_least", param=0)
    assert tools.n_content == 1


def test_no_cap_by_default():
    data, cfg, cls = _fixture()
    tools = ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls), max_turns=60)
    tools.call("init")
    for _ in range(4):
        tools.call("extend_best", keep=False)
    assert tools.n_content == 5 and tools.session.log.content_cap is None


def test_a_non_positive_cap_is_refused():
    data, cfg, cls = _fixture()
    with pytest.raises(ValueError):
        ToolSession(Session.on_sandbox(_sandbox(data, cfg), cls), content_cap=0)
