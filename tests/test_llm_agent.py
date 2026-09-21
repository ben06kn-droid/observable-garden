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
pytest.importorskip(
    "claude_agent_sdk",
    reason="searchers.llm_agent imports the agent SDK at module level. Agent runs\ngo through the seat on the laptop and never on EC2, so the SDK is absent there\nand these tests skip rather than failing collection for the whole suite.")

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
    """Superseded in part by the hard-cap test below: the (B+1)th call now
    answers with an explicit refusal rather than a bare countdown."""
    agent, _, sb = make_agent(tmp_path, arm="budget", budget=2)
    h = handlers(agent)["evaluate"]
    for k in range(2):
        assert text_of(call(h, {"features": [k], "signs": [1]})).startswith("Sharpe ")
    out = text_of(call(h, {"features": [3], "signs": [1]}))
    assert out.startswith("Refused:")
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


def test_refused_submit_does_not_latch_the_run(tmp_path):
    """A submit the watch refuses must leave the run open.

    Latching submitted_spec before the watch call inverted this: the refusal
    left the flag set with no verdict, so every retry hit "Already submitted.",
    the agent could never recover, and the harness still graded OOS and exited
    0. That silently voided s0_T5000_sonnet_budget20_089, whose first submit
    named a specification it had never evaluated."""
    agent, _, _ = make_agent(tmp_path)
    hs = handlers(agent)
    call(hs["evaluate"], {"features": [0], "signs": [1]})

    out = text_of(call(hs["submit"], {"features": [1, 2], "signs": [1, 1],
                                      "mean": 1.0, "sd": 0.5}))
    assert out.startswith("Rejected:") and "never evaluated" in out
    assert agent.submitted_spec is None and agent.verdict is None
    assert not (tmp_path / "verdict.json").exists()
    assert not (tmp_path / "stated.json").exists()

    # Still open: the agent can submit something it did evaluate.
    assert text_of(call(hs["submit"], {"features": [0], "signs": [1],
                                       "mean": 1.0, "sd": 0.5})) == "Submitted."
    assert agent.verdict is not None
    assert (tmp_path / "verdict.json").exists()


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


# -- arm prompts and result text (amendment 4) -------------------------------

def test_prereg_yields_all_three_treatment_strings():
    """§2 states count and budget inline rather than in fences, so they are
    picked out by placeholder. Retyping them into code would defeat reading the
    file at all."""
    from experiments.e_agent import read_prompts
    p = read_prompts()
    assert p["count_result"] == "Specifications evaluated so far: {N}."
    assert p["budget_prompt"] == "You may call evaluate at most {B} times."
    assert p["budget_result"] == "Evaluations remaining: {R}."


def test_count_prompt_is_byte_identical_to_control():
    """§2 gives count 'tools as control'; the whole treatment is result text."""
    from experiments.e_agent import read_prompts, system_prompt_for
    p = read_prompts()
    assert system_prompt_for("count", 50, 40, 3, p) == system_prompt_for("control", 50, 40, 3, p)


def test_budget_prompt_is_control_plus_the_substituted_line():
    from experiments.e_agent import read_prompts, system_prompt_for
    p = read_prompts()
    base = system_prompt_for("control", 50, 40, 3, p)
    for B in (20, 60, 180):
        got = system_prompt_for("budget", 50, 40, 3, p, budget=B)
        assert got.startswith(base)
        assert got[len(base):].strip() == f"You may call evaluate at most {B} times."
        assert "{B}" not in got


def test_budget_prompt_without_a_cap_raises():
    from experiments.e_agent import read_prompts, system_prompt_for
    with pytest.raises(ValueError, match="explicit cap"):
        system_prompt_for("budget", 50, 40, 3, read_prompts())


def test_count_result_text_carries_the_running_count(tmp_path):
    agent, _, _ = make_agent(tmp_path, arm="count")
    h = handlers(agent)["evaluate"]
    first = text_of(call(h, {"features": [0], "signs": [1]}))
    second = text_of(call(h, {"features": [1], "signs": [1]}))
    assert first.endswith("Specifications evaluated so far: 1.")
    assert second.endswith("Specifications evaluated so far: 2.")


