"""ETF recent panel: design numbers under W2 (draft `prereg/etf-recent-panel.md`). Outcome-free;
laptop. Nothing is fetched.

The dependence comes only from the already-read ETF recency pool
(`data/planted_cache/recency_pool`: 3,019 rows of 2006-2017, the 82,240 signed members'
gross streams demeaned over the pool, and the base feature columns; manifest SHA-256s
checked). The method is that of `experiments/french_long_design_w2.py`: stationary row
resampling to the target length, then W2 nulls (h 1,260; `estimator.recency.stream_test_w2`)
and the class W2 null (`french_long_design_w2.class_maxima_w2`).

Lengths are counted on the XNYS calendar (exchange_calendars, as `data/fetch_etf.py`):
- in-sample sessions 2005-01-03..2024-12-31, and feature rows = sessions - 255 (warm-up 253
  and the d = 1 lag, as the ETF panel and the French long read);
- choice A, the whole scored stream: Sancho's stream starts at feature row 763 (756 plus
  the d = 1 embargo, as B1), and the class runs on every feature row;
- choice B, scoring 2015-01-02..2024-12-31 only: every test on those sessions.

Per choice: the stream's W2 bars (5 panels, B 2,000) at d = 1 (0.03 / 0.06) and d = 0
(0.01 / 0.02); the class's W2 bars (3 panels) at 0.01 / 0.02; the net Sharpe at 80% power
over the weighted effective years; and the null's 0.90 quantile g, so that L90 = S - g
(`quixote.confidence`).

Holdout detectability: holdout rows = sessions 2025-01-02..--holdout-end. The SE of the
realised Sharpe by Lo's iid formula, and two approximate P(held) values, both by the iid
normal approximation:
- P(held | true Sharpe = bar), taking in-sample S = bar: Phi(g / SE);
- P(held | true Sharpe = 0), for an object certified at S = bar: Phi(-(bar - g) / SE).

Seeds: 720000-720999 (checked 2026-10-11: NO COLLISION).

    python -m experiments.etf_recent_design_w2 --out runs/etf_recent_design_w2/2026-10-11
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from math import erf, sqrt
from pathlib import Path

import numpy as np

ALPHAS = {"stream d = 1": (0.03, 0.06), "stream d = 0 (NOT IMPLEMENTABLE)": (0.01, 0.02), "class": (0.01, 0.02)}
B = 2000
H = 1260
POOL = Path("data/planted_cache/recency_pool")
POOL_SHA256 = {"G.npy": "1a056e8fffc404744f1dcc8e0b6e7bbf7bf1798a09db956e0b91213eba6a9c53",
               "BC.npy": "782ec363463331d8e503fdc6d6deb790abfdc9db06a88fc897c3c35fb3c1d4e6"}
LOST = 255                      # sessions -> feature rows (warm-up 253 + the d = 1 lag)
FIRST = 763                     # Sancho's first scored feature row at d = 1 (756 + embargo)


def sessions(a: str, b: str) -> int:
    import exchange_calendars as xc
    return len(xc.get_calendar("XNYS", start="2004-01-01").sessions_in_range(a, b))


def lengths() -> dict:
    n_in = sessions("2005-01-03", "2024-12-31")
    rows = n_in - LOST
    return {"sessions_insample": n_in, "feature_rows": rows,
            "A": {"stream": rows - FIRST, "class": rows},
            "B": {"stream": sessions("2015-01-02", "2024-12-31"), "class": sessions("2015-01-02", "2024-12-31")}}


def phi(z: float) -> float:
    return 0.5 * (1 + erf(z / sqrt(2)))


def se_sharpe(sr: float, years: float, ppy: float = 252.0) -> float:
    return sqrt((1 + sr * sr / (2 * ppy)) / years)


def main(argv=None) -> int:
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import recency_planted as P1
    from experiments.binance_design_quantities import certified_sharpe
    from experiments.french_long_design_w2 import class_maxima_w2
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout-end", default="2026-10-09", help="the expected last fetched session")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "design.json").exists():
        raise SystemExit("exists; not overwriting")
    for f, h in POOL_SHA256.items():
        if hashlib.sha256((POOL / f).read_bytes()).hexdigest() != h:
            raise SystemExit(f"REFUSED: {f} is not the pool's recorded SHA-256")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    G = np.load(POOL / "G.npy", mmap_mode="r")
    BC = np.load(POOL / "BC.npy")
    n_pool = BC.shape[0]
    seeds = iter(range(720000, 721000))
    qs = sorted({round(1 - x, 4) for v in ALPHAS.values() for x in v} | {0.9})
    ln = lengths()
    n_ho = sessions("2025-01-02", a.holdout_end)
    y_ho = n_ho / 252
    rec = {"pool": {"rows": n_pool, "sha256": POOL_SHA256}, "B": B, "h": H, "lengths": ln,
           "holdout": {"end": a.holdout_end, "rows": n_ho, "years": y_ho, "se_at_0": se_sharpe(0, y_ho)},
           "choices": {}}
    for choice in ("A", "B"):
        r = {}
        for kind, n_panels in (("stream", 5), ("class", 3)):
            T = ln[choice][kind]
            w = Rc.weights(T, H)
            neff_y = w.sum() ** 2 / (w * w).sum() / 252
            panels = []
            for _ in range(n_panels):
                s = next(seeds)
                rng = np.random.default_rng(s)
                i = P1.pool_rows(T, n_pool, P1.ROW_BLOCK, rng)
                bc = BC[i]
                L = int(select_block_length(bc - bc.mean(axis=0)))
                t1 = time.time()
                if kind == "stream":
                    x = bc[:, int(rng.integers(bc.shape[1]))]
                    M = Rc.stream_test_w2(x, L, 252.0, B, s, h=H)["null_max"]
                else:
                    M = class_maxima_w2(G, i, L, s, B)
                panels.append({"seed": s, "L": L, "seconds": time.time() - t1,
                               "q": {f"{q:.4f}": float(np.quantile(M, q)) for q in qs}})
            r[kind] = {"rows": T, "years": T / 252, "n_eff_years": neff_y, "panels": panels}
        summ = {}
        for test, alphas in ALPHAS.items():
            src = r["class" if test == "class" else "stream"]
            g = float(np.mean([p["q"]["0.9000"] for p in src["panels"]]))
            for lvl, al in zip(("96%", "90%"), alphas):
                bar = float(np.mean([p["q"][f"{1 - al:.4f}"] for p in src["panels"]]))
                se = se_sharpe(bar, y_ho)
                summ[f"{test}, {lvl} (alpha {al})"] = {
                    "bar": bar, "net80": certified_sharpe(bar, src["n_eff_years"], 252.0), "g_L90": g,
                    "holdout_se_at_bar": se, "P_held_true_eq_bar": phi(g / se),
                    "P_held_true_0_certified_at_bar": phi(-(bar - g) / se_sharpe(0, y_ho))}
        r["summary"] = summ
        rec["choices"][choice] = r
    rec["seconds"] = time.time() - t0
    L = [f"ETF recent panel: design numbers under W2 (outcome-free; the ETF recency pool's dependence, "
         f"{n_pool} rows of 2006-2017; h {H}; B {B})", "=" * 100,
         f"in-sample sessions {ln['sessions_insample']}, feature rows {ln['feature_rows']}; "
         f"holdout 2025-01-02..{a.holdout_end}: {n_ho} rows ({y_ho:.2f} years), SE at Sharpe 0 {rec['holdout']['se_at_0']:.3f}"]
    for choice, r in rec["choices"].items():
        tag = "A, the whole scored stream" if choice == "A" else "B, scoring 2015-01-02..2024-12-31 only"
        L.append(f"choice {tag}: stream {r['stream']['rows']} rows (effective {r['stream']['n_eff_years']:.1f} y), "
                 f"class {r['class']['rows']} rows (effective {r['class']['n_eff_years']:.1f} y)")
        for k, v in r["summary"].items():
            L.append(f"   {k:<44} W2 bar {v['bar']:.3f} -> net 80% {v['net80']:.3f}; L90 gap {v['g_L90']:.3f}; "
                     f"P(held | true = bar) {v['P_held_true_eq_bar']:.2f}; P(held | true 0, certified at bar) "
                     f"{v['P_held_true_0_certified_at_bar']:.2f}")
    L.append(f"wall {rec['seconds']:.0f} s")
    (out / "design.txt").write_text("\n".join(L) + "\n")
    (out / "design.json").write_text(json.dumps(rec, indent=1, default=float))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
