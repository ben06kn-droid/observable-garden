"""heterogeneous-correlation-fat-tails (6.3): does the full-class null survive
realistic features?

Pre-registered in `prereg/heterogeneous-correlation-fat-tails.md`. Three cells,
each breaking one assumption behind the declared-class tier's calibration:

    (A) factor-structured correlation      lambda_i * lambda_j at rho=0.3,
                                           loadings 0.398-0.698
    (B) fat tails and clustered volatility t(4) noise on a COMMON GARCH path
    (C) both

`ExhaustiveClass` is the anchor and the only searcher for which exactness is
claimed, predicted by P1. Every other searcher submits below its class maximum,
so P2 predicts conservatism and only validity is claimed -- one-sided, on the
lower end of the interval, per `prereg/README.md` amendment 1.

    python -m experiments.heterogeneous_and_fat --cell C --smoke 48 --workers 16
    python -m experiments.heterogeneous_and_fat --cell A --workers 16
"""
from __future__ import annotations

import argparse
import pickle
import time
from pathlib import Path

import numpy as np
from scipy.stats import kstest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import select_block_length
from estimator.metrics import ks_critical_value, type1_rate
from experiments._parallel import run_cells
from experiments.search_depth import git_state
from garden._full_class_engine import full_class_null_max, full_class_observed_max
from garden.spec_class import SubsetClass
from searchers.scripted import Adaptive, Greedy, SignedAdaptive

ALPHAS = (0.05, 0.01)

# arm D's configuration, so the baseline this perturbs is a measured one
M, T, T_OOS, K, D = 50, 5000, 1000, 40, 3
SIGMA = 1.0
B_REPS = 10_000
SEED0, BLOCK = 400_000, 25
SEED0_REPLICATION = 410_000          # amendment 2(b), registered before the run
N_DRAWS = 2000

SIGNED = SubsetClass(max_size=D, signed=True)      # 82,240 members at K=40
UNSIGNED = SubsetClass(max_size=D, signed=False)   # 10,700

# Each searcher is priced against a class it can actually reach (arm D's
# finding: class mismatch, not search inefficiency, dominates the gate's
# conservatism). That needs TWO class nulls per draw, not one.
MATCHED = {
    "exhaustive-signed": SIGNED,
    "signed-adaptive": SIGNED,
    "greedy": UNSIGNED,
    "adaptive": UNSIGNED,
}
MEMBERS = tuple(MATCHED)
NULL_QUANTILES = (0.90, 0.95, 0.99, 0.999)

# amendment 2(a): fixed before the code was written
GARCH_ALPHA, GARCH_BETA, T_DOF, GARCH_BURN = 0.10, 0.85, 4.0, 1000
CELLS = ("A", "B", "C")
# amendment 3(a): heterogeneous_correlation returns the identity at rho <= 0, so
# the heterogeneous cells must run at rho > 0 or they test nothing. 0.3 is what
# `unequal-correlation` used; it puts loadings on 0.398-0.698 and pairwise
# correlations on 0.164-0.482.
RHO_HETEROGENEOUS = 0.3


def common_garch_t_noise(rng: np.random.Generator, n: int, m: int,
                         sigma: float) -> np.ndarray:
    """(n, m) return noise: per-asset t(4) innovations on ONE shared volatility
    path.

    The path is common by design, not per-asset. A base feature column is
    `mean_i(x[t,i,k] * eps[t,i])`, an average over m = 50 assets; t(4) has finite
    variance, so independent per-asset tails and independent per-asset volatility
    would both wash out by the central limit theorem and the cell would stress
    the estimator barely at all. A shared `sigma_t` survives the cross-sectional
    average and reaches the statistic the null is taken over.
    """
    omega = sigma ** 2 * (1.0 - GARCH_ALPHA - GARCH_BETA)
    scale = np.sqrt((T_DOF - 2.0) / T_DOF)            # t(4) standardised to var 1
    s2, e_prev = sigma ** 2, 0.0
    path = np.empty(n)
    for t in range(GARCH_BURN + n):
        s2 = omega + GARCH_ALPHA * e_prev ** 2 + GARCH_BETA * s2
        e_prev = np.sqrt(s2) * float(rng.standard_t(T_DOF)) * scale
        if t >= GARCH_BURN:
            path[t - GARCH_BURN] = np.sqrt(s2)
    z = rng.standard_t(T_DOF, size=(n, m)) * scale
    return path[:, None] * z


