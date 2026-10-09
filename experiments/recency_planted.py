"""The recency-weighted certificate on planted panels (`prereg/recency-weight-planted.md`,
committed at 07fa892; amendments e48113e and a2fc19f). Box only for the run, on the author's typed go;
the laptop runs the smoke (cost only).

Arms (seed blocks): N20 702000-702999, N40 703000-703999, C20 704000-704399,
D20 704400-704799, E20 704800-705199, NV40 706000-706999, NA40 707000-707999; smoke and dry
705900-705909.

Steps:
  1. `--build-pool` (once): the ETF in-sample pool (3,019 rows) at zero cost, its residual
     returns; every class member's gross stream on each pool row, demeaned over the pool
     (82,240 x 3,019, a memory-mapped file); the 40 base columns, demeaned; a manifest with
     their hashes.
  2. per panel: the long panel's pool rows (a stationary bootstrap of the pool, block 7, to
     20 or 40 years); the declared stream (the planted member's pool-demeaned stream, plus
     the arm's drift); the base columns; the arm's shift (NV40, NA40) on every stream;
     block length by the class rule on the whole window, and the Politis-White median on
     the last n_eff rows; then the arm's tests (section 3 of the plan), the stream tests
     on one shared index set, the class tests on another.
Nothing about any rate is printed; the reader is `experiments/read_recency_planted.py`.

    python -m experiments.recency_planted --build-pool
    python -m experiments.recency_planted --smoke --out runs/recency_planted_smoke/<date> --workers 8
    python -m experiments.recency_planted --out runs/recency_planted/<date> --workers 180 --expect-head <commit>
    python -m experiments.recency_planted --dry --out runs/recency_planted_dry/<date> --workers 4
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

PLAN = "07fa8921463f6812dffdf8a1df47ef9c8423c731"
PLAN_AMENDMENT = "e48113e9abe539711527285d7fe13195ad7596c8"
PLAN_AMENDMENT2 = "a2fc19f673f3b67344643ae55decc3812c75d127"
H = 1260
B = 5000
PPY = 252.0
ROW_BLOCK = 7
YEARS = {"N20": 20, "N40": 40, "C20": 20, "D20": 20, "E20": 20, "NV40": 40, "NA40": 40}
SEEDS = {"N20": range(702000, 703000), "N40": range(703000, 704000), "C20": range(704000, 704400),
         "D20": range(704400, 704800), "E20": range(704800, 705200), "NV40": range(706000, 707000),
         "NA40": range(707000, 708000)}
SMOKE = range(705900, 705910)
PROFILE = {"N20": ("null", 0.0), "N40": ("null", 0.0), "C20": ("constant", 0.5), "D20": ("decaying", 0.5),
           "E20": ("emerging", 1.0), "NV40": ("null", 0.0), "NA40": ("null", 0.0)}
NULL_CLASS = ("N20", "N40")
SUPERSEDED = ("N20", "N40")
NA_COEF = (0.3, 0.3)
POOL_DIR = Path(__file__).resolve().parent.parent / "data" / "planted_cache" / "recency_pool"


# -- the pool --------------------------------------------------------------------------------

def pool_panel():
    import dataclasses
    from environments import planted_panel as pp
    base = pp.load_base()
    p = base.in_sample
    z = np.zeros_like(np.asarray(p.cost_rate, float))
    return base, dataclasses.replace(p, returns=base.E_is, cost_rate=z, borrow_rate=np.zeros_like(z))


def build_pool(out: Path | None = None) -> dict:
    out = POOL_DIR if out is None else out
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise SystemExit(f"{out / 'manifest.json'} exists; the pool is built once")
    base, panel = pool_panel()
    members = base.members
    cache = pf.build(panel, members, name="recency-pool-gross")
    F = pf.feature_returns(panel)
    T, N = panel.features.shape[0], len(members)
    G = np.lib.format.open_memmap(out / "G.npy", mode="w+", dtype=np.float64, shape=(N, T))
    sd = np.empty(N)
    for s0 in range(0, N, CHUNK):
        X = pf.streams(cache, F, s0, min(s0 + CHUNK, N))
        X = X - X.mean(axis=1, keepdims=True)
        G[s0:s0 + len(X)] = X
        sd[s0:s0 + len(X)] = X.std(axis=1, ddof=1)
    G.flush()
    del G
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    np.save(out / "BC.npy", bc - bc.mean(axis=0))
    np.save(out / "sd.npy", sd)
    sha = {f: hashlib.sha256((out / f).read_bytes()).hexdigest() for f in ("G.npy", "BC.npy", "sd.npy")}
    man = {"T_pool": T, "N": N, "sha256": sha, "built_on": f"{platform.system()} {platform.machine()}"}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    return man


def load_pool(d: Path | None = None):
    d = POOL_DIR if d is None else d
    G = np.load(d / "G.npy", mmap_mode="r")
    return G, np.load(d / "BC.npy"), np.load(d / "sd.npy")


# -- one panel -------------------------------------------------------------------------------

def pool_rows(T: int, n_pool: int, L: int, rng: np.random.Generator) -> np.ndarray:
    """T indices into a pool of n_pool rows: geometric blocks (mean length L), circular."""
    idx = np.empty(T, dtype=np.int64)
    pos = 0
    while pos < T:
        start = int(rng.integers(n_pool))
        n = min(int(rng.geometric(1.0 / L)), T - pos)
        idx[pos:pos + n] = (start + np.arange(n)) % n_pool
        pos += n
    return idx


def profile(kind: str, T: int) -> np.ndarray:
    t = np.arange(T, dtype=float)
    half = T // 2
    ramp = (t - half) / (T - 1 - half)
    return {"null": np.zeros(T), "constant": np.ones(T),
            "decaying": np.where(t < half, 1.0, 1.0 - ramp),
            "emerging": np.where(t < half, 0.0, ramp)}[kind]


def shift(arm: str, Z: np.ndarray) -> np.ndarray:
    """NV40: x2 on the oldest 75% of rows. NA40: on the newest 25%, (x_t + 0.3 x_{t-1} +
    0.3 x_{t-2}) / sqrt(1.18). Rows along axis 0; applied to every column."""
    Z = np.array(Z, dtype=float, copy=True)
    T = Z.shape[0]
    cut = int(round(0.75 * T))
    if arm == "NV40":
        Z[:cut] *= 2.0
    elif arm == "NA40":
        a1, a2 = NA_COEF
        Y = Z.copy()
        Y[cut:] = (Z[cut:] + a1 * Z[cut - 1:T - 1] + a2 * Z[cut - 2:T - 2]) / np.sqrt(1 + a1 * a1 + a2 * a2)
        Z = Y
    return Z


def _int(child) -> int:
    return int(child.generate_state(1, dtype=np.uint32)[0])


def class_tests(G, i: np.ndarray, L: int, seed: int, Bn: int, chunk: int = 512) -> dict:
    """Weighted class maxima under both centrings, aggregated to pool rows."""
    from estimator import recency as Rc
    from estimator.bootstrap import stationary_bootstrap_indices
    T, n_pool = len(i), G.shape[1]
    w = Rc.weights(T, H)
    V1, V2 = w.sum(), (w * w).sum()
    a = np.bincount(i, weights=w, minlength=n_pool)
    cnt = np.bincount(i, minlength=n_pool).astype(float)
    rng = np.random.default_rng(seed)
    A = np.empty((n_pool, Bn))
    for b in range(Bn):
        A[:, b] = np.bincount(i[stationary_bootstrap_indices(T, L, rng)], weights=w, minlength=n_pool)
    ann = np.sqrt(PPY)
    S_obs = -np.inf
    M = {"unweighted": np.full(Bn, -np.inf), "weighted_superseded": np.full(Bn, -np.inf)}
    den = V1 - V2 / V1
    for s0 in range(0, G.shape[0], chunk):
        X = np.asarray(G[s0:s0 + chunk])
        X2 = X * X
        mw = (X @ a) / V1
        vw = ((X2 @ a) - V1 * mw * mw) / den
        S = np.where(vw > 0, mw / np.sqrt(np.where(vw > 0, vw, 1.0)), 0.0) * ann
        S_obs = max(S_obs, float(S.max()))
        P1, P2 = X @ A, X2 @ A
        for cen, c in (("unweighted", (X @ cnt) / T), ("weighted_superseded", mw)):
            c = c[:, None]
            mean = (P1 - c * V1) / V1
            var = ((P2 - 2 * c * P1 + c * c * V1) - V1 * mean * mean) / den
            rep = np.where(var > 0, mean / np.sqrt(np.where(var > 0, var, 1.0)), 0.0) * ann
            M[cen] = np.maximum(M[cen], rep.max(axis=0))
    return {cen: {"S": S_obs, "p": (1 + int(np.sum(m >= S_obs))) / (Bn + 1)} for cen, m in M.items()}


def one(task, Bn: int = B, smoke: bool = False) -> dict:
    from environments import planted_panel as pp
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    arm, seed = task
    t0 = time.time()
    G, BC, sd = load_pool()
    n_pool = G.shape[1]
    T = YEARS[arm] * 252
    ch = np.random.SeedSequence(int(seed)).spawn(4)
    i = pool_rows(T, n_pool, ROW_BLOCK, np.random.default_rng(ch[0]))
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    members = members_in_order(CLS, BC.shape[1])
    m_star = pp.planted_member(seed, members)
    j = members.index(m_star)
    kind, beta = PROFILE[arm]
    x = np.asarray(G[j], float)[i] + beta * profile(kind, T) * sd[j] / np.sqrt(PPY)
    bc = BC[i]
    if arm in ("NV40", "NA40"):
        x = shift(arm, x[:, None])[:, 0]
        bc = shift(arm, bc)
    w = Rc.weights(T, H)
    n_eff = int(round(w.sum() ** 2 / (w * w).sum()))
    L = int(select_block_length(bc - bc.mean(axis=0)))
    tail = bc[-n_eff:]
    L_tail = int(select_block_length(tail - tail.mean(axis=0)))
    t_setup = time.time() - t0
    rec = {"arm": arm, "seed": int(seed), "T": T, "n_eff_rows": n_eff, "member_index": j,
           "block_length": L, "block_length_last_neff": L_tail, "seconds": {"setup": t_setup}}
    s_seed, c_seed = _int(ch[2]), _int(ch[3])
    tests = {"unweighted": dict(h=None), "weighted": dict(h=H)}
    if arm in SUPERSEDED:
        tests["weighted_superseded"] = dict(h=H, centring="weighted_superseded")
    out = {}
    for name, kw in tests.items():
        t1 = time.time()
        r = Rc.stream_test(x, L, PPY, Bn, s_seed, **kw)
        rec["seconds"][f"stream_{name}"] = time.time() - t1
        if not smoke:
            out[name] = {"S": r["S"], "p": r["p"], "L90": r["confidence"]["L"]["0.90"]}
    if not smoke:
        rec["stream"] = out
    if arm in NULL_CLASS:
        t1 = time.time()
        cl = class_tests(G, i, L, c_seed, Bn)
        rec["seconds"]["class_both_centrings"] = time.time() - t1
        if not smoke:
            rec["class"] = cl
    rec["seconds"]["total"] = time.time() - t0
    if smoke:
        rec = {k: rec[k] for k in ("arm", "seed", "T", "seconds")}
    return rec


def tasks() -> list[tuple]:
    return [(arm, s) for arm in SEEDS for s in SEEDS[arm]]


def smoke_tasks() -> list[tuple]:
    """Ten smoke seeds over the arms' shapes: each arm at least once."""
    arms = list(SEEDS)
    return [(arms[k % len(arms)], s) for k, s in enumerate(SMOKE)]


