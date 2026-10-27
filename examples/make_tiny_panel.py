"""Writes examples/data/tiny_panel.npz: a small synthetic daily panel (600 rows, 12 assets,
8 features) with a weak edge planted in one feature. The committed file is the object of record;
rerunning this writes the same arrays (the .npz container itself carries a timestamp).

    python -m examples.make_tiny_panel

With --plant it writes instead examples/data/tiny_panel_planted.npz: the same panel with a known
two-feature rule planted on top, and tiny_panel_planted.json recording that rule and its
population Sharpe. The planted strength is set so the rule's population Sharpe, net of the
panel's costs, is PLANT_TARGET; it is calibrated on a long simulation of the same process with
another seed, never on the 600 rows themselves.

    python -m examples.make_tiny_panel --plant
"""
import argparse
import json
from pathlib import Path

import numpy as np

from quixote import panel

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "tiny_panel.npz"
PLANTED = DATA / "tiny_panel_planted.npz"
CLASS = Path(__file__).resolve().parent / "class.json"

# the planted rule, in the class's terms: +rev5_rank -vol20_rank, equal weight
PLANT = (("rev5_rank", 1), ("vol20_rank", -1))
PLANT_TARGET = 3.0             # population Sharpe, annualised, net of costs; fixed before any run
LONG_T, LONG_SEED = 50_000, 1007


def plant(arrays: dict, strength: float) -> dict:
    """Row t's planted signal tilts the return 1 + delay rows later, as `panel.tiny`'s own edge does."""
    names = list(arrays["feature_names"])
    F, R = arrays["features"], arrays["returns"].copy()
    s = sum(sign * F[:, :, names.index(nm)] for nm, sign in PLANT)
    lag = 1 + int(arrays["delay"])
    R[lag:] += strength * s[:-lag]
    return {**arrays, "returns": R}


def rule_sharpe(arrays: dict) -> float:
    """The planted rule's Sharpe through the harness's own class table (net of costs). The arrays
    go through `panel.save` and `panel.read`, so the defaults (costs, borrow) are the file's."""
    import tempfile
    from quixote import classes
    from quixote.run import Harness
    with tempfile.TemporaryDirectory() as d:
        panel.save(Path(d) / "long.npz", **arrays)
        arrays = panel.read(str(Path(d) / "long.npz"))
    lc = classes.load(str(CLASS), arrays, compute_bar=False)
    h = Harness(arrays, lc).open(1)
    names = list(arrays["feature_names"])
    support = tuple((names.index(nm), float(sign)) for nm, sign in PLANT)
    return float(h.table.sharpe(support))


def calibrate() -> tuple[float, float]:
    """Bisect the strength so the long simulation's Sharpe hits PLANT_TARGET."""
    long = panel.tiny(seed=LONG_SEED, T=LONG_T)
    lo, hi = 0.0, 0.01
    for _ in range(14):
        mid = (lo + hi) / 2
        if rule_sharpe(plant(long, mid)) < PLANT_TARGET:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    return k, rule_sharpe(plant(long, k))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plant", action="store_true", help="write the planted copy and its truth file")
    a = ap.parse_args()
    if not a.plant:
        sha = panel.save(OUT, **panel.tiny(seed=7))
        print(f"wrote {OUT} (sha256 {sha[:16]})")
        return
    k, pop = calibrate()
    arrays = plant(panel.tiny(seed=7), k)
    sha = panel.save(PLANTED, **arrays)
    T = LONG_T - 1 - int(arrays["delay"])
    truth = {
        "panel_file": PLANTED.name,
        "panel_sha256": sha,
        "base": "panel.tiny(seed=7), the panel in tiny_panel.npz",
        "planted_rule": [(("+" if s > 0 else "-") + nm) for nm, s in PLANT],
        "strength": k,
        "population_sharpe": pop,
        "population_sharpe_target": PLANT_TARGET,
        "population_method": (f"the planted rule's annualised Sharpe, net of the panel's costs, through the "
                              f"harness's class table on panel.tiny(seed={LONG_SEED}, T={LONG_T}) with the "
                              f"same plant; standard error about {np.sqrt(252 / T):.2f}"),
    }
    PLANTED.with_suffix(".json").write_text(json.dumps(truth, indent=1) + "\n")
    print(f"wrote {PLANTED} (sha256 {sha[:16]}): {' '.join(truth['planted_rule'])}, strength {k:.6f}, "
          f"population Sharpe {pop:.3f}")


if __name__ == "__main__":
    main()
