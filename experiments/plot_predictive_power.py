"""The two figures spec §4.3 and §4.4 actually call for, built from the
already-collected e9 grid (figures/e9_predictive_power_v2_data.pkl) --
no new experiment runs needed, everything here is a view onto results
already reported in SCOPE.md §9.

Figure 1 (§4.3, "the single most legible figure in the project"): realized
decay (E[SR_IS-SR_OOS], now exact -- no measurement noise) vs. predicted
decay (bootstrap's and closed-form(raw)'s), against trial budget N, one
panel per rho.

Figure 2 (§4.4): the correlation-sensitivity figure -- bias (predicted -
realized decay) against rho at a fixed large N, for all three correction
methods. This is the direct visual of SCOPE.md SS9's bias table.

Usage: python -m experiments.plot_predictive_power
"""
from __future__ import annotations

import pickle

import matplotlib.pyplot as plt
import numpy as np

BLUE = "#2a78d6"     # bootstrap
ORANGE = "#eb6834"   # closed-form, raw N
AQUA = "#1baf7a"      # closed-form, effective N
DARK = "#0b0b0b"      # realized (truth)

N_LEVELS = [10, 100, 1000]
RHO_LEVELS = [0.0, 0.3, 0.6, 0.9]


def load():
    with open("figures/e9_predictive_power_v2_data.pkl", "rb") as f:
        return pickle.load(f)


def plot_decay_vs_N(results):
    fig, axes = plt.subplots(1, len(RHO_LEVELS), figsize=(16, 4.2), sharey=False)
    for ax, rho in zip(axes, RHO_LEVELS):
        realized, boot_pred, raw_pred = [], [], []
        for N in N_LEVELS:
            cell = results[(N, rho)]
            realized.append((cell["sr_is"] - cell["sr_oos_true"]).mean())
            boot_pred.append((cell["sr_is"] - cell["sr_deflated_boot"]).mean())
            raw_pred.append((cell["sr_is"] - cell["sr_deflated_raw"]).mean())

        ax.plot(N_LEVELS, realized, "o-", color=DARK, linewidth=2.5, markersize=7, label="realized (truth)")
        ax.plot(N_LEVELS, boot_pred, "o-", color=BLUE, linewidth=2, markersize=6, label="bootstrap-predicted")
        ax.plot(N_LEVELS, raw_pred, "o-", color=ORANGE, linewidth=2, markersize=6, label="closed-form(raw)-predicted")

        ax.set_xscale("log")
        ax.set_xticks(N_LEVELS)
        ax.set_xlabel("trial budget N")
        ax.set_title(f"ρ = {rho}")
        if ax is axes[0]:
            ax.set_ylabel("decay (SR_IS − SR_OOS)")

    axes[-1].legend(loc="upper left", frameon=False, fontsize=8)
    fig.suptitle("Realized vs. predicted decay across trial budget (spec §4.3)", fontsize=12)
    fig.tight_layout()
    fig.savefig("figures/e9_decay_vs_N.png", dpi=150)
    print("Saved figures/e9_decay_vs_N.png")


def plot_bias_vs_rho(results, N=1000):
    fig, ax = plt.subplots(figsize=(6.5, 5))
    for pred_key, color, label in [
        ("sr_deflated_raw", ORANGE, "closed-form (raw N)"),
        ("sr_deflated_eff", AQUA, "closed-form (effective N)"),
        ("sr_deflated_boot", BLUE, "bootstrap"),
    ]:
        bias = []
        for rho in RHO_LEVELS:
            cell = results[(N, rho)]
            realized_decay = cell["sr_is"] - cell["sr_oos_true"]
            predicted_decay = cell["sr_is"] - cell[pred_key]
            bias.append((predicted_decay - realized_decay).mean())
        ax.plot(RHO_LEVELS, bias, "o-", color=color, linewidth=2, markersize=7, label=label)

    ax.axhline(0.0, linestyle="--", color="#8a8a86", linewidth=1.5, zorder=0)
    ax.set_xlabel("ρ (feature correlation)")
    ax.set_ylabel("bias (predicted decay − realized decay)")
    ax.set_title(f"Correlation sensitivity at N={N} (spec §4.4)\n"
                 "above zero = over-deflates, below zero = under-deflates")
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig("figures/e9_bias_vs_rho.png", dpi=150)
    print("Saved figures/e9_bias_vs_rho.png")


if __name__ == "__main__":
    results = load()
    plot_decay_vs_N(results)
    plot_bias_vs_rho(results, N=1000)
