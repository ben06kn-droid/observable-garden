"""The scripted twin cell (`prereg/twin-calibration.md`, the planted-panel amendment).

Per panel seed, at level 0 and one planted level (`environments/planted_panel.py`):
the real panel and **K = 19 twins under each of `joint_time_permutation` and
`block_permutation`** (`quixote/twins.py`) — 39 return matrices per level — each
priced by the **class tier** (the certifying tier by the 2026-09-30 tier rule), and each
of the six registered scripted searchers, class-capped, run on every matrix. The twin
p-value is the registered rank,

    p = (1 + #{twins k with p_k <= p_real}) / (K + 1),

with ties counted against the real run, as registered.

**A twin here permutes the rows of the panel's return matrix against X, which stays in
calendar order.** Positions are a function of X alone, so every member's cost and
borrow path is identical in the real panel and in all its twins, and one position loop
per chunk serves all 39 matrices (`streams_multi`). Each matrix is priced by the same
function: its own null block length from its own depth-1 (+) streams, its own B
replicates from `default_rng(panel seed)` — so the procedure applied to the real panel
and to a twin is one procedure, which exchangeability needs.

    python -m experiments.planted_twins --smoke 2 --workers 2      # cost only
    python -m experiments.planted_twins --draws N --workers 31     # the registered run

`--smoke` takes the dedicated block 985000-985999 and writes cost only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, canonical
from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
from experiments.planted_edge import _searchers, _sharpe_rows, peak_rss_mb
from experiments._resume import load_done  # noqa: F401  (re-exported; tested here)
from quixote.twins import K_FOR_ALPHA, twin_p_value, twins

SEED0 = 650_000
SEED0_REPLICATION = 660_000      # registered: one shot, for the first T1 failure
SEED0_SMOKE = 985_000
K = K_FOR_ALPHA[0.05]            # 19, registered
B_DEFAULT = 1_000
CONSTRUCTIONS = ("joint_time_permutation", "block_permutation")
PRICE_PER_HOUR = 9.85 / 6


def streams_multi(panel, supports, R_stack: np.ndarray) -> np.ndarray:
    """(J, n, T) net streams of `supports` against J return matrices at once.
    `R_stack` is (T, M, J). Positions, costs and borrow are computed once."""
    T = panel.features.shape[0]
    J = R_stack.shape[2]
    n = len(supports)
    out = np.empty((J, n, T))

    def step(t, new, prev):
        k = ((np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
             + (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        out[:, :, t] = (new @ R_stack[t]).T - k

    pp._positions_loop(panel, supports, step)
    return out


def power_state() -> str:
    """Power source and Low Power Mode, for a smoke's cost to be read against
    (`pmset` on macOS; elsewhere not applicable). A throttled machine measures a
    different cost, which is how a 2026-10-02 smoke was confounded."""
    if sys.platform != "darwin":
        return "n/a (not macOS)"
    import subprocess
    try:
        g = subprocess.run(["pmset", "-g"], capture_output=True, text=True).stdout
        b = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    except OSError:
        return "unknown (pmset unavailable)"
    lpm = next((ln.split()[-1] for ln in g.splitlines() if "lowpowermode" in ln), "?")
    src = "mains" if "AC Power" in b else ("battery" if "Battery Power" in b else "?")
    return f"source {src}, Low Power Mode {'ON' if lpm == '1' else 'off' if lpm == '0' else lpm}"


def _count_matrix(T, L, B, seed):
    rng = np.random.default_rng(seed)
    C = np.empty((T, B))
    for b in range(B):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    return C


def run_level(base, seed: int, beta: float, B: int) -> dict:
    t = {}
    t0 = time.time()
    draw = pp.make_draw(base, seed, beta)
    panel = draw.in_sample
    T, M, Kf = panel.features.shape
    ann = float(np.sqrt(panel.periods_per_year))
    # children [0..2] are the panel's own (pp.children); [3] and [4] are the twins'
    ch = np.random.SeedSequence(int(seed)).spawn(5)
    R0 = panel.returns
    mats = [R0]
    for c, cs in zip(CONSTRUCTIONS, (ch[3], ch[4])):
        mats += twins(R0, K, seed=cs, construction=c)
    J = len(mats)                                      # 1 + 2K = 39
    R_stack = np.stack(mats, axis=2)                   # (T, M, J)
    members = base.members
    N = len(members)
    index = {canonical(m): i for i, m in enumerate(members)}
    t["generate"] = time.time() - t0

    t0 = time.time()
    obs = np.empty((J, N))
    M_b = np.full((J, B), -np.inf)
    Cs, Ls, lag1 = None, None, None
    singles = [index[canonical(((k, 1.0),))] for k in range(Kf)]
    for s in range(0, N, CHUNK):
        X = streams_multi(panel, members[s:s + CHUNK], R_stack)       # (J, n, T)
        if Cs is None:
            # each matrix's own null block length, from its own depth-1 (+) streams;
            # the singles all sit in the first chunk
            assert max(singles) < CHUNK
            Ls = []
            for j in range(J):
                bc = X[j][singles].T
                Ls.append(int(select_block_length(bc - bc.mean(axis=0))))
            Cs = [_count_matrix(T, L, B, seed) for L in Ls]
            x0 = X[0] - X[0].mean(axis=1, keepdims=True)
            num = (x0[:, 1:] * x0[:, :-1]).sum(axis=1)
            den = (x0 * x0).sum(axis=1)
            lag1 = float(np.median(np.where(den > 0, num / np.where(den > 0, den, 1), 0)))
        for j in range(J):
            Xj = X[j]
            obs[j, s:s + len(Xj)] = _sharpe_rows(Xj, ann)
            X0 = Xj - Xj.mean(axis=1, keepdims=True)
            mean = (X0 @ Cs[j]) / T
            var = ((X0 * X0) @ Cs[j] - T * mean * mean) / (T - 1)
            pos = var > 0
            null = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
            M_b[j] = np.maximum(M_b[j], null.max(axis=0))
    t["class_pass"] = time.time() - t0

    t0 = time.time()
    single_ix = singles
    out = []
    for srch in _searchers(seed, T, panel.periods_per_year):
        p, score, sub = np.empty(J), np.empty(J), None
        for j in range(J):
            o = obs[j]
            tr = srch._search(Kf, lambda k, o=o: float(o[single_ix[k]]),
                              lambda sup, o=o: float(o[index[canonical(sup)]]))
            score[j] = tr.score
            p[j] = (1 + int(np.sum(M_b[j] >= tr.score))) / (B + 1)
            if j == 0:
                sub = canonical(tuple(tr.support))
        rec = {"searcher": srch.name, "support": [list(q) for q in sub],
               "score_real": float(score[0]), "p_class_real": float(p[0]),
               "truth_in_sample": pp.truth(base, draw, sub)["in_sample"]}
        for c_i, c in enumerate(CONSTRUCTIONS):
            pk = p[1 + c_i * K: 1 + (c_i + 1) * K]
            rec[f"p_twin_{c}"] = twin_p_value(p[0], pk)
            rec[f"ties_{c}"] = int(np.sum(pk == p[0]))
        out.append(rec)
    t["searchers"] = time.time() - t0
    return {"seed": seed, "beta": beta, "c": draw.c, "block_lengths": Ls,
            "median_lag1_autocorr_real": lag1, "searchers": out, "secs": t}


# -- the score-rank cell: runs first --------------------------------------------
#
# The statistic is the searcher's submitted realized net Sharpe, ranked among its K
# twins in the registered form with ties against the real run. No class pass and no
# bootstrap: a searcher scores only the supports it visits, so streams are computed
# on demand, a prefix batch at a time, for all 39 matrices at once, and shared by every
# search on the panel. This tests the TWIN CONSTRUCTIONS; the registered p-rank
# statistic (`run_level` above) is a later cell.

SCORE_LEVELS = (0.0, 1.0)            # fixed, independent of 7.5's curve


class MultiCache:
    """Sharpe of a support on every return matrix, computed per depth-(d-1) prefix
    batch (every signed extension at once), through `streams_multi`."""

    def __init__(self, panel, R_stack, ann):
        self.panel, self.R, self.ann = panel, R_stack, ann
        self.K = panel.features.shape[2]
        self.sr: dict = {}
        self.batches = 0

    def get(self, support) -> np.ndarray:
        key = canonical(support)
        if key not in self.sr:
            prefix = key[:-1]
            held = {k for k, _ in prefix}
            batch = [prefix + ((j, s),) for j in range(self.K) if j not in held
                     for s in (1.0, -1.0)]
            X = streams_multi(self.panel, batch, self.R)              # (J, n, T)
            S = np.stack([_sharpe_rows(X[j], self.ann) for j in range(X.shape[0])])
            for i, sup in enumerate(batch):
                self.sr[canonical(sup)] = S[:, i]
            self.batches += 1
        return self.sr[key]


def median_lag1_signed_singles(panel) -> float:
    """The score-rank cell's autocorrelation sign: the median, over the real panel's 80
    signed depth-1 members (every feature at +1 and at -1), of each net stream's
    demeaned lag-1 autocorrelation, sum_{t>=2} x_t x_{t-1} / sum_t x_t^2.

    Deliberately NOT the p-rank cell's figure (`run_level`), which is the median over the
    first class-pass chunk's 512 members -- the depth-1 members and the first depth-2
    ones in enumeration order. The two answer the same question from different member
    sets and are not interchangeable."""
    from environments.class_table import streams_for
    K = panel.features.shape[2]
    X = streams_for(panel, [((k, s),) for k in range(K) for s in (1.0, -1.0)])
    x0 = X - X.mean(axis=1, keepdims=True)
    num = (x0[:, 1:] * x0[:, :-1]).sum(axis=1)
    den = (x0 * x0).sum(axis=1)
    return float(np.median(np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0)))


def score_rank_p(real: float, twin_scores) -> float:
    """`(1 + #{twins scoring >= the real run}) / (K + 1)`: the registered rank, with a
    higher score the more extreme and ties counted against the real run."""
    twin_scores = list(twin_scores)
    return (1 + sum(1 for x in twin_scores if x >= real)) / (len(twin_scores) + 1)


def run_level_score(base, seed: int, beta: float) -> dict:
    t = {}
    t0 = time.time()
    draw = pp.make_draw(base, seed, beta)
    panel = draw.in_sample
    T, M, Kf = panel.features.shape
    ann = float(np.sqrt(panel.periods_per_year))
    ch = np.random.SeedSequence(int(seed)).spawn(5)
    R0 = panel.returns
    mats = [R0]
    for c, cs in zip(CONSTRUCTIONS, (ch[3], ch[4])):
        mats += twins(R0, K, seed=cs, construction=c)
    J = len(mats)
    cache = MultiCache(panel, np.stack(mats, axis=2), ann)
    t["generate"] = time.time() - t0

    t0 = time.time()
    out = []
    for srch in _searchers(seed, T, panel.periods_per_year):
        score, sub = np.empty(J), None
        for j in range(J):
            tr = srch._search(Kf, lambda k, j=j: float(cache.get(((k, 1.0),))[j]),
                              lambda sup, j=j: float(cache.get(sup)[j]))
            score[j] = tr.score
            if j == 0:
                sub = canonical(tuple(tr.support)) if tr.support else None
        # EMPTY-SUPPORT GUARD: a real run that submits nothing has no specification to
        # price and no population Sharpe (a zero weight path has zero variance). It is
        # recorded with support and truth None and its score as found (-inf), so the
        # registered rank places it at p = 1: a non-rejection, never a certificate.
        rec = {"searcher": srch.name,
               "support": [list(q) for q in sub] if sub else None,
               "score_real": float(score[0]),
               "truth_in_sample": pp.truth(base, draw, sub)["in_sample"] if sub else None}
        for c_i, c in enumerate(CONSTRUCTIONS):
            sk = score[1 + c_i * K: 1 + (c_i + 1) * K]
            rec[f"p_score_{c}"] = score_rank_p(score[0], sk)
            rec[f"ties_{c}"] = int(np.sum(sk == score[0]))
        out.append(rec)
    t["searches"] = time.time() - t0
    return {"seed": seed, "beta": beta, "c": draw.c, "prefix_batches": cache.batches,
            "median_lag1_autocorr_signed_singles": median_lag1_signed_singles(panel),
            "searchers": out, "secs": t}


def run_seed(payload) -> dict:
    seed, levels, B, cell = payload
    base = pp.load_base()
    t0, c0 = time.time(), time.process_time()
    fn = (lambda b: run_level_score(base, seed, b)) if cell == "score" else \
        (lambda b: run_level(base, seed, b, B))
    out = {"seed": seed, "cell": cell, "levels": [fn(b) for b in levels]}
    out["secs"] = time.time() - t0
    # this seed's own CPU seconds: unaffected by sleep, which wall time is not
    out["cpu_secs"] = time.process_time() - c0
    from experiments.code_state import platform_info
    out["platform"] = platform_info()
    out["peak_rss_mb"] = peak_rss_mb()
    return out


def cost_only(rec: dict) -> dict:
    return {"seed": rec["seed"], "cell": rec["cell"], "secs": rec["secs"],
            "cpu_secs": rec.get("cpu_secs"), "peak_rss_mb": rec["peak_rss_mb"],
            "stage_secs": [lv["secs"] for lv in rec["levels"]],
            "prefix_batches": [lv.get("prefix_batches") for lv in rec["levels"]],
            "platform": rec.get("platform")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=0)
    ap.add_argument("--planted", type=float, default=None,
                    help="the planted level: stage 1's nearest-the-bar, once fixed")
    ap.add_argument("--B", type=int, default=B_DEFAULT)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--out", default="runs/planted_twins")
    ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--replication", action="store_true",
                    help="the registered one-shot replication block 660000-660999, "
                         "for the first T1 failure only; writes to OUT + _replication")
    ap.add_argument("--cell", choices=("score", "prank"), default="score",
                    help="score: the score-rank cell, runs first, levels 0 and 1.0 fixed; "
                         "prank: the registered p-rank cell, a later cell")
    a = ap.parse_args(argv)
    smoke = a.smoke > 0
    if a.cell == "score":
        if a.planted is not None:
            raise SystemExit("the score-rank cell's levels are fixed at 0 and 1.0")
        levels = list(SCORE_LEVELS)
    elif smoke:
        levels = [0.0, 1.0 if a.planted is None else a.planted]   # cost is level-free
    else:
        if a.planted is None:
            raise SystemExit("--planted is required for the p-rank cell: stage 1's "
                             "nearest-the-bar, fixed by dated commit before it is live")
        levels = [0.0, a.planted]
    if smoke and a.replication:
        raise SystemExit("--replication and --smoke are exclusive")
    seed0 = SEED0_SMOKE if smoke else (SEED0_REPLICATION if a.replication else SEED0)
    n = a.smoke if smoke else a.draws
    suffix = ("" if a.cell == "prank" else "_score") + ("_replication" if a.replication else "")
    out = Path(f"runs/_smoke/planted_twins{suffix}" if smoke else a.out + suffix)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "draws.jsonl"
    done = load_done(path)
    todo = [(seed0 + i, levels, a.B, a.cell) for i in range(n) if seed0 + i not in done]
    print(f"{'SMOKE (cost only)' if smoke else 'REGISTERED'}: seeds {seed0}-{seed0 + n - 1}, "
          f"levels {levels}, K {K} x {len(CONSTRUCTIONS)}, "
          f"{'no bootstrap' if a.cell == 'score' else f'B {a.B}'}, {len(todo)} to run",
          flush=True)
    power_start = power_state()
    print(f"  power at start: {power_start}", flush=True)
    t0 = time.time()
    from concurrent.futures import ProcessPoolExecutor, as_completed
    with ProcessPoolExecutor(max_workers=a.workers) as pool, open(path, "a") as fh:
        for fut in as_completed([pool.submit(run_seed, p) for p in todo]):
            rec = fut.result()
            fh.write(json.dumps(cost_only(rec) if smoke else rec, default=str) + "\n")
            fh.flush()
            print(f"  seed {rec['seed']} done in {rec['secs']:.0f}s, "
                  f"peak RSS {rec['peak_rss_mb']:.0f} MB", flush=True)
    wall = time.time() - t0
    if smoke:
        recs = [json.loads(l) for l in path.read_text().splitlines() if l]
        per = np.array([r["secs"] for r in recs])
        stages = {}
        for r in recs:
            for lv in r["stage_secs"]:
                for k, v in lv.items():
                    stages.setdefault(k, []).append(v)
        L = [f"scripted twin cell ({a.cell}) — SMOKE, cost only (no rule quantity is "
             "written or shown)",
             "=" * 78,
             f"  panels {len(recs)} (seeds {seed0}-{seed0 + n - 1}), 2 levels, "
             f"{1 + 2 * K} return matrices per level, "
             f"{'no bootstrap' if a.cell == 'score' else f'B {a.B}'}, workers {a.workers}, "
             f"wall {wall:.0f}s",
             f"  per seed (both levels): wall mean {per.mean():.0f}s median "
             f"{np.median(per):.0f}s max {per.max():.0f}s; CPU mean "
             f"{np.mean([r['cpu_secs'] for r in recs]):.0f}s median "
             f"{np.median([r['cpu_secs'] for r in recs]):.0f}s max "
             f"{max(r['cpu_secs'] for r in recs):.0f}s",
             f"  wall/CPU ratio max {max(r['secs'] / r['cpu_secs'] for r in recs):.2f} "
             "(well above 1 means the machine slept or was contended during that seed)",
             "  per level, by stage (median s): " + ", ".join(
                 f"{k} {np.median(v):.1f}" for k, v in stages.items()),
             f"  peak RSS per worker: max {max(r['peak_rss_mb'] for r in recs):.0f} MB",
             f"  throughput: {len(recs) / wall * 3600:.1f} panels per hour wall "
             f"({a.workers} workers, this machine)",
             f"  power: at start {power_start}; at end {power_state()}"]
        text = "\n".join(L)
        print("\n" + text)
        (out / "smoke_cost.txt").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
