"""Where things live on disk, in one place (re-exported as `quixote.paths`).

- `REPO`: the repository root (a source checkout or an editable install).
- `LOCAL_DATA`: machine-local data that is never committed (raw downloads, pinned feature
  arrays, class tables, planted caches). It stays at `<repo>/data/`, where it has always been;
  set `OG_LOCAL_DATA` to put it elsewhere.
- `RESEARCH`: the research record, `research/`. `RESEARCH_DATA` holds its committed data files
  (download manifests and the like).

This module imports nothing from the project, so any module may import it.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]          # <repo>/quixote/engine/environments/_paths.py
LOCAL_DATA = Path(os.environ.get("OG_LOCAL_DATA", REPO / "data"))
RESEARCH = REPO / "research"
RESEARCH_DATA = RESEARCH / "data"
