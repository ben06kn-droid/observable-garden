"""The second version-2 pilot runner's task list (no panels built)."""
from experiments import ml_v2_pilot2_2026_10_09 as P


def test_the_task_list_and_settings_are_the_registered_ones():
    t = P.tasks()
    seeds = [x for x in t if x[0] == "seed"]
    assert len(seeds) == 350 and {x[1] for x in seeds} == set(range(698000, 698350))
    assert [x[1] for x in t if x[0] == "level0"] == list(range(698400, 698500))
    assert P.LEVELS == (1.0, 1.5) and P.RATES == (0.3, 0.1, 0.03)
    assert P.L_GRID == {"L": (1.0, 3.0, 10.0, 30.0)}
    assert P.MEMORY_SETS == {"M1": ("roll252", "roll756", "expand"), "M2": ("roll756", "expand")}
    assert P.COST_ARMS == {"registered": 1.0, "high": 5.0}
    assert all(x[1] in P.DRY_BLOCK for x in P.dry_tasks())
