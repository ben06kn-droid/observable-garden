"""agent-pilot: 5 model-backed runs on the ADR panel, to shake out the harness.

Pre-registered in `prereg/agent-pilot.md`; prompts and tools in
`prereg/AGENT_PROMPTS_REAL.md`, read at runtime by `experiments/real_prompts.py`.

**This module claims no verdict.** It computes no out-of-sample number, touches
no holdout, and its report says so on its first line. What it measures is
engagement and refusals: moves by type, triggers declared against triggers that
fired, picks accepted against picks contradicted, and the cost of a run.

    python -m experiments.agent_pilot --runs 5
    python -m experiments.agent_pilot --dry-run       # scripted policy, no model

`--dry-run` drives the same tool surface with a scripted policy and no model
call. It is how the harness is exercised without spending the seat, and it is
what the milestone test in `tests/test_agent_adapter.py` already covers for the
adapter; here it also covers the panel, the masking and the report.

The two arms differ in surface, which `AGENT_PROMPTS_REAL.md` §2 records as a
confound for search behaviour and not for the certifier:

- **control** — `evaluate` and `submit`, the agent builds its own specification;
- **replay gate** — the quixote grammar through `quixote/agent_adapter.py`, so
  the harness performs every move and the log is what ran.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from environments.class_table import build_class_table
from environments.real_panel import ADR_HOME, build_adr_panel
from environments.real_sandbox import RealSandbox
from environments.sandbox import Distribution, Specification
from experiments.code_state import code_state
from experiments.real_prompts import TOOLS_FOR, read_prompts, system_prompt_for
from garden.spec_class import SubsetClass
from quixote.agent_adapter import ToolRefused, ToolSession
from quixote.session import Session
from quixote.twins import Masking

# FROZEN at the pilot's behaviour, 2026-09-29. The session, adapter and prompt
# machinery now lives in `experiments/agent_backend.py`, which this imports and
# `experiments/agent_cell.py` also drives -- two runners, one backend, so the
# agent cell's runs are comparable with the pilot's rather than a second copy
# that drifts. New work belongs in `agent_cell.py`, not here.
from experiments.agent_backend import (        # noqa: E402
    CERTIFY_B, MAX_TURNS, MODEL, REFUSAL_KINDS, SERVER_NAME, RunRecord,
    _certify_run, _drive_model, _num, _served_model_assertion, _spec_from,
    classify_refusal, control_tools, replay_tools,
)
# Each panel's registered class. The ADR panel is signed subsets of size <= 2
# over K = 22 (prereg/adr-features.md section 3); the ETF panel is depth 3 over
# K = 40, 82,240 members (prereg/agent-on-real-data.md). Attempts 1-4 ran the ADR
# panel at depth 3 by mistake; recorded in prereg/agent-pilot.md amendment 4.
DEPTH = {"adr": 2, "etf": 3}
D = DEPTH["adr"]
SEED = 20260924                    # agent-pilot.md: the first 5 draws
SEED_ETF = 20260925                # amendment 7, the ETF pilot's own block
ARM_PLAN = ("control", "control", "replay gate", "replay gate", "replay gate")
SERVER_NAME = "garden_pilot"
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs" / "agent_pilot"

def masked_panel(which: str = "adr"):
    """The ADR panel with its instruments masked per `AGENT_PROMPTS_REAL.md` §4.

    Two of the four allowed fields are populated from `ADR_HOME`, which is the
    committed home-market table; `sector` and `liquidity_band` are **absent, not
    null**, because this panel does not carry them, which §4 permits explicitly.

    Masking is close to vacuous on this panel and amendment 1 of
    `AGENT_PROMPTS_REAL.md` says why: no tool here exposes an asset label or a
    date at all. It is applied anyway, so the agent-facing metadata and the
    grading map are the same objects they will be on a panel where it bites.
    """
    if which == "etf":
        # In-sample export only: the holdout is not opened by a pilot
        # (amendment 7). ETF tickers are maskable but carry no home market, so
        # only the two fields that apply cross (AGENT_PROMPTS_REAL.md section 4:
        # a field that does not apply is absent, not null).
        from environments.real_panel import build_etf_panel
        panel = build_etf_panel()
        masking = Masking.build(list(panel.assets), {}, seed=SEED_ETF)
        table = build_class_table(panel, SubsetClass(max_size=DEPTH["etf"], signed=True),
                                  "etf")
        return panel, masking, table
    panel = build_adr_panel()
    meta = {}
    for ticker in panel.assets:
        if ticker in ADR_HOME:
            _, tzname, (hh, mm), _ = ADR_HOME[ticker]
            meta[ticker] = {"has_home_market": True,
                            "home_close_et": f"{hh:02d}:{mm:02d} {tzname}"}
    masking = Masking.build(list(panel.assets), meta, seed=SEED)
    # The declared class as stored net streams. `evaluate` becomes a lookup and
    # the replay resamples rows of the same table, so the null prices the
    # statistic the search optimised (`environments/class_table.py`). Built once
    # and cached; the manifest carries the panel hash.
    table = build_class_table(panel, SubsetClass(max_size=D, signed=True), "adr")
    return panel, masking, table


# -- what a run records ------------------------------------------------------

def _scripted_control(rec, handlers):
    """`--dry-run`'s control policy: three evaluations and a submission."""
    ev, sub = handlers[0], handlers[1]
    for feats in ([0], [0, 2], [0, 2, 4]):
        asyncio.run(ev.handler({"features": feats, "signs": [1] * len(feats)}))
    asyncio.run(sub.handler({"features": [0, 2], "signs": [1, -1], "mean": 0.5, "sd": 0.5}))


