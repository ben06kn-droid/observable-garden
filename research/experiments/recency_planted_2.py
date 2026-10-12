"""The recency-weighted certificate on planted panels, ROUND 2 (`prereg/recency-weight-planted-2.md`,
46b589e; amendments 86277fc, 8a23368). Box only for the run, on the author's typed go; the laptop runs
the smoke (cost only).

Arms (seed blocks): N40 709000-709999, NV40 710000-710999, NA40 711000-711999 and 715000-715999 (n = 2,000),
NAREV40 712000-712999, E20 713000-713399, D20 713400-713799, C20 713800-714199; smoke and dry
714900-714909.

Per panel, as round 1 (`experiments.recency_planted`: the same pool, row resampling, drifts
and shifts; NAREV40 adds the scaled dependence to the OLDEST 75% of rows), then:
- stream, on one shared seed: W2; R15; the round-1 fixed centring (beside); the unweighted
  statistic on the whole window (beside);
- class under W2 on N40 and NA40: the same W2 index sets for every member, each centred by
  its q-weighted mean, aggregated to pool rows.
Nothing about any rate is printed; the reader is `experiments/read_recency_planted_2.py`.

    python -m experiments.recency_planted --build-pool            (round 1's pool, once per machine)
    python -m experiments.recency_planted_2 --smoke --out runs/recency_planted_2_smoke/<date> --workers 4
    python -m experiments.recency_planted_2 --dry --out runs/recency_planted_2_dry/<date> --workers 4
    python -m experiments.recency_planted_2 --out runs/recency_planted_2/<date> --workers 180 --expect-head <commit>
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

from experiments import recency_planted as P1

PLAN = "46b589e314ae04befd94fa60da01165d8217bdc1"
PLAN_AMENDMENT = "86277fc827f1e222280abadadd0532ebbc0f9496"
PLAN_AMENDMENT2 = "8a23368a6701cafbac3a5c37f2a717b4aeb74142"      # NA40 at n = 2,000; the adjusted rule
H, B, PPY = P1.H, P1.B, P1.PPY
YEARS = {"N40": 40, "NV40": 40, "NA40": 40, "NAREV40": 40, "E20": 20, "D20": 20, "C20": 20}
SEEDS = {"N40": range(709000, 710000), "NV40": range(710000, 711000), "NA40": list(range(711000, 712000)) + list(range(715000, 716000)),
         "NAREV40": range(712000, 713000), "E20": range(713000, 713400), "D20": range(713400, 713800),
         "C20": range(713800, 714200)}
SMOKE = range(714900, 714910)
PROFILE = {"N40": ("null", 0.0), "NV40": ("null", 0.0), "NA40": ("null", 0.0), "NAREV40": ("null", 0.0),
           "E20": ("emerging", 1.0), "D20": ("decaying", 0.5), "C20": ("constant", 0.5)}
CLASS_ARMS = ("N40", "NA40")


def shift(arm: str, Z: np.ndarray) -> np.ndarray:
    """Round 1's NV40 and NA40; NAREV40: the scaled dependence on the OLDEST 75% of rows."""
    if arm in ("NV40", "NA40"):
        return P1.shift(arm, Z)
    Z = np.array(Z, dtype=float, copy=True)
    if arm == "NAREV40":
        T = Z.shape[0]
        cut = int(round(0.75 * T))
        a1, a2 = P1.NA_COEF
        Y = Z.copy()
        Y[2:cut] = (Z[2:cut] + a1 * Z[1:cut - 1] + a2 * Z[0:cut - 2]) / np.sqrt(1 + a1 * a1 + a2 * a2)
        Z = Y
    return Z


def class_w2(G, i: np.ndarray, L: int, seed: int, Bn: int, chunk: int = 512) -> dict:
    """The class maximum under W2, aggregated to pool rows: the same W2 index sets for every
    member, each member centred by its q-weighted mean."""
    from estimator import recency as Rc
    T, n_pool = len(i), G.shape[1]
    w = Rc.weights(T, H)
    V1, V2 = w.sum(), (w * w).sum()
    pi, q = Rc.w2_pi_q(w, L)
    a = np.bincount(i, weights=w, minlength=n_pool)
    qp = np.bincount(i, weights=q, minlength=n_pool)
    rng = np.random.default_rng(seed)
    A = np.empty((n_pool, Bn))
    for b in range(Bn):
        A[:, b] = np.bincount(i[Rc.w2_indices(T, L, pi, q, rng)], weights=w, minlength=n_pool)
    ann, den = np.sqrt(PPY), V1 - V2 / V1
    S_obs, M = -np.inf, np.full(Bn, -np.inf)
    for s0 in range(0, G.shape[0], chunk):
        X = np.asarray(G[s0:s0 + chunk])
        X2 = X * X
        mw = (X @ a) / V1
        vw = ((X2 @ a) - V1 * mw * mw) / den
        S_obs = max(S_obs, float((np.where(vw > 0, mw / np.sqrt(np.where(vw > 0, vw, 1.0)), 0.0) * ann).max()))
        c = (X @ qp)[:, None]
        P1m, P2m = X @ A, X2 @ A
        mean = (P1m - c * V1) / V1
        var = ((P2m - 2 * c * P1m + c * c * V1) - V1 * mean * mean) / den
        M = np.maximum(M, (np.where(var > 0, mean / np.sqrt(np.where(var > 0, var, 1.0)), 0.0) * ann).max(axis=0))
    return {"S": S_obs, "p": (1 + int(np.sum(M >= S_obs))) / (Bn + 1)}


