"""The harness end to end: the scripted agent on a tiny panel, its log, and the audit."""
import json

import pytest

from quixote import audit as A
from quixote import panel as P
from quixote.cli import EXAMPLES
from quixote.run import load_agent, run_session
from quixote.verdict import EXIT_CODES

B = 100


@pytest.fixture(scope="module")
def session(tmp_path_factory):
    d = tmp_path_factory.mktemp("run")
    panel = d / "panel.npz"
    P.save(panel, **P.tiny(seed=7, T=300, M=8))
    cls = d / "class.json"
    cls.write_text((EXAMPLES / "class.json").read_text())
    log_path = d / "log.json"
    lines = []
    log = run_session(load_agent("examples.scripted_searcher:Agent"), panel, cls, log_path,
                      B_bar=B, echo=lines.append)
    return {"dir": d, "panel": panel, "cls": cls, "log_path": log_path, "log": log, "echo": lines}


def test_log_records_hashes_and_submission(session):
    log = json.loads(session["log_path"].read_text())
    assert log["format"].startswith("quixote-log/")
    assert log["panel_sha256"] == P.sha256(session["panel"])
    assert log["class_size"] == 128 and log["class_bar"] > 0
    assert log["calls"][0]["tool"] == "declare_triggers"
    assert log["calls"][-1]["tool"] == "submit"
    assert log["submitted"]["support"] and log["n_moves"] >= 1
    assert any("size 128" in s and "bar" in s for s in session["echo"])


def test_audit_returns_a_verdict(session):
    r = A.audit_log(session["log_path"], session["panel"], session["cls"], B=B)
    assert r.status in EXIT_CODES and r.exit_code == EXIT_CODES[r.status]
    assert 0 < r.p_class <= 1 and r.class_size == 128 and r.class_bar > 0
    assert r.submitted_sharpe == pytest.approx(session["log"]["submitted"]["score"])
    assert "verdict:" in A.render(r)
    short, long = A.render(r), A.render(r, verbose=True)
    assert r.reasons and all(f"  - {x}" not in short for x in r.reasons)
    assert f"  - {r.reasons[0]}" in long and "--verbose" not in long


def test_audit_refuses_a_changed_class(session):
    other = session["dir"] / "other_class.json"
    spec = json.loads(session["cls"].read_text())
    spec["max_size"] = 3
    other.write_text(json.dumps(spec))
    with pytest.raises(A.AuditRefused, match="search over classes"):
        A.audit_log(session["log_path"], session["panel"], other, B=B)


def test_audit_refuses_another_panel(session):
    other = session["dir"] / "other_panel.npz"
    P.save(other, **P.tiny(seed=8, T=300, M=8))
    with pytest.raises(A.AuditRefused, match="panel hash"):
        A.audit_log(session["log_path"], other, session["cls"], B=B)


def test_audit_refuses_an_edited_log(session):
    log = json.loads(session["log_path"].read_text())
    for c in log["calls"]:
        if c["tool"] == "init" and "text" in c:
            c["text"] = c["text"] + " (edited)"
    edited = session["dir"] / "edited.json"
    edited.write_text(json.dumps(log))
    with pytest.raises(A.AuditRefused, match="re-execute"):
        A.audit_log(edited, session["panel"], session["cls"], B=B)


def test_bad_agent_spec():
    with pytest.raises(ValueError):
        load_agent("no_colon_here")


def test_quixote_example_prints_a_verdict(capsys):
    from quixote.cli import main
    code = main(["example", "--B", "200"])
    out = capsys.readouterr().out
    assert code in set(EXIT_CODES.values()) and 0 <= code <= 5
    assert "verdict:" in out and "bar" in out
