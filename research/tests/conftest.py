"""Tests of the research record (research/). They run with research/ as the working directory,
as the research code always ran from the directory holding prereg/, runs/ and data/; the
machine-local data stays at <repo>/data (environments._paths.LOCAL_DATA).

The switch is module-scoped and autouse, so it is in place before any module-scoped fixture
reads a relative path, and it is undone after each module. It also puts the repository root, the
engine and research/ on PYTHONPATH, so a test that runs research code in a subprocess
(`python -m experiments.<name>`) imports what pytest imports."""
import os
from pathlib import Path

import pytest

RESEARCH = Path(__file__).resolve().parent.parent
REPO = RESEARCH.parent
PATHS = [str(REPO), str(REPO / "quixote" / "engine"), str(RESEARCH)]


@pytest.fixture(autouse=True, scope="module")
def _research_cwd():
    mp = pytest.MonkeyPatch()
    mp.chdir(RESEARCH)
    old = os.environ.get("PYTHONPATH")
    mp.setenv("PYTHONPATH", os.pathsep.join(PATHS + ([old] if old else [])))
    yield
    mp.undo()
