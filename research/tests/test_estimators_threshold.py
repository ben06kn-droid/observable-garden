"""ET's root-finder on a synthetic truncated normal whose answer is known
(`experiments/estimators_threshold_2026_10_06.py`, addendum 382ac84)."""
import numpy as np
import pytest
from scipy.stats import norm

from experiments import estimators_threshold_2026_10_06 as et


def _e(sigma, n=200_001):
    # deterministic normal quantiles: centred, so mean(e) is 0 to rounding
    return sigma * norm.ppf((np.arange(1, n + 1) - 0.5) / n)


@pytest.mark.parametrize("theta,B,sigma,c", [(0.3, 0.2, 0.3, 0.9), (0.6, 0.35, 0.25, 1.0),
                                             (0.0, 0.4, 0.2, 0.8), (1.0, 0.1, 0.3, 0.9)])
def test_the_root_is_the_truncated_normal_mean_inverted(theta, B, sigma, c):
    a = (c - theta - B) / sigma
    S = theta + B + sigma * norm.pdf(a) / norm.sf(a)        # E[X | X >= c], X ~ N(theta+B, sigma)
    got, flag, g = et.et_root(S, B, _e(sigma), c)
    assert not flag
    assert got == pytest.approx(theta, abs=2e-3)
    assert abs(g) < 1e-3


def test_the_restricted_mean_is_never_below_the_unrestricted_at_the_top_bound():
    e = _e(0.3, 10_001)
    S, B, c = 1.2, 0.3, 1.1
    assert et.restricted_mean(S - B, B, e, c) >= S - 1e-12


def test_no_root_inside_takes_the_nearer_bound_and_flags():
    e = _e(0.01, 1001)
    # c far above everything reachable: the restricted mean is c > S on the whole interval
    th, flag, _ = et.et_root(1.0, 0.2, e, 5.0)
    assert flag and th == pytest.approx(1.0 - 3.0)
    # c far below: no truncation, so the root is S - B (to rounding of mean(e))
    th, flag, _ = et.et_root(1.0, 0.2, e, -10.0)
    assert th == pytest.approx(0.8, abs=1e-9)


def test_etm_is_the_average_of_et_and_the_base():
    d = 0.2 + _e(0.3, 20_001)
    base, ET, ETm, flag, _ = et.candidates(1.2, 0.2, d, 0.9)
    assert base == pytest.approx(1.0)
    assert ETm == pytest.approx(0.5 * (ET + base))
    assert ET <= base + 1e-9          # conditioning on the threshold lowers the estimate
