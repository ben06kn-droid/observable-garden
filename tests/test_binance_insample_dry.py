"""The Binance read's dry path: the whole run_read on a SYNTHETIC Binance-shaped panel
(never this panel), and the reader on its output."""
import json

import numpy as np

from experiments import binance_insample_read as R
from experiments import read_binance_insample as Rd


def test_the_dry_path_runs_every_step_in_order(tmp_path):
    assert R.main(["--dry", "--out", str(tmp_path)]) == 0
    rec = json.loads((tmp_path / "results.json").read_text())
    assert rec["dry_run"] and "synthetic" in rec["panel"]
    assert rec["repeat_bit_identical"] == {"d0": True, "d1": True}
    t1, t2, d1 = rec["test1_stream_d0"], rec["test2_class_d0"], rec["descriptive_stream_d1"]
    assert t1["alpha"] == 0.04 and t2["alpha"] == 0.01 and t1["seed"] == 701000 and t2["seed"] == 701001
    assert t1["n_rows"] == d1["n_rows"] + 2                       # d = 0: one more row, one less embargo
    assert "p" not in d1 and d1["seed"] == 701002 and d1["ci95"][0] <= d1["S"] <= d1["ci95"][1]
    assert np.isfinite(t1["S"]) and 0 < t1["p"] <= 1 and len(t2["best_member"]["features"]) >= 1
    text, out = Rd.read(rec)
    assert text.startswith("DRY RUN") and out["descriptive_stream_d1"]["verdict"] is None


def test_the_synthetic_panels_have_the_two_timings():
    from learn2 import learner as Ln
    (r0, v0, c0), (r1, v1, c1) = R.synthetic(1), R.synthetic(2)
    p0, i0, _ = R.setup(r0, v0, c0)
    p1, i1, _ = R.setup(r1, v1, c1)
    assert (i0.d, i1.d) == (0, 1) and p0.features.shape[0] == p1.features.shape[0] + 1
    assert c0["rates"].shape == p0.cost_rate.shape and (c0["rates"] >= 0).all()
