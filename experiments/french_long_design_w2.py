"""French long history, section f REDONE under W2 (draft `prereg/french-long-history.md`; the
author's answer 6, 2026-10-11). Outcome-free; laptop.

As `experiments/french_long_design.py` (the already-read 2009-2019 pool's dependence only;
gross streams demeaned over the pool; stationary row resampling to the target length), but
every weighted null is W2 (block starts ~ w^2, the first ~ q, q-centring;
`estimator.recency.stream_test_w2`, `experiments.recency_planted_2.class_w2`), h = 1,260.

Lengths: B1 (1926-07-01 .. 1989-12-31, about 63.5 years: 16,000 rows) and B2 (to
2019-12-31, about 93.5 years: 23,560 rows). Per length: the stream's W2 bars (5 panels,
B 2,000) at the registered alphas, d = 1 (0.03 / 0.06) and d = 0 (0.01 / 0.02); the class's
W2 bars (3 panels, B 2,000) at 0.01 / 0.02; the net Sharpe at 80% power over the weighted
effective years.

Seeds: 716000-716999 (checked 2026-10-11: NO COLLISION).

    python -m experiments.french_long_design_w2 --out runs/french_long_design_w2/2026-10-11
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

LENGTHS = {"B1": 16000, "B2": 23560}
ALPHAS = {"stream d = 1": (0.03, 0.06), "stream d = 0 (NOT IMPLEMENTABLE)": (0.01, 0.02), "class": (0.01, 0.02)}
B = 2000
H = 1260


def main(argv=None) -> int:
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import recency_planted as P1
    from experiments import recency_planted_2 as P2
    from experiments.binance_design_quantities import certified_sharpe
    from experiments.french_long_design import POOL, build_pool
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
    seeds = iter(range(716000, 717000))
    qs = sorted({round(1 - x, 4) for v in ALPHAS.values() for x in v})
    rec = {"pool": man, "B": B, "h": H, "lengths": {}}
    for name, T in LENGTHS.items():
        w = Rc.weights(T, H)
        neff_y = w.sum() ** 2 / (w * w).sum() / 252
        r = {"rows": T, "years": T / 252, "n_eff_years": neff_y, "stream": [], "class": []}
        for _ in range(5):
            s = next(seeds)
            rng = np.random.default_rng(s)
            i = P1.pool_rows(T, n_pool, P1.ROW_BLOCK, rng)
            bc = BC[i]
            L = int(select_block_length(bc - bc.mean(axis=0)))
            x = bc[:, int(rng.integers(bc.shape[1]))]
            M = Rc.stream_test_w2(x, L, 252.0, B, s, h=H)["null_max"]
            r["stream"].append({"L": L, "q": {f"{q:.4f}": float(np.quantile(M, q)) for q in qs}})
        for _ in range(3):
            s = next(seeds)
            rng = np.random.default_rng(s)
            i = P1.pool_rows(T, n_pool, P1.ROW_BLOCK, rng)
            bc = BC[i]
            L = int(select_block_length(bc - bc.mean(axis=0)))
            t1 = time.time()
            Mb = class_maxima_w2(G, i, L, s, B)
            r["class"].append({"L": L, "seconds": time.time() - t1,
                               "q": {f"{q:.4f}": float(np.quantile(Mb, q)) for q in qs}})
        summ = {}
        for test, alphas in ALPHAS.items():
            src = r["class"] if test == "class" else r["stream"]
            for lvl, al in zip(("96%", "90%"), alphas):
                bar = float(np.mean([c["q"][f"{1 - al:.4f}"] for c in src]))
                summ[f"{test}, {lvl} (alpha {al})"] = {"bar": bar, "net80": certified_sharpe(bar, neff_y, 252.0)}
        r["summary"] = summ
        rec["lengths"][name] = r
    rec["seconds"] = time.time() - t0
    L = [f"French long history: design numbers under W2 (outcome-free; the 2009-2019 pool's dependence; h {H}; B {B})",
         "=" * 100]
    for name, r in rec["lengths"].items():
        L.append(f"{name}: {r['rows']} rows ({r['years']:.1f} years; weighted effective {r['n_eff_years']:.1f} years)")
        for k, v in r["summary"].items():
            L.append(f"   {k:<44} W2 bar {v['bar']:.3f} -> net 80% {v['net80']:.3f}")
        L.append(f"   class seconds per W2 null (B {B}) {np.mean([c['seconds'] for c in r['class']]):.0f}")
    L.append(f"wall {rec['seconds']:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    print("\n".join(L))
    return 0


def class_maxima_w2(G, i, L, seed, Bn, chunk: int = 512) -> np.ndarray:
    """The class's W2 null maxima, aggregated to pool rows (as `recency_planted_2.class_w2`)."""
    from estimator import recency as Rc
    T, n_pool = len(i), G.shape[1]
    w = Rc.weights(T, H)
    V1, V2 = w.sum(), (w * w).sum()
    pi, q = Rc.w2_pi_q(w, L)
    qp = np.bincount(i, weights=q, minlength=n_pool)
    rng = np.random.default_rng(seed)
    A = np.empty((n_pool, Bn))
    for b in range(Bn):
        A[:, b] = np.bincount(i[Rc.w2_indices(T, L, pi, q, rng)], weights=w, minlength=n_pool)
    den = V1 - V2 / V1
    M = np.full(Bn, -np.inf)
    for s0 in range(0, G.shape[0], chunk):
        X = np.asarray(G[s0:s0 + chunk])
        c = (X @ qp)[:, None]
        P1m, P2m = X @ A, (X * X) @ A
        mean = (P1m - c * V1) / V1
        var = ((P2m - 2 * c * P1m + c * c * V1) - V1 * mean * mean) / den
        M = np.maximum(M, (np.where(var > 0, mean / np.sqrt(np.where(var > 0, var, 1.0)), 0.0) * np.sqrt(252.0)).max(axis=0))
    return M


if __name__ == "__main__":
    raise SystemExit(main())
