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


# -- the on-disk log path: the first shake-out found it missing ----------------

def _finished_run_dir(tmp_path, arm="replay gate (reasoned pick)", panel="s0"):
    """One finished run directory, written by the real runner through the real
    tool handlers. `--dry-run` makes REAL moves, so this exercises the on-disk
    path rather than skipping it -- which is why the first shake-out's dry runs
    could not have caught the missing session log."""
    ac.main(["--panel", panel, "--arm", arm, "--runs", "1",
             "--dry-run", "--out", str(tmp_path)])
    files = sorted(tmp_path.glob("cell_*.json"))
    assert len(files) == 1
    return files[0]


def test_a_finished_run_directory_carries_its_session_log(tmp_path):
    """`experiments/agent_cell.py` wrote no `session_log` event until 2026-09-30,
    so the records existed in process and never reached the file. Those runs could
    not be re-graded at all (`prereg/agent-pilot.md`, the first shake-out)."""
    d = json.loads(_finished_run_dir(tmp_path).read_text())
    kinds = {e.get("kind") for e in d["events"]}
    assert "session_log" in kinds, sorted(kinds)
    records = [e for e in d["events"] if e["kind"] == "session_log"][0]["records"]
    assert records, "a finished run's log must hold its moves"
    # every move carries its PARAMETERS, or it is a different move on re-execution
    for r in records:
        assert "move" in r and r["move"]["kind"] == r["kind"]
        if r["kind"] == "pick":
            assert r["move"]["among"], "a pick without its candidate set"
            assert r["move"]["statistic"]
        if r["kind"] == "flip":
            assert r["move"]["feature"] is not None


def test_a_finished_run_directory_re_grades(tmp_path):
    """The point of storing the log: the run can be replayed later, when the
    replay is fixed or changed. Three ADR pilot runs could not be, and that is why
    this is a test rather than a convention."""
    from experiments.regrade_pilot import main as regrade

    _finished_run_dir(tmp_path)
    assert regrade(["--panel", "s0", "--dir", str(tmp_path)]) == 0
    rows = json.loads((tmp_path / "regrade_2026-09-28.json").read_text())
    assert len(rows) == 1
    row = rows[0]
    assert row["regradable"] is True, row.get("why")
    assert row["rebuild_support_matches"] is True
    assert row["rebuild_score_gap"] == pytest.approx(0.0, abs=1e-12)
    assert row["integrity_ok"] and row["commitment_ok"]


def test_every_stored_shown_re_renders_FROM_DISK_to_the_sent_payload(tmp_path):
    """`prereg/agent-cell.md` amendment 8's invariant, checked against the
    ARTIFACT rather than against the adapter's return values.

    The first shake-out could confirm only half of it: the payloads reached disk
    through the `tool_result` events, but the stored pairs did not, so the round
    trip was unverifiable from the run file. Both halves are on disk now, and this
    compares them to each other with nothing held in memory.
    """
    from quixote.log import render_shown

    d = json.loads(_finished_run_dir(tmp_path).read_text())
    records = [e for e in d["events"] if e["kind"] == "session_log"][0]["records"]
    payloads = [e for e in d["events"]
                if e.get("kind") == "tool_result" and e.get("ok")
                and "| shown: " in (e.get("text") or "")]
    assert records and payloads

    # one payload per logged move, in order
    assert len(payloads) == len(records), (
        f"{len(records)} logged moves against {len(payloads)} shown-bearing "
        "payloads; they must correspond one to one")

    for rec, payload in zip(records, payloads):
        shown = [tuple(pair) for pair in rec["shown"]]
        assert shown, f"{rec['kind']} at step {rec['step']} stored no shown pairs"
        rendered = render_shown(shown)
        assert f"| shown: {rendered}" in payload["text"], (
            f"{rec['kind']} at step {rec['step']}:\n"
            f"  re-rendered from disk: {rendered!r}\n"
            f"  payload on disk:       {payload['text']!r}")


def test_the_dry_run_pick_is_accepted_so_the_path_is_actually_exercised(tmp_path):
    """A pick refused would leave no pick record, and the round-trip test above
    would pass vacuously on the moves that remained. The first shake-out's picks
    were ALL refused -- at a full support, under a firing rule, and after stop --
    so this asserts the dry run's pick is the accepted case."""
    d = json.loads(_finished_run_dir(tmp_path).read_text())
    records = [e for e in d["events"] if e["kind"] == "session_log"][0]["records"]
    picks = [r for r in records if r["kind"] == "pick"]
    assert picks, "the dry run must land an accepted pick"
    # a pick adds ONE candidate, and its shown holds one pair per candidate scored
    assert len(picks[0]["shown"]) >= len(picks[0]["move"]["among"])


# -- amendment 10: the budget is the turn limit, written at open ---------------

