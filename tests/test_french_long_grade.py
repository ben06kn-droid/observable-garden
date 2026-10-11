"""The B1 holdout grader on SYNTHETIC panels only (never the real file): the whole grading end
to end with the real Sancho fits (a synthetic in-sample read, then the spanning grading; every
check passes and the in-sample Sharpes reproduce); a restarted book fails check c3; a
non-causal fit fails check c2; a missing or out-of-window holdout value refuses; the laptop
is refused."""
import datetime as dt
from types import SimpleNamespace

import numpy as np
import pytest

from experiments import french_long_grade as G
from experiments import french_long_read as FL

T_IN, T_HO, M = 1300, 260, 8


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    rng = np.random.default_rng(717000)
    R = 0.01 * rng.standard_normal((T_IN + T_HO, M))
    R[:150, 6] = np.nan                                   # a late industry
    d0 = dt.date(1926, 7, 1)
    dates = [d0 + dt.timedelta(days=k) for k in range(T_IN + T_HO)]
    names = [f"N{j}" for j in range(M)]
    tmp = tmp_path_factory.mktemp("fl_grade")
    p = tmp / "b1_insample.csv"
    p.write_text("synthetic")
    return {"dates_in": dates[:T_IN], "dates_ho": dates[T_IN:], "R_in": R[:T_IN], "R_ho": R[T_IN:],
            "names": names, "paths": [p], "tmp": tmp}


@pytest.fixture(scope="module")
def read_b1(synth):
    """A synthetic in-sample read (the runner's own code) and its pins."""
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    mp = pytest.MonkeyPatch()
    mp.setattr(FL, "B", 120)
    try:
        res = FL.run_read(synth["dates_in"], synth["names"], synth["R_in"], "b1", members_in_order(CLS, 40)[:128],
                          workers=2, cache_dir=synth["tmp"], cache_name="synthetic-grade")
    finally:
        mp.undo()
    pins = FL.pin_record(synth["dates_in"], synth["names"], synth["R_in"], synth["paths"])
    return res, pins


def test_the_grading_end_to_end(synth, read_b1, capsys):
    res, pins = read_b1
    g = G.grade(synth["dates_in"], synth["names"], synth["R_in"], synth["dates_ho"], synth["R_ho"], pins, res,
                synth["paths"], workers=2, B_=200)
    for part in ("b1", "b2", "b3", "c"):
        assert all(g["checks"][part].values()), (part, g["checks"][part])
    assert g["n_periods"] == T_HO and g["first_holdout_date"] == str(synth["dates_ho"][0])
    assert set(g["objects"]) == set(G.OBJECTS) and g["seed"] == 719000 and g["B"] == 200
    for o in g["objects"].values():
        lo, hi = o["ci90"]
        assert lo <= hi and o["held"] == (o["realized"] >= o["L90_weighted"])
    assert g["objects"]["stream_d0"]["descriptive"]["unweighted"]["label"] == G.UNWEIGHTED_LABEL
    out = capsys.readouterr().out
    assert "FAIL" not in out and "check c no restart: c3_book_carried_stream_d1: pass" in out
    for o in g["objects"].values():                       # no value printed
        assert f"{o['realized']:.3f}" not in out


def _causal_fit(args):
    dates, names, R, lag = args
    panel, info, inp = FL.sancho_inputs(dates, names, R, lag)
    X = panel.features[:, :, 0]
    return lag, X - X.mean(axis=1, keepdims=True), 300, 0.0


def _noncausal_fit(args):
    lag, b, first, s = _causal_fit(args)
    return lag, b / b.std(), first, s                      # scaled by the whole series: not causal


def _restarted(book, inp, rows):
    """A book restarted from zero at the boundary: the failure c3 exists to catch."""
    from learn2 import views as Vw
    k = int(len(rows) * 0.8)
    return np.concatenate([Vw.net_stream(book, inp, rows[:k]), Vw.net_stream(book, inp, rows[k:])])


