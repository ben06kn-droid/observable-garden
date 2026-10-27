"""Write assets/example-data.js: every number, hash and log line the mockups show.

Run from the repository root (reads the package and the committed logs; writes only under
app/design/):

    python app/design/make_example_data.py

Nothing on a page is typed by hand. For each example (a committed log on a committed panel):

- `verdict`: `quixote audit --B 500 --seed 0`, plus L_0.90 parsed out of its reasons line, where
  the audit reports it (it has no field of its own).
- `log`: the log, verbatim.
- `tree`: the log re-executed call by call. Each content move's candidates are rescored through the
  class table (the scorer the audit uses) in the grammar's order; a restart's candidates are the
  single features it ranks. The script refuses to write if a kept move does not reproduce the
  logged support and Sharpe exactly.
- `ghosts`: the first three replicates of the certifying null (trigger replay, the draws
  `quixote.certify.three_nulls` makes with seed 0), as the rule each held after every step. The
  script refuses to write if their scores are not the null's.

Also: the planted example's truth file, `quixote power` for the example class, and the paper's one
certificate, parsed from its two committed read files.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from quixote import audit as A
from quixote import classes, panel as P
from quixote.certify import three_nulls
from quixote.grammar import Grammar, Move
from quixote.replay import LoggedPolicy
from quixote.run import replay

REPO = Path(__file__).resolve().parents[2]
EX = REPO / "examples"
B, SEED, N_GHOSTS = 500, 0, 3
CONTENT = ("init", "extend_best", "swap_worst", "flip", "refine")

EXAMPLES = {
    "nothing": {"title": "Nothing to find", "log": "scripted_session.json", "panel": "tiny_panel.npz",
                "blurb": "The scripted searcher on the tiny panel, whose only edge is weak."},
    "planted": {"title": "Planted edge", "log": "planted_session.json", "panel": "tiny_panel_planted.npz",
                "truth": "tiny_panel_planted.json",
                "blurb": "The same searcher on a copy of the panel with a known rule planted in it."},
    "restart": {"title": "A longer search", "log": "restart_session.json", "panel": "tiny_panel.npz",
                "blurb": "A searcher that swaps, flips and restarts, on the tiny panel."},
}
CERT = {
    "read": REPO / "research/runs/french_long_b1/2026-10-11/read.txt",
    "grade": REPO / "research/runs/french_long_b1_grade/2026-10-11-r2/read.txt",
}


def rule_name(support, names):
    return " ".join(("+" if s > 0 else "-") + names[int(k)] for k, s in support)


def as_support(state_support):
    return tuple((int(k), float(s)) for k, s in state_support)


def grow_tree(log, g, names):
    """Every candidate every logged move scored, in the order the harness scored them."""
    support, stem, moves = (), 0, []
    for c in log["calls"]:
        tool, st = c.get("tool"), c.get("state") or {}
        if not c.get("ok"):
            continue
        if tool in CONTENT:
            move = Move(tool, statistic=c["args"].get("statistic", "sharpe"), feature=c["args"].get("feature"))
            before = () if tool == "init" else support
            cands = g.candidates(before, move)
            best = max(range(len(cands)), key=lambda i: cands[i][0])    # first maximum: the grammar's tie order
            kept = " kept:" in c["text"]
            if kept and (cands[best][1] != as_support(st["support"]) or cands[best][0] != st["score"]):
                raise SystemExit(f"{tool}: rescored {cands[best]}, the log says {st['support']} {st['score']}")
            if len(cands) != st["n_candidates"]:
                raise SystemExit(f"{tool}: {len(cands)} candidates rescored, the log says {st['n_candidates']}")
            moves.append({"kind": tool, "stem": stem, "from_ground": tool == "init",
                          "candidates": [{"rule": rule_name(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": best, "kept": kept})
            if kept:
                support = cands[best][1]
        elif tool == "restart":
            stem += 1
            K = len(names)
            cands = [(g.score(((k, 1.0),)), ((k, 1.0),)) for k in range(K)]
            new = as_support(st["support"])
            idx = [ns for _, ns in cands].index(new)
            moves.append({"kind": "restart", "stem": stem, "from_ground": True,
                          "candidates": [{"rule": rule_name(ns, names), "sharpe": float(s)} for s, ns in cands],
                          "chosen": idx, "kept": True})
            support = new
    return moves


def ghost_paths(h, lc, base, ann, names):
    """The first replicates of the trigger null, drawn exactly as three_nulls draws them."""
    session = h.tools.session
    nulls, _ = three_nulls(session.log, lc.spec_class, base, ann, B=N_GHOSTS, seed=SEED, table=h.table)
    pol = LoggedPolicy(session.log, lc.spec_class)
    real = pol.trace(base, ann, score_fn=h.table.scorer(None))
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng(SEED)
    out = []
    for b in range(N_GHOSTS):
        idx = stationary_bootstrap_indices(base.shape[0], L, rng)
        sf = h.table.scorer(idx, demeaned=True)
        pol.trace(S0[idx], ann, frozen=real.actions(), score_fn=sf)      # same calls, same order, as three_nulls
        t = pol.trace(S0[idx], ann, meta_steps=real.n_moves, score_fn=sf)
        pol.trace(S0[idx], ann, score_fn=sf)
        if t.score != nulls.trigger[b]:
            raise SystemExit(f"ghost {b}: {t.score} is not the null's {nulls.trigger[b]}")
        stem, path = 0, []
        for act, sup in zip(t.moves, t.supports):
            if act == "stop":
                continue
            if act == "restart":
                stem += 1
            path.append({"stem": stem, "rule": rule_name(sup, names), "sharpe": float(sf(sup, "sharpe"))})
        out.append({"replicate": b + 1, "score": float(t.score), "filled": bool(t.filled), "path": path})
    return out, L


def example(key, spec):
    log_path, panel_path, class_path = EX / "logs" / spec["log"], EX / "data" / spec["panel"], EX / "class.json"
    log = json.loads(log_path.read_text())
    arrays = P.read(str(panel_path))
    lc = classes.load(str(class_path), arrays, compute_bar=False)
    h = replay(log, arrays, lc)
    base = h.sandbox.base_feature_columns()
    ann = float(np.sqrt(h.panel.periods_per_year))
    names = [str(x) for x in h.panel.feature_names]

    tree = grow_tree(log, Grammar(lc.spec_class, base, ann, score_fn=h.table.scorer(None)), names)
    ghosts, L = ghost_paths(h, lc, base, ann, names)

    v = A.audit_log(log_path, panel_path, class_path, B=B, seed=SEED).to_dict()
    m = re.search(r"L_0\.90 ([+-]?\d+\.\d+)", " ".join(v["reasons"]))
    v["L90"] = float(m.group(1)) if m else None
    v["meaning_cli"] = A.MEANINGS.get(v["status"], "")

    rel = lambda p: str(p.relative_to(REPO))
    out = {
        "key": key, "title": spec["title"], "blurb": spec["blurb"], "log_file": spec["log"],
        "command": f"quixote audit {rel(log_path)} --panel {rel(panel_path)} --class {rel(class_path)} "
                   f"--B {B} --seed {SEED} --verbose",
        "verdict": v, "log": log, "feature_names": names,
        "panel_shape": {"rows": int(arrays["returns"].shape[0]), "assets": int(arrays["returns"].shape[1]),
                        "features": int(arrays["features"].shape[2])},
        "block_length": L, "tree": tree, "ghosts": ghosts,
        "evaluations": sum(len(mv["candidates"]) for mv in tree),
        "stems": 1 + max(mv["stem"] for mv in tree),
    }
    if "truth" in spec:
        truth = json.loads((EX / "data" / spec["truth"]).read_text())
        if truth["panel_sha256"] != log["panel_sha256"]:
            raise SystemExit("the truth file is not the planted panel's")
        sup = tuple((names.index(r[1:]), 1.0 if r[0] == "+" else -1.0) for r in truth["planted_rule"])
        truth["insample_sharpe"] = float(h.table.sharpe(sup))
        planted = rule_name(sup, names)
        truth["evaluated"] = any(c["rule"] == planted or set(c["rule"].split()) == set(planted.split())
                                 for mv in tree for c in mv["candidates"])
        out["truth"] = truth
    return out, h


def certificate():
    read, grade = CERT["read"].read_text(), CERT["grade"].read_text()

    def num(pat, text):
        m = re.search(pat, text, re.S)
        if not m:
            raise SystemExit(f"certificate: {pat!r} not found")
        return m.group(1)

    t1 = read[read.index("test1_stream_d1"):read.index("test2_stream_d0")]
    t3 = read[read.index("test3_class_d1"):]
    g1 = grade[grade.index("(1) the Sancho stream, d = 1"):grade.index("(2) the Sancho stream")]
    return {
        "panel": "French 49 industries",
        "insample": num(r"; (\d{4}-\d\d-\d\d \.\. \d{4}-\d\d-\d\d),", read).replace(" .. ", " to "),
        "rows": int(num(r"rows (\d+);", t1)),
        "statistic": num(r"(recency-weighted \(W2, h [\d,]+\))", t1),
        "sharpe": float(num(r"net Sharpe ([+-]?\d+\.\d+); p", t1)),
        "p": float(num(r"; p (\d\.\d+) \(96%", t1)),
        "p_needed": float(num(r"\(96% level iff p < (\d\.\d+);", t1)),
        "L90": float(num(r"weighted L90 ([+-]\d+\.\d+)", t1)),
        "class_p": float(num(r"net Sharpe [+-]?\d+\.\d+; p (\d\.\d+)", t3)),
        "holdout": num(r"holdout (\d{4}-\d\d-\d\d \.\. \d{4}-\d\d-\d\d)", grade).replace(" .. ", " to "),
        "holdout_sharpe": float(num(r"realised holdout net Sharpe \(unweighted\) ([+-]\d+\.\d+)", g1)),
        "holdout_ci": num(r"90% (\[[^\]]+\])", g1),
        "held": "HELD" in num(r"the bound\) [+-]\d+\.\d+; (\w+)", g1),
        "registered": num(r"registered at ([0-9a-f]{40})", read),
        "grading_registered": num(r"registered at ([0-9a-f]{40})", grade),
        "files": [str(CERT["read"].relative_to(REPO)), str(CERT["grade"].relative_to(REPO))],
        "note_map_row": 34,
    }


def main():
    exs, h = {}, None
    for key, spec in EXAMPLES.items():
        exs[key], hh = example(key, spec)
        h = h or hh
        v = exs[key]["verdict"]
        print(f"{key}: {v['status']}, p {v['p_replay']:.4f}, L90 {v['L90']}, "
              f"{exs[key]['evaluations']} evaluations on {exs[key]['stems']} stem(s)")

    years = round(h.table.T / h.panel.periods_per_year, 3)
    size = exs["nothing"]["verdict"]["class_size"]
    power = json.loads(subprocess.run([sys.executable, "-m", "quixote.cli", "power", "--years", str(years), "--size",
                                       str(size), "--json"], check=True, capture_output=True,
                                      text=True, cwd=REPO).stdout)
    power["command"] = f"quixote power --years {years} --size {size}"

    data = {"source": "app/design/make_example_data.py, from the committed logs and read files",
            "examples": exs, "power": power, "certificate": certificate()}
    out = Path(__file__).parent / "assets" / "example-data.js"
    out.parent.mkdir(exist_ok=True)
    out.write_text("// Generated by app/design/make_example_data.py. Do not edit by hand.\n"
                   "window.QX = " + json.dumps(data, indent=1) + ";\n")
    print(f"wrote {out.relative_to(REPO)}; certificate p {data['certificate']['p']}, "
          f"held {data['certificate']['held']}")


if __name__ == "__main__":
    main()
