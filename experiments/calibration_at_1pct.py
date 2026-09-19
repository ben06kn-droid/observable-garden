"""calibration-at-1pct: is the gate calibrated at 1%, not just at 5%?

    python -m experiments.calibration_at_1pct --arm A            # local, seconds
    python -m experiments.calibration_at_1pct --arm B --smoke 50  # sizing measurement
    python -m experiments.calibration_at_1pct --arm B --workers 32
    python -m experiments.calibration_at_1pct --arm C --workers 32

Pre-registered in prereg/calibration-at-1pct.md.

**Arm A** reads the p-value every graded s0 run already stored and reports the
rejection rate at three levels with Wilson intervals plus a KS test against
U(0,1), per model and pooled. It gates nothing: at n = 419 a true rate of 1% has
a Wilson half-width of about 0.95 points, so it cannot resolve the 1% tail. The
counts were computed on 2026-09-19, before the pre-registration existed, and are
recorded there as observed rather than registered.

**Arm B** is what the decision rules turn on: the agent arm's own configuration
(s0, K=40, M=50, T=5,000, sigma=1) with scripted searchers, priced against the
same 82,240-member declared class the agents were held to, at the same
B = 10,000 `watch.open` gave every agent run.

**Arm C** re-runs arm B's first 500 draws at B = 50,000 to ask whether 10,000
replicates place the 1% critical value.

The class null depends on the base columns and the class, not on the searcher,
so one null per draw serves both searchers. That is why arm B costs one bootstrap
per draw rather than two.

Reports numbers only. Interpretation belongs in the write-up.
"""
from __future__ import annotations

import argparse
import csv
import json
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
from garden._full_class_engine import full_class_null_max
from garden.spec_class import SubsetClass
from searchers.scripted import Adaptive, Greedy

ALPHAS = (0.10, 0.05, 0.01)
BATCHES = ("b1-baseline", "b2-arms", "b3-models", "b4-s3-recal", "b5-opus")
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"

# Arms B and C: the agent arm's configuration, from experiments/e_agent.py CONFIGS["s0"].
M, T, T_OOS, K, D = 50, 5000, 1000, 40, 3
CLASS = SubsetClass(max_size=D, signed=True)      # 82,240 members at K=40
SEED0, BLOCK = 100_000, 25                        # used by no earlier experiment
N_DRAWS_B, B_B = 5000, 10_000
N_DRAWS_C, B_C = 500, 50_000
SEARCHERS = ("greedy", "adaptive")

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#8a8a86", "#222222", "#8a8a86"


# ------------------------------------------------------------------ arm A

def read_manifest(runs_root: Path) -> list[dict]:
    rows: list[dict] = []
    for b in BATCHES:
        p = runs_root / b / "runs.csv"
        if not p.exists():
            continue
        with p.open(newline="") as fh:
            rd = csv.reader(fh)
            fields = next(rd)
            rows += [{k: json.loads(v) for k, v in zip(fields, row)} for row in rd]
    return rows


def s0_pvalues(rows: list[dict]) -> list[dict]:
    """Every graded s0 run carrying a p-value. s0 is the pure null, so every
    rejection is a type-I error; s3 carries a real edge and is not this
    question."""
    return [r for r in rows
            if r["config"] == "s0" and r["graded"] and r["p_value"] is not None]


def summarize(name: str, p: np.ndarray) -> dict:
    ks = kstest(p, "uniform")
    out = {"group": name, "n": int(p.size),
           "ks_stat": float(ks.statistic), "ks_p": float(ks.pvalue),
           "ks_crit_05": float(ks_critical_value(p.size, 0.05)), "levels": {}}
    for a in ALPHAS:
        rate, lo, hi = type1_rate(p, alpha=a)
        out["levels"][a] = {"rejections": int(np.sum(p < a)), "rate": rate,
                            "lo": lo, "hi": hi}
    return out


def groups_of(runs: list[dict]) -> dict[str, np.ndarray]:
    g = {"pooled": np.array([r["p_value"] for r in runs], dtype=float)}
    for model in sorted({r["model"] for r in runs}):
        g[model] = np.array([r["p_value"] for r in runs if r["model"] == model],
                            dtype=float)
    return g


