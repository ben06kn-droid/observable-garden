"""`experiments/grade_real.py` for 6.5 holdout grading (`prereg/holdout-grading.md`), on synthetic prices.

One feature build over in-sample and holdout; the grade over the earned-return window;
and every refusal: platform, grading commit and clean tree, sealed submissions,
the submissions hash, the manifest hashes, overlapping or mismatched inputs.
"""
import datetime as dt
import hashlib
import json
import subprocess

import numpy as np
import pytest

from experiments import grade_real as gr

TICKERS = ("SPY", "AAA", "BBB", "CCC", "DDD", "EEE")


def _bdays(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def prices():
    rng = np.random.default_rng(7)
    days = _bdays(dt.date(2020, 1, 1), 1000)          # 2020 .. mid-2023
    return {t: (days, 100 * np.exp(np.cumsum(rng.normal(0.0002, 0.012, len(days)))))
            for t in TICKERS}


def _write(dirpath, prices, keep):
    dirpath.mkdir(parents=True, exist_ok=True)
    for t, (days, px) in prices.items():
        rows = [f"{d},{float(p)!r},1000\n" for d, p in zip(days, px) if keep(d)]
        (dirpath / f"{t}.csv").write_text("date,adjclose,volume\n" + "".join(rows))
    return dirpath


@pytest.fixture
def split(tmp_path, prices):
    ins = _write(tmp_path / "insample", prices, lambda d: d < dt.date(2023, 1, 1))
    ho = _write(tmp_path / "holdout", prices, lambda d: d >= dt.date(2023, 1, 1))
    return ins, ho


def test_the_span_build_is_build_etf_panels_computation(tmp_path, prices):
    from environments.real_panel import build_etf_panel
    ins = _write(tmp_path / "ins_only", prices, lambda d: d < dt.date(2023, 1, 1))
    panel = build_etf_panel(ins)
    from data.etf_loader import load_panel
    dates, tickers, F, earn = gr.build_span(
        {t: (v[0], np.asarray(v[1])) for t, v in load_panel(ins).items()})
    T = len(dates)
    assert np.array_equal(F[gr.WARM:T - 2], panel.features, equal_nan=True)
    assert np.array_equal(np.nan_to_num(earn[gr.WARM:T - 2]), panel.returns)
    assert list(dates[gr.WARM:T - 2]) == list(panel.meta["dates"])


def test_grading_the_in_sample_window_reproduces_the_class_tables_streams(tmp_path, prices):
    """The execution, costs and borrow are the panel's own: over the panel's periods the
    net Sharpe at 5 bps equals `streams_for`'s, the stream every evaluate sees."""
    from environments.class_table import streams_for
    from environments.real_panel import build_etf_panel
    from data.etf_loader import load_panel
    ins = _write(tmp_path / "ins_only", prices, lambda d: d < dt.date(2023, 1, 1))
    panel = build_etf_panel(ins)
    dates, _, F, earn = gr.build_span(
        {t: (v[0], np.asarray(v[1])) for t, v in load_panel(ins).items()})
    T = len(dates)
    for sup in (((0, 1.0),), ((3, 1.0), (17, -1.0)), ((5, -1.0), (22, 1.0), (31, 1.0))):
        w = np.zeros(40)
        for k, s in sup:
            w[k] = s
        rows = gr.grade_span([{"name": "x", "weights": w.tolist()}], dates, F, earn,
                             dates[gr.WARM + 2], dates[T - 1])
        s = streams_for(panel, [sup])[0]
        ref = s.mean() / s.std(ddof=1) * np.sqrt(252)
        assert rows[0]["net_sharpe_5bps"] == pytest.approx(ref, abs=1e-10)
        assert rows[0]["n_periods"] == len(s)


def test_the_holdout_window_grades_only_holdout_returns_with_a_continuous_book(split, prices):
    ins, ho = split
    w = np.zeros(40); w[0] = 1.0
    rows, meta = gr.grade([{"name": "s", "weights": w.tolist()}], ins, ho)
    days = prices["SPY"][0]
    n_ho = sum(d >= dt.date(2023, 1, 1) for d in days)
    assert rows[0]["n_periods"] == n_ho              # every holdout day earns, none other
    assert rows[0]["first_earned"] >= "2023-01-01"
    assert meta["span"][0] < "2023-01-01" < meta["span"][1]     # one build over both
    assert rows[0]["net_sharpe_10bps"] <= rows[0]["net_sharpe_5bps"] <= rows[0]["gross_sharpe"] + 1e-12
    # the same build over the unsplit series gives the same grade
    dates, _, F, earn = gr.build_span(prices)
    again = gr.grade_span([{"name": "s", "weights": w.tolist()}], dates, F, earn,
                          gr.GRADE_START, gr.GRADE_END)
    assert again[0]["net_sharpe_5bps"] == pytest.approx(rows[0]["net_sharpe_5bps"], abs=1e-12)


def test_mismatched_or_overlapping_inputs_are_refused(tmp_path, prices):
    ins = _write(tmp_path / "i", prices, lambda d: d < dt.date(2023, 1, 1))
    ho = _write(tmp_path / "h", prices, lambda d: d >= dt.date(2022, 12, 1))
    with pytest.raises(gr.GradingRefused, match="overlap"):
        gr.load_span(ins, ho)
    (ho / "EEE.csv").unlink()
    with pytest.raises(gr.GradingRefused, match="tickers differ"):
        gr.load_span(ins, ho)


def test_the_platform_pin_refuses_any_other_platform():
    assert gr.require_platform(gr.platform_now()) == gr.platform_now()
    with pytest.raises(gr.GradingRefused, match="not the pinned"):
        gr.require_platform(("Plan9", "mips"))
    assert gr.PINNED_PLATFORM == ("Linux", "x86_64")


def test_the_manifest_and_submissions_hashes_refuse_a_changed_input(split):
    ins, ho = split
    man = {"derived": {}}
    for t in TICKERS:
        man["derived"][t] = {"insample": {"sha256": gr.sha256_file(ins / f"{t}.csv")},
                             "holdout": {"sha256": gr.sha256_file(ho / f"{t}.csv")}}
    assert gr.require_manifest_hashes(ins, "insample", man) == len(TICKERS)
    assert gr.require_manifest_hashes(ho, "holdout", man) == len(TICKERS)
    (ho / "AAA.csv").write_text((ho / "AAA.csv").read_text() + "2025-12-31,1.0,1\n")
    with pytest.raises(gr.GradingRefused, match="differ from the manifest's hash"):
        gr.require_manifest_hashes(ho, "holdout", man)
    (ins / "BBB.csv").unlink()
    with pytest.raises(gr.GradingRefused, match="missing"):
        gr.require_manifest_hashes(ins, "insample", man)
    subs = ins.parent / "subs.json"
    subs.write_text("[]")
    gr.require_file_hash(subs, hashlib.sha256(b"[]").hexdigest(), "submissions file")
    with pytest.raises(gr.GradingRefused, match="not the recorded"):
        gr.require_file_hash(subs, "0" * 64, "submissions file")


def _repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    run = lambda *a: subprocess.run(["git", "-C", str(r), *a], check=True, capture_output=True)
    run("init", "-q")
    run("config", "user.email", "t@example.com")
    run("config", "user.name", "t")
    (r / "a.txt").write_text("a")
    run("add", "a.txt")
    run("commit", "-q", "-m", "S")
    s = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True,
                       text=True).stdout.strip()
    (r / "b.txt").write_text("b")
    run("add", "b.txt")
    run("commit", "-q", "-m", "G")
    g = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True,
                       text=True).stdout.strip()
    return r, s, g


