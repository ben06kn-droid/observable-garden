"""experiments/_parallel.py: parallel results equal serial ones, in order, and finished cells resume."""
import pytest

from experiments._parallel import run_cells


def _affine(x, k):  # module level, so worker processes can import it
    return x * k + 1


def _explode(*_):
    raise AssertionError("this task must not run")


def test_parallel_results_match_serial_in_task_and_cell_order():
    cells = {("a", 2): [(i, 2) for i in range(20)], ("b", 3): [(i, 3) for i in range(7)], ("empty",): []}
    out = run_cells(_affine, cells, workers=2, verbose=False)
    assert out == {key: [_affine(*task) for task in tasks] for key, tasks in cells.items()}
    assert list(out) == list(cells)


def test_finished_cells_are_loaded_not_recomputed(tmp_path):
    cells = {"x": [(i, 5) for i in range(4)], ("y", 0.5): [(i, 0.5) for i in range(3)]}
    first = run_cells(_affine, cells, checkpoint_dir=tmp_path, workers=2, verbose=False)
    assert run_cells(_explode, cells, checkpoint_dir=tmp_path, workers=2, verbose=False) == first


def test_e11_parallel_run_reproduces_its_serial_run(tmp_path):
    import numpy as np

    from experiments.e11_power_vs_N_pinned import run

    serial = run(n_draws=2, B=50, verbose=False)
    parallel = run(n_draws=2, B=50, verbose=False, workers=2, checkpoint_dir=tmp_path)
    assert list(parallel) == list(serial)
    for key in serial:
        for field in serial[key]:
            np.testing.assert_array_equal(parallel[key][field], serial[key][field])


def test_a_failing_task_raises():
    with pytest.raises(AssertionError, match="must not run"):
        run_cells(_explode, {"x": [(1,)]}, workers=1, verbose=False)
