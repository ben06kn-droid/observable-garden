"""The Binance panel's scripted in-sample read (`prereg/binance-panel.md`, section m; live at
ecc07f0e6117e92db9ac03be462f418e3b0ac246). Laptop (Darwin arm64) only. No agents.

In this order:
  0. the bit-for-bit repeat: two version 2 fits at d = 0, and two at d = 1, must give
     identical positions, or nothing is priced;
  1. version 2's stream at d = 0 through the supplied-streams tier, certified iff
     p < 0.04. Its 8,104 scored rows; B 5,000; block length by section k's rule (the
     median Politis-White length of the base columns over the whole in-sample window);
     default_rng(701000);
  2. the class maximum against the class null at d = 0, certified iff p < 0.01. All 8,866
     rows; 82,240 members; the fast kernel; B 5,000; block length by the class rule;
     default_rng(701001);
  3. descriptive only: the same stream at d = 1. Its observed net Sharpe and the 2.5% and
     97.5% points of the Sharpe over B 5,000 stationary-bootstrap resamples of the
     stream (block length by section k's rule on the d = 1 panel; default_rng(701002)).
     No p-value and no verdict.
Both streams: the cost rule, and the dead-contract closure after the model.

Recorded, whatever the verdict: for tests 1 and 2, the observed net Sharpe, p, the 90%
lower bound and the confidence fields; for the class, the best member. The runner writes
`results.json` and prints NOTHING about any outcome. The reader is
`experiments/read_binance_insample.py`.

    python -m experiments.binance_insample_read --out runs/binance_insample/2026-10-09 \\
        --wheel ~/og-wheels/lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl --expect-head <commit>
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import platform
import time
from pathlib import Path

import numpy as np

from experiments import french_insample_read as FR

REGISTRATION = "ecc07f0e6117e92db9ac03be462f418e3b0ac246"
NAME = "4h-2021-01"
B = 5000
SEED_STREAM, SEED_CLASS, SEED_D1 = 701000, 701001, 701002
ALPHA_STREAM, ALPHA_CLASS = 0.04, 0.01
PINNED_BLOBS = {**{f: b for f, b in __import__("experiments.ml_v2_confirm_2026_10_09", fromlist=["x"]).PINNED_V2.items()
                   if f.startswith("learn2/")},
                "learn/stream_tier.py": FR.PINNED_BLOBS["learn/stream_tier.py"]}


# -- start-up refusals (section m) --------------------------------------------------------

def refusals(expect_head: str, wheel: str | None, platform_name: str | None = None,
             lib: Path | None = None) -> list[str]:
    import lightgbm
    from environments import binance_pins as Pn
    bad = []
    plat = platform_name or f"{platform.system()} {platform.machine()}"
    if plat != FR.PLATFORM:
        bad.append(f"platform {plat}, not {FR.PLATFORM}")
    if lightgbm.__version__ != FR.LIGHTGBM:
        bad.append(f"LightGBM {lightgbm.__version__}, not {FR.LIGHTGBM}")
    if not wheel or not Path(wheel).expanduser().exists():
        bad.append("no wheel file given (--wheel)")
    elif FR._sha256(Path(wheel).expanduser()) != FR.WHEEL_SHA256:
        bad.append("the wheel's SHA-256 is not the macOS pin")
    lib = lib or FR.lib_path()
    if not lib.exists() or FR._sha256(lib) != FR.LIB_SHA256:
        bad.append("the installed lib_lightgbm.dylib is missing or its SHA-256 is not the registered one")
    for delay in (0, 1):
        F, S = Pn.files(delay)
        for k, p in F.items():
            if not p.exists() or FR._sha256(p) != S[k]:
                bad.append(f"pin {p.name} is missing or not at its registered SHA-256")
    for f, blob in PINNED_BLOBS.items():
        got = FR._git("rev-parse", f"HEAD:{f}").stdout.strip()
        if got != blob:
            bad.append(f"{f}: blob {got or 'missing'} is not the pinned {blob}")
    if FR._git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    if FR._git("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode != 0:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    head = FR._git("rev-parse", "HEAD").stdout.strip()
    if head != expect_head:
        bad.append(f"HEAD {head} is not the expected {expect_head}")
    return bad


# -- the generic pieces (the dry path runs them on a synthetic panel) ----------------------

def setup(raw: dict, v2: dict, costs: dict):
    """(panel at the cost rule, learn2 inputs, alive_earned) for one timing."""
    from learn2 import learner as Ln
    panel = dataclasses.replace(raw["panel"], cost_rate=np.asarray(costs["rates"], float))
    inp = Ln.from_panel(panel, blocks={"X": v2["X"], "V": v2["V"], "F": v2["F"]}, groups=v2["G"])
    alive = np.array([raw["info"][s]["alive_earned"] for s in panel.meta["symbols"]]).T
    return panel, inp, alive


def fit_twice(inp):
    """(the first fit's book, first scored row, whether two fits are bit-identical)."""
    from experiments import binance_design_v2 as D
    D.configure("4h")
    b1, first, _ = D.book_of(inp)
    b2, _, _ = D.book_of(inp)
    return b1, first, bool(np.array_equal(b1, b2))


def whole_window_L(panel) -> tuple[int, np.ndarray]:
    """Section k's rule: the median base-column Politis-White length over all panel rows."""
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments import binance_design_v2_4h as E
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    return E.median_rule(E.pw_lengths(bc), bc.shape[0]), bc


def stream_test(stream: np.ndarray, L: int, ppy: float, B: int, seed: int) -> dict:
    """The supplied-streams tier's computation at a GIVEN block length: the same table,
    rows, null maximum, score, p and confidence as `learn.stream_tier.certify`, whose
    block length would instead come from the scored window's base columns."""
    from estimator.bootstrap import stationary_bootstrap_indices
    from learn import stream_tier
    from quixote.confidence import confidence
    table = stream_tier.table_from_streams(np.asarray(stream, float)[None, :], ppy)
    rng = np.random.default_rng(seed)
    rows = [stationary_bootstrap_indices(len(stream), L, rng) for _ in range(B)]
    M_b = np.asarray(table.null_max(rows), float)
    S = float(table.sharpe(((0, 1.0),)))
    p = (1 + int(np.sum(M_b >= S))) / (B + 1)
    return {"S": S, "p": p, "null_max": M_b, "block_length": int(L),
            "confidence": confidence(S, M_b, ppy=float(ppy), tier="declared stream")}


def describe(stream: np.ndarray, L: int, ppy: float, B: int, seed: int) -> dict:
    """The d = 1 stream, descriptive: the observed net Sharpe and the 2.5%/97.5% points of
    the Sharpe over stationary-bootstrap resamples of the stream itself."""
    from estimator.bootstrap import stationary_bootstrap_indices
    s = np.asarray(stream, float)
    ann = np.sqrt(ppy)
    sh = lambda x: float(x.mean() / x.std(ddof=1) * ann) if x.std(ddof=1) > 0 else 0.0
    rng = np.random.default_rng(seed)
    reps = np.array([sh(s[stationary_bootstrap_indices(len(s), L, rng)]) for _ in range(B)])
    lo, hi = np.quantile(reps, [0.025, 0.975])
    return {"S": sh(s), "ci95": [float(lo), float(hi)], "block_length": int(L), "B": B, "seed": seed}


def run_read(d0: tuple, d1: tuple, members, B: int = B, seeds=(SEED_STREAM, SEED_CLASS, SEED_D1),
             cache_dir=None, cache_name: str = "binance-4h-2021-01-d0-signed-3") -> dict:
    """Step 0, then tests 1 and 2, then the descriptive d = 1 stream. Prints nothing."""
    import environments.planted_fast as pf
    from experiments import binance_design_v2_4h as E
    from learn2 import views as Vw
    t0 = time.time()
    (raw0, v20, c0), (raw1, v21, c1) = d0, d1
    p0, inp0, alive0 = setup(raw0, v20, c0)
    p1, inp1, alive1 = setup(raw1, v21, c1)
    if inp0.d != 0 or inp1.d != 1:
        return {"stopped": f"timings are d = {inp0.d} and d = {inp1.d}, not 0 and 1"}
    book0, first0, same0 = fit_twice(inp0)
    book1, first1, same1 = fit_twice(inp1)
    out = {"repeat_bit_identical": {"d0": same0, "d1": same1}}
    if not (same0 and same1):
        out["stopped"] = "two fits differ; nothing priced"
        return out
    # 1. the d = 0 stream
    rows0 = np.arange(first0, inp0.earned.shape[0])
    s0 = Vw.net_stream(E.close_dead(book0, alive0), inp0, rows0)
    L0, bc0 = whole_window_L(p0)
    st = stream_test(s0, L0, inp0.ppy, B, seeds[0])
    conf = st["confidence"]
    out["test1_stream_d0"] = {"test": "version 2 stream at d = 0, supplied-streams tier", "alpha": ALPHA_STREAM,
                              "window_rows": [int(rows0[0]), int(rows0[-1])], "n_rows": int(len(rows0)),
                              "B": B, "seed": seeds[0], "block_length": st["block_length"],
                              "block_length_rule": "median Politis-White of the base columns over the whole in-sample window",
                              "S": st["S"], "p": st["p"], "certified": bool(st["p"] < ALPHA_STREAM),
                              "L90": conf["L"]["0.90"], "confidence": conf}
    del s0, st
    # 2. the class maximum at d = 0
    cache = pf.build(p0, members, name=cache_name, cache_dir=cache_dir)
    out["test2_class_d0"] = FR.price_class(p0, cache, bc0, seeds[1], B, ALPHA_CLASS, p0.feature_names)
    out["test2_class_d0"]["test"] = "class maximum against the class null at d = 0"
    # 3. descriptive: the d = 1 stream
    rows1 = np.arange(first1, inp1.earned.shape[0])
    s1 = Vw.net_stream(E.close_dead(book1, alive1), inp1, rows1)
    L1, _ = whole_window_L(p1)
    out["descriptive_stream_d1"] = {"label": "descriptive, not a test: the same stream with a one-bar delay",
                                    "window_rows": [int(rows1[0]), int(rows1[-1])], "n_rows": int(len(rows1)),
                                    **describe(s1, L1, inp1.ppy, B, seeds[2])}
    out["seconds"] = time.time() - t0
    return out


def main(argv=None) -> int:
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--wheel")
    ap.add_argument("--expect-head")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "results.json").exists():
        raise SystemExit(f"{out / 'results.json'} exists; the read runs once")
    bad = refusals(a.expect_head or "", a.wheel)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    from environments import binance_pins as Pn
    from experiments import binance_design_v2_4h as E
    out.mkdir(parents=True, exist_ok=True)

    def pinned(delay):
        raw = E.raw_4h(NAME, lag=1 + delay)
        X = Pn.load("X", delay=delay)
        if X.shape != raw["panel"].features.shape:
            raise SystemExit("REFUSED: a pinned X's shape differs from the build")
        raw["panel"] = dataclasses.replace(raw["panel"], features=X)
        return raw, Pn.load("v2", delay=delay), Pn.load("costs", delay=delay)
    members = members_in_order(CLS, 40)
    rec = {"registration": REGISTRATION, "git_head": a.expect_head, "dry_run": False,
           "platform": f"{platform.system()} {platform.machine()}", "pins": {"d0": Pn.SHA256_D0, "d1": Pn.SHA256},
           "lib_lightgbm_sha256": FR._sha256(FR.lib_path()), "wheel_sha256": FR.WHEEL_SHA256,
           "pinned_blobs": PINNED_BLOBS}
    rec.update(run_read(pinned(0), pinned(1), members))
    (out / "results.json").write_text(json.dumps(rec, indent=1, default=float))
    print(f"results written to {out / 'results.json'}; no outcome printed. "
          f"Read with: python -m experiments.read_binance_insample --dir {out}")
    return 0 if "stopped" not in rec else 1


if __name__ == "__main__":
    raise SystemExit(main())
