"""fixed-sequence-replay (7.1): what does freezing a meta decision cost?

Pre-registered in `prereg/fixed-sequence-replay.md`, amendments 1-6 (and the
amendment fixing B). Per draw: an s0 panel at the registered configuration
(K = 40, M = 50, T = 5,000), and, for each of amendment 6's six searchers, the
three replay nulls on one shared resampled index:

    1. fixed_sequence  -- meta actions frozen at the realized sequence
    2. trigger         -- declared triggers evaluated at every step; past the
                          realized length a continue takes 7.1's fill
    3. policy          -- the policy, exact

    python -m experiments.fixed_sequence_replay --smoke 48 --workers 192
    python -m experiments.fixed_sequence_replay --workers 192 --checkpoint-dir ckpt_fsr

**Smoke mode runs on the dedicated seed block 970000-970999 and prints cost
only** -- never a rejection rate, a distance or anything a rule reads
(`prereg/README.md`). The full run writes per-draw summaries and a cost report.
The rules are read once, after all 2,000 draws exist, by `--read`.

Scoring uses the moment path (`scoring = "moments"`), held equivalent to the
column path by `tests/test_meta_adaptive.py`. The null computation below mirrors
`estimator.trigger_replay.replay_nulls`' resampling exactly, and
`tests/test_fixed_sequence_replay.py` holds the two equal.
"""
from __future__ import annotations

import argparse
import pickle
import time
from pathlib import Path

import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from estimator.trigger_replay import ReplayNulls
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from searchers.meta_adaptive import registered_71

M, T, T_OOS, K = 50, 5000, 1000, 40
SEED0 = 300_000                 # registered block
SEED0_REPLICATION = 310_000     # amendment 3(c)
SEED0_SMOKE = 970_000           # amendment 6: smoke and scaling only, no rules printed
N_DRAWS = 2000
BLOCK = 25                      # draws per checkpoint
B_DEFAULT = 10_000              # fixed by the amendment after 6; overridable only for smoke
PRICE_PER_HOUR = 9.85           # c7a.48xlarge, as recorded in ROADMAP's Compute section


def panel(seed: int):
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    base = Sandbox(generate(cfg), periods_per_year=cfg.periods_per_year).base_feature_columns()
    return base, float(np.sqrt(cfg.periods_per_year)), float(np.sqrt(cfg.periods_per_year / cfg.T))


def nulls_for(searcher, base, S0, L, ann, B, seed):
    """Nulls 1-3 for one searcher, exactly as `replay_nulls` draws them (one RNG
    seeded by the draw, one shared index per replicate), plus the per-replicate
    engagement flag that `replay_nulls` does not return."""
    realized = searcher.trace(base, ann)
    acts, n = realized.actions(), realized.n_moves
    rng = np.random.default_rng(seed)
    n1, n2, n3 = np.empty(B), np.empty(B), np.empty(B)
    engaged = np.zeros(B, dtype=bool)
    for b in range(B):
        R = S0[stationary_bootstrap_indices(T, L, rng), :]
        n1[b] = searcher.trace(R, ann, frozen=acts).score
        t2 = searcher.trace(R, ann, meta_steps=n)
        n2[b], engaged[b] = t2.score, any(m.filled for m in t2.moves)
        n3[b] = searcher.trace(R, ann).score
    return realized, n1, n2, n3, engaged


