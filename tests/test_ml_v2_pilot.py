"""The version-2 pilot runner's task list and dry tasks (no panels built)."""
from experiments import ml_v2_pilot_2026_10_08 as P


def test_the_task_list_is_the_registered_block():
    t = P.tasks()
    seeds = [x for x in t if x[0] == "seed"]
    menus = [x for x in t if x[0] == "menu"]
    level0 = [x for x in t if x[0] == "level0"]
    assert len(seeds) == 350 and len(menus) == 280 and len(level0) == 100
    assert {x[1] for x in seeds} == set(range(697000, 697350))
    assert [x[1] for x in level0] == list(range(697400, 697500))
    assert all(x[3] in (1.0, 1.5) and (x[1] - P.SHAPE_SEEDS[x[2]]) < 20 for x in menus)
    assert P.SHAPE_SEEDS["regime"] == 697300 and P.LEVELS == (0.5, 1.0, 1.5, 2.5) and P.B == 1000


def test_dry_tasks_are_on_the_smoke_block_and_one_of_each_kind():
    t = P.dry_tasks()
    assert [x[0] for x in t] == ["seed", "menu", "level0"]
    assert all(x[1] in P.DRY_BLOCK for x in t)


def test_the_runner_refuses_on_the_laptop():
    bad = P.refusals("0" * 40, None)
    assert any("platform" in b for b in bad) and any("wheel" in b for b in bad)
