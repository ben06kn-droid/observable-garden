"""`quixote power`: the floor falls with years and rises with the class's size."""
import pytest

from quixote import power as W


def test_floor_decreases_with_years():
    bars = [W.floor(128, y).bar for y in (2, 5, 10, 20)]
    assert all(a > b for a, b in zip(bars, bars[1:]))


def test_floor_increases_with_size():
    bars = [W.floor(n, 10).bar for n in (1, 10, 1000, 100000)]
    assert all(a < b for a, b in zip(bars, bars[1:]))


def test_power_sharpe_above_bar_and_render():
    f = W.floor(128, 10)
    assert f.sharpe_for_80pct > f.bar > 0 and f.periods == 2520
    assert "smallest Sharpe the gate can certify" in f.render()
    assert set(f.to_dict()) >= {"size", "years", "bar", "sharpe_for_80pct"}


def test_bad_input():
    with pytest.raises(ValueError):
        W.floor(0, 10)
    with pytest.raises(ValueError):
        W.floor(10, 0)
