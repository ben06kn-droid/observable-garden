"""EXPLORATORY, unregistered: the Sablier sample world (2026-11-10) as a quixote panel (`quixote/panel.py`).

Sablier's data is external, under their terms (personal research, nothing redistributed). This script reads
the CSV from where Overfitting-Gate keeps it and writes the panel beside it, in that repo's gitignored
`data/`; nothing here or in its output is committed to either repo. Note:
`research/prereg/sablier-sample-exploratory-2026-11-10.md`.

The panel, as phase 1's French panel is built (`prereg/french-panel.md` c-e; `environments.french_panel`):
- simple returns from the indexed closes (503 returns from 504 closes);
- the declared market: the equal-weighted average of the 12 returns;
- the 20 base signals of `prereg/etf-features.md` (`real_panel._etf_base_signals`), causal, from returns
  only, each as a cross-sectional z-score and an average-tie rank: 40 features; none needs volume;
- the first WARM (253) rows dropped, as the French panel drops its warm-up, so every 252-row window is full;
- masked asset names I00-I11; periods_per_year 252; delay 1; cost_bps 5; borrow_bps_yr 50 (phase 1's
  French-industry costs, `prereg/french-panel.md` e).

    .venv/bin/python research/experiments/sablier_sample_panel.py CSV OUT.npz
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

import quixote.panel as Qp                                       # puts the engine's packages on the path
from environments.french_panel import WARM, rank_average      # noqa: E402
from environments.real_panel import ETF_BASE, _etf_base_signals, _zscore  # noqa: E402


def build(csv_path: Path) -> dict:
    rows = list(csv.reader(open(csv_path)))
    if rows[0][0] != "day":
        raise SystemExit("not the sample world's format (first column 'day')")
    P = np.array([[float(x) for x in r[1:]] for r in rows[1:]])
    r = P[1:] / P[:-1] - 1.0                                        # simple returns, day 1..T-1
    T, M = r.shape
    logp = np.cumsum(np.log1p(r), axis=0)
    sig = _etf_base_signals(logp, r, r.mean(axis=1))
    feats, names = [], []
    for nm in ETF_BASE:
        feats += [_zscore(sig[nm]), rank_average(sig[nm])]
        names += [f"{nm}_z", f"{nm}_rank"]
    F = np.stack(feats, axis=2)
    keep = slice(WARM, T)
    days = np.arange(1, T + 1)                                     # the day whose close each return ends at
    return {"returns": r[keep], "features": F[keep], "feature_names": names, "periods_per_year": 252,
            "delay": 1, "cost_bps": 5.0, "borrow_bps_yr": 50.0,
            "row_labels": [f"d{d:03d}" for d in days[keep]], "asset_names": [f"I{j:02d}" for j in range(M)]}


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    src, out = Path(argv[0]), Path(argv[1])
    d = build(src)
    sha = Qp.save(out, d["returns"], d["features"], d["feature_names"], d["periods_per_year"], delay=d["delay"],
                  cost_bps=d["cost_bps"], borrow_bps_yr=d["borrow_bps_yr"], row_labels=d["row_labels"],
                  asset_names=d["asset_names"])
    F = d["features"]
    print(json.dumps({"source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "panel": str(out),
                      "panel_sha256": sha, "returns": list(d["returns"].shape), "features": list(F.shape),
                      "nonfinite_features": int((~np.isfinite(F)).sum()), "first_row": d["row_labels"][0],
                      "last_row": d["row_labels"][-1], "dropped_for_volume": []}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