def test_the_grading_commit_and_the_sealed_commit_guards(tmp_path):
    r, s, g = _repo(tmp_path)
    assert gr.require_grading_commit(g, r) == g
    with pytest.raises(gr.GradingRefused, match="not the recorded grading commit"):
        gr.require_grading_commit(s, r)
    gr.require_sealed_submissions(s, r)
    with pytest.raises(gr.GradingRefused, match="not in this repository"):
        gr.require_sealed_submissions("0" * 40, r)
    (r / "a.txt").write_text("changed")
    with pytest.raises(gr.GradingRefused, match="dirty"):
        gr.require_grading_commit(g, r)


def test_main_writes_grades_without_printing_any(tmp_path, split, monkeypatch, capsys):
    ins, ho = split
    r, s, g = _repo(tmp_path)
    monkeypatch.setattr(gr, "REPO", r)
    monkeypatch.setattr(gr, "PINNED_PLATFORM", gr.platform_now())
    man = {"derived": {t: {"insample": {"sha256": gr.sha256_file(ins / f"{t}.csv")},
                           "holdout": {"sha256": gr.sha256_file(ho / f"{t}.csv")}}
                       for t in TICKERS}}
    (tmp_path / "man.json").write_text(json.dumps(man))
    w = np.zeros(40); w[1] = 1.0
    subs = tmp_path / "subs.json"
    subs.write_text(json.dumps([{"name": "s", "weights": w.tolist()}]))
    out = tmp_path / "grades.json"
    assert gr.main(["--insample", str(ins), "--holdout", str(ho), "--submissions", str(subs),
                    "--submissions-sha256", gr.sha256_file(subs), "--sealed-commit", s,
                    "--grading-commit", g, "--manifest", str(tmp_path / "man.json"),
                    "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    d = json.loads(out.read_text())
    assert "sharpe" not in printed.lower() and "unread" in printed
    assert d["grades"][0]["n_periods"] > 0 and len(d["feature_matrix_sha256"]) == 64
    assert d["platform"] == list(gr.platform_now()) and d["grading_commit"] == g


def test_the_streams_are_the_graded_days_and_reproduce_every_sharpe(split):
    ins, ho = split
    w = np.zeros(40); w[2] = 1.0; w[9] = -1.0
    rows, meta = gr.grade([{"name": "s", "weights": w.tolist()}], ins, ho)
    r = rows[0]
    st = r["stream"]
    assert set(st) == {"gross", "net_5bps", "net_10bps"}
    assert len(meta["graded_dates"]) == r["n_periods"] == len(st["gross"])
    assert meta["graded_dates"][0] == r["first_earned"] and meta["graded_dates"][-1] == r["last_earned"]
    for key, sk in (("gross_sharpe", "gross"), ("net_sharpe_5bps", "net_5bps"),
                    ("net_sharpe_10bps", "net_10bps")):
        x = np.asarray(st[sk])
        assert x.mean() / x.std(ddof=1) * np.sqrt(252) == pytest.approx(r[key], abs=1e-12)
    g, n5, n10 = (np.asarray(st[k]) for k in ("gross", "net_5bps", "net_10bps"))
    assert np.all(n10 <= n5 + 1e-15) and np.all(n5 <= g + 1e-15)     # costs only subtract
    turn5 = n5 - n10                         # the extra 5 bps of turnover cost
    assert np.all(turn5 >= -1e-15)
    assert np.all((g - n5) - turn5 >= -1e-15)   # gross - net_5 = the same cost + borrow


def _score_runs(repo, ins, entries):
    """Synthetic run files in <repo>/runs/etf_replay: (name, support, stored score or None
    for 'the true score', offset)."""
    from environments.real_panel import build_etf_panel
    from quixote.grammar import weights as gw
    panel = build_etf_panel(ins)
    d = repo / "runs" / "etf_replay"
    d.mkdir(parents=True, exist_ok=True)
    for i, (name, sup, off) in enumerate(entries):
        w = [float(v) for v in gw(tuple((int(k), float(v)) for k, v in sup), 40)]
        true = gr.panel_net_scores(panel, {name: w})[name]
        (d / f"cell_etf_{i}_replay_{i}.json").write_text(json.dumps(
            {"run_id": name, "submitted_support": sup, "submitted_sharpe": true + off}))


def _preflight_args(tmp_path, ins, ho, s, g):
    man = {"derived": {t: {"insample": {"sha256": gr.sha256_file(ins / f"{t}.csv")},
                           "holdout": {"sha256": gr.sha256_file(ho / f"{t}.csv")}}
                       for t in TICKERS}}
    (tmp_path / "man.json").write_text(json.dumps(man))
    subs = tmp_path / "subs.json"
    subs.write_text("[]")
    return ["--insample", str(ins), "--holdout", str(ho), "--submissions", str(subs),
            "--submissions-sha256", gr.sha256_file(subs), "--sealed-commit", s,
            "--grading-commit", g, "--manifest", str(tmp_path / "man.json"), "--preflight"]


def test_preflight_runs_every_guard_reproduces_in_sample_and_reads_no_holdout_price(
        tmp_path, split, monkeypatch, capsys):
    ins, ho = split
    r, s, g = _repo(tmp_path)
    monkeypatch.setattr(gr, "REPO", r)
    monkeypatch.setattr(gr, "PINNED_PLATFORM", gr.platform_now())
    _score_runs(r, ins, [("a", [[2, 1.0]], 0.0), ("b", [[5, 1.0], [9, -1.0]], 0.0),
                         ("tie", [[1, 1.0], [6, 1.0]], 0.05)])       # ret1_rank, off by 0.05
    called = []
    monkeypatch.setattr(gr, "load_span", lambda *a: called.append("load") or {})
    monkeypatch.setattr(gr, "load_holdout", lambda *a: called.append("holdout") or {})
    args = _preflight_args(tmp_path, ins, ho, s, g)
    assert gr.main(args) == 0
    out = capsys.readouterr().out
    assert called == [], "preflight must not load any holdout price"
    assert "in-sample reproduction: 2 compared" in out
    assert "tie-affected reported separately: {'tie': " in out
    res = gr.run_grading(ins, ho, tmp_path / "subs.json", gr.sha256_file(tmp_path / "subs.json"),
                         s, g, tmp_path / "man.json", None, repo=r, preflight=True)
    assert res["reproduction"]["compared"] == 2
    assert res["reproduction"]["tie_affected"]["tie"] == pytest.approx(0.05, abs=1e-9)
    assert res["reproduction"]["max_diff"] <= gr.REPRO_TOL
    assert "versions: python" in out and "numpy" in out and "pandas" in out and "scipy" in out
    assert out.strip().endswith("nothing was graded") and "PREFLIGHT ok" in out
    # a guard that fails still refuses under preflight
    bad = list(args)
    bad[bad.index("--submissions-sha256") + 1] = "0" * 64
    with pytest.raises(gr.GradingRefused, match="not the recorded"):
        gr.main(bad)


def test_preflight_refuses_when_an_ordinary_score_does_not_reproduce(tmp_path, split, monkeypatch):
    ins, ho = split
    r, s, g = _repo(tmp_path)
    monkeypatch.setattr(gr, "REPO", r)
    monkeypatch.setattr(gr, "PINNED_PLATFORM", gr.platform_now())
    _score_runs(r, ins, [("a", [[2, 1.0]], 0.0), ("b", [[5, 1.0]], 2e-9)])
    with pytest.raises(gr.GradingRefused, match="in-sample reproduction failed: b"):
        gr.main(_preflight_args(tmp_path, ins, ho, s, g))


def test_preflight_refuses_with_no_stored_score_to_compare(tmp_path, split, monkeypatch):
    ins, ho = split
    r, s, g = _repo(tmp_path)
    monkeypatch.setattr(gr, "REPO", r)
    monkeypatch.setattr(gr, "PINNED_PLATFORM", gr.platform_now())
    with pytest.raises(gr.GradingRefused, match="nothing to compare"):
        gr.main(_preflight_args(tmp_path, ins, ho, s, g))


def test_panel_net_scores_is_the_class_tables_stream_sharpe(tmp_path, prices):
    from environments.class_table import streams_for
    from environments.real_panel import build_etf_panel
    from quixote.grammar import weights as gw
    ins = _write(tmp_path / "ins_only", prices, lambda d: d < dt.date(2023, 1, 1))
    panel = build_etf_panel(ins)
    sup = ((3, 1.0), (17, -1.0))
    got = gr.panel_net_scores(panel, {"x": [float(v) for v in gw(sup, 40)]})["x"]
    st = streams_for(panel, [sup])[0]
    assert got == pytest.approx(st.mean() / st.std(ddof=1) * np.sqrt(252), abs=1e-12)
