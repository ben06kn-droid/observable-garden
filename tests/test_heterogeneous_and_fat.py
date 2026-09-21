"""6.3's DGP variants: the three cells must actually differ, and the fat-tail
cell must reach the statistic the null is taken over.

Both properties were wrong in the first draft. `heterogeneous_correlation`
returns the identity at rho <= 0, so cells registered at arm D's rho = 0 made
(A) a baseline rerun and (C) identical to (B). And a per-asset volatility path
would wash out across M = 50 assets, leaving a cell that looks like a stress
test and is not one.
"""
import numpy as np
import pytest

import experiments.heterogeneous_and_fat as h


@pytest.fixture
def small(monkeypatch):
    from garden.spec_class import SubsetClass
    signed, unsigned = SubsetClass(max_size=2, signed=True), SubsetClass(max_size=2, signed=False)
    for attr, value in (("M", 8), ("T", 400), ("T_OOS", 100), ("K", 8), ("D", 2),
                        ("SIGNED", signed), ("UNSIGNED", unsigned),
                        ("B_REPS", 300), ("GARCH_BURN", 100),
                        ("MATCHED", {"exhaustive-signed": signed, "signed-adaptive": signed,
                                     "greedy": unsigned, "adaptive": unsigned})):
        monkeypatch.setattr(h, attr, value)
    return h


def test_the_three_cells_are_actually_different(small):
    """The regression. (B) and (C) came out bit-identical because the
    heterogeneous flag is a no-op at rho = 0."""
    out = {c: tuple(round(small.run_draw(c, 400_000)[k]["sr_sel"], 9)
                    for k in small.MEMBERS) for c in ("A", "B", "C")}
    assert out["A"] != out["B"]
    assert out["B"] != out["C"]
    assert out["A"] != out["C"]


def test_the_heterogeneous_cells_use_a_positive_rho(small):
    """At rho <= 0 heterogeneous_correlation returns the identity, so a cell
    registered at rho = 0 tests nothing."""
    from environments.dgp import heterogeneous_correlation
    assert small.RHO_HETEROGENEOUS > 0
    assert not np.allclose(
        heterogeneous_correlation(8, small.RHO_HETEROGENEOUS, 3), np.eye(8))
    for cell, expect in (("A", True), ("B", False), ("C", True)):
        _, cfg = small.make_panel(cell, 400_000)
        assert cfg.heterogeneous is expect
        assert (cfg.rho > 0) is expect


def test_a_common_volatility_path_survives_the_cross_sectional_average():
    """Why the path is common rather than per-asset. A base feature column
    averages over M assets; with independent per-asset paths the clustering
    averages away and the cell would stress nothing."""
    n = 20_000
    noise = 3.0 / np.sqrt(n)              # ~3 sd of a zero autocorrelation
    rng = np.random.default_rng(0)
    e = h.common_garch_t_noise(rng, n, 50, 1.0)
    pm = e.mean(axis=1)
    common_ac = float(np.corrcoef(np.abs(pm[:-1]), np.abs(pm[1:]))[0, 1])

    scale = np.sqrt((h.T_DOF - 2) / h.T_DOF)
    indep = (rng.standard_t(h.T_DOF, size=(n, 50)) * scale).mean(axis=1)
    indep_ac = float(np.corrcoef(np.abs(indep[:-1]), np.abs(indep[1:]))[0, 1])

    # the common path leaves clustering well outside sampling noise; independent
    # per-asset innovations leave it indistinguishable from zero
    assert common_ac > 5 * noise, common_ac
    assert abs(indep_ac) < noise, indep_ac


def test_the_garch_path_is_stationary_and_correctly_scaled():
    assert h.GARCH_ALPHA + h.GARCH_BETA < 1.0
    rng = np.random.default_rng(1)
    e = h.common_garch_t_noise(rng, 20000, 50, 1.0)
    assert 0.85 < e.std() < 1.15          # omega set for unconditional variance sigma^2
    assert np.isfinite(e).all()


def test_each_searcher_is_scored_against_a_class_it_can_reach(small):
    r = small.run_draw("C", 400_000)
    assert set(r) == {"_draw", *small.MEMBERS}
    # the anchor submits the signed class maximum, so nothing can beat it
    top = r["exhaustive-signed"]["sr_sel"]
    for k in small.MEMBERS:
        assert r[k]["sr_sel"] <= top + 1e-12
    assert r["_draw"]["null_q_signed"].shape == (len(small.NULL_QUANTILES),)
    assert r["_draw"]["null_q_unsigned"].shape == (len(small.NULL_QUANTILES),)
