"""gate-comparison (7.0): which certifier should the gate use, and in what order?

Pre-registered in `prereg/gate-comparison.md`, amendments 1-9. Per draw, on one
panel, each searcher is priced by up to four certifiers:

1. **declared class, full sample** — the full-class null over the class the
   searcher can actually reach (amendment 1's matched-class correction);
2. **holdout 70/30** — search the first 3,500 periods, one test on the last
   1,500, by amendment 8's stationary-block-bootstrap p-value;
3. **holdout 50/50** — the same at 2,500/2,500;
4. **process replay, full sample** — `estimator/recursive_bootstrap.py`, which
   re-executes the searcher's own selection inside every replicate.

`ExhaustiveClass` is the calibration anchor and is scored under certifier 1
**only**: the pre-registration records that a holdout or a replay of an
exhaustive enumeration is a different object and not part of this question.

    python -m experiments.gate_comparison --smoke 4 --B 500 --workers 8   # cost only
    python -m experiments.gate_comparison --cell s0 --workers 192 --checkpoint-dir ckpt_g70

**Smoke and scaling draw only from the registered cost-only block 980000-980999**
(amendment 7) and print cost alone: wall time, per-draw and per-certifier
seconds, guard counts. No rejection rate, p-value or distance appears in that
report (`prereg/README.md`). 970000-970999 is `fixed-sequence-replay`'s and is
not touched here.

**What this experiment does not decide** (amendment 6): the certifying null is
trigger replay, fixed by 7.1. 7.0 measures power at matched *actual* size, and
coverage; it does not reopen validity.
"""
from __future__ import annotations

import argparse
import dataclasses
import pickle
import time
from pathlib import Path

import numpy as np

from environments.dgp import DGPConfig, calibrate_sigma, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import (select_block_length, sharpe,
                                 stationary_bootstrap_indices)
from estimator.recursive_bootstrap import recursive_null_max_bootstrap
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden._full_class_engine import full_class_null_max, full_class_observed_max
from garden.spec_class import SubsetClass
from searchers.diagnostic import ExhaustiveClass
from searchers.meta_adaptive import StopWhenCleared
from searchers.scripted import (Adaptive, BudgetedRandom, Greedy, SignedAdaptive,
                                SignedGreedy)

ALPHAS = (0.05, 0.01)

# e_agent.py's s0 and s3 configurations, as the Design section registers. s3's
# sigma is solved for so the oracle Sharpe is 1.0, which is what `e_agent`
# amendment 9 does; writing a sigma down here instead would be a different DGP.
M, T, T_OOS, K, D = 50, 5000, 1000, 40, 3
ORACLE_SHARPE = {"s0": None, "s3": 1.0}
S_TRUE = {"s0": 0, "s3": 3}

SEED0 = 200_000                  # registered
SEED0_REPLICATION = 210_000      # amendment 4
SEED0_SMOKE = 980_000            # amendment 7: cost only, dedicated
N_DRAWS = 2000
BLOCK = 25
B_DEFAULT = 10_000
B_FALLBACK = 1_000               # amendment 7, if the projection exceeds $150
BUDGETS = (25, 100, 400)         # amendment 5
HOLDOUTS = ((0.70, "holdout_70_30"), (0.50, "holdout_50_50"))
NULL_QUANTILES = (0.90, 0.95, 0.99, 0.999)
PRICE_PER_HOUR = 9.85            # c7a.48xlarge (amendment 7)

SIGNED = SubsetClass(max_size=D, signed=True)      # 82,240 members at K=40
UNSIGNED = SubsetClass(max_size=D, signed=False)   # 10,700

# One Sharpe standard error at this T, annualised. 7.1 registered the stop bar at
# 3.5 se = 0.786 on this identical configuration, and the pre-registration reuses
# 7.1's searcher, so the bar transfers with it.
SE = float(np.sqrt(252.0 / T))
STOP_BAR = 3.5 * SE

# searcher -> (matched class, is a slack searcher, certifiers it is scored under)
CLASS_ONLY = ("class",)
ALL_FOUR = ("class", "holdout_70_30", "holdout_50_50", "replay")
MATCHED = {
    "exhaustive-signed": (SIGNED, False, CLASS_ONLY),
    "greedy": (UNSIGNED, False, ALL_FOUR),
    "adaptive": (UNSIGNED, False, ALL_FOUR),
    "signed-greedy": (SIGNED, False, ALL_FOUR),
    "signed-adaptive": (SIGNED, False, ALL_FOUR),
    "stop-when-cleared": (SIGNED, True, ALL_FOUR),
    **{f"budgeted-random-{b}": (SIGNED, True, ALL_FOUR) for b in BUDGETS},
}
MEMBERS = tuple(MATCHED)
SLACK = tuple(n for n, (_, slack, _) in MATCHED.items() if slack)


