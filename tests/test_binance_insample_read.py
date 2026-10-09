"""The Binance in-sample read's runner: its start-up refusals on this laptop checkout. The
pricing path is tested on a synthetic panel in tests/test_binance_insample_dry.py, and
its bootstrap path against learn/stream_tier.py in tests/test_binance_stream_equivalence.py."""
from experiments import binance_insample_read as R


def test_the_runner_refuses_a_wrong_head_and_a_missing_wheel():
    bad = R.refusals("0" * 40, None)
    assert any("not the expected" in b for b in bad) and any("--wheel" in b for b in bad)


def test_the_pinned_blobs_are_the_confirmations_learn2_and_the_stream_tier():
    from experiments.ml_v2_confirm_2026_10_09 import PINNED_V2
    assert {f for f in R.PINNED_BLOBS if f.startswith("learn2/")} == {f for f in PINNED_V2 if f.startswith("learn2/")}
    assert R.PINNED_BLOBS["learn/stream_tier.py"] == "107abb472bb23b606877673e8b80ec75bf3eba95"
    bad = R.refusals("0" * 40, None)
    assert not any("blob" in b for b in bad) and not any("pin " in b for b in bad)


def test_the_registered_constants():
    assert (R.SEED_STREAM, R.SEED_CLASS, R.SEED_D1) == (701000, 701001, 701002)
    assert (R.ALPHA_STREAM, R.ALPHA_CLASS, R.B) == (0.04, 0.01, 5000)
    assert R.REGISTRATION == "ecc07f0e6117e92db9ac03be462f418e3b0ac246"
