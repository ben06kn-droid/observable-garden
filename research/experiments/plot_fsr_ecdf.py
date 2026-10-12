"""7.1's headline figure: the three replay nulls for one bar searcher, one draw.

    python -m experiments.plot_fsr_ecdf <draw.pkl>

The empirical CDFs of nulls 1-3 for `stop-when-cleared` on draw seed 300000,
B = 10,000. It is the picture behind rule 4: the frozen null sits a long way from
the policy null (mean Kolmogorov distance 0.4483 over 2,000 draws) and the
trigger null is indistinguishable from it (0.0000). Colors are the repo's
existing three, and each series also has its own line style, so identity never
depends on color alone.
"""
from __future__ import annotations

import pickle
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

POLICY = "#0b0b0b"     # null 3, the reference
FROZEN = "#eb6834"     # null 1, fixed-sequence replay
TRIGGER = "#2a78d6"    # null 2, trigger replay
GRID = "#d9d9d6"


def ecdf(x: np.ndarray):
    xs = np.sort(x)
    return xs, np.arange(1, xs.size + 1) / xs.size


def main(path: str, out: str = "figures/fixed_sequence_replay_ecdf.png") -> None:
    d = pickle.load(open(path, "rb"))
    fig, ax = plt.subplots(figsize=(7.2, 5))
    series = [("policy replay (null 3), exact", d["policy"], POLICY, "-", 2.4),
              ("trigger replay (null 2)", d["trigger"], TRIGGER, (0, (5, 2)), 2.0),
              ("fixed-sequence replay (null 1)", d["fixed_sequence"], FROZEN, (0, (1, 1.4)), 2.0)]
    for label, arr, color, style, lw in series:
        xs, fs = ecdf(np.asarray(arr))
        ax.plot(xs, fs, color=color, linestyle=style, linewidth=lw, label=label)

    ax.axvline(d["realized_score"], color="#8a8a86", linewidth=1.4, zorder=0)
    ax.annotate(f"realized {d['realized_score']:.2f}", xy=(d["realized_score"], 0.06),
                xytext=(6, 0), textcoords="offset points", color="#4a4a48", fontsize=9)

    ax.set_xlabel("null maximum (annualised Sharpe)")
    ax.set_ylabel("empirical CDF")
    ax.set_title(f"{d['searcher']}: the three replay nulls on one draw\n"
                 f"seed {d['seed']}, B = {d['B']:,}", fontsize=11)
    ax.grid(color=GRID, linewidth=0.8, alpha=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", frameon=False, fontsize=9)

    # the two numbers the figure exists to show, measured on this draw
    pol = np.sort(np.asarray(d["policy"]))
    grid = np.concatenate([pol, np.sort(np.asarray(d["fixed_sequence"]))])
    def cdf(a, g):
        return np.searchsorted(np.sort(a), g, side="right") / a.size
    k1 = float(np.max(np.abs(cdf(d["fixed_sequence"], grid) - cdf(d["policy"], grid))))
    k2 = float(np.max(np.abs(cdf(d["trigger"], grid) - cdf(d["policy"], grid))))
    ax.text(0.03, 0.97, f"this draw: KS(frozen, policy) = {k1:.3f}\n"
                        f"                KS(trigger, policy) = {k2:.3f}",
            transform=ax.transAxes, va="top", fontsize=9, color="#4a4a48")

    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"saved {out}; KS(1,3)={k1:.4f} KS(2,3)={k2:.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
