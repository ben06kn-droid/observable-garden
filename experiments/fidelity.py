"""Check 2's fidelity measurement: re-present one decision with resampled numbers.

`prereg/agent-cell.md` check 2, with amendment 7's two open questions settled as:

- **What the resampling resamples:** the **candidate statistics**, recomputed on a
  **bootstrap replicate of the streams**. Not drawn from thin air and not perturbed by
  noise — the numbers the agent sees are the numbers the same specifications would have
  produced on a resampled history, so they are jointly plausible and carry the panel's
  own dependence. The stationary block bootstrap and block length are the gate's own
  (`estimator/bootstrap.py`).
- **Statelessness:** each presentation is **stateless**. The transcript prefix is rebuilt
  from the log and is **byte-identical to the original except for the replaced numbers**,
  which is why `InformationSet.shown` had to be the verbatim payload with a round trip
  (amendment 8). A continuing session would let presentation *k* see presentation
  *k − 1*, and the measurement would then be of adaptation rather than of fidelity.

Subsamples, per amendment 11 as amended: **every accepted `pick`** in the reasoned-pick
arm, and the **first 10 runs in seed order** for meta moves.

**The information set for decision k is the prompt plus `shown[0..k-1]`** (amendment 7).
A pick's own `shown` is post-execution and belongs to decision k+1, so it is excluded
from its own presentation; including it would hand the agent the answer, since the
candidate statistics are exactly what the declared rule ranks by.

**Nothing here runs on the seat without `--live`.** `--dry-run` substitutes a scripted
responder that answers by the declared rule, so the harness is testable end to end at no
cost; the fidelity rate it reports is then 1.0 by construction and is labelled as such.

**`--live`** presents each decision to the model, statelessly:
- one fresh client per presentation, holding nothing from any other;
- the arm's registered system prompt, then the rendered prefix and the decision;
- a single **forced-choice** tool, `choose`, whose argument must be one of the
  decision's options. For a pick these are the candidate labels shown; for a meta move
  they are `continue`, `stop` and `restart`.

An answer outside the options, or no `choose` call, is recorded as **no answer** and
counts as disagreement. The model call is one injected function
(`client(request) -> tool input`), so the tests drive the whole path with a stub
responder and never call a model. Every presentation is logged with its request, its
raw answer, the parsed choice and the rule's prediction. **A live run spends seat
time**: it prints the number of model calls and refuses without `--yes`. Planted
panels (`--panel planted`) resample the masked view the agent searched, rebuilt from the
run's seed and level on the pinned X.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from estimator.metrics import wilson_ci
from quixote.log import render_shown

N_PRESENTATIONS = 20
ROOT = Path("runs")


def decisions_of(path: Path, kinds: tuple[str, ...]) -> list[dict]:
    """The decisions in one run, with the prefix each was made on."""
    x = json.loads(path.read_text())
    log = [e for e in x["events"] if e.get("kind") == "session_log"]
    if not log:
        return []
    recs = log[0]["records"]
    st = [e for e in x["events"] if e.get("kind") == "start"]
    start = ({k: st[0].get(k) for k in ("panel", "level", "M", "K", "T")} if st else {})
    out = []
    for k, r in enumerate(recs):
        if r["kind"] not in kinds:
            continue
        if r.get("move", {}).get("note") == "rejected":
            continue
        out.append({
            "run_id": x.get("run_id"), "seed": int(x["seed"]), "step": r["step"],
            "k": k, "kind": r["kind"], "move": r.get("move") or {},
            "support_before": [tuple(p) for p in
                               (r.get("information") or {}).get("support", [])],
            # amendment 7: the prompt plus shown[0..k-1]; the decision's OWN shown is
            # post-execution and belongs to the next decision
            "prefix": [(rr["kind"], [tuple(p) for p in (rr.get("shown") or [])])
                       for rr in recs[:k]],
            "shown_self": [tuple(p) for p in (r.get("shown") or [])],
            "declared": x.get("triggers_predeclared") or [],
            "arm": x.get("arm"), "start": start,
        })
    return out


def resampled_shown(dec: dict, panel: str, rep: int) -> list[tuple[str, float]]:
    """The decision's `shown`, recomputed on a bootstrap replicate of the streams.

    One replicate per presentation, seeded from the run's own seed and the
    presentation index, so a presentation is reproducible and two presentations of one
    decision differ in exactly the resample.
    """
    from quixote.grammar import Grammar, Move

    score_fn = None
    if panel == "planted":
        sb, cls, ann, view = _planted_sandbox(dec)
    else:
        from experiments.agent_cell import simulated_panel
        _d, _c, cls, sb, dgp = simulated_panel(panel, dec["seed"])
        ann = float(np.sqrt(dgp.periods_per_year))
    base = np.asarray(sb.base_feature_columns(), dtype=float)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng((dec["seed"] * 1_000_003 + rep) % (2**63))
    rows = stationary_bootstrap_indices(base.shape[0], L, rng)
    R = S0[rows, :]
    if panel == "planted":
        # the live `best` was the net stream's Sharpe (the sandbox scorer); on the
        # replicate it is the demeaned net stream on the same rows
        from environments.class_table import streams_for

        def score_fn(support, statistic="sharpe"):
            x = streams_for(view, [tuple(support), tuple(support)])[0]
            x = (x - x.mean())[rows]
            sd = x.std(ddof=1)
            return float(x.mean() / sd * ann) if sd > 0 else 0.0
    g = Grammar(cls, R, ann, score_fn=score_fn)
    sup = tuple(dec["support_before"])
    m = dec["move"]
    if dec["kind"] == "pick":
        move = Move("pick", statistic=m.get("statistic", "sharpe"),
                    among=tuple(int(j) for j in (m.get("among") or ())))
        return [(f"{ns[-1][0]}{'+' if ns[-1][1] > 0 else '-'}", float(v))
                for v, ns in g.pick_candidates(sup, move)]
    # a meta move's information set is the trigger state; recompute the data-dependent
    # parts (best, last_gain) on the replicate and keep the counters
    live = dict(dec["shown_self"])
    best = g.score(sup) if sup else float("-inf")
    out = []
    for label, value in dec["shown_self"]:
        if label == "best":
            out.append((label, float(best)))
        elif label == "last_gain":
            out.append((label, float(best - live.get("best", best))))
        else:
            out.append((label, float(value)))
    return out


def _planted_sandbox(dec: dict):
    """(sandbox, class, annualisation, masked view) for a planted run's decision,
    rebuilt from its seed and level on the pinned X: what the agent searched."""
    from environments import planted_panel as pp
    from environments.planted_view import agent_view
    from environments.real_sandbox import RealSandbox
    level = (dec.get("start") or {}).get("level")
    if level is None:
        raise ValueError(f"{dec.get('run_id')}: a planted decision needs its run's level")
    draw = pp.make_draw(pp.load_base(), dec["seed"], float(level))
    view, _ = agent_view(draw.in_sample, dec["seed"])
    return (RealSandbox(view, spec_class=pp.CLS), pp.CLS,
            float(np.sqrt(view.periods_per_year)), view)


def render_presentation(dec: dict, shown: list[tuple[str, float]]) -> str:
    """The transcript prefix plus this decision, BYTE-IDENTICAL to the original except
    for the replaced numbers. Built from the same renderer the adapter used."""
    lines = [f"declared: " + "; ".join(
        f"{d['kind']}({d['param']:g})->{d.get('action','stop')}"
        for d in dec["declared"])]
    for kind, pairs in dec["prefix"]:
        lines.append(f"{kind} | shown: {render_shown(pairs)}")
    lines.append(f"DECIDE {dec['kind']} | shown: {render_shown(shown)}")
    return "\n".join(lines)


def rule_choice(dec: dict, shown: list[tuple[str, float]]) -> str | None:
    """What the DECLARED rule selects on these numbers -- the prediction fidelity is
    measured against. For a pick it is the argmax of the named statistic; for a meta
    move it is the action its firing rule licenses."""
    if dec["kind"] == "pick":
        return max(shown, key=lambda p: p[1])[0] if shown else None
    from quixote.triggers import Trigger
    state = {k: v for k, v in shown}
    for d in dec["declared"]:
        t = Trigger.from_record(d)
        try:
            fires, _ = t.evaluate(state)
        except Exception:                           # noqa: BLE001
            continue
        if fires:
            return t.action
    return "continue"


def scripted_responder(dec: dict, shown: list[tuple[str, float]]) -> str | None:
    """`--dry-run`'s stand-in: answers BY THE DECLARED RULE, so fidelity is 1.0 by
    construction. It exercises the harness, not the agent, and the report says so."""
    return rule_choice(dec, shown)


META_CHOICES = ("continue", "stop", "restart")
CHOOSE_INSTRUCTION = ("Make this one decision now by calling `choose` with exactly one "
                      "of the options listed. Nothing else is recorded.")


def options_for(dec: dict, shown: list[tuple[str, float]]) -> list[str]:
    return [lab for lab, _ in shown] if dec["kind"] == "pick" else list(META_CHOICES)


def presentation_request(dec: dict, shown: list[tuple[str, float]],
                         system_prompt: str) -> dict:
    """One STATELESS presentation: a function of the decision, the replicate's numbers
    and the arm's prompt, and of nothing that happened in any other presentation."""
    opts = options_for(dec, shown)
    user = (render_presentation(dec, shown) + "\n\noptions: " + ", ".join(opts)
            + "\n" + CHOOSE_INSTRUCTION)
    return {"system": system_prompt, "user": user, "options": opts,
            "tool": {"name": "choose", "input": {"choice": opts}}}