def test_budget_result_text_counts_down_and_the_cap_is_hard(tmp_path):
    """The (B+1)th call is refused by the harness with a message. It is a cap,
    not a class violation, so it never reaches Watch and is not counted among
    refused_attempts."""
    agent, w, sb = make_agent(tmp_path, arm="budget", budget=2)
    h = handlers(agent)["evaluate"]
    assert text_of(call(h, {"features": [0], "signs": [1]})).endswith("Evaluations remaining: 1.")
    assert text_of(call(h, {"features": [1], "signs": [1]})).endswith("Evaluations remaining: 0.")

    refused = text_of(call(h, {"features": [2], "signs": [1]}))
    assert refused.startswith("Refused:")
    assert "budget of 2 is spent" in refused
    assert "submit" in refused
    assert sb.returns_matrix().shape[1] == 2          # nothing further was evaluated
    assert w.refused_attempts == []                   # not a Theta breach
    assert agent._budget_refusals == 1


def test_run_id_carries_the_assigned_dose_and_model():
    """Batch 3 put the model in the id too, so a cell is readable from `ls`."""
    from experiments.e_agent import make_run_id
    assert make_run_id("s0", "budget", 81, 5000, 20) == "s0_T5000_sonnet_budget20_081"
    assert make_run_id("s0", "budget", 82, 5000, 60) == "s0_T5000_sonnet_budget60_082"
    assert make_run_id("s0", "count", 80, 5000) == "s0_T5000_sonnet_count_080"
    assert make_run_id("s3", "gate", 85, 5000) == "s3_T5000_sonnet_gate_085"
    assert (make_run_id("s0", "gate", 320, 5000, None, "claude-fable-5-1")
            == "s0_T5000_fable_gate_320")


# -- batch 3: the model dimension --------------------------------------------

def test_agent_config_rejects_an_unknown_model():
    from searchers.llm_agent import MODELS
    with pytest.raises(ValueError, match="model must be one of"):
        AgentConfig(model="claude-not-a-model")
    for m in MODELS:
        AgentConfig(model=m)               # both must construct


def test_seed_extension_to_500_preserves_the_earlier_draws():
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    for n in (80, 320):
        earlier = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=n)
        np.testing.assert_array_equal(dgp_seeds(500)[:n], earlier)
    assert len(set(dgp_seeds(500).tolist())) == 500


def test_worker_index_is_forwarded_to_the_run(monkeypatch):
    """Amendment 6 records the worker index per run, so the CLI has to carry it
    all the way into run_one. It is None when the runner is sequential."""
    import experiments.e_agent as ea
    seen = {}

    def fake_run_one(*args):
        seen["worker"] = args[6]
        return 0

    monkeypatch.setattr(ea, "read_prompts", lambda *a, **k: {})
    monkeypatch.setattr(ea, "run_one", fake_run_one)
    base = ["--arm", "control", "--config", "s0", "--runs", "1", "--seed-index", "5"]

    assert ea.main(base + ["--worker", "3"]) == 0
    assert seen["worker"] == 3
    assert ea.main(base) == 0
    assert seen["worker"] is None


def test_seed_stream_extension_preserves_the_first_eighty():
    """Amendment 4 extends the seed draw from 80 to 320. Seeds 0-79 must keep
    the meaning they had in the first batch."""
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    first80 = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=80)
    np.testing.assert_array_equal(dgp_seeds(320)[:80], first80)
    assert len(set(dgp_seeds(320).tolist())) == 320


def test_all_four_arms_are_live():
    from searchers.llm_agent import ARMS, LIVE_ARMS
    assert set(LIVE_ARMS) == set(ARMS)


# -- considered, both rules --------------------------------------------------

def write_transcript(tmp_path, rows):
    import json as _json
    (tmp_path / "transcript.jsonl").write_text(
        "\n".join(_json.dumps(r) for r in rows) + "\n")