def _scripted_replay(rec, handlers):
    """`--dry-run`'s replay policy: a prior, an anchor, two extensions, a stop
    that does not fire, a stop that does, and a submission. It deliberately
    exercises a refusal."""
    by = {h.name: h for h in handlers}
    asyncio.run(by["declare_triggers"].handler(
        {"triggers": [{"trigger": "best_so_far_above", "param": -99.0,
                       "action": "stop"}]}))
    asyncio.run(by["pick_prior"].handler({"features": [1], "signs": [1],
                                          "reason": "dry run"}))
    asyncio.run(by["init"].handler({}))
    asyncio.run(by["extend_best"].handler({}))
    asyncio.run(by["stop"].handler({"trigger": "best_so_far_above", "param": 1e9}))
    asyncio.run(by["stop"].handler({"trigger": "best_so_far_above", "param": -99.0}))
    asyncio.run(by["submit"].handler({}))


def run_one(arm: str, seed: int, panel, masking, index: int,
            dry_run: bool = False, table=None, panel_name: str = "adr") -> RunRecord:
    cls = SubsetClass(max_size=DEPTH[panel_name], signed=True)
    sandbox = RealSandbox(panel, spec_class=cls, class_table=table)
    K = sandbox.num_features
    rec = RunRecord(run_id=f"pilot_{panel_name}_{index}_{arm.replace(' ', '_')}_{seed}",
                    arm=arm, seed=seed)
    rec.log("start", arm=arm, seed=seed, K=K, M=sandbox.num_assets,
            T=sandbox.num_periods, masked_labels=sorted(masking.labels.values()))

    if arm == "control":
        handlers = control_tools(sandbox, rec, K)
        tools = None
    else:
        session = Session.on_sandbox(sandbox, cls, name_prefix=rec.run_id)
        tools = ToolSession(session)
        handlers = replay_tools(tools, rec, K)

    if dry_run:
        (_scripted_control if arm == "control" else _scripted_replay)(rec, handlers)
    else:
        _drive_model(arm, rec, handlers, panel, sandbox, K)

    if tools is not None:
        rec.triggers_predeclared = [dict(t) for t in tools.session.log.declared_trigger_records]
        rec.triggers_changed = bool(tools.session.log.trigger_changes)
        _certify_run(rec, tools, sandbox, cls, table)
        # The move's PARAMETERS are recorded, not only its kind. A log that keeps
        # the kind alone cannot be replayed later: a `flip` without its feature and
        # a `pick` without its statistic and candidate list are different moves on
        # re-execution, so the run cannot be re-graded when the replay is fixed or
        # changed. That is exactly what happened on 2026-09-28 — the ADR seat runs
        # could not be re-graded under the corrected replay indexing, while the ETF
        # runs, whose moves happen to be parameterless, could. See
        # `experiments/regrade_pilot.py`.
        rec.log("session_log", records=[
            {"step": r.step, "kind": r.move.kind, "support": list(r.support_after),
             "score": r.score_after, "n_candidates": r.n_candidates,
             "trigger": r.trigger, "trigger_value": r.trigger_value,
             "replayable": r.replayable,
             "move": {"kind": r.move.kind, "statistic": r.move.statistic,
                      "feature": r.move.feature, "note": r.move.note,
                      "among": list(r.move.among or ()),
                      "else_statistic": r.move.else_statistic,
                      "choice": r.move.choice}}
            for r in tools.session.log.records])
        if not rec.submitted:
            support, score = tools.session.submission()
            rec.submitted_support = [[int(k), float(s)] for k, s in support]
            rec.submitted_sharpe = float(score)
    elif rec.submitted and sandbox.submission is not None:
        rec.submitted_sharpe = float(max((e.sharpe for e in sandbox.transcript),
                                         default=float("nan")))
    rec.endpoint = _served_model_assertion(rec)
    if not rec.submitted:
        rec.no_submit = True
    rec.log("end", submitted=rec.submitted, engagement=rec.engagement,
            no_submit=rec.no_submit)
    return rec


