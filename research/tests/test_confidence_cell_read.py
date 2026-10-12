"""The V2 cell's reader, on SYNTHETIC files only."""
import json

import numpy as np
import pytest

from experiments import confidence_cell_read as cr

NAMES = ["s1", "s2", "s3", "s4", "s5", "s6"]


def _conf(S, L, P, C0=0.5):
    return {"S": S, "C0": C0, "L": {"0.90": L, "0.95": L, "0.99": L}, "P_H": P,
            "n_ge": [0] * 81, "B": 1000}


def _rec(seed, covered_v2=True, sr=1.0, L=0.5, P=0.75, ho=0.3, p_class=0.01):
    levels = []
    for beta in cr.LEVELS:
        ss = [{"searcher": nm, "score": 1.5, "p_class": p_class, "p_trigger": 0.02,
               "truth": {"in_sample": sr, "holdout": ho}, "holdout_realized": ho,
               "conf_class": _conf(1.5, L, P), "conf_replay": _conf(1.5, L, P)}
              for nm in NAMES]
        levels.append({"beta": beta,
                       "v2": {"D": 0.3, "u": (seed % 1000) / 1000.0,
                              "covered": {f"{g:.2f}": covered_v2 for g in cr.GS},
                              "q": {f"{g:.2f}": 0.5 for g in cr.GS}},
                       "argmax": {"score": 2.0, "truth": {"in_sample": sr, "holdout": ho},
                                  "holdout_realized": ho, "conf_class": _conf(2.0, L, P)},
                       "searchers": ss})
    return {"seed": seed, "levels": levels}


def _file(tmp_path, recs):
    f = tmp_path / "d.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return f


def test_v2_verdicts_and_the_stop_on_a_fail_low(tmp_path):
    # covered on 950 of 1000 panels at every g: CONSERVATIVE at 0.90, EXACT at
    # 0.95, FAILS LOW at 0.99, and the read stops after V2
    recs = [_rec(s, covered_v2=(s % 100 >= 5)) for s in cr.SEEDS]   # 950 covered
    text, stopped = cr.read(cr.load(_file(tmp_path, recs)))
    v2 = text.split("2. V1")[0] if not stopped else text
    assert "EXACT" in v2                                  # g = 0.95
    assert "CONSERVATIVE" in v2                           # g = 0.90: 0.95 > 0.90
    assert "FAILS LOW" in v2 and stopped                  # g = 0.99: 0.95 < 0.99
    assert "V1 AND V3 ARE NOT PRINTED" in text and "3. V3" not in text


def test_without_a_v2_failure_v1_and_v3_are_printed(tmp_path):
    recs = [_rec(s) for s in cr.SEEDS]                     # all covered
    text, stopped = cr.read(cr.load(_file(tmp_path, recs)))
    assert not stopped and "2. V1" in text and "3. V3" in text
    assert "trigger replay (AUDIT)" in text and "(class argmax)" in text
    # V1: sr 1.0 >= L 0.5 everywhere -> 1000 of 1000, conservative
    line = next(l for l in text.splitlines() if l.strip().startswith("s1 "))
    assert " 1000   1000" in line and "conservative" in line
    # V3 pools the six searchers: P = 0.75, outcome always true -> one bin,
    # 6000/6000 observed, Brier (0.75 - 1)^2 = 0.0625
    assert "n 6000, Brier 0.0625" in text and "observed 6000/6000" in text


def test_v1_counts_failures_low(tmp_path):
    recs = [_rec(s, sr=(0.4 if s % 10 == 0 else 1.0)) for s in cr.SEEDS]  # 90% covered
    text, _ = cr.read(cr.load(_file(tmp_path, recs)))
    s1_99 = [l for l in text.splitlines() if l.strip().startswith("s1 ") and " 0.99 " in l]
    assert len(s1_99) == 6                     # 3 levels x (class, replay audit)
    assert all("FAILS LOW" in l and " 900   1000" in l for l in s1_99)


def test_certified_subset_and_empty_certified(tmp_path):
    recs = [_rec(s, p_class=0.5) for s in cr.SEEDS]       # nothing certified
    text, _ = cr.read(cr.load(_file(tmp_path, recs)))
    lines = [l for l in text.splitlines() if l.strip().startswith("certified")]
    assert len(lines) == 6 and all(l.rstrip().endswith("none") for l in lines)


def test_it_refuses_the_wrong_block_or_shape(tmp_path):
    recs = [_rec(s) for s in cr.SEEDS]
    with pytest.raises(SystemExit, match="seeds"):
        cr.load(_file(tmp_path, recs[:-1]))
    bad = [_rec(s) for s in cr.SEEDS]
    bad[3]["levels"] = bad[3]["levels"][:2]
    with pytest.raises(SystemExit, match="levels"):
        cr.load(_file(tmp_path, bad))


def test_v1_tightness_is_the_gap_between_sr_and_the_bound(tmp_path):
    # sr alternates 1.0 / 2.0 with L = 0.5: gaps 0.5 and 1.5, median 1.0
    recs = [_rec(s, sr=(1.0 if s % 2 else 2.0)) for s in cr.SEEDS]
    text, _ = cr.read(cr.load(_file(tmp_path, recs)))
    line = next(l for l in text.splitlines() if l.strip().startswith("s1 ") and " 0.95 " in l)
    assert line.rstrip().endswith("+1.0000 [+0.5000, +1.5000]")
    assert "gap SR_pop - L_g: median [q25, q75]" in text

