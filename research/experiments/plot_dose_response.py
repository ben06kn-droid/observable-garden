"""Primary figure for the dose-response sweep (experiments/dose_response_beam.py)
and the secondary divergence-rate diagnostic. Run after dose_response_beam.py
has written figures/dose_response_beam_data.pkl.

Only two of the three requested lines are real full sweeps: naive and
recursive, both n=150 across all 7 variants. Procedure-level bootstrap was
spot-checked for agreement with recursive on 3 variants at n=15
(experiments/procedure_spotcheck.py) -- that's a bias check, not
an independent type-I-rate measurement, and is annotated as such rather
than plotted as a fabricated third line.

Usage: python -m experiments.plot_dose_response
"""
from __future__ import annotations

import pickle

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import kstest

from estimator.metrics import type1_rate

BLUE = "#2a78d6"    # naive
ORANGE = "#eb6834"  # recursive
GRAY = "#8a8a86"    # nominal reference

DOSE_ORDER = [
    ("lattice_adaptive (dose 0)", 20),
    ("beam16", 16),
    ("beam4", 4),
    ("beam2", 2),
    ("adaptive (dose max, k=1)", 1),
]
STRUCTURAL = ["depth_adaptive", "neighbor_adaptive"]


def load():
    with open("figures/dose_response_beam_data.pkl", "rb") as f:
        return pickle.load(f)


def plot_primary(data):
    p_naive, p_recursive = data["p_naive"], data["p_recursive"]
    names = [n for n, _ in DOSE_ORDER]
    x = [k for _, k in DOSE_ORDER]

    fig, ax = plt.subplots(figsize=(6.5, 5))

    for series, color, label in [(p_naive, BLUE, "naive"), (p_recursive, ORANGE, "recursive")]:
        rates, los, his = [], [], []
        for name in names:
            rate, lo, hi = type1_rate(series[name], alpha=0.05)
            rates.append(rate); los.append(rate - lo); his.append(hi - rate)
        ax.errorbar(x, rates, yerr=[los, his], marker="o", markersize=6, capsize=4,
                    color=color, label=label, linewidth=2)

    # Recursive's 5 dose-axis points are the SAME underlying measurement,
    # not 5 independent ones -- greedy search converges to the same
    # near-global optimum regardless of beam width on this DGP (~99.7%+ of
    # draws), so sr_sel and M_b coincide across variants. Said once, in the
    # figure, rather than left implicit in equal-looking error bars.
    ax.text(0.98, 0.80, "recursive's 5 points share one\nunderlying measurement (n=150) --\nsee text, not 5 independent draws",
            transform=ax.transAxes, fontsize=7, color=ORANGE, ha="right", va="top", style="italic")

    ax.axhline(0.05, linestyle="--", color=GRAY, linewidth=1.5, zorder=0)
    ax.text(20, 0.037, "nominal α=0.05", color=GRAY, fontsize=9, ha="right", va="top")

    # Procedure-level: agreement spot-check annotation, not a fabricated line.
    # Mark the two spot-checked points with a hollow diamond; one shared
    # caption below the legend explains what it means (no criss-crossing
    # arrows onto nearly-overlapping error bars).
    for xi, name in [(4, "beam4"), (2, "beam2")]:
        ax.plot(xi, type1_rate(p_recursive[name], alpha=0.05)[0], marker="D",
                markersize=10, markerfacecolor="none", markeredgecolor="#52514e",
                markeredgewidth=1.3, linestyle="", zorder=5)
    ax.text(0.02, 0.02, "◇ procedure-level spot-check (n=15): agrees with recursive",
            transform=ax.transAxes, fontsize=8, color="#52514e", va="bottom")

    ax.set_xscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{k}" if k != 20 else "20\n(full lattice)" for k in x])
    ax.set_xlabel("beam width k  (dose: full menu → argmax-only)")
    ax.set_ylabel("type-I rate at α=0.05")
    ax.set_title("Naive bootstrap's type-I rate rises monotonically\nas the candidate menu depends more on realized data")
    ax.legend(loc="upper right", frameon=False)
    ax.set_ylim(0, 0.22)
    ax.margins(x=0.08)
    fig.tight_layout()
    fig.savefig("figures/dose_response_beam_primary.png", dpi=150)
    print("Saved figures/dose_response_beam_primary.png")


