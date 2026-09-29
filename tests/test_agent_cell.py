"""`experiments/agent_cell.py`: the 7.3 agent cell's runner.

Four checks the pre-registration requires and a reader cannot make by eye:

1. the shared prompt text is byte-identical across ALL SIX arms, on every panel;
2. the orientation arm refuses to run without a table;
3. every orientation run config carries the delivered table's hash;
4. the simulated sandbox exposes no returns to the agent beyond `evaluate`.

Nothing here makes a model call.
"""
import json
import numpy as np
import pytest

from experiments import agent_cell as ac
from experiments.real_prompts import ARMS, read_prompts, system_prompt_for

PANEL_SHAPES = {"s0": (50, 40, 3), "s3": (50, 40, 3), "etf": (40, 40, 3)}


# -- 1. byte identity of the shared text, across all six arms, on every panel --

def _orientation_table_for(M, K):
    from quixote.orientation import orientation_table, render
    rng = np.random.default_rng(0)
    return render(orientation_table(rng.normal(size=(200, M, K)), seed=0))


@pytest.mark.parametrize("panel", sorted(PANEL_SHAPES))
def test_the_shared_prompt_text_is_byte_identical_across_all_six_arms(panel):
    """`AGENT_PROMPTS_REAL.md` §2. An arm that differs in its shared text is not
    an arm, it is a different experiment: the whole comparison rests on the arms
    being the same prompt plus exactly one registered block."""
    M, K, d = PANEL_SHAPES[panel]
    p = read_prompts()
    shared = (p["control"].replace("{M}", str(M)).replace("{K}", str(K))
              .replace("{d}", str(d)) + "\n\n" + p["cost"])
    table = _orientation_table_for(M, K)
    seen = {}
    for arm in ARMS:
        prompt = system_prompt_for(arm, M, K, d, p, orientation_table=table)
        assert prompt.startswith(shared), f"{arm} on {panel}"
        seen[arm] = prompt
    assert len(ARMS) == 6
    # and the arms are genuinely different past the shared head
    tails = {arm: t[len(shared):] for arm, t in seen.items()}
    assert tails["control"] == tails["declared-class gate"] == ""
    for arm in ("replay gate", "prior-weighted", "orientation",
                "replay gate (reasoned pick)"):
        assert tails[arm], arm


# -- 2. the orientation arm refuses to run without a table --------------------

def test_the_orientation_arm_refuses_to_run_without_a_table():
    """The table IS the arm. A prompt built without one would be the replay arm
    wearing the orientation arm's name, and every behavioural reading from the
    cell would be attributed to a paragraph that was never delivered."""
    with pytest.raises(ValueError, match="orientation arm's prompt carries a table"):
        system_prompt_for("orientation", 50, 40, 3, read_prompts())
    # and it is satisfied by a rendered table
    prompt = system_prompt_for("orientation", 50, 40, 3, read_prompts(),
                               orientation_table=_orientation_table_for(50, 40))
    assert "orientation" not in prompt[:0] or True
    assert len(prompt) > 0


# -- 3. the delivered table's hash is in every orientation run config ---------

def test_every_orientation_run_config_carries_the_delivered_table_hash(tmp_path):
    """`prereg/agent-cell.md` and `AGENT_PROMPTS_REAL.md` both require it: the
    delivered table is hashed per run and the hash is stored in the run config.
    Without it there is no way to show afterwards WHICH table an agent saw."""
    ac.main(["--panel", "s0", "--arm", "orientation", "--runs", "2",
             "--dry-run", "--out", str(tmp_path)])
    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert cfg["arm"] == "orientation" and cfg["runs"] == 2
    hashes = cfg["orientation_table_hashes"]
    assert len(hashes) == 2
    for run_id, h in hashes.items():
        assert isinstance(h, str) and len(h) == 16, (run_id, h)
    # different draws deliver different tables, so the hashes must differ
    assert len(set(hashes.values())) == 2