def make_panel(cell: str, seed: int):
    """One draw's panel. s = 0 throughout, so returns are pure noise and the
    signal machinery never enters."""
    hetero = cell in ("A", "C")
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0,
                    rho=RHO_HETEROGENEOUS if hetero else 0.0,
                    sigma=SIGMA, seed=seed, heterogeneous=hetero)
    data = generate(cfg)
    if cell in ("B", "C"):
        # s = 0 means beta_full is zero, so the return IS the noise: replacing it
        # wholesale is exact rather than an approximation.
        rng = np.random.default_rng(seed + 7_000_000)
        data.r_in = common_garch_t_noise(rng, T, M, SIGMA)
        data.r_oos = common_garch_t_noise(rng, T_OOS, M, SIGMA)
    return data, cfg


def build(name: str, seed: int):
    if name == "greedy":
        return Greedy(seed=seed)
    if name == "adaptive":
        return Adaptive(max_features=D, seed=seed)
    return SignedAdaptive(max_features=D, seed=seed)


def run_draw(cell: str, seed: int) -> dict:
    """Price both matched class nulls once, then score each searcher against the
    null of the class it can reach."""
    t0 = time.time()
    data, cfg = make_panel(cell, seed)
    ann = float(np.sqrt(cfg.periods_per_year))
    sb0 = Sandbox(data, periods_per_year=cfg.periods_per_year)
    base = sb0.base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))

    nulls, floor, cap = {}, 0, 0
    for tag, cls in (("signed", SIGNED), ("unsigned", UNSIGNED)):
        M_b, _, f, c = full_class_null_max(base, cls, B=B_REPS, block_length=L,
                                           annualization=ann, seed=seed)
        nulls[tag] = M_b
        floor, cap = floor + int(f), cap + int(c)

    def score(M_b, sr):
        return float((1 + np.sum(M_b >= sr)) / (M_b.size + 1))

    out: dict = {"_draw": {"block_length": L, "floor": floor, "cap": cap,
                           "null_q_signed": np.quantile(nulls["signed"], NULL_QUANTILES),
                           "null_q_unsigned": np.quantile(nulls["unsigned"], NULL_QUANTILES)}}

    sr_s, _, fs, cs = full_class_observed_max(base, SIGNED, annualization=ann)
    out["exhaustive-signed"] = {"p_value": score(nulls["signed"], sr_s),
                                "sr_sel": float(sr_s)}
    out["_draw"]["floor"] += int(fs)
    out["_draw"]["cap"] += int(cs)

    for name in ("signed-adaptive", "greedy", "adaptive"):
        cls = MATCHED[name]
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=cls)
        build(name, seed).run(sb)
        sr = float(sb.submission[1].mean)
        tag = "signed" if cls is SIGNED else "unsigned"
        out[name] = {"p_value": score(nulls[tag], sr), "sr_sel": sr}

    out["_draw"]["seconds"] = time.time() - t0
    return out


