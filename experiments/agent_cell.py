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

Nothing here decides a rule. The cell's readouts are computed by
`experiments/analyze_agent.py` afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
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
from experiments.real_prompts import ARMS, read_prompts, system_prompt_for
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


def run_one(arm: str, panel_name: str, seed: int, index: int, *,
            prompts: dict, dry_run: bool = False) -> tuple[RunRecord, dict]:
    """One run. Returns the record and the per-run config entry."""
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

    if arm == "control":
        handlers, tools = control_tools(sandbox, rec, K), None
    else:
        session = Session.on_sandbox(sandbox, cls, name_prefix=rec.run_id)
        tools = ToolSession(session)
        handlers = replay_tools(tools, rec, K)

    if not dry_run:
        _drive_model(arm, rec, handlers, panel, sandbox, K, prompt=prompt,
                     depth=DEPTH[panel_name])

    if tools is not None:
        rec.triggers_predeclared = [dict(t) for t in
                                    tools.session.log.declared_trigger_records]
        rec.triggers_changed = bool(tools.session.log.trigger_changes)
        # The close-time self-check, recorded in the log (the pre-agent-cell list)
        tools.session.close()
        if not dry_run:
            _certify_run(rec, tools, sandbox, cls, table)
    rec.endpoint = _served_model_assertion(rec)
    if not rec.submitted:
        rec.no_submit = True
    rec.log("end", submitted=rec.submitted, no_submit=rec.no_submit)

    entry = {"run_id": rec.run_id, "arm": arm, "panel": panel_name, "seed": seed,
             "orientation_table_hash": ohash,
             "self_check": (tools.session.log.self_check if tools else None)}
    return rec, entry


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
    ap.add_argument("--out", default=str(RUNS_ROOT))
    a = ap.parse_args(argv)

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
    records, entries = [], []
    for i in range(runs):
        rec, entry = run_one(a.arm, a.panel, seeds[i], i, prompts=prompts,
                             dry_run=a.dry_run)
        records.append(rec)
        entries.append(entry)
        (out / f"{rec.run_id}.json").write_text(
            json.dumps(rec.to_json(), indent=1, default=str))
        print(f"  run {i} ({a.arm} on {a.panel}) done", flush=True)

    config = {
        "panel": a.panel, "arm": a.arm, "runs": runs, "seeds": seeds,
        "seed_block": SEEDS[a.panel], "depth": DEPTH[a.panel],
        "model": MODEL, "max_turns": MAX_TURNS, "credential": a.credential,
        "code_state": code_state(), "dry_run": a.dry_run,
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
    print(f"\nwrote {len(records)} runs and run_config.json to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
