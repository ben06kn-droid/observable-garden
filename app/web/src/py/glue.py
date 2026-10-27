"""The Python the gate's Web Worker runs under Pyodide. Nothing here prices anything: it registers
the two stand-ins, reads the search back from its log for drawing, and calls the package's own
`quixote.audit.audit_log`, the function behind `quixote audit`.

- `STANDINS`: which stand-ins were registered. Each registers only when the real package cannot
  be imported, so under Pyodide both go in (arch has no build; scipy is not shipped) and the
  same code on a desktop changes nothing.
- `search_tree(log, panel, class)`: every candidate every logged move scored, rescored through the
  class table (the scorer the audit uses), in the order the harness scored them; a restart's
  candidates are the single features it ranks. Refuses if a kept move does not reproduce the log.
- `run_audit(...)`: the audit, with the progress callback and the first replicates of the null.
"""
import json

import estimator.block_length as _block_length
import estimator.scipy_lite as _scipy_lite

STANDINS = {"arch": _block_length.install_as_arch(), "scipy": _scipy_lite.install_as_scipy()}

import numpy as np  # noqa: E402

from quixote import audit as A  # noqa: E402
from quixote import classes, panel as P  # noqa: E402
from quixote.grammar import Grammar, Move  # noqa: E402
from quixote.run import ReplayMismatch, replay  # noqa: E402

CONTENT = ("init", "extend_best", "swap_worst", "flip", "refine")


def _rule(support, names):
    return " ".join(("+" if s > 0 else "-") + names[int(k)] for k, s in support)


def _support(state_support):
    return tuple((int(k), float(s)) for k, s in state_support)


def search_tree(log_path, panel_path, class_path):
    log = json.loads(open(log_path).read())
    arrays = P.read(panel_path)
    lc = classes.load(class_path, arrays, compute_bar=False)
    try:
        h = replay(log, arrays, lc)
    except ReplayMismatch as e:
        raise A.AuditRefused(f"the log does not re-execute: {e}") from None
    base = h.sandbox.base_feature_columns()
    g = Grammar(lc.spec_class, base, float(np.sqrt(h.panel.periods_per_year)), score_fn=h.table.scorer(None))
    names = [str(x) for x in h.panel.feature_names]
    support, stem, moves = (), 0, []
    for i, c in enumerate(log["calls"]):
        tool, st = c.get("tool"), c.get("state") or {}
        if not c.get("ok"):
            continue
        if tool in CONTENT:
            move = Move(tool, statistic=(c.get("args") or {}).get("statistic", "sharpe"),
                        feature=(c.get("args") or {}).get("feature"))
            cands = g.candidates(() if tool == "init" else support, move)
            best = max(range(len(cands)), key=lambda j: cands[j][0])
            kept = " kept:" in c["text"]
            if kept and (cands[best][1] != _support(st["support"]) or cands[best][0] != st["score"]):
                raise A.AuditRefused(f"call {i} ({tool}) does not rescore to what the log records")
            moves.append({"kind": tool, "stem": stem, "from_ground": tool == "init", "call": i, "text": c["text"],
                          "candidates": [{"rule": _rule(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": best, "kept": kept})
            if kept:
                support = cands[best][1]
        elif tool == "restart":
            stem += 1
            cands = [(g.score(((k, 1.0),)), ((k, 1.0),)) for k in range(len(names))]
            new = _support(st["support"])
            moves.append({"kind": "restart", "stem": stem, "from_ground": True, "call": i, "text": c["text"],
                          "candidates": [{"rule": _rule(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": [ns for _, ns in cands].index(new), "kept": True})
            support = new
    return json.dumps({"feature_names": names, "moves": moves,
                       "evaluations": sum(len(m["candidates"]) for m in moves),
                       "stems": 1 + max((m["stem"] for m in moves), default=0),
                       "panel_shape": [int(x) for x in arrays["returns"].shape] + [int(arrays["features"].shape[2])]})


def run_audit(log_path, panel_path, class_path, B, seed, replicate_paths, progress):
    """The package's audit. Returns {"result": AuditResult.to_dict()} or {"refused": message}."""
    try:
        r = A.audit_log(log_path, panel_path, class_path, B=int(B), seed=int(seed),
                        progress=(lambda stage, done, total: progress(stage, int(done), int(total))),
                        replicate_paths=int(replicate_paths))
    except A.AuditRefused as e:
        return json.dumps({"refused": str(e)})
    d = r.to_dict()
    paths = d.pop("replicate_paths", None)
    if paths is not None:
        names = None
        try:
            names = [str(x) for x in P.read(panel_path)["feature_names"]]
        except Exception:
            pass
        for p in paths:
            for s in p["steps"]:
                if names:
                    s["rule"] = _rule(s["support"], names)
    return json.dumps({"result": d, "replicate_paths": paths})
