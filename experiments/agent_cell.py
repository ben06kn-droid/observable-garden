"""7.3's agent cell: one runner, three panels, all six registered arms.

`prereg/agent-cell.md` (amendment 5) fixes which panel carries which cell:

- **cells 1 and 2 — the SIMULATED panel**, `s0` and `s3`, both at `rho = 0`, at
  `experiments/e_agent.py`'s registered configuration (K = 40, M = 50, T = 5,000).
  `s0`'s null is true by construction, which is the only footing cell 1's validity
  claim has; `rho = 0` makes the feature covariance the identity, which is what
  makes cell 2 a placebo.
- **cell 3 — the ETF panel**, which is 6.5 and opens its holdout once.
- **the ADR panel contributes nothing**, and `--panel` offers no such option, so
  the distinction is enforced here rather than remembered.

The session, adapter and prompt machinery is `experiments/agent_backend.py`,
shared with `experiments/agent_pilot.py` — two runners, one backend, so the cell's
runs are comparable with the pilot's instead of coming from a second copy that
drifts. `agent_pilot.py` is frozen at the pilot's behaviour; new work lands here.

    python -m experiments.agent_cell --panel s0 --arm "replay gate" --runs 80 \\
        --credential seat --out runs/agent_cell_s0_replay

`--defer-pricing` writes the complete log and stops before the certifying null;
`experiments/price_runs.py` prices the committed files later, elsewhere, through
the same `certify_log`.

Nothing here decides a rule. The cell's readouts are computed by
`experiments/analyze_agent.py` afterwards.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import json
import re
from dataclasses import replace
from pathlib import Path

import numpy as np

from environments.class_table import build_class_table
from environments.dgp import DGPConfig, calibrate_sigma, generate
from environments.sandbox import Sandbox
from experiments.agent_backend import (
    MAX_TURNS, MODEL, RunRecord, _certify_run, _drive_model, _num,
    _served_model_assertion, control_tools, replay_tools,
)
from experiments.code_state import code_state
from experiments.real_prompts import ARMS, TOOLS_FOR, read_prompts, system_prompt_for
from garden.spec_class import SubsetClass
from quixote.agent_adapter import ToolSession
from quixote.orientation import orientation_table, render, table_hash
from quixote.session import Session

ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = ROOT / "runs" / "agent_cell"
CELL_PREREG = ROOT / "prereg" / "agent-cell.md"
REAL_PREREG = ROOT / "prereg" / "AGENT_PROMPTS_REAL.md"

# The simulated cells, from `experiments/e_agent.py`'s CONFIGS so the two runners
# cannot drift apart on what `s0` and `s3` mean. rho = 0 in both, which cell 2
# depends on.
SIM_CONFIGS = {
    "s0": dict(s=0, K=40, M=50, T=5000, T_oos=1000, oracle_sharpe=None),
    "s3": dict(s=3, K=40, M=50, T=5000, T_oos=1000, oracle_sharpe=1.0),
}
PANELS = ("s0", "s3", "etf")
DEPTH = {"s0": 3, "s3": 3, "etf": 3}

# Seed blocks, one per panel, disjoint from the pilot's (20260924 / 20260925).
SEEDS = {"s0": 20260929, "s3": 20260930, "etf": 20261001}


def _read_prereg(pattern: str, what: str) -> int:
    """One registered number, parsed from the pre-registration rather than copied
    here, so a number changed in the file changes the run."""
    m = re.search(pattern, CELL_PREREG.read_text())
    if not m:
        raise SystemExit(
            f"cannot find {what} in {CELL_PREREG.name}. The runner reads it "
            "rather than holding its own copy; if the wording moved, fix the "
            "pattern here rather than hard-coding the number.")
    return int(m.group(1))


def reasoned_pick_runs() -> int:
    """The reasoned-pick ARM's registered run count: 20 per config.

    `prereg/agent-cell.md` amendment 6. Distinct from the fidelity SUBSAMPLE below,
    which the file previously let be read as the same quantity -- and this runner
    read the subsample where it needed the arm until 2026-09-29.
    `prereg/AGENT_PROMPTS_REAL.md` amendment 3 registers the arm and states no
    count, which is why a reader chasing the number has to be sent here.
    """
    return _read_prereg(
        r"reasoned-pick arm is (\d+) runs on `s0`",
        "the reasoned-pick arm's run count (amendment 6)")


def fidelity_subsample() -> int:
    """Check 2's subsample: the FIRST n runs of each config, IN SEED ORDER.

    Amendment 6 fixes the selection rule as well as the size. A subsample chosen
    after seeing which runs produced picks would select on the outcome the
    measurement is about, so it is determined by the seed order the runner draws
    before anything runs and is checkable afterwards against `run_config.json`.
    """
    return _read_prereg(
        r"pre-registered subsample\s*—\s*(\d+)\s+runs per config",
        "check 2's fidelity subsample size")


def simulated_panel(which: str, seed: int):
    """One simulated draw, through the SAME evaluate path and class table the ETF
    cell uses, so a difference between panels is the panel and not the plumbing."""
    cfg = SIM_CONFIGS[which]
    dgp = DGPConfig(M=cfg["M"], T=cfg["T"], T_oos=cfg["T_oos"], K=cfg["K"],
                    s=cfg["s"], rho=0.0, sigma=1.0, seed=seed)
    if cfg["oracle_sharpe"] is not None:
        dgp = replace(dgp, sigma=calibrate_sigma(cfg["oracle_sharpe"], dgp))
    data = generate(dgp)
    cls = SubsetClass(max_size=DEPTH[which], signed=True)
    sandbox = Sandbox(data, periods_per_year=dgp.periods_per_year, spec_class=cls)
    return data, cfg, cls, sandbox, dgp


def etf_panel():
    from environments.real_panel import build_etf_panel
    from environments.real_sandbox import RealSandbox
    panel = build_etf_panel()
    cls = SubsetClass(max_size=DEPTH["etf"], signed=True)
    table = build_class_table(panel, cls, "etf")
    return panel, cls, RealSandbox(panel, spec_class=cls, class_table=table), table


def orientation_for(X, seed: int) -> tuple[dict, str, str]:
    """The delivered table, its rendering, and its hash.

    `X` is the (T, M, K) FEATURE array and nothing else: `orientation_table(X,
    labels, seed)` takes no returns, no alpha and no threshold, which is the
    structural fact `prereg/agent-cell.md` amendment 2 rests the scoped threshold
    check on. Both panels supply the same shape -- the simulated draw's `x_in` and
    the ETF panel's `features` -- so the table is built identically on each.
    """
    table = orientation_table(np.asarray(X, dtype=float), labels=None, seed=seed)
    return table, render(table), table_hash(table)


def _scripted(rec, handlers, arm: str) -> None:
    """`--dry-run`'s policy: no model call, but REAL moves through the real tool
    handlers, so the on-disk log path is exercised rather than skipped.

    The first shake-out could not have caught the missing session log from a dry
    run, because the dry run made no moves at all. It does now: an anchor, an
    extension, a `pick` while the support still has room, and a stop that fires.
    The pick is deliberately placed early -- that is the condition
    `prereg/AGENT_PROMPTS_REAL.md` amendment 8's sentence of fact states, and a dry
    run that picked at a full support would exercise the refusal rather than the
    acceptance this path exists to test.
    """
    by = {h.name: h for h in handlers}

    def call(name, args):
        return asyncio.run(by[name].handler(args))

    # The control and declared-class-gate arms have no grammar: their tools are
    # `evaluate` and `submit`, so a scripted run evaluates and submits.
    if "declare_triggers" not in by:
        for feats in ([0], [0, 1], [0, 1, 2]):
            call("evaluate", {"features": feats, "signs": [1] * len(feats)})
        call("submit", {})
        return

    call("declare_triggers", {"triggers": [
        {"trigger": "failures_at_least", "param": 2.0, "action": "stop"}]})
    if True:
        call("init", {})
        # a pick with room in the support: one candidate is added, so it is
        # accepted, which is what the on-disk `shown` round trip needs to check
        call("pick", {"among": [0, 1, 2, 3, 4], "statistic": "autocorr_1",
                      "reason": "dry run"})
        call("extend_best", {})
        for _ in range(4):
            call("swap_worst", {})
        call("stop", {"trigger": "failures_at_least", "param": 2.0})
    call("submit", {})


# The tool surfaces this runner can build, keyed by the registered tool set they
# serve. An arm is routed by WHICH TOOLS IT IS REGISTERED FOR in
# `experiments/real_prompts.TOOLS_FOR`, never by its name.
#
# Until 2026-10-01 the routing was `if arm == "control"`, so the declared-class
# gate arm -- registered for `evaluate` and `submit`, exactly as control is --
# would have been handed the replay grammar under a prompt describing
# `evaluate` and `submit`. No such run was made; the defect was caught before
# 6.5's declared-class arm was launched.
_EVALUATE_SUBMIT = frozenset({"evaluate", "submit"})
_GRAMMAR = frozenset(TOOLS_FOR["replay gate"])


def buildable(arm: str) -> bool:
    """Whether this runner can give `arm` exactly its registered tools."""
    return frozenset(TOOLS_FOR[arm]) in (_EVALUATE_SUBMIT, _GRAMMAR)


def handlers_for(arm: str, sandbox, cls, rec, K: int):
    """`(handlers, ToolSession or None)` for `arm`, checked against the registered
    tool table before a single call is made."""
    registered = frozenset(TOOLS_FOR[arm])
    if registered == _EVALUATE_SUBMIT:
        handlers, tools = control_tools(sandbox, rec, K), None
    elif registered == _GRAMMAR:
        session = Session.on_sandbox(sandbox, cls, name_prefix=rec.run_id)
        # the harness's turn limit becomes the declared budget at open
        tools = ToolSession(session, max_turns=MAX_TURNS)
        handlers = replay_tools(tools, rec, K)
    else:
        raise SystemExit(
            f"arm {arm!r} is registered for tools {sorted(registered)}, which this "
            "runner does not build. Refused rather than run on a different surface.")
    built = frozenset(h.name for h in handlers)
    if built != registered:
        raise SystemExit(
            f"arm {arm!r}: built tools {sorted(built)} differ from the registered "
            f"{sorted(registered)} (experiments/real_prompts.TOOLS_FOR)")
    return handlers, tools


def run_one(arm: str, panel_name: str, seed: int, index: int, *,
            prompts: dict, dry_run: bool = False,
            credential: str = "unknown",
            defer_pricing: bool = False) -> tuple[RunRecord, dict]:
    """One run. Returns the record and the per-run config entry.

    `defer_pricing` runs the session and writes the complete log, close-time
    self-check included, and stops there: no certifying null and no verdict. The
    file says so in a `pricing_deferred` event, and `experiments/price_runs.py`
    prices it later from the file through the same `certify_log`.
    """
    if panel_name == "etf":
        panel, cls, sandbox, table = etf_panel()
        X = panel.features
    else:
        data, _cfg, cls, sandbox, _dgp = simulated_panel(panel_name, seed)
        panel, table, X = None, None, data.x_in

    K = sandbox.num_features
    rec = RunRecord(
        run_id=f"cell_{panel_name}_{index}_{arm.replace(' ', '_')}_{seed}",
        arm=arm, seed=seed)
    rec.log("start", arm=arm, seed=seed, panel=panel_name, K=K,
            M=sandbox.num_assets, T=sandbox.num_periods)

    # The orientation arm's table, and its hash, per run.
    otable = orendered = ohash = None
    if arm == "orientation":
        otable, orendered, ohash = orientation_for(X, seed)
        rec.log("orientation_table", hash=ohash, features=len(otable.get("rows", ())))

    prompt = system_prompt_for(arm, sandbox.num_assets, K, DEPTH[panel_name],
                               prompts, orientation_table=orendered)

    handlers, tools = handlers_for(arm, sandbox, cls, rec, K)

    if dry_run:
        _scripted(rec, handlers, arm)
    else:
        _drive_model(arm, rec, handlers, panel, sandbox, K, prompt=prompt,
                     depth=DEPTH[panel_name])

    if tools is not None:
        rec.triggers_predeclared = [dict(t) for t in
                                    tools.session.log.declared_trigger_records]
        rec.triggers_changed = bool(tools.session.log.trigger_changes)
        # The close-time self-check, recorded in the log (the pre-agent-cell list)
        check = tools.session.close()
        # The self-check goes into the RUN FILE, not only into the run config: a
        # resume decides run by run whether a file is complete, and a completeness
        # test that has to consult a shared index cannot tell a finished run from
        # one whose index entry was written before it crashed.
        rec.log("self_check", **check)
        # THE SESSION LOG, ON DISK. The first shake-out found this missing from
        # this runner (`prereg/agent-pilot.md`, 2026-09-29): the records existed in
        # process and never reached the file, so those runs could not be re-graded
        # and amendment 8's round trip could not be audited from the artifact.
        #
        # Every move carries its PARAMETERS and its `shown` payload. Parameters
        # because a `flip` without its feature is a different move on re-execution
        # (the ADR seat runs could not be re-graded for exactly that reason);
        # `shown` because `prereg/agent-cell.md` amendment 8 registers that
        # re-rendering it reproduces the payload sent, byte for byte, and an
        # invariant that cannot be checked from the stored run is not one a reader
        # can rely on.
        # the declared budget, so a re-grade reads the bound the search ran under
        # instead of reconstructing it (amendment 10)
        rec.log("declared_budget", budget=tools.session.log.budget)
        rec.log("session_log", records=[
            {"step": r.step, "kind": r.move.kind, "support": list(r.support_after),
             "score": r.score_after, "n_candidates": r.n_candidates,
             "trigger": r.trigger, "trigger_value": r.trigger_value,
             "replayable": r.replayable, "contradicted": r.contradicted,
             "move": {"kind": r.move.kind, "statistic": r.move.statistic,
                      "feature": r.move.feature, "note": r.move.note,
                      "among": list(r.move.among or ()),
                      "else_statistic": r.move.else_statistic,
                      "choice": r.move.choice},
             "shown": ([list(pair) for pair in r.information.shown]
                       if r.information is not None else []),
             "trigger_stamped_at": r.trigger_stamped_at,
             "information": (r.information.as_context()
                             if r.information is not None else None)}
            for r in tools.session.log.records])
        # The CHANGE HISTORY, with timestamps. Attempt 2 recorded its absence as a
        # gap: the file carried a `triggers_changed` boolean and the committed
        # rules, so re-grading worked, but a reader could not see WHAT was changed
        # or WHEN. A change is a data-dependent decision and its timing is the
        # whole reason it is priced, so the timing belongs in the artifact.
        rec.log("trigger_changes", changes=[
            {"at_step": ch.get("at_step"), "trigger": dict(ch.get("trigger") or {}),
             "reason": ch.get("reason"), "timestamp": ch.get("timestamp")}
            for ch in (tools.session.log.trigger_changes or ())])
        if not rec.submitted:
            support, score = tools.session.submission()
            rec.submitted_support = [[int(k), float(s)] for k, s in support]
            rec.submitted_sharpe = float(score)
        if defer_pricing:
            # The log above is everything pricing needs; the certifying null is
            # the expensive part of a run and the part that needs no model, so it
            # moves to wherever the compute is (prereg/agent-cell.md, 2026-10-01).
            rec.log("pricing_deferred",
                    priced_by="experiments/price_runs.py",
                    reason="the session and its log are written here; the "
                           "certifying null and the class p are computed later "
                           "from this file, by the same certify_log")
        elif not dry_run:
            _certify_run(rec, tools, sandbox, cls, table)
    else:
        # An arm with no session has no self-check, and the field says so rather
        # than being absent -- the resume rule is "a completed file carries a
        # self_check event", and it has to hold for every arm.
        rec.log("self_check", replayable=None, check=None, basis=None,
                reason="this arm has no session, so there is nothing to re-execute",
                error=None)
    # WHICH CREDENTIAL PAID FOR THIS RUN, on the record itself.
    #
    # `--credential` reached the run config and never the run record, so every run
    # file written before 2026-09-30 says `unknown` -- the s0 replay cell's first
    # eleven runs among them, which were seat runs by invocation. A per-run field
    # is what cost attribution needs: a directory-level config cannot describe a
    # directory that was filled by more than one invocation, which is exactly what
    # a resumed cell is.
    rec.credential = credential
    rec.endpoint = _served_model_assertion(rec)
    if not rec.submitted:
        rec.no_submit = True
    rec.log("end", submitted=rec.submitted, no_submit=rec.no_submit)

    entry = {"run_id": rec.run_id, "arm": arm, "panel": panel_name, "seed": seed,
             "orientation_table_hash": ohash,
             "self_check": (tools.session.log.self_check if tools else None)}
    return rec, entry



# -- resume, and the worker pool ---------------------------------------------
#
# Run ids and seeds are fixed BY INDEX: index i always gets `seeds[i]`, drawn from
# the panel's registered block, and the run id contains i. So a resumed run is the
# same run, not a fresh draw that happens to fill a gap -- which is what makes
# resuming legitimate rather than a quiet re-randomisation.


def run_id_for(arm: str, panel: str, seed: int, index: int) -> str:
    return f"cell_{panel}_{index}_{arm.replace(' ', '_')}_{seed}"


def completion_of(path: Path) -> str:
    """`"missing"`, `"partial"`, `"complete"`, or `"complete_legacy"`.

    **`end` is the completion marker.** It is written last, after the self-check,
    the session log and the verdict, so a file carrying it is a run that finished.

    **`complete`** additionally carries a `self_check` event, which is the evidence
    that the run's own log re-executes. **`complete_legacy`** finished but predates
    2026-09-30, when the self-check moved into the run file — it is finished work and
    is **skipped, never redone**.

    That distinction is not pedantry. Requiring `self_check` for completeness would
    have classed **eleven finished seat runs of the s0 replay cell as partial and
    deleted them**, because they were written hours before the field existed. A
    resume rule that destroys completed work to satisfy a newer schema is worse than
    no resume rule; the self-check is evidence of AUDITABILITY, not of completion.

    **Partial** files are deleted and redone. A half-written run is not a smaller
    run: its log stops at whatever move the process died on, and a cell that counted
    it would be reading a search nobody ended.
    """
    if not path.exists():
        return "missing"
    try:
        d = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return "partial"
    kinds = {e.get("kind") for e in d.get("events", [])}
    if "end" not in kinds:
        return "partial"
    return "complete" if "self_check" in kinds else "complete_legacy"


def is_complete(state: str) -> bool:
    """Both complete kinds count as done, so neither is redone on a resume."""
    return state in ("complete", "complete_legacy")


def _task(payload) -> dict:
    """One run, in this process. Module-level so a process pool can pickle it.

    Each call builds its OWN panel, sandbox and `ToolSession` inside `run_one`, so
    workers share no mutable state -- which is why this is a process pool and not a
    thread pool: the sandbox, the grammar and the session are not designed to be
    touched by two searches at once, and a thread pool would make that an
    unreproducible bug rather than an impossible one.
    """
    arm, panel, seed, index, out_dir, dry_run, credential, defer = payload
    prompts = read_prompts()
    rec, entry = run_one(arm, panel, seed, index, prompts=prompts, dry_run=dry_run,
                         credential=credential, defer_pricing=defer)
    path = Path(out_dir) / f"{rec.run_id}.json"
    path.write_text(json.dumps(rec.to_json(), indent=1, default=str))
    entry["index"] = index
    return entry


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=PANELS, required=True)
    ap.add_argument("--arm", choices=ARMS, required=True,
                    help="one of the six registered arms")
    ap.add_argument("--runs", type=int, default=None,
                    help="free; the reasoned-pick arm defaults to its registered "
                         "count read from the pre-registration")
    ap.add_argument("--credential", default="seat", choices=("api", "seat"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--defer-pricing", action="store_true",
                    help="write the complete log and self-check, skip the "
                         "certifying null; price later with "
                         "experiments/price_runs.py")
    ap.add_argument("--out", default=str(RUNS_ROOT))
    ap.add_argument("--workers", type=int, default=1,
                    help="processes, not threads; each builds its own sandbox and "
                         "ToolSession. Completed run ids are skipped and partial "
                         "ones are redone, so an interrupted cell resumes on the "
                         "same seeds.")
    a = ap.parse_args(argv)
    if not buildable(a.arm):
        # before seeds, directories or the pool: nothing is spent on an arm whose
        # registered tools do not exist
        raise SystemExit(
            f"arm {a.arm!r} is registered for {list(TOOLS_FOR[a.arm])}, which this "
            "runner does not build; see prereg/agent-on-real-data.md.")

    runs = a.runs
    if runs is None:
        runs = (reasoned_pick_runs() if a.arm == "replay gate (reasoned pick)"
                else 20)
    # Amendment 6: which runs check 2 re-presents, fixed before anything runs.
    fidelity_n = fidelity_subsample()
    prompts = read_prompts()
    seeds = [int(s) for s in np.random.default_rng(
        SEEDS[a.panel]).integers(0, 2**31 - 1, size=runs)]

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # RESUME. Decide per run id, before anything starts, so the decision is
    # visible in the log of the resumed run rather than inferred afterwards.
    todo, skipped, redone, legacy = [], [], [], []
    for i in range(runs):
        rid = run_id_for(a.arm, a.panel, seeds[i], i)
        path = out / f"{rid}.json"
        state = completion_of(path)
        if is_complete(state):
            skipped.append(rid)
            if state == "complete_legacy":
                legacy.append(rid)
            continue
        if state == "partial":
            path.unlink()
            redone.append(rid)
        todo.append((a.arm, a.panel, seeds[i], i, str(out), a.dry_run,
                     a.credential, a.defer_pricing))
    if skipped:
        print(f"  resuming: {len(skipped)} completed run(s) skipped", flush=True)
    if legacy:
        print(f"  of those, {len(legacy)} predate the in-file self-check "
              "(2026-09-30) and carry none; finished work, not redone", flush=True)
    if redone:
        print(f"  resuming: {len(redone)} partial run(s) deleted and redone: "
              f"{', '.join(r.split('_')[2] for r in redone)}", flush=True)

    workers = max(1, int(a.workers))
    if workers == 1 or len(todo) <= 1:
        fresh = [_task(t) for t in todo]
        for t in todo:
            print(f"  run {t[3]} ({a.arm} on {a.panel}) done", flush=True)
    else:
        from concurrent.futures import ProcessPoolExecutor, as_completed
        fresh = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_task, t): t[3] for t in todo}
            for fut in as_completed(futures):
                fresh.append(fut.result())
                print(f"  run {futures[fut]} ({a.arm} on {a.panel}) done", flush=True)

    # The index is rebuilt from the DIRECTORY, not from this invocation, so a
    # resumed cell's config describes the whole cell and not just the tail of it.
    # Ordered by run index, because amendment 6's fidelity subsample is "the first
    # n in seed order" and completion order is not seed order under a pool.
    entries = []
    for i in range(runs):
        rid = run_id_for(a.arm, a.panel, seeds[i], i)
        path = out / f"{rid}.json"
        if not is_complete(completion_of(path)):
            continue
        d = json.loads(path.read_text())
        sc = [e for e in d["events"] if e.get("kind") == "self_check"]
        ot = [e for e in d["events"] if e.get("kind") == "orientation_table"]
        entries.append({
            "run_id": rid, "arm": a.arm, "panel": a.panel, "seed": seeds[i],
            "index": i,
            "orientation_table_hash": (ot[0].get("hash") if ot else None),
            "credential": d.get("credential"),
            "self_check": ({k: v for k, v in sc[0].items() if k not in ("kind", "t")}
                           if sc else None)})
    records = entries

    config = {
        "panel": a.panel, "arm": a.arm, "runs": runs, "seeds": seeds,
        "seed_block": SEEDS[a.panel], "depth": DEPTH[a.panel],
        "model": MODEL, "max_turns": MAX_TURNS, "credential": a.credential,
        "code_state": code_state(), "dry_run": a.dry_run,
        # this INVOCATION's setting; whether a given run was priced in-line is on
        # the run file itself (a `pricing_deferred` event), since a resumed
        # directory can mix the two
        "defer_pricing": a.defer_pricing,
        "workers": workers,
        # what this invocation did, so a resume is on the record
        "resume": {"skipped_complete": skipped, "deleted_partial": redone,
                   "skipped_without_self_check": legacy,
                   "ran_now": sorted(e["index"] for e in fresh)},
        "sim_config": SIM_CONFIGS.get(a.panel),
        # amendment 5 / AGENT_PROMPTS_REAL.md: the delivered table is hashed per
        # run and the hash is stored in the run config. Null for a non-orientation
        # arm, which carries no table.
        "orientation_table_hashes": {e["run_id"]: e["orientation_table_hash"]
                                     for e in entries},
        "runs_index": entries,
        # amendment 6: check 2's subsample is the FIRST n runs in seed order, so
        # the selection is recorded here rather than made later on the outcome
        "fidelity_subsample_size": fidelity_n,
        "fidelity_subsample_run_ids": [e["run_id"] for e in entries[:fidelity_n]]
                                      if a.arm == "replay gate (reasoned pick)"
                                      else [],
    }
    (out / "run_config.json").write_text(json.dumps(config, indent=1, default=str))
    print(f"\n{len(records)} complete run(s) in {out}; "
          f"{len(fresh)} written by this invocation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
