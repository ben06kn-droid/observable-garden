"""How the bar falls with class depth: the 95th percentile of the class-null maximum for
the classes of size at most 1, 2 and 3. EXPLORATORY, reads the null only
(`prereg/new-panels-audit-2026-10-06.md`, item 4).

The panel is the pinned planted panel's in-sample window (`planted_panel.load_base()`:
the pinned X with the real in-sample ETF returns, data already open). The null is the
class null's: every member's net stream, demeaned, on B stationary-bootstrap replicates
drawn as `planted_fast.class_pass_levels` draws them. **No observed score is computed
or compared**: only the replicate maxima are kept.

    python -m experiments.bar_by_depth_2026_10_06 --out runs/new_panels_audit/bar_by_depth.txt
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np

B = 1000
SEED = 20261007


def main(argv=None) -> int:
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from environments.real_sandbox import RealSandbox
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    t0 = time.time()
    base = pp.load_base()
    panel = base.in_sample
    cache = pf.build(panel, base.members)
    T = panel.features.shape[0]
    ann = float(np.sqrt(panel.periods_per_year))
    D = pf.demeaned(panel)
    F = np.einsum("tmk,tm->tk", D, np.asarray(panel.returns, float))
    bc = np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(SEED)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    size = np.array([len(m) for m in cache.members])
    Mx = {k: np.full(B, -np.inf) for k in (1, 2, 3)}
    N = cache.N
    for s in range(0, N, CHUNK):
        X = pf.streams(cache, F, s, min(s + CHUNK, N))
        X0 = X - X.mean(axis=1, keepdims=True)           # demeaned: the null only
        mean = (X0 @ C) / T
        var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
        pos = var > 0
        rep = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
        sz = size[s:s + len(X)]
        for k in (1, 2, 3):
            if (sz == k).any():
                Mx[k] = np.maximum(Mx[k], rep[sz == k].max(axis=0))
        del X, X0, rep
    cum = {1: Mx[1], 2: np.maximum(Mx[1], Mx[2]), 3: np.maximum.reduce([Mx[1], Mx[2], Mx[3]])}
    n = {k: int((size <= k).sum()) for k in (1, 2, 3)}
    L_ = ["How the bar falls with class depth — EXPLORATORY, the class null only",
          "=" * 88,
          f"  panel: the pinned planted panel's in-sample window (pinned X, real in-sample ETF "
          f"returns), T {T}, {panel.features.shape[1]} assets, K {panel.features.shape[2]}",
          f"  null: demeaned net streams, stationary bootstrap, block {L}, B {B}, seed {SEED}; "
          "no observed score computed",
          ""]
    for k in (1, 2, 3):
        q = np.quantile(cum[k], [0.50, 0.90, 0.95, 0.99])
        L_.append(f"  class of size <= {k}: {n[k]:6d} members   null max: median {q[0]:.3f}  "
                  f"q90 {q[1]:.3f}  q95 {q[2]:.3f}  q99 {q[3]:.3f}")
    L_.append("")
    L_.append(f"  the 0.05 bar (q95) at size <= 1 is {np.quantile(cum[1], .95):.3f}, "
              f"{np.quantile(cum[3], .95) - np.quantile(cum[1], .95):.3f} below the "
              f"size <= 3 bar {np.quantile(cum[3], .95):.3f}")
    L_.append(f"  wall {time.time() - t0:.0f} s on the laptop")
    text = "\n".join(L_)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