def build(name: str, seed: int):
    """A fresh searcher. Every parameter is a property of the searcher, fixed
    before the run and **not rescaled per certifier** (amendment 5): the holdout
    arm runs the same searcher on a shorter slice, which is the point of it.
    """
    cls = MATCHED[name][0]
    if name == "exhaustive-signed":
        return ExhaustiveClass(cls, seed=seed)
    if name == "greedy":
        return Greedy(seed=seed)
    if name == "adaptive":
        return Adaptive(max_features=D, seed=seed)
    if name == "signed-greedy":
        return SignedGreedy(seed=seed)
    if name == "signed-adaptive":
        return SignedAdaptive(max_features=D, seed=seed)
    if name == "stop-when-cleared":
        # Capped to the declared class (amendment 1), and scored with the moment
        # scorer amendment 3 sized replay on; 7.1's equivalence test holds the two
        # scoring paths to ~1e-12.
        s = StopWhenCleared(bar=STOP_BAR, seed=seed).set_class(cls)
        s.scoring = "moments"
        return s
    if name.startswith("budgeted-random-"):
        return BudgetedRandom(budget=int(name.rsplit("-", 1)[1]), max_size=D,
                              signed=True, seed=seed)
    raise KeyError(name)


def make_panel(cell: str, seed: int):
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=S_TRUE[cell], rho=0.0,
                    sigma=1.0, seed=seed)
    if ORACLE_SHARPE[cell] is not None:
        cfg = dataclasses.replace(cfg, sigma=calibrate_sigma(ORACLE_SHARPE[cell], cfg))
    return generate(cfg), cfg


def _mc_p(null: np.ndarray, observed: float) -> float:
    """The (1 + #)/(B + 1) form every null in this repository uses."""
    null = np.asarray(null)
    return float((1 + np.sum(null >= observed)) / (null.size + 1))


def holdout_p(stream: np.ndarray, B: int, annualization: float, seed: int) -> float:
    """Amendment 8: one stream, one-sided against a zero-mean null by the
    stationary block bootstrap, block length by Politis-White on the holdout
    slice itself. No maximum over anything — the holdout tier's claim is that the
    slice is independent of the search, so no multiplicity belongs in it."""
    x = np.asarray(stream, dtype=float)
    if x.size < 3 or x.std(ddof=1) == 0:
        return 1.0
    observed = float(sharpe(x[:, None], axis=0, annualization=annualization)[0])
    centred = (x - x.mean())[:, None]
    L = int(select_block_length(centred))
    rng = np.random.default_rng(seed)
    null = np.empty(B)
    for b in range(B):
        idx = stationary_bootstrap_indices(x.size, L, rng)
        null[b] = sharpe(centred[idx], axis=0, annualization=annualization)[0]
    return _mc_p(null, observed)


