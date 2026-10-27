"""The optional progress callback on `audit_log` and the replay loop only observes.

The browser shows a run's progress; the desktop passes nothing. These hold that passing a
callback changes no number, and that it is called as promised: by stage, at most every
`PROGRESS_EVERY` replicates and once at the end.
"""
from pathlib import Path

from quixote import audit as A
from quixote.certify import PROGRESS_EVERY

EX = Path(__file__).resolve().parents[1] / "examples"
ARGS = (EX / "logs" / "scripted_session.json", EX / "data" / "tiny_panel.npz", EX / "class.json")


def test_progress_changes_nothing_and_reports_by_stage():
    B = 450
    calls = []
    plain = A.audit_log(*ARGS, B=B, seed=0)
    watched = A.audit_log(*ARGS, B=B, seed=0, progress=lambda *c: calls.append(c))
    assert watched.to_dict() == plain.to_dict()

    assert calls[:2] == [("class", 0, B), ("class", B, B)]
    replay = [c for c in calls if c[0] == "replay"]
    assert [c[1] for c in replay] == [200, 400, 450]           # every PROGRESS_EVERY, then the end
    assert all(c[2] == B for c in replay)
    assert PROGRESS_EVERY >= 100


def test_no_callback_is_the_default():
    r = A.audit_log(*ARGS, B=60, seed=0, progress=None)
    assert r.status in A.MEANINGS