def run_draw(seed: int, B: int) -> dict:
    t_draw = time.time()
    base, ann, se = panel(seed)
    S0 = base - base.mean(axis=0, keepdims=True)
    L = int(select_block_length(S0))
    out = {"_draw": {"seed": seed, "block_length": L}}
    for s in registered_71(seed, se):
        s.scoring = "moments"
        t0 = time.time()
        realized, n1, n2, n3, engaged = nulls_for(s, base, S0, L, ann, B, seed)
        rn = ReplayNulls(fixed_sequence=n1, trigger=n2, policy=n3, block_length=L, B=B,
                         realized_score=realized.score, realized_actions=tuple(realized.actions()))
        out[s.name] = {
            "realized_score": float(realized.score),
            "realized_actions": tuple(realized.actions()),
            "p_fixed": rn.p_value("fixed_sequence"),
            "p_trigger": rn.p_value("trigger"),
            "p_policy": rn.p_value("policy"),
            "signed_ks_2v3": rn.signed_kolmogorov_distance("trigger", "policy"),
            "ks_1v3": rn.kolmogorov_distance("fixed_sequence", "policy"),
            "ks_2v3": rn.kolmogorov_distance("trigger", "policy"),
            "engaged": int(engaged.sum()),
            "differ_2v3": int(np.sum(n2 != n3)),
            "differ_1v3": int(np.sum(n1 != n3)),
            "seconds": time.time() - t0,
        }
    out["_draw"]["seconds"] = time.time() - t_draw
    return out


def run(n_draws: int, seed0: int, B: int, workers: int | None, checkpoint_dir: str | None) -> dict:
    starts = list(range(0, n_draws, BLOCK))
    cells = {("fsr", s): [(seed0 + i, B) for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[("fsr", s)]]
    return {"git_at_launch": git_state(), "seed0": seed0, "draws": n_draws, "B": B,
            "workers": workers, "rows": rows}


def cost_report(data: dict, full_draws: int = N_DRAWS, B_full: int = B_DEFAULT) -> str:
    """Cost only. Nothing a rule reads appears here, so it is safe for smoke."""
    rows = data["rows"]
    secs = np.array([r["_draw"]["seconds"] for r in rows])
    names = [k for k in rows[0] if not k.startswith("_")]
    per = {nm: np.mean([r[nm]["seconds"] for r in rows]) for nm in names}
    scale = B_full / data["B"]
    L = [f"fixed-sequence-replay -- COST ONLY, {len(rows)} draws from seed {data['seed0']}, "
         f"B={data['B']:,}, workers={data['workers']}",
         f"git at launch {data['git_at_launch']['commit'][:7]}"
         + (" (tracked changes)" if data["git_at_launch"].get("dirty") else ""), "",
         f"per draw (all six searchers): mean {secs.mean():.1f}s  median {np.median(secs):.1f}s  "
         f"max {secs.max():.1f}s"]
    L += [f"  {nm:34s} mean {per[nm]:7.2f}s per draw" for nm in names]
    cpu_h = secs.mean() * scale * full_draws / 3600
    L += ["", f"projected at B={B_full:,} and {full_draws:,} draws: {cpu_h:,.0f} CPU-hours"]
    if data["workers"]:
        wall = cpu_h / data["workers"]
        L.append(f"  at {data['workers']} workers: {wall:.1f} h wall if this run's contention holds, "
                 f"${wall * PRICE_PER_HOUR:,.0f} at ${PRICE_PER_HOUR}/h")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", type=int, default=None,
                    help="draws on the dedicated smoke block 970000+, cost report only")
    ap.add_argument("--replication", action="store_true",
                    help="amendment 3(c): the registered replication block 310000+")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    if a.smoke and a.replication:
        raise SystemExit("--smoke and --replication are exclusive")
    if not a.smoke and a.B != B_DEFAULT:
        raise SystemExit(f"a registered run uses B={B_DEFAULT:,}; --B is for smoke only")
    seed0 = SEED0_SMOKE if a.smoke else (SEED0_REPLICATION if a.replication else SEED0)
    n = a.smoke or N_DRAWS
    data = run(n, seed0, a.B, a.workers, a.checkpoint_dir)
    text = cost_report(data)
    print(text, flush=True)
    tag = "_smoke%d" % n if a.smoke else ("_replication" if a.replication else "")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"fixed_sequence_replay{tag}_cost.txt").write_text(text + "\n")
    with (out / f"fixed_sequence_replay{tag}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)


if __name__ == "__main__":
    main()
