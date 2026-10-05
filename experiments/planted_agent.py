"""7.5 stage 2: agents on planted panels. Built, and refused for real runs until live.

`prereg/planted-edge.md`, "Agent half", amended by "Recorded for stage 2". Per run:
1. a planted panel (`environments/planted_panel`, the pinned X) at one of the agent
   levels **0, 1.0 and 1.5**;
2. shown through the **masked view** (`environments/planted_view.py`): features
   shuffled per panel and labelled F00-F39, instruments relabelled, no dates;
3. searched **on the fly** (`RealSandbox` with no class table), with pricing deferred to
   `experiments/price_runs.py`, which rebuilds the panel and the mask from the seed.

**Arms.**
- `replay gate` and `replay gate (reasoned pick)` use 6.5's registered prompts and
  tools.
- `unsaturable` uses the replay gate's tools and prompt, plus the registered cap
  sentence read from `prereg/planted-edge.md`. It runs with
  `ToolSession(content_cap=3)`, and the replay null enforces the same cap
  (`quixote/replay.py`).
- `prior-weighted` uses 6.5's registered prompt and tools for that arm: `short_list`
  once before any `evaluate`, then `evaluate` and `submit`. It has no grammar session.
  `price_runs` prices its two routes (`prior_weighted`).

**Refused until stage 2 goes live.** The agent seed block is fixed by stage 2's live
commit and `AGENT_SEEDS` stays `None` until then. So this runner makes **dry runs on
design seeds only**: a scripted policy through the real tool handlers, with no model
call and no seat.

    python -m experiments.planted_agent --arm unsaturable --level 1.0 --runs 2 \\
        --seed0 640900 --dry-run --out runs/_dry/planted_agent
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from environments import planted_panel as pp
from environments.planted_view import agent_view
from environments.real_sandbox import RealSandbox
from experiments.agent_backend import (MAX_TURNS, RunRecord, prior_weighted_tools,
                                       replay_tools)
from experiments.agent_cell import (_drive_model, _scripted, _served_model_assertion,
                                    completion_of, is_complete, log_session)
from experiments.real_prompts import TOOLS_FOR, read_prompts, system_prompt_for
from quixote.agent_adapter import ToolSession
from quixote.session import Session

ARMS = ("replay gate", "replay gate (reasoned pick)", "unsaturable", "prior-weighted")
LEVELS = (0.0, 1.0, 1.5)     # nearest-the-bar returned 1.5; 1.0 fills the third slot
CAP = 3
DEPTH = 3
DESIGN = range(640_000, 641_000)
AGENT_SEEDS: range | None = None          # fixed by stage 2's live commit
# THE SHAKE-OUT BLOCK (checked 2026-10-05: no collision). Model-backed runs on these
# seeds are allowed, into runs/_shakeout/ only, and are never read for any rule.
SHAKEOUT = range(632_000, 632_010)
SHAKEOUT_DIR = Path("runs/_shakeout")
PREREG = Path(__file__).resolve().parent.parent / "prereg" / "planted-edge.md"
CAP_HEADING = "### The unsaturable arm's prompt sentence"


def cap_sentence(path: Path = PREREG) -> str:
    """The registered sentence: the first fenced block after its heading, or a refusal."""
    text = path.read_text()
    i = text.find(CAP_HEADING)
    if i < 0:
        raise SystemExit(f"{path.name} has no '{CAP_HEADING}'; the unsaturable arm's "
                         "prompt is not registered")
    m = re.search(r"```\n(.*?)\n```", text[i:], re.S)
    if not m or f"at most {CAP} content moves" not in m.group(1):
        raise SystemExit(f"the registered cap sentence is missing or does not state a cap "
                         f"of {CAP}")
    return m.group(1).strip()


def tool_arm(arm: str) -> str:
    """The registered tool set and base prompt an arm uses."""
    return "replay gate" if arm == "unsaturable" else arm


def prompt_for(arm: str, M: int, K: int, prompts: dict) -> str:
    base = system_prompt_for(tool_arm(arm), M, K, DEPTH, prompts)
    return base + "\n\n" + cap_sentence() if arm == "unsaturable" else base


def run_id_for(arm: str, level: float, seed: int, index: int) -> str:
    return f"cell_planted_{index}_{arm.replace(' ', '_')}_L{level:.1f}_{seed}"


def run_one(arm: str, seed: int, level: float, index: int, *, prompts: dict,
            dry_run: bool, credential: str = "unknown", base=None) -> RunRecord:
    if arm not in ARMS or level not in LEVELS:
        raise SystemExit(f"arm {arm!r} / level {level} is not registered: {ARMS}, {LEVELS}")
    base = pp.load_base() if base is None else base       # the pinned X
    draw = pp.make_draw(base, seed, level)
    view, _mask = agent_view(draw.in_sample, seed)         # the mask stays here
    sandbox = RealSandbox(view, spec_class=pp.CLS)         # on the fly: no class table
    T, M, K = view.features.shape
    cap = CAP if arm == "unsaturable" else None
    rec = RunRecord(run_id=run_id_for(arm, level, seed, index), arm=arm, seed=seed)
    rec.log("start", arm=arm, seed=seed, panel="planted", level=level, K=K, M=M, T=T,
            masked=True, content_cap=cap)
    prompt = prompt_for(arm, M, K, prompts)
    # a neutral prefix: specification names never carry the arm, level or seed
    if arm == "prior-weighted":
        tools = None
        handlers = prior_weighted_tools(sandbox, rec, K, pp.CLS)
    else:
        session = Session.on_sandbox(sandbox, pp.CLS, name_prefix="q")
        tools = ToolSession(session, max_turns=MAX_TURNS, content_cap=cap)
        handlers = replay_tools(tools, rec, K)
    built = frozenset(h.name for h in handlers)
    if built != frozenset(TOOLS_FOR[tool_arm(arm)]):
        raise SystemExit(f"built tools {sorted(built)} are not the registered "
                         f"{sorted(TOOLS_FOR[tool_arm(arm)])}")
    if dry_run:
        rec.log("system_prompt", sha=hashlib.sha256(prompt.encode()).hexdigest()[:16],
                chars=len(prompt))
        _scripted(rec, handlers, tool_arm(arm))
    else:
        _drive_model(tool_arm(arm), rec, handlers, view, sandbox, K, prompt=prompt,
                     depth=DEPTH)
    if tools is not None:
        log_session(rec, tools)
    else:
        rec.log("self_check", replayable=None, check=None, basis=None,
                reason="this arm has no session, so there is nothing to re-execute",
                error=None)
    rec.log("pricing_deferred", priced_by="experiments/price_runs.py",
            reason="planted runs are priced from the file on the pinned X, which "
                   "rebuilds the panel and the mask from the seed")
    rec.credential = credential
    from experiments.code_state import platform_info
    rec.platform = platform_info()
    rec.endpoint = _served_model_assertion(rec)
    if not rec.submitted:
        rec.no_submit = True
    rec.log("end", submitted=rec.submitted, no_submit=rec.no_submit)
    return rec


def check_seeds(seeds, dry_run: bool, out: Path | None = None) -> str:
    """What this invocation is allowed to be: `"dry"` (design seeds, no model),
    `"shakeout"` (model-backed, shake-out seeds, written under runs/_shakeout/), or
    `"registered"` (the agent block, once stage 2 is live). Anything else refuses."""
    seeds = list(seeds)
    if dry_run:
        bad = [s for s in seeds if s not in DESIGN]
        if bad:
            raise SystemExit(f"seeds {bad[:3]} are outside the design block "
                             "640000-640999; a dry run uses design seeds")
        return "dry"
    if all(s in SHAKEOUT for s in seeds):
        if out is None or SHAKEOUT_DIR.resolve() not in [Path(out).resolve(),
                                                         *Path(out).resolve().parents]:
            raise SystemExit(f"shake-out runs are written under {SHAKEOUT_DIR}/ only")
        return "shakeout"
    if AGENT_SEEDS is not None and all(s in AGENT_SEEDS for s in seeds):
        return "registered"
    raise SystemExit("stage 2 is not live: model-backed runs are allowed only on the "
                     f"shake-out seeds {SHAKEOUT.start}-{SHAKEOUT.stop - 1}, into "
                     f"{SHAKEOUT_DIR}/; otherwise --dry-run on design seeds")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS, required=True)
    ap.add_argument("--level", type=float, choices=LEVELS, required=True)
    ap.add_argument("--runs", type=int, required=True)
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="runs/_dry/planted_agent")
    a = ap.parse_args(argv)
    seeds = list(range(a.seed0, a.seed0 + a.runs))
    mode = check_seeds(seeds, a.dry_run, Path(a.out))
    print(f"  {mode}: {a.arm} at level {a.level}, seeds {seeds[0]}-{seeds[-1]}", flush=True)
    prompts = read_prompts()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i, seed in enumerate(seeds):
        path = out / f"{run_id_for(a.arm, a.level, seed, i)}.json"
        if is_complete(completion_of(path)):
            continue
        rec = run_one(a.arm, seed, a.level, i, prompts=prompts, dry_run=a.dry_run)
        path.write_text(json.dumps(rec.to_json(), indent=1, default=str))
        print(f"  {path.name} written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