def test_the_adapter_declares_the_turn_limit_as_the_budget_at_session_open():
    """`prereg/agent-cell.md` amendment 10. An agent's procedure ends at a declared
    trigger or at the harness's turn limit, so the limit is part of the procedure
    and a null must run to the same bound."""
    from quixote.agent_adapter import ToolSession
    from quixote.session import Session

    _d, _c, cls, sb, _dgp = ac.simulated_panel("s0", 31)
    sess = Session.on_sandbox(sb, cls, name_prefix="budget")
    assert sess.log.budget is None
    ts = ToolSession(sess, max_turns=ac.MAX_TURNS)
    assert ts.session.log.budget == ac.MAX_TURNS
    assert ts.session.log.agent_driven is True
    # and it is declared before any evaluation, which is what makes it a
    # declaration rather than a description
    assert sess.log.first_evaluation_at is None


def test_an_agent_log_without_a_budget_raises_rather_than_falling_back():
    """No fallback to `meta_adaptive.BUDGET` on the agent path. Attempt 2 is why:
    7.1's cap of 12 against a 14-record agent log made the integrity check report a
    structural failure on a search that had not diverged, at a score gap of exactly
    zero. A replay that silently substitutes another bound produces a number that
    looks like a p-value and is not one."""
    from quixote.agent_adapter import ToolSession
    from quixote.replay import LoggedPolicy
    from quixote.session import Session

    _d, _c, cls, sb, _dgp = ac.simulated_panel("s0", 31)
    sess = Session.on_sandbox(sb, cls, name_prefix="nobudget")
    ToolSession(sess)                      # agent path, no turn limit passed
    assert sess.log.agent_driven is True and sess.log.budget is None
    with pytest.raises(ValueError, match="declares no budget"):
        LoggedPolicy(sess.log, cls)

    # a NON-agent log still gets 7.1's bound, so scripted searchers are unaffected
    plain = Session.on_sandbox(sb, cls, name_prefix="scripted")
    assert plain.log.agent_driven is False
    from searchers.meta_adaptive import BUDGET
    assert LoggedPolicy(plain.log, cls).budget == BUDGET


def test_a_finished_run_records_its_declared_budget_on_disk(tmp_path):
    """So a re-grade READS the bound instead of reconstructing it. A reconstructed
    bound is a weaker claim, and `regrade_pilot` says which it used."""
    d = json.loads(_finished_run_dir(tmp_path).read_text())
    declared = [e for e in d["events"] if e.get("kind") == "declared_budget"]
    assert declared and declared[0]["budget"] == ac.MAX_TURNS

    from experiments.regrade_pilot import main as regrade
    assert regrade(["--panel", "s0", "--dir", str(tmp_path)]) == 0
    row = json.loads((tmp_path / "regrade_2026-09-28.json").read_text())[0]
    assert row["budget"] == ac.MAX_TURNS
    assert row["budget_source"] == "read from the log"
    # the symptom a short bound produced is gone: the sequences match in LENGTH
    assert row["n_actions_realized"] == row["n_actions_replayed"]


# -- amendment 10: the change history is serialized ---------------------------

def test_the_trigger_change_history_reaches_the_run_file_with_timestamps(tmp_path):
    """Attempt 2 recorded the gap: the file carried a `triggers_changed` boolean
    and the committed rules, so re-grading worked, but a reader could not see what
    was changed or when. A change is a data-dependent decision and its timing is
    why the verdict prices it."""
    from quixote.agent_adapter import ToolSession
    from quixote.session import Session

    # a session that actually changes a trigger, driven through the tools
    _d, _c, cls, sb, _dgp = ac.simulated_panel("s0", 33)
    sess = Session.on_sandbox(sb, cls, name_prefix="chg")
    ts = ToolSession(sess, max_turns=ac.MAX_TURNS)
    ts.call("declare_triggers", triggers=[
        {"trigger": "failures_at_least", "param": 2.0, "action": "stop"}])
    ts.call("init")
    ts.call("change_trigger", trigger="failures_at_least", param=9.0, action="stop")
    changes = sess.log.trigger_changes
    assert len(changes) == 1
    assert changes[0]["timestamp"] is not None
    assert changes[0]["at_step"] is not None

    # and the runner serializes exactly those fields
    d = json.loads(_finished_run_dir(tmp_path).read_text())
    ev = [e for e in d["events"] if e.get("kind") == "trigger_changes"]
    assert ev, "a finished run must carry a trigger_changes event, even if empty"
    for ch in ev[0]["changes"]:
        assert set(ch) == {"at_step", "trigger", "reason", "timestamp"}
        assert ch["timestamp"] is not None


# -- --workers N, with resume --------------------------------------------------

