"""French holdout grading: the split, the grader and the reader on SYNTHETIC panels with a
fake "holdout" segment (no real holdout row exists here)."""
import datetime as dt
import json

import numpy as np
import pytest

from environments.french_panel import panel_from_returns
from experiments import french_holdout_grade as G
from experiments import french_holdout_split as Sp
from experiments import read_french_holdout as Rd


def _days(start, n):
    d, out = dt.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(12)
    M = 8
    n_in, n_ho = 1300 + 255, 320
    dates = _days("2014-01-01", n_in + n_ho)
    R = np.round(0.01 * rng.standard_normal((n_in + n_ho, M)), 4)
    return dates[:n_in], [f"i{j}" for j in range(M)], R[:n_in], dates[n_in:], R[n_in:]


@pytest.fixture(scope="module")
def setup(data):
    dates_in, names, R_in, dates_ho, R_ho = data
    p_in, p_sp, h0 = G.build(dates_in, names, R_in, dates_ho, R_ho)
    refs = {"member_2937": round(G.sharpe(G.net(p_in, G.member_positions(p_in), 0)), 3),
            "ridge_stack": round(G.sharpe(G.net(p_in, G.ridge_positions(p_in), G.RIDGE_FIRST_ROW)), 3)}
    conf = {"grid": [-1.0, 0.05, 81], "curve": list(np.linspace(0.0, 1.0, 81))}
    insample = {"ridge_stack": {"L90": 0.05, "confidence": conf}, "member_2937": {"L90": -0.5, "confidence": conf}}
    pos_in = {"member_2937": G.member_positions(p_in), "ridge_stack": G.ridge_positions(p_in)}
    pos_sp = {"member_2937": G.member_positions(p_sp), "ridge_stack": G.ridge_positions(p_sp)}
    return dict(p_in=p_in, p_sp=p_sp, h0=h0, refs=refs, insample=insample, pos_in=pos_in, pos_sp=pos_sp)


# -- split ----------------------------------------------------------------------------------

def _text(dates, M=3):
    head = ["header", "  Average Value Weighted Returns -- Daily", "," + ",".join(f"I{j}" for j in range(M))]
    body = [d.strftime("%Y%m%d") + "," + ",".join(["0.10"] * M) for d in dates]
    return "\n".join(head + body + ["", "  Average Equal Weighted Returns -- Daily", "x"])


def test_the_split_keeps_only_2020_onward_and_checks_the_count(tmp_path):
    dates = _days("2019-12-20", 20)
    s = Sp.split_holdout(_text(dates), expected_rows=None)
    assert s["first_date"] >= "20200101" and all(int(d) >= 20200101 for d, _ in s["rows"])
    n = sum(d >= dt.date(2020, 1, 1) for d in dates)
    assert len(s["rows"]) == n and s["last_date"] == dates[-1].strftime("%Y%m%d")
    with pytest.raises(Sp.SplitRefused, match="not the counted"):
        Sp.split_holdout(_text(dates), expected_rows=n + 1)
    bad = _text(dates).replace(dates[-1].strftime("%Y%m%d") + ",0.10", dates[-1].strftime("%Y%m%d") + ",-99.99")
    with pytest.raises(Sp.SplitRefused, match="missing-value"):
        Sp.split_holdout(bad, expected_rows=None)
    sha = Sp.write_csv(tmp_path / "h.csv", s["columns"], s["rows"])
    d, cols, R = G.load_holdout(tmp_path / "h.csv")
    assert len(sha) == 64 and cols == s["columns"] and np.allclose(R, 0.001)


def test_the_holdout_loader_refuses_in_sample_rows(tmp_path):
    (tmp_path / "h.csv").write_text("date,a,b\n2019-12-31,0.1,0.2\n2020-01-02,0.1,0.2\n")
    with pytest.raises(G.GradingRefused):
        G.load_holdout(tmp_path / "h.csv")


# -- grader ---------------------------------------------------------------------------------

def test_a_correct_spanning_build_passes_every_check_and_grades(data, setup):
    dates_in, names, R_in, dates_ho, R_ho = data
    g = G.grade(dates_in, names, R_in, dates_ho, R_ho, setup["p_in"].features, setup["refs"], setup["insample"])
    assert all(g["tolerances"]["pass"].values())
    assert all(v for k, v in g["no_restart"].items() if not k.endswith("_nonzero"))
    assert g["first_holdout_date"] == str(dates_ho[0])
    assert g["last_date"] == str(dates_ho[-1]) and g["n_periods"] == len(dates_ho)
    for name, o in g["objects"].items():
        lo, hi = o["ci95"]
        assert lo <= o["realized"] <= hi and o["held"] == (o["realized"] >= o["L90_insample"])
        assert o["realized_minus_L90"] == pytest.approx(o["realized"] - o["L90_insample"])


