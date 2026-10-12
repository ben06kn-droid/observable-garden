"""The ETF recent host grader on SYNTHETIC data only: a synthetic in-sample read by the runner's
own main (rows dropped before a stand-in cutoff, a scored window), then the grading of the
three objects plus a rule and a model-stream submission on a synthetic holdout; a restarted book
refuses; the holdout parser refuses gaps and a boundary mismatch; the grader refuses until its
registrations are set."""
import base64
import datetime as dt
import hashlib
import json

import numpy as np
import pytest

from experiments import etf_recent_grade as EG
from experiments import etf_recent_read as ER
from experiments import french_long_grade as FG
from tests.test_etf_recent_read import DROP, SCORE0, _write_cut

M, T_IN, T_HO = 30, 1600, 60
_FITS = {}


def _fit_memo(args):
    dates, tickers, P, Vol, lag = args
    key = (len(dates), lag)
    if key not in _FITS:
        _FITS[key] = ER._fit(args)
    return _FITS[key]


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    rng = np.random.default_rng(723150)
    T = T_IN + T_HO
    f = 0.008 * rng.standard_normal(T)
    R = f[:, None] + 0.008 * rng.standard_normal((T, M))
    P = 50.0 * np.cumprod(1.0 + R, axis=0)
    Vol = np.exp(rng.normal(13.0, 0.5, (T, M)))
    days = np.busday_offset("2005-01-03", np.arange(T), roll="forward")
    dates = [dt.date.fromisoformat(str(d)) for d in days]
    tickers = ["SPY"] + [f"E{j:02d}" for j in range(M - 1)]
    root = tmp_path_factory.mktemp("grade")
    mp = pytest.MonkeyPatch()
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from experiments import french_long_read as FL
    mp.setattr(ER, "refusals", lambda head, wheel: [])
    mp.setattr(ER, "LAST_DATE", dates[T_IN - 1])
    mp.setattr(ER, "USE_FROM", dates[DROP])
    mp.setattr(ER, "SCORE_FROM", dates[SCORE0])
    mp.setattr(ER, "SCORE_TO", dates[T_IN - 1])
    mp.setattr(ER, "members", lambda: members_in_order(CLS, 40)[:128])
    mp.setattr(ER, "CACHE_DIR", root / "cache")
    mp.setattr(FL, "B", 120)
    cut = _write_cut(root / "cut", dates[:T_IN], tickers, P[:T_IN], Vol[:T_IN])
    out = root / "read"
    assert ER.main(["--cut", str(cut), "--out", str(out), "--expect-head", "x", "--wheel", "w", "--workers", "2"]) == 0
    rec, bad, paths = ER.check_cut(cut)
    d_in, tk, P_in, V_in, n_drop = ER.load_from(paths, use_from=dates[DROP], last=dates[T_IN - 1])
    results = json.loads((out / "results.json").read_text())
    pins = json.loads((out / "pins.json").read_text())
    # one rule submission and one model-stream submission, priced as pricing would price them
    support = ((0, 1.0), (3, -1.0))
    panel_in, _ = ER.sancho_inputs(d_in, tk, P_in, V_in, 2)
    _, s = FG.member_book(panel_in, support)
    S_w = FG.wsharpe(s[ER.scored_index(panel_in)])
    S_u = EG.sharpe(s[ER.scored_index(panel_in)], 252.0)
    submissions = {"sessions": 3, "no_submit": ["s3"], "submissions": [
        {"session": "s1", "arm": "A", "kind": "rule", "support": [[0, 1.0], [3, -1.0]], "predict": {"mean": 0.3, "sd": 0.5}},
        {"session": "s2", "arm": "B", "kind": "baseline_model", "support": "baseline_model",
         "predict": {"mean": 0.6, "sd": 0.4}}]}
    priced = {"priced": [{"session": "s1", "S": S_u, "S_w": S_w, "L90": S_u - 1.0, "L90_w2": S_w - 1.2},
                         {"session": "s2", "S": 0.45, "S_w": 0.5, "L90": 0.05, "L90_w2": 0.1}]}
    w = dict(dates_in=d_in, tickers=tk, P_in=P_in, V_in=V_in, n_dropped=n_drop, cut=rec,
             dates_ho=dates[T_IN:], P_ho=P[T_IN:], V_ho=Vol[T_IN:], pins=pins, results=results,
             priced=priced, submissions=submissions)
    yield w
    mp.undo()