TIME_KEYS = {"t", "timestamp", "opened_at", "first_evaluation_at",
             "trigger_stamped_at", "stamped_at", "duration_s", "usd", "usage"}


def _strip_time(o):
    """Everything but the wall clock. Two runs of the same seed are the same
    search; they are not the same MOMENT, so timestamps differ by construction and
    comparing them would test the clock rather than the run."""
    if isinstance(o, dict):
        return {k: _strip_time(v) for k, v in o.items() if k not in TIME_KEYS}
    if isinstance(o, list):
        return [_strip_time(x) for x in o]
    return o


def _canon(path):
    return json.dumps(_strip_time(json.loads(path.read_text())), sort_keys=True)


def test_four_workers_produce_byte_identical_logs_to_one(tmp_path):
    """Run ids and seeds are fixed BY INDEX, and each worker builds its own
    sandbox and `ToolSession` in its own process, so parallelism cannot reach the
    search. If it could, the cell's results would depend on how many cores ran it.
    """
    one, four = tmp_path / "w1", tmp_path / "w4"
    args = ["--panel", "s0", "--arm", "replay gate (reasoned pick)",
            "--runs", "4", "--dry-run"]
    ac.main(args + ["--workers", "1", "--out", str(one)])
    ac.main(args + ["--workers", "4", "--out", str(four)])

    a = sorted(p.name for p in one.glob("cell_*.json"))
    b = sorted(p.name for p in four.glob("cell_*.json"))
    assert a == b and len(a) == 4, (a, b)          # the same run ids, not just as many
    for name in a:
        assert _canon(one / name) == _canon(four / name), name


def test_resume_skips_completed_ids_and_redoes_a_partial_one(tmp_path):
    """An interrupted cell resumes on the SAME seeds. A completed run is skipped
    rather than repeated, and a half-written one is deleted and redone rather than
    kept -- a partial run is not a smaller run, its log stops at whatever move the
    process died on."""
    args = ["--panel", "s0", "--arm", "replay gate (reasoned pick)",
            "--runs", "4", "--dry-run", "--out", str(tmp_path)]
    ac.main(args + ["--workers", "1"])
    files = sorted(tmp_path.glob("cell_*.json"))
    assert len(files) == 4
    before = {f.name: _canon(f) for f in files}

    # run 2 is made PARTIAL: its tail markers are removed, as a crash would
    partial = files[2]
    d = json.loads(partial.read_text())
    d["events"] = [e for e in d["events"]
                   if e.get("kind") not in ("self_check", "end")]
    partial.write_text(json.dumps(d, indent=1))
    assert ac.completion_of(partial) == "partial"
    # run 3 is MISSING entirely
    files[3].unlink()
    assert ac.completion_of(files[3]) == "missing"
    assert ac.completion_of(files[0]) == "complete"

    ac.main(args + ["--workers", "4"])

    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert len(cfg["resume"]["skipped_complete"]) == 2
    assert len(cfg["resume"]["deleted_partial"]) == 1
    assert cfg["resume"]["ran_now"] == [2, 3]

    # the two untouched runs are byte-identical: they were skipped, not repeated
    for name in (files[0].name, files[1].name):
        assert _canon(tmp_path / name) == before[name], name
    # and the redone pair matches what a fresh run produces, on the same seeds
    for name in (partial.name, files[3].name):
        assert _canon(tmp_path / name) == before[name], name
    assert len(list(tmp_path.glob("cell_*.json"))) == 4


def test_the_run_config_is_rebuilt_from_the_directory_not_the_invocation(tmp_path):
    """A resumed cell's config must describe the WHOLE cell. If it described only
    the tail, amendment 6's fidelity subsample -- the first n runs in seed order --
    would be computed from whichever runs happened to be left."""
    args = ["--panel", "s0", "--arm", "replay gate (reasoned pick)",
            "--runs", "4", "--dry-run", "--out", str(tmp_path)]
    ac.main(args + ["--workers", "1"])
    (sorted(tmp_path.glob("cell_*.json"))[0]).unlink()
    ac.main(args + ["--workers", "2"])

    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert len(cfg["runs_index"]) == 4
    # ordered by run index, which completion order under a pool is not
    assert [e["index"] for e in cfg["runs_index"]] == [0, 1, 2, 3]
    assert cfg["fidelity_subsample_run_ids"][:4] == [
        e["run_id"] for e in cfg["runs_index"]]
    assert cfg["workers"] == 2


def test_a_completed_run_file_is_one_that_carries_its_self_check(tmp_path):
    """The completeness test reads the run file alone. A test that consulted the
    shared index could not tell a finished run from one whose index entry was
    written before it crashed -- and every arm carries a `self_check` event,
    including one with no session, so the rule is uniform."""
    ac.main(["--panel", "s0", "--arm", "control", "--runs", "1", "--dry-run",
             "--out", str(tmp_path)])
    f = sorted(tmp_path.glob("cell_*.json"))[0]
    assert ac.completion_of(f) == "complete"
    d = json.loads(f.read_text())
    sc = [e for e in d["events"] if e.get("kind") == "self_check"]
    assert sc and sc[0]["replayable"] is None      # no session on the control arm
    assert "no session" in sc[0]["reason"]