def test_amendment_3_counts_unevaluated_feature_sets(tmp_path):
    """Sets named in prose and not evaluated within that turn or the next two."""
    agent, _, _ = make_agent(tmp_path, arm="control")
    agent.config.seed_index = 80                       # amendment 3 applies
    write_transcript(tmp_path, [
        {"ts": 1, "kind": "assistant_text", "text": "Trying [0,1] and also [2,3] later."},
        {"ts": 2, "kind": "tool_result", "tool": "evaluate", "args": {"features": [0, 1]}},
        {"ts": 3, "kind": "assistant_text", "text": "Now [4,5]."},
        {"ts": 4, "kind": "tool_result", "tool": "evaluate", "args": {"features": [4, 5]}},
    ])
    agent._finalize()
    out = json.loads((tmp_path / "considered.json").read_text())
    assert out["rule"] == "amendment_3"
    assert [2, 3] in out["considered"]                 # named, never evaluated
    assert [0, 1] not in out["considered"]             # evaluated in the same turn
    assert [4, 5] not in out["considered"]


def test_section_5_rule_still_applies_below_seed_eighty(tmp_path):
    agent, _, _ = make_agent(tmp_path, arm="control")
    agent.config.seed_index = 79
    write_transcript(tmp_path, [
        {"ts": 1, "kind": "assistant_text", "text": "Trying [0,1] and also [2,3]."},
        {"ts": 2, "kind": "tool_result", "tool": "evaluate", "args": {"features": [0, 1]}},
    ])
    agent._finalize()
    out = json.loads((tmp_path / "considered.json").read_text())
    assert out["rule"] == "section_5"
    assert out["n_considered"] == 0                    # the rule that fired 0 of 80 times


# -- run directory safety ----------------------------------------------------

def test_run_paths_does_not_create_the_directory_until_first_write(tmp_path):
    """Eager creation left an empty shell whenever a run died before writing,
    indistinguishable from a stale one."""
    target = tmp_path / "s0_T5000_control_007"
    paths = RunPaths(target)
    assert not target.exists()
    paths.write_json("config.json", {"ok": True})
    assert target.exists() and (target / "config.json").exists()


def test_run_paths_refuses_a_non_empty_existing_directory(tmp_path):
    """transcript.jsonl and usage.jsonl are append-mode, so a second run writing
    into an existing directory interleaves with the first into a file that still
    parses. Hard error naming the path; no force flag, because moving or
    deleting the old run should be a decision rather than a default."""
    target = tmp_path / "s0_T5000_gate_009"
    RunPaths(target).write_json("verdict.json", {"status": "FAIL"})
    with pytest.raises(FileExistsError, match=str(target)):
        RunPaths(target)
    with pytest.raises(FileExistsError, match="interleave"):
        RunPaths(target)


def test_run_paths_accepts_an_existing_empty_directory(tmp_path):
    """pytest hands out tmp_path already created, and an empty shell from a
    crashed run carries no records to interleave with."""
    target = tmp_path / "empty"
    target.mkdir()
    paths = RunPaths(target)          # must not raise
    paths.append_jsonl("transcript.jsonl", {"kind": "x"})
    assert (target / "transcript.jsonl").exists()


# -- pre-registration compliance ---------------------------------------------

def test_thinking_is_explicitly_disabled(tmp_path):
    """AGENT_PROMPTS.md §3 pins extended thinking off. The SDK default of None
    is not off -- it defers to the CLI, which spent 3,206 thinking tokens on
    pilot run 0. The option has to be set explicitly."""
    agent, _, _ = make_agent(tmp_path)
    opts = agent._options(tmp_path)
    assert opts.thinking == {"type": "disabled"}
    assert opts.thinking is not None          # the defaulting bug, guarded directly


def test_run_id_includes_T_so_reruns_cannot_interleave():
    """transcript.jsonl and usage.jsonl are append-mode, so two runs sharing a
    directory produce one interleaved file that still parses."""
    from experiments.e_agent import make_run_id
    short = make_run_id("s0", "control", 0, 500)
    long = make_run_id("s0", "control", 0, 5000)
    # The model tag joined the id in batch 3; what this guards is unchanged --
    # two sample lengths must not share a directory.
    assert short == "s0_T500_sonnet_control_000"
    assert long == "s0_T5000_sonnet_control_000"
    assert short != long


