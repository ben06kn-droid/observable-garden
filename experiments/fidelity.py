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
        })
    return out


def resampled_shown(dec: dict, panel: str, rep: int) -> list[tuple[str, float]]:
    """The decision's `shown`, recomputed on a bootstrap replicate of the streams.

    One replicate per presentation, seeded from the run's own seed and the
    presentation index, so a presentation is reproducible and two presentations of one
    decision differ in exactly the resample.
    """
    from experiments.agent_cell import simulated_panel
    from quixote.grammar import Grammar, Move

    _d, _c, cls, sb, dgp = simulated_panel(panel, dec["seed"])
    base = np.asarray(sb.base_feature_columns(), dtype=float)
    ann = float(np.sqrt(dgp.periods_per_year))
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    rng = np.random.default_rng((dec["seed"] * 1_000_003 + rep) % (2**63))
    R = S0[stationary_bootstrap_indices(base.shape[0], L, rng), :]
    g = Grammar(cls, R, ann)
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


def measure(decs: list[dict], panel: str, n_pres: int, responder) -> list[dict]:
    out = []
    for dec in decs:
        agree = 0
        for rep in range(n_pres):
            shown = resampled_shown(dec, panel, rep)
            if not shown:
                continue
            predicted = rule_choice(dec, shown)
            answered = responder(dec, shown)
            agree += int(answered == predicted and predicted is not None)
        out.append({**{k: dec[k] for k in ("run_id", "kind", "step")},
                    "presentations": n_pres, "agreed": agree})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="an arm or shake-out directory")
    ap.add_argument("--panel", default="s0", choices=("s0", "s3"))
    ap.add_argument("--presentations", type=int, default=N_PRESENTATIONS)
    ap.add_argument("--dry-run", action="store_true",
                    help="scripted responder; no model call, no seat")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    if not a.dry_run:
        raise SystemExit(
            "live presentation is not wired: --dry-run only. Check 2 runs on the seat "
            "and that is a separate, registered decision.")

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

    rows = (measure(picks, a.panel, a.presentations, scripted_responder)
            + measure(metas, a.panel, a.presentations, scripted_responder))
    L = ["check 2 — FIDELITY (DRY RUN: scripted responder, no model, no seat)", "=" * 78,
         f"  {a.dir}, panel {a.panel}, {a.presentations} presentations per decision",
         "  Resampling: candidate statistics recomputed on a stationary block bootstrap",
         "  replicate of the streams. Presentations are STATELESS and the prefix is",
         "  byte-identical to the original except the replaced numbers.",
         "  Subsamples: every accepted pick; meta moves from the first 10 runs in seed",
         "  order.", ""]
    by = Counter()
    for r in rows:
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
        L.append(f"  {kind:<10} decisions {n:>3}  presentations {pres:>4}  "
                 f"rate {ag / pres:.4f}  Wilson [{lo:.4f}, {hi:.4f}]{note}")
    L += ["", "  DRY RUN: the responder answers BY THE DECLARED RULE, so a rate of",
          "  1.0000 means the harness is consistent, NOT that an agent is faithful.",
          "  No fidelity claim follows, and fidelity-driven pricing stays unlicensed."]
    text = "\n".join(L)
    print(text)
    out = Path(a.out or (d / "fidelity_dryrun.txt"))
    out.write_text(text + "\n")
    (d / "fidelity_rows.json").write_text(json.dumps(rows, indent=1))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