def one(task, Bn: int = B, smoke: bool = False) -> dict:
    from environments import planted_panel as pp
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from estimator import recency as Rc
    from estimator.bootstrap import select_block_length
    arm, seed = task
    t0 = time.time()
    G, BC, sd = P1.load_pool()
    n_pool = G.shape[1]
    T = YEARS[arm] * 252
    ch = np.random.SeedSequence(int(seed)).spawn(4)
    i = P1.pool_rows(T, n_pool, P1.ROW_BLOCK, np.random.default_rng(ch[0]))
    members = members_in_order(CLS, BC.shape[1])
    j = members.index(pp.planted_member(seed, members))
    kind, beta = PROFILE[arm]
    x = np.asarray(G[j], float)[i] + beta * P1.profile(kind, T) * sd[j] / np.sqrt(PPY)
    bc = BC[i]
    if arm in ("NV40", "NA40", "NAREV40"):
        x = shift(arm, x[:, None])[:, 0]
        bc = shift(arm, bc)
    w = Rc.weights(T, H)
    n_eff = int(round(w.sum() ** 2 / (w * w).sum()))
    L = int(select_block_length(bc - bc.mean(axis=0)))
    tail = bc[-n_eff:]
    L_tail = int(select_block_length(tail - tail.mean(axis=0)))
    rec = {"arm": arm, "seed": int(seed), "T": T, "n_eff_rows": n_eff, "member_index": j,
           "block_length": L, "block_length_last_neff": L_tail, "seconds": {"setup": time.time() - t0}}
    s_seed, c_seed = P1._int(ch[2]), P1._int(ch[3])
    runs = {"W2": lambda: Rc.stream_test_w2(x, L, PPY, Bn, s_seed, h=H),
            "R15": lambda: Rc.stream_test_r15(x, bc, PPY, Bn, s_seed),
            "fixed": lambda: Rc.stream_test(x, L, PPY, Bn, s_seed, h=H),
            "unweighted": lambda: Rc.stream_test(x, L, PPY, Bn, s_seed)}
    out = {}
    for name, fn in runs.items():
        t1 = time.time()
        r = fn()
        rec["seconds"][f"stream_{name}"] = time.time() - t1
        if not smoke:
            out[name] = {"S": r["S"], "p": r["p"], "L90": r["confidence"]["L"]["0.90"], "L": r["block_length"]}
    if not smoke:
        rec["stream"] = out
    if arm in CLASS_ARMS:
        t1 = time.time()
        cl = class_w2(G, i, L, c_seed, Bn)
        rec["seconds"]["class_W2"] = time.time() - t1
        if not smoke:
            rec["class"] = {"W2": cl}
    rec["seconds"]["total"] = time.time() - t0
    if smoke:
        rec = {k: rec[k] for k in ("arm", "seed", "T", "seconds")}
    return rec


def tasks() -> list[tuple]:
    return [(arm, s) for arm in SEEDS for s in SEEDS[arm]]


def smoke_tasks() -> list[tuple]:
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
    man = P1.POOL_DIR / "manifest.json"
    if not man.exists():
        bad.append("the pool is not built (python -m experiments.recency_planted --build-pool)")
    else:
        for f, h in json.loads(man.read_text())["sha256"].items():
            if hashlib.sha256((P1.POOL_DIR / f).read_bytes()).hexdigest() != h:
                bad.append(f"pool file {f} does not match its manifest")
    return bad


def _one_smoke(t):
    return one(t, smoke=True)


def _one_dry(t):
    return one(t, Bn=200)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="cost only: seconds recorded, no rule quantity")
    ap.add_argument("--dry", action="store_true", help="the smoke seeds with B 200, all fields; never read")
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--expect-head")
    a = ap.parse_args(argv)
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
        {"git_head": a.expect_head, "plan": PLAN, "plan_amendment": PLAN_AMENDMENT, "smoke": a.smoke,
         "dry_run": a.dry, "platform": f"{platform.system()} {platform.machine()}", "tasks": len(todo),
         "workers": a.workers, "H": H, "B": 200 if a.dry else B,
         "pool_manifest": json.loads((P1.POOL_DIR / "manifest.json").read_text())}, indent=1))
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
