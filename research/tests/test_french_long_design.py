"""The French long-history design simulation's class null equals the recency planted runner's
fixed-centring class null (synthetic pool)."""
import numpy as np

from experiments import french_long_design as F
from experiments import recency_planted as P


def test_class_maxima_match_the_planted_runner():
    rng = np.random.default_rng(1)
    G = rng.standard_normal((25, 40)) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    i = P.pool_rows(600, 40, 7, rng)
    M = F.class_maxima(G, i, 3, 5, 60, chunk=8)
    S_ref = P.class_tests(G, i, 3, 5, 60, chunk=8)
    # same null maxima: the planted runner's p for the observed maximum must follow from M
    assert S_ref["unweighted"]["p"] == (1 + int(np.sum(M >= S_ref["unweighted"]["S"]))) / 61


def test_the_w2_class_maxima_match_the_round2_runner():
    from experiments import french_long_design_w2 as F2
    from experiments import recency_planted_2 as P2
    rng = np.random.default_rng(4)
    G = rng.standard_normal((25, 40)) * 0.01
    G -= G.mean(axis=1, keepdims=True)
    i = P.pool_rows(600, 40, 7, rng)
    M = F2.class_maxima_w2(G, i, 3, 5, 50, chunk=8)
    ref = P2.class_w2(G, i, 3, 5, 50, chunk=8)
    assert ref["p"] == (1 + int(np.sum(M >= ref["S"]))) / 51
