"""searchers/llm_agent.py and experiments/e_agent.py — no model calls anywhere.

Every test here drives the MCP tool handlers directly, as a scripted caller
would, so the whole binding is exercised without a token being spent.
"""
import asyncio
import json

import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox, Specification
from garden import watch as watch_mod
from garden.spec_class import SubsetClass
from searchers.llm_agent import (
    ARMS, LIVE_ARMS, SERVER_NAME, AgentConfig, LLMAgent, RunPaths, build_prompt, spec_from,
    tool_names,
)

PPY = 252
K = 8


def make_agent(tmp_path, arm="control", budget=None):
    cls = SubsetClass(max_size=3, signed=True)
    cfg = DGPConfig(M=20, T=200, T_oos=80, K=K, s=0, rho=0.0, sigma=1.0, seed=5)
    sb = Sandbox(generate(cfg), periods_per_year=PPY, spec_class=cls)
    w = watch_mod.open(sb, cls, B=300, seed=6, agent_view="standing")
    agent_cfg = AgentConfig(arm=arm, K=K, M=20, d=3, budget=budget,
                            system_prompt="test", run_id="t")
    agent = LLMAgent(agent_cfg, RunPaths(tmp_path), seed=6)
    agent._watch = w
    return agent, w, sb


def handlers(agent):
    """The SdkMcpTool objects the server would expose, by bare name.

    Taken from `_build_tools` rather than from the server: create_sdk_mcp_server
    returns a plain dict ({type, name, instance}) with no route back to the tool
    objects."""
    return {t.name: t for t in agent._build_tools()}


