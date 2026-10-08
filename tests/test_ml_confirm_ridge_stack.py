"""The confirmation runner's task list and start-up refusals (registration section 7)."""
import hashlib

from experiments import ml_confirm_ridge_stack as C


def test_the_task_list_is_the_registered_block():
    t = C.tasks()
    seeds = [s for _, s, _ in t]
    assert len(t) == 800 and len(set(seeds)) == 800
    assert min(seeds) == 689000 and max(seeds) == 689799
    assert [s for k, s, sh in t if sh == "gated"] == list(range(689300, 689400))
    assert [s for k, s, _ in t if k == "level0"] == list(range(689400, 689800))
    n_panels = sum(len(C.levels_for(s, sh)) for k, s, sh in t if k == "planted")
    assert n_panels == 4 * 100 + 4 * 50 * 2                    # 400 at 1.5; 200 at 1.0 and 2.5
    assert C.levels_for(689049, "U") == (1.0, 1.5, 2.5) and C.levels_for(689050, "U") == (1.5,)
    assert C.levels_for(689349, "gated") == (1.0, 1.5, 2.5)


def test_the_pinned_constants_are_the_registered_ones():
    assert C.REGISTRATION == "77f3ee19469f500d5c3959c9612a04d250856b02"
    assert C.PINNED_BLOBS["learn/ridge_stack.py"] == "2c09b25701038964c97a193f66a5203f99bf0915"
    assert C.LIGHTGBM == "4.7.0" and C.CARRY_SEED == 689999


def test_every_refusal_fires_and_a_good_setup_passes(tmp_path):
    wheel = tmp_path / "w.whl"
    wheel.write_bytes(b"not the wheel")
    lib = tmp_path / "lib.so"
    lib.write_bytes(b"not the lib")
    bad = C.refusals("0" * 40, str(wheel), platform_name="Darwin arm64", lib=lib)
    text = "\n".join(bad)
    for needle in ("wheel's SHA-256", "lib_lightgbm.so", "is not the expected", "platform Darwin"):
        assert needle in text
    assert "no wheel file" in "\n".join(C.refusals("0" * 40, None, lib=lib))
    # with the registered hashes patched to the stand-in files, only HEAD/platform/tree remain
    C_w, C_l = C.WHEEL_SHA256, C.LIB_SHA256
    try:
        C.WHEEL_SHA256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
        C.LIB_SHA256 = hashlib.sha256(lib.read_bytes()).hexdigest()
        head = C._git("rev-parse", "HEAD").stdout.strip()
        rest = C.refusals(head, str(wheel), platform_name="Linux x86_64", lib=lib)
        assert not any("blob" in r or "SHA-256" in r or "expected" in r or "platform" in r
                       or "ancestor" in r for r in rest), rest
    finally:
        C.WHEEL_SHA256, C.LIB_SHA256 = C_w, C_l


def test_dry_tasks_are_one_planted_task_at_three_levels_and_one_level0_task():
    import pytest
    assert C.dry_tasks([689900, 689901]) == [("planted", 689900, "gated"), ("level0", 689901, None)]
    assert C.levels_for(689900, "gated") == (1.0, 1.5, 2.5)
    for bad in ([689000, 689901], [689900, 689900], [689900, 689910]):
        with pytest.raises(SystemExit):
            C.dry_tasks(bad)
