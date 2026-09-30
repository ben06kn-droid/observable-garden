"""Re-grade the agent pilot's stored logs under the corrected replay indexing.

`prereg/unfaithful-searchers.md` amendment 3 item (3) records a defect in
`quixote/replay.py`: `_run_logged` indexed the logged content moves by the global
step counter, which also advances on meta decisions, so after a `restart` the
replay applied the wrong logged move and past the end silently took the fill.
Every identity check on a log whose restart rule fired was affected, which
includes pilot runs.

This re-grades what CAN be re-graded, and reports what cannot.

**What cannot.** The pilot's `session_log` event records `r.move.kind` and not the
move's parameters, so a `flip`'s feature and a `pick`'s statistic and candidate
list are absent from the file. A run containing either cannot be rebuilt: the
replay would re-derive a different search and the re-grade would be measuring the
reconstruction, not the run. Those runs are reported as not re-gradable, which is
itself a finding about the log format.

**The faithfulness gate.** A rebuilt log is only used if replaying it reproduces
the support and score the file recorded. A rebuild that does not is discarded and
reported, because a re-grade off a wrong rebuild is worse than no re-grade.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

# Move kinds that carry no parameters, so a record of the kind alone is enough to
# rebuild the move exactly.
PARAMETERLESS = {"init", "extend_best", "swap_worst", "refine"}
META = {"restart", "stop"}


def rebuildable(records: list[dict]) -> tuple[bool, str]:
    """A log is rebuildable if every record carries its move's parameters, or if
    every move it holds needs none. Runs written after the 2026-09-28 serializer
    fix carry a `move` object and are rebuildable whatever kinds they contain."""
    if all("move" in r for r in records):
        return True, ""
    kinds = {r["kind"] for r in records}
    lost = sorted(kinds - PARAMETERLESS - META)
    if lost:
        return False, ("the log records move kinds without their parameters, and "
                       f"these carry parameters: {', '.join(lost)}")
    return True, ""


def rebuild_log(records: list[dict], declared: list[dict], budget: int | None):
    """A SessionLog carrying the recorded moves, triggers and supports."""
    from quixote.grammar import Move
    from quixote.session import MoveRecord, SessionLog

    log = SessionLog()
    log.declared_trigger_records = [dict(d) for d in declared]
    log.budget = budget
    for r in records:
        m = r.get("move")
        if m:
            move = Move(kind=m["kind"], statistic=m.get("statistic", "sharpe"),
                        feature=m.get("feature"), note=m.get("note", "") or "",
                        among=tuple(m.get("among") or ()),
                        else_statistic=m.get("else_statistic"),
                        choice=m.get("choice"))
        else:
            move = Move(r["kind"])
        support = tuple((int(k), float(s)) for k, s in r["support"])
        log.records.append(MoveRecord(
            step=int(r["step"]), move=move, support_after=support,
            score_after=(None if r["score"] is None else float(r["score"])),
            n_candidates=int(r["n_candidates"] or 0),
            information=None, timestamp=None,
            trigger=r.get("trigger"), trigger_value=r.get("trigger_value"),
            replayable=bool(r.get("replayable", True))))
    return log


def regrade_one(path: Path, table, cls, ann: float, base: np.ndarray) -> dict:
    from quixote.replay import LoggedPolicy, commitment_check, integrity_check

    d = json.loads(path.read_text())
    sl = [e for e in d["events"] if e.get("kind") == "session_log"]
    out = {"file": path.name, "run_id": d.get("run_id"),
           "recorded_status": (d.get("verdict") or {}).get("status"),
           "recorded_score": (d.get("verdict") or {}).get("realized_score"),
           "restarts": sum(1 for r in (sl[0]["records"] if sl else [])
                           if r["kind"] == "restart")}
    if not sl:
        out["regradable"] = False
        out["why"] = "no session_log event in the file"
        return out
    records = sl[0]["records"]
    ok, why = rebuildable(records)
    if not ok:
        out["regradable"] = False
        out["why"] = why
        return out

    log = rebuild_log(records, d.get("triggers_predeclared") or [], None)
    score_fn = None if table is None else table.scorer()
    # The faithfulness gate: does replaying the rebuild reproduce the file?
    #
    # Compared against the BEST recorded score, not the last. A replay tracks the
    # best support it reached — that is the submission a search is priced on — and
    # a log's final record is wherever the search happened to stop, which for a
    # log ending in `restart` then `stop` is a WORSE support than its best. The
    # first version of this gate compared against the last record and reported
    # every rebuild as unfaithful, which was the gate being wrong and not the
    # rebuild. The same best-against-last confusion was found once before, in the
    # ETF pilot itself (`prereg/agent-pilot.md`).
    scored = [r for r in records if r.get("score") is not None]
    best = max(scored, key=lambda r: float(r["score"]))
    trace = LoggedPolicy(log, cls).trace(base, ann, score_fn=score_fn,
                                         frozen=LoggedPolicy(log, cls).frozen_actions())
    recorded_support = tuple((int(k), float(s)) for k, s in best["support"])
    out["rebuild_support_matches"] = tuple(trace.support) == recorded_support
    out["rebuild_score"] = float(trace.score)
    out["rebuild_score_gap"] = float(trace.score) - float(best["score"])
    out["recorded_best_score"] = float(best["score"])

    integrity = integrity_check(log, cls, base, ann, score_fn=score_fn)
    commitment = commitment_check(log, cls, base, ann, score_fn=score_fn)
    out.update({
        "regradable": True,
        "integrity_ok": bool(integrity.agrees),
        "commitment_ok": bool(commitment.agrees),
        "integrity_reason": integrity.reason(),
        "commitment_reason": commitment.reason(),
        "realized_support": list(integrity.realized_support),
        "replayed_support": list(integrity.replayed_support),
        "realized_score": float(integrity.realized_score),
        "replayed_score": float(integrity.replayed_score),
    })
    return out


def _simulated_basis(seed: int):
    """The basis for ONE simulated run, rebuilt from its own seed.

    A real panel is the same for every run in a directory; a simulated draw is
    not. So `s0` and `s3` are rebuilt per run, from the seed the run file records,
    and a re-grade that could not reproduce the draw would show up as the
    faithfulness gate failing rather than as a silent mismatch.
    """
    from experiments.agent_cell import simulated_panel

    _data, _cfg, cls, sandbox, dgp = simulated_panel_for(seed)
    return (None, cls, float(np.sqrt(dgp.periods_per_year)),
            sandbox.base_feature_columns())


def simulated_panel_for(seed: int):
    """`agent_cell.simulated_panel` for whichever config the seed belongs to.

    The run file records its panel, so the caller passes it in; this exists so the
    import stays local and `regrade_pilot` does not import the runner at module
    scope.
    """
    from experiments.agent_cell import simulated_panel
    return simulated_panel(_PANEL[0], seed)


_PANEL = ["s0"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="etf", choices=("adr", "etf", "s0", "s3"))
    ap.add_argument("--dir", required=True)
    ap.add_argument("--glob", default=None,
                    help="run-file pattern; defaults to the pilot's and the cell's")
    a = ap.parse_args(argv)

    from environments.class_table import build_class_table
    from garden.spec_class import SubsetClass

    patterns = ([a.glob] if a.glob else
                ["pilot_*_replay_gate_*.json", "cell_*.json"])
    files = sorted({p for pat in patterns for p in Path(a.dir).glob(pat)})

    if a.panel in ("s0", "s3"):
        _PANEL[0] = a.panel
        rows = []
        for path in files:
            seed = int(json.loads(path.read_text()).get("seed"))
            table, cls, ann, base = _simulated_basis(seed)
            rows.append(regrade_one(path, table, cls, ann, base))
    else:
        if a.panel == "etf":
            from environments.real_panel import build_etf_panel
            panel = build_etf_panel()
        else:
            from environments.real_panel import build_adr_panel
            panel = build_adr_panel()
        cls = SubsetClass(max_size=3, signed=True)
        table = build_class_table(panel, cls, a.panel)
        ann = float(np.sqrt(table.annualization))
        base = np.asarray(panel.features, dtype=float)
        rows = [regrade_one(p, table, cls, ann, base) for p in files]

    print(f"RE-GRADE under the corrected indexing — {a.dir}")
    print("=" * 78)
    for r in rows:
        print(f"\n{r['file']}  (restarts in log: {r['restarts']})")
        print(f"  recorded verdict: {r['recorded_status']}")
        if not r["regradable"]:
            print(f"  NOT RE-GRADABLE: {r['why']}")
            continue
        print(f"  rebuild reproduces the file's BEST record: support "
              f"{'yes' if r['rebuild_support_matches'] else 'NO'}, "
              f"score gap {r['rebuild_score_gap']:+.2e}")
        if not r["rebuild_support_matches"] or abs(r["rebuild_score_gap"]) > 1e-9:
            print("  -> DISCARDED: the rebuild does not reproduce the file, so the "
                  "checks below would grade the reconstruction, not the run")
            continue
        print(f"  INTEGRITY  {'PASS' if r['integrity_ok'] else 'FAIL'}")
        print(f"  COMMITMENT {'PASS' if r['commitment_ok'] else 'FAIL'}")
        print(f"  realized {r['realized_support']} score {r['realized_score']:.6f}")
        print(f"  replayed {r['replayed_support']} score {r['replayed_score']:.6f}")
    out = Path(a.dir) / "regrade_2026-09-28.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
