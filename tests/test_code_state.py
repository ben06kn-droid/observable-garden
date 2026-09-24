"""experiments/code_state.py — what the mid-batch guard watches.

The fingerprint decides whether run_arms.sh lets a batch continue, so the cost
of getting CODE_PATHS wrong is asymmetric and wrong in both directions: too
narrow and a real change to the harness passes unnoticed, too wide and ordinary
work halts four live workers. It was too wide once -- the whole of experiments/
-- and editing analyze_agent.py during batch 4 stopped it for a file no run
imports.

The end-to-end probes run against a throwaway repo rather than this one:
code_state resolves ROOT from its own location, so probing in place would move
the real tree's fingerprint, which is precisely the thing that must not happen
while a batch is running.
"""
import subprocess
import sys
from pathlib import Path

from experiments.code_state import CODE_PATHS

REPO = Path(__file__).resolve().parent.parent


def covered(rel: str) -> bool:
    """Whether CODE_PATHS contains this file, matching by prefix as git does."""
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in CODE_PATHS)


# -- what must be inside, and what must not ----------------------------------

def test_the_harness_and_runner_are_watched():
    for rel in ("experiments/e_agent.py", "experiments/run_arms.sh",
                "experiments/worker_rows.py", "experiments/code_state.py",
                "environments/dgp.py", "environments/sandbox.py",
                "garden/watch.py", "garden/spec_class.py",
                "searchers/llm_agent.py", "estimator/bootstrap.py",
                "pyproject.toml"):
        assert covered(rel), f"{rel} must be inside the fingerprint"


def test_analysis_and_figure_code_is_not_watched():
    """The defect this file exists for. None of these is imported by a run."""
    for rel in ("experiments/analyze_agent.py", "experiments/make_schedule.py",
                "experiments/plot_headline_figures.py", "experiments/chain.sh",
                "experiments/schedule_80_s3.txt"):
        assert not covered(rel), f"{rel} must be outside the fingerprint"


def test_every_watched_path_exists():
    """A typo in CODE_PATHS is silent: git prints nothing for a path it cannot
    resolve, so the entry contributes an empty hash rather than an error."""
    for p in CODE_PATHS:
        assert (REPO / p).exists(), f"CODE_PATHS names a missing path: {p}"


# -- the property itself, against a throwaway repo ---------------------------

def _sandbox(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    for d in ("environments", "estimator", "garden", "searchers"):
        (root / d).mkdir()
        (root / d / "__init__.py").write_text("")
    (root / "experiments" / "code_state.py").write_bytes(
        (REPO / "experiments" / "code_state.py").read_bytes())
    for name in ("__init__.py", "e_agent.py", "worker_rows.py"):
        (root / "experiments" / name).write_text("# stub\n")
    (root / "experiments" / "run_arms.sh").write_text("# stub\n")
    (root / "experiments" / "analyze_agent.py").write_text("# stub\n")
    (root / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    (root / "prereg").mkdir()
    (root / "prereg" / "AGENT_PROMPTS.md").write_text("# design\n## 6. Amendments\nx\n")
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n")
    run = lambda *a: subprocess.run(a, cwd=root, capture_output=True, text=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "harness")
    return root


def _fingerprint(root: Path) -> str:
    p = subprocess.run([sys.executable, "experiments/code_state.py",
                        "--field", "fingerprint"],
                       cwd=root, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def test_editing_an_analysis_script_leaves_the_fingerprint_alone(tmp_path):
    root = _sandbox(tmp_path)
    before = _fingerprint(root)
    (root / "experiments" / "analyze_agent.py").write_text("# stub\n# edited\n")
    assert _fingerprint(root) == before


def test_editing_the_harness_still_moves_the_fingerprint(tmp_path):
    """Narrowing must not disarm the guard for a change that does matter."""
    root = _sandbox(tmp_path)
    before = _fingerprint(root)
    (root / "experiments" / "e_agent.py").write_text("# stub\n# edited\n")
    assert _fingerprint(root) != before


def test_an_untracked_analysis_script_leaves_the_fingerprint_alone(tmp_path):
    """Untracked files under a watched path count, so a new figure script in
    experiments/ must not count either."""
    root = _sandbox(tmp_path)
    before = _fingerprint(root)
    (root / "experiments" / "plot_new_thing.py").write_text("# new\n")
    assert _fingerprint(root) == before


def test_an_untracked_harness_module_still_moves_it(tmp_path):
    root = _sandbox(tmp_path)
    before = _fingerprint(root)
    (root / "garden" / "new_engine.py").write_text("# new\n")
    assert _fingerprint(root) != before


def test_the_fingerprint_covers_the_real_data_prompts_and_their_reader():
    """Added 2026-09-24, before the first model-backed real-data run: the file a
    real-data run's prompt is BUILT by, and the pre-registration that prompt is
    read from, both determine what the run does."""
    from experiments import code_state as cs
    assert "experiments/real_prompts.py" in cs.CODE_PATHS
    assert cs.REAL_PREREG_FILE.name == "AGENT_PROMPTS_REAL.md"
    assert cs.real_prereg_design_md5() not in ("missing", cs.prereg_design_md5())
    assert "real_prereg_design_md5" in cs.code_state()


def test_appending_an_amendment_to_either_prereg_moves_no_fingerprint(tmp_path):
    """Both files' amendment logs are excluded, for the reason the module gives:
    an amendment records a decision and changes no prompt, tool or pinned value,
    so writing one down must not invalidate a batch mid-flight."""
    from experiments import code_state as cs
    for path, heading in ((cs.PREREG_FILE, cs.AMENDMENTS_HEADING),
                          (cs.REAL_PREREG_FILE, cs.REAL_AMENDMENTS_HEADING)):
        text = path.read_text()
        assert heading in text, path.name
        design, _, _ = text.partition(heading)
        assert heading not in design


def test_dirty_paths_does_not_eat_the_first_paths_first_character():
    """Regression: porcelain's status field is two columns, so an unstaged
    modification starts with a space. Stripping the whole output removed it and
    line[3:] then cut into the path itself."""
    from experiments import code_state as cs
    lines = [" M experiments/code_state.py", "?? prereg/new.md", " D garden/x.py"]
    got = sorted(line[3:].strip() for line in "\n".join(lines).splitlines() if line.strip())
    assert got == ["experiments/code_state.py", "garden/x.py", "prereg/new.md"]
    for p in cs.dirty_paths():
        assert (cs.ROOT / p).exists() or p.endswith((".pyc",)), p