def parse_answer(tool_input, options) -> str | None:
    """The forced choice, or None for no answer or an answer outside the options."""
    if not isinstance(tool_input, dict):
        return None
    c = tool_input.get("choice")
    return c if isinstance(c, str) and c in options else None


def sdk_client(request: dict):
    """The live model call: a fresh Claude Agent SDK client, the arm's system prompt,
    one `choose` tool, thinking disabled. Returns the `choose` tool input, or None.
    Never called by the tests, which inject a stub."""
    import asyncio
    import tempfile
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient,
                                  ToolUseBlock, create_sdk_mcp_server, tool)
    from experiments.agent_backend import MODEL

    got = {}

    @tool("choose", "Record your one decision.", {"choice": str})
    async def choose(args):
        got.setdefault("input", dict(args))
        return {"content": [{"type": "text", "text": "Recorded."}]}

    async def go():
        server = create_sdk_mcp_server(name="fidelity", version="1.0.0", tools=[choose])
        with tempfile.TemporaryDirectory(prefix="fidelity_") as tmp:
            opts = ClaudeAgentOptions(
                model=MODEL, system_prompt=request["system"], tools=[],
                setting_sources=[], thinking={"type": "disabled"},
                mcp_servers={"fidelity": server},
                allowed_tools=["mcp__fidelity__choose"], max_turns=2, cwd=tmp)
            async with ClaudeSDKClient(options=opts) as client:
                await client.query(request["user"])
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for b in msg.content:
                            if isinstance(b, ToolUseBlock) and b.name.endswith("choose"):
                                got.setdefault("input", dict(b.input))
    asyncio.run(go())
    return got.get("input")