def arms_of(runs: list[dict]) -> dict[str, np.ndarray]:
    """Not pre-registered; reported for context. The pre-registration notes that
    the gate and pushed arms saw a 5% bar during their search, which changes
    behaviour rather than the validity of the p-value."""
    return {arm: np.array([r["p_value"] for r in runs if r["arm"] == arm], dtype=float)
            for arm in sorted({r["arm"] for r in runs})}


def table(rows: list[dict], title: str, note: str = "") -> list[str]:
    L = [title, "-" * 78]
    if note:
        L += [note, ""]
    L += [f"{'group':<22}{'n':>6}" + "".join(f"{f'a={a}':>22}" for a in ALPHAS),
          f"{'':<22}{'':>6}" + "".join(f"{'k    rate (95% CI)':>22}" for _ in ALPHAS)]
    for s in rows:
        line = f"{s['group']:<22}{s['n']:>6}"
        for a in ALPHAS:
            d = s["levels"][a]
            line += f"{d['rejections']:>4}  {d['rate']:.4f} ({d['lo']:.3f}-{d['hi']:.3f})".rjust(22)
        L.append(line)
    L += ["", f"{'group':<22}{'n':>6}{'KS stat':>12}{'KS p':>12}{'KS crit .05':>14}"]
    for s in rows:
        L.append(f"{s['group']:<22}{s['n']:>6}{s['ks_stat']:>12.4f}"
                 f"{s['ks_p']:>12.4f}{s['ks_crit_05']:>14.4f}")
    return L + [""]


