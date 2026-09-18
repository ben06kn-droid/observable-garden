"""experiments/worker_rows.py — the parallel row assignment.

The property that matters for correctness is disjointness: two workers must
never receive the same row, because both would then run into the same run
directory. RunPaths is the backstop, but it should never be reached.
"""
import pytest

from experiments.worker_rows import assign, block_of, read_rows

SCHEDULE = "experiments/schedule_240.txt"


@pytest.fixture(scope="module")
def rows():
    return read_rows(SCHEDULE)


@pytest.mark.parametrize("workers", [1, 2, 3, 4, 5, 8, 16])
@pytest.mark.parametrize("start", [0, 11, 91, 240])
def test_workers_never_share_a_row(rows, workers, start):
    parts = assign(rows, start, workers)
    flat = [n for p in parts for n in p]
    assert len(flat) == len(set(flat))                  # disjoint
    assert sorted(flat) == list(range(start, len(rows)))  # and complete
    assert len(parts) == workers


@pytest.mark.parametrize("workers", [1, 2, 3, 4, 8])
def test_every_worker_rotates_through_every_cell(rows, workers):
    """Amendment 6: dealing within a block, rather than striding the flat row
    order, is what keeps each worker's rotation complete. Striding gave workers
    only one budget dose at N=4 and none at all at N=8."""
    parts = assign(rows, 11, workers)
    all_cells = {block_of(rows[n]) for n in range(11, len(rows))}
    for k, idx in enumerate(parts):
        assert {block_of(rows[n]) for n in idx} == all_cells, f"worker {k} is short a cell"


@pytest.mark.parametrize("workers", [2, 3, 4, 8])
def test_each_block_is_split_evenly(rows, workers):
    """Round-robin within a block means worker loads differ by at most one run
    per block, so no worker is left holding a whole cell."""
    parts = assign(rows, 11, workers)
    per = {}
    for k, idx in enumerate(parts):
        for n in idx:
            per.setdefault(block_of(rows[n]), [0] * workers)[k] += 1
    for cell, counts in per.items():
        assert max(counts) - min(counts) <= 1, f"{cell} is unevenly split: {counts}"


def test_one_worker_is_the_whole_schedule(rows):
    """--workers 1 must stay exactly today's behaviour."""
    assert assign(rows, 11, 1) == [list(range(11, len(rows)))]


def test_assignment_is_deterministic(rows):
    """A stopped worker resumes by re-running with the same start and workers,
    so the same three inputs must always reproduce the same row set."""
    assert assign(rows, 11, 4) == assign(rows, 11, 4)


def test_worker_rows_are_ascending(rows):
    """Ascending order preserves the rotation order the schedule fixes."""
    for idx in assign(rows, 11, 4):
        assert idx == sorted(idx)


@pytest.mark.parametrize("workers,start", [(0, 0), (-1, 0)])
def test_bad_worker_count_is_refused(rows, workers, start):
    with pytest.raises(ValueError, match="workers must be"):
        assign(rows, start, workers)


def test_start_past_the_end_is_refused(rows):
    with pytest.raises(ValueError, match="outside the schedule"):
        assign(rows, len(rows) + 1, 2)


def test_comments_do_not_shift_indices(tmp_path):
    """The amendment-5 replacement row carries a comment line above it. Index n
    here must mean the same row run_arms.sh reaches with --start n."""
    f = tmp_path / "s.txt"
    f.write_text("# header\n80 s0 count - m\n#\n# note\n81 s0 gate - m\n\n82 s0 count - m\n")
    assert [r[0] for r in read_rows(f)] == ["80", "81", "82"]