def refusals(expect_head: str) -> list[str]:
    g = lambda *a: subprocess.run(["git", *a], capture_output=True, text=True)
    bad = []
    if f"{platform.system()} {platform.machine()}" != "Linux x86_64":
        bad.append("not Linux x86_64 (the box)")
    if g("rev-parse", "HEAD").stdout.strip() != expect_head:
        bad.append("HEAD is not --expect-head")
    if g("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    for c in (PLAN, PLAN_AMENDMENT, PLAN_AMENDMENT2):
        if g("merge-base", "--is-ancestor", c, "HEAD").returncode != 0:
            bad.append(f"the plan commit {c} is not an ancestor of HEAD")
    man = POOL_DIR / "manifest.json"
    if not man.exists():
        bad.append("the pool is not built (--build-pool)")
    else:
        m = json.loads(man.read_text())
        for f, h in m["sha256"].items():
            if hashlib.sha256((POOL_DIR / f).read_bytes()).hexdigest() != h:
                bad.append(f"pool file {f} does not match its manifest")
    return bad


def _one_smoke(t):
    return one(t, smoke=True)


def _one_dry(t):
    return one(t, Bn=200)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-pool", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="cost only: seconds recorded, no rule quantity")
    ap.add_argument("--dry", action="store_true", help="the smoke seeds with B 200, all fields; never read")
    ap.add_argument("--out")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--expect-head")
    a = ap.parse_args(argv)
    if a.build_pool:
        print(json.dumps(build_pool(), indent=1))
        return 0
    out = Path(a.out)
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out / 'results.jsonl'} exists; not overwriting")
    if not (a.smoke or a.dry):
        bad = refusals(a.expect_head or "")
        if bad:
            raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out.mkdir(parents=True, exist_ok=True)
    todo = smoke_tasks() if (a.smoke or a.dry) else tasks()
    fn = _one_smoke if a.smoke else (_one_dry if a.dry else one)
    (out / "provenance.json").write_text(json.dumps(
        {"git_head": a.expect_head, "plan": PLAN, "plan_amendment": PLAN_AMENDMENT, "smoke": a.smoke, "dry_run": a.dry,
         "platform": f"{platform.system()} {platform.machine()}", "tasks": len(todo), "workers": a.workers,
         "H": H, "B": 200 if a.dry else B, "pool_manifest": json.loads((POOL_DIR / "manifest.json").read_text())},
        indent=1))
    t0 = time.time()
    done = 0
    with open(out / "results.jsonl.partial", "w") as fh, ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(fn, t) for t in todo]
        for f in as_completed(futs):
            fh.write(json.dumps(f.result(), default=float) + "\n")
            fh.flush()
            done += 1
            print(f"{done}/{len(todo)} tasks, {time.time() - t0:.0f} s", flush=True)
    os.replace(out / "results.jsonl.partial", out / "results.jsonl")
    print(f"wall {time.time() - t0:.0f} s; {len(todo)} tasks; no rate printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
