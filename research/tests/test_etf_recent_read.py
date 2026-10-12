"""The ETF recent panel's in-sample read end to end on a SYNTHETIC cut (never real data): the
cut record's refusals, the loader's refusals, the panel against `build_etf_panel`, pins.json
before the fits, the repeat, the two W2 streams with the unweighted and 10 bps lines beside,
the class with both best members; the runner refuses on the laptop."""
import datetime as dt
import hashlib
import json

import numpy as np
import pytest

from experiments import etf_recent_read as ER

M, T = 30, 1600
DROP, SCORE0 = 100, 1250          # synthetic stand-ins for 2010-01-04 and 2015-01-02 (row indices)


def _synthetic(seed=721150):
    rng = np.random.default_rng(seed)
    f = 0.008 * rng.standard_normal(T)
    R = f[:, None] + 0.008 * rng.standard_normal((T, M))
    P = 50.0 * np.cumprod(1.0 + R, axis=0)
    Vol = np.exp(rng.normal(13.0, 0.5, (T, M)))
    days = np.busday_offset("2005-01-03", np.arange(T), roll="forward")
    dates = [dt.date.fromisoformat(str(d)) for d in days]
    tickers = ["SPY"] + [f"E{j:02d}" for j in range(M - 1)]
    return dates, tickers, P, Vol


def _write_cut(root, dates, tickers, P, Vol, n_included=None, poison_before=None):
    """`poison_before`: rows dated before it hold non-numeric text, so a parse of any of them fails."""
    d = root / "insample"
    d.mkdir(parents=True, exist_ok=True)
    sha = {}
    for j, t in enumerate(tickers):
        p = d / f"{t}.csv"
        p.write_text("date,adjclose,volume\n" + "".join(
            (f"{day.isoformat()},POISON,POISON\n" if poison_before and day < poison_before else
             f"{day.isoformat()},{float(P[i, j])!r},{float(Vol[i, j])!r}\n") for i, day in enumerate(dates)))
        sha[t] = hashlib.sha256(p.read_bytes()).hexdigest()
    rec = {"registration": ER.REGISTRATION, "last_fetched_session": "2026-10-09", "included": list(tickers),
           "n_included": len(tickers) if n_included is None else n_included, "csv_sha256": sha,
           "combined_sha256": ER.combined_sha(sha, tickers), "rows": {t: len(dates) for t in tickers}}
    (root / "insample.cut.json").write_text(json.dumps(rec, indent=1))
    return root / "insample.cut.json"


@pytest.fixture(scope="module")
def synth():
    return _synthetic()


def test_the_panel_is_build_etf_panel_at_d1(synth, tmp_path):
    from environments.real_panel import build_etf_panel
    dates, tickers, P, Vol = synth
    _write_cut(tmp_path, dates, tickers, P, Vol)
    ref = build_etf_panel(tmp_path / "insample")
    loaded = ER.load({t: tmp_path / "insample" / f"{t}.csv" for t in tickers}, last=dates[-1])
    panel, blk = ER.etf_panel(*loaded, lag=2)
    assert panel.assets == ref.assets and panel.feature_names == ref.feature_names
    for f in ("features", "returns", "cost_rate", "borrow_rate"):
        assert np.array_equal(getattr(panel, f), getattr(ref, f), equal_nan=True), f
    assert panel.meta["dates"] == ref.meta["dates"] and panel.meta["delay"] == 1
    p0, b0 = ER.etf_panel(*loaded, lag=1)
    assert p0.features.shape[0] == panel.features.shape[0] + 1 and p0.meta["delay"] == 0
    assert np.array_equal(p0.features[:-1], panel.features)          # the same signal rows
    assert np.allclose(p0.returns[1:], panel.returns)                # d = 0 earns one row earlier
    assert blk["X"].shape[:2] == panel.features.shape[:2] and blk["V"].shape[0] == blk["G"].shape[0]


def test_the_cut_record_refusals(synth, tmp_path):
    dates, tickers, P, Vol = synth
    cut = _write_cut(tmp_path / "ok", dates, tickers, P, Vol)
    assert ER.check_cut(cut)[1] == []
    rec = json.loads(cut.read_text())
    good = rec["combined_sha256"]
    rec["combined_sha256"] = "0" * 64
    cut.write_text(json.dumps(rec))
    assert any("combined" in b for b in ER.check_cut(cut)[1])
    rec["combined_sha256"] = good
    cut.write_text(json.dumps(rec))
    (tmp_path / "ok" / "insample" / "E03.csv").write_text("date,adjclose,volume\n")
    assert any("E03.csv" in b for b in ER.check_cut(cut)[1])
    few = _write_cut(tmp_path / "few", dates, tickers[:29], P[:, :29], Vol[:, :29])
    assert any("fewer than 30" in b and "ask the author" in b for b in ER.check_cut(few)[1])
    nospy = _write_cut(tmp_path / "nospy", dates, tickers[1:] + ["E99"], P, Vol)
    assert any("SPY" in b for b in ER.check_cut(nospy)[1])


