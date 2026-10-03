"""7.5 stage 1's reader, on SYNTHETIC files in the results' format -- never on results."""
import json

import pytest

from experiments import planted_edge_read as rd

NAMES = ["stop-when-cleared", "extend-while-improving", "cleared-restart",
         "lookahead-stop-when-cleared", "random-extend-while-improving",
         "second-best-while-improving"]


def _rec(i, b, false_at=None, power=None):
    """One searcher record. `false_at[(b, alpha)]`: panels i < it carry a false certificate
    at that level (p below alpha, truth <= 0). `power[b]`: panels i < it carry a correct one."""
    false_at, power = false_at or {}, power or {}
    p, truth = 0.5, 0.3
    if i < false_at.get((b, 0.01), 0):
        p, truth = 0.005, -0.2
    elif i < false_at.get((b, 0.05), 0):
        p, truth = 0.03, -0.2
    elif b > 0 and i < power.get(b, 0):
        p, truth = 0.002, 0.9
    return {"searcher": None, "support": [[0, 1.0], [1, -1.0], [2, 1.0]], "score": 0.5,
            "n_moves": 3, "p_class": p, "p_trigger": p,
            "truth": {"in_sample": truth, "holdout": truth * 0.9 + (0.01 * (i % 7))},
            "holdout_realized": truth * 0.8, "equals": i % 10 == 0,
            "two_of_three": i % 3 == 0, "equals_pop_best": i % 20 == 0,
            "two_of_three_pop_best": i % 4 == 0}


def _synthetic(path, false_at=None, power=None, seeds=None, drop_level=False):
    seeds = list(seeds if seeds is not None else rd.SEEDS)
    lines = []
    for i, seed in enumerate(seeds):
        levels = []
        for b in rd.LEVELS:
            if drop_level and b == 1.5 and i == 0:
                continue
            ss = []
            for name in NAMES:
                r = _rec(i, b, false_at, power)
                r["searcher"] = name
                ss.append(r)
            levels.append({"seed": seed, "beta": b, "pop_best_sr": 0.3 + b * (1 + (i % 5) / 4),
                           "class_argmax_recovery": {"equals": i % 8 == 0, "two_of_three": i % 2 == 0,
                                                     "equals_pop_best": i % 9 == 0,
                                                     "two_of_three_pop_best": i % 3 == 0},
                           "searchers": ss})
        lines.append(json.dumps({"seed": seed, "levels": levels}))
    path.write_text("\n".join(lines) + "\n")
    return path


def test_it_refuses_anything_but_the_registered_2000_seeds(tmp_path):
    with pytest.raises(SystemExit, match="not exactly"):
        rd.load(_synthetic(tmp_path / "a", seeds=range(600000, 601999)))
    with pytest.raises(SystemExit, match="not exactly"):
        rd.load(_synthetic(tmp_path / "b", seeds=range(600001, 602001)))
    f = _synthetic(tmp_path / "c")
    lines = f.read_text().splitlines()
    f.write_text("\n".join(lines + [lines[0]]) + "\n")
    with pytest.raises(SystemExit, match="twice"):
        rd.load(f)
    with pytest.raises(SystemExit, match="four levels"):
        rd.load(_synthetic(tmp_path / "d", drop_level=True))
    f.write_text("\n".join(lines[:-1] + ['{"seed": 601999, "lev']) + "\n")
    with pytest.raises(SystemExit, match="does not parse"):
        rd.load(f)


def test_the_registered_thresholds_at_n_2000():
    assert rd.kstar(2000, 0.05) == 120 and rd.kstar(2000, 0.01) == 29
    assert rd.kstar(20, 0.05) == 3 and rd.kstar(20, 0.01) == 2


def test_rule_1_at_the_threshold_passes_below_and_fails_at(tmp_path):
    text, failed = rd.read(rd.load(_synthetic(tmp_path / "e", false_at={(0.0, 0.05): 119})))
    assert not failed and "all 48 pass" in text
    text, failed = rd.read(rd.load(_synthetic(tmp_path / "f", false_at={(0.0, 0.05): 120})))
    assert failed and "6 of 48 fail high" in text


def test_a_rule_1_failure_stops_the_read_and_prints_the_whole_block_replication(tmp_path):
    text, failed = rd.read(rd.load(_synthetic(tmp_path / "g", false_at={(1.0, 0.01): 29})))
    assert failed
    assert "NOT PRINTED" in text and "--replication --draws 2000" in text
    assert "has-session -t '=curve_rep'" in text
    assert "RULE 2 — power" not in text and "THE STANDING CHECK\n" not in text


def test_nearest_the_bar_is_the_pooled_power_nearest_half_ties_to_the_lower(tmp_path):
    f = _synthetic(tmp_path / "h", power={0.5: 400, 1.0: 1100, 1.5: 1900})
    text, failed = rd.read(rd.load(f))
    assert not failed
    assert "NEAREST-THE-BAR: level 1.0" in text
    f = _synthetic(tmp_path / "i", power={0.5: 900, 1.0: 1100, 1.5: 1900})
    text, _ = rd.read(rd.load(f))
    assert "NEAREST-THE-BAR: level 0.5" in text          # 0.45 and 0.55 tie: the lower


def test_all_sections_print_when_rule_1_passes(tmp_path):
    text, failed = rd.read(rd.load(_synthetic(tmp_path / "j", power={1.0: 1000})))
    assert not failed
    for sec in ("RULE 2 — power", "RULE 3 — recovery", "RULE 5 — out of sample",
                "THE STANDING CHECK", "(class argmax)", "combined (planted)",
                "stage 2's input"):
        assert sec in text, sec
