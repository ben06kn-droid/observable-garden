"""experiments/make_schedule.py — amendment 4's quotas, amendment 5's replacements.

The schedule is generated rather than hand-edited, so these guard the generator:
a hand-appended row would make the committed file unreproducible, and a silently
shifted line index would repoint a --start on resume at the wrong run.
"""
import numpy as np
import pytest

import experiments.make_schedule as ms


def test_base_schedule_still_matches_amendment_4():
    rows = ms.build()
    ms.verify(rows)                     # raises on any quota, count or contiguity defect
    assert len(rows) == 240
    assert rows[0][0] == 80 and rows[-1][0] == 319


def test_replacement_restores_the_void_runs_cell():
    base, reps = ms.build(), ms.replacement_rows()
    ms.verify_replacements(base, reps)
    void = next(r for r in base if r[0] == 89)
    assert tuple(reps[0][1:]) == tuple(void[1:])      # same config, arm and dose
    assert reps[0][0] == 500


def test_the_void_row_is_kept_so_line_indices_do_not_shift():
    """A resume passes --start as a line index into the schedule. Deleting the
    void row would silently repoint every later index by one."""
    seeds = [r[0] for r in ms.build()]
    assert 89 in seeds
    assert seeds[11] == 91                            # the resume line after seed 90


def test_batch3_crosses_the_arms_with_the_models():
    """Amendment 7: {control, gate, pushed} × {sonnet, fable}, 30 per cell,
    180 rows, seeds 320-499, opening cycle covering every cell."""
    rows = ms.build_batch3()
    ms.verify_batch3(rows)              # raises on any quota, count or seed defect
    assert len(rows) == 180
    assert rows[0][0] == 320 and rows[-1][0] == 499
    assert len({(a, m) for _, _, a, _, m in rows[:len(ms.B3_CELLS)]}) == 6


def test_batch3_includes_the_pushed_arm_on_both_models():
    cells = {(a, m) for _, _, a, _, m in ms.build_batch3()}
    assert ("pushed", "claude-sonnet-5") in cells
    assert ("pushed", "claude-fable-5-1") in cells


def test_batch3_seeds_do_not_collide_with_batch_2_or_its_replacement():
    """Seed 500 replaced void seed 89 precisely because 320-499 were spoken for."""
    taken = {r[0] for r in ms.build()} | {r[0] for r in ms.replacement_rows()}
    assert not (taken & {r[0] for r in ms.build_batch3()})


def _reps(**over):
    spec = {"void_seed": 89, "seed": 500, "config": "s0", "arm": "budget",
            "budget": 20, "why": "test"}
    spec.update(over)
    return [spec]


@pytest.mark.parametrize("over,match", [
    ({"arm": "gate", "budget": None}, "changes the cell"),
    ({"budget": 180}, "changes the cell"),
    ({"seed": 90}, "collides"),
    ({"seed": 400}, "allocated to batch 3"),
    ({"void_seed": 79}, "not in the schedule"),
])
def test_a_bad_replacement_is_refused(monkeypatch, over, match):
    monkeypatch.setattr(ms, "REPLACEMENTS", _reps(**over))
    with pytest.raises(SystemExit, match=match):
        ms.verify_replacements(ms.build(), ms.replacement_rows())


def test_replacement_seed_is_drawable_and_leaves_earlier_draws_alone():
    """Amendment 5 puts the replacement at index 500, past the 500 draws the
    stream used to take. Extending it must not move any earlier seed."""
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    seeds = dgp_seeds()
    assert len(seeds) > 500                           # index 500 exists
    earlier = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=500)
    np.testing.assert_array_equal(seeds[:500], earlier)
    assert len(set(seeds.tolist())) == len(seeds)