def test_the_loader_refuses_late_rows_gaps_and_mismatched_dates(tmp_path):
    a = tmp_path / "SPY.csv"
    a.write_text("date,adjclose,volume\n2005-01-03,10,5\n2025-01-02,11,5\n")
    with pytest.raises(SystemExit, match="after 2024-12-31"):
        ER.load({"SPY": a})
    b = tmp_path / "E00.csv"
    b.write_text("date,adjclose,volume\n2005-01-03,10,5\n2005-01-04,,5\n")
    with pytest.raises(SystemExit, match="missing value"):
        ER.load({"E00": b}, last=dt.date(2005, 1, 4))
    c = tmp_path / "E01.csv"
    c.write_text("date,adjclose,volume\n2005-01-03,10,5\n2005-01-04,11,5\n")
    d = tmp_path / "E02.csv"
    d.write_text("date,adjclose,volume\n2005-01-03,10,5\n2005-01-05,11,5\n")
    with pytest.raises(SystemExit, match="dates differ"):
        ER.load({"E01": c, "E02": d}, last=dt.date(2005, 1, 4))
    with pytest.raises(SystemExit, match="not 2005-01-03 .. 2024-12-31"):
        ER.load({"E01": c})


def test_the_read_end_to_end_on_a_synthetic_cut(synth, tmp_path, monkeypatch):
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from experiments import french_long_read as FL
    dates, tickers, P, Vol = synth
    cut = _write_cut(tmp_path / "cut", dates, tickers, P, Vol, poison_before=dates[DROP])
    monkeypatch.setattr(ER, "refusals", lambda head, wheel: [])
    monkeypatch.setattr(ER, "LAST_DATE", dates[-1])
    monkeypatch.setattr(ER, "USE_FROM", dates[DROP])
    monkeypatch.setattr(ER, "SCORE_FROM", dates[SCORE0])
    monkeypatch.setattr(ER, "SCORE_TO", dates[-1])
    monkeypatch.setattr(ER, "members", lambda: members_in_order(CLS, 40)[:128])
    monkeypatch.setattr(ER, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(FL, "B", 120)
    out = tmp_path / "run"
    rc = ER.main(["--cut", str(cut), "--out", str(out), "--expect-head", "x", "--wheel", "w", "--workers", "2"])
    assert rc == 0
    pins = json.loads((out / "pins.json").read_text())
    assert pins["combined_sha256"] == json.loads(cut.read_text())["combined_sha256"]
    assert pins["d0"]["X_shape"][0] == pins["d1"]["X_shape"][0] + 1 and len(pins["d1"]["v2_V_block_sha256"]) == 64
    # amendment 2: the first row used and the count dropped are pinned; the poisoned pre-cutoff rows
    # were never parsed, so none of them reached X or any fit
    assert pins["first_row_used"] == str(dates[DROP]) and pins["rows_dropped_before"]["count"] == DROP
    assert pins["rows"] == T - DROP and pins["d1"]["first_feature_date"] == str(dates[DROP + ER.WARM])
    sc = pins["d1"]["scored_rows"]
    assert sc["first_earned"] == str(dates[SCORE0]) and sc["last_earned"] == str(dates[-1])
    rec = json.loads((out / "results.json").read_text())
    assert rec["repeat_bit_identical"] == {"d1": True, "d0": True} and rec["cut"]["n_included"] == M
    t1, t2, t3 = rec["test1_stream_d1"], rec["test2_stream_d0"], rec["test3_class_d1"]
    assert t1["alphas"] == {"96%": 0.03, "90%": 0.06} and t2["alphas"] == {"96%": 0.01, "90%": 0.02}
    assert t3["alphas"] == {"96%": 0.01, "90%": 0.02}
    assert (t1["seed"], t2["seed"], t3["seed"]) == (721000, 721001, 721002)
    assert t1["first_scored_row"] == 763 and t2["first_scored_row"] == 762
    assert "NOT IMPLEMENTABLE" in t2["test"]
    for t in (t1, t2, rec["test3_class_d1"]):                       # every test on the scored window
        assert t["first_earned"] == str(dates[SCORE0]) and t["last_earned"] == str(dates[-1])
        assert t["n_rows"] == T - SCORE0
    assert rec["rows_dropped_before_2010"] == DROP
    # the agent cell's precompute: files, shapes, manifest hashes, values equal to results.json
    pdir = out / "precompute"
    man = json.loads((pdir / "manifest.json").read_text())
    assert rec["precompute"]["manifest_sha256"] == hashlib.sha256((pdir / "manifest.json").read_bytes()).hexdigest()
    for f, h in man["sha256"].items():
        assert hashlib.sha256((pdir / f).read_bytes()).hexdigest() == h, f
    assert man["registration"] == ER.REGISTRATION and man["git_head"] == "x"
    n_sc = T - SCORE0
    assert man["T_scored"] == n_sc and man["N"] == 128 and man["B"] == 120
    assert man["first_earned"] == str(dates[SCORE0]) and man["last_earned"] == str(dates[-1])
    sa = np.load(pdir / "sancho_d1.npz")
    assert sa["stream"].shape == (n_sc,) and sa["null_w2"].shape == (120,) and int(sa["seed"]) == 721000
    assert float(sa["S_w"]) == t1["weighted_W2"]["S"] and float(sa["S_unw"]) == t1["unweighted"]["S"]
    assert str(sa["earned_dates"][0]) == str(dates[SCORE0]) and float(sa["turnover_mean"]) > 0
    from estimator import recency as Rc
    assert np.isclose(Rc.weighted_sharpe(sa["stream"], Rc.weights(n_sc, 1260), 252.0), t1["weighted_W2"]["S"])
    cs = np.load(pdir / "class_stats.npz")
    G = np.load(pdir / "class_scored.npy", mmap_mode="r")
    assert G.shape == (128, n_sc) and cs["S_w"].shape == cs["S_unw"].shape == (128,)
    assert cs["null_w2_max"].shape == cs["null_unw_max"].shape == cs["null_unw_argmax"].shape == (120,)
    assert int(np.argmax(cs["S_w"])) == t3["weighted_W2"]["best_member"]["index"]
    assert float(cs["S_w"].max()) == t3["weighted_W2"]["S"] and float(cs["S_unw"].max()) == t3["unweighted"]["S"]
    j = t3["weighted_W2"]["best_member"]["index"]                      # row j is member j's scored stream
    assert np.isclose(Rc.weighted_sharpe(np.asarray(G[j]), Rc.weights(n_sc, 1260), 252.0), cs["S_w"][j])
    sd = np.asarray(G).std(axis=1, ddof=1)
    S_unw = np.where(sd > 0, np.asarray(G).mean(axis=1) / np.where(sd > 0, sd, 1.0), 0.0) * np.sqrt(252.0)
    assert np.allclose(S_unw, cs["S_unw"])
    assert np.all(cs["null_unw_argmax"] >= 0) and np.array_equal(cs["null_unw_S_at_argmax"], cs["null_unw_max"])
    p_unw = (1 + int(np.sum(cs["null_unw_max"] >= t3["unweighted"]["S"]))) / 121
    assert p_unw == t3["unweighted"]["p"]
    p_w = (1 + int(np.sum(cs["null_w2_max"] >= t3["weighted_W2"]["S"]))) / 121
    assert p_w == t3["weighted_W2"]["p"]
    assert cs["null_unw_undemeaned_argmax"].shape == cs["null_unw_undemeaned_S_at_argmax"].shape == (120,)
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    bcs = np.load(pdir / "base_columns.npy")
    pan, _ = ER.sancho_inputs(*ER.load_from(ER.check_cut(cut)[2], use_from=dates[DROP], last=dates[-1])[:4], lag=2)
    ref_bc = np.asarray(RealSandbox(pan, spec_class=CLS).base_feature_columns(), float)[ER.scored_index(pan)]
    assert bcs.shape == (n_sc, ref_bc.shape[1]) and np.array_equal(bcs, ref_bc)
    # the unweighted stream null (test 1's, seed 721000) and the joint class+model null (seed 721002)
    assert sa["null_unw"].shape == (120,)
    assert (1 + int(np.sum(sa["null_unw"] >= t1["unweighted"]["S"]))) / 121 == t1["unweighted"]["p"]
    jm = cs["joint_unw_max"]
    assert jm.shape == (120,) and np.all(jm >= cs["null_unw_max"])
    from estimator.bootstrap import stationary_bootstrap_indices
    rng = np.random.default_rng(721002)
    Cc = np.empty((n_sc, 120))
    for bb in range(120):
        Cc[:, bb] = np.bincount(stationary_bootstrap_indices(n_sc, t3["block_length"], rng), minlength=n_sc)
    x0 = sa["stream"] - sa["stream"].mean()
    for bb in (0, 5, 37, 119):
        m = (x0 @ Cc[:, bb]) / n_sc
        v = ((x0 * x0) @ Cc[:, bb] - n_sc * m * m) / (n_sc - 1)
        mrep = (m / np.sqrt(v) if v > 0 else 0.0) * np.sqrt(252.0)
        assert np.isclose(jm[bb], max(cs["null_unw_max"][bb], mrep), rtol=0, atol=1e-12)
    for t in (t1, t2, t3):
        assert 0 < t["weighted_W2"]["p"] <= 1 and t["unweighted"]["label"] == FL.UNWEIGHTED_LABEL
    assert "cost_10bps_beside" in t1 and set(t1["performance_line"]["lines"]) == {"252", "756"}
    assert t3["N"] == 128 and t3["weighted_W2"]["best_member"]["features"] and t3["unweighted"]["best_member"]
    with pytest.raises(SystemExit, match="runs once"):
        ER.main(["--cut", str(cut), "--out", str(out), "--expect-head", "x", "--wheel", "w"])


def test_the_registration_is_set_and_the_laptop_is_refused():
    assert ER.REGISTRATION == "310225cd4932bc18e1c8e2e248cbbb133124a004"
    bad = ER.refusals("0" * 40, None)
    assert any("Linux" in b for b in bad) and any("--expect-head" in b for b in bad)
    assert not any("not an ancestor" in b for b in bad)


def test_rows_before_the_cutoff_are_never_parsed_and_x_ignores_them(synth, tmp_path, monkeypatch):
    """Amendment 2: a file whose pre-cutoff rows are poisoned loads to the same arrays, and builds the
    same X, as a clean file; the cutoff, not the data, decides what enters."""
    dates, tickers, P, Vol = synth
    monkeypatch.setattr(ER, "LAST_DATE", dates[-1])
    clean = _write_cut(tmp_path / "clean", dates, tickers, P, Vol)
    pois = _write_cut(tmp_path / "pois", dates, tickers, P, Vol, poison_before=dates[DROP])
    a = ER.load_from(ER.check_cut(clean)[2], use_from=dates[DROP], last=dates[-1])
    b = ER.load_from(ER.check_cut(pois)[2], use_from=dates[DROP], last=dates[-1])
    assert a[0] == b[0] and a[0][0] == dates[DROP] and a[4] == b[4] == DROP
    assert np.array_equal(a[2], b[2]) and np.array_equal(a[3], b[3])
    pa, _ = ER.etf_panel(*a[:4], lag=2)
    pb, _ = ER.etf_panel(*b[:4], lag=2)
    assert np.array_equal(pa.features, pb.features, equal_nan=True)
    assert pa.meta["dates"][0] == dates[DROP + ER.WARM]
    with pytest.raises(ValueError):                              # the poison would fail any parse
        ER.load_from(ER.check_cut(pois)[2], use_from=dates[0], last=dates[-1])


def test_price_class_argmax_equals_french_price_class(synth, tmp_path):
    """The precompute's unweighted class pricing is `french_insample_read.price_class`, arithmetic
    unchanged: the same S, p, L90 and best member, plus each replicate's argmax, which attains it."""
    import environments.planted_fast as pf
    from environments.class_table import members_in_order
    from environments.planted_panel import CLS
    from environments.real_sandbox import RealSandbox
    from experiments import french_insample_read as FR
    dates, tickers, P, Vol = synth
    panel, _ = ER.etf_panel(dates, tickers, P, Vol, lag=2)
    members = members_in_order(CLS, 40)[:96]
    cache = pf.build(panel, members, name="argmax-test", cache_dir=tmp_path / "c")
    bc = np.asarray(RealSandbox(panel, spec_class=CLS).base_feature_columns(), float)
    ref = FR.price_class(panel, cache, bc, 721002, 80, 0.01, panel.feature_names)
    store = np.zeros((cache.N, panel.features.shape[0]))
    got = ER.price_class_argmax(panel, cache, bc, 721002, 80, 0.01, panel.feature_names, store=store)
    for k in ("S", "p", "L90", "block_length", "certified"):
        assert got[k] == ref[k], k
    assert got["best_member"] == ref["best_member"]
    M, arg = got["_null_max"], got["_argmax"]
    assert np.all((arg >= 0) & (arg < cache.N))
    F = pf.feature_returns(panel)
    assert np.array_equal(store, pf.streams(cache, F, 0, cache.N))
    assert np.allclose(got["_S_all"], pf._sharpe_rows(store, np.sqrt(252.0)))
    # EB's un-demeaned replicate argmax, recomputed directly from the stored streams and the same C
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    T = store.shape[1]
    L = int(select_block_length(bc - bc.mean(axis=0)))
    rng = np.random.default_rng(721002)
    C = np.empty((T, 80))
    for b in range(80):
        C[:, b] = np.bincount(stationary_bootstrap_indices(T, L, rng), minlength=T)
    for b in (0, 7, 41, 79):
        m = (store @ C[:, b]) / T
        v = ((store * store) @ C[:, b] - T * m * m) / (T - 1)
        sb = np.where(v > 0, m / np.sqrt(np.where(v > 0, v, 1.0)), 0.0) * np.sqrt(252.0)
        assert int(np.argmax(sb)) == int(got["_u_argmax"][b])
        assert np.isclose(sb.max(), got["_u_max"][b])
