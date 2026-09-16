"""The three figures behind the README's headline findings, as PNGs.

Run after the experiments have written their data files:

    python -m experiments.plot_headline_figures

  figures/headline_breadth.png       E19(c): the naive correction degrades as the candidate set widens,
                                     while both repairs stay at nominal.
  figures/headline_anchor_rank.png   E17b: inflation grades with how strongly the anchor tracks
                                     performance, along the curve the order statistics predicted first.
  figures/headline_dose_response.png E18: the same effect as a search's menu becomes more data-dependent.

Every point is a pre-registered measurement with a Wilson 95% interval; the dashed line is the 5% a
correct test should hit. Where the two repairs agree almost exactly, replay is drawn dashed on top of the
declared class so both remain visible. Numbers and caveats are in SCOPE.md.
"""
from __future__ import annotations

import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from estimator.metrics import type1_rate
from experiments.e17b_anchor_rank import LIMIT as RANK_LIMIT

BLUE = "#2a78d6"      # naive: the Reality Check applied to the log
ORANGE = "#eb6834"    # recursive: replay inside each resample
GREEN = "#2e9e5b"     # full class: declared in advance
GRAY = "#8a8a86"      # the 5% a correct test should hit
ALPHA = 0.05
NAIVE_LABEL = "Reality Check on the search's log"
REPLAY_LABEL = "replay (recursive bootstrap)"
CLASS_LABEL = "declared class"


def rates(p_values: np.ndarray):
    rate, lo, hi = type1_rate(p_values, alpha=ALPHA)
    return rate * 100, (rate - lo) * 100, (hi - rate) * 100


def series(arrays):
    out = np.array([rates(a) for a in arrays])
    return out[:, 0], np.vstack([out[:, 1], out[:, 2]])


def draw(ax, x, arrays, colour, label, dashed=False):
    y, err = series(arrays)
    ax.errorbar(x, y, yerr=err, marker="o", markersize=5, capsize=3, color=colour, label=label,
                linestyle="--" if dashed else "-", linewidth=1.6, zorder=3 if dashed else 2)


def finish(ax, title, subtitle, xlabel, legend=True):
    ax.axhline(ALPHA * 100, color=GRAY, linestyle="--", linewidth=1, zorder=1)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("false positives on data with no edge (%)")
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=26 if subtitle else 10)
    if subtitle:
        ax.text(0, 1.03, subtitle, transform=ax.transAxes, fontsize=9, color="#555", va="bottom")
    ax.spines[["top", "right"]].set_visible(False)
    if legend:
        ax.legend(frameon=False, fontsize=9)


def ordinal(rank: int, last: int) -> str:
    if rank == 1:
        return "winner"
    if rank == last:
        return "worst"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(rank % 10 if rank % 100 not in (11, 12, 13) else 0, "th")
    return f"{rank}{suffix}"


def breadth(path="figures/headline_breadth.png"):
    d = pickle.load(open("figures/e19c_feature_count_data.pkl", "rb"))
    Ks, rhos = list(d["Ks"]), list(d["rhos"])
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, (r, rho) in zip(axes, enumerate(rhos)):
        draw(ax, Ks, [d["p_naive"][r, k] for k in range(len(Ks))], BLUE, NAIVE_LABEL)
        draw(ax, Ks, [d["p_full_class"][r, k] for k in range(len(Ks))], GREEN, CLASS_LABEL)
        draw(ax, Ks, [d["p_recursive"][r, k] for k in range(len(Ks))], ORANGE, REPLAY_LABEL, dashed=True)
        ax.set_xscale("log", base=2)
        ax.set_xticks(Ks); ax.set_xticklabels(Ks)
        finish(ax, "uncorrelated features" if not rho else f"features correlated at {rho:g}", "",
               "candidate features the search could choose from", legend=(rho == 0))
    axes[1].set_ylabel("")
    fig.suptitle("A search that builds on its own winner: the standard correction degrades\n"
                 "as the candidate set widens, while both repairs hold",
                 fontsize=12.5, fontweight="bold", x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def anchor_rank(path="figures/headline_anchor_rank.png"):
    d = pickle.load(open("figures/e17b_anchor_rank_data.pkl", "rb"))
    ranks = list(d["ranks"])
    x = np.arange(len(ranks))
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.plot(x, [RANK_LIMIT[r] * 100 for r in ranks], color=GRAY, linestyle=":", linewidth=1.4,
            marker="_", markersize=13, label="predicted before the run (theory)")
    draw(ax, x, [d["p_naive"][i] for i in range(len(ranks))], BLUE, NAIVE_LABEL)
    draw(ax, x, [d["p_recursive"][i] for i in range(len(ranks))], ORANGE, REPLAY_LABEL)
    ax.set_xticks(x)
    ax.set_xticklabels([ordinal(r, ranks[-1]) for r in ranks])
    finish(ax, "It is chasing winners that does the damage",
           "measured against a prediction fixed before the run",
           "which feature the search built its next candidate around")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def dose_response(path="figures/headline_dose_response.png"):
    d = pickle.load(open("figures/e18_depth_data.pkl", "rb"))
    order = [("lattice", "whole grid\n(fixed in advance)"), ("beam16", "keep 16"), ("beam4", "keep 4"),
             ("beam2", "keep 2"), ("adaptive", "keep 1\n(greedy)")]
    keys = [k for k, _ in order]
    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    draw(ax, x, [d[k]["p_naive"] for k in keys], BLUE, NAIVE_LABEL)
    draw(ax, x, [d[k]["p_full_class"] for k in keys], GREEN, CLASS_LABEL)
    draw(ax, x, [d[k]["p_recursive"] for k in keys], ORANGE, REPLAY_LABEL, dashed=True)
    ax.set_xticks(x); ax.set_xticklabels([lbl for _, lbl in order], fontsize=9)
    finish(ax, "Narrowing around its own results makes it worse",
           "each step carries fewer candidates forward, so later ones lean harder on earlier results",
           "how much of each round the search keeps")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def main() -> None:
    for build in (breadth, anchor_rank, dose_response):
        print(f"wrote {build()}")


if __name__ == "__main__":
    main()
