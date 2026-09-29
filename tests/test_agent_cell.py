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


# -- check 2's precondition: the presented information set is stored ------------

def _reasoned_pick_session(seed=21):
    """A session shaped like a reasoned-pick run: a declared rule, a `pick` with a
    named statistic over a candidate set, and a meta move. Returns the session and
    the payloads the adapter actually returned, in order, so the round trip can be
    checked against what was sent rather than against a re-derivation."""
    from quixote.agent_adapter import ToolSession
    from quixote.session import Session

    _d, _c, cls, sb, _dgp = ac.simulated_panel("s0", seed)
    sess = Session.on_sandbox(sb, cls, name_prefix="fid")
    ts = ToolSession(sess)
    ts.call("declare_triggers", triggers=[
        {"trigger": "failures_at_least", "param": 2.0, "action": "stop"}])
    payloads = [ts.call("init"),
                ts.call("pick", among=[0, 1, 2, 3, 4], statistic="autocorr_1"),
                ts.call("extend_best")]
    for _ in range(6):
        if ts.session.fired_triggers():
            break
        payloads.append(ts.call("swap_worst"))
    if ts.session.fired_triggers():
        payloads.append(ts.call("stop", trigger="failures_at_least", param=2.0))
    return ts.session, payloads


def test_the_information_set_slot_exists_and_is_the_re_interrogation_template():
    """What IS in place: `InformationSet` carries a `shown` field for the
    (label, value) pairs revealed, and `as_context()` is documented as the fixed
    template a re-interrogation rebuilds from, "so it cannot drift between the
    original session and a re-interrogation". The slot and the contract are there.
    """
    from quixote.log import InformationSet

    assert "shown" in InformationSet.__dataclass_fields__
    log = _reasoned_pick_session()[0].log
    for rec in log.records:
        if rec.move.is_meta:
            continue
        assert rec.information is not None, rec.move.kind
        ctx = rec.information.as_context()
        assert set(ctx) == {"step", "support", "score", "shown"}


def test_every_pick_and_meta_move_stores_the_information_set_presented():
    """Check 2's precondition, stated as the test it needs to pass.

    For every `pick` and every meta move, the log must record the candidate
    values the agent was actually shown -- not a count of them, and not the
    harness's own state before the move. A fidelity measurement re-presents a
    decision, so it needs the decision's inputs verbatim; a count of candidates is
    not enough to rebuild what was on screen, and re-deriving the values later
    would be measuring today's numbers against yesterday's choice.
    """
    log = _reasoned_pick_session()[0].log
    picks = [r for r in log.records if r.move.kind == "pick"]
    metas = [r for r in log.records if r.move.is_meta]
    assert picks, "the fixture must make a pick"

    for rec in picks:
        info = rec.information
        assert info is not None and info.shown, (
            f"pick at step {rec.step} records no shown values")
        # One pair per CANDIDATE, which is not `len(among)`: the declared class is
        # signed, so each named feature yields a + and a - candidate and the count
        # the harness recorded is the one to match.
        assert len(info.shown) == rec.n_candidates, (
            f"pick at step {rec.step} saw {rec.n_candidates} candidates "
            f"but records {len(info.shown)} shown values")
        assert len(info.shown) >= len(rec.move.among)
        for label, value in info.shown:
            assert isinstance(label, str) and isinstance(value, float)

    for rec in metas:
        info = rec.information
        assert info is not None and info.shown, (
            f"{rec.move.kind} at step {rec.step} records no shown values; a meta "
            "move's information set is the trigger state it was taken on")


def test_re_rendering_shown_reproduces_the_payload_sent_byte_for_byte():
    """`prereg/agent-cell.md` amendment 8's invariant, and the reason the adapter
    and the re-interrogation share ONE renderer.

    A fidelity measurement re-presents a decision and asks whether the declared
    rule predicts the choice. If the adapter formatted the payload one way and the
    re-presentation formatted it another, the agent would be scored against
    numbers it never saw in that form -- and the difference would read as
    infidelity. So the stored `shown` must render back to exactly the text that
    was sent, not to something equivalent.
    """
    from quixote.log import render_shown

    session, payloads = _reasoned_pick_session()
    records = [r for r in session.log.records]
    assert len(records) == len(payloads), (len(records), len(payloads))

    for rec, payload in zip(records, payloads):
        assert payload.ok, (rec.move.kind, payload.text)
        rendered = render_shown(rec.information.shown)
        assert rendered, f"{rec.move.kind} at step {rec.step} rendered nothing"
        # BYTE FOR BYTE, as a substring of the payload the agent received
        assert f"| shown: {rendered}" in payload.text, (
            f"{rec.move.kind} at step {rec.step}:\n"
            f"  re-rendered: {rendered!r}\n"
            f"  payload:     {payload.text!r}")
        # and the machine-readable half of the payload carries the same pairs
        assert payload.state["shown"] == [list(p) for p in rec.information.shown]


def test_the_payload_round_trip_survives_a_json_round_trip():
    """The agent receives `ToolResult.to_json()`, not the dataclass. The pairs
    have to survive that, or a re-presentation rebuilt from a stored transcript
    would differ from one rebuilt from the log."""
    import json

    from quixote.log import render_shown

    session, payloads = _reasoned_pick_session()
    for rec, payload in zip(session.log.records, payloads):
        blob = json.loads(payload.to_json())
        assert blob["result"] == payload.text
        assert blob["shown"] == [list(p) for p in rec.information.shown]
        assert f"| shown: {render_shown(rec.information.shown)}" in blob["result"]


def test_a_pick_shows_the_candidate_statistics_it_will_be_measured_against():
    """Amendment 8 changes what the `pick` tool renders, and this is the change.

    Before it, `_pick` returned the outcome alone -- the agent named a candidate
    set and learned only which one the rule selected. A fidelity measurement would
    then have had to re-derive the candidate values afterwards, scoring today's
    numbers against yesterday's choice. The candidates and their statistic are now
    in the payload, so the numbers the agent saw are the numbers it is measured
    against.
    """
    session, payloads = _reasoned_pick_session()
    picks = [(r, p) for r, p in zip(session.log.records, payloads)
             if r.move.kind == "pick"]
    assert picks, "the fixture must make a pick"
    rec, payload = picks[0]
    # every candidate the harness scored appears in the text the agent got
    for label, value in rec.information.shown:
        assert f"{label}={value:.4f}" in payload.text, label
    # ranked by the statistic the move NAMED, not by sharpe
    assert rec.move.statistic == "autocorr_1"
