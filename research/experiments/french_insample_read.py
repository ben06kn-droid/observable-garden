"""The French panel's scripted in-sample read (`prereg/french-panel.md`, section k; live at
de9da1b914bcd2522ef95ddc4be4231eb47b1af0). Laptop (Darwin arm64) only. No agents.

Two tests, run once, in this order:
  (i)  ridge_stack's stream through the supplied-streams tier, certified iff p < 0.04;
       B 5,000, block length by the class rule, default_rng(693000);
  (ii) the class maximum against the class null, certified iff p < 0.01; 82,240 members,
       fast kernel, B 5,000, block length by the class rule, default_rng(693001).
Before pricing, two ridge_stack fits must give bit-identical positions, or nothing is priced.

Recorded for each, whatever the verdict: the observed net Sharpe, p, the 90% lower bound
and the full confidence fields; for the class, the best member's identity. The runner
writes `results.json` and prints NOTHING about any outcome; the reader
(`experiments/read_french_insample.py`) renders it once.

    python -m experiments.french_insample_read --out runs/french_insample/2026-10-07 \
        --wheel ~/og-wheels/lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl --expect-head <commit>

The dry path is `run_read` on a synthetic panel (tests/test_french_insample_read.py); it is
never run on this panel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

import numpy as np

REGISTRATION = "de9da1b914bcd2522ef95ddc4be4231eb47b1af0"
PINNED_BLOBS = {"learn/ridge_stack.py": "2c09b25701038964c97a193f66a5203f99bf0915",
                "learn/inputs.py": "c52ff6d12a71f2c536de8e2bdc3478cc5c00e124",
                "learn/trees.py": "e21f38706067bacf251ef8494fbd8674fc20b1c4",
                "learn/stream_tier.py": "107abb472bb23b606877673e8b80ec75bf3eba95"}
LIGHTGBM = "4.7.0"
WHEEL_SHA256 = "129535462686f274df179133643118c5c5c5667167fe6c3a28d955f0b3c8e868"
LIB_SHA256 = "bc392db609d97730a9ed2acec7a56529b356c03dfad39bebf689523fed7dff18"
X_SHA256 = "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc"
PLATFORM = "Darwin arm64"
B = 5000
SEED_STREAM, SEED_CLASS = 693000, 693001
ALPHA_STREAM, ALPHA_CLASS = 0.04, 0.01


# -- start-up refusals (section d) --------------------------------------------------------

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lib_path() -> Path:
    import lightgbm
    return Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.dylib"


def refusals(expect_head: str, wheel: str | None, platform_name: str | None = None,
             lib: Path | None = None, x_path: Path | None = None) -> list[str]:
    import lightgbm
    from environments.french_panel import PINNED_X
    bad = []
    plat = platform_name or f"{platform.system()} {platform.machine()}"
    if plat != PLATFORM:
        bad.append(f"platform {plat}, not {PLATFORM}")
    if lightgbm.__version__ != LIGHTGBM:
        bad.append(f"LightGBM {lightgbm.__version__}, not {LIGHTGBM}")
    if not wheel or not Path(wheel).expanduser().exists():
        bad.append("no wheel file given (--wheel)")
    elif _sha256(Path(wheel).expanduser()) != WHEEL_SHA256:
        bad.append("the wheel's SHA-256 is not the macOS pin")
    lib = lib or lib_path()
    if not lib.exists() or _sha256(lib) != LIB_SHA256:
        bad.append("the installed lib_lightgbm.dylib is missing or its SHA-256 is not the registered one")
    x_path = Path(x_path) if x_path is not None else PINNED_X
    if not x_path.exists() or _sha256(x_path) != X_SHA256:
        bad.append("the pinned French X is missing or its SHA-256 is not the registered one")
    for f, blob in PINNED_BLOBS.items():
        got = _git("rev-parse", f"HEAD:{f}").stdout.strip()
        if got != blob:
            bad.append(f"{f}: blob {got or 'missing'} is not the pinned {blob}")
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    if _git("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode != 0:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    head = _git("rev-parse", "HEAD").stdout.strip()
    if head != expect_head:
        bad.append(f"HEAD {head} is not the expected {expect_head}")
    return bad


# -- the two tests (generic: the dry path runs them on a synthetic panel) ----------------

def repeat_check(panel, run) -> bool:
    return bool(np.array_equal(run(panel)["positions"], run(panel)["positions"]))


def price_stream(panel, res: dict, bc: np.ndarray, seed: int, B: int, alpha: float) -> dict:
    from learn import inputs as I
    from learn import stream_tier
    rows = res["scored_rows"]
    s = I.net_stream(res["positions"], panel, rows)
    st = stream_tier.certify(s[None, :], bc[rows], panel.periods_per_year, B, seed)
    conf = st["confidence"]
    return {"test": "ridge_stack stream, supplied-streams tier", "alpha": alpha,
            "window_rows": [int(rows[0]), int(rows[-1])], "n_rows": int(len(rows)),
            "B": B, "seed": seed, "block_length": int(st["block_length"]),
            "S": float(st["score"]), "p": float(st["p"]), "certified": bool(st["p"] < alpha),
            "L90": conf["L"]["0.90"], "confidence": conf}


def price_class(panel, cache, bc: np.ndarray, seed: int, B: int, alpha: float,
                feature_names) -> dict:
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    from quixote.confidence import confidence
    T = panel.features.shape[0]
    ann = float(np.sqrt(panel.periods_per_year))
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(seed)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    F = pf.feature_returns(panel)
    M_b = np.full(B, -np.inf)
    best, best_j = -np.inf, -1
    for s0 in range(0, cache.N, CHUNK):
        X = pf.streams(cache, F, s0, min(s0 + CHUNK, cache.N))
        obs = pf._sharpe_rows(X, ann)
        j = int(np.argmax(obs))
        if obs[j] > best:
            best, best_j = float(obs[j]), s0 + j
        X0 = X - X.mean(axis=1, keepdims=True)
        mean = (X0 @ C) / T
        var = ((X0 * X0) @ C - T * mean * mean) / (T - 1)
        pos = var > 0
        rep = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
        M_b = np.maximum(M_b, rep.max(axis=0))
    p = (1 + int(np.sum(M_b >= best))) / (B + 1)
    conf = confidence(best, M_b, ppy=float(panel.periods_per_year), tier="class")
    member = cache.members[best_j]
    return {"test": "class maximum against the class null", "alpha": alpha,
            "window_rows": [0, T - 1], "n_rows": T, "N": cache.N, "B": B, "seed": seed,
            "block_length": L, "S": best, "p": p, "certified": bool(p < alpha),
            "L90": conf["L"]["0.90"], "confidence": conf,
            "best_member": {"index": best_j, "support": [[int(k), float(sg)] for k, sg in member],
                            "features": [f"{'+' if sg > 0 else '-'}{feature_names[int(k)]}"
                                         for k, sg in member]}}


def run_read(panel, members, cache_dir=None, B: int = B, seeds=(SEED_STREAM, SEED_CLASS),
             cache_name: str = "french49-signed-3") -> dict:
    """Repeat check, then (i) and (ii), in that order. Returns the record; prints nothing."""
    import environments.planted_fast as pf
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from learn import ridge_stack
    run = lambda p: ridge_stack.run(p, "ridge_stack")
    t0 = time.time()
    if not repeat_check(panel, run):
        return {"repeat_bit_identical": False, "stopped": "two fits differ; nothing priced"}
    res = run(panel)
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    out = {"repeat_bit_identical": True}
    out["i_stream"] = price_stream(panel, res, bc, seeds[0], B, ALPHA_STREAM)
    cache = pf.build(panel, members, name=cache_name, cache_dir=cache_dir)
    out["ii_class"] = price_class(panel, cache, bc, seeds[1], B, ALPHA_CLASS, panel.feature_names)
    out["seconds"] = time.time() - t0
    return out


def main(argv=None) -> int:
    from environments.class_table import members_in_order
    from environments.french_panel import build_french_panel
    from environments.planted_panel import CLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--expect-head", required=True)
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    if (out / "results.json").exists():
        raise SystemExit(f"{out / 'results.json'} exists; the read runs once")
    out.mkdir(parents=True, exist_ok=True)
    panel = build_french_panel()
    members = members_in_order(CLS, panel.features.shape[2])
    rec = {"registration": REGISTRATION, "git_head": a.expect_head,
           "platform": f"{platform.system()} {platform.machine()}", "x_sha256": X_SHA256,
           "lib_lightgbm_sha256": _sha256(lib_path()), "wheel_sha256": WHEEL_SHA256,
           "pinned_blobs": PINNED_BLOBS}
    rec.update(run_read(panel, members))
    (out / "results.json").write_text(json.dumps(rec, indent=1, default=float))
    print(f"results written to {out / 'results.json'}; no outcome printed. "
          f"Read with: python -m experiments.read_french_insample --dir {out}")
    return 0 if rec.get("repeat_bit_identical") else 1


if __name__ == "__main__":
    raise SystemExit(main())
