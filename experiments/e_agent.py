"""Agent-arm pilot runner.

Runs N model-backed searches sequentially, each on a fresh DGP draw, under one
arm and one config. Rotation between arms is the caller's job (AGENT_PROMPTS.md
4 requires arms to alternate within a session); this script does none of it.

    python -m experiments.e_agent --arm control --config s0 --runs 1 --seed-index 0

Stops on the first rate-limit or auth error from the SDK: logs it, writes
`error.json` into the run directory, and exits non-zero. It never retries in a
loop -- a seat that is rate limited stays rate limited, and a retry loop would
burn the window and contaminate the usage accounting.

Everything pinned lives in prereg/AGENT_PROMPTS.md, which is read at runtime
rather than copied here. The verbatim prompt text must come from the
pre-registered file or the byte-identity guarantee of 2 is unenforceable.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden import watch as watch_mod
from garden.spec_class import SubsetClass
from searchers.llm_agent import (
    ARMS, LIVE_ARMS, AgentConfig, AuthFailed, LLMAgent, RateLimited, RunPaths, build_prompt,
)

PREREG = Path(__file__).resolve().parent.parent / "prereg" / "AGENT_PROMPTS.md"
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"

# prereg/AGENT_PROMPTS.md 3, pinned.
MASTER_SEED = 20260916
MODEL = "claude-sonnet-5"
MAX_TURNS = 60
D = 3
CONFIGS = {
    "s0": dict(s=0, K=40, M=50, T=5000, T_oos=1000),
    "s3": dict(s=3, K=40, M=50, T=5000, T_oos=1000),
}


def read_prompts(path: Path = PREREG) -> dict:
    """Extract the verbatim prompt blocks from the pre-registered file.

    Read rather than duplicated: 2 requires byte identity of the shared text
    across arms, which can only be guaranteed if there is one copy."""
    text = path.read_text()
    blocks = re.findall(r"```\n(.*?)\n```", text, re.S)
    if len(blocks) < 2:
        raise ValueError(f"expected at least two fenced blocks in {path}, found {len(blocks)}")
    return {"control": blocks[0].strip(), "gate_suffix": blocks[1].strip()}


def system_prompt_for(arm: str, M: int, K: int, d: int, prompts: dict | None = None) -> str:
    """Control prompt plus exactly what the arm adds (AGENT_PROMPTS.md 2)."""
    prompts = prompts or read_prompts()
    base = build_prompt(prompts["control"], M=M, K=K, d=d)
    if arm == "gate":
        return base + "\n\n" + prompts["gate_suffix"]
    if arm == "budget":
        raise NotImplementedError(
            "the budget arm's appended sentence carries {B}; it is deferred in "
            "AGENT_PROMPTS.md 2 and needs a dated 6 amendment before it can run")
    return base


def dgp_seeds(n: int = 80) -> np.ndarray:
    """AGENT_PROMPTS.md 4: the first n draws from default_rng(MASTER_SEED)."""
    return np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=n)


def make_run_id(config_name: str, arm: str, seed_index: int, T: int) -> str:
    """T is part of the id so a rerun at a different sample length cannot land
    in the same directory.

    It matters more than an ordinary collision would: transcript.jsonl and
    usage.jsonl are append-mode, so two runs sharing a directory interleave
    their records into one file that still parses. Run s0_control_000 (T=500)
    was nearly lost to exactly that before the config moved to T=5000."""
    return f"{config_name}_T{T}_{arm}_{seed_index:03d}"


def run_one(arm: str, config_name: str, seed_index: int, prompts: dict) -> int:
    cfg = CONFIGS[config_name]
    seed = int(dgp_seeds()[seed_index])
    run_id = make_run_id(config_name, arm, seed_index, cfg["T"])
    paths = RunPaths(RUNS_ROOT / run_id)

    dgp = DGPConfig(M=cfg["M"], T=cfg["T"], T_oos=cfg["T_oos"], K=cfg["K"],
                    s=cfg["s"], rho=0.0, sigma=1.0, seed=seed)
    data = generate(dgp)
    spec_class = SubsetClass(max_size=D, signed=True)
    sandbox = Sandbox(data, periods_per_year=dgp.periods_per_year, spec_class=spec_class)

    # The class is opened by the harness, never declared by the agent.
    w = watch_mod.open(sandbox, spec_class, alpha=0.05, reference_sharpe=1.0,
                       B=10_000, seed=seed, agent_view="standing")

    agent_cfg = AgentConfig(
        arm=arm, model=MODEL, max_turns=MAX_TURNS,
        system_prompt=system_prompt_for(arm, cfg["M"], cfg["K"], D, prompts),
        M=cfg["M"], K=cfg["K"], d=D, run_id=run_id,
    )
    paths.write_json("config.json", {
        "run_id": run_id, "arm": arm, "config": config_name, "seed_index": seed_index,
        "dgp_seed": seed, "master_seed": MASTER_SEED, "model": MODEL,
        "max_turns": MAX_TURNS, "spec_class": spec_class.name, "d": D,
        "dgp": {k: v for k, v in vars(dgp).items() if not k.startswith("_")},
        "watch_open": {"status": w.state.status, "class_size": w.state.class_size,
                       "critical_value": w.state.critical_value,
                       "power_at_reference": w.state.power_at_reference},
        "prompt_sha_note": "verbatim text read from prereg/AGENT_PROMPTS.md at runtime",
        "started": time.time(),
    })

    agent = LLMAgent(agent_cfg, paths, seed=seed)
    try:
        agent.run(w)
    except (RateLimited, AuthFailed) as e:
        paths.write_json("error.json", {"kind": type(e).__name__, "detail": str(e),
                                        "ts": time.time()})
        print(f"STOPPING: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    # OOS is computed here, by the harness, after submit -- never by the agent,
    # and never reachable through any tool it can call.
    if agent.submitted_spec is not None:
        paths.write_json("oos.json", {
            "oos_sharpe": sandbox.oos_sharpe_for_grading(agent.submitted_spec),
            "computed_by": "harness, after submit",
        })
    else:
        paths.write_json("no_submit.json", {
            "reason": "run ended without calling submit",
            "max_turns": MAX_TURNS, "n_evaluated": agent._n_eval,
        })
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--arm", choices=ARMS, required=True)
    p.add_argument("--config", choices=sorted(CONFIGS), default="s0")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--seed-index", type=int, default=0)
    a = p.parse_args(argv)

    if a.arm not in LIVE_ARMS:
        print(f"arm {a.arm!r} is deferred in prereg/AGENT_PROMPTS.md 2. The cut design is "
              f"{LIVE_ARMS}; running it needs a dated 6 amendment stating its run count.",
              file=sys.stderr)
        return 3

    prompts = read_prompts()
    for i in range(a.runs):
        idx = a.seed_index + i
        print(f"[{i + 1}/{a.runs}] arm={a.arm} config={a.config} seed_index={idx}", flush=True)
        code = run_one(a.arm, a.config, idx, prompts)
        if code:
            return code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
