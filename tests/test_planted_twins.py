"""The scripted twin cell's driver (`experiments/planted_twins.py`), small synthetic panel."""
import json

import numpy as np
import pytest

from environments import planted_panel as pp
from environments.class_table import streams_for
from experiments import planted_twins as tw
from tests.test_planted_panel import _panel


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


def test_the_real_matrix_gives_the_sandboxs_streams(base):
    d = pp.make_draw(base, 3, 1.0)
    sups = base.members[:30]
    R = np.stack([d.in_sample.returns, d.in_sample.returns[::-1]], axis=2)
    X = tw.streams_multi(d.in_sample, sups, R)
    np.testing.assert_allclose(X[0], streams_for(d.in_sample, sups), rtol=0, atol=1e-15)


def test_a_twin_keeps_every_members_cost_path(base):
    """Positions depend on X alone, so with zero returns every matrix gives the same
    stream: minus cost and borrow, identically."""
    d = pp.make_draw(base, 4, 1.0)
    sups = base.members[:30]
    Z = np.zeros(d.in_sample.returns.shape + (3,))
    X = tw.streams_multi(d.in_sample, sups, Z)
    assert np.array_equal(X[0], X[1]) and np.array_equal(X[0], X[2])
    assert (X[0] <= 0).all()


def test_a_level_gives_registered_rank_p_values(base, monkeypatch):
    monkeypatch.setattr(tw, "CHUNK", 512)
    r = tw.run_level(base, 5, 0.0, B=30)
    assert len(r["block_lengths"]) == 1 + 2 * tw.K
    attainable = {k / 20 for k in range(1, 21)}
    for s in r["searchers"]:
        for c in tw.CONSTRUCTIONS:
            assert min(abs(s[f"p_twin_{c}"] - a) for a in attainable) < 1e-12
            assert 0 <= s[f"ties_{c}"] <= tw.K
        assert s["truth_in_sample"] < 0                 # level 0 is a null for every member


def test_the_smoke_record_carries_no_rule_quantity(base, monkeypatch):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    for cell in ("prank", "score"):
        text = json.dumps(tw.cost_only(tw.run_seed((985000, [0.0, 1.0], 20, cell))))
        for word in ("p_twin", "p_class", "p_score", "score_real", "truth", "support",
                     "ties", "autocorr"):
            assert word not in text, word


def test_the_score_rank_is_the_registered_form_with_ties_against_the_real_run():
    assert tw.score_rank_p(1.0, [0.5] * 19) == 1 / 20
    assert tw.score_rank_p(1.0, [1.0] + [0.5] * 18) == 2 / 20       # a tie counts against
    assert tw.score_rank_p(0.0, [1.0] * 19) == 1.0


def test_a_score_level_ranks_every_searcher_under_both_constructions(base):
    r = tw.run_level_score(base, 6, 0.0)
    attainable = {k / 20 for k in range(1, 21)}
    for s in r["searchers"]:
        for c in tw.CONSTRUCTIONS:
            assert min(abs(s[f"p_score_{c}"] - a) for a in attainable) < 1e-12
        assert s["truth_in_sample"] < 0


def test_the_multi_cache_scores_equal_the_sandboxs_sharpe(base):
    from experiments.planted_edge import _sharpe_rows
    d = pp.make_draw(base, 7, 1.0)
    R = np.stack([d.in_sample.returns, d.in_sample.returns[::-1]], axis=2)
    ann = np.sqrt(d.in_sample.periods_per_year)
    cache = tw.MultiCache(d.in_sample, R, ann)
    sup = base.members[40]
    direct = _sharpe_rows(streams_for(d.in_sample, [sup, sup]), ann)[0]
    assert cache.get(sup)[0] == pytest.approx(direct, abs=1e-12)


def test_the_score_cell_refuses_a_level_other_than_its_fixed_two():
    with pytest.raises(SystemExit, match="fixed at 0 and 1.0"):
        tw.main(["--cell", "score", "--planted", "0.5", "--smoke", "1"])


def test_an_empty_real_submission_is_recorded_and_never_rejects(base, monkeypatch):
    """The empty-support guard: no support, no truth, and p = 1 under both
    constructions, whatever the twins scored."""
    from searchers.meta_adaptive import Trace

    class Empty:
        name = "empty"

        def _search(self, K, single, support_score, **kw):
            single(0)                                     # it looks, and finds nothing
            return Trace(support=(), score=float("-inf"))

    monkeypatch.setattr(tw, "_searchers", lambda seed, T, ppy: [Empty()])
    r = tw.run_level_score(base, 9, 1.0)
    (s,) = r["searchers"]
    assert s["support"] is None and s["truth_in_sample"] is None
    for c in tw.CONSTRUCTIONS:
        assert s[f"p_score_{c}"] == 1.0


