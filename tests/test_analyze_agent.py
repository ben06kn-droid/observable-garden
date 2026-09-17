"""experiments/analyze_agent.py — the §5 exclusion rules.

No run directories are read: classify_exclusion takes the loaded dict, so the
rules can be exercised on constructed records.
"""
import pytest

from experiments.analyze_agent import classify_exclusion


def run(**over) -> dict:
    r = {"model": "claude-sonnet-5", "models_seen": ["claude-sonnet-5"],
         "non_mcp_tools": [], "rate_limit_rejected": False, "submitted": True}
    r.update(over)
    return r


# -- only strings naming a model count as model strings -----------------------

@pytest.mark.parametrize("sentinel", ["<synthetic>", "", "unknown", None])
def test_sentinels_in_models_seen_do_not_exclude(sentinel):
    """The SDK reports sentinels such as "<synthetic>" for messages it generates
    itself. Treating one as a model string voided s0_T5000_sonnet_gate_087, a run
    that was otherwise clean."""
    assert classify_exclusion(run(models_seen=["claude-sonnet-5", sentinel])) is None


def test_a_real_second_model_still_excludes():
    """The sentinel rule must not swallow the case it exists to catch."""
    assert classify_exclusion(
        run(models_seen=["claude-sonnet-5", "claude-fable-5-1"])) == "model_string"


def test_no_model_string_at_all_excludes():
    """A run reporting only sentinels never evidenced its assigned model."""
    assert classify_exclusion(run(models_seen=["<synthetic>"])) == "model_string"
    assert classify_exclusion(run(models_seen=[])) == "model_string"


def test_model_is_checked_against_the_runs_own_assignment():
    """Batch 3 crosses arms with two models; comparing every run to one pinned
    string would exclude the entire fable half."""
    assert classify_exclusion(
        run(model="claude-fable-5-1", models_seen=["claude-fable-5-1"])) is None
    assert classify_exclusion(
        run(model="claude-fable-5-1", models_seen=["claude-sonnet-5"])) == "model_string"


# -- the other two rules, in §5's order ---------------------------------------

def test_non_mcp_tool_excludes():
    assert classify_exclusion(run(non_mcp_tools=["Bash"])) == "non_mcp_tool"


def test_rate_limit_excludes_only_when_it_preceded_a_submit():
    assert classify_exclusion(
        run(rate_limit_rejected=True, submitted=False)) == "rate_limit_before_submit"
    assert classify_exclusion(run(rate_limit_rejected=True, submitted=True)) is None
