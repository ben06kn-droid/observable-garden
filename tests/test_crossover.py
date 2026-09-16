import numpy as np
import pytest

from environments.prices import (
    draw_shifts, forward_returns, panel, rule_positions, returns_from_positions, shift_pool,
    shifted_surrogate, simulate_walk,
)
from searchers.crossover import AdaptiveCrossover, CrossoverGrid, OffGridError

WARMUP = 200


def make_returns(seed=0, n_periods=1000):
    grid = CrossoverGrid()
    r = simulate_walk(n_periods, np.random.default_rng(seed), WARMUP)
    P = rule_positions(r, grid.rules, WARMUP)
    return grid, P, forward_returns(r, WARMUP)


def test_every_neighbour_stays_on_the_declared_grid():
    grid = CrossoverGrid()
    n = len(grid.rules)
    for i in range(n):
        for j in grid.neighbours(i):
            assert 0 <= j < n
            assert grid.rules[j] in grid.rules
            assert j != i


def test_coarse_menu_is_a_subset_of_the_grid():
    grid = CrossoverGrid()
    coarse = grid.coarse()
    assert 0 < len(coarse) < len(grid.rules)
    assert len(set(coarse)) == len(coarse)
    assert all(0 <= c < len(grid.rules) for c in coarse)


def test_off_grid_rule_and_wrong_width_raise():
    grid, P, fwd = make_returns()
    with pytest.raises(OffGridError):
        grid.index_of((7, 11, False))          # 7 and 11 are not on the declared lists
    with pytest.raises(OffGridError):
        AdaptiveCrossover(grid).run(returns_from_positions(P, fwd)[:, :10])


@pytest.mark.parametrize("anchor", ["winner", "loser"])
def test_search_submits_the_best_rule_it_evaluated(anchor):
    grid, P, fwd = make_returns(seed=3)
    R = returns_from_positions(P, fwd)
    ann = np.sqrt(252)
    res = AdaptiveCrossover(grid, anchor=anchor).run(R, annualization=ann)
    sharpes = R.mean(axis=0) / R.std(axis=0, ddof=1) * ann
    assert res.sharpe == pytest.approx(max(sharpes[list(res.evaluated)]), rel=1e-12)
    assert res.selected in res.evaluated and res.anchor in res.evaluated


def test_winner_and_loser_anchor_on_opposite_ends_of_the_coarse_round():
    grid, P, fwd = make_returns(seed=4)
    R = returns_from_positions(P, fwd)
    ann = np.sqrt(252)
    coarse = grid.coarse()
    sharpes = R.mean(axis=0) / R.std(axis=0, ddof=1) * ann
    win = AdaptiveCrossover(grid, anchor="winner", rounds=0).run(R, ann)
    lose = AdaptiveCrossover(grid, anchor="loser", rounds=0).run(R, ann)
    assert win.anchor == coarse[int(np.argmax(sharpes[coarse]))]
    assert lose.anchor == coarse[int(np.argmin(sharpes[coarse]))]


def test_search_is_deterministic_on_the_same_data():
    grid, P, fwd = make_returns(seed=5)
    R = returns_from_positions(P, fwd)
    a = AdaptiveCrossover(grid).run(R, 1.0)
    b = AdaptiveCrossover(grid).run(R, 1.0)
    assert (a.selected, a.anchor, a.evaluated) == (b.selected, b.anchor, b.evaluated)


