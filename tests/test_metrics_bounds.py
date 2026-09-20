"""Wilson intervals stay inside [0, 1], exactly, at the boundaries.

At k=0 the closed form leaves a floating-point residue where the true lower
bound is zero: wilson_ci(0, 500) returned 4.3e-19. That printed as "-0.000" in
one report, and made a containment test of the form `lo <= rate <= hi` read
false when the observed rate was exactly zero -- which is precisely the case a
zero-rejection arm produces.
"""
import pytest

from estimator.metrics import type1_rate, wilson_ci


@pytest.mark.parametrize("n", [1, 10, 500, 5000])
def test_zero_successes_gives_an_exact_zero_lower_bound(n):
    lo, hi = wilson_ci(0, n)
    assert lo == 0.0
    assert 0.0 < hi <= 1.0


@pytest.mark.parametrize("n", [1, 10, 500, 5000])
def test_all_successes_gives_an_exact_one_upper_bound(n):
    lo, hi = wilson_ci(n, n)
    assert hi == 1.0
    assert 0.0 <= lo < 1.0


def test_a_zero_rate_is_contained_in_its_own_interval():
    """The containment test an arm with no rejections actually runs."""
    lo, hi = wilson_ci(0, 500)
    assert lo <= 0.0 <= hi


@pytest.mark.parametrize("k,n", [(0, 100), (1, 100), (50, 100), (99, 100), (100, 100)])
def test_bounds_bracket_the_point_estimate(k, n):
    lo, hi = wilson_ci(k, n)
    assert 0.0 <= lo <= k / n <= hi <= 1.0


def test_type1_rate_inherits_the_clamp():
    import numpy as np
    rate, lo, hi = type1_rate(np.full(500, 0.9), alpha=0.05)
    assert rate == 0.0 and lo == 0.0 and hi > 0.0
