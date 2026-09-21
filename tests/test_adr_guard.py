"""The 7.4 ancestor guard refuses to build features against an unregistered state.

Each refusal is constructed rather than waited for: a throwaway clone lets the
tests move HEAD behind the registration and dirty the registration files without
touching the working checkout.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "data"))

from adr_guard import (REGISTRATION_COMMITS, REGISTRATION_PATHS,  # noqa: E402
                       RegistrationRefused, require_registered_features)

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


@pytest.fixture
def clone(tmp_path):
    dst = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(REPO), str(dst)],
                   check=True)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(["git", "-C", str(dst), "checkout", "-q", head], check=True)
    return dst


def test_passes_on_a_checkout_that_contains_the_registration(clone, capsys):
    require_registered_features(repo=clone)
    assert "adr_guard: PASS" in capsys.readouterr().out     # speaks when it passes


def test_refuses_when_head_is_behind_the_feature_list(clone):
    feature_list = REGISTRATION_COMMITS[0][1]
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", f"{feature_list}~1"],
                   check=True)
    with pytest.raises(RegistrationRefused, match="not an ancestor of HEAD"):
        require_registered_features(repo=clone)


def test_refuses_when_head_has_the_list_but_not_the_amendment(clone):
    feature_list = REGISTRATION_COMMITS[0][1]
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", feature_list], check=True)
    with pytest.raises(RegistrationRefused, match="amendment 1"):
        require_registered_features(repo=clone)


def test_refuses_an_unknown_registration_commit(clone):
    with pytest.raises(RegistrationRefused, match="not in this repository"):
        require_registered_features(repo=clone, commits=(("made up", "0" * 40),))


def test_refuses_a_working_tree_edit_of_the_registration(clone):
    p = clone / REGISTRATION_PATHS[0]
    p.write_text(p.read_text() + "\nan edit after the commit\n")
    with pytest.raises(RegistrationRefused, match="uncommitted changes"):
        require_registered_features(repo=clone)


def test_refuses_outside_a_git_checkout(tmp_path):
    with pytest.raises(RegistrationRefused, match="not a git checkout"):
        require_registered_features(repo=tmp_path)


def test_the_guard_is_outside_the_published_fingerprint():
    from experiments.code_state import CODE_PATHS
    assert not any(p == "data" or p.startswith("data/") for p in CODE_PATHS)
