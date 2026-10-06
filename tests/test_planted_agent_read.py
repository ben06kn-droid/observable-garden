"""The stage-2 reader, on SYNTHETIC priced files only."""
import json

import numpy as np
import pytest

from experiments import planted_agent_read as ar

GRID = [-1.0, 0.05, 81]


def _conf(S, L=0.2, C0=0.9, P=0.7):
    curve = list(np.linspace(1.0, 0.0, 81))
    return {"C0": C0, "L": {g: L for g in ar.GS}, "P_H": P, "curve": curve, "grid": GRID}


def _run(arm, lv, seed, p=0.5, sr=0.3, ho=0.2, route=None, pred=(0.8, 0.3), pv=0.5):
    pw = None
    if arm == "prior-weighted":
        pw = {"route": route, "status": "CERTIFIED" if route else "FAIL", "declined": False}
    rec = {"equals": False, "two_of_three": True, "equals_pop_best": False,
           "two_of_three_pop_best": False}
    d = {"arm": arm, "seed": seed, "run_id": f"{arm}_{lv}_{seed}",
         "prediction": {"mean": pred[0], "sd": pred[1]},
         "class_p": {"p_upper": p, "confidence": _conf(sr), **({"prior_weighted": pw} if pw else {})},
         "planted_truth": {"submitted_truth": {"in_sample": sr, "holdout": ho},
                           "submitted_recovery": rec, "submitted_support_true": [[0, 1.0]],
                           "short_list_contains_m_star": False,
                           "short_list_overlaps_m_star": True}}
    kinds = ["start", "class_p", "planted_truth", "end"]
    if arm in ar.GRAMMAR:
        d["verdict"] = {"p_certifying": pv, "confidence": _conf(sr)}
        kinds.append("verdict")
    d["events"] = [{"kind": k, **({"level": lv} if k == "start" else {})} for k in kinds]
    return d


def _write(tmp_path, f=lambda arm, lv, i: {}, rp=14):
    for arm, lvs in ar.ARMS.items():
        for lv in lvs:
            n = rp if arm == "replay gate (reasoned pick)" else ar.N
            for i in range(n):
                d = _run(arm, lv, ar.SEED0 + i, **f(arm, lv, i))
                (tmp_path / f"cell_planted_{arm.replace(' ', '_')}_{lv}_{i}.json").write_text(
                    json.dumps(d))
    return tmp_path


pytestmark = pytest.mark.filterwarnings("ignore:Precision loss:RuntimeWarning")


def test_a_clean_set_reads_through_every_rule(tmp_path):
    text, stopped = ar.read(ar.load(_write(tmp_path)))
    assert not stopped
    for head in ("RULE 1", "RULE 2", "RULE 3", "RULE 4", "RULE 5", "RULE 6", "RULE 7",
                 "PRIOR-WEIGHTED", "DESCRIPTIVE"):
        assert head in text, head
    assert "the sealed holdout was not opened" in text


def test_rule1_fails_high_and_the_read_stops(tmp_path):
    # unsaturable at level 1.0: 6 of 20 certified with negative population Sharpe
    f = lambda arm, lv, i: ({"p": 0.001, "sr": -0.1}
                            if arm == "unsaturable" and lv == 1.0 and i < 6 else {})
    text, stopped = ar.read(ar.load(_write(tmp_path, f)))
    assert stopped and "FAILS HIGH" in text and "RULE 2" not in text
    assert "631000-631019" in text and "   unsaturable" in text


def test_rule1_reads_the_prior_weighted_arm_per_route(tmp_path):
    f = lambda arm, lv, i: ({"route": "list", "sr": -0.2}
                            if arm == "prior-weighted" and lv == 0.0 and i < 5 else {})
    text, stopped = ar.read(ar.load(_write(tmp_path, f)))
    lines = [l for l in text.splitlines() if "prior-weighted" in l and "0.0" in l]
    assert any("list route" in l and "  5/20" in l and "FAILS HIGH" in l for l in lines)
    assert any("search route" in l and "  0/20" in l for l in lines)
    assert stopped


def test_rule2_counts_only_correct_certificates(tmp_path):
    f = lambda arm, lv, i: ({"p": 0.001, "sr": 0.5 if i < 8 else -0.5}
                            if arm == "replay gate" and lv == 1.5 else {})
    _, stopped = ar.read(ar.load(_write(tmp_path, f)))
    assert stopped        # 12 false certificates at 1.5 also fail rule 1
    f = lambda arm, lv, i: ({"p": 0.001, "sr": 0.5}
                            if arm == "replay gate" and lv == 1.5 and i < 8 else {})
    text, _ = ar.read(ar.load(_write(tmp_path, f)))
    line = next(l for l in text.split("RULE 2")[1].splitlines()
                if l.strip().startswith("replay gate ") and " 1.5 " in l)
    assert "  8/20 " in line and "scripted 0.4391" in line


