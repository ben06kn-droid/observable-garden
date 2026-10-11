"""The agent cell's reader and the panel's grading reader on MADE-UP priced and graded files only:
both branches of R1, R2 (EB closer / not) and R3 (B lower / not distinguished), the joint
bootstrap's use, CRPS, R4, read-once refusals, and the objects' branch sentences."""
import base64
import json

import numpy as np
import pytest

from experiments import read_agent_cell_etf_recent as RA
from experiments import read_etf_recent_grade as RG

NB = 400


def _b64(a):
    return base64.b64encode(np.ascontiguousarray(a, np.float32).tobytes()).decode()


def _world(realized, L90, eb, raw, stated_a, stated_b, seed=1):
    """n submissions alternating arms A/B; the joint bootstrap jitters every item by one
    common shock per replicate plus a small idiosyncratic one (shared window)."""
    rng = np.random.default_rng(seed)
    n = len(realized)
    arms = ["A" if i % 2 == 0 else "B" for i in range(n)]
    priced = {"n_sessions": n + 1, "no_submit": ["z"], "priced": [], "nulls": {
        "class_w2_max": rng.normal(1.0, 0.2, 500).tolist(), "class_unw_max": rng.normal(0.8, 0.2, 500).tolist(),
        "sancho_w2": rng.normal(0.4, 0.2, 500).tolist()}}
    items = []
    for i in range(n):
        st = stated_a if arms[i] == "A" else stated_b
        priced["priced"].append({"session": f"s{i}", "arm": arms[i], "kind": "rule", "support": [[i % 40, 1.0]],
                                 "S_w": raw[i], "S_unw": raw[i] - 0.1, "L90": L90[i], "EB": {"value": eb[i]},
                                 "predict": {"mean": st[i // 2], "sd": 0.4, "note": ""},
                                 "search": {"moves": 5 + i, "candidates_seen": None}})
        items.append({"id": f"s{i}", "type": "submission", "arm": arms[i], "realized": realized[i],
                      "net_return": realized[i] * 0.1, "ci90": [realized[i] - 1, realized[i] + 1]})
    for bid in ("book_all", "book_A", "book_B"):
        items.append({"id": bid, "type": "book", "realized": 0.2, "net_return": 0.02, "ci90": [-1.0, 1.4]})
    common = rng.normal(0, 0.05, NB)[:, None]
    RS = np.array([it["realized"] for it in items])[None, :] + common + rng.normal(0, 0.02, (NB, len(items)))
    RR = RS * 0.1
    grades = {"label": "weak: 1.76 years", "first_holdout_date": "2025-01-02", "last_date": "2026-10-09",
              "n_periods": 444, "block_length": 5, "seed": 723000, "items": items,
              "bootstrap": {"shape": [NB, len(items)], "sharpe_b64": _b64(RS), "net_return_b64": _b64(RR)}}
    return priced, grades


def test_r1_r2_r3_both_branches():
    n = 20
    # bounds far above realised: TOO HIGH; EB on top of realised, raw far above: EB CLOSER; B states lower
    p, g = _world(realized=[0.0] * n, L90=[1.0] * n, eb=[0.0] * n, raw=[2.0] * n,
                  stated_a=[1.5] * 10, stated_b=[0.5] * 10)
    text, dec = RA.read(p, g)
    assert dec["R1"]["all"]["too_high"] and "TOO HIGH" in text
    v = dec["R2"]["gate point estimate EB (rules) vs raw weighted (S_w)"]["verdict"]
    assert "CLOSER" in v
    assert "LOWER" in dec["R3"]["B_minus_A_mean"]["verdict"]
    assert "CRPS weighted (primary)" in dec["R2"] and "CRPS unweighted (beside)" in dec["R2"]
    assert dec["R4"]["positive"] == 0 and "book_A" in dec["R4"]
    assert "limits:" in text and "1 no_submit" in text
    # the opposite branches
    p, g = _world(realized=[2.0] * n, L90=[0.0] * n, eb=[0.0] * n, raw=[2.0] * n,
                  stated_a=[1.0] * 10, stated_b=[1.0] * 10)
    text, dec = RA.read(p, g)
    assert not dec["R1"]["all"]["too_high"] and "consistent with a 90% bound" in text
    assert "NOT closer" in dec["R2"]["gate point estimate EB (rules) vs raw weighted (S_w)"]["verdict"]
    assert "not distinguished" in dec["R3"]["B_minus_A_mean"]["verdict"]


def test_the_sample_crps_matches_the_direct_formula():
    s = np.random.default_rng(3).normal(size=301)
    c = RA.SampleCRPS(s)
    for y in (-2.0, 0.1, 3.0):
        direct = np.abs(s - y).mean() - 0.5 * np.abs(s[:, None] - s[None, :]).mean()
        assert c(y) == pytest.approx(direct, abs=1e-12)


def test_read_once(tmp_path):
    p, g = _world([0.5] * 4, [0.0] * 4, [0.3] * 4, [1.0] * 4, [0.4] * 2, [0.4] * 2)
    (tmp_path / "priced.json").write_text(json.dumps(p))
    (tmp_path / "grades.json").write_text(json.dumps(g))
    args = ["--priced", str(tmp_path / "priced.json"), "--grades", str(tmp_path / "grades.json"), "--out", str(tmp_path / "r")]
    assert RA.main(args) == 0
    with pytest.raises(SystemExit, match="read once"):
        RA.main(args)


def test_the_objects_reader_branches(tmp_path):
    def obj(i, cert96, cert90, real, L):
        return {"id": i, "type": "object", "certified": {"96%": cert96, "90%": cert90}, "realized": real,
                "L90_weighted": L, "held": real >= L, "ci90": [real - 0.7, real + 0.7], "net_return": real / 10,
                "only_2026": {"rows": 194, "realized": 0.1}}
    g = {"label": "weak: 1.76 years", "first_holdout_date": "2025-01-02", "last_date": "2026-10-09", "n_periods": 444,
         "block_length": 5, "B": 10000, "seed": 723000,
         "items": [obj("stream_d1", True, True, 0.9, 0.5), obj("stream_d0", False, True, 0.1, 0.6),
                   obj("class_member", False, False, -0.2, -1.0)]}
    (tmp_path / "grades.json").write_text(json.dumps(g))
    text = RG.read(tmp_path)
    assert "(1) the Sancho stream, d = 1: certified in-sample under the recency weights (W2) at the registered weight (96% level); its weighted lower bound held" in text
    assert "NOT IMPLEMENTABLE: certified in-sample" in text and "(90% level, labelled); its weighted lower bound did not hold" in text
    assert "(3) the class's weighted best member, d = 1: refused in-sample; consistent with the registered detection floor. Graded: realised -0.200 ≥" in text
    assert "weak: 1.76 years" in text and "2026 only (194 rows; descriptive, never deciding)" in text
    with pytest.raises(SystemExit, match="read once"):
        RG.read(tmp_path)
