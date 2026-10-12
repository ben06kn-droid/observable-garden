"""EXPLORATORY. What did agents do when a rule they declared was not enforced?

**Provenance, and it is the whole caveat.** Before 2026-09-30,
`Session.active_trigger_records` keyed declared rules by ACTION alone, so every rule
sharing an action overwrote the previous one and the live session ran under only the
LAST rule declared per action (`prereg/agent-cell.md`, the diagnosis of the 15). The
unenforced rules were still **declared, logged, and visible to the agent in its own
prompt** -- the harness simply never checked them.

That accident is a natural experiment nobody designed: for each unenforced rule we can
ask when it WOULD have fired, using the per-step trigger state the harness stored in
each move's `shown`, and then ask what the agent did at that point. An agent that stops
when its own unenforced rule fires is self-enforcing; one that continues was relying on
the harness.

**This is exploratory and carries NO claim.** The population is whatever pre-fix runs
exist, the rules examined are whichever ones the keying happened to drop, and the agent
never knew which of its rules were live. It is reported as a description of runs already
made, is not a registered readout, and licenses nothing.

    python -m experiments.self_enforcement
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from quixote.triggers import Trigger

ROOT = Path("runs")


def enforced_under_old_rule(declared: list[dict]) -> list[dict]:
    """What the live session actually held: keyed by action, last wins."""
    out: dict = {}
    for r in declared:
        out[r.get("action", "stop")] = r
    return list(out.values())


def analyse_run(path: Path) -> dict | None:
    x = json.loads(path.read_text())
    declared = x.get("triggers_predeclared") or []
    if len(declared) < 2:
        return None                      # nothing was dropped
    live = enforced_under_old_rule(declared)
    live_keys = {(r["kind"], r["param"], r.get("action", "stop")) for r in live}
    unenforced = [r for r in declared
                  if (r["kind"], r["param"], r.get("action", "stop")) not in live_keys]
    if not unenforced:
        return None
    log = [e for e in x["events"] if e.get("kind") == "session_log"]
    if not log:
        return None
    recs = log[0]["records"]

    out = {"run_id": x.get("run_id"), "n_declared": len(declared),
           "n_unenforced": len(unenforced), "rules": [], "stopped_at_end": False}
    out["stopped_at_end"] = any(r["kind"] == "stop" for r in recs)
    for rule in unenforced:
        t = Trigger.from_record(rule)
        first = None
        for i, r in enumerate(recs):
            state = {k: v for k, v in (r.get("shown") or [])}
            if not {"step", "best", "failures", "last_gain"} <= set(state):
                continue
            state.setdefault("budget_left", None)
            fires, value = t.evaluate(state)
            if fires:
                first = (i, r["kind"], float(value))
                break
        entry = {"rule": f"{t.kind}({rule['param']:g})->{t.action}", "fired": first is not None}
        if first is not None:
            i, kind, value = first
            after = recs[i:]
            # did the agent stop AT that point, or take further content moves?
            content_after = sum(1 for r in after
                                if r["kind"] not in ("stop", "restart"))
            entry.update({"first_step": i, "move_at_first": kind,
                          "value": value, "content_moves_after": content_after,
                          "behaviour": "STOPPED at or before the next move"
                          if content_after <= 1 else "CONTINUED"})
        out["rules"].append(entry)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/self_enforcement_exploratory.txt")
    a = ap.parse_args(argv)

    rows, per_arm = [], {}
    for d in sorted(ROOT.glob("*")):
        if not d.is_dir():
            continue
        got = [r for r in (analyse_run(f) for f in sorted(d.glob("cell_*.json"))) if r]
        if got:
            per_arm[d.name] = got
            rows += got

    L = ["EXPLORATORY — the self-enforcement natural experiment", "=" * 78,
         "  PROVENANCE: before 2026-09-30 the live evaluator keyed declared rules by",
         "  ACTION alone, so only the LAST rule per action was enforced. The others",
         "  were declared, logged and in the agent's own prompt, but never checked.",
         "  This asks, for each unenforced rule, when it WOULD have fired on the",
         "  per-step state the harness stored, and what the agent did then.",
         "  EXPLORATORY, NO CLAIM: the population is whatever pre-fix runs exist, the",
         "  rules examined are whichever the keying dropped, and the agent never knew",
         "  which of its rules were live. Licenses nothing.", ""]
    tally = Counter()
    for arm, got in per_arm.items():
        fired = sum(1 for r in got for e in r["rules"] if e["fired"])
        total = sum(len(r["rules"]) for r in got)
        stopped = sum(1 for r in got for e in r["rules"]
                      if e["fired"] and e["behaviour"].startswith("STOPPED"))
        cont = sum(1 for r in got for e in r["rules"]
                   if e["fired"] and e["behaviour"] == "CONTINUED")
        tally["rules"] += total; tally["fired"] += fired
        tally["stopped"] += stopped; tally["continued"] += cont
        L.append(f"  {arm:<30} runs {len(got):>3}  unenforced rules {total:>3}  "
                 f"fired {fired:>3}  stopped {stopped:>3}  continued {cont:>3}")
    L += ["",
          f"  TOTAL: {tally['rules']} unenforced rules across {len(rows)} runs; "
          f"{tally['fired']} would have fired",
          f"  of those that fired: STOPPED {tally['stopped']}, CONTINUED "
          f"{tally['continued']}"]
    if tally["fired"]:
        L.append(f"  self-enforcement share: "
                 f"{tally['stopped'] / tally['fired']:.4f} "
                 f"({tally['stopped']}/{tally['fired']}) — EXPLORATORY, no interval "
                 "and no claim")
    by_rule = Counter()
    for r in rows:
        for e in r["rules"]:
            if e["fired"]:
                by_rule[(e["rule"].split("(")[0], e["behaviour"][:7])] += 1
    L += ["", "  by predicate (fired only):"]
    for (kind, beh), n in sorted(by_rule.items()):
        L.append(f"    {kind:<20} {beh:<8} {n}")
    text = "\n".join(L)
    print(text)
    Path(a.out).write_text(text + "\n")
    print(f"\nwritten to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
