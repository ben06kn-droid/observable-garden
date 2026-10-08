"""The ridge_stack confirmation (`prereg/ml-ridge-stack-confirmation.md`, registered at
77f3ee19469f500d5c3959c9612a04d250856b02). Box only.

Panels on 689000-689999:
  planted  U 689000-689099, corner 689100-689199, product 689200-689299,
           gated 689300-689399; every seed at level 1.5, the first 50 of each rule
           also at 1.0 and 2.5 (one residual draw and one set of rule features per seed)
  level 0  689400-689799 at the registered cost and at zero cost

ridge_stack is priced as one declared strategy through the supplied-streams tier; the
control is priced beside it the same way; the class tier beside both on the at-cost panels.
The per-panel pricing and recorded fields are the pilot's (`experiments.ml_pilot_2026_10_07`,
`price`), with mv_combine not run.

Refuses to start unless (section 7): the four pinned learn/ blobs match HEAD; LightGBM is
4.7.0; the wheel file given has the registered SHA-256; the installed lib_lightgbm.so has
the recorded SHA-256; no tracked changes; the registration commit is an ancestor of HEAD;
HEAD equals --expect-head; the platform is Linux x86_64.

**No holdout quantity is computed. Nothing about any outcome is printed.** The reader is
`experiments/read_ml_confirm_ridge_stack.py`.

    python -m experiments.ml_confirm_ridge_stack --out runs/ml_confirm/ridge_stack \
        --workers 150 --wheel ~/WHEEL.whl --expect-head <commit>
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

REGISTRATION = "77f3ee19469f500d5c3959c9612a04d250856b02"
PINNED_BLOBS = {"learn/ridge_stack.py": "2c09b25701038964c97a193f66a5203f99bf0915",
                "learn/inputs.py": "c52ff6d12a71f2c536de8e2bdc3478cc5c00e124",
                "learn/trees.py": "e21f38706067bacf251ef8494fbd8674fc20b1c4",
                "learn/stream_tier.py": "107abb472bb23b606877673e8b80ec75bf3eba95"}
LIGHTGBM = "4.7.0"
WHEEL_SHA256 = "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7"
LIB_SHA256 = "573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a"

RULE_SEEDS = {"U": 689000, "corner": 689100, "product": 689200, "gated": 689300}
PER_RULE = 100
ALL_LEVELS = 50                      # the first 50 seeds of each rule also at 1.0 and 2.5
LEVEL0_SEEDS = range(689400, 689800)
CARRY_SEED = 689999                  # the reader's paired bootstrap, recorded here
PREDICTORS = ("ridge_stack", "control")


def levels_for(seed: int, shape: str) -> tuple:
    return (1.0, 1.5, 2.5) if seed - RULE_SEEDS[shape] < ALL_LEVELS else (1.5,)


def tasks() -> list[tuple]:
    out = [("planted", s, shape) for shape, s0 in RULE_SEEDS.items()
           for s in range(s0, s0 + PER_RULE)]
    out += [("level0", s, None) for s in LEVEL0_SEEDS]
    return out


_W: dict = {}


def _init():
    if not _W:
        import environments.planted_panel as pp
        import environments.planted_fast as pf
        base = pp.load_base()
        _W.update(base=base, cache=pf.build(base.in_sample, base.members),
                  inv=pp.invariants_for(base))
    return _W


def one(task) -> list[dict]:
    import dataclasses
    import numpy as np
    import environments.planted_panel as pp
    import environments.planted_fast as pf
    from environments import planted_rules as prl
    from experiments.ml_pilot_2026_10_07 import _class_summary, price
    kind, seed, shape = task
    W = _init()
    base, cache, inv = W["base"], W["cache"], W["inv"]
    t0 = time.time()
    recs = []
    if kind == "planted":
        rule = prl.draw_features(seed, shape)
        draws = [prl.make_draw_rule(base, seed, beta, shape, rule)
                 for beta in levels_for(seed, shape)]
        classes, (Ea, Ea2, Eak) = pf.class_pass_draws(base, cache, seed, draws, 1000,
                                                      summary=_class_summary)
        w_star = draws[0].w_star_is
        tov, spd = prl.turnover(w_star), prl.speed(w_star)
        for d, cl in zip(draws, classes):
            panel = d.in_sample
            pop = pp.population_from_moments(Ea, Ea2, Eak, inv, d.c, panel.periods_per_year)
            recs.append({"seed": seed, "kind": "planted", "rule": rule, "shape": shape,
                         "level": d.beta, "cost": "registered", "c": d.c,
                         "plant_turnover": tov, "speed": spd,
                         "plant_all_rows": {
                             "net": pp.population_sharpe(base.in_sample, base.Sigma_is,
                                                         w_star, w_star, d.c),
                             "gross": prl.gross_population_sharpe(base.in_sample, base.Sigma_is,
                                                                  w_star, w_star, d.c)},
                         "shadow_share": float(pop.max() / d.beta), "class": cl,
                         "predictors": {n: price(n, panel, base, w_star, d.c, seed)
                                        for n in PREDICTORS}})
    else:
        d = pp.make_draw(base, seed, 0.0)
        classes, _ = pf.class_pass_draws(base, cache, seed, [d], 1000, summary=_class_summary)
        zero = np.zeros_like(np.asarray(d.in_sample.cost_rate, float))
        free = dataclasses.replace(d.in_sample, cost_rate=zero, borrow_rate=np.zeros_like(zero))
        for cost, panel, cl in (("registered", d.in_sample, classes[0]), ("zero", free, None)):
            recs.append({"seed": seed, "kind": "level0", "rule": None, "shape": None,
                         "level": 0.0, "cost": cost, "c": 0.0, "class": cl,
                         "predictors": {n: price(n, panel, base, d.w_star_is, 0.0, seed)
                                        for n in PREDICTORS}})
    for r in recs:
        r["task_seconds"] = time.time() - t0
    return recs


# -- start-up refusals (registration, section 7) -----------------------------------------

def _git(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lib_path() -> Path:
    import lightgbm
    return Path(lightgbm.__file__).parent / "lib" / "lib_lightgbm.so"


def refusals(expect_head: str, wheel: str | None, platform_name: str | None = None,
             lib: Path | None = None) -> list[str]:
    """Every registered start-up condition that fails, as text; empty means start."""
    import lightgbm
    bad = []
    head = _git("rev-parse", "HEAD").stdout.strip()
    for f, blob in PINNED_BLOBS.items():
        got = _git("rev-parse", f"HEAD:{f}").stdout.strip()
        if got != blob:
            bad.append(f"{f}: blob {got or 'missing'} is not the pinned {blob}")
    if lightgbm.__version__ != LIGHTGBM:
        bad.append(f"LightGBM {lightgbm.__version__}, not {LIGHTGBM}")
    if not wheel or not Path(wheel).expanduser().exists():
        bad.append("no wheel file given (--wheel)")
    elif _sha256(Path(wheel).expanduser()) != WHEEL_SHA256:
        bad.append("the wheel's SHA-256 is not the registered one")
    lib = lib or lib_path()
    if not lib.exists() or _sha256(lib) != LIB_SHA256:
        bad.append("the installed lib_lightgbm.so is missing or its SHA-256 is not the recorded one")
    if _git("status", "--porcelain", "--untracked-files=no").stdout.strip():
        bad.append("uncommitted changes to tracked files")
    if _git("merge-base", "--is-ancestor", REGISTRATION, "HEAD").returncode != 0:
        bad.append(f"the registration {REGISTRATION} is not an ancestor of HEAD")
    if head != expect_head:
        bad.append(f"HEAD {head} is not the expected {expect_head}")
    plat = platform_name or f"{platform.system()} {platform.machine()}"
    if plat != "Linux x86_64":
        bad.append(f"platform {plat}, not Linux x86_64")
    return bad


def provenance(head: str) -> dict:
    import lightgbm
    import numpy as np
    return {"platform": f"{platform.system()} {platform.machine()}",
            "python": platform.python_version(), "numpy": np.__version__,
            "lightgbm": lightgbm.__version__, "lib_lightgbm_sha256": _sha256(lib_path()),
            "wheel_sha256": WHEEL_SHA256, "git_head": head, "registration": REGISTRATION,
            "pinned_blobs": PINNED_BLOBS, "B": 1000, "carry_seed": CARRY_SEED,
            "cpus": os.cpu_count()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=150)
    ap.add_argument("--wheel", required=True, help="the LightGBM wheel file that was installed")
    ap.add_argument("--expect-head", required=True, help="the commit carrying the committed runner")
    a = ap.parse_args(argv)
    bad = refusals(a.expect_head, a.wheel)
    if bad:
        raise SystemExit("REFUSED:\n  " + "\n  ".join(bad))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / "results.jsonl").exists():
        raise SystemExit(f"{out / 'results.jsonl'} exists; not overwriting")
    _init()
    todo = tasks()
    (out / "provenance.json").write_text(json.dumps(
        {**provenance(a.expect_head), "tasks": len(todo), "workers": a.workers,
         "dry_run": False, "task_list": todo}, indent=1))
    t0 = time.time()
    done = 0
    with open(out / "results.jsonl.partial", "w") as fh, \
            ProcessPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(one, t) for t in todo]
        for f in as_completed(futs):
            for r in f.result():
                fh.write(json.dumps(r, default=float) + "\n")
            fh.flush()
            done += 1
            print(f"{done}/{len(todo)} tasks, {time.time() - t0:.0f} s", flush=True)
    os.replace(out / "results.jsonl.partial", out / "results.jsonl")
    print(f"wall {time.time() - t0:.0f} s; {len(todo)} tasks; results in {out}; no outcome printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
