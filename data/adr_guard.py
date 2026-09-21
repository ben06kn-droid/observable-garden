"""The ancestor guard: no 7.4 bar is opened before its registration is committed.

    from adr_guard import require_registered_features
    require_registered_features()          # first line of any feature-building entry point

Every 7.4 feature-building entry point calls this before it reads a bar. It
refuses, by raising, unless:

1. every registration commit below is an ancestor of HEAD, so the code that is
   about to run was written on top of the committed feature list and its
   amendments, not beside them or before them; and
2. the registration files have no uncommitted changes, so what runs is what is
   committed and not a working-tree edit of it.

It prints one line when it passes as well as when it refuses. A check that is
silent when it does not fire cannot be told apart from a check that never ran.

It lives in data/ beside the fetcher, outside `experiments.code_state.CODE_PATHS`,
so adding it moves no published fingerprint.

A new amendment to prereg/adr-features.md is added to REGISTRATION_COMMITS in the
commit that follows it. The guard cannot name the commit that contains it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (what, full commit hash). Full hashes, so an abbreviation can never become
# ambiguous as history grows.
REGISTRATION_COMMITS = (
    ("feature list", "2fd2decb9b382aee41f05398b5bae22eaae81234"),
    ("feature amendment 1: costs and corporate actions",
     "897d5de9f8875af28a810d1328cd085ccc466dcd"),
)

REGISTRATION_PATHS = ("prereg/adr-features.md", "prereg/adr-universe.md")


class RegistrationRefused(RuntimeError):
    """Raised instead of building features against an unregistered state."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def require_registered_features(repo: Path = REPO,
                                commits=REGISTRATION_COMMITS,
                                paths=REGISTRATION_PATHS,
                                quiet: bool = False) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise RegistrationRefused(f"not a git checkout at {repo}; refusing to build features")

    for what, sha in commits:
        exists = _git(repo, "cat-file", "-e", f"{sha}^{{commit}}")
        if exists.returncode != 0:
            raise RegistrationRefused(
                f"registration commit {sha[:7]} ({what}) is not in this repository; "
                "refusing to build features")
        anc = _git(repo, "merge-base", "--is-ancestor", sha, "HEAD")
        if anc.returncode != 0:
            raise RegistrationRefused(
                f"registration commit {sha[:7]} ({what}) is not an ancestor of HEAD "
                f"{head.stdout.strip()[:7]}; refusing to build features")

    dirty = _git(repo, "status", "--porcelain", "--", *paths).stdout.strip()
    if dirty:
        raise RegistrationRefused(
            "the registration has uncommitted changes, so what would run is not what is "
            f"committed; refusing to build features:\n{dirty}")

    if not quiet:
        print(f"adr_guard: PASS -- {len(commits)} registration commits are ancestors of "
              f"HEAD {head.stdout.strip()[:7]}; {', '.join(paths)} unmodified", flush=True)
