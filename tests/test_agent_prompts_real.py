"""`prereg/AGENT_PROMPTS_REAL.md` §6: the six checks that file asks for.

Every assertion reads the pre-registration, never a copy of it.
"""
import re

import pytest

from experiments.real_prompts import (ARMS, PREREG, TOOLS_FOR, read_prompts,
                                      registered_triggers, system_prompt_for)
from quixote.agent_adapter import CONTENT_TOOLS, META_TOOLS, TOOLS, ToolSession
from quixote.twins import Masking

M, K, D = 40, 40, 3


def _all_prompts():
    return {arm: system_prompt_for(arm, M, K, D) for arm in ARMS}


# 1. the shared text is byte-identical across arms

def test_the_control_prompt_and_cost_sentence_are_byte_identical_across_arms():
    p = read_prompts()
    shared = p["control"].replace("{M}", str(M)).replace("{K}", str(K)) \
                         .replace("{d}", str(D)) + "\n\n" + p["cost"]
    for arm, prompt in _all_prompts().items():
        assert prompt.startswith(shared), arm


def test_the_declared_class_gate_prompt_is_control_byte_for_byte():
    """§2: the gate is applied by the harness after the run and is not described
    to the agent."""
    prompts = _all_prompts()
    assert prompts["declared-class gate"] == prompts["control"]


def test_an_unknown_arm_is_refused_rather_than_defaulted():
    with pytest.raises(ValueError, match="unknown arm"):
        system_prompt_for("pushed", M, K, D)
    with pytest.raises(ValueError, match="unknown arm"):
        system_prompt_for("gate", M, K, D)          # the simulated panel's arm


# 2. each arm adds exactly what the file states

def test_each_arm_adds_exactly_the_registered_block_and_nothing_else():
    p, prompts = read_prompts(), _all_prompts()
    base = prompts["control"]
    assert prompts["prior-weighted"] == base + "\n\n" + p["prior_weighted_suffix"]
    assert prompts["replay gate"] == base + "\n\n" + p["replay_suffix"]


def test_the_prompt_leaves_no_placeholder_unsubstituted():
    for arm, prompt in _all_prompts().items():
        assert not re.findall(r"\{[A-Za-z_]+\}", prompt), arm
    assert f"{M} instruments" in _all_prompts()["control"]


def test_the_short_list_cap_is_the_registered_five():
    """The cap comes from `prereg/prior-weighted-alpha.md`; the prompt states it
    and the session enforces it."""
    assert "up to 5 specifications" in read_prompts()["prior_weighted_suffix"]


# 3. the replay arm's tools and triggers come from the code

def test_the_replay_arms_tools_are_the_adapters_grammar():
    assert TOOLS_FOR["replay gate"] == CONTENT_TOOLS + META_TOOLS + ("predict", "submit")
    for name in TOOLS_FOR["replay gate"]:
        assert name in TOOLS, name
    suffix = read_prompts()["replay_suffix"]
    for move in CONTENT_TOOLS:
        assert f"`{move}`" in suffix, move
    for move in META_TOOLS:
        assert f"`{move}`" in suffix, move


def test_the_replay_arms_trigger_list_is_the_library_generated_from_it():
    """'The trigger list in the prompt is the library in quixote/triggers.py and
    is generated from it in the test, so prompt and library cannot drift.'"""
    suffix = read_prompts()["replay_suffix"]
    named = set(re.findall(r"`([a-z_]+)`", suffix))
    triggers = set(registered_triggers())
    assert triggers <= named, triggers - named
    # and nothing that looks like a trigger but is not one
    for candidate in named:
        if candidate.endswith(("_above", "_at_least", "_at_most")):
            assert candidate in triggers, candidate


def test_the_control_arm_cannot_reach_a_grammar_tool():
    assert set(TOOLS_FOR["control"]) == {"evaluate", "submit"}
    assert not set(TOOLS_FOR["control"]) & (set(CONTENT_TOOLS) | set(META_TOOLS))


# 4-5. what no prompt may say