class LiveResponder:
    """Presents each decision through `client`, statelessly, and logs every
    presentation. `client(request) -> tool input`; `sdk_client` is the live one."""

    def __init__(self, system_prompt_of, client=sdk_client, name: str = "model"):
        self.system_prompt_of = system_prompt_of
        self.client = client
        self.name = name
        self.log: list[dict] = []

    def __call__(self, dec: dict, shown: list[tuple[str, float]]) -> str | None:
        req = presentation_request(dec, shown, self.system_prompt_of(dec))
        raw = self.client(dict(req))                      # a copy: nothing shared
        ans = parse_answer(raw, req["options"])
        self.log.append({"run_id": dec["run_id"], "step": dec["step"], "kind": dec["kind"],
                         "shown": [list(p) for p in shown], "options": req["options"],
                         "raw": raw, "answer": ans, "predicted": rule_choice(dec, shown),
                         "user_sha": __import__("hashlib").sha256(
                             req["user"].encode()).hexdigest()[:16]})
        return ans


def system_prompt_of(dec: dict) -> str:
    """The arm's registered system prompt, as the run was given it."""
    from experiments.real_prompts import read_prompts, system_prompt_for
    st = dec.get("start") or {}
    prompts = read_prompts()
    if st.get("panel") == "planted":
        from experiments.planted_agent import prompt_for
        return prompt_for(dec["arm"], st["M"], st["K"], prompts)
    from experiments.agent_cell import DEPTH
    return system_prompt_for(dec["arm"], st["M"], st["K"], DEPTH[st["panel"]], prompts)