def test_the_score_cell_records_the_signed_singles_lag1_autocorrelation(base):
    r = tw.run_level_score(base, 10, 0.0)
    v = r["median_lag1_autocorr_signed_singles"]
    assert -1.0 <= v <= 1.0
    d = pp.make_draw(base, 10, 0.0)
    assert v == tw.median_lag1_signed_singles(d.in_sample)
    # and it is NOT the cost record's: no rule quantity, but a property of the panel
    assert "autocorr" not in json.dumps(tw.cost_only(
        {"seed": 1, "cell": "score", "secs": 1.0, "cpu_secs": 1.0, "peak_rss_mb": 1.0,
         "levels": [{"secs": {}, "prefix_batches": 1}]}))


def test_resume_drops_a_truncated_last_line_and_keeps_the_file_appendable(tmp_path):
    f = tmp_path / "draws.jsonl"
    f.write_text('{"seed": 1}\n{"seed": 2}\n{"seed": 3, "lev')
    assert tw.load_done(f) == {1, 2}
    assert f.read_text() == '{"seed": 1}\n{"seed": 2}\n'
    with open(f, "a") as fh:
        fh.write('{"seed": 3}\n')
    assert tw.load_done(f) == {1, 2, 3}


def test_resume_refuses_a_malformed_line_that_is_not_the_last(tmp_path):
    f = tmp_path / "draws.jsonl"
    f.write_text('{"seed": 1}\n{"se\n{"seed": 3}\n')
    with pytest.raises(SystemExit, match="corruption"):
        tw.load_done(f)


def test_an_empty_twin_submission_never_counts_against_the_real_run(base, monkeypatch):
    """A twin whose search submits nothing scores -inf, which is never >= a real
    run's finite score: so it never raises the real run's p."""
    assert tw.score_rank_p(0.3, [float("-inf")] * 19) == 1 / 20
    assert tw.score_rank_p(-5.0, [float("-inf")] * 19) == 1 / 20

    from searchers.meta_adaptive import Trace
    first = {}

    class EmptyOnTwins:
        """Searches the real panel (the first matrix it sees) normally, and submits
        nothing on every twin."""
        name = "empty-on-twins"

        def _search(self, K, single, support_score, **kw):
            v = single(0)
            first.setdefault("v", v)
            if v != first["v"]:
                return Trace(support=(), score=float("-inf"))
            return Trace(support=((0, 1.0),), score=v)

    monkeypatch.setattr(tw, "_searchers", lambda seed, T, ppy: [EmptyOnTwins()])
    r = tw.run_level_score(base, 11, 1.0)
    (s,) = r["searchers"]
    assert s["support"] == [[0, 1.0]]
    for c in tw.CONSTRUCTIONS:
        assert s[f"p_score_{c}"] == 1 / 20 and s[f"ties_{c}"] == 0


def test_every_record_carries_its_platform(base, monkeypatch):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    rec = tw.run_seed((985000, [0.0], 10, "score"))
    for r in (rec, tw.cost_only(rec)):
        assert set(r["platform"]) >= {"machine", "system", "python", "numpy"}


def test_the_replication_flag_runs_its_own_block_into_its_own_directory(base, monkeypatch, tmp_path):
    monkeypatch.setattr(pp, "load_base", lambda: base)
    monkeypatch.chdir(tmp_path)
    seen = []
    real = tw.run_seed
    monkeypatch.setattr(tw, "run_seed", lambda payload: seen.append(payload[0]) or real(payload))

    class Inline:                                  # run in-process so the patches hold
        def __init__(self, max_workers=None): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def submit(self, fn, *a):
            from concurrent.futures import Future
            f = Future(); f.set_result(fn(*a)); return f
    import concurrent.futures as cf
    monkeypatch.setattr(cf, "ProcessPoolExecutor", Inline)
    assert tw.main(["--cell", "score", "--replication", "--draws", "2", "--workers", "1",
                    "--out", str(tmp_path / "res")]) == 0
    assert seen == [660000, 660001]
    assert (tmp_path / "res_score_replication" / "draws.jsonl").exists()
    with pytest.raises(SystemExit, match="exclusive"):
        tw.main(["--replication", "--smoke", "1"])


def test_the_prank_cell_is_refused_until_its_live_heading_exists(tmp_path):
    from experiments import planted_twins as pt
    f = tmp_path / "p.md"
    f.write_text("- its heading will be `## P-rank cell — LIVE`\n")
    with pytest.raises(SystemExit, match="not live"):
        pt.require_prank_live(f)
    f.write_text("## P-rank cell — LIVE, someday\n")
    pt.require_prank_live(f)
    with pytest.raises(SystemExit, match="not live"):
        pt.require_prank_live(pt.PRANK_PREREG)          # the real file: a draft
    with pytest.raises(SystemExit, match="not live"):
        pt.main(["--cell", "prank", "--planted", "1.5", "--draws", "1000"])
