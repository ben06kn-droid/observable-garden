"""The read script's own bootstrap path decides the stream's certificate, so it must equal
`learn.stream_tier.certify` when both are given the same block length and seed. On
synthetic streams: certify takes its block length from the base columns
(`select_block_length` on the demeaned columns); the read path is given that same length
explicitly."""
import numpy as np
import pytest

from estimator.bootstrap import select_block_length
from experiments import binance_insample_read as R
from learn import stream_tier


def _case(seed, T=600, K=6, drift=0.0, ar=0.0, bc_ar=None):
    rng = np.random.default_rng(seed)
    e = rng.standard_normal(T)
    s = np.empty(T)
    s[0] = e[0]
    for t in range(1, T):
        s[t] = ar * s[t - 1] + e[t]
    s = 0.01 * s + drift
    if bc_ar is None:                                  # persistent columns: a long block
        bc = np.cumsum(rng.standard_normal((T, K)), axis=0) * 0.001 + 0.01 * rng.standard_normal((T, K))
    else:                                              # AR(1) columns: a short block
        u = rng.standard_normal((T, K))
        bc = np.empty((T, K))
        bc[0] = u[0]
        for t in range(1, T):
            bc[t] = bc_ar * bc[t - 1] + u[t]
    return s, bc


CASES = [(1, 0.0, 0.0, 2190.0, None), (2, 0.002, 0.3, 2190.0, None), (3, -0.001, 0.6, 365.0, None),
         (4, 0.004, 0.0, 252.0, None), (5, 0.001, 0.2, 2190.0, 0.0), (6, 0.0, 0.0, 2190.0, 0.05),
         (8, 0.002, 0.4, 2190.0, 0.5)]


def test_the_cases_cover_block_lengths_one_two_and_long():
    Ls = {int(select_block_length(bc - bc.mean(axis=0))) for bc in (_case(c[0], bc_ar=c[4])[1] for c in CASES)}
    assert 1 in Ls and 2 in Ls and max(Ls) > 10


@pytest.mark.parametrize("seed,drift,ar,ppy,bc_ar", CASES)
def test_the_read_path_equals_stream_tier_at_the_same_block_length_and_seed(seed, drift, ar, ppy, bc_ar):
    s, bc = _case(seed, drift=drift, ar=ar, bc_ar=bc_ar)
    B, sd = 400, 701000 + seed
    ref = stream_tier.certify(s[None, :], bc, ppy, B, sd)
    L = int(select_block_length(bc - bc.mean(axis=0)))
    assert L == ref["block_length"]
    got = R.stream_test(s, L, ppy, B, sd)
    assert got["S"] == ref["score"]
    assert got["p"] == ref["p"]
    assert np.array_equal(got["null_max"], np.asarray(ref["null_max"], float))
    assert got["confidence"]["L"]["0.90"] == ref["confidence"]["L"]["0.90"]


def test_a_different_block_length_or_seed_changes_the_null():
    s, bc = _case(7, ar=0.5)
    a = R.stream_test(s, 1, 2190.0, 300, 5)
    assert not np.array_equal(a["null_max"], R.stream_test(s, 6, 2190.0, 300, 5)["null_max"])
    assert not np.array_equal(a["null_max"], R.stream_test(s, 1, 2190.0, 300, 6)["null_max"])