def run_cell(cell: str, n_draws: int, workers: int | None,
             checkpoint_dir: str | None, seed0: int) -> dict:
    starts = list(range(0, n_draws, BLOCK))
    cells = {(cell, s): [(cell, seed0 + i) for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[(cell, s)]]
    data = {"cell": cell, "git_at_launch": git_state(),
            "seeds": seed0 + np.arange(n_draws), "members": MEMBERS,
            "settings": {"M": M, "T": T, "K": K, "d": D, "B": B_REPS,
                         "draws": n_draws, "workers": workers, "seed0": seed0,
                         "garch": [GARCH_ALPHA, GARCH_BETA], "t_dof": T_DOF,
                         "signed_size": SIGNED.size(K), "unsigned_size": UNSIGNED.size(K),
                         "rho": RHO_HETEROGENEOUS if cell in ("A", "C") else 0.0},
            "seconds": np.array([r["_draw"]["seconds"] for r in rows]),
            "block_length": np.array([r["_draw"]["block_length"] for r in rows]),
            "floor": np.array([r["_draw"]["floor"] for r in rows]),
            "cap": np.array([r["_draw"]["cap"] for r in rows])}
    for q in ("null_q_signed", "null_q_unsigned"):
        data[q] = np.array([r["_draw"][q] for r in rows])
    for name in MEMBERS:
        data[name] = {f: np.array([r[name][f] for r in rows])
                      for f in ("p_value", "sr_sel")}
    return data


def report(data: dict, full_n: int) -> str:
    s, n = data["settings"], data["settings"]["draws"]
    secs = data["seconds"]
    g = data["git_at_launch"]
    L = [f"heterogeneous-correlation-fat-tails — cell {data['cell']}", "=" * 78,
         f"n={n} draws, B={s['B']:,}, K={s['K']}, M={s['M']}, T={s['T']:,}, "
         f"seeds from {s['seed0']}",
         f"classes: signed {s['signed_size']:,}, unsigned {s['unsigned_size']:,} "
         f"(two nulls per draw, each searcher matched)",
         f"GARCH({s['garch'][0]}, {s['garch'][1]}) common path, t({s['t_dof']:.0f}) noise"
         if data["cell"] in ("B", "C") else "Gaussian noise",
         f"git at launch {g['commit'][:7]}"
         + (" (tracked changes)" if g.get("dirty") else "")
         + (f" [{g['untracked']} untracked]" if g.get("untracked") else ""), ""]

    L += ["RULE 1 — anchor exactness (P1 predicts it; claimed here only)", "-" * 78]
    ex = data["exhaustive-signed"]["p_value"]
    for a in ALPHAS:
        rate, lo, hi = type1_rate(ex, alpha=a)
        inside = lo <= a <= hi
        L.append(f"  a={a:<5} k={int(np.sum(ex < a)):<5} rate {rate:.4f} "
                 f"({lo:.4f}-{hi:.4f})   contains {a}: {'yes' if inside else 'NO'}")
    ks = kstest(ex, "uniform")
    L += [f"  KS D={ks.statistic:.4f} vs 5% critical {ks_critical_value(ex.size, 0.05):.4f},"
          f" p={ks.pvalue:.4f}: {'does not reject' if ks.pvalue >= 0.05 else 'REJECTS'}", ""]

    L += ["RULE 2 — validity, one-sided (README amendment 1: fails high iff the",
          "         LOWER end exceeds nominal; upper end is the largest",
          "         liberality not ruled out). No KS: P2 does not predict uniformity.",
          "-" * 78,
          f"    {'searcher':<20}{'a':>6}{'k':>7}{'rate':>9}{'lower':>9}{'upper':>9}"
          f"{'liberal?':>10}"]
    for name in ("signed-adaptive", "greedy", "adaptive"):
        p = data[name]["p_value"]
        for a in ALPHAS:
            rate, lo, hi = type1_rate(p, alpha=a)
            L.append(f"    {name:<20}{a:>6}{int(np.sum(p < a)):>7}{rate:>9.4f}"
                     f"{lo:>9.4f}{hi:>9.4f}{'YES' if lo > a else 'no':>10}")
    L += [""]

    L += ["RULE 3 — block lengths (reported, not gated)", "-" * 78,
          f"  min {int(data['block_length'].min())}, "
          f"median {int(np.median(data['block_length']))}, "
          f"max {int(data['block_length'].max())}, "
          f"mean {data['block_length'].mean():.2f}",
          "  arm D's Gaussian iid baseline chose 1 (median 1, max 2); cells B and C",
          "  must choose longer or the selector is not seeing the dependence.", "",
          "RULE 4 — guards (reported, not gated)", "-" * 78,
          f"  variance floor binds {int(data['floor'].sum())}   "
          f"sharpe cap binds {int(data['cap'].sum())}", ""]

    L += ["COST", "-" * 78,
          f"  per draw   mean {secs.mean():7.2f}s   median {np.median(secs):7.2f}s"
          f"   max {secs.max():7.2f}s",
          f"  this run   {secs.sum()/3600:.2f} CPU-hours over {n} draws"]
    if n < full_n:
        w = s.get("workers")
        cpu_h = secs.mean() * full_n / 3600
        if w:
            L.append(f"  projected  {cpu_h:.1f} CPU-hours for {full_n} draws "
                     f"({cpu_h/w:.2f} h wall at {w} workers, ${cpu_h/w*1.64:.2f} at $1.64/h)")
            L.append(f"  all three cells: {3*cpu_h/w:.2f} h wall, ${3*cpu_h/w*1.64:.2f}")
    L += [""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cell", choices=CELLS, required=True)
    ap.add_argument("--out", default="figures")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--smoke", type=int, default=None,
                    help="run this many draws instead of the full count and "
                         "report the measured per-draw cost")
    ap.add_argument("--replication", action="store_true",
                    help="amendment 2(b): rerun on the registered fresh seed "
                         "block after a first failure")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    n = a.smoke if a.smoke else N_DRAWS
    seed0 = SEED0_REPLICATION if a.replication else SEED0
    data = run_cell(a.cell, n, a.workers, a.checkpoint_dir, seed0)
    text = report(data, N_DRAWS)
    print(text)

    tag = f"_cell{a.cell}" + ("_replication" if a.replication else "") + \
          (f"_smoke{n}" if a.smoke else "")
    (out_dir / f"heterogeneous_and_fat{tag}.txt").write_text(text + "\n")
    with (out_dir / f"heterogeneous_and_fat{tag}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)


if __name__ == "__main__":
    main()