def test_the_grading_end_to_end(world, capsys):
    g = EG.grade(**world, workers=1, fit_fn=_fit_memo, B_=60)
    ids = [i["id"] for i in g["items"]]
    assert ids == ["stream_d1", "stream_d0", "class_member", "s1", "s2", "book_all", "book_A", "book_B"]
    assert g["n_periods"] == T_HO and g["B"] == 60 and g["seed"] == 723000
    assert all(v for v in g["checks"]["b1"].values()) and all(v for v in g["checks"]["c"].values())
    for it in g["items"]:
        assert np.isfinite(it["realized"]) and len(it["ci90"]) == 2
        if it["type"] != "book":
            assert it["held"] == (it["realized"] >= it["L90"])
    # the objects keep the parent's W2 L90 (scripted certificate); submissions are held against the
    # cell's UNWEIGHTED L90, with the W2 beside, labelled
    for o in ("stream_d1", "stream_d0", "class_member"):
        it = next(i for i in g["items"] if i["id"] == o)
        assert it["L90"] == it["L90_weighted"] and "W2-weighted L90, as registered" in it["L90_statistic"]
    s1 = next(i for i in g["items"] if i["id"] == "s1")
    assert s1["L90"] == pytest.approx(world["priced"]["priced"][0]["L90"]) and "unweighted" in s1["L90_statistic"]
    assert s1["held_w2"]["label"] == "recency-weighted, descriptive"
    assert s1["held_w2"]["held"] == (s1["realized"] >= s1["L90_w2"])
    s2 = next(i for i in g["items"] if i["id"] == "s2")
    d1 = next(i for i in g["items"] if i["id"] == "stream_d1")
    assert s2["realized"] == d1["realized"]                        # the model-stream submission is test 1's stream
    shp = g["bootstrap"]["shape"]
    RS = np.frombuffer(base64.b64decode(g["bootstrap"]["sharpe_b64"]), np.float32).reshape(shp)
    assert shp == [60, len(ids)] and np.isfinite(RS).all()
    out = capsys.readouterr().out
    assert "check b1 pins" in out and "check c no restart" in out and "FAIL" not in out
    for it in g["items"]:                                          # no value printed
        assert f"{it['realized']:.3f}" not in out


def test_a_restarted_book_refuses(world):
    from learn2 import views as Vw
    n_in = {lag: ER.sancho_inputs(world["dates_in"], world["tickers"], world["P_in"], world["V_in"], lag)[1].earned.shape[0]
            for lag in (2, 1)}
    sizes = {n + T_HO: n for n in n_in.values()}

    def restarted(book, inp, rows):
        T = inp.earned.shape[0]
        if T not in sizes:
            return Vw.net_stream(book, inp, rows)
        h0 = sizes[T]
        a, b = rows[rows < h0], rows[rows >= h0]
        return np.concatenate([Vw.net_stream(book, inp, a), Vw.net_stream(book, inp, b)])
    with pytest.raises(EG.GradingRefused, match="c3_book_carried_stream"):
        EG.grade(**world, workers=1, fit_fn=_fit_memo, net_fn=restarted, B_=20)


def test_wrong_pins_or_prices_refuse(world):
    bad = dict(world, pins={**world["pins"], "d1": {**world["pins"]["d1"], "X_features_sha256": "0" * 64}})
    with pytest.raises(EG.GradingRefused, match="b1 pins"):
        EG.grade(**bad, workers=1, fit_fn=_fit_memo, B_=10)
    for key in ("S_w", "S"):                                       # both the unweighted and the W2 Sharpe are checked
        pr = {"priced": [{**world["priced"]["priced"][0], key: world["priced"]["priced"][0][key] + 0.01},
                         world["priced"]["priced"][1]]}
        with pytest.raises(EG.GradingRefused, match="b2 in-sample"):
            EG.grade(**dict(world, priced=pr), workers=1, fit_fn=_fit_memo, B_=10)


def _chart(days, adj):
    ts = [int(dt.datetime(d.year, d.month, d.day, 14, 30, tzinfo=dt.timezone.utc).timestamp()) for d in days]
    return json.dumps({"chart": {"result": [{"timestamp": ts, "indicators": {
        "quote": [{"volume": [1000] * len(days)}], "adjclose": [{"adjclose": adj}]}}], "error": None}}).encode()


