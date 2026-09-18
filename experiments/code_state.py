"""The code state a run was produced under.

Every run records it in config.json, and run_arms.sh refuses to continue a batch
across a code change unless --allow-code-change is passed.

The comparison cannot be on HEAD itself. run_arms.sh commits after every run, so
HEAD moves constantly while the code does not: a guard on HEAD would fire on the
second run of every batch and never mean anything. The fingerprint therefore
covers only what determines how a run behaves, and excludes runs/, which is
where the batch's own commits land.

The pre-registration contributes the md5 of its sections 1-5 rather than the
file, because section 6 is the amendment log: it records decisions but changes
no prompt, tool, or pinned value, so appending an amendment must not invalidate
a batch that is mid-flight. Sections 1-5 are exactly the part a run reads.

    python -m experiments.code_state --field fingerprint
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Excludes runs/ and figures/ (outputs), note/ and the top-level .md files
# (prose). prereg/ is handled separately, by section, just below.
CODE_PATHS = ("environments", "estimator", "garden", "searchers", "experiments",
              "pyproject.toml")

PREREG_FILE = ROOT / "prereg" / "AGENT_PROMPTS.md"
AMENDMENTS_HEADING = "## 6. Amendments"


def _git(*args: str) -> str:
    p = subprocess.run(("git", *args), cwd=ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def head_sha() -> str:
    return _git("rev-parse", "HEAD").strip() or "unknown"


def prereg_design_md5() -> str:
    """md5 of sections 1-5 of AGENT_PROMPTS.md -- the design a run executes.

    Section 6 is deliberately excluded. An amendment is a record of a decision;
    it alters no prompt, tool, or pinned value, and stopping four live workers
    to write one down would make the log costly to keep honest."""
    try:
        text = PREREG_FILE.read_text()
    except OSError:
        return "missing"
    design = text.split(AMENDMENTS_HEADING)[0]
    return hashlib.md5(design.encode()).hexdigest()


def dirty_paths() -> list[str]:
    """Tracked modifications plus untracked files, over the code paths and the
    pre-registration. The prereg is watched here even though only its design
    sections feed the fingerprint: an uncommitted edit to it is worth seeing."""
    out = _git("status", "--porcelain", "--", *CODE_PATHS, "prereg").strip()
    return sorted(line[3:].strip() for line in out.splitlines() if line.strip())


def code_fingerprint() -> str:
    """sha256 over: the committed tree of each code path, the diff against it,
    the bytes of every untracked file under it, and the prereg design md5."""
    h = hashlib.sha256()
    for p in CODE_PATHS:
        h.update(f"{p}:{_git('rev-parse', f'HEAD:{p}').strip()}\n".encode())
    h.update(_git("diff", "HEAD", "--", *CODE_PATHS).encode())
    for rel in _git("ls-files", "--others", "--exclude-standard", "--",
                    *CODE_PATHS).split("\n"):
        rel = rel.strip()
        # Compiled bytecode is not source. It is normally filtered by
        # --exclude-standard via .gitignore, but resting a mid-batch guard on an
        # ignore rule is fragile: in a tree without one, the first import writes
        # experiments/__pycache__/*.pyc and the fingerprint moves at an unchanged
        # HEAD, stopping every worker for a change that never happened.
        if not rel or "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        f = ROOT / rel
        if f.is_file():
            h.update(f"{rel}:".encode())
            h.update(hashlib.sha256(f.read_bytes()).hexdigest().encode())
            h.update(b"\n")
    h.update(f"prereg-design:{prereg_design_md5()}\n".encode())
    return h.hexdigest()[:16]


def code_state() -> dict:
    d = dirty_paths()
    return {"head": head_sha(), "fingerprint": code_fingerprint(),
            "prereg_design_md5": prereg_design_md5(),
            "dirty": bool(d), "dirty_paths": d}


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", choices=("fingerprint", "head", "prereg_design_md5", "json"),
                    default="json")
    a = ap.parse_args(argv)
    s = code_state()
    print(json.dumps(s) if a.field == "json" else s[a.field])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