def plot_diagnostics(data, entropy_data):
    """Two panels side by side: Jaccard divergence rate and normalized beam
    entropy, both against naive type-I rate. Shown together deliberately --
    entropy was predicted to track type-I more tightly (a magnitude measure
    vs. divergence's rate that saturates near 1.0), but measured on this
    7-point sample it does NOT clearly outperform divergence (Pearson
    r=0.861 vs 0.901; Spearman 0.935 vs 0.972). Reported as found, not
    spun -- both are decent directional diagnostics, neither is a clean
    linear predictor of exact inflation magnitude."""
    from math import comb, log
    from matplotlib.lines import Line2D

    p_naive, divergence = data["p_naive"], data["divergence"]
    norm_entropy = entropy_data["norm_entropy"]
    dose_names = {n for n, _ in DOSE_ORDER}

    label_offsets_div = {
        "adaptive (dose max, k=1)": (8, -14), "depth_adaptive": (8, 6),
        "neighbor_adaptive": (8, -28), "beam2": (8, -4), "beam4": (8, 6),
    }
    label_offsets_ent = {
        "adaptive (dose max, k=1)": (8, -4), "depth_adaptive": (8, 8),
        "neighbor_adaptive": (8, -18), "beam2": (-10, 10), "beam4": (8, -14),
        "beam16": (8, 8),
    }

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))

    for ax, series, offsets, xlabel, title in [
        (axes[0], divergence, label_offsets_div,
         "divergence rate\n(mean Jaccard distance, real vs. replicate round-1 beam)",
         "Divergence rate (a rate, saturates near 1.0)"),
        (axes[1], norm_entropy, label_offsets_ent,
         "normalized beam entropy\n(H / log C(K, beam width))",
         "Normalized entropy (a magnitude -- predicted\nto track more tightly; measured: it doesn't)"),
    ]:
        for name in p_naive:
            rate, lo, hi = type1_rate(p_naive[name], alpha=0.05)
            x_val = series[name].mean() if hasattr(series[name], "mean") else series[name]
            color = BLUE if name in dose_names else ORANGE
            ax.errorbar([x_val], [rate], yerr=[[rate - lo], [hi - rate]], marker="o",
                        markersize=8, capsize=4, color=color)
            label = name.split(" ")[0]
            dx, dy = offsets.get(name, (8, 6))
            ax.annotate(label, (x_val, rate), fontsize=7.5, xytext=(dx, dy), textcoords="offset points")
        ax.axhline(0.05, linestyle="--", color=GRAY, linewidth=1.5, zorder=0)
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel("naive bootstrap type-I rate at α=0.05")
        ax.set_title(title, fontsize=10)

    axes[0].legend(handles=[
        Line2D([0], [0], marker="o", color=BLUE, label="dose axis (beam width)", linestyle=""),
        Line2D([0], [0], marker="o", color=ORANGE, label="structural axis (depth/neighbor)", linestyle=""),
    ], loc="upper left", frameon=False, fontsize=8)

    fig.suptitle("Neither diagnostic is a clean linear predictor of inflation magnitude", fontsize=11)
    fig.tight_layout()
    fig.savefig("figures/dose_response_beam_divergence.png", dpi=150)
    print("Saved figures/dose_response_beam_divergence.png")


if __name__ == "__main__":
    data = load()
    with open("figures/entropy_diagnostic_data.pkl", "rb") as f:
        entropy_data = pickle.load(f)
    plot_primary(data)
    plot_diagnostics(data, entropy_data)
