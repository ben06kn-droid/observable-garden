"""The pushed arm (prereg AGENT_PROMPTS.md §2, amendment 7).

This file replaces the placeholder guard the branch used to carry. That test
asserted the arm refused to run while its sentence was a TODO; now that §2
registers the sentence, the assertion inverts: what must be true is that the
registered text is exactly what ships.

The sentence is written out literally below. Everywhere else the rule is to read
the pre-registration rather than retype it, but a tripwire that reads the same
file it is guarding cannot fail -- so here the duplication is the point.
"""
import types

import pytest

from experiments.e_agent import read_prompts, system_prompt_for
from searchers.llm_agent import ARMS, LIVE_ARMS, LLMAgent, tool_names
from tests.test_llm_agent import call, handlers, make_agent, text_of

PUSHED_SENTENCE = (
    "Each evaluate result also reports how your current best compares with a "
    "search-adjusted bar for the class of specifications you can produce."
)


def test_the_registered_sentence_is_what_ships():
    assert read_prompts()["pushed_prompt"] == PUSHED_SENTENCE


def test_no_placeholder_survives():
    """The branch shipped a TODO placeholder until amendment 7 landed."""
    p = read_prompts()["pushed_prompt"]
    assert "TODO" not in p and "placeholder" not in p.lower()
    assert "pushed_is_placeholder" not in read_prompts()


def test_pushed_is_a_live_arm():
    assert "pushed" in ARMS and "pushed" in LIVE_ARMS


def test_pushed_prompt_is_control_plus_exactly_the_sentence():
    prompts = read_prompts()
    control = system_prompt_for("control", M=50, K=40, d=3, prompts=prompts)
    pushed = system_prompt_for("pushed", M=50, K=40, d=3, prompts=prompts)
    assert pushed == control + "\n\n" + PUSHED_SENTENCE


def test_pushed_has_exactly_the_control_tools():
    """§2: "tools as control". `status` belongs to gate alone -- the whole point
    of pushed is that the standing arrives unasked."""
    assert tool_names("pushed") == tool_names("control")
    assert not any(n.endswith("status") for n in tool_names("pushed"))


def _report(best, cv, cleared):
    return types.SimpleNamespace(best_so_far=best, critical_value=cv,
                                 best_so_far_cleared=cleared, sr_is=best)


@pytest.mark.parametrize("best,cv,cleared,expect", [
    (1.20, 0.90, True, " Bar 0.900; best 1.200; margin +0.300; clears."),
    (0.40, 0.90, False, " Bar 0.900; best 0.400; margin -0.500; does not clear."),
])
def test_the_standing_reports_all_four_quantities(tmp_path, best, cv, cleared, expect):
    """§2 names four: critical value, best in-sample Sharpe so far, margin, and
    whether it clears. Margin is against the best, not the call just made."""
    agent, _, _ = make_agent(tmp_path, arm="pushed")
    assert agent._arm_sentence(_report(best, cv, cleared)) == expect


def test_every_evaluate_result_carries_the_standing(tmp_path):
    agent, _, _ = make_agent(tmp_path, arm="pushed")
    h = handlers(agent)["evaluate"]
    for features in ([0], [1], [0, 1]):
        out = text_of(call(h, {"features": features, "signs": [1] * len(features)}))
        assert "Bar " in out and "best " in out and "margin " in out
        assert out.rstrip().endswith(("clears.", "does not clear."))


def test_control_and_gate_results_are_unchanged_by_the_new_arm(tmp_path):
    """The standing must not leak into an arm that did not register it."""
    for arm in ("control", "gate"):
        agent, _, _ = make_agent(tmp_path / arm, arm=arm)
        out = text_of(call(handlers(agent)["evaluate"], {"features": [0], "signs": [1]}))
        assert "Bar " not in out and "margin " not in out
