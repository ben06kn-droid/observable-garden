"""The Binance design script's power formula (no data)."""
import numpy as np
import pytest

from experiments import binance_design_quantities as D


@pytest.mark.parametrize("bar,T,ppy", [(1.0, 3.25, 2190.0), (2.0, 2.9, 2190.0), (1.4, 9.98, 252.0)])
def test_the_certified_sharpe_solves_lo_s_iid_equation(bar, T, ppy):
    sr = D.certified_sharpe(bar, T, ppy)
    assert sr - D.Z80 * np.sqrt((1 + sr * sr / (2 * ppy)) / T) == pytest.approx(bar, abs=1e-10)


def test_seeds_quantiles_and_B():
    assert (D.SEED_CLASS, D.SEED_STREAM, D.SEED_LEAK) == (695000, 695001, 695002)
    assert D.QUANTILES == (0.95, 0.96, 0.975, 0.99) and D.B == 5000
