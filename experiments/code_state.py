"""The code state a run was produced under.

Every run records it in config.json, and run_arms.sh refuses to continue a batch
across a code change unless --allow-code-change is passed.

The comparison cannot be on HEAD itself. run_arms.sh commits after every run, so
HEAD moves constantly while the code does not: a guard on HEAD would fire on the
second run of every batch and never mean anything. The fingerprint therefore
covers only the paths that determine how a run behaves -- prereg among them,
since the prompts are read from it at runtime -- and excludes runs/, which is
where the batch's own commits land.

It covers committed content, uncommitted edits, and untracked files under those
paths, because all three change what executes.

    python -m experiments.code_state --field fingerprint
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Excludes runs/ and figures/ (outputs), note/ and the top-level .md files
# (prose). prereg/ is in: read at runtime, so editing it changes the run.
CODE_PATHS = ("environments", "estimator", "garden", "searchers", "experiments",
              "prereg", "pyproject.toml")


def _git(*args: str) -> str:
    p = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def head_sha() -> str:
    return _git("rev-parse", "HEAD").strip() or "unknown"


def dirty_paths() -> list[str]:
    """Tracked modifications plus untracked files, under CODE_PATHS only."""
    out = _git("status", "--porcelain", "--", *CODE_PATHS).strip()
    return sorted(line[3:].strip() for line in out.splitlines() if line.strip())


def code_fingerprint() -> str:
    """sha256 over: the committed tree of each code path, the diff against it,
    and the bytes of every untracked file under it."""
    h = hashlib.sha256()
    for p in CODE_PATHS:
        h.update(f"{p}:{_git('rev-parse', f'HEAD:{p}').strip()}\n".encode())
    h.update(_git("diff", "HEAD", "--", *CODE_PATHS).encode())
    for rel in _git("ls-files", "--others", "--exclude-standard", "--",
                    *CODE_PATHS).split("\n"):
        rel = rel.strip()
        if not rel:
            continue
        f = ROOT / rel
        if f.is_file():
            h.update(f"{rel}:".encode())
            h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
            h.update(b"\n")
    return h.hexdigest()[:16]


def code_state() -> dict:
    d = dirty_paths()
    return {"head": head_sha(), "fingerprint": code_fingerprint(),
            "dirty": bool(d), "dirty_paths": d}


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", choices=("fingerprint", "head", "json"), default="json")
    a = ap.parse_args(argv)
    s = code_state()
    print(json.dumps(s) if a.field == "json" else s[a.field])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
