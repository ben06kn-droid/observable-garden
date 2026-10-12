"""`learn2` is Sancho's former package name (model version 2). The research record imports
`learn2`; the package is now `sancho` at the repository's top level.

This alias makes `learn2` and every `learn2.<module>` the SAME module objects as `sancho` and
`sancho.<module>`, so state set through one name (for example `learner.FIRST`) is seen through
the other. Research runners that check `learn2/` git blobs at HEAD run from their pinned commits
(see research/README.md), not from this tree.
"""
import importlib
import sys

import sancho as _sancho

for _name in ("blocks", "families", "leak", "learner", "states", "timing", "views"):
    _mod = importlib.import_module(f"sancho.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _mod
    globals()[_name] = _mod

__path__ = list(_sancho.__path__)
