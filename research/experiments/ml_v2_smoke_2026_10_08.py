"""Version 2's cost-only smoke (`prereg/ml-v2-exploratory-2026-10-08.md`, Part 4): level-0
planted ETF panels on the fresh block 696000-696999 (seeds 696000, 696001), laptop.

Per panel: every one of the 126 fit cells (information x horizon x neutrality x memory) is
fitted, and its seconds and grid-edge refits are recorded. On the first panel also:
- the leak test for every block: X, V and the groups on the real ETF row returns and
  volume behind the pinned inputs; F on a synthetic funding array (the ETF has none);
- the leak test for a sample of three views;
- a bit-for-bit repeat of two cells.

**Nothing about any outcome is printed or stored:** no Sharpe, p-value or certification.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_smoke_2026_10_08 --out runs/ml_v2_smoke/2026-10-08 --workers 4
"""
from __future__ import annotations

import argparse
import itertools
import json
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

SEEDS = (696000, 696001)
LEAK_ROWS = (1500, 2400)
LEAK_VIEWS = ((("P", "X", "V"), 5, "market", "always"), (("P",), 1, "group", "mkt_up"),
              (("X", "V"), 20, "market", "disp_low"))
REPEAT_CELLS = ((("P", "X", "V"), 5, "market", "expand"), (("V",), 20, "group", "roll252"))

_W: dict = {}


def inputs_for(seed: int):
    import environments.planted_panel as pp
    from environments import etf_v2_inputs as E
    from learn2 import learner as Ln
    if "base" not in _W:
        _W["base"] = pp.load_base()
        _W["v2"] = E.for_segment(_W["base"].in_sample)
    d = pp.make_draw(_W["base"], seed, 0.0)
    v2 = _W["v2"]
    return Ln.from_panel(d.in_sample, blocks={"X": v2["X"], "V": v2["V"]}, groups=v2["G"])


def fit_one(task):
    from learn2 import learner as Ln
    seed, cell = task
    inp = inputs_for(seed)
    t0 = time.time()
    f = Ln.fit_cell(inp, *cell)
    return {"seed": seed, "cell": [list(cell[0]), cell[1], cell[2], cell[3]], "seconds": time.time() - t0,
            "refits": len(f["diagnostics"]),
            "edge_refits": sum(1 for x in f["diagnostics"] if x["at_edge"]),
            "edges": [x["at_edge"] for x in f["diagnostics"]]}


def cells(available):
    from learn2 import learner as Ln
    from learn2 import views as Vw
    return [(i, h, n, m) for i in Vw.informations(available) for h in Vw.HORIZONS
            for n in Vw.NEUTRALITY for m in Ln.MEMORIES]


def main(argv=None) -> int:
    from environments import etf_v2_inputs as E
    from learn2 import blocks as Bk
    from learn2 import leak as Lk
    from learn2 import learner as Ln
    from learn2 import views as Vw
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    L, rec = [], {"seeds": SEEDS}

    def P(s=""):
        L.append(s)
        print(s, flush=True)

    P("ML v2 smoke, cost only: level-0 planted ETF panels (696000, 696001); no outcome printed")
    P(f"platform {platform.system()} {platform.machine()}; workers {a.workers}")
    P("=" * 88)
    available = inputs_for(SEEDS[0]).available
    cl = cells(available)
    P(f"available blocks {available}; {len(cl)} fit cells per panel")
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as ex:
        fits = list(ex.map(fit_one, [(s, c) for s in SEEDS for c in cl]))
    wall = time.time() - t0
    rec["fits"] = fits
    secs = np.array([f["seconds"] for f in fits])
    P(f"fits: {len(fits)} cells in {wall:.0f} s wall ({secs.sum():.0f} cell-seconds)")
    for key, name in ((lambda f: "P" in f["cell"][0], "with P"), (lambda f: "P" not in f["cell"][0], "without P")):
        s = np.array([f["seconds"] for f in fits if key(f)])
        P(f"   cells {name}: {len(s)}; seconds per cell median {np.median(s):.1f}, max {s.max():.1f}")
    for m in Ln.MEMORIES:
        s = np.array([f["seconds"] for f in fits if f["cell"][3] == m])
        P(f"   memory {m}: seconds per cell median {np.median(s):.1f}")
    for h in Vw.HORIZONS:
        s = np.array([f["seconds"] for f in fits if f["cell"][1] == h])
        P(f"   horizon {h}: seconds per cell median {np.median(s):.1f}")
    n_ref = sum(f["refits"] for f in fits)
    n_edge = sum(f["edge_refits"] for f in fits)
    by_block = {}
    for f in fits:
        for e in f["edges"]:
            for b in e:
                by_block[b] = by_block.get(b, 0) + 1
    P(f"   refits with a penalty at a grid edge: {n_edge} of {n_ref}; by block {by_block}")

    P("")
    P("LEAK TESTS (positions / block rows <= t bit-identical when everything after t is replaced)")
    from data.etf_loader import INSAMPLE_DIR, load_panel
    from environments.real_panel import declared_market
    pan = load_panel(INSAMPLE_DIR)
    tick = sorted(pan)
    common = sorted(set.intersection(*(set(pan[t][0]) for t in tick)))
    ix = {t: {d: i for i, d in enumerate(pan[t][0])} for t in tick}
    Px = np.array([[pan[t][1][ix[t][d]] for t in tick] for d in common])
    Vol = np.array([[pan[t][2][ix[t][d]] for t in tick] for d in common])
    r = np.nan_to_num(np.vstack([np.full((1, len(tick)), np.nan), Px[1:] / Px[:-1] - 1.0]))
    mkt = declared_market(tick, r)
    leak_rows = (2000, 3500)
    res = {"X": Lk.leak_block(Bk.build_X, (r, mkt), leak_rows),
           "V": Lk.leak_block(lambda v: Bk.build_V(v, Px, r), (Vol,), leak_rows),
           "groups": Lk.leak_block(Bk.build_groups, (r,), leak_rows),
           "F (synthetic funding)": Lk.leak_block(Bk.build_F, (1e-4 * np.random.default_rng(0).standard_normal((800, 12)),), (400, 600))}
    for k, v in res.items():
        ok = all(x["identical_up_to_t"] for x in v)
        P(f"   block {k:<22} {'PASS' if ok else 'FAIL'} (a later change visible: {any(x['changed_after_t'] for x in v)})")
    rec["leak_blocks"] = res
    inp = inputs_for(SEEDS[0])
    rec["leak_views"] = {}
    for v in LEAK_VIEWS:
        t1 = time.time()
        rv = Lk.leak_view(lambda i, v=v: Vw.view_book(Vw.FitCache(i), v)["book"], inp, LEAK_ROWS, seed=696002)
        ok = all(x["identical_up_to_t"] for x in rv)
        rec["leak_views"][str(v)] = rv
        P(f"   view {str(v):<52} {'PASS' if ok else 'FAIL'} (change visible: "
          f"{any(x['changed_after_t'] for x in rv)}); {time.time() - t1:.0f} s")
    P("")
    rec["repeat"] = {}
    for c in REPEAT_CELLS:
        a1 = Ln.fit_cell(inp, *c)["pred"]
        a2 = Ln.fit_cell(inp, *c)["pred"]
        same = bool(np.array_equal(a1, a2, equal_nan=True))
        rec["repeat"][str(c)] = same
        P(f"   bit-for-bit repeat {str(c):<48} {same}")
    P(f"wall {time.time() - t0:.0f} s")
    (out / "smoke.txt").write_text("\n".join(L) + "\n")
    (out / "smoke.json").write_text(json.dumps(rec, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
