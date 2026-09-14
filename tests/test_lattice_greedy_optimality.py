"""LatticeAdaptive's greedy `_select` restricts itself to the SAME
round-by-round path structure as Adaptive (best single -> best extension of
it -> ...), even though it has the full lattice pre-evaluated. An earlier
version of this test claimed this greedy pick always equals the true
full-lattice maximum, verified on 30 draws across two configs. That claim
was false in general -- a direct counterexample was found (K=20, M=50,
T=500, rho=0.3, seed=70022): the greedy pick landed on 1.9956 while an
UNSELECTED triple {2,7,19}, already sitting in the same transcript, scored
2.0148. Greedy forward selection is a heuristic without a general
optimality guarantee; the earlier 30/30 agreement was a property of those
specific small samples, not a theorem.

This mattered beyond bookkeeping: experiments relying on deflate()'s default
sr_sel (max over the whole transcript) as a stand-in for "the searcher's own
submission" are wrong whenever this gap is nonzero -- not just for
LatticeAdaptive, but for any variant (BeamAdaptive, width > 1) whose
transcript can contain evaluated-but-unselected candidates. Every
experiment now passes sr_sel explicitly (the searcher's own replay()/
submission value) rather than relying on the default.

This file now: (1) locks in the counterexample as a regression guard so the
false claim can't quietly get re-asserted, and (2) measures the actual
mismatch rate rather than assuming it away.
"""
import numpy as np

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from estimator.bootstrap import sharpe
from searchers.diagnostic import LatticeAdaptive


def test_known_counterexample_greedy_pick_is_suboptimal():
    config = DGPConfig(M=50, T=500, T_oos=200, K=20, s=0, rho=0.3, sigma=1.0, seed=70022)
    data = generate(config)
    ann = np.sqrt(config.periods_per_year)

    sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
    LatticeAdaptive(max_features=3, seed=70022).run(sandbox)
    _, dist = sandbox.submission

    true_max = sharpe(sandbox.returns_matrix(), axis=0, annualization=ann).max()
    assert true_max > dist.mean + 0.01, (
        "expected the documented counterexample (greedy pick strictly below "
        "the true transcript max); if this now fails, either the searcher's "
        "logic changed or the DGP/seed no longer reproduces it -- update "
        "the docstring accordingly rather than deleting this test"
    )


def test_greedy_suboptimality_rate_is_measured_not_assumed():
    """Quantifies how often LatticeAdaptive's greedy pick misses the true
    lattice max, over an independent seed range from the counterexample
    above. Asserts only that mismatches are rare (a sanity bound on how
    surprised we should be), not that they never happen."""
    mismatches = 0
    n_draws = 30
    for i in range(n_draws):
        config = DGPConfig(M=50, T=500, T_oos=200, K=20, s=0, rho=0.3, sigma=1.0, seed=71_000 + i)
        data = generate(config)
        ann = np.sqrt(config.periods_per_year)
        sandbox = Sandbox(data, periods_per_year=config.periods_per_year)
        LatticeAdaptive(max_features=3, seed=71_000 + i).run(sandbox)
        _, dist = sandbox.submission
        true_max = sharpe(sandbox.returns_matrix(), axis=0, annualization=ann).max()
        if true_max > dist.mean + 1e-6:
            mismatches += 1

    rate = mismatches / n_draws
    assert rate < 0.25, f"greedy suboptimality rate {rate:.2f} is far higher than expected -- investigate"
