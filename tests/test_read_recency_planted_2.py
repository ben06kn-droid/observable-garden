"""Round 2's reader on MADE-UP rows only: the registered rule's three branches, the order,
the NA40 sentence, power lines."""
import json

import numpy as np
import pytest

from experiments import read_recency_planted_2 as Rd


def _rows(seed=0, over=None):
    over = over or {}
    rng = np.random.default_rng(seed)
    rows = []
    for arm, n in Rd.N_REGISTERED.items():
        rates = {"W2": 0.035, "R15": 0.035, "fixed": 0.04, "unweighted": 0.035, **over.get(arm, {})}
        for k in range(n):
            u = rng.random()
            rec = {"arm": arm, "seed": 709000 + k, "block_length": 7, "block_length_last_neff": 8,
                   "stream": {t: {"S": 0.0, "p": 0.035 if u < r else 0.5, "L90": -1.0, "L": 7} for t, r in rates.items()}}
            if arm in Rd.CLASS_ARMS:
                rc = over.get(arm, {}).get("class", 0.008)
                rec["class"] = {"W2": {"S": 0.0, "p": 0.009 if u < rc else 0.5}}
            rows.append(rec)
    return rows


def test_w2_adopted_when_no_check_fails_and_the_order():
    text, out = Rd.read(_rows())
    assert out["decision"] == "W2 is ADOPTED for weighted reads"
    assert text.index("1. W2") < text.index("2. R15") < text.index("3. THE REGISTERED RULE") < text.index("6. POWER")
    assert "NA40 UNDER W2 (no expectation registered): it does not fail" in text


def test_r15_used_when_w2_fails_and_stop_when_both_fail():
    _, out = Rd.read(_rows(over={"NA40": {"W2": 0.08}}))
    assert out["decision"].startswith("W2 is NOT adopted") and out["NA40 W2 fails"]
    _, out2 = Rd.read(_rows(over={"N40": {"class": 0.03}}))
    assert out2["decision"].startswith("W2 is NOT adopted")
    _, out3 = Rd.read(_rows(over={"NA40": {"W2": 0.08}, "NV40": {"R15": 0.09}}))
    assert out3["decision"].startswith("W2 and R15 both fail")


def test_power_lines_and_a_short_arm(tmp_path):
    text, out = Rd.read(_rows(over={"E20": {"W2": 0.6, "R15": 0.5, "unweighted": 0.3}}))
    assert out["power E20 96% W2-unweighted"][1] > 0 and "W2 - R15" in text
    rows = [r for r in _rows() if not (r["arm"] == "D20" and r["seed"] == 709000)]
    assert Rd.read(rows)[1] == {"stopped": ["D20"]}
    (tmp_path / "provenance.json").write_text(json.dumps({"platform": "Linux x86_64"}))
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in _rows()))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
