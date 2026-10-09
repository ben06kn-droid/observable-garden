"""The version-2 confirmation runner: task list, pins and refusals (no panels built)."""
from experiments import ml_v2_confirm_2026_10_09 as C


def test_the_task_list_is_the_registered_block():
    t = C.tasks()
    seeds = [x for x in t if x[0] == "seed"]
    assert len(seeds) == 560 and {x[1] for x in seeds} == set(range(699000, 699560))
    assert [x[1] for x in seeds if x[2] == "regime"] == list(range(699480, 699560))
    assert [x[1] for x in t if x[0] == "level0"] == list(range(700000, 700400))
    assert len(seeds) * 2 == 1120
    assert all(x[1] in C.DRY_BLOCK for x in C.dry_tasks())


def test_the_configuration_is_the_registered_one():
    assert C.REGISTRATION == "083c734724340b0d1ae7f6bfd98b0a61e23fe84c"
    assert C.MEMORIES == ("roll756", "expand") and C.RATES == (0.3, 0.1, 0.03)
    assert C.L_GRID == {"L": (1.0, 3.0, 10.0, 30.0)} and C.COST_ARMS == {"registered": 1.0, "high": 5.0}


def test_the_pinned_blobs_match_this_checkout_and_the_laptop_is_refused():
    for f, blob in C.PINNED_V2.items():
        assert C.__dict__ and blob == __import__("subprocess").run(
            ["git", "rev-parse", f"HEAD:{f}"], capture_output=True, text=True).stdout.strip(), f
    bad = C.refusals("0" * 40, None)
    assert any("wheel" in b for b in bad) and any("expected" in b for b in bad)
    assert not any("pinned" in b and "learn2" in b for b in bad)