# -- usage accounting --------------------------------------------------------

def test_usage_row_records_both_paths_and_marks_which_governs(tmp_path):
    """Run 0 showed the two accountings disagreeing in opposite directions on
    input and output, so the row has to say which field governs what, and keep
    the raw per-message blocks: the undercount's mechanism is not diagnosable
    from a sum.

    Driven with a stub rather than a real ResultMessage. _write_usage reaches
    every field through getattr, so this exercises the logging logic without
    depending on the SDK's constructor signature."""
    from types import SimpleNamespace
    agent, _, _ = make_agent(tmp_path)
    h = handlers(agent)["evaluate"]
    call(h, {"features": [0], "signs": [1]})      # produces transcript timestamps

    # Two assistant responses, the second with an output count the sum misses.
    agent._turn_usage = [
        {"input_tokens": 10, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 100, "output_tokens": 2},
        {"input_tokens": 6, "cache_creation_input_tokens": 0,
         "cache_read_input_tokens": 200, "output_tokens": 3},
    ]
    agent._turn_usage_raw = [dict(u) for u in agent._turn_usage]

    msg = SimpleNamespace(
        usage={"input_tokens": 6, "cache_creation_input_tokens": 0,
               "cache_read_input_tokens": 200, "output_tokens": 900},
        model_usage={"claude-sonnet-5": {"outputTokens": 900, "thinkingTokens": 42}},
        total_cost_usd=0.01, num_turns=2, stop_reason="end_turn",
        terminal_reason="completed", is_error=False, subtype="success",
        api_error_status=None)
    agent._write_usage(msg)

    row = json.loads((tmp_path / "usage.jsonl").read_text().splitlines()[-1])

    # Both paths present, neither silently conflated.
    assert row["assistant_summed"]["output_tokens"] == 5          # the undercount, kept raw
    assert row["result_usage"]["output_tokens"] == 900            # authoritative
    assert row["assistant_summed"]["cache_read_input_tokens"] == 300
    assert len(row["assistant_usage_raw"]) == 2                   # unsummed, for diagnosis

    # The row says which governs what.
    a = row["authoritative"]
    assert a["output_tokens"] == "result_usage"
    assert a["cumulative_input"] == "assistant_summed"
    assert "undercounts" in a["note"]

    # Wall clock, first to last transcript timestamp.
    assert row["wall_seconds"] is not None and row["wall_seconds"] >= 0.0
    assert row["first_ts"] <= row["last_ts"]
    assert row["model_usage"]["claude-sonnet-5"]["thinkingTokens"] == 42


def test_wall_seconds_is_none_before_any_transcript_entry(tmp_path):
    from types import SimpleNamespace
    agent, _, _ = make_agent(tmp_path)
    agent._write_usage(SimpleNamespace(usage={}, model_usage=None, total_cost_usd=None,
                                       num_turns=0, stop_reason=None, terminal_reason=None,
                                       is_error=False, subtype=None, api_error_status=None))
    row = json.loads((tmp_path / "usage.jsonl").read_text().splitlines()[-1])
    assert row["wall_seconds"] is None


# -- runner ------------------------------------------------------------------

def test_runner_guards_the_budget_cap():
    """Amendment 4 made count and budget live, so the deferral guard no longer
    fires for them. What replaces it: budget needs a cap, and a cap is
    meaningless for the other arms."""
    from experiments.e_agent import main
    assert main(["--arm", "budget", "--runs", "1"]) == 64           # missing --budget
    assert main(["--arm", "control", "--budget", "20", "--runs", "1"]) == 64


def test_seed_sequence_is_the_pre_registered_one():
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    expected = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=80)
    np.testing.assert_array_equal(dgp_seeds(80), expected)
    assert len(set(dgp_seeds(80).tolist())) == 80


def test_live_arms_cover_every_arm_after_amendment_4():
    assert set(LIVE_ARMS) == set(ARMS)
