"""French long history, item f (draft `prereg/french-long-history.md`): design numbers by
simulation, under the recency weights (h = 1,260 rows). Outcome-free.

The pool is the French in-sample panel (the pinned X, 2,516 rows, 2009-12-30 .. 2019-12-27),
which was read in 2026-10 and is used here only for its dependence. **No row before
2008-12-29 is read.** Gross streams (zero cost), demeaned over the pool, so every null is
exact; long panels are stationary row resamples of the pool (block 7), as in the recency
planted runner.

For each candidate in-sample length (20, 40, 64 and 94 years: B1 from 1926-07 is about 64,
B2 about 94; the start date waits on item a):
- the stream tier's null bars under the weights (fixed centring) and without them, at the
  proposed per-test alphas, the stream being a pool base column (5 panels, B 2,000), and
  for iid normal returns;
- the class tier's weighted null bars (3 panels, B 2,000), from the pool's 82,240 member
  streams, aggregated to pool rows;
- the net Sharpe certified with 80% power at each bar (Lo's iid formula, ppy 252, over the
  weighted effective years; over the window's years for the unweighted bars).

Seeds: 708000-708999 (checked: NO COLLISION, 2026-10-09).

    python -m experiments.french_long_design --out runs/french_long_design/2026-10-09
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import time
from pathlib import Path

import numpy as np

LENGTHS = (20, 40, 64, 94)
ALPHAS = {"stream_d1": (0.03, 0.06), "stream_d0": (0.01, 0.02), "class": (0.01, 0.02), "single_stream_ref": (0.04, 0.08)}
B = 2000
H = 1260
POOL = Path(__file__).resolve().parent.parent / "data" / "planted_cache" / "french_long_pool"


def build_pool() -> dict:
    import environments.planted_fast as pf
    from environments.class_table import CHUNK, members_in_order
    from environments.french_panel import build_french_panel
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    POOL.mkdir(parents=True, exist_ok=True)
    if (POOL / "manifest.json").exists():
        return json.loads((POOL / "manifest.json").read_text())
    p = build_french_panel()
    z = np.zeros_like(np.asarray(p.cost_rate, float))
    p = dataclasses.replace(p, cost_rate=z, borrow_rate=np.zeros_like(z))
    members = members_in_order(CLS, p.features.shape[2])
    cache = pf.build(p, members, name="french-long-pool-gross")
    F = pf.feature_returns(p)
    N, T = len(members), p.features.shape[0]
    G = np.lib.format.open_memmap(POOL / "G.npy", mode="w+", dtype=np.float64, shape=(N, T))
    for s0 in range(0, N, CHUNK):
        X = pf.streams(cache, F, s0, min(s0 + CHUNK, N))
        G[s0:s0 + len(X)] = X - X.mean(axis=1, keepdims=True)
    G.flush()
    del G
    bc = np.asarray(RealSandbox(p, spec_class=CLS).base_feature_columns(), float)
    np.save(POOL / "BC.npy", bc - bc.mean(axis=0))
    man = {"T_pool": T, "N": N, "sha256": {f: hashlib.sha256((POOL / f).read_bytes()).hexdigest()
                                           for f in ("G.npy", "BC.npy")}}
    (POOL / "manifest.json").write_text(json.dumps(man, indent=1))
    return man


def main(argv=None) -> int:
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import recency_planted as P
    from experiments.binance_design_quantities import certified_sharpe
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit("exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    man = build_pool()
    G = np.load(POOL / "G.npy", mmap_mode="r")
    BC = np.load(POOL / "BC.npy")
    n_pool = BC.shape[0]
    seeds = iter(range(708000, 709000))
    qs = sorted({1 - x for v in ALPHAS.values() for x in v})
    rec = {"pool": man, "B": B, "h": H, "lengths": {}}
    for Y in LENGTHS:
        T = Y * 252
        w = Rc.weights(T, H)
        neff_y = w.sum() ** 2 / (w * w).sum() / 252
        r = {"rows": T, "n_eff_years": neff_y, "stream": {"weighted": [], "unweighted": []}, "iid": {}, "class": []}
        for _ in range(5):
            s = next(seeds)
            rng = np.random.default_rng(s)
            i = P.pool_rows(T, n_pool, P.ROW_BLOCK, rng)
            bc = BC[i]
            L = int(select_block_length(bc - bc.mean(axis=0)))
            x = bc[:, int(rng.integers(bc.shape[1]))]
            for key, h in (("weighted", H), ("unweighted", None)):
                M = Rc.stream_test(x, L, 252.0, B, s, h=h)["null_max"]
                r["stream"][key].append({"L": L, "q": {f"{q:.3f}": float(np.quantile(M, q)) for q in qs}})
        s = next(seeds)
        z = np.random.default_rng(s).standard_normal(T) * 0.01
        for key, h in (("weighted", H), ("unweighted", None)):
            M = Rc.stream_test(z, 1, 252.0, B, s, h=h)["null_max"]
            r["iid"][key] = {f"{q:.3f}": float(np.quantile(M, q)) for q in qs}
        for _ in range(3):
            s = next(seeds)
            rng = np.random.default_rng(s)
            i = P.pool_rows(T, n_pool, P.ROW_BLOCK, rng)
            bc = BC[i]
            L = int(select_block_length(bc - bc.mean(axis=0)))
            t1 = time.time()
            Mb = class_maxima(G, i, L, s, B)
            r["class"].append({"L": L, "seconds": time.time() - t1,
                               "q": {f"{q:.3f}": float(np.quantile(Mb, q)) for q in qs}})
        # summaries: the mean bar over panels; net Sharpe at 80% power
        summ = {}
        for tier, alphas in ALPHAS.items():
            for lvl, al in zip(("96%", "90%"), alphas):
                q = f"{1 - al:.3f}"
                if tier == "class":
                    bar = float(np.mean([c["q"][q] for c in r["class"]]))
                    summ[f"{tier} {lvl} (alpha {al})"] = {"bar_weighted": bar, "net80_weighted": certified_sharpe(bar, neff_y, 252.0)}
                else:
                    bw = float(np.mean([c["q"][q] for c in r["stream"]["weighted"]]))
                    bu = float(np.mean([c["q"][q] for c in r["stream"]["unweighted"]]))
                    summ[f"{tier} {lvl} (alpha {al})"] = {
                        "bar_weighted": bw, "net80_weighted": certified_sharpe(bw, neff_y, 252.0),
                        "bar_unweighted": bu, "net80_unweighted": certified_sharpe(bu, Y, 252.0),
                        "iid_bar_weighted": r["iid"]["weighted"][q], "iid_bar_unweighted": r["iid"]["unweighted"][q]}
        r["summary"] = summ
        rec["lengths"][str(Y)] = r
    rec["seconds"] = time.time() - t0
    L = ["French long history: design numbers by simulation (outcome-free; the 2009-2019 pool's dependence; "
         f"h {H}; B {B})", "=" * 100]
    for Y, r in rec["lengths"].items():
        L.append(f"{Y} years ({r['rows']} rows; weighted effective {r['n_eff_years']:.1f} years)")
        for k, v in r["summary"].items():
            if "bar_unweighted" in v:
                L.append(f"   {k:<34} weighted bar {v['bar_weighted']:.3f} -> net80 {v['net80_weighted']:.3f}; "
                         f"unweighted bar {v['bar_unweighted']:.3f} -> {v['net80_unweighted']:.3f} "
                         f"(iid: {v['iid_bar_weighted']:.3f} / {v['iid_bar_unweighted']:.3f})")
            else:
                L.append(f"   {k:<34} weighted bar {v['bar_weighted']:.3f} -> net80 {v['net80_weighted']:.3f}")
        L.append(f"   class seconds per panel {np.mean([c['seconds'] for c in r['class']]):.0f}")
    L.append(f"wall {rec['seconds']:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    print("\n".join(L))
    return 0


def class_maxima(G, i, L, seed, Bn, chunk: int = 512) -> np.ndarray:
    """The weighted (fixed-centring) class null maxima, aggregated to pool rows."""
    from estimator import recency as Rc
    from estimator.bootstrap import stationary_bootstrap_indices
    T, n_pool = len(i), G.shape[1]
    w = Rc.weights(T, H)
    V1, V2 = w.sum(), (w * w).sum()
    cnt = np.bincount(i, minlength=n_pool).astype(float)
    rng = np.random.default_rng(seed)
    A = np.empty((n_pool, Bn))
    for b in range(Bn):
        A[:, b] = np.bincount(i[stationary_bootstrap_indices(T, L, rng)], weights=w, minlength=n_pool)
    M = np.full(Bn, -np.inf)
    den = V1 - V2 / V1
    for s0 in range(0, G.shape[0], chunk):
        X = np.asarray(G[s0:s0 + chunk])
        c = ((X @ cnt) / T)[:, None]
        P1, P2 = X @ A, (X * X) @ A
        mean = (P1 - c * V1) / V1
        var = ((P2 - 2 * c * P1 + c * c * V1) - V1 * mean * mean) / den
        M = np.maximum(M, (np.where(var > 0, mean / np.sqrt(np.where(var > 0, var, 1.0)), 0.0) * np.sqrt(252.0)).max(axis=0))
    return M


if __name__ == "__main__":
    raise SystemExit(main())