def figure(groups: dict[str, np.ndarray], out: Path) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"pooled": INK, "claude-sonnet-5": BLUE, "claude-fable-5-1": ORANGE,
              "greedy": BLUE, "adaptive": ORANGE}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    for ax, hi, label in ((axes[0], 1.0, "all p-values"),
                          (axes[1], 0.10, "the left tail, where 1% lives")):
        ax.plot([0, hi], [0, hi], color=GRAY, lw=1.2, ls="--", zorder=1,
                label="U(0,1)" if hi == 1.0 else None)
        for name, p in groups.items():
            x = np.sort(p)
            y = np.arange(1, x.size + 1) / x.size
            ax.step(np.concatenate([[0], x]), np.concatenate([[0], y]), where="post",
                    color=colors.get(name, GRAY), lw=1.6, zorder=2,
                    label=f"{name} (n={p.size})" if hi == 1.0 else None)
        ax.set_xlim(0, hi)
        ax.set_ylim(0, hi if hi < 1 else 1.0)
        ax.set_xlabel(f"p-value — {label}", color=INK, fontsize=10)
        ax.grid(alpha=0.25, zorder=0, linewidth=0.8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=9)
    for a in ALPHAS:
        axes[1].axvline(a, color=GRAY, lw=0.8, alpha=0.7, zorder=1)
    axes[0].set_ylabel("empirical CDF", color=INK, fontsize=10)
    axes[0].legend(frameon=False, fontsize=9, loc="lower right")
    fig.suptitle("s0 p-values against U(0,1) — calibration-at-1pct", fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def arm_a(out_dir: Path, runs_dir: Path) -> None:
    rows = read_manifest(runs_dir)
    runs = s0_pvalues(rows)
    if not runs:
        raise SystemExit("no graded s0 runs carrying a p-value")

    groups, arms = groups_of(runs), arms_of(runs)
    by_group = [summarize(k, v) for k, v in groups.items()]
    by_arm = [summarize(k, v) for k, v in arms.items()]

    s0_all = [r for r in rows if r["config"] == "s0"]
    L = ["calibration-at-1pct — arm A: the existing s0 runs, re-scored", "=" * 78,
         f"manifest rows {len(rows)}; s0 runs {len(s0_all)}; graded and carrying a "
         f"p-value {len(runs)}", ""]
    L += table(by_group, "PRE-REGISTERED — per model and pooled")
    L += table(by_arm, "BY ARM — context, not pre-registered",
               "The gate and pushed arms saw a 5% bar during their search.")
    L += ["FIGURE", "-" * 78,
          "  " + figure(groups, out_dir / "calibration_at_1pct_ecdf.png"), ""]

    text = "\n".join(L)
    print(text)
    (out_dir / "calibration_at_1pct.txt").write_text(text + "\n")
    with (out_dir / "calibration_at_1pct_data.pkl").open("wb") as fh:
        pickle.dump({"groups": groups, "arms": arms, "by_group": by_group,
                     "by_arm": by_arm, "alphas": ALPHAS}, fh)


# ------------------------------------------------------------ arms B and C

def build(name: str, seed: int):
    return Greedy(seed=seed) if name == "greedy" else Adaptive(max_features=D, seed=seed)


def run_draw(B: int, seed: int) -> dict:
    """One null draw: price the declared class once, then score each searcher's
    own submission against it. The class null is a property of the base columns
    and the class, so both searchers share it."""
    t0 = time.time()
    cfg = DGPConfig(M=M, T=T, T_oos=T_OOS, K=K, s=0, rho=0.0, sigma=1.0, seed=seed)
    ann = float(np.sqrt(cfg.periods_per_year))
    data = generate(cfg)

    base = Sandbox(data, periods_per_year=cfg.periods_per_year).base_feature_columns()
    L = int(select_block_length(base - base.mean(axis=0)))
    M_b, _, floor, cap = full_class_null_max(base, CLASS, B=B, block_length=L,
                                             annualization=ann, seed=seed)
    out: dict = {"_draw": {"block_length": L, "floor": int(floor), "cap": int(cap),
                           "null_max_mean": float(M_b.mean())}}
    for name in SEARCHERS:
        sb = Sandbox(data, periods_per_year=cfg.periods_per_year, spec_class=CLASS)
        build(name, seed).run(sb)
        _, dist = sb.submission
        sr = float(dist.mean)
        out[name] = {"p_value": float((1 + np.sum(M_b >= sr)) / (B + 1)), "sr_sel": sr}
    out["_draw"]["seconds"] = time.time() - t0
    return out


def run_scripted(arm: str, n_draws: int, B: int, workers: int | None,
                 checkpoint_dir: str | None, git: dict) -> dict:
    starts = list(range(0, n_draws, BLOCK))
    cells = {(arm, s): [(B, SEED0 + i) for i in range(s, min(s + BLOCK, n_draws))]
             for s in starts}
    got = run_cells(run_draw, cells, checkpoint_dir=checkpoint_dir, workers=workers)
    rows = [d for s in starts for d in got[(arm, s)]]
    data = {"arm": arm, "git_at_launch": git, "seeds": SEED0 + np.arange(n_draws),
            "settings": {"M": M, "T": T, "K": K, "d": D, "B": B, "draws": n_draws,
                         "class_size": CLASS.size(K), "class": CLASS.name},
            "seconds": np.array([r["_draw"]["seconds"] for r in rows]),
            "block_length": np.array([r["_draw"]["block_length"] for r in rows]),
            "floor": np.array([r["_draw"]["floor"] for r in rows]),
            "cap": np.array([r["_draw"]["cap"] for r in rows])}
    for name in SEARCHERS:
        data[name] = {f: np.array([r[name][f] for r in rows])
                      for f in ("p_value", "sr_sel")}
    return data


def report_scripted(data: dict, out_dir: Path, full_n: int) -> str:
    s, n = data["settings"], data["settings"]["draws"]
    secs = data["seconds"]
    git = data["git_at_launch"]
    L = [f"calibration-at-1pct — arm {data['arm']}: scripted searchers under the declared class",
         "=" * 78,
         f"n={n} draws, B={s['B']:,}, K={s['K']}, M={s['M']}, T={s['T']:,}, "
         f"class {s['class']} ({s['class_size']:,} members)",
         f"git at launch {git['commit'][:7]}{' (dirty)' if git['dirty'] else ''}", ""]

    rows = [summarize(name, data[name]["p_value"]) for name in SEARCHERS]
    L += table(rows, "TYPE-I AND UNIFORMITY")

    L += ["COST", "-" * 78,
          f"  per draw   mean {secs.mean():7.2f}s   median {np.median(secs):7.2f}s"
          f"   max {secs.max():7.2f}s",
          f"  this run   {secs.sum() / 3600:.2f} CPU-hours over {n} draws"]
    if n < full_n:
        L.append(f"  projected  {secs.mean() * full_n / 3600:.1f} CPU-hours for the full "
                 f"{full_n} draws "
                 f"({secs.mean() * full_n / 3600 / 32:.1f} h wall on 32 cores)")
    L += ["", "GUARDS AND BLOCK LENGTHS", "-" * 78,
          f"  variance floor binds {int(data['floor'].sum())}   "
          f"sharpe cap binds {int(data['cap'].sum())}",
          f"  block length: min {int(data['block_length'].min())}, "
          f"median {int(np.median(data['block_length']))}, "
          f"max {int(data['block_length'].max())}", ""]
    return "\n".join(L)


def compare_arms(arm_c: dict, out_dir: Path) -> list[str]:
    """Decision rule 3: the B=50,000 rejection rate at 1% must lie inside the
    B=10,000 Wilson interval computed on the same draws."""
    p = out_dir / "calibration_at_1pct_armB_data.pkl"
    if not p.exists():
        return ["TAIL RESOLUTION", "-" * 78,
                "  arm B's data file is absent; run arm B first", ""]
    with p.open("rb") as fh:
        arm_b = pickle.load(fh)
    n = arm_c["settings"]["draws"]
    L = ["TAIL RESOLUTION — arm C against arm B on the same first "
         f"{n} draws", "-" * 78]
    for name in SEARCHERS:
        pb, pc = arm_b[name]["p_value"][:n], arm_c[name]["p_value"][:n]
        rb, lo, hi = type1_rate(pb, alpha=0.01)
        rc, _, _ = type1_rate(pc, alpha=0.01)
        inside = lo <= rc <= hi
        L.append(f"  {name:<10} B=10,000 {rb:.4f} ({lo:.4f}-{hi:.4f})   "
                 f"B=50,000 {rc:.4f}   inside: {'yes' if inside else 'NO'}")
    return L + [""]


def arm_bc(arm: str, out_dir: Path, workers: int | None, checkpoint_dir: str | None,
           smoke: int | None) -> None:
    full_n, B = (N_DRAWS_B, B_B) if arm == "B" else (N_DRAWS_C, B_C)
    n = smoke if smoke else full_n
    data = run_scripted(arm, n, B, workers, checkpoint_dir, git_state())

    text = report_scripted(data, out_dir, full_n)
    if arm == "C":
        text += "\n" + "\n".join(compare_arms(data, out_dir))
    if not smoke:
        groups = {name: data[name]["p_value"] for name in SEARCHERS}
        text += "\nFIGURE\n" + "-" * 78 + "\n  " + figure(
            groups, out_dir / f"calibration_at_1pct_arm{arm}_ecdf.png") + "\n"
    print(text)

    suffix = f"_arm{arm}_smoke{n}" if smoke else f"_arm{arm}"
    (out_dir / f"calibration_at_1pct{suffix}.txt").write_text(text + "\n")
    with (out_dir / f"calibration_at_1pct{suffix}_data.pkl").open("wb") as fh:
        pickle.dump(data, fh)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("A", "B", "C"), default="A")
    ap.add_argument("--runs-dir", default=str(RUNS_ROOT))
    ap.add_argument("--out", default="figures")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--checkpoint-dir", default=None)
    ap.add_argument("--smoke", type=int, default=None,
                    help="run this many draws instead of the full count, and "
                         "report the measured per-draw cost. Sizes the real run.")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if a.arm == "A":
        arm_a(out_dir, Path(a.runs_dir))
    else:
        arm_bc(a.arm, out_dir, a.workers, a.checkpoint_dir, a.smoke)


if __name__ == "__main__":
    main()
