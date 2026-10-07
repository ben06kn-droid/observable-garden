"""The ML pilot runner's pieces (`experiments/ml_pilot_2026_10_07.py`), on synthetic bases:
the class pass on planted rules, the scored-window population Sharpe, and the task list."""
import numpy as np
import pytest

from environments import planted_fast as pf
from environments import planted_panel as pp
from environments import planted_rules as prl
from environments.class_table import streams_for
from experiments import ml_pilot_2026_10_07 as P
from experiments import planted_edge as pe
from tests.test_planted_panel import _panel

RULE = {"shape": "product", "a": 1, "b": 3}


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture(scope="module")
def cache(base, tmp_path_factory):
    return pf.build(base.in_sample, base.members, cache_dir=tmp_path_factory.mktemp("fast"))


def test_the_class_pass_on_rule_draws_matches_the_registered_streams(base, cache):
    seed = 687990
    draws = [prl.make_draw_rule(base, seed, b, "product", RULE) for b in (1.0, 2.5)]
    full, _ = pf.class_pass_draws(base, cache, seed, draws, 40)
    summ, _ = pf.class_pass_draws(base, cache, seed, draws, 40, summary=P._class_summary)
    for (d, obs, rep, L), s in zip(full, summ):
        ref = pe._sharpe_rows(streams_for(d.in_sample, base.members),
                              np.sqrt(d.in_sample.periods_per_year))
        np.testing.assert_allclose(obs, ref, rtol=0, atol=1e-9)
        M_b = rep.max(axis=0)
        assert s["class_max"] == float(obs.max())
        assert s["p"] == (1 + int(np.sum(M_b >= obs.max()))) / 41 and s["B"] == 40


def test_levels_must_share_the_planted_positions(base, cache):
    a = prl.make_draw_rule(base, 687991, 1.0, "product", RULE)
    b = prl.make_draw_rule(base, 687991, 1.0, "U", {"shape": "U", "a": 2, "b": None})
    with pytest.raises(AssertionError):
        pf.class_pass_draws(base, cache, 687991, [a, b], 10)


def test_the_window_sharpe_over_all_rows_is_the_population_sharpe(base):
    d = prl.make_draw_rule(base, 687992, 1.5, "product", RULE)
    rows = np.arange(d.w_star_is.shape[0])
    w = P.window_sharpes(base, d.in_sample, d.w_star_is, d.w_star_is, d.c, rows)
    assert w["net"] == pytest.approx(1.5, abs=1e-8)
    rec = prl.plant_record(base, d)
    assert w["gross"] == pytest.approx(rec["gross"]["in_sample"], rel=1e-12)
    # a window: the book starts from zero at its first row, as net_stream does
    r = rows[len(rows) // 3:]
    ws = P.window_sharpes(base, d.in_sample, d.w_star_is, d.w_star_is, d.c, r)
    sub = P.window(d.in_sample, r)
    assert ws["net"] == pytest.approx(
        pp.population_sharpe(sub, base.Sigma_is, d.w_star_is[r], d.w_star_is[r], d.c), rel=1e-12)


def test_the_task_list_is_the_registered_block():
    t = P.tasks()
    seeds = [s for _, s, _ in t]
    assert len(t) == 300 and len(set(seeds)) == 300
    assert min(seeds) == 687000 and max(seeds) == 687299
    assert {sh for k, _, sh in t if k == "planted"} == set(prl.RULES)
    assert [s for k, s, sh in t if sh == "gated"] == list(range(687150, 687200))
    assert P.LEVELS == (1.0, 1.5, 2.5) and P.B == 1000 and P.CARRY_SEED == 687999


def test_dry_tasks_are_one_planted_and_one_level0_task_on_the_smoke_block():
    assert P.dry_tasks([686004, 686005], "gated") == [("planted", 686004, "gated"),
                                                      ("level0", 686005, None)]
    for bad in ([687000, 686005], [686004, 686004], [686004, 687299]):
        with pytest.raises(SystemExit):
            P.dry_tasks(bad, "gated")
    with pytest.raises(SystemExit):
        P.dry_tasks([686004, 686005], "spiral")