def test_no_prompt_names_a_threshold_a_p_value_or_a_critical_value():
    """§2: the thresholds are not stated to the agent, so it cannot
    reverse-engineer a decision boundary. §5: no arm is told a null, a critical
    value or a p-value."""
    forbidden = ("0.05", "0.04", "0.01", "alpha", "α", "p-value", "p value",
                 "critical value", "null distribution", "significance")
    for arm, prompt in _all_prompts().items():
        low = prompt.lower()
        for word in forbidden:
            assert word.lower() not in low, (arm, word)


def test_no_prompt_mentions_the_contaminated_feature():
    """`agent-on-real-data.md`: the researcher saw ret1_z's in-sample statistic,
    so a HUMAN declaration of it is inadmissible. The agent must not be nudged
    toward or away from it."""
    for arm, prompt in _all_prompts().items():
        assert "ret1" not in prompt.lower(), arm


def test_the_prompts_do_not_mention_overfitting_or_multiple_testing():
    """`AGENT_PROMPTS.md` §1: 'that absence is the experiment'. The control arm
    carries it, and no arm here reintroduces it."""
    for word in ("overfit", "multiple testing", "multiplicity", "data mining",
                 "data-mining", "look-ahead"):
        assert word not in _all_prompts()["control"].lower(), word


def test_the_deferred_treatments_stay_absent():
    """§5: no status tool, no count sentence, no budget sentence, no twin arm."""
    joined = " ".join(_all_prompts().values()).lower()
    assert "status" not in joined
    assert "evaluated so far" not in joined
    assert "evaluations remaining" not in joined
    for arm in ARMS:
        assert "status" not in TOOLS_FOR[arm]


# 6. masking

def test_the_masked_view_carries_four_structural_fields_and_no_identity():
    """§4: opaque labels, exactly four fields, and the reverse map is the
    harness's."""
    assert Masking.ALLOWED_FIELDS == ("has_home_market", "home_close_et", "sector",
                                      "liquidity_band")
    meta = {"ASML": {"has_home_market": True, "home_close_et": "11:30",
                     "sector": "tech", "liquidity_band": "high"},
            "SPY": {"sector": "broad", "liquidity_band": "high"}}   # ETF: fields absent
    m = Masking.build(["ASML", "SPY"], meta, seed=0)
    view = m.agent_view()
    assert all(re.fullmatch(r"A\d{3}", label) for label in view)
    assert "ASML" not in str(view) and "SPY" not in str(view)
    assert set(view[m.mask("SPY")]) == {"sector", "liquidity_band"}      # absent, not null
    assert all(k in Masking.ALLOWED_FIELDS for v in view.values() for k in v)


def test_an_identifying_field_is_refused_rather_than_filtered():
    with pytest.raises(ValueError, match="identifying fields"):
        Masking.build(["SPY"], {"SPY": {"ticker": "SPY", "sector": "broad"}})
    with pytest.raises(ValueError, match="identifying fields"):
        Masking.build(["SPY"], {"SPY": {"country": "US"}})


def test_the_reverse_map_is_unreachable_from_the_tool_surface():
    """'The agent-facing view holds no reverse map.' The tool surface is the
    adapter's `TOOLS`, and none of them returns identities."""
    m = Masking.build(["ASML", "SPY"], {}, seed=1)
    assert m.unmask(m.mask("SPY")) == "SPY"          # harness-only
    assert "unmask" not in TOOLS
    assert not any("unmask" in t or "identity" in t for t in TOOLS)
    assert "_reverse" not in str(m.agent_view())


def _flat(text: str) -> str:
    """The pre-registration is hard-wrapped, so an assertion about a sentence
    has to ignore where the lines break."""
    return " ".join(text.split())


def test_the_file_states_what_masking_costs():
    """§4 records the cost of masking rather than leaving it to be discovered:
    a prior over named instruments is impossible by design."""
    text = _flat(PREREG.read_text())
    assert "A theory-driven prior over *named* instruments is impossible under masking" in text
    assert "masking is the first suspect and the result is reported as such" in text


def test_feature_names_are_deliberately_not_masked_and_the_file_says_why():
    text = _flat(PREREG.read_text())
    assert "**Feature names are not masked.**" in text
    assert "describe arithmetic rather than identity" in text
