"""The declared-class p-value for every run of an agent-cell arm.

`prereg/agent-cell.md` amendment 11 registers this as a **descriptive** readout on
**all** runs: the bracket's upper end, one null for every run whatever the agent
declared or changed, and expected conservative — the class tier charges the class
maximum whatever route reached it, so it needs no position and no cooperation from
the log.

It was not computed when the arm ran: `experiments/agent_backend.py`'s
`_certify_run` passed no `p_declared_class`, so `p_upper` is absent from all 80
verdicts. This computes it after the fact, locally — **no model, no seat.**

**The basis, stated rather than assumed.** The class-maximum null is computed by
`garden._full_class_engine.full_class_null_max` on the panel's **base feature
columns**, and the submitted specification is scored on the **same** base columns by
the grammar's scorer, so the observed statistic and the replicate statistic are
computed on one basis. The two scoring paths in this repository agree to about
1e-12 and not exactly (`quixote/grammar.py`), which is immaterial for a descriptive
readout and is recorded so it is not mistaken for exactness.

**B matches the run's certifying null** so the two p-values have the same
granularity; `(1 + #{M_b >= sr}) / (B + 1)` either way.

    python -m experiments.agent_cell_class_p --dir runs/agent_cell_s0_replay
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from estimator.bootstrap import select_block_length
from estimator.metrics import wilson_ci
from garden._full_class_engine import full_class_null_max, full_class_observed_max

ALPHAS = (0.05, 0.01)


def class_p_for_run(panel_name: str, seed: int, support, B: int) -> dict:
    """One run's declared-class p-value, on the run's own draw."""
    from experiments.agent_cell import simulated_panel

    _data, _cfg, cls, sandbox, dgp = simulated_panel(panel_name, seed)
    return class_p_on(sandbox, cls, float(np.sqrt(dgp.periods_per_year)), seed,
                      support, B)


def class_p_on(sandbox, cls, ann: float, seed: int, support, B: int) -> dict:
    """`class_p_for_run` on a draw the caller has already built, so
    `experiments/price_runs.py` does not generate each simulated panel twice."""
    from quixote.grammar import Grammar

    base = np.asarray(sandbox.base_feature_columns(), dtype=float)
    L = int(select_block_length(base - base.mean(axis=0)))
    M_b, _, n_floor, n_cap = full_class_null_max(
        base, cls, B=B, block_length=L, annualization=ann, seed=seed)
    class_max, _, _, _ = full_class_observed_max(base, cls, annualization=ann)

    sup = tuple((int(k), float(s)) for k, s in support) if support else ()
    sr = (float(Grammar(cls, base, ann).score(sup)) if sup else float("-inf"))
    p = (1 + int(np.sum(M_b >= sr))) / (B + 1)
    return {"seed": seed, "p_upper": p, "submitted_score_on_base": sr,
            "class_max": float(class_max), "block_length": L,
            "null_max_mean": float(M_b.mean()), "B": B,
            "guard_floor": int(n_floor), "guard_cap": int(n_cap)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--panel", default="s0")
    ap.add_argument("--B", type=int, default=None,
                    help="default: the B each run's certifying null used")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)

    d = Path(a.dir)
    files = sorted(d.glob("cell_*.json"), key=lambda p: int(p.name.split("_")[2]))
    rows = []
    for f in files:
        x = json.loads(f.read_text())
        v = x.get("verdict") or {}
        B = a.B or int(v.get("B") or 200)
        sup = x.get("submitted_support")
        r = class_p_for_run(a.panel, int(x["seed"]), sup, B)
        r.update({"run_id": x.get("run_id"), "index": int(f.name.split("_")[2]),
                  "status": v.get("status"),
                  "p_certifying": v.get("p_certifying"),
                  "submitted_sharpe_recorded": x.get("submitted_sharpe")})
        rows.append(r)
        print(f"  run {r['index']:>2}: p_upper {r['p_upper']:.4f}", flush=True)

    L = ["prereg/agent-cell.md amendment 11 — DESCRIPTIVE: the declared-class "
         "p-value, all runs", "=" * 78,
         f"  {len(rows)} runs from {a.dir}, panel {a.panel}",
         f"  B per run: {sorted({r['B'] for r in rows})}; basis: base feature "
         "columns for both the null and the submitted score",
         "  The bracket's UPPER end. One null for every run whatever the agent",
         "  declared or changed; expected conservative. No threshold, no branch.", ""]
    p = np.asarray([r["p_upper"] for r in rows], dtype=float)
    for al in ALPHAS:
        k = int((p < al).sum())
        lo, hi = wilson_ci(k, len(p))
        L.append(f"    alpha = {al:<5} {k:>3}/{len(p):<3} = {k / len(p):7.4f}   "
                 f"Wilson [{lo:.4f}, {hi:.4f}]")
    L += ["",
          f"    p_upper: min {p.min():.4f}  median {np.median(p):.4f}  "
          f"max {p.max():.4f}",
          f"    guard hits across runs: floor {sum(r['guard_floor'] for r in rows)}, "
          f"cap {sum(r['guard_cap'] for r in rows)}"]
    # against the certifying null, where a run has one
    both = [r for r in rows if r["p_certifying"] is not None]
    if both:
        d_ = np.asarray([r["p_upper"] - r["p_certifying"] for r in both], dtype=float)
        L += ["", f"    on the {len(both)} runs carrying a certifying p as well:",
              f"      p_upper - p_certifying: mean {d_.mean():+.4f}  "
              f"median {np.median(d_):+.4f}  min {d_.min():+.4f}  max {d_.max():+.4f}",
              "      a positive difference is the class tier being the more"
              " conservative end"]
    text = "\n".join(L)
    print("\n" + text, flush=True)
    out = Path(a.out or (d / "class_p_readout.txt"))
    out.write_text(text + "\n")
    (d / "class_p.json").write_text(json.dumps(rows, indent=1))
    print(f"\nwritten to {out} and {d / 'class_p.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