# agent-pilot.md, "What is measured" 6. B is small on purpose: this asks whether
# the null is COMPUTABLE from an agent's log end to end, not what its p-value is,
# and rule 5 forbids the number entering anything.
def report(records: list[RunRecord], dry_run: bool) -> str:
    L = ["agent-pilot — HARNESS SHAKE-OUT AND ENGAGEMENT ONLY. NO VERDICT CLAIM.",
         "=" * 78,
         "prereg/agent-pilot.md rule 5: no number here enters a verdict, a headline or",
         "a figure, and any number quoted elsewhere is quoted as a pilot number with",
         f"n = {len(records)} beside it.",
         "" if not dry_run else "*** DRY RUN: scripted policies, no model was called. ***", ""]

    unregistered = [(r.run_id, x) for r in records for x in r.refusals
                    if x["kind"] == "UNREGISTERED"]
    L += ["RULE 1 — harness integrity (the only blocking rule)", "-" * 78]
    if unregistered:
        L.append(f"  FAILS: {len(unregistered)} unregistered refusal(s); each is a defect")
        for run_id, x in unregistered[:10]:
            L.append(f"    {run_id}: [{x['tool']}] {x['message'][:90]}")
    else:
        L.append(f"  holds: every refusal is one of the {len(REFUSAL_KINDS)} registered kinds")
    L.append("")

    L += ["ENGAGEMENT, per run", "-" * 78,
          f"  {'run':<34}{'arm':<13}{'calls':>6}{'moves':>7}{'engag':>8}{'sub':>5}{'$':>8}"]
    for r in records:
        L.append(f"  {r.run_id:<34}{r.arm:<13}{r.n_tool_calls:>6}"
                 f"{sum(r.moves.values()):>7}{r.engagement:>8.2f}"
                 f"{'yes' if r.submitted else 'NO':>5}"
                 f"{(f'{r.usd:.3f}' if r.usd is not None else '-'):>8}")
    L.append("")

    L += ["MOVES BY TYPE", "-" * 78]
    for r in records:
        moves = ", ".join(f"{k} {v}" for k, v in sorted(r.moves.items())) or "none"
        L.append(f"  {r.run_id}: {moves}")
    L += ["", "TRIGGERS: declared vs fired", "-" * 78]
    for r in records:
        if not r.triggers_declared:
            L.append(f"  {r.run_id}: none declared")
            continue
        parts = [f"{k} {r.triggers_fired.get(k, 0)}/{v}"
                 for k, v in sorted(r.triggers_declared.items())]
        L.append(f"  {r.run_id}: " + ", ".join(parts))
    L += ["", "TRIGGERS DECLARED UP FRONT, AND CHANGES", "-" * 78]
    for r in records:
        if r.arm == "control":
            continue
        decl = ", ".join(f"{t['kind']}({t['param']:g})->{t['action']}"
                         for t in r.triggers_predeclared) or "none declared"
        L.append(f"  {r.run_id}: {decl}"
                 + ("   CHANGED (priced as unreplayable)" if r.triggers_changed else ""))
    L += ["", "PICKS: accepted vs contradicted (rejected as declared)", "-" * 78]
    for r in records:
        L.append(f"  {r.run_id}: {r.picks_accepted} accepted, "
                 f"{r.picks_contradicted} contradicted")
    L += ["", "ENDPOINT — which endpoint answered, and did it serve the pinned model?",
          "-" * 78]
    for r in records:
        e = r.endpoint or {}
        L.append(f"  {r.run_id:<40}{e.get('base_url', '?'):<10}"
                 f"{','.join(e.get('models_reported', [])) or 'none reported':<22}"
                 + {"ok": "OK", "mismatch": "MISMATCH — excluded from analysis",
                    "no model called": "no model called (dry run)"}.get(
                        e.get("status"), "unknown"))
    L += ["  §3 excludes a run reporting any other model string; the endpoint is",
          "  recorded so the string's provenance is visible, not just its value.",
          "", "NO_SUBMIT — reached max_turns without submitting (a recorded outcome,",
          "            kept in the run count, not an error)", "-" * 78]
    for arm in sorted({r.arm for r in records}):
        rows = [r for r in records if r.arm == arm]
        k = sum(1 for r in rows if r.no_submit)
        L.append(f"  {arm:<14} {k} of {len(rows)}"
                 + (f"   ({', '.join(r.run_id for r in rows if r.no_submit)})" if k else ""))
    L += ["  Under decision (b) a trigger_is_firing refusal consumes a turn by design:",
          "  the harness holding an agent to its own declared rule costs turns, and",
          "  the turn budget is unchanged.", "",
          "REFUSALS by kind", "-" * 78]
    kinds: dict = {}
    for r in records:
        for x in r.refusals:
            kinds[x["kind"]] = kinds.get(x["kind"], 0) + 1
    L.append("  " + (", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "none"))

    L += ["", "DECLARATIONS", "-" * 78,
          f"  pick_prior used in {sum(1 for r in records if r.prior_pick)} of "
          f"{sum(1 for r in records if r.arm != 'control')} replay-arm runs",
          "  (AGENT_PROMPTS_REAL.md amendment 1: on the ADR panel a zero here is NOT",
          "   evidence about masking — no tool exposes an asset label or a date)"]

    replay = [r for r in records if r.arm != "control"]
    L += ["", "CERTIFYING NULL — computable from the log, end to end?", "-" * 78]
    for r in replay:
        L.append(f"  {r.run_id}: "
                 + {True: "yes", False: "NO", None: "not attempted"}[r.certifying_null_computable])
    specimen = next((r for r in replay if r.verdict), None)
    if specimen:
        v = specimen.verdict
        L += ["", f"SPECIMEN VERDICT BLOCK — {specimen.run_id}", "-" * 78,
              f"  status            {v['status']}   (alpha {v['alpha']})",
              f"  certifying null   {v['certifying_null']}",
              f"  p_certifying      {_num(v['p_certifying'])}   at B = {v['B']}",
              f"  p_frozen          {_num(v['p_frozen'])}   (fixed-sequence replay, the "
              "bracket's liberal end)",
              f"  p_policy          {_num(v['p_policy'])}",
              f"  realized score    {_num(v['realized_score'])}",
              f"  moves             {v['n_moves']}   candidates {v['n_candidates']}",
              f"  fill engaged      {v['fill_engaged']} of {v['fill_replicates']} replicates",
              f"  hand-over share   {_num(v.get('handover_share'))}   "
              f"({v.get('handover_replicates')} replicates where a logged move did "
              "not apply and the fill carried the remainder)",
              f"  unreplayable      {v['unreplayable_decisions'] or 'none'}",
              "  CAVEAT: " + v["basis_caveat"]]
        for reason in v["reasons"]:
            L.append(f"    - {reason}")

    costs = [r.usd for r in records if r.usd is not None]
    if costs:
        L += ["", "COST", "-" * 78,
              f"  mean ${np.mean(costs):.3f} per run against the $0.268 stored mean "
              f"({np.mean(costs) / 0.268:.1f}x), total ${np.sum(costs):.2f}"]
    errs = [(r.run_id, r.error) for r in records if r.error]
    if errs:
        L += ["", "ERRORS", "-" * 78] + [f"  {i}: {e}" for i, e in errs]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--panel", default="adr", choices=("adr", "etf"))
    ap.add_argument("--credential", default="api", choices=("api", "seat"),
                    help="which credential paid for the run; recorded in the index")
    ap.add_argument("--arms", default="all", choices=("all", "replay", "control"),
                    help="re-run only one arm's runs, keeping their registered seeds")
    ap.add_argument("--out", default=str(RUNS_ROOT))
    a = ap.parse_args(argv)

    global D
    D = DEPTH[a.panel]
    seeds = [int(s) for s in np.random.default_rng(
        SEED_ETF if a.panel == "etf" else SEED).integers(0, 2**31 - 1, size=5)]
    panel, masking, table = masked_panel(a.panel)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    wanted = {"all": set(ARM_PLAN),
              "replay": {"replay gate"}, "control": {"control"}}[a.arms]
    records = []
    for i in range(min(a.runs, len(ARM_PLAN))):
        if ARM_PLAN[i] not in wanted:
            continue
        rec = run_one(ARM_PLAN[i], seeds[i], panel, masking, i, dry_run=a.dry_run,
                      table=table, panel_name=a.panel)
        rec.credential = a.credential
        records.append(rec)
        (out / f"{rec.run_id}.json").write_text(json.dumps(rec.to_json(), indent=1,
                                                          default=str))
        print(f"  run {i} ({rec.arm}) done: {rec.n_tool_calls} calls, "
              f"engagement {rec.engagement:.2f}"
              + (f", ${rec.usd:.3f}" if rec.usd else ""), flush=True)

    text = report(records, a.dry_run)
    print("\n" + text, flush=True)
    tag = (f"_{a.panel}" + ("_dry" if a.dry_run else "")
           + ("" if a.arms == "all" else f"_{a.arms}"))
    (out / f"pilot_report{tag}.txt").write_text(text)
    (out / f"pilot_index{tag}.json").write_text(json.dumps(
        {"seeds": seeds, "arms": list(ARM_PLAN[:a.runs]), "model": MODEL,
         "max_turns": MAX_TURNS, "code_state": code_state(), "arms_run": a.arms,
         "panel": a.panel, "depth": DEPTH[a.panel], "credential": a.credential,
         # The served-model assertion, per run (see _served_model_assertion).
         "endpoint": [{"run_id": r.run_id, **(r.endpoint or {})} for r in records],
         "class_table": {"path": table.path, "N": table.N, "T": table.T,
                         "panel_hash": table.panel_hash},
         "masked_labels": masking.labels, "dry_run": a.dry_run}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