def test_a_tolerance_failure_refuses_before_any_holdout_value(data, setup):
    dates_in, names, R_in, dates_ho, R_ho = data
    X_bad = setup["p_in"].features.copy()
    X_bad[10, 0, 0] += 1e-6
    with pytest.raises(G.GradingRefused, match="Option A tolerances"):
        G.grade(dates_in, names, R_in, dates_ho, R_ho, X_bad, setup["refs"], setup["insample"])


def test_a_restarted_book_makes_the_grader_refuse(setup):
    def restarted_net(panel, w, start):              # the book restarts from zero at the boundary
        a = G.net(panel, w, start)
        b = G.net(panel, w, setup["h0"])
        return np.concatenate([a[:setup["h0"] - start], b])
    nr = G.check_no_restart(setup["p_in"], setup["p_sp"], setup["h0"], setup["pos_in"], setup["pos_sp"],
                            net_fn=restarted_net)
    assert nr["member_2937_carried_position_nonzero"] and not nr["member_2937_book_carried"]
    with pytest.raises(G.GradingRefused, match="no-restart"):
        G.refuse_if_failed({k: v for k, v in nr.items() if not k.endswith("_nonzero")}, "no-restart checks")


def test_a_restarted_state_makes_the_grader_refuse(setup):
    import dataclasses
    p_sp, h0 = setup["p_sp"], setup["h0"]
    F = p_sp.features.copy()
    F[h0:h0 + 253] = 0.0                               # lookbacks restarted: unwarmed rows
    p_restart = dataclasses.replace(p_sp, features=F)
    nr = G.check_no_restart(setup["p_in"], p_restart, h0, setup["pos_in"], setup["pos_sp"])
    assert not nr["holdout_features_warm"]
    pos = dict(setup["pos_sp"])
    w = pos["ridge_stack"].copy()
    w[h0:] = 0.0                                       # walk-forward restarted: no position yet
    pos["ridge_stack"] = w
    nr2 = G.check_no_restart(setup["p_in"], setup["p_sp"], h0, setup["pos_in"], pos)
    assert not nr2["ridge_stack_position_at_boundary"]
    pos3 = dict(setup["pos_sp"])
    w3 = pos3["ridge_stack"].copy()
    w3[h0 - 5] += 0.01                                 # in-sample positions moved by a restart
    pos3["ridge_stack"] = w3
    nr3 = G.check_no_restart(setup["p_in"], setup["p_sp"], h0, setup["pos_in"], pos3)
    assert not nr3["ridge_stack_positions_identical"]
    for bad in (nr, nr2, nr3):
        with pytest.raises(G.GradingRefused):
            G.refuse_if_failed({k: v for k, v in bad.items() if not k.endswith("_nonzero")}, "no-restart checks")


def test_the_curve_lookup_interpolates_and_flags_values_off_the_grid():
    conf = {"grid": [-1.0, 0.05, 81], "curve": list(np.linspace(0.0, 1.0, 81))}
    assert G.curve_at(conf, 1.0) == (pytest.approx(0.5), False)
    assert G.curve_at(conf, 5.0)[1] and G.curve_at(conf, -2.0) == (0.0, True)


def test_the_grader_refuses_on_the_laptop():
    bad = G.refusals("0" * 40)
    assert any("Linux" in b for b in bad) and any("expect-head" in b for b in bad)


# -- reader ---------------------------------------------------------------------------------

def _grades(x_stream, x_member):
    o = lambda x, L: {"realized": x, "ci95": [x - 0.8, x + 0.8], "L90_insample": L, "realized_minus_L90": x - L,
                      "ci95_minus_L90": [x - 0.8 - L, x + 0.8 - L], "C_at_realized": 0.4, "C_clipped": False,
                      "held": x >= L}
    return {"registration": G.LIVE, "git_head": "x", "first_holdout_date": "2020-01-02", "last_date": "2026-08-31",
            "n_periods": 1674, "block_length": 3, "B": 10000, "seed": 694000,
            "objects": {"ridge_stack": o(x_stream, 0.065), "member_2937": o(x_member, -0.518)}}


def test_the_reader_prints_both_branches_and_the_standing_sentence():
    t = Rd.read(_grades(0.30, -0.90))
    assert "the ridge_stack stream: the in-sample 90% lower bound held on the holdout" in t
    assert "class member 2937 (+ma_spread_z, -ma_spread_rank): the in-sample 90% lower bound did not hold" in t
    assert Rd.ALWAYS in t and "2026-08-31" in t and t.index("ridge_stack") < t.index("member 2937")
    t2 = Rd.read(_grades(0.01, -0.2))
    assert "did not hold on the holdout (realised +0.010 < bound +0.065)" in t2


def test_the_reader_reads_once(tmp_path):
    (tmp_path / "grades.json").write_text(json.dumps(_grades(0.3, 0.0)))
    assert Rd.main(["--dir", str(tmp_path)]) == 0
    with pytest.raises(SystemExit, match="already read"):
        Rd.main(["--dir", str(tmp_path)])