def test_book_carried_catches_a_restart():
    rng = np.random.default_rng(1)
    T, Mx = 40, 5
    inp = SimpleNamespace(earned=0.01 * rng.standard_normal((T, Mx)), cost_rate=np.full((T, Mx), 5e-4),
                          borrow_rate=np.full((T, Mx), 2e-5))
    book = rng.standard_normal((T, Mx))
    h0 = 3 + int((T - 3) * 0.8)
    assert G.book_carried(G.default_net, book, inp, 3, h0)
    assert not G.book_carried(_restarted, book, inp, 3, h0)


def test_a_restarted_book_refuses_the_grading(synth, read_b1):
    res, pins = read_b1
    every = lambda h, r: {k: True for k in r}
    with pytest.raises(G.GradingRefused, match="c3_book_carried_stream_d1"):
        G.grade(synth["dates_in"], synth["names"], synth["R_in"], synth["dates_ho"], synth["R_ho"], pins, res,
                synth["paths"], ref_check=every, workers=1, fit_fn=_causal_fit, net_fn=_boundary_restart)


def _boundary_restart(book, inp, rows):
    """Restart the book from zero at the in-sample/holdout boundary of a spanning panel."""
    from learn2 import views as Vw
    n_rows = inp.earned.shape[0]
    if n_rows <= T_IN - 253:                               # an in-sample-only panel
        return Vw.net_stream(book, inp, rows)
    lag = (T_IN + T_HO) - 253 - n_rows
    k = (T_IN - 253 - lag) - rows[0]
    return np.concatenate([Vw.net_stream(book, inp, rows[:k]), Vw.net_stream(book, inp, rows[k:])])


def test_a_noncausal_fit_fails_positions_identity(synth, read_b1):
    res, pins = read_b1
    every = lambda h, r: {k: True for k in r}
    with pytest.raises(G.GradingRefused, match="c2_positions_identical_stream_d1"):
        G.grade(synth["dates_in"], synth["names"], synth["R_in"], synth["dates_ho"], synth["R_ho"], pins, res,
                synth["paths"], ref_check=every, workers=1, fit_fn=_noncausal_fit)


def test_the_in_sample_reproduction_is_checked(synth, read_b1):
    res, pins = read_b1
    assert G.check_refs({"a": 1.0841, "b": 0.7738}, {"a": 1.084, "b": 0.774}) == {"a": True, "b": True}
    assert G.check_refs({"a": 1.0856}, {"a": 1.084}) == {"a": False}
    bad = dict(pins, d1=dict(pins["d1"], X_features_sha256="0" * 64))
    with pytest.raises(G.GradingRefused, match="d1_X_features_sha256"):
        G.grade(synth["dates_in"], synth["names"], synth["R_in"], synth["dates_ho"], synth["R_ho"], bad, res,
                synth["paths"], workers=1, fit_fn=_causal_fit)


def test_the_holdout_loader_refuses(tmp_path):
    ok = tmp_path / "ok.csv"
    ok.write_text("date,A,B\n1990-01-02,0.1,0.2\n1990-01-03,0.3,-0.1\n")
    d, n, R = G.load_holdout(ok)
    assert d[0] == dt.date(1990, 1, 2) and R[1, 1] == pytest.approx(-0.001)
    miss = tmp_path / "miss.csv"
    miss.write_text("date,A,B\n1990-01-02,0.1,\n1990-01-03,0.3,-0.1\n")
    with pytest.raises(G.GradingRefused, match="missing holdout value"):
        G.load_holdout(miss)
    early = tmp_path / "early.csv"
    early.write_text("date,A,B\n1989-12-29,0.1,0.2\n1990-01-02,0.3,-0.1\n")
    with pytest.raises(G.GradingRefused, match="outside"):
        G.load_holdout(early)
    late = tmp_path / "late.csv"
    late.write_text("date,A,B\n1995-12-29,0.1,0.2\n1996-01-02,0.3,-0.1\n")
    with pytest.raises(SystemExit, match="after the read's end"):
        G.load_holdout(late)


def test_the_member_support_and_the_laptop_refusal():
    names = ["a_z", "a_rank", "b_z", "b_rank"]
    assert G.member_support(names, ["+a_rank", "-b_z"]) == ((1, 1.0), (2, -1.0))
    assert G.LIVE == "00417de103785335f2b3a4b6860b7e81a1b33135"
    bad = G.refusals("0" * 40)
    assert any("Linux" in b for b in bad) and not any("wheel" in b for b in bad)
