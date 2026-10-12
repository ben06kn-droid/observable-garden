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


def test_batch4_is_sonnet_on_its_own_seeds():
    """Amendment 9's s3 re-run under the recalibrated sigma, seeds 501-580."""
    rows = ms.build_batch4()
    ms.verify_batch4(rows)
    assert len(rows) == 80
    assert rows[0][0] == 501 and rows[-1][0] == 580
    assert {m for _, _, _, _, m in rows} == {"claude-sonnet-5"}
    assert {c for _, c, _, _, _ in rows} == {"s3"}


def test_batch5_emits_one_model_and_both_draw_the_same_seeds():
    """Amendment 12 defers the Fable arm to the allowance reset and runs Opus on
    the same seeds, so the two are paired by DGP draw. That pairing is the reason
    the deferral is harmless, so it is pinned here rather than left to the caller.
    The run id carries the model tag, so the pair never shares a directory."""
    opus, fable = ms.build_batch5("claude-opus-5"), ms.build_batch5("claude-fable-5-1")
    ms.verify_batch5(opus, "claude-opus-5")
    ms.verify_batch5(fable, "claude-fable-5-1")
    assert {m for _, _, _, _, m in opus} == {"claude-opus-5"}
    assert {m for _, _, _, _, m in fable} == {"claude-fable-5-1"}
    assert [r[0] for r in opus] == [r[0] for r in fable] == list(range(581, 661))
    assert [r[2] for r in opus] == [r[2] for r in fable]      # same arm on each seed


def test_batch5_refuses_a_model_it_does_not_own():
    with pytest.raises(SystemExit, match="batch 5 model must be one of"):
        ms.build_batch5("claude-sonnet-5")


def test_batch5_seeds_do_not_collide_with_any_earlier_batch():
    taken = ({r[0] for r in ms.build()} | {r[0] for r in ms.replacement_rows()}
             | {r[0] for r in ms.build_batch3()} | {r[0] for r in ms.build_batch4()})
    assert not (taken & {r[0] for r in ms.build_batch5()})


def test_batch5_seeds_are_drawable():
    """Amendment 11 extended the draw to 661 values so seed 660 exists at all."""
    pytest.importorskip(
        "claude_agent_sdk",
        reason="experiments.e_agent pulls in searchers.llm_agent, which imports the\n    agent SDK at module level. Absent on EC2 by design, so this test skips there.")
    from experiments.e_agent import dgp_seeds
    seeds = dgp_seeds()
    assert len(seeds) > 660
    assert len(set(seeds.tolist())) == len(seeds)


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
    pytest.importorskip(
        "claude_agent_sdk",
        reason="experiments.e_agent pulls in searchers.llm_agent, which imports the\n    agent SDK at module level. Absent on EC2 by design, so this test skips there.")
    from experiments.e_agent import MASTER_SEED, dgp_seeds
    seeds = dgp_seeds()
    assert len(seeds) > 500                           # index 500 exists
    earlier = np.random.default_rng(MASTER_SEED).integers(0, 2**31 - 1, size=500)
    np.testing.assert_array_equal(seeds[:500], earlier)
    assert len(set(seeds.tolist())) == len(seeds)