def test_rule7_matches_actual_size_on_level_zero(tmp_path):
    def f(arm, lv, i):
        if arm != "unsaturable":
            return {}
        if lv == 0.0:
            return {"p": 0.2 + i * 0.01, "pv": 0.3 + i * 0.01}
        if lv == 1.5:
            return {"p": 0.1 if i < 7 else 0.9, "pv": 0.25 if i < 3 else 0.9}
        return {}
    text, _ = ar.read(ar.load(_write(tmp_path, f)))
    r7 = text.split("RULE 7")[1].split("PRIOR-WEIGHTED")[0]
    assert "class tier   threshold 0.2000 (actual size at level 0 0.0500); at 1.5 7/20" in r7
    assert "replay tier  threshold 0.3000 (actual size at level 0 0.0500); at 1.5 3/20" in r7


def test_the_stated_distribution_beside_the_curve(tmp_path):
    text, _ = ar.read(ar.load(_write(tmp_path)))
    d = text.split("DESCRIPTIVE")[1]
    # stated mean 0.8, sd 0.3 -> P(SR>0) = Phi(2.667) = 0.996; C0 0.9 -> +0.096
    assert "stated P(SR>0) - C0: mean +0.096" in d
    assert "cover 20/20" in d


def test_it_refuses_an_unregistered_or_unpriced_set(tmp_path):
    a = tmp_path / "a"
    a.mkdir()
    with pytest.raises(SystemExit, match="reasoned-pick"):
        ar.load(_write(a, rp=15))
    p = tmp_path / "b"
    p.mkdir()
    _write(p)
    f = next(p.glob("cell_planted_replay_gate_0.0_3.json"))
    d = json.loads(f.read_text())
    d["events"] = [e for e in d["events"] if e["kind"] != "class_p"]
    f.write_text(json.dumps(d))
    with pytest.raises(SystemExit, match="not priced"):
        ar.load(p)


def test_the_format_is_price_runs_own(monkeypatch, tmp_path):
    """End to end on a small set: planted dry runs, priced by price_runs, read here."""
    from environments import planted_panel as pp
    from experiments import planted_agent as pa
    from experiments import price_runs as pr
    from experiments.real_prompts import read_prompts
    from tests.test_planted_panel import _panel
    base = pp.base_from(_panel(K=5))
    monkeypatch.setattr(pp, "load_base", lambda: base)
    inv = pp.invariants_for(base, cache_dir=tmp_path / "inv")
    monkeypatch.setattr(pp, "invariants_for", lambda b, **kw: inv)
    monkeypatch.setattr(ar, "N", 2)
    monkeypatch.setattr(ar, "RP_COUNTS", (2,))
    out = tmp_path / "runs"
    out.mkdir()
    prompts = read_prompts()
    for arm, lvs in ar.ARMS.items():
        for lv in lvs:
            for i in range(2):
                rec = pa.run_one(arm, ar.SEED0 + i, lv, i, prompts=prompts, dry_run=True,
                                 base=base)
                f = out / f"{rec.run_id}.json"
                f.write_text(json.dumps(rec.to_json(), default=str))
                r = pr.price_one((str(f), False, 20))
                pr._write(f, pr.load_run(f), r)
    text, _ = ar.read(ar.load(out))
    assert "RULE 1" in text
    assert ("RULE 7" in text) or ("THE READ STOPS HERE" in text)


def test_p5_is_reported_for_certified_runs_separately_on_both_tiers(tmp_path):
    runs = ar.load(_write(tmp_path, lambda arm, lv, i: (
        {"p": 0.001, "sr": 0.5} if lv == 1.5 and i < 5 else {})))
    realized = {d["run_id"]: (1.0 if i % 2 else -1.0)
                for rs in runs.values() for i, d in enumerate(rs)}
    for (arm, lv), rs in runs.items():                 # replay tier certifies the same 5
        for i, d in enumerate(rs):
            if "verdict" in d:
                d["verdict"]["status"] = "CERTIFIED" if (lv == 1.5 and i < 5) else "FAIL"
    lines = []
    ar.descriptive(runs, lines.append, realized)
    text = "\n".join(lines)
    assert "class  P_5 all " in text and "class  P_5 certified" in text
    assert "replay P_5 certified" in text
    cert15 = [l for l in lines if "P_5 certified" in l and "(n 5)" in l]
    assert cert15                                      # the 5 certified at 1.5, both tiers
    assert any("P_5 certified none" in l for l in lines)   # no certified at level 0