def measure(decs: list[dict], panel: str, n_pres: int, responder) -> list[dict]:
    out = []
    for dec in decs:
        agree = no_answer = 0
        for rep in range(n_pres):
            shown = resampled_shown(dec, panel, rep)
            if not shown:
                continue
            predicted = rule_choice(dec, shown)
            answered = responder(dec, shown)
            no_answer += int(answered is None)
            agree += int(answered == predicted and predicted is not None)
        out.append({**{k: dec[k] for k in ("run_id", "kind", "step")},
                    "presentations": n_pres, "agreed": agree, "no_answer": no_answer})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="an arm or shake-out directory")
    ap.add_argument("--panel", default="s0", choices=("s0", "s3", "planted"))
    ap.add_argument("--presentations", type=int, default=N_PRESENTATIONS)
    ap.add_argument("--dry-run", action="store_true",
                    help="scripted responder; no model call, no seat")
    ap.add_argument("--live", action="store_true",
                    help="present each decision to the model; spends seat time")
    ap.add_argument("--yes", action="store_true",
                    help="confirm a live run's model calls, after reading their count")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if a.dry_run == a.live:
        raise SystemExit("exactly one of --dry-run and --live")

    d = ROOT / a.dir
    files = sorted(d.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2]))
    cfg_f = d / "run_config.json"
    first10 = []
    if cfg_f.exists():
        cfg = json.loads(cfg_f.read_text())
        first10 = cfg.get("fidelity_subsample_run_ids") or []

    picks, metas = [], []
    for f in files:
        picks += decisions_of(f, ("pick",))                    # EVERY accepted pick
        rid = json.loads(f.read_text()).get("run_id")
        if not first10 or rid in first10:                      # meta: first 10 runs
            metas += decisions_of(f, ("stop", "restart"))

    if a.live:
        calls = (len(picks) + len(metas)) * a.presentations
        print(f"  live: {len(picks)} picks + {len(metas)} meta decisions x "
              f"{a.presentations} presentations = {calls} model calls", flush=True)
        if not a.yes:
            raise SystemExit("a live run spends seat time; rerun with --yes to confirm "
                             f"{calls} model calls")
        responder = LiveResponder(system_prompt_of, client=sdk_client)
    else:
        responder = scripted_responder
    rows = (measure(picks, a.panel, a.presentations, responder)
            + measure(metas, a.panel, a.presentations, responder))
    head = ("check 2 — FIDELITY (LIVE: the model, one stateless forced-choice "
            "presentation each)" if a.live else
            "check 2 — FIDELITY (DRY RUN: scripted responder, no model, no seat)")
    L = [head, "=" * 78,
         f"  {a.dir}, panel {a.panel}, {a.presentations} presentations per decision",
         "  Resampling: candidate statistics recomputed on a stationary block bootstrap",
         "  replicate of the streams. Presentations are STATELESS and the prefix is",
         "  byte-identical to the original except the replaced numbers.",
         "  Subsamples: every accepted pick; meta moves from the first 10 runs in seed",
         "  order.", ""]
    by = Counter()
    for r in rows:
        by[(r["kind"], "no_answer")] += r.get("no_answer", 0)
        by[(r["kind"], "pres")] += r["presentations"]
        by[(r["kind"], "agree")] += r["agreed"]
        by[(r["kind"], "n")] += 1
    for kind in sorted({k for k, _ in by}):
        n, pres, ag = by[(kind, "n")], by[(kind, "pres")], by[(kind, "agree")]
        if not pres:
            L.append(f"  {kind:<10} UNMEASURED — 0 presentations")
            continue
        lo, hi = wilson_ci(ag, pres)
        note = ("  UNMEASURED as a rate: too few decisions under prereg/README.md's "
                "low-n rule" if n < 10 else "")
        na = by[(kind, "no_answer")]
        L.append(f"  {kind:<10} decisions {n:>3}  presentations {pres:>4}  "
                 f"rate {ag / pres:.4f}  Wilson [{lo:.4f}, {hi:.4f}]  no answer {na}{note}")
    if a.live:
        L += ["", "  LIVE: no answer counts as disagreement. Every presentation is in",
              "  fidelity_live_presentations.jsonl. What licenses fidelity-driven pricing",
              "  is the registered rule, read on this file, not this summary."]
    else:
        L += ["", "  DRY RUN: the responder answers BY THE DECLARED RULE, so a rate of",
              "  1.0000 means the harness is consistent, NOT that an agent is faithful.",
              "  No fidelity claim follows, and fidelity-driven pricing stays unlicensed."]
    text = "\n".join(L)
    print(text)
    tag = "live" if a.live else "dryrun"
    out = Path(a.out or (d / f"fidelity_{tag}.txt"))
    out.write_text(text + "\n")
    (d / f"fidelity_rows{'' if not a.live else '_live'}.json").write_text(
        json.dumps(rows, indent=1))
    if a.live:
        (d / "fidelity_live_presentations.jsonl").write_text(
            "".join(json.dumps(r, default=str) + "\n" for r in responder.log))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