def holdout_certify(name: str, data, cfg, frac: float, B: int, seed: int) -> float:
    """Search the first `frac` of the in-sample periods, test once on the rest.

    The searcher is re-run on the slice; no search happens on the holdout part
    and nothing is re-selected there (amendment 8). An empty submission scores
    1.0 rather than undefined.
    """
    cut = int(round(T * frac))
    cls = MATCHED[name][0]
    ann = float(np.sqrt(cfg.periods_per_year))
    search_data = dataclasses.replace(data, x_in=data.x_in[:cut], r_in=data.r_in[:cut])
    sb = Sandbox(search_data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    build(name, seed).run(sb)
    if sb.submission is None:
        return 1.0
    spec = sb.submission[0]
    test_data = dataclasses.replace(data, x_in=data.x_in[cut:], r_in=data.r_in[cut:])
    tester = Sandbox(test_data, periods_per_year=cfg.periods_per_year, spec_class=cls)
    tester.evaluate(spec)                      # exactly one test on the holdout slice
    assert len(tester.transcript) == 1
    return holdout_p(tester.transcript[0].return_stream, B, ann, seed + 11)


def oos_sharpes(data, cfg, weights: np.ndarray) -> tuple[float, float]:
    """Gross OOS Sharpe of a fixed submission, unshifted and under the `S[0]`
    sign flip (amendment 9, rule 5).

    The flip is `beta_full[S[0]] *= -1` on the out-of-sample panel with the
    realised noise held, constructed exactly as
    `experiments/costs_and_regime_change.py` does it, so the two experiments'
    numbers are the same object. The submission is held fixed, which is why no
    PASS decision can move under it.
    """
    ann = float(np.sqrt(cfg.periods_per_year))
    p = data.x_oos @ weights                                  # (T_oos, M) positions
    unshifted = float(sharpe(np.mean(p * data.r_oos, axis=1)[:, None],
                             axis=0, annualization=ann)[0])
    if data.S.size == 0:
        return unshifted, unshifted                           # s0: no beta to flip
    eps = data.r_oos - data.x_oos @ data.beta_full
    beta_flipped = data.beta_full.copy()
    beta_flipped[data.S[0]] *= -1.0
    r_flip = data.x_oos @ beta_flipped + eps
    flipped = float(sharpe(np.mean(p * r_flip, axis=1)[:, None],
                           axis=0, annualization=ann)[0])
    return unshifted, flipped


def run_draw(cell: str, seed: int, B: int) -> dict:
    """One panel, every searcher, every certifier that searcher is scored under.

    Both matched class nulls are priced once and shared, as arm D and 6.3 do.
    Recorded per draw, per the Design section: the observed statistic, the
    p-value under each certifier, and the null-max quantiles — so no later
    experiment has to re-price a null.
    """
    t_draw = time.time()
    data, cfg = make_panel(cell, seed)
    ann = float(np.sqrt(cfg.periods_per_year))
    sb0 = Sandbox(data, periods_per_year=cfg.periods_per_year)
    base = sb0.base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))

    t0 = time.time()
    nulls, floor, cap = {}, 0, 0
    for tag, cls in (("signed", SIGNED), ("unsigned", UNSIGNED)):
        M_b, _, f, c = full_class_null_max(base, cls, B=B, block_length=L,
                                           annualization=ann, seed=seed)
        nulls[tag] = M_b
        floor, cap = floor + int(f), cap + int(c)
    out: dict = {"_draw": {"seed": seed, "cell": cell, "block_length": L,
                           "seconds_class_nulls": time.time() - t0,
                           "null_q_signed": np.quantile(nulls["signed"], NULL_QUANTILES),
                           "null_q_unsigned": np.quantile(nulls["unsigned"], NULL_QUANTILES)}}

    for name in MEMBERS:
        cls, is_slack, certifiers = MATCHED[name]
        tag = "signed" if cls is SIGNED else "unsigned"
        row = {"slack_searcher": is_slack, "class": cls.name}

        t0 = time.time()
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
        build(name, seed).run(sb)
        spec, dist = sb.submission
        row["sr_sel"] = float(dist.mean)
        row["n_evaluations"] = len(sb.transcript)
        row["support_size"] = int(np.sum(spec.weights != 0))
        row["seconds_search"] = time.time() - t0

        # 1. declared class, full sample
        row["p_class"] = _mc_p(nulls[tag], row["sr_sel"])

        # 2-3. holdouts
        for frac, key in HOLDOUTS:
            if key not in certifiers:
                row[f"p_{key}"], row[f"seconds_{key}"] = None, 0.0
                continue
            t0 = time.time()
            row[f"p_{key}"] = holdout_certify(name, data, cfg, frac, B, seed)
            row[f"seconds_{key}"] = time.time() - t0

        # 4. process replay, full sample
        if "replay" in certifiers:
            t0 = time.time()
            rb = recursive_null_max_bootstrap(base, build(name, seed), B=B,
                                              block_length=L, annualization=ann,
                                              seed=seed)
            row["p_replay"] = _mc_p(rb.M_b, row["sr_sel"])
            row["null_q_replay"] = np.quantile(rb.M_b, NULL_QUANTILES)
            row["seconds_replay"] = time.time() - t0
        else:
            row["p_replay"], row["seconds_replay"] = None, 0.0

        # rule 5's readout: the submission is held fixed under the flip
        row["oos_unshifted"], row["oos_flipped"] = oos_sharpes(data, cfg, spec.weights)
        out[name] = row

    # the anchor's own statistic, for the guard counts the class engine reports
    _, _, fs, cs = full_class_observed_max(base, SIGNED, annualization=ann)
    out["_draw"]["floor"] = floor + int(fs)
    out["_draw"]["cap"] = cap + int(cs)
    out["_draw"]["seconds"] = time.time() - t_draw
    return out


# -- assembly ----------------------------------------------------------------

