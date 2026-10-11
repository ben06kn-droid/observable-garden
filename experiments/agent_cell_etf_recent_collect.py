"""The agent cell on the ETF recent panel (`prereg/agent-cell-etf-recent.md`): the COLLECTOR.

Reads the committed session logs (one JSON per session, `experiments.agent_backend.RunRecord`
format: `run_id` and `{"events": [...]}`; the harness is `experiments/agent_cell_etf_recent.py`,
whose final event is `{"kind": "submit", "submission": {"arm", "kind", "support", "predict",
"candidate_S_w", "candidate_S_unw", "L90_shown"}}`) and writes the submission list the host grader takes:

    submissions.json = {"sessions": n, "no_submit": [...], "submissions": [
        {"session", "arm", "kind": "rule" | "sancho", "support": [[k, sign], ...] | "sancho",
         "predict": {"mean", "sd", "note"}}, ...]}

and prints its SHA-256 (the grader pins it on its command line). A session is complete iff its
log holds an `end` event; an incomplete session refuses the collection (it is resumed and
finished first, never skipped). A complete session with no `submit` event is `no_submit`:
counted and listed, never replaced. Only {session, arm, kind, support, predict} cross into the
file; nothing else from a log does.

    python -m experiments.agent_cell_etf_recent_collect --logs runs/agent_cell_etf_recent/sessions \\
        --out runs/agent_cell_etf_recent/submissions.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class CollectRefused(RuntimeError):
    pass


def events_of(d: dict, kind: str) -> list[dict]:
    return [e for e in d.get("events", []) if e.get("kind") == kind]


def session_id(path: Path, d: dict) -> str:
    return str(d.get("run_id") or path.stem)


def submission_of(d: dict) -> dict | None:
    """The session's final `submit` event's fields, or None (no_submit)."""
    subs = events_of(d, "submit")
    if not subs or events_of(d, "no_submit"):
        return None
    s = subs[-1].get("submission") or {}
    kind = s.get("kind")
    if kind not in ("rule", "sancho"):
        raise CollectRefused(f"a submit event with kind {kind!r}")
    if s.get("arm") not in ("A", "B"):
        raise CollectRefused(f"a submit event with arm {s.get('arm')!r}")
    support = "sancho" if kind == "sancho" else [[int(k), float(sg)] for k, sg in (s.get("support") or [])]
    if kind == "rule" and not support:
        raise CollectRefused("a rule submission with no support")
    p = s.get("predict") or {}
    if "mean" not in p or "sd" not in p:
        raise CollectRefused("a submission with no stated mean and sd")
    return {"arm": s["arm"], "kind": kind, "support": support,
            "predict": {"mean": float(p["mean"]), "sd": float(p["sd"]), "note": p.get("note")}}


def collect(paths: list[Path]) -> dict:
    subs, no_submit, seen = [], [], set()
    for path in sorted(paths):
        d = json.loads(Path(path).read_text())
        sid = session_id(Path(path), d)
        if sid in seen:
            raise CollectRefused(f"session {sid} appears twice")
        seen.add(sid)
        if not events_of(d, "end"):
            raise CollectRefused(f"session {sid} is incomplete (no end event); finish it first")
        s = submission_of(d)
        if s is None:
            no_submit.append(sid)
        else:
            subs.append({"session": sid, **s})
    return {"sessions": len(seen), "no_submit": no_submit, "submissions": subs}


def write(rec: dict, out: Path) -> str:
    out = Path(out)
    if out.exists():
        raise CollectRefused(f"{out} exists; the list is written once")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1))
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", required=True, help="the directory of committed session logs (*.json)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    paths = sorted(p for p in Path(a.logs).glob("*.json") if p.name != "run_config.json")
    try:
        rec = collect(paths)
        sha = write(rec, Path(a.out))
    except CollectRefused as e:
        raise SystemExit(f"REFUSED: {e}")
    print(f"collected {rec['sessions']} sessions: {len(rec['submissions'])} submissions, "
          f"{len(rec['no_submit'])} no_submit; {a.out} SHA-256 {sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
