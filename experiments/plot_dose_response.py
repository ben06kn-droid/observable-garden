"""Primary figure for the dose-response sweep (experiments/e5_dose_response.py)
and the secondary divergence-rate diagnostic. Run after e5_dose_response.py
has written figures/e5_dose_response_data.pkl.

Only two of the three requested lines are real full sweeps: naive and
recursive, both n=150 across all 7 variants. Procedure-level bootstrap was
spot-checked for agreement with recursive on 3 variants at n=15
(experiments/e5b_procedure_level_spotcheck.py) -- that's a bias check, not
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
    with open("figures/e5_dose_response_data.pkl", "rb") as f:
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
    fig.savefig("figures/e5_dose_response_primary.png", dpi=150)
    print("Saved figures/e5_dose_response_primary.png")


def plot_divergence(data):
    p_naive, divergence = data["p_naive"], data["divergence"]
    dose_names = {n for n, _ in DOSE_ORDER}

    # Several points cluster tightly (adaptive, neighbor_adaptive land at
    # nearly identical coordinates) -- stack their labels vertically with
    # explicit offsets instead of letting them collide.
    label_offsets = {
        "adaptive (dose max, k=1)": (8, -14),
        "depth_adaptive": (8, 6),
        "neighbor_adaptive": (8, -28),
        "beam2": (8, -4),
        "beam4": (8, 6),
    }

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    for name in p_naive:
        rate, lo, hi = type1_rate(p_naive[name], alpha=0.05)
        div = divergence[name].mean()
        color = BLUE if name in dose_names else ORANGE
        ax.errorbar([div], [rate], yerr=[[rate - lo], [hi - rate]], marker="o",
                    markersize=8, capsize=4, color=color)
        label = name.split(" ")[0]
        dx, dy = label_offsets.get(name, (8, 6))
        ax.annotate(label, (div, rate), fontsize=8, xytext=(dx, dy), textcoords="offset points")

    ax.axhline(0.05, linestyle="--", color=GRAY, linewidth=1.5, zorder=0)
    ax.set_xlabel("divergence rate (mean Jaccard distance, real vs. bootstrap-replicate round-1 beam)")
    ax.set_ylabel("naive bootstrap type-I rate at α=0.05")
    ax.set_title("Type-I inflation tracks candidate-set instability directly")
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([0], [0], marker="o", color=BLUE, label="dose axis (beam width)", linestyle=""),
        Line2D([0], [0], marker="o", color=ORANGE, label="structural axis (depth/neighbor)", linestyle=""),
    ], loc="upper left", frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig("figures/e5_divergence_diagnostic.png", dpi=150)
    print("Saved figures/e5_divergence_diagnostic.png")


if __name__ == "__main__":
    data = load()
    plot_primary(data)
    plot_divergence(data)