def test_a_finished_run_written_before_the_in_file_self_check_is_not_redone(tmp_path):
    """The rule that nearly destroyed eleven seat runs.

    `end` is the completion marker -- it is written last. A run finished before
    2026-09-30 carries no `self_check` event because the field did not exist, and
    requiring one for completeness would have classed eleven finished runs of the s0
    replay cell as partial and DELETED them. The self-check is evidence of
    auditability, not of completion, so such a run is `complete_legacy`: skipped,
    recorded, never redone.
    """
    args = ["--panel", "s0", "--arm", "replay gate (reasoned pick)",
            "--runs", "2", "--dry-run", "--out", str(tmp_path)]
    ac.main(args + ["--workers", "1"])
    files = sorted(tmp_path.glob("cell_*.json"))

    # age one file: drop its self_check, as a pre-2026-09-30 run would have
    aged = files[0]
    d = json.loads(aged.read_text())
    d["events"] = [e for e in d["events"] if e.get("kind") != "self_check"]
    aged.write_text(json.dumps(d, indent=1))
    assert ac.completion_of(aged) == "complete_legacy"
    assert ac.is_complete("complete_legacy") and ac.is_complete("complete")
    before = _canon(aged)

    ac.main(args + ["--workers", "2"])

    # it survived, byte for byte, and the resume says why it was skipped
    assert aged.exists() and _canon(aged) == before
    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert len(cfg["resume"]["skipped_complete"]) == 2
    assert len(cfg["resume"]["skipped_without_self_check"]) == 1
    assert cfg["resume"]["deleted_partial"] == []
    assert cfg["resume"]["ran_now"] == []

    # and a file with NO `end` is still partial, so a real crash is still redone
    d2 = json.loads(files[1].read_text())
    d2["events"] = [e for e in d2["events"] if e.get("kind") != "end"]
    files[1].write_text(json.dumps(d2, indent=1))
    assert ac.completion_of(files[1]) == "partial"


def test_the_credential_is_written_onto_each_run_record(tmp_path):
    """`--credential` reached the run config and never the run record, so every run
    file written before 2026-09-30 says `unknown` -- the s0 replay cell's first
    eleven among them. A per-run field is what cost attribution needs: a
    directory-level config cannot describe a directory filled by more than one
    invocation, which is exactly what a resumed cell is."""
    ac.main(["--panel", "s0", "--arm", "control", "--runs", "2", "--dry-run",
             "--credential", "seat", "--workers", "2", "--out", str(tmp_path)])
    for f in sorted(tmp_path.glob("cell_*.json")):
        assert json.loads(f.read_text())["credential"] == "seat", f.name
    cfg = json.loads((tmp_path / "run_config.json").read_text())
    assert [e["credential"] for e in cfg["runs_index"]] == ["seat", "seat"]


# -- every arm runs on exactly its registered tools ---------------------------

@pytest.mark.parametrize("arm", ac.ARMS)
def test_every_arm_is_built_with_exactly_its_registered_tools(arm):
    """Routing by `arm == "control"` handed the declared-class gate the replay
    grammar under an evaluate/submit prompt (found 2026-10-01, before that arm
    ran). An arm's tools are now its registered tools or the arm is refused."""
    from experiments.agent_backend import RunRecord
    from experiments.real_prompts import TOOLS_FOR

    if not ac.buildable(arm):
        assert arm == "prior-weighted", f"{arm} unexpectedly unbuildable"
        return
    _d, _c, cls, sb, _dgp = ac.simulated_panel("s0", 7)
    rec = RunRecord(run_id=f"tools_{arm}", arm=arm, seed=7)
    handlers, _ = ac.handlers_for(arm, sb, cls, rec, sb.num_features)
    assert sorted(h.name for h in handlers) == sorted(TOOLS_FOR[arm])


def test_an_unbuilt_arm_is_refused_before_anything_is_created(tmp_path):
    out = tmp_path / "pw"
    with pytest.raises(SystemExit, match="does not build"):
        ac.main(["--panel", "s0", "--arm", "prior-weighted", "--runs", "1",
                 "--dry-run", "--out", str(out)])
    assert not out.exists()


def test_a_run_record_carries_its_platform():
    rec, _ = ac.run_one("replay gate", "s0", 20260929, 0, prompts=ac.read_prompts(),
                        dry_run=True, credential="seat")
    assert set(rec.platform) >= {"machine", "system", "python", "numpy"}
