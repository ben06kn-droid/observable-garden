"""Regression guard for the mechanistic finding in SCOPE.md: re-deriving
each round's winner inside the bootstrap (the "oracle" bootstrap) must give
a null-max estimate >= the naive fixed-transcript bootstrap's, since the
naive version explores a strictly narrower space (round 2 anchored at the
observed winner only, vs. every replicate's own re-derived winner)."""
import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe, null_max_bootstrap
from experiments.verify_selective_inference_theory import recursive_bootstrap_null_max
from searchers.scripted import Adaptive


def test_oracle_bootstrap_mean_null_max_at_least_naive():
    K = 15
    config = DGPConfig(M=60, T=500, T_oos=100, K=K, s=0, rho=0.3, sigma=1.0, seed=3)
    data = generate(config)
    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    Adaptive(max_features=3, seed=3).run(sandbox)
    R = sandbox.returns_matrix()

    naive = null_max_bootstrap(R, B=1500, seed=3)
    oracle_M_b = recursive_bootstrap_null_max(R[:, :K], B=1500, max_features=3, seed=3)

    # Allow a little Monte Carlo slack; the effect is not tiny (~10%+ in practice).
    assert oracle_M_b.mean() > naive.mean_null_max * 0.97


def test_pair_return_stream_equals_sum_of_singles():
    # The additive-linearity property the reconstruction trick depends on.
    from environments.sandbox import Specification

    config = DGPConfig(M=40, T=200, T_oos=50, K=8, s=0, rho=0.2, sigma=1.0, seed=1)
    data = generate(config)
    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)

    w_a, w_b = np.zeros(8), np.zeros(8)
    w_a[1], w_b[4] = 1.0, 1.0
    sandbox.evaluate(Specification(weights=w_a))
    sandbox.evaluate(Specification(weights=w_b))
    sandbox.evaluate(Specification(weights=w_a + w_b))

    stream_a, stream_b, stream_pair = (e.return_stream for e in sandbox.transcript)
    np.testing.assert_allclose(stream_pair, stream_a + stream_b, atol=1e-10)
