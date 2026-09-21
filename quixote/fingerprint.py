"""How a Don Quixote run is pinned to the code that produced it.

`quixote` is deliberately **absent** from `experiments.code_state.CODE_PATHS`.
Adding it there would move every published fingerprint -- `b3-models`,
`b4-s3-recal`, `b5-opus` and the covered rows of `b2-arms` all carry fingerprints
computed without it -- and a fingerprint that moves for a reason unrelated to the
run it pins is worse than no fingerprint.

So quixote runs carry their own, over a wider set of paths than the existing one:
`quixote` plus **everything quixote imports**. The dependency is one-way --
nothing in `garden`, `estimator`, `environments` or `searchers` imports
`quixote` -- but a change in `garden` still changes what a quixote run does, so
it has to be inside the hash.
"""
from __future__ import annotations

import hashlib

from experiments.code_state import (CODE_PATHS, code_fingerprint, head_sha,
                                    prereg_design_md5)

QUIXOTE_PATHS = ("quixote", "garden", "estimator", "environments", "searchers")


def quixote_fingerprint() -> str:
    """A fingerprint over QUIXOTE_PATHS, computed the same way `code_state` does
    so the two are comparable, and salted with a tag so it can never be mistaken
    for a CODE_PATHS fingerprint in a stored record."""
    inner = code_fingerprint(paths=QUIXOTE_PATHS) if _accepts_paths() else None
    if inner is None:
        raise RuntimeError(
            "experiments.code_state.code_fingerprint does not accept a paths "
            "argument; quixote must not widen CODE_PATHS to compensate, because "
            "that would move published fingerprints. Add the parameter instead.")
    return hashlib.sha256(f"quixote:{inner}".encode()).hexdigest()[:16]


def _accepts_paths() -> bool:
    import inspect
    return "paths" in inspect.signature(code_fingerprint).parameters


def quixote_code_state() -> dict:
    return {"head": head_sha(), "quixote_fingerprint": quixote_fingerprint(),
            "prereg_design_md5": prereg_design_md5(),
            "paths": list(QUIXOTE_PATHS),
            "note": "quixote is not in experiments.code_state.CODE_PATHS by "
                    "design; see quixote/fingerprint.py"}
