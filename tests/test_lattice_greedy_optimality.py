"""Empirical property the e2 lattice-control result leans on: LatticeAdaptive's
greedy selection (only ~K+2(K-1) of the full lattice's combos examined) turns
out to always land on the TRUE full-lattice maximum in this DGP, across every
draw checked. This means e1_null_calibration's default sr_sel (max over the
whole transcript) and the searcher's own submitted value coincide for
LatticeAdaptive too -- so the completed e2 run's numbers are valid without
needing the explicit-sr_sel fix applied in experiments/e2_lattice_control.py.
Locked in as a regression rather than left as an unverified assumption."""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe
from searchers.diagnostic import LatticeAdaptive


@pytest.mark.parametrize("seed", range(10))
def test_greedy_submission_equals_true_lattice_max(seed):
    config = DGPConfig(M=40, T=300, T_oos=100, K=15, s=0, rho=0.3, sigma=1.0, seed=1000 + seed)
    data = generate(config)
    ann = np.sqrt(config.periods_per_year)

    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    LatticeAdaptive(max_features=3, seed=1000 + seed).run(sandbox)
    _, dist = sandbox.submission

    true_max = sharpe(sandbox.returns_matrix(), axis=0, annualization=ann).max()
    assert dist.mean == pytest.approx(true_max, abs=1e-9)