def test_the_holdout_parser(tmp_path):
    from data.etf_recent_cut import sessions
    last = dt.date(2025, 1, 10)
    days = sessions(dt.date(2024, 12, 30), last)
    raw, cutd = tmp_path / "raw", tmp_path / "insample"
    raw.mkdir()
    cutd.mkdir()
    fetch = {"tickers": {}}
    for t in ("SPY", "E00"):
        adj = [100.0 + i for i in range(len(days))]
        body = _chart(days, adj)
        (raw / f"{t}.json").write_bytes(body)
        fetch["tickers"][t] = {"sha256": hashlib.sha256(body).hexdigest()}
        b = adj[days.index(dt.date(2024, 12, 31))]
        (cutd / f"{t}.csv").write_text(f"date,adjclose,volume\n2024-12-30,99.0,5\n2024-12-31,{b},5\n")
    (raw / "fetch.json").write_text(json.dumps(fetch))
    d, P, V = EG.make_holdout(raw, ["SPY", "E00"], last, cutd)
    assert d == sessions(dt.date(2025, 1, 2), last) and P.shape == (len(d), 2)
    # a boundary close that differs from the cut's, as text
    (cutd / "E00.csv").write_text("date,adjclose,volume\n2024-12-31,1.0,5\n")
    with pytest.raises(EG.GradingRefused, match="2024-12-31"):
        EG.make_holdout(raw, ["SPY", "E00"], last, cutd)
    # a missing holdout session
    short = [x for x in days if x != dt.date(2025, 1, 6)]
    body = _chart(short, [100.0 + i for i in range(len(short))])
    (raw / "SPY.json").write_bytes(body)
    fetch["tickers"]["SPY"]["sha256"] = hashlib.sha256(body).hexdigest()
    (raw / "fetch.json").write_text(json.dumps(fetch))
    b = 100.0 + short.index(dt.date(2024, 12, 31))
    (cutd / "SPY.csv").write_text(f"date,adjclose,volume\n2024-12-31,{b},5\n")
    with pytest.raises(EG.GradingRefused, match="missing or null"):
        EG.make_holdout(raw, ["SPY"], last, cutd)


def test_refuses_until_registrations_are_set(monkeypatch):
    assert EG.CELL == "00c7af167f8ddb9a4874cc29b438926112360fb9"      # the cell, live
    bad = EG.refusals("0" * 40)
    assert any("GRADING" in b and "not live" in b for b in bad)          # the panel's grading: not yet
    monkeypatch.setattr(EG, "CELL", None)
    assert any("CELL" in b and "not live" in b for b in EG.refusals("0" * 40))
    assert EG.PANEL == "310225cd4932bc18e1c8e2e248cbbb133124a004"


def test_the_grading_takes_240_submissions(world):
    """Amendment 2: 120 per arm. The grader prices and bootstraps 240 submissions plus the objects
    and the three books, held against each submission's own priced unweighted L90."""
    sups = [((0, 1.0), (3, -1.0)), ((1, 1.0),), ((2, -1.0), (5, 1.0)), ((7, 1.0), (9, 1.0), (11, -1.0))]
    panel_in, _ = ER.sancho_inputs(world["dates_in"], world["tickers"], world["P_in"], world["V_in"], 2)
    idx = ER.scored_index(panel_in)
    S = {}
    for sup in sups:
        _, s = FG.member_book(panel_in, sup)
        S[sup] = (EG.sharpe(s[idx], 252.0), FG.wsharpe(s[idx]))
    subs, priced = [], []
    for i in range(240):
        arm = "A" if i % 2 == 0 else "B"
        if i % 5 == 0:
            subs.append({"session": f"s{i}", "arm": arm, "kind": "baseline_model", "support": "baseline_model",
                         "predict": {"mean": 0.2, "sd": 0.5}})
            priced.append({"session": f"s{i}", "S": 0.45, "S_w": 0.5, "L90": -0.2, "L90_w2": -0.1})
        else:
            sup = sups[i % 4]
            su, sw = S[sup]
            subs.append({"session": f"s{i}", "arm": arm, "kind": "rule", "support": [list(x) for x in sup],
                         "predict": {"mean": 0.2, "sd": 0.5}})
            priced.append({"session": f"s{i}", "S": su, "S_w": sw, "L90": su - 1.0, "L90_w2": sw - 1.2})
    w = dict(world, submissions={"sessions": 240, "no_submit": [], "submissions": subs}, priced={"priced": priced})
    g = EG.grade(**w, workers=1, fit_fn=_fit_memo, B_=40)
    kinds = [i["type"] for i in g["items"]]
    assert kinds.count("submission") == 240 and kinds.count("object") == 3 and kinds.count("book") == 3
    assert g["bootstrap"]["shape"] == [40, 246]
    for it in g["items"]:
        if it["type"] == "submission":
            assert it["held"] == (it["realized"] >= it["L90"])
