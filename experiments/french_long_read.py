"""The French long-history in-sample reads, B1 and B2 (draft `prereg/french-long-history.md`).
Box only (Linux x86_64, the Linux LightGBM pin), the Sancho fits and the class tier in the
same session. **It refuses to run until the registration is live.** Prints no outcome; the
reader is `experiments/read_french_long.py`.

Inputs: the host cuts (`data/french_long_split.py`), each checked against its cut record's
SHA-256:
- B1: the `b1` cut (1926-07-01 .. 1989-12-31);
- B2: the `b1` cut + the `b2-extra` cut (1990-01-01 .. 2008-12-26) + the registered in-sample
  CSV (2008-12-29 .. 2019-12-31, SHA-256 1547da6f...c04e).
Any row after the read's end refuses the read.

In this order:
  0. the bit-for-bit repeat: two Sancho fits at d = 1 and two at d = 0 (positions only);
  1. Sancho at d = 1, one supplied stream, the certificate on the WEIGHTED statistic under W2
     (h 1,260): certified at the 96% level iff p < 0.03, at the 90% level iff p < 0.06;
  2. Sancho at d = 0, NOT IMPLEMENTABLE, the same: 96% iff p < 0.01, 90% iff p < 0.02;
  3. the class maximum (82,240 members, the fast kernel) at the registered timing d = 1, W2:
     96% iff p < 0.01, 90% iff p < 0.02.
Before any fit or pricing call it writes `pins.json`: the SHA-256 of each cut CSV, of X (both
timings) and of Sancho's inputs (section j). It refuses to price if a cut CSV's SHA-256 differs
from its H1 record. For each test: the weighted L90 (W2 null); the UNWEIGHTED statistic, its p and L90 beside, labelled
"unweighted, descriptive, not the certificate"; for the streams, the performance line (the
unweighted net Sharpe over the last 252 and 756 scored rows, 90% intervals). Block length: the
registered rule (the class rule on the base columns over the whole in-sample window), with
the Politis-White median on the last n_eff rows recorded beside.
Sancho: version 2's base view as confirmed at 97d2519 (P and X; no volume or funding on this
panel), M2, G3, L {1, 3, 10, 30}; positions zero on every row whose earned day is not
eligible (after the model; learn2 untouched).

    python -m experiments.french_long_read --read b1 --cuts <b1.cut.json> --out runs/french_long_b1/<date> \
        --expect-head <commit> --wheel ~/WHEEL.whl --workers 6
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REGISTRATION = "756af89c0b7c7663bac184364b722cdb16a73807"
H = 1260
B = 5000
SEEDS = {"b1": 718000, "b2": 718010}                 # +0 d = 1, +1 d = 0, +2 class, +3 performance line
ALPHA = {"stream_d1": (0.03, 0.06), "stream_d0": (0.01, 0.02), "class": (0.01, 0.02)}
ENDS = {"b1": 19891231, "b2": 20191231}
INSAMPLE_CSV_SHA256 = "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e"
UNWEIGHTED_LABEL = "unweighted, descriptive, not the certificate"


# -- inputs --------------------------------------------------------------------------------

def read_csv(path: Path, end: int):
    dates, rows = [], []
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        names = next(rd)[1:]
        for r in rd:
            d = int(r[0].replace("-", ""))
            if d > end:
                raise SystemExit(f"REFUSED: {path.name} holds a row dated {r[0]}, after the read's end")
            dates.append(dt.date.fromisoformat(r[0]))
            rows.append([float(x) / 100.0 if x.strip() else np.nan for x in r[1:]])
    return dates, names, np.array(rows, float)


def load(read: str, paths: list[Path]):
    parts = [read_csv(p, ENDS[read]) for p in paths]
    names = parts[0][1]
    if any(p[1] != names for p in parts):
        raise SystemExit("REFUSED: the cuts' industries differ")
    dates = [d for p in parts for d in p[0]]
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise SystemExit("REFUSED: the cuts' dates are not strictly increasing")
    return dates, names, np.vstack([p[2] for p in parts])


# -- the generic read (the dry path runs it on a synthetic panel) --------------------------

def sancho_inputs(dates, names, R, lag: int):
    from environments.french_long_panel import long_panel
    from environments.french_panel import WARM
    from learn2 import blocks as Bk
    from learn2 import learner as Ln
    panel, info = long_panel(dates, names, R, lag=lag)
    rp, has = info["rp"], info["has"]
    n = has.sum(axis=1)
    market = np.where(n > 0, (rp * has).sum(axis=1) / np.maximum(n, 1), 0.0)
    T = rp.shape[0]
    keep = slice(WARM, T - lag)
    X = Bk.build_X(rp, market)[keep]
    G = Bk.build_groups(rp, market)[keep]
    return panel, info, Ln.from_panel(panel, blocks={"X": X}, groups=G)


def _fit(args):
    dates, names, R, lag = args
    from experiments import binance_design_v2 as D
    D.configure("4h")                                # the carried-forward M2 (roll756, expand)
    panel, info, inp = sancho_inputs(dates, names, R, lag)
    book, first, meta = D.book_of(inp)
    return lag, book, first, meta["seconds_per_fit"]


def stream_block(panel, inp, book, first, eligible, seed: int, alphas, label: str) -> dict:
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from learn2 import views as Vw
    rows = np.arange(first, inp.earned.shape[0])
    s = Vw.net_stream(np.where(eligible, book, 0.0), inp, rows)
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    w = Rc.weights(len(rows), H)
    n_eff = int(round(w.sum() ** 2 / (w * w).sum()))
    tail = bc[-n_eff:]
    L_tail = int(select_block_length(tail - tail.mean(axis=0)))
    wt = Rc.stream_test_w2(s, L, inp.ppy, B, seed, h=H)
    un = Rc.stream_test(s, L, inp.ppy, B, seed)
    return {"test": label, "alphas": {"96%": alphas[0], "90%": alphas[1]}, "n_rows": int(len(rows)),
            "first_earned": str(panel.meta["earned_dates"][rows[0]]),
            "block_length": L, "block_length_last_neff": L_tail, "n_eff_rows": n_eff, "B": B, "seed": seed,
            "weighted_W2": {"S": wt["S"], "p": wt["p"], "L90": wt["confidence"]["L"]["0.90"], "confidence": wt["confidence"],
                            "certified": {"96%": bool(wt["p"] < alphas[0]), "90%": bool(wt["p"] < alphas[1])}},
            "unweighted": {"label": UNWEIGHTED_LABEL, "S": un["S"], "p": un["p"], "L90": un["confidence"]["L"]["0.90"]},
            "performance_line": Rc.performance_line(s, inp.ppy, L, B, seed + 3)}


def class_block(panel, members, seed: int, alphas, cache_dir=None, cache_name="french-long-signed-3") -> dict:
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    from experiments import french_insample_read as FR
    from quixote.confidence import confidence
    T = panel.features.shape[0]
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    cache = pf.build(panel, members, name=cache_name, cache_dir=cache_dir)
    F = pf.feature_returns(panel)
    chunks = (pf.streams(cache, F, s0, min(s0 + CHUNK, cache.N)) for s0 in range(0, cache.N, CHUNK))
    obs, M_b = Rc.class_null_w2(chunks, T, L, panel.periods_per_year, B, seed, H)
    j = int(np.argmax(obs))
    S = float(obs[j])
    p = (1 + int(np.sum(M_b >= S))) / (B + 1)
    conf = confidence(S, M_b, ppy=float(panel.periods_per_year), tier="class, recency-weighted, W2")
    un = FR.price_class(panel, cache, bc, seed, B, alphas[0], panel.feature_names)
    member = cache.members[j]
    return {"test": "class maximum, d = 1", "alphas": {"96%": alphas[0], "90%": alphas[1]}, "n_rows": T, "N": cache.N,
            "block_length": L, "B": B, "seed": seed,
            "weighted_W2": {"S": S, "p": p, "L90": conf["L"]["0.90"], "confidence": conf,
                            "certified": {"96%": bool(p < alphas[0]), "90%": bool(p < alphas[1])},
                            "best_member": {"index": j, "features": [f"{'+' if sg > 0 else '-'}{panel.feature_names[int(k)]}"
                                                                     for k, sg in member]}},
            "unweighted": {"label": UNWEIGHTED_LABEL, "S": un["S"], "p": un["p"], "L90": un["L90"],
                           "best_member": un["best_member"]["features"]}}


def run_read(dates, names, R, read: str, members, workers: int = 4, cache_dir=None, cache_name=None) -> dict:
    t0 = time.time()
    seed = SEEDS[read]
    with ProcessPoolExecutor(workers) as ex:
        fits = list(ex.map(_fit, [(dates, names, R, lag) for lag in (2, 2, 1, 1)]))
    by = {}
    for lag, book, first, secs in fits:
        by.setdefault(lag, []).append((book, first, secs))
    same = {f"d{lag - 1}": bool(np.array_equal(v[0][0], v[1][0])) for lag, v in by.items()}
    out = {"read": read, "repeat_bit_identical": same, "seconds_per_fit": {f"d{l - 1}": v[0][2] for l, v in by.items()}}
    if not all(same.values()):
        out["stopped"] = "two fits differ; nothing priced"
        return out
    for lag, key, al, label, s in ((2, "test1_stream_d1", ALPHA["stream_d1"], "Sancho stream, d = 1", seed),
                                   (1, "test2_stream_d0", ALPHA["stream_d0"], "Sancho stream, d = 0, NOT IMPLEMENTABLE", seed + 1)):
        panel, info, inp = sancho_inputs(dates, names, R, lag)
        book, first, _ = by[lag][0]
        out[key] = stream_block(panel, inp, book, first, info["eligible_earned"], s, al, label)
    panel, info, _ = sancho_inputs(dates, names, R, 2)
    out["test3_class_d1"] = class_block(panel, members, seed + 2, ALPHA["class"], cache_dir,
                                        cache_name or f"french-long-{read}-signed-3")
    out["entry_dates"] = dict(zip(names, info["entry_date"]))
    out["seconds"] = time.time() - t0
    return out


def _sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float64).tobytes()).hexdigest()


def pin_record(dates, names, R, paths) -> dict:
    """The SHA-256 of each cut CSV, of X (both timings) and of Sancho's inputs (version 2's X
    block and the groups, both timings), written before any pricing call (section j)."""
    rec = {"cut_csv_sha256": {Path(p).name: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths},
           "rows": int(R.shape[0]), "first_date": str(dates[0]), "last_date": str(dates[-1])}
    for lag in (2, 1):
        panel, info, inp = sancho_inputs(dates, names, R, lag)
        rec[f"d{lag - 1}"] = {"X_features_sha256": _sha(panel.features), "X_shape": list(panel.features.shape),
                              "v2_X_block_sha256": _sha(inp.blocks["X"]), "groups_sha256": _sha(inp.groups),
                              "entry_dates": dict(zip(names, info["entry_date"]))}
    return rec


# -- refusals and main ---------------------------------------------------------------------

def refusals(expect_head: str, wheel: str | None) -> list[str]:
    import lightgbm
    from experiments import ml_confirm_ridge_stack as C
    from experiments.ml_v2_confirm_2026_10_09 import PINNED_V2
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    bad = []
    if not REGISTRATION:
        bad.append("the registration is not live (REGISTRATION is unset)")
    elif g("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    if f"{platform.system()} {platform.machine()}" != "Linux x86_64":
        bad.append("not Linux x86_64 (the box)")
    if g("rev-parse", "HEAD").stdout.strip() != expect_head:
        bad.append("HEAD is not --expect-head")
    if g("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    lib = Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.so"
    if lightgbm.__version__ != "4.7.0" or not lib.exists() or hashlib.sha256(lib.read_bytes()).hexdigest() != C.LIB_SHA256:
        bad.append("LightGBM is not the Linux pin")
    if not wheel or hashlib.sha256(Path(wheel).expanduser().read_bytes()).hexdigest() != C.WHEEL_SHA256:
        bad.append("the wheel is not the Linux pin")
    for f, blob in PINNED_V2.items():
        if f.startswith("learn2/") and g("rev-parse", f"HEAD:{f}").stdout.strip() != blob:
            bad.append(f"{f} is not the confirmation's blob")
    return bad


def main(argv=None) -> int:
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--read", required=True, choices=list(SEEDS))
    ap.add_argument("--cuts", nargs="+", required=True, help="the host cut records (.cut.json), in date order")
    ap.add_argument("--insample", help="B2: the registered 2008-12-29 .. 2019-12-31 CSV")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect-head", required=True)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    paths = []
    for c in a.cuts:
        rec = json.loads(Path(c).read_text())
        p = Path(c).with_name(Path(rec["csv"]).name)
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != rec["csv_sha256"]:
            bad.append(f"{p.name} is missing or not its cut record's SHA-256")
        paths.append(p)
    if a.read == "b2":
        ins = Path(a.insample or "")
        if not ins.exists() or hashlib.sha256(ins.read_bytes()).hexdigest() != INSAMPLE_CSV_SHA256:
            bad.append("the registered in-sample CSV is missing or not its SHA-256")
        paths.append(ins)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    if (out / "results.json").exists():
        raise SystemExit("results exist; the read runs once")
    out.mkdir(parents=True, exist_ok=True)
    dates, names, R = load(a.read, paths)
    pins = pin_record(dates, names, R, paths)
    (out / "pins.json").write_text(json.dumps(pins, indent=1))          # before any fit or pricing call
    members = members_in_order(CLS, 40)
    rec = {"registration": REGISTRATION, "git_head": a.expect_head, "platform": f"{platform.system()} {platform.machine()}",
           "inputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, "rows": int(R.shape[0]),
           "first_date": str(dates[0]), "last_date": str(dates[-1])}
    rec.update(run_read(dates, names, R, a.read, members, workers=a.workers))
    (out / "results.json").write_text(json.dumps(rec, indent=1, default=float))
    print(f"results written to {out / 'results.json'}; no outcome printed")
    return 0 if "stopped" not in rec else 1


if __name__ == "__main__":
    raise SystemExit(main())