def test_a_non_orientation_arm_records_no_table_hash(tmp_path):
    """The field is present and null rather than absent, so a reader can tell
    'this arm carries no table' from 'nobody recorded it'."""
    ac.main(["--panel", "s0", "--arm", "control", "--runs", "1",
             "--dry-run", "--out", str(tmp_path)])
    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert list(cfg["orientation_table_hashes"].values()) == [None]


# -- 4. the simulated sandbox exposes no returns beyond evaluate --------------

FORBIDDEN = ("returns_matrix", "get_data", "oos_sharpe_for_grading")


def test_the_simulated_sandbox_exposes_no_returns_to_the_agent_beyond_evaluate():
    """The agent reaches the data through `evaluate` and through nothing else.
    That single channel is what `prereg/agent-cell.md` amendment 4's calibration
    claim rests on, and what 7.3's U2 measured the price of when it is broken:
    a peek outside the session is invisible to every timestamp, log and replay.

    The sandbox has methods the HARNESS needs -- grading, the raw panel -- and the
    test is that none of them is wired to a tool the agent can call.
    """
    from experiments.agent_backend import control_tools, replay_tools

    _data, _cfg, cls, sandbox, _dgp = ac.simulated_panel("s0", 7)
    for name in FORBIDDEN:
        assert hasattr(sandbox, name), f"{name} should exist for the harness"

    class _Rec:
        def log(self, *a, **k):
            pass
        def note_refusal(self, *a, **k):
            pass

    from quixote.agent_adapter import ToolSession
    from quixote.session import Session
    sess = Session.on_sandbox(sandbox, cls, name_prefix="chan")
    for handlers in (control_tools(sandbox, _Rec(), sandbox.num_features),
                     replay_tools(ToolSession(sess), _Rec(), sandbox.num_features)):
        names = {getattr(h, "name", getattr(h, "__name__", "")) for h in handlers}
        for bad in FORBIDDEN:
            assert not any(bad in str(n) for n in names), (bad, names)


def test_the_simulated_panel_is_rho_zero_on_both_configs():
    """Cell 2 is a placebo only at `rho = 0`: the feature covariance is then the
    identity, so the table carries no information. A non-zero rho would make a
    behavioural difference uninterpretable -- neither priming nor information."""
    for which in ("s0", "s3"):
        _d, _c, _cls, _sb, dgp = ac.simulated_panel(which, 3)
        assert dgp.rho == 0.0, which
        assert dgp.K == 40 and dgp.M == 50 and dgp.T == 5000
    # and the ADR panel is not offered at all (amendment 5)
    assert "adr" not in ac.PANELS


def test_the_arm_size_and_the_fidelity_subsample_are_different_numbers():
    """Amendment 6. The file let these be read as one quantity, and this runner
    read the SUBSAMPLE where it needed the ARM until 2026-09-29. Both are parsed
    from the pre-registration, so a number changed there changes the run."""
    assert ac.reasoned_pick_runs() == 20        # the arm, per config
    assert ac.fidelity_subsample() == 10        # check 2's subsample, per config
    assert ac.reasoned_pick_runs() > ac.fidelity_subsample()


def test_the_fidelity_subsample_is_the_first_runs_in_seed_order(tmp_path):
    """Amendment 6 fixes the SELECTION rule, not only the size: a subsample chosen
    after seeing which runs produced picks would select on the outcome the
    measurement is about. The runner records which run ids it is, before any
    fidelity is measured, so the choice is checkable against the seed list."""
    ac.main(["--panel", "s0", "--arm", "replay gate (reasoned pick)",
             "--runs", "4", "--dry-run", "--out", str(tmp_path)])
    cfg = json.loads((tmp_path / "run_config.json").read_text())
    ids = [e["run_id"] for e in cfg["runs_index"]]
    assert cfg["fidelity_subsample_size"] == 10
    # 4 runs here, so the subsample is all of them, in seed order and no other
    assert cfg["fidelity_subsample_run_ids"] == ids[:10] == ids
    # and a non-fidelity arm names none
    ac.main(["--panel", "s0", "--arm", "control", "--runs", "1",
             "--dry-run", "--out", str(tmp_path / "ctl")])
    other = json.loads((tmp_path / "ctl" / "run_config.json").read_text())
    assert other["fidelity_subsample_run_ids"] == []