def test_make_server_wraps_the_same_tools():
    """The server really is built from _build_tools, so exercising the handlers
    directly exercises what the model would reach."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        agent, _, _ = make_agent(tmp, arm="gate")
        srv = agent._make_server()
        assert srv["type"] == "sdk" and srv["name"] == SERVER_NAME
        assert {t.name for t in agent._build_tools()} == {"evaluate", "submit", "status"}


def call(h, args):
    return asyncio.run(h.handler(args))


def text_of(res):
    return res["content"][0]["text"]


# -- spec construction -------------------------------------------------------

def test_spec_from_builds_signed_weights():
    s = spec_from([0, 3], [1, -1], K)
    assert s.weights[0] == 1.0 and s.weights[3] == -1.0
    assert np.count_nonzero(s.weights) == 2


@pytest.mark.parametrize("features,signs,match", [
    ([0, 1], [1], "differ in length"),
    ([], [], "at least one feature"),
    ([0, 0], [1, 1], "repeated feature"),
    ([99], [1], "out of range"),
    ([0], [2], "sign must be"),
])
def test_spec_from_rejects_malformed(features, signs, match):
    with pytest.raises(ValueError, match=match):
        spec_from(features, signs, K)


# -- prompt substitution -----------------------------------------------------

def test_build_prompt_substitutes_the_three_integers():
    out = build_prompt("M={M} K={K} d={d}", M=50, K=40, d=3)
    assert out == "M=50 K=40 d=3"


def test_build_prompt_raises_on_an_unsubstituted_placeholder():
    with pytest.raises(ValueError, match="unsubstituted placeholder"):
        build_prompt("M={M} and {B} remains", M=50, K=40, d=3)


def test_prompts_are_read_from_the_prereg_file_not_duplicated():
    from experiments.e_agent import read_prompts, system_prompt_for
    p = read_prompts()
    assert "{M}" in p["control"] and "{K}" in p["control"] and "{d}" in p["control"]
    control = system_prompt_for("control", 50, 40, 3, p)
    gate = system_prompt_for("gate", 50, 40, 3, p)
    # AGENT_PROMPTS.md §2: each arm is the control prompt plus exactly what it adds.
    assert gate.startswith(control)
    assert len(gate) > len(control)
    assert "status" in gate[len(control):]


# -- tool availability per arm -----------------------------------------------

def test_status_exists_only_in_the_gate_arm(tmp_path):
    for arm in ("control", "count", "budget"):
        names = tool_names(arm)
        assert f"mcp__{SERVER_NAME}__status" not in names
    assert f"mcp__{SERVER_NAME}__status" in tool_names("gate")


def test_status_handler_is_absent_outside_gate(tmp_path):
    agent, _, _ = make_agent(tmp_path, arm="control")
    assert "status" not in handlers(agent)
    agent_g, _, _ = make_agent(tmp_path / "g", arm="gate")
    assert "status" in handlers(agent_g)


# -- evaluate ----------------------------------------------------------------

def test_evaluate_logs_and_returns_a_short_line(tmp_path):
    agent, w, sb = make_agent(tmp_path)
    h = handlers(agent)["evaluate"]
    out = text_of(call(h, {"features": [0], "signs": [1]}))
    assert out.startswith("Sharpe ") and "n=" in out
    # Under 40 tokens: a crude word/char bound is enough to catch a regression.
    assert len(out) < 60
    assert sb.returns_matrix().shape[1] == 1
    rows = [json.loads(x) for x in (tmp_path / "transcript.jsonl").read_text().splitlines()]
    assert any(r["kind"] == "tool_result" and r["tool"] == "evaluate" for r in rows)


def test_evaluate_rejects_out_of_class_without_crashing(tmp_path):
    agent, w, sb = make_agent(tmp_path)
    h = handlers(agent)["evaluate"]
    out = text_of(call(h, {"features": [0, 1, 2, 3], "signs": [1, 1, 1, 1]}))  # size 4 > d=3
    assert out.startswith("Rejected:")
    assert sb.returns_matrix().shape[1] == 0


def test_budget_arm_stops_evaluating_at_the_cap(tmp_path):
    agent, _, sb = make_agent(tmp_path, arm="budget", budget=2)
    h = handlers(agent)["evaluate"]
    for k in range(2):
        assert text_of(call(h, {"features": [k], "signs": [1]})).startswith("Sharpe ")
    out = text_of(call(h, {"features": [3], "signs": [1]}))
    assert "remaining: 0" in out
    assert sb.returns_matrix().shape[1] == 2


def test_count_arm_appends_the_running_count(tmp_path):
    agent, _, _ = make_agent(tmp_path, arm="count")
    h = handlers(agent)["evaluate"]
    out = text_of(call(h, {"features": [0], "signs": [1]}))
    assert "Specifications evaluated so far: 1." in out


# -- submit ------------------------------------------------------------------

def test_submit_routes_to_watch_and_writes_artifacts(tmp_path):
    agent, w, _ = make_agent(tmp_path)
    hs = handlers(agent)
    call(hs["evaluate"], {"features": [0], "signs": [1]})
    out = text_of(call(hs["submit"], {"features": [0], "signs": [1], "mean": 1.0, "sd": 0.5}))
    assert out == "Submitted."
    assert agent.verdict is not None and agent.verdict.method == "full_class"
    assert json.loads((tmp_path / "stated.json").read_text()) == {"mean": 1.0, "sd": 0.5}
    assert json.loads((tmp_path / "verdict.json").read_text())["status"] == agent.verdict.status


def test_submit_twice_is_refused(tmp_path):
    agent, _, _ = make_agent(tmp_path)
    hs = handlers(agent)
    call(hs["evaluate"], {"features": [0], "signs": [1]})
    call(hs["submit"], {"features": [0], "signs": [1], "mean": 1.0, "sd": 0.5})
    assert text_of(call(hs["submit"], {"features": [1], "signs": [1],
                                       "mean": 2.0, "sd": 0.5})) == "Already submitted."


def test_oos_is_not_written_before_submit(tmp_path):
    agent, _, _ = make_agent(tmp_path)
    call(handlers(agent)["evaluate"], {"features": [0], "signs": [1]})
    assert not (tmp_path / "oos.json").exists()
    assert agent.submitted_spec is None


# -- built-in tools are removed, not merely refused ---------------------------

def test_no_builtin_tool_is_reachable(tmp_path):
    """Replaces a 'disallowed_tools list is complete' test, which cannot be
    written: the SDK exposes no enumerable built-in tool list, so such a test
    would assert a hardcoded list against itself. `tools=[]` removes the set
    outright, and allowed_tools names only MCP tools."""
    agent, _, _ = make_agent(tmp_path, arm="gate")
    opts = agent._options(tmp_path)
    assert opts.tools == []
    assert opts.setting_sources == []
    assert all(n.startswith(f"mcp__{SERVER_NAME}__") for n in opts.allowed_tools)
    for builtin in ("Bash", "Read", "Write", "Edit", "Glob", "Grep", "WebFetch",
                    "WebSearch", "Task", "TodoWrite", "NotebookEdit"):
        assert builtin not in opts.allowed_tools
    assert isinstance(opts.system_prompt, str)   # a plain str replaces the preset


# -- runner ------------------------------------------------------------------

def test_deferred_arms_are_refused_by_the_runner():
    from experiments.e_agent import main
    assert main(["--arm", "count", "--runs", "1"]) == 3
    assert main(["--arm", "budget", "--runs", "1"]) == 3


def test_seed_sequence_is_the_pre_registered_one():
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    expected = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=80)
    np.testing.assert_array_equal(dgp_seeds(), expected)
    assert len(set(dgp_seeds().tolist())) == 80


def test_live_arms_are_control_and_gate():
    assert LIVE_ARMS == ("control", "gate")
    assert set(LIVE_ARMS) <= set(ARMS)
