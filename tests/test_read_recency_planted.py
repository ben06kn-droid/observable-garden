"""The recency planted reader on MADE-UP rows only (no planted panel has been drawn)."""
import json

import numpy as np
import pytest

from experiments import read_recency_planted as Rd


def _rows(rate=None, seed=0, **over):
    """Made-up rows: per arm and test, p below each level with the given probability."""
    rng = np.random.default_rng(seed)
    base = {"stream": {"unweighted": 0.04, "weighted": 0.04, "weighted_superseded": 0.15},
            "class": {"unweighted": 0.01, "weighted_superseded": 0.06}}
    rows = []
    for arm, n in Rd.N_REGISTERED.items():
        r_arm = {**base["stream"], **over.get(arm, {})}
        for k in range(n):
            u = rng.random()
            rec = {"arm": arm, "seed": 700000 + k, "block_length": 2, "block_length_last_neff": 3,
                   "stream": {t: {"S": 0.0, "p": (0.035 if u < r else 0.5), "L90": -1.0} for t, r in r_arm.items()
                              if t != "weighted_superseded" or arm in ("N20", "N40")}}
            if arm in ("N20", "N40"):
                rec["class"] = {t: {"S": 0.0, "p": (0.009 if u < r else 0.5)} for t, r in base["class"].items()}
            rows.append(rec)
    return rows


def test_the_order_and_a_nominal_run():
    text, out = Rd.read(_rows())
    assert text.index("SIZE") < text.index("POWER") < text.index("NON-STATIONARY")
    assert out["size stream N20 fixed 96%"]["fails"] is False and out["size stream N40 superseded 96%"]["fails"]
    assert out["superseded-fixed stream N40 96%"]["above_zero"] and out["size class N20 superseded 96%"]["fails"]
    assert "NV40 expectation (does not fail at either level): HOLDS" in text
    assert "NA40 (no expectation): the weighted rate does not fail" in text


def test_power_expectations_both_ways():
    over = {"E20": {"weighted": 0.5, "unweighted": 0.26}, "D20": {"weighted": 0.2, "unweighted": 0.47},
            "C20": {"weighted": 0.51, "unweighted": 0.69}}
    text, out = Rd.read(_rows(**over))
    assert out["power E20"]["holds"] and out["power D20"]["holds"] and out["power C20"]["holds"]
    bad = {"E20": {"weighted": 0.2, "unweighted": 0.3}}
    _, out2 = Rd.read(_rows(**bad))
    assert not out2["power E20"]["holds"]


def test_a_size_failure_and_the_na40_branch():
    text, out = Rd.read(_rows(N20={"weighted": 0.09}, NA40={"weighted": 0.12}))
    assert out["size stream N20 fixed 96%"]["fails"]
    assert out["NA40 weighted fails"] and "block-length rule is reopened" in text


def test_a_short_arm_stops_and_the_read_happens_once(tmp_path):
    rows = [r for r in _rows() if not (r["arm"] == "C20" and r["seed"] == 700000)]
    assert Rd.read(rows)[1] == {"stopped": ["C20"]}
    (tmp_path / "provenance.json").write_text(json.dumps({"platform": "Linux x86_64", "dry_run": False}))
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in _rows()))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
    (tmp_path / "s").mkdir()
    (tmp_path / "s" / "provenance.json").write_text(json.dumps({"platform": "Darwin arm64"}))
    with pytest.raises(SystemExit, match="not a box run"):
        Rd.main(["--dir", str(tmp_path / "s")])


def test_wilson():
    lo, hi = Rd.wilson(40, 1000)
    assert lo < 0.04 < hi and abs(lo - 0.0295) < 0.002
