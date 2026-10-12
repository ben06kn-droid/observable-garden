"""The French design script's power formula (no data)."""
import numpy as np
import pytest

from experiments import french_design_quantities as D


@pytest.mark.parametrize("bar,T", [(0.5, 9.98), (0.9, 6.98), (1.2, 10.0)])
def test_the_certified_sharpe_solves_the_stated_equation(bar, T):
    sr = D.certified_sharpe(bar, T)
    assert sr - D.Z80 * np.sqrt((1 + sr * sr / 2) / T) == pytest.approx(bar, abs=1e-10)
    assert sr > bar


def test_the_seeds_are_the_checked_block():
    assert (D.SEED_CLASS, D.SEED_RIDGE, D.SEED_LEAK) == (692003, 692004, 692005)
    assert D.B == 5000 and D.QUANTILES == (0.96, 0.99)
