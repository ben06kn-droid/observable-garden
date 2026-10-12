"""7.5 build item 2: the sealed agent holdout (`experiments/planted_holdout.py`).

Design block only, on a small synthetic base. No registered archive is generated.
"""
import inspect
import tarfile

import numpy as np
import pytest

from environments import planted_panel as pp
from experiments import planted_holdout as ph
from tests.test_planted_panel import _panel

SEEDS = [640000, 640001, 640002]
LEVELS = [0.0, 1.0, 1.5]


@pytest.fixture(scope="module")
def base():
    return pp.base_from(_panel(K=5))


@pytest.fixture
def sealed(base, tmp_path):
    out = tmp_path / "ho"
    m = ph.generate(SEEDS, LEVELS, out, base=base)
    archive, sha = ph.seal(out)
    return out, m, archive, sha


def test_the_sealed_returns_are_the_generators_holdout_bit_for_bit(base, sealed):
    _, m, archive, sha = sealed
    manifest, ret = ph.open_sealed(archive, sha)
    assert len(ret) == len(SEEDS) * len(LEVELS) == len(manifest["panels"])
    for seed in SEEDS:
        for level in LEVELS:
            d = pp.make_draw(base, seed, level)
            assert np.array_equal(ret[(seed, level)], d.holdout.returns)
    assert manifest["block"] == "design"
    assert manifest["pinned_x_sha256"] == pp.PINNED_X_SHA256


def test_levels_of_one_seed_share_the_residual_draw(base, sealed):
    """Paired, as registered: the levels differ only by the planted term c * w*."""
    _, m, archive, sha = sealed
    _, ret = ph.open_sealed(archive, sha)
    for seed in SEEDS:
        d = pp.make_draw(base, seed, 1.5)
        np.testing.assert_allclose(ret[(seed, 1.5)] - ret[(seed, 0.0)],
                                   d.c * d.w_star_ho, rtol=0, atol=1e-15)
    hashes = {p["seed"]: set() for p in m["panels"]}
    for p in m["panels"]:
        hashes[p["seed"]].add(p["idx_ho_sha256"])
    assert all(len(h) == 1 for h in hashes.values())


def test_the_seal_is_a_function_of_the_content(base, tmp_path, sealed):
    out, _, archive, sha = sealed
    archive2, sha2 = ph.seal(out)
    assert sha2 == sha
    other = tmp_path / "ho2"
    ph.generate(SEEDS, LEVELS, other, base=base)
    # same content, different directory name and generation time -> different
    # manifest bytes, so only the panel files are compared
    _, r1 = ph.open_sealed(archive, sha)
    _, r2 = ph.open_sealed(*ph.seal(other))
    assert all(np.array_equal(r1[k], r2[k]) for k in r1)


def test_a_wrong_hash_or_a_tampered_file_is_refused(sealed, tmp_path):
    out, _, archive, sha = sealed
    with pytest.raises(SystemExit, match="Refused unopened"):
        ph.open_sealed(archive, "0" * 64)
    f = out / ph.fname(SEEDS[0], 1.0)
    a = np.load(f)
    a[0, 0] += 1e-9
    np.save(f, a)
    archive2, sha2 = ph.seal(out)                 # re-sealed after tampering
    with pytest.raises(SystemExit, match="differs from the manifest"):
        ph.open_sealed(archive2, sha2)


@pytest.mark.parametrize("seed", [600000, 601999, 610000, 980000, 0, 641000])
def test_seeds_outside_the_design_block_are_refused(base, tmp_path, seed):
    with pytest.raises(SystemExit, match="design block"):
        ph.generate([seed], [1.0], tmp_path / "x", base=base)
    assert ph.AGENT_SEEDS == range(630000, 630020)   # the live agent block
    assert not (tmp_path / "x").exists()


def test_unregistered_levels_are_refused(base, tmp_path):
    with pytest.raises(SystemExit, match="registered"):
        ph.generate([640000], [0.75], tmp_path / "x", base=base)


def test_it_writes_outside_the_repository_and_into_a_new_directory(base, tmp_path):
    with pytest.raises(SystemExit, match="inside the repository"):
        ph.generate([640000], [1.0], ph.REPO / "runs" / "_holdout_test", base=base)
    assert not (ph.REPO / "runs" / "_holdout_test").exists()
    (tmp_path / "full").mkdir()
    (tmp_path / "full" / "x").write_text("x")
    with pytest.raises(SystemExit, match="not empty"):
        ph.generate([640000], [1.0], tmp_path / "full", base=base)


def test_no_encryption_decryption_or_key_handling():
    src = inspect.getsource(ph)
    code = src.split('"""', 2)[2]                 # past the module docstring
    for word in ("subprocess", "openssl", "passphrase", "cryptography", "Fernet",
                 "decrypt", "os.system"):
        assert word not in code, word


def test_the_archive_holds_only_regular_files_with_zeroed_metadata(sealed):
    _, _, archive, _ = sealed
    with tarfile.open(archive, "r:gz") as tf:
        for m in tf.getmembers():
            assert m.isfile() and m.mtime == 0 and m.uid == 0 and m.gid == 0


def test_the_live_agent_block_is_accepted(base, tmp_path):
    assert ph.check_seeds([630000, 630019]) == [630000, 630019]
    with pytest.raises(SystemExit, match="design block"):
        ph.check_seeds([630020])