def run(cell: str, n_draws: int, seed0: int, B: int, workers, checkpoint_dir) -> dict:
    starts = list(range(0, n_draws, BLOCK))
    cells = {(cell, s): [(cell, seed0 + i, B) for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[(cell, s)]]
    data = {"cell": cell, "git_at_launch": git_state(), "members": MEMBERS,
            "settings": {"M": M, "T": T, "K": K, "d": D, "B": B, "draws": n_draws,
                         "workers": workers, "seed0": seed0, "stop_bar": STOP_BAR,
                         "budgets": BUDGETS, "oracle_sharpe": ORACLE_SHARPE[cell],
                         "signed_size": SIGNED.size(K), "unsigned_size": UNSIGNED.size(K)},
            "seconds": np.array([r["_draw"]["seconds"] for r in rows]),
            "block_length": np.array([r["_draw"]["block_length"] for r in rows]),
            "floor": np.array([r["_draw"]["floor"] for r in rows]),
            "cap": np.array([r["_draw"]["cap"] for r in rows])}
    keep = ("sr_sel", "p_class", "p_holdout_70_30", "p_holdout_50_50", "p_replay",
            "n_evaluations", "support_size", "oos_unshifted", "oos_flipped")
    for name in MEMBERS:
        data[name] = {f: np.array([r[name][f] if r[name][f] is not None else np.nan
                                   for r in rows], dtype=float) for f in keep}
        data[name]["certifiers"] = MATCHED[name][2]
    data["rows"] = rows
    return data


def cost_report(data: dict, full_draws: int = N_DRAWS, B_full: int = B_DEFAULT) -> str:
    """Cost only — no rate, no p-value, no distance. That is what
    `prereg/README.md` requires of a smoke or a scaling curve."""
    rows, s = data["rows"], data["settings"]
    secs, g = data["seconds"], data["git_at_launch"]
    scale = B_full / s["B"]
    L = ["gate-comparison (7.0) — COST ONLY", "=" * 78,
         f"{len(rows)} draws from seed {s['seed0']}, cell {data['cell']}, "
         f"B={s['B']:,}, workers={s['workers']}",
         f"git at launch {g['commit'][:7]}"
         + (" (tracked changes)" if g.get("dirty") else ""), "",
         f"per draw   mean {secs.mean():8.2f}s   median {np.median(secs):8.2f}s"
         f"   max {secs.max():8.2f}s", "",
         "where it goes (mean seconds per draw, summed over searchers)", "-" * 78,
         f"  {'class nulls (shared, 2 per draw)':<40}"
         f"{np.mean([r['_draw']['seconds_class_nulls'] for r in rows]):10.2f}"]
    for part, label in (("seconds_search", "search"),
                        ("seconds_replay", "process replay"),
                        ("seconds_holdout_70_30", "holdout 70/30 (search + test)"),
                        ("seconds_holdout_50_50", "holdout 50/50 (search + test)")):
        tot = np.mean([sum(r[n][part] for n in MEMBERS) for r in rows])
        L.append(f"  {label:<40}{tot:10.2f}")
    L += ["", "guards and selector (reported, not gated)", "-" * 78,
          f"  variance floor binds {int(data['floor'].sum())}   "
          f"sharpe cap binds {int(data['cap'].sum())}",
          f"  block length: median {int(np.median(data['block_length']))}, "
          f"max {int(data['block_length'].max())}", ""]

    cpu_h = secs.mean() * scale * full_draws / 3600
    L += ["PROJECTION to the registered design (amendment 7's $150 threshold)", "-" * 78,
          f"  at B={B_full:,}, {full_draws:,} draws: {cpu_h:,.1f} CPU-hours per cell"]
    if s["workers"]:
        wall = cpu_h / s["workers"]
        per_cell = wall * PRICE_PER_HOUR
        both = 2 * per_cell
        L += [f"  at {s['workers']} workers: {wall:,.2f} h wall, ${per_cell:,.2f} per cell",
              f"  both cells (s0 + s3): {2 * wall:,.2f} h wall, ${both:,.2f}",
              f"  threshold $150 -> runs at B={B_full:,}" if both <= 150 else
              f"  threshold $150 exceeded -> registered fallback B={B_FALLBACK:,} "
              f"(projected ${both * B_FALLBACK / B_full:,.2f})"]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", choices=["s0", "s3"], default="s0")
    ap.add_argument("--smoke", type=int, default=None,
                    help="draws from the dedicated cost-only block 980000+")
    ap.add_argument("--replication", action="store_true",
                    help="amendment 4's replication block 210000+")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    if a.smoke and a.replication:
        raise SystemExit("--smoke and --replication are exclusive")
    if a.B not in (B_DEFAULT, B_FALLBACK) and not a.smoke:
        raise SystemExit(f"a registered run uses B={B_DEFAULT:,} or the registered "
                         f"fallback B={B_FALLBACK:,}; other values are smoke only")
    seed0 = SEED0_SMOKE if a.smoke else (SEED0_REPLICATION if a.replication else SEED0)
    data = run(a.cell, a.smoke or N_DRAWS, seed0, a.B, a.workers, a.checkpoint_dir)
    text = cost_report(data)
    print(text, flush=True)
    tag = f"_{a.cell}" + (f"_smoke{a.smoke}" if a.smoke else
                          ("_replication" if a.replication else ""))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"gate_comparison{tag}_cost.txt").write_text(text)
    with (out / f"gate_comparison{tag}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)


if __name__ == "__main__":
    main()
