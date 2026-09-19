"""calibration-at-1pct, arm A: re-score the existing s0 runs.

    python -m experiments.calibration_at_1pct [--out figures]

Pre-registered in prereg/calibration-at-1pct.md. Arm A reads the p-value every
graded s0 run already stored, and reports the rejection rate at three levels
with Wilson intervals plus a Kolmogorov-Smirnov test against U(0,1), per model
and pooled.

Arm A gates nothing. At n = 419 a true rate of 1% has a Wilson half-width of
about 0.95 points, so this arm cannot resolve the 1% tail; arms B and C, which
are scripted and go to EC2, are what the pre-registration turns on. The counts
at the three levels were computed on 2026-09-19, before the pre-registration
existed, and are recorded there as observed rather than pre-registered. The
intervals, the KS tests and the figure are new here.

Reports numbers only. Interpretation belongs in the write-up.
"""
from __future__ import annotations

import argparse
import csv
import json
import pickle
from pathlib import Path

import numpy as np
from scipy.stats import kstest

from estimator.metrics import ks_critical_value, type1_rate

ALPHAS = (0.10, 0.05, 0.01)
BATCHES = ("b1-baseline", "b2-arms", "b3-models", "b4-s3-recal", "b5-opus")
RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"

BLUE, ORANGE, GRAY, INK, MUTED = "#2a78d6", "#eb6834", "#8a8a86", "#222222", "#8a8a86"


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
    head = f"{'group':<22}{'n':>6}" + "".join(f"{f'a={a}':>22}" for a in ALPHAS)
    L += [head, f"{'':<22}{'':>6}" + "".join(f"{'k    rate (95% CI)':>22}" for _ in ALPHAS)]
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

    colors = {"pooled": INK, "claude-sonnet-5": BLUE, "claude-fable-5-1": ORANGE}
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
    fig.suptitle("s0 p-values against U(0,1) — calibration-at-1pct, arm A",
                 fontsize=12, color=INK)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return str(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", default=str(RUNS_ROOT))
    ap.add_argument("--out", default="figures")
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(Path(a.runs_dir))
    runs = s0_pvalues(rows)
    if not runs:
        raise SystemExit("no graded s0 runs carrying a p-value")

    groups, arms = groups_of(runs), arms_of(runs)
    by_group = [summarize(k, v) for k, v in groups.items()]
    by_arm = [summarize(k, v) for k, v in arms.items()]

    total = len(rows)
    s0_all = [r for r in rows if r["config"] == "s0"]
    L = ["calibration-at-1pct — arm A: the existing s0 runs, re-scored",
         "=" * 78,
         f"manifest rows {total}; s0 runs {len(s0_all)}; graded and carrying a "
         f"p-value {len(runs)}", ""]
    L += table(by_group, "PRE-REGISTERED — per model and pooled")
    L += table(by_arm, "BY ARM — context, not pre-registered",
               "The gate and pushed arms saw a 5% bar during their search.")
    L += ["FIGURE", "-" * 78, "  " + figure(groups, out_dir / "calibration_at_1pct_ecdf.png"), ""]

    text = "\n".join(L)
    print(text)
    (out_dir / "calibration_at_1pct.txt").write_text(text + "\n")
    with (out_dir / "calibration_at_1pct_data.pkl").open("wb") as fh:
        pickle.dump({"groups": groups, "arms": arms, "by_group": by_group,
                     "by_arm": by_arm, "alphas": ALPHAS}, fh)


if __name__ == "__main__":
    main()
