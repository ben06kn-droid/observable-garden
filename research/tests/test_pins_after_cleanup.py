"""The 2026-10 cleanup moved the engine to quixote/engine/, renamed learn2/ to sancho/ and
moved this record to research/. Registered runners pin git blobs by their pre-cleanup paths
(learn2/..., learn/..., environments/...), so they refuse at the new layout and are reproduced
from their pinned commits (research/README.md). These tests check, instead of the pins at HEAD:

1. every pinned blob is still exactly what it pinned, at the tag pre-cleanup-2026-10-12;
2. the moved code is the tagged code, line for line, except for the import and path lines the
   cleanup had to change (the learn2 -> sancho imports, the environments._paths imports and the
   machine-local data paths). So the cleanup changed where code lives, not what it computes.

Both need the tag in the local clone; they skip without it (a shallow CI checkout)."""
import difflib
import re
import subprocess
from pathlib import Path

import pytest

TAG = "pre-cleanup-2026-10-12"
REPO = Path(__file__).resolve().parents[2]


def _git(*a):
    return subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True)


have_tag = pytest.mark.skipif(_git("rev-parse", "-q", "--verify", f"{TAG}^{{commit}}").returncode != 0,
                              reason=f"the tag {TAG} is not in this clone")


def _pin_tables():
    from experiments import binance_insample_read as BR
    from experiments import french_insample_read as FR
    from experiments import ml_confirm_ridge_stack as RS
    from experiments import ml_v2_confirm_2026_10_09 as V2
    return {"ml_v2_confirm.PINNED_V2": V2.PINNED_V2, "ml_confirm_ridge_stack.PINNED_BLOBS": RS.PINNED_BLOBS,
            "french_insample_read.PINNED_BLOBS": FR.PINNED_BLOBS, "binance_insample_read.PINNED_BLOBS": BR.PINNED_BLOBS}


@have_tag
def test_every_pinned_blob_holds_at_the_pre_cleanup_tag():
    for table, pins in _pin_tables().items():
        for path, blob in pins.items():
            got = _git("rev-parse", f"{TAG}:{path}").stdout.strip()
            assert got == blob, f"{table}: {path} at {TAG} is {got}, pinned {blob}"


# where each pre-cleanup package lives now
MOVED = {"learn2": "sancho", "environments": "quixote/engine/environments",
         "estimator": "quixote/engine/estimator", "searchers": "quixote/engine/searchers",
         "garden": "quixote/engine/garden"}
# the only kinds of line the cleanup changed inside moved code
ALLOWED = [re.compile(p) for p in (
    r"^\s*$",
    r"^\s*from (learn2|sancho)(\.| import)",                            # learn2 -> sancho
    r"^\s*from environments\._paths import ",                           # the one path module
    r"^\s*from (learn|sancho)\.(inputs|families) import FAMILIES, PAIRS",  # the family map's home
    r"^REPO = Path\(__file__\)\.resolve\(\)\.parent\.parent$",           # replaced by environments._paths
    r'\b(LOCAL_DATA|RESEARCH_DATA)\b|Path\(__file__\)\.resolve\(\)\.parent\.parent / ',  # data paths
    r'^\s*"data" / "planted_cache"$', r'REPO / "data" / ', r'^\s*p = RESEARCH_DATA / man$',
    r'^CACHE_DIR = (REPO|Path\(__file__\)\.resolve\(\)\.parent\.parent) / "\.cache" / "oracle"$',
)]


def _changed_lines(old: str, new: str) -> list[str]:
    out = []
    for ln in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0):
        if ln.startswith(("---", "+++", "@@")):
            continue
        if ln[:1] in "+-":
            out.append(ln[1:])
    return out


@have_tag
def test_the_moved_code_is_the_tagged_code_but_for_imports_and_data_paths():
    files = _git("ls-tree", "-r", "--name-only", TAG, "--", *MOVED).stdout.split()
    assert len(files) > 40
    for old_path in files:
        if not old_path.endswith(".py"):
            continue
        top, rest = old_path.split("/", 1)
        new_path = REPO / MOVED[top] / rest
        assert new_path.exists(), f"{old_path} has no counterpart at {new_path}"
        old = _git("show", f"{TAG}:{old_path}").stdout
        bad = [ln for ln in _changed_lines(old, new_path.read_text()) if not any(r.search(ln) for r in ALLOWED)]
        assert not bad, f"{old_path} -> {new_path.relative_to(REPO)} changed beyond imports and paths: {bad[:5]}"