def test_panel_search_spans_every_block_and_refines_within_one():
    grid = CrossoverGrid()
    width = len(grid.rules)
    blocks = 3
    P, fwd = panel(blocks, 800, grid.rules, WARMUP, np.random.default_rng(11))
    R = returns_from_positions(P, fwd)
    R[:, width:2 * width] += 0.002          # make the middle asset clearly the best place to search
    res = AdaptiveCrossover(grid, anchor="winner", blocks=blocks).run(R, np.sqrt(252))

    coarse = {b * width + c for b in range(blocks) for c in grid.coarse()}
    assert coarse <= set(res.evaluated)                      # the coarse round spans every asset
    assert res.selected // width == 1 and res.anchor // width == 1
    refined = [c for c in res.evaluated if c not in coarse]
    assert refined and all(c // width == res.anchor // width for c in refined)


def test_blocks_must_match_the_matrix_width():
    grid, P, fwd = make_returns(seed=12)
    R = returns_from_positions(P, fwd)
    with pytest.raises(OffGridError, match="block"):
        AdaptiveCrossover(grid, blocks=2).run(R)
    with pytest.raises(ValueError):
        AdaptiveCrossover(grid, blocks=0)


@pytest.mark.parametrize("blocks", [1, 3])
def test_run_from_sharpes_matches_run(blocks):
    grid = CrossoverGrid()
    if blocks == 1:
        _, P, fwd = make_returns(seed=21)
    else:
        P, fwd = panel(blocks, 800, grid.rules, WARMUP, np.random.default_rng(21))
    R = returns_from_positions(P, fwd)
    ann = np.sqrt(252)
    mu, sd = R.mean(axis=0), R.std(axis=0, ddof=1)
    sharpes = np.where(sd > 0, mu / np.where(sd > 0, sd, 1.0), 0.0) * ann
    for anchor in ("winner", "loser"):
        searcher = AdaptiveCrossover(grid, anchor=anchor, blocks=blocks)
        a, b = searcher.run(R, ann), searcher.run_from_sharpes(sharpes)
        assert (a.selected, a.anchor, a.evaluated) == (b.selected, b.anchor, b.evaluated)
        assert a.sharpe == pytest.approx(b.sharpe, rel=1e-12)


def test_run_from_sharpes_checks_width():
    grid, P, fwd = make_returns(seed=22)
    with pytest.raises(OffGridError):
        AdaptiveCrossover(grid).run_from_sharpes(np.zeros(10))


def test_single_block_is_the_default_and_unchanged():
    grid, P, fwd = make_returns(seed=13)
    R = returns_from_positions(P, fwd)
    a = AdaptiveCrossover(grid).run(R, 1.0)
    b = AdaptiveCrossover(grid, blocks=1).run(R, 1.0)
    assert (a.selected, a.anchor, a.evaluated) == (b.selected, b.anchor, b.evaluated)


def test_positions_need_a_long_enough_warmup():
    grid = CrossoverGrid()
    r = simulate_walk(300, np.random.default_rng(0), 50)
    with pytest.raises(ValueError):
        rule_positions(r, grid.rules, warmup=50)     # slowest window is 200


def test_surrogate_preserves_positions_and_shifts_returns():
    grid, P, fwd = make_returns(seed=6)
    R = returns_from_positions(P, fwd)
    S = shifted_surrogate(P, fwd, 37)
    assert S.shape == R.shape
    np.testing.assert_allclose(S, P * np.roll(fwd, 37)[:, None])
    assert not np.allclose(S, R)


def test_shift_pool_excludes_near_alignment_and_draws_without_replacement():
    pool = shift_pool(1000, exclude=200)
    assert pool.min() == 200 and pool.max() == 800
    drawn = draw_shifts(1000, 200, 300, np.random.default_rng(0))
    assert len(set(drawn.tolist())) == 300
    assert drawn.min() >= 200 and drawn.max() <= 800
    with pytest.raises(ValueError):
        draw_shifts(1000, 200, len(pool) + 1, np.random.default_rng(0))


def test_panel_stacks_independent_assets():
    grid = CrossoverGrid()
    P, fwd = panel(3, 600, grid.rules, WARMUP, np.random.default_rng(1))
    n = len(grid.rules)
    assert P.shape == fwd.shape == (600, 3 * n)
    # each asset's block carries its own returns, repeated across that asset's rules
    for a in range(3):
        block = fwd[:, a * n:(a + 1) * n]
        assert np.allclose(block, block[:, [0]])
    assert not np.allclose(fwd[:, 0], fwd[:, n])
