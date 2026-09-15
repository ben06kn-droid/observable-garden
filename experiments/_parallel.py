"""Run independent experiment tasks across processes, checkpointing each finished cell.

A cell is a batch of independent tasks whose results belong together, typically
every draw for one grid point. Each finished cell is written to its own file in
`checkpoint_dir`, so an interrupted run (a closed laptop, a reclaimed spot
instance) resumes from the unfinished cells instead of from zero. Results come
back in task order, and each task carries its own seed, so a parallel run
reproduces a serial one exactly.

Task functions must be defined at module level, because worker processes import
them by name, and should return small picklable results. Call run_cells from a
module or script with an `if __name__ == "__main__":` guard, not from code piped
into `python -`: on macOS, workers start by re-importing the parent's main file. Workers get one BLAS
thread each unless the environment already says otherwise: many single-threaded
workers beat a few processes competing for the same cores.
"""
from __future__ import annotations

import os
import pickle
import re
import time
from collections.abc import Callable, Hashable, Sequence
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


def default_workers() -> int:
    return max(1, (os.cpu_count() or 2) - 1)


def _checkpoint_path(directory: Path, key: Hashable) -> Path:
    parts = key if isinstance(key, tuple) else (key,)
    return directory / ("_".join(re.sub(r"[^A-Za-z0-9.+-]", "-", str(p)) for p in parts) + ".pkl")


def _save(path: Path, value) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "wb") as f:
        pickle.dump(value, f)
    os.replace(tmp, path)


def run_cells(
    fn: Callable,
    cells: dict[Hashable, Sequence[tuple]],
    checkpoint_dir: str | Path | None = None,
    workers: int | None = None,
    verbose: bool = True,
) -> dict[Hashable, list]:
    """Apply fn(*task) to every task in every cell across worker processes.

    Returns {cell: [results in task order]}, with cells in the order given. Tasks from all
    unfinished cells share one pool, so small cells don't leave cores idle.
    """
    directory = Path(checkpoint_dir) if checkpoint_dir is not None else None
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)

    results: dict[Hashable, list] = {}
    pending = []
    for key, tasks in cells.items():
        path = _checkpoint_path(directory, key) if directory is not None else None
        if path is not None and path.exists():
            with open(path, "rb") as f:
                results[key] = pickle.load(f)
        elif not tasks:
            results[key] = []
        else:
            pending.append(key)
    if verbose and directory is not None and len(results) > 0:
        print(f"resuming: {len(results)} of {len(cells)} cells already done in {directory}", flush=True)

    if pending:
        for var in _THREAD_VARS:
            os.environ.setdefault(var, "1")
        t0 = time.time()
        pool = ProcessPoolExecutor(max_workers=workers or default_workers())
        try:
            futures = {key: [pool.submit(fn, *task) for task in cells[key]] for key in pending}
            owner = {fut: key for key, futs in futures.items() for fut in futs}
            left = {key: len(futs) for key, futs in futures.items()}
            for fut in as_completed(owner):
                fut.result()
                key = owner[fut]
                left[key] -= 1
                if left[key]:
                    continue
                results[key] = [f.result() for f in futures[key]]
                if directory is not None:
                    _save(_checkpoint_path(directory, key), results[key])
                if verbose:
                    done = len(pending) - sum(1 for n in left.values() if n)
                    print(f"  cell {key}: {len(results[key])} tasks, {done}/{len(pending)} cells "
                          f"({time.time() - t0:.0f}s)", flush=True)
        except BaseException:
            pool.shutdown(wait=False, cancel_futures=True)
            raise
        pool.shutdown()
    return {key: results[key] for key in cells}
