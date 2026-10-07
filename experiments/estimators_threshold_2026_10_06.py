"""The threshold candidates ET and ETm, `prereg/estimators-exploratory-2026-10-06.md`,
addendum `382ac84`. EXPLORATORY.

Reads the per-panel rows (`--dump`) and the replicate differences (`--dump-diffs`) of
`experiments/estimators_2026_10_06.py`.

ET is the theta whose restricted mean of (theta + B + e_b), over replicates with
theta + B + e_b >= c, equals S. ETm is the average of ET and S - B. Prior art: Zhong &
Prentice (2008), Biostatistics 9(4) 621-634. The table covers certified submissions
only, against both targets.

    python -m experiments.estimators_threshold_2026_10_06 --rows <rows.jsonl> \\
        --diffs <diffs.npz> --out <txt>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.stats import t as tdist

ALPHA = 0.05
TOL = 1e-10


def restricted_mean(theta: float, B: float, e: np.ndarray, c: float) -> float:
    x = theta + B + e
    keep = x >= c
    return float(x[keep].mean()) if keep.any() else float(c)


def et_root(S: float, B: float, e: np.ndarray, c: float) -> tuple[float, bool, float]:
    """(theta, flagged, g at theta) for ET on [S - 3, S - B]; see the addendum."""
    e = np.asarray(e, float)
    lo, hi = S - 3.0, S - B
    if hi < lo:
        lo, hi = hi, lo

    def g(th):
        return restricted_mean(th, B, e, c) - S
    glo, ghi = g(lo), g(hi)
    if glo < 0 and ghi < 0:
        return hi, True, ghi
    if glo > 0 and ghi > 0:
        return lo, True, glo
    if glo == 0:
        return lo, False, 0.0
    if ghi == 0:
        return hi, False, 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        gm = g(mid)
        if (gm < 0) == (glo < 0):
            lo, glo = mid, gm
        else:
            hi, ghi = mid, gm
        if hi - lo < TOL:
            break
    th = 0.5 * (lo + hi)
    return th, False, g(th)


def candidates(S, B, d, c):
    """(base, ET, ETm, flagged, g) from the raw differences d_b of one base."""
    d = np.asarray(d, float)
    e = d - d.mean()
    et, flag, gval = et_root(S, B, e, c)
    base = S - B
    return base, et, 0.5 * (et + base), flag, gval


def stats(err) -> str:
    e = np.asarray(err, float)
    if e.size == 0:
        return "n    0"
    if e.size >= 2:
        sd = e.std(ddof=1)
        lo = e.mean() - tdist.ppf(0.95, e.size - 1) * sd / np.sqrt(e.size)
        tail = f"SD {sd:.3f}  lower95 {lo:+.3f}"
    else:
        tail = "SD undef  lower95 undef"
    return (f"n {e.size:4d}  bias {e.mean():+.3f}  MAE {np.abs(e).mean():.3f}  "
            f"RMSE {np.sqrt((e * e).mean()):.3f}  " + tail)


BLOCKS = (("class argmax", "EB", "class argmax (base EB)  [decision row]"),
          ("extend-while-improving", "EBs", "extend-while-improving (base EBs)  [decision row]"),
          ("extend-while-improving", "EB", "extend-while-improving (base EB)  [reported, no decision]"))
LEVEL_ROWS = ((0.5,), (1.0,), (1.5,), (0.5, 1.0))


def build(rows, diffs):
    out = []
    for r in rows:
        if r["p_class"] >= ALPHA:
            continue
        for name, base, _ in BLOCKS:
            if r["searcher"] != name:
                continue
            B = r["B_EB"] if base == "EB" else r["B_EBs"]
            d = diffs[f"{r['seed']}_{r['level']:.1f}_{base}"]
            b, et, etm, flag, gval = candidates(r["score"], B, d, r["c"])
            out.append({"searcher": name, "base_kind": base, "level": r["level"],
                        "E0": r["E0"], "EH": r["EH"], "base": b, "ET": et, "ETm": etm,
                        "flag": flag, "g": gval, "in_sample": r["in_sample"],
                        "holdout": r["holdout"], "seed": r["seed"]})
    return out


def tabulate(c_rows, decision_lines=True) -> str:
    L = ["Threshold candidates, certified submissions only — EXPLORATORY",
         "(prereg/estimators-exploratory-2026-10-06.md, addendum 382ac84)",
         "=" * 96,
         "  error = estimate - target; lower95 = one-sided 95% lower end of the mean (t)"]
    dec = {}
    for name, base, title in BLOCKS:
        L += ["", title, "-" * 96]
        for lv in LEVEL_ROWS:
            g = [x for x in c_rows if x["searcher"] == name and x["base_kind"] == base
                 and x["level"] in lv]
            lab = "+".join(f"{v:.1f}" for v in lv)
            nf = sum(x["flag"] for x in g)
            neg = sum(x["ET"] < 0 for x in g)
            gbad = sum(abs(x["g"]) > 1e-6 and not x["flag"] for x in g)
            L.append(f"   level {lab}: certified {len(g)}; flagged {nf}; ET below zero {neg}"
                     + (f"; |g| > 1e-6 at the root {gbad}" if gbad else ""))
            for tgt, tname in (("in_sample", "in-sample SR_pop"), ("holdout", "holdout SR_pop")):
                for e in ("E0", "EH", "base", "ET", "ETm"):
                    err = [x[e] - x[tgt] for x in g]
                    L.append(f"      vs {tname:<16} {e:<4}  {stats(err)}")
                    if tgt == "holdout":
                        a = np.asarray(err, float)
                        dec[(name, base, lab, e)] = (
                            (float(a.mean()) if a.size else float("nan")),
                            (float(np.sqrt((a * a).mean())) if a.size else float("nan")), a.size)
    if decision_lines:
        L += ["", "DECISION RULE (addendum 382ac84): at 1.0, 1.5 and pooled 0.5+1.0, against holdout,",
              "mean overstatement <= +0.10 and RMSE not above the base's, on both decision rows",
              "-" * 96]
        qual = {}
        for cand in ("ET", "ETm"):
            ok = True
            for name, base, title in BLOCKS[:2]:
                for lab in ("1.0", "1.5", "0.5+1.0"):
                    m, r_, n = dec[(name, base, lab, cand)]
                    _, rb, _ = dec[(name, base, lab, "base")]
                    passed = n > 0 and m <= 0.10 and r_ <= rb
                    ok &= passed
                    L.append(f"   {cand:<4} {name:<24} base {base:<3} {lab:>7}: mean {m:+.3f} "
                             f"(<= +0.10: {'yes' if m <= 0.10 else 'NO'}), RMSE {r_:.3f} vs base "
                             f"{rb:.3f} ({'not above' if r_ <= rb else 'ABOVE'}), n {n}  -> "
                             f"{'pass' if passed else 'FAIL'}")
            qual[cand] = ok
        L.append("")
        for cand, ok in qual.items():
            pooled = np.mean([dec[(n_, b_, "0.5+1.0", cand)][1] for n_, b_, _ in BLOCKS[:2]])
            L.append(f"   {cand}: {'QUALIFIES' if ok else 'does not qualify'}; pooled RMSE "
                     f"(mean of the two decision rows, 0.5+1.0, holdout) {pooled:.3f}")
        q = [c for c, ok in qual.items() if ok]
        if not q:
            L.append("   -> neither qualifies: no point estimate is registered")
        elif len(q) == 1:
            L.append(f"   -> {q[0]} goes forward")
        else:
            best = min(q, key=lambda c: np.mean([dec[(n_, b_, "0.5+1.0", c)][1]
                                                for n_, b_, _ in BLOCKS[:2]]))
            L.append(f"   -> both qualify; {best} has the lower pooled RMSE and goes forward")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--diffs", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    rows = [json.loads(ln) for ln in open(a.rows)]
    diffs = np.load(a.diffs)
    text = tabulate(build(rows, diffs))
    Path(a.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
