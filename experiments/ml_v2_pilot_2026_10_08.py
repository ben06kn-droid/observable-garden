"""The version-2 pilot (`prereg/ml-v2-exploratory-2026-10-08.md`, "The version-2 pilot",
817f8d2). EXPLORATORY. Box only.

Tasks:
- `seed`  (planted): one seed of one shape at levels 0.5/1.0/1.5/2.5; per level the five
  single streams (v2 base view under G1/G2/G3, version 1, the plain ridge) through the
  supplied-streams tier, R4's quantities, and the class tier beside them (one class pass
  per seed).
- `menu`  (planted): the first 20 seeds of each shape at levels 1.0 and 1.5; all 126 fits,
  the 294 views under each grid on the common window from row 778, and the nested menus'
  best view and menu-tier p.
- `level0`: 100 seeds at cost and at zero cost (fits shared); the five single streams and
  the menus at both costs, the class tier at cost.
Every tier uses B = 1,000 and the panel's seed. Results are written as JSON rows; **nothing
about any outcome is printed.** The reader is `experiments/read_ml_v2_pilot_2026_10_08.py`.

    OMP_NUM_THREADS=1 python -m experiments.ml_v2_pilot_2026_10_08 --out runs/ml_v2_pilot/2026-10-08 \\
        --workers 180 --wheel ~/WHEEL.whl --expect-head <commit>
Dry path (smoke block, one task of each kind; never pilot panels):
    ... --out runs/ml_v2_pilot_dry/2026-10-08 --dry --workers 3 --wheel ... --expect-head ...
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

NOTE_COMMIT = "817f8d2c3c85df00aebcd39bb8863dc5be6c552b"
SHAPES = ("U", "corner", "product", "gated", "leadlag", "volcond", "regime")
SHAPE_SEEDS = {s: 697000 + 50 * i for i, s in enumerate(SHAPES)}
PER_SHAPE = 50
LEVELS = (0.5, 1.0, 1.5, 2.5)
MENU_LEVELS = (1.0, 1.5)
MENU_SEEDS = 20
LEVEL0 = range(697400, 697500)
DRY_BLOCK = range(696000, 697000)
DRY = {"seed": (696500, "leadlag"), "menu": (696501, "volcond", 1.0), "level0": 696502}
B = 1000
MENU_START = 778
NEW_SHAPES = ("leadlag", "volcond", "regime")


def tasks() -> list[tuple]:
    out = []
    for sh, s0 in SHAPE_SEEDS.items():
        for s in range(s0, s0 + PER_SHAPE):
            out.append(("seed", s, sh, None))
            if s - s0 < MENU_SEEDS:
                out += [("menu", s, sh, lev) for lev in MENU_LEVELS]
    out += [("level0", s, None, None) for s in LEVEL0]
    return out


def dry_tasks() -> list[tuple]:
    s, sh = DRY["seed"]
    m, msh, mlev = DRY["menu"]
    return [("seed", s, sh, None), ("menu", m, msh, mlev), ("level0", DRY["level0"], None, None)]


_W: dict = {}


def _base():
    if not _W:
        import environments.planted_panel as pp
        import environments.planted_fast as pf
        from environments import etf_v2_inputs as E
        base = pp.load_base()
        pinned = E.load()
        _W.update(base=base, cache=pf.build(base.in_sample, base.members),
                  v2={"is": E.for_segment(base.in_sample, pinned), "ho": E.for_segment(base.holdout, pinned)})
    return _W


def _draws(seed: int, shape: str, levels) -> list:
    from environments import planted_rules as prl
    W = _base()
    if shape in NEW_SHAPES:
        rule = prl.draw_features_v2(seed, shape, n_v=W["v2"]["is"]["V"].shape[2])
        return [prl.make_draw_rule_v2(W["base"], seed, b, shape, rule, v2=W["v2"]) for b in levels]
    rule = prl.draw_features(seed, shape)
    return [prl.make_draw_rule(W["base"], seed, b, shape, rule) for b in levels]


def _inputs(panel, zero_cost: bool = False):
    from learn2 import learner as Ln
    v2 = _W["v2"]["is"]
    inp = Ln.from_panel(panel, blocks={"X": v2["X"], "V": v2["V"]}, groups=v2["G"])
    if zero_cost:
        inp = dataclasses.replace(inp, cost_rate=np.zeros_like(inp.cost_rate),
                                  borrow_rate=np.zeros_like(inp.borrow_rate))
    return inp


def _bc(panel) -> np.ndarray:
    import environments.planted_panel as pp
    from environments.real_sandbox import RealSandbox
    return np.asarray(RealSandbox(panel, spec_class=pp.CLS).base_feature_columns(), float)


def _tier(stream, bc_rows, ppy, seed) -> dict:
    from learn import stream_tier
    st = stream_tier.certify(stream[None, :], bc_rows, ppy, B, seed)
    return {"p": st["p"], "score": st["score"], "block_length": int(st["block_length"])}


def singles(panel, inp, cache, seed, w_star=None, c=0.0) -> dict:
    """The five single streams, their R4 quantities, at this panel's cost."""
    from experiments.ml_pilot_2026_10_07 import window_sharpes
    from learn import inputs as I1
    from learn import ridge_stack
    from learn2 import views as Vw
    W = _base()
    bc = _bc(panel)
    out = {}
    base = Vw.base_view(inp.available)
    for g, rates in Vw.RATE_GRIDS.items():
        vb = Vw.view_book(cache, base, rates=rates)
        rows = np.arange(vb["first"], inp.earned.shape[0])
        s = Vw.net_stream(vb["book"], inp, rows)
        rec = _tier(s, bc[rows], inp.ppy, seed)
        rec.update(Vw.turnover_stats(vb["book"], inp, rows))
        rec["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
        corr = vb["variant_corr"]
        rec["variant_corr_mean"] = float(corr[np.triu_indices(9, 1)].mean()) if corr is not None else None
        if c > 0:
            rec["pop"] = window_sharpes(W["base"], panel, vb["book"], w_star, c, rows)
            rec["plant_window"] = window_sharpes(W["base"], panel, w_star, w_star, c, rows)
        out[f"v2 base {g}"] = rec
    diags = [d for m in ("roll252", "roll756", "expand") for d in cache.get(base[0], 5, "market", m)["diagnostics"]]
    out["v2 base edges"] = {"refits": len(diags), "at_edge": sum(1 for d in diags if d["at_edge"])}
    for name, which in (("version 1", "ridge_stack"), ("plain ridge", "control")):
        res = ridge_stack.run(panel, which)
        rows = res["scored_rows"]
        p = res["positions"]
        s = I1.net_stream(p, panel, rows)
        rec = _tier(s, bc[rows], panel.periods_per_year, seed)
        rec.update(Vw.turnover_stats(p, inp, rows))
        rec["ann_vol"] = float(s.std(ddof=1) * np.sqrt(inp.ppy))
        if c > 0:
            rec["pop"] = window_sharpes(W["base"], panel, p, w_star, c, rows)
            rec["plant_window"] = window_sharpes(W["base"], panel, w_star, w_star, c, rows)
        out[name] = rec
    return out


def menus(panel, inp, cache, seed) -> dict:
    """Per grid and nested menu: the best view (by observed score, stored not printed) and
    its menu-tier p, on the common window from MENU_START."""
    from learn2 import states as S
    from learn2 import views as Vw
    rows = np.arange(MENU_START, inp.earned.shape[0])
    bc = _bc(panel)[rows]
    gates = S.regime_gates(S.market_states(inp.earned, inp.d))
    views = Vw.all_views(inp.available)
    sel = {"21": lambda v: v[2] == "market" and v[3] == "always",
           "42": lambda v: v[3] == "always", "294": lambda v: True}
    out = {}
    for g, rates in Vw.RATE_GRIDS.items():
        streams = np.array([Vw.net_stream(Vw.view_book(cache, v, gates, rates)["book"], inp, rows)
                            for v in views])
        sd = streams.std(axis=1, ddof=1)
        score = np.where(sd > 0, streams.mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0) * np.sqrt(inp.ppy)
        rec = {}
        for name, f in sel.items():
            ii = [i for i, v in enumerate(views) if f(v)]
            j = int(np.argmax(score[ii]))
            mp = Vw.menu_p(streams[ii], j, bc, inp.ppy, B, seed)
            v = views[ii[j]]
            rec[name] = {"p": mp["p"], "score": mp["score"], "block_length": int(mp["block_length"]),
                         "view": [list(v[0]), v[1], v[2], v[3]], "n": len(ii)}
        out[g] = rec
    return out


def class_summary(d, obs, rep, L) -> dict:
    M_b = rep.max(axis=0)
    S_ = float(obs.max())
    return {"p": (1 + int(np.sum(M_b >= S_))) / (len(M_b) + 1), "class_max": S_, "block_length": int(L)}


def one(task) -> list[dict]:
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments import planted_rules as prl
    from learn2 import views as Vw
    kind, seed, shape, level = task
    W = _base()
    t0 = time.time()
    recs = []
    if kind == "seed":
        draws = _draws(seed, shape, LEVELS)
        classes, _ = pf.class_pass_draws(W["base"], W["cache"], seed, draws, B, summary=class_summary)
        w_star = draws[0].w_star_is
        for d, cl in zip(draws, classes):
            inp = _inputs(d.in_sample)
            cache = Vw.FitCache(inp)
            recs.append({"kind": "seed", "seed": seed, "shape": shape, "rule": d.rule, "level": d.beta,
                         "cost": "registered", "c": d.c, "speed": prl.speed(w_star),
                         "plant_turnover": prl.turnover(w_star), "class": cl,
                         "streams": singles(d.in_sample, inp, cache, seed, w_star, d.c)})
    elif kind == "menu":
        (d,) = _draws(seed, shape, (level,))
        inp = _inputs(d.in_sample)
        cache = Vw.FitCache(inp)
        recs.append({"kind": "menu", "seed": seed, "shape": shape, "rule": d.rule, "level": level,
                     "cost": "registered", "speed": prl.speed(d.w_star_is),
                     "menus": menus(d.in_sample, inp, cache, seed)})
    else:
        d = pp.make_draw(W["base"], seed, 0.0)
        classes, _ = pf.class_pass_draws(W["base"], W["cache"], seed, [d], B, summary=class_summary)
        inp = _inputs(d.in_sample)
        cache = Vw.FitCache(inp)
        free = dataclasses.replace(d.in_sample, cost_rate=np.zeros_like(np.asarray(d.in_sample.cost_rate)),
                                   borrow_rate=np.zeros_like(np.asarray(d.in_sample.borrow_rate)))
        inp0 = _inputs(free, zero_cost=True)
        cache0 = Vw.FitCache(inp0)
        cache0.fits = cache.fits                     # costs do not enter the fits
        cache0.targets = cache.targets
        for cost, panel, ip, ch, cl in (("registered", d.in_sample, inp, cache, classes[0]),
                                        ("zero", free, inp0, cache0, None)):
            recs.append({"kind": "level0", "seed": seed, "shape": None, "rule": None, "level": 0.0,
                         "cost": cost, "class": cl, "streams": singles(panel, ip, ch, seed),
                         "menus": menus(panel, ip, ch, seed)})
    for r in recs:
        r["task_seconds"] = time.time() - t0
    return recs


# -- refusals (as the confirmation's runner, with the v2 pins) --------------------------------

def refusals(expect_head: str, wheel: str | None) -> list[str]:
    from experiments import ml_confirm_ridge_stack as C
    from environments import etf_v2_inputs as E
    bad = [b for b in C.refusals(expect_head, wheel) if "registration" not in b]
    if C._git("merge-base", "--is-ancestor", NOTE_COMMIT, "HEAD").returncode != 0:
        bad.append(f"the pilot section {NOTE_COMMIT} is not an ancestor of HEAD")
    import hashlib
    if not E.PINNED.exists() or hashlib.sha256(E.PINNED.read_bytes()).hexdigest() != E.PINNED_SHA256:
        bad.append("the v2 inputs pin is missing or not its registered SHA-256")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=180)
    ap.add_argument("--wheel", required=True)
    ap.add_argument("--expect-head", required=True)
    ap.add_argument("--dry", action="store_true", help="one task of each kind on the smoke block")
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out / 'results.jsonl'} exists; not overwriting")
    _base()
    todo = dry_tasks() if a.dry else tasks()
    todo.sort(key=lambda t: {"menu": 0, "level0": 1, "seed": 2}[t[0]])   # longest first
    import platform
    (out / "provenance.json").write_text(json.dumps(
        {"git_head": a.expect_head, "note": NOTE_COMMIT, "platform": f"{platform.system()} {platform.machine()}",
         "dry_run": a.dry, "tasks": len(todo), "workers": a.workers, "task_list": todo}, indent=1))
    t0 = time.time()
    done = 0
    with open(out / "results.jsonl.partial", "w") as fh, ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for f in as_completed(futs):
            for r in f.result():
                fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            done += 1
            print(f"{done}/{len(todo)} tasks, {time.time() - t0:.0f} s", flush=True)
    os.replace(out / "results.jsonl.partial", out / "results.jsonl")
    print(f"wall {time.time() - t0:.0f} s; {len(todo)} tasks; no outcome printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
