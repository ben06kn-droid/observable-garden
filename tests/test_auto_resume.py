"""--auto-resume: a rate limit is a wait, not a failure (prereg §6, amendment 7).

These drive the real experiments/run_arms.sh against a stub e_agent inside a
throwaway git repo. The retry path is shell, and the defects that have actually
bitten this script -- an unbound variable on a branch taken once per batch, a
bash-3.2 `local` that reads the wrong scope -- are all invisible to anything
short of running it. GARDEN_AUTO_RESUME_SLEEP keeps the waits at a second.
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

STUB = '''\
import argparse, json, os, sys
from pathlib import Path

CONFIGS = {"s0": dict(s=0, K=40, M=50, T=5000, T_oos=1000)}
TAGS = {"claude-sonnet-5": "sonnet"}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm"); p.add_argument("--config"); p.add_argument("--runs", type=int, default=1)
    p.add_argument("--seed-index", type=int); p.add_argument("--budget", type=int, default=None)
    p.add_argument("--model", default="claude-sonnet-5"); p.add_argument("--worker", type=int, default=None)
    a = p.parse_args()
    rid = f"{a.config}_T5000_{TAGS[a.model]}_{a.arm}_{a.seed_index:03d}"
    d = Path("runs") / rid
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(json.dumps({"run_id": rid, "worker": a.worker}))

    counter = Path("attempts.txt")
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))

    kind = os.environ.get("STUB_FAIL_KIND", "")
    times = int(os.environ.get("STUB_FAIL_TIMES", "0"))
    if n < times:
        if kind == "RateLimited":
            (d / "error.json").write_text(json.dumps(
                {"kind": "RateLimited", "detail": "rate limit rejected: {'resets_at': 1}"}))
            return 2
        if kind == "AuthFailed":
            # Same exit code as a rate limit. Only error.json tells them apart.
            (d / "error.json").write_text(json.dumps({"kind": "AuthFailed", "detail": "bad key"}))
            return 2
        (d / "void.json").write_text("{}")
        return 4
    (d / "verdict.json").write_text(json.dumps({"status": "FAIL"}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


@pytest.fixture
def sandbox(tmp_path):
    """A minimal repo the script can run in: git, a venv, three modules, one row."""
    root = tmp_path / "repo"
    (root / "experiments").mkdir(parents=True)
    (root / "runs").mkdir()
    for name in ("run_arms.sh", "worker_rows.py", "code_state.py"):
        (root / "experiments" / name).write_bytes((REPO / "experiments" / name).read_bytes())
    (root / "experiments" / "run_arms.sh").chmod(0o755)
    (root / "experiments" / "e_agent.py").write_text(STUB)
    (root / "experiments" / "__init__.py").write_text("")
    (root / "experiments" / "sched.txt").write_text(
        "# seed config arm budget model\n300 s0 control - claude-sonnet-5\n")
    os.symlink(REPO / ".venv", root / ".venv")
    # Mirror the real repo: without this, the first import writes
    # experiments/__pycache__/*.pyc, which the fingerprint counted as new
    # untracked code, so the guard stopped every worker before it ran a row.
    (root / ".gitignore").write_text("__pycache__/\n*.pyc\n.venv\n")

    run = lambda *a: subprocess.run(a, cwd=root, capture_output=True, text=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "harness")
    return root


def drive(root, *, fail_kind, fail_times, extra=()):
    env = dict(os.environ, STUB_FAIL_KIND=fail_kind, STUB_FAIL_TIMES=str(fail_times),
               GARDEN_AUTO_RESUME_SLEEP="1")
    p = subprocess.run(
        ["bash", "experiments/run_arms.sh", "--schedule", "experiments/sched.txt",
         "--workers", "1", "--only-worker", "0", *extra],
        cwd=root, env=env, capture_output=True, text=True, timeout=300)
    log_path = root / "runs/_logs/worker_0.log"
    log = log_path.read_text() if log_path.exists() else "(no worker log)"
    # Fold the script's own output into what a failure prints. Without it an
    # assertion just says "0 != 1" and says nothing about why the row never ran.
    return p, f"{log}\n--- stdout ---\n{p.stdout}\n--- stderr ---\n{p.stderr}"


def attempts(root) -> int:
    f = root / "attempts.txt"
    return int(f.read_text()) if f.exists() else 0


def test_rate_limit_twice_then_success_completes_the_row_with_retry_2(sandbox):
    p, log = drive(sandbox, fail_kind="RateLimited", fail_times=2, extra=("--auto-resume",))
    assert attempts(sandbox) == 3, f"expected 3 attempts, got {attempts(sandbox)}\n{log}"
    assert (sandbox / "runs/s0_T5000_sonnet_control_300/verdict.json").exists()
    assert "completed after 2 retries" in log, log
    assert log.count("rate limited; sleeping") == 2, log
    assert log.count("awake; retrying") == 2, log
    # The stop recorded while retrying must not survive a row that finished.
    assert not (sandbox / "runs/_logs/stopped_0").exists()
    assert p.returncode == 0, p.stderr
    # Each failed attempt's directory was parked, not left to block the retry.
    parked = list((sandbox / "runs/_aborted").glob("s0_T5000_sonnet_control_300*"))
    assert len(parked) == 2, parked


def test_exit_4_stops_the_worker_immediately(sandbox):
    """A void run is a defect; retrying it would only reproduce it."""
    p, log = drive(sandbox, fail_kind="void", fail_times=1, extra=("--auto-resume",))
    assert attempts(sandbox) == 1
    stopped = sandbox / "runs/_logs/stopped_0"
    assert stopped.exists()
    first = stopped.read_text().splitlines()[0]
    assert "exit 4" in first and "retries 0" in first, first
    assert "sleeping" not in log
    assert p.returncode == 1


def test_auth_failure_is_never_retried_despite_sharing_exit_2(sandbox):
    """e_agent returns 2 for both RateLimited and AuthFailed, so the exit code
    alone cannot decide. error.json's kind is what gates the retry."""
    p, log = drive(sandbox, fail_kind="AuthFailed", fail_times=1, extra=("--auto-resume",))
    assert attempts(sandbox) == 1, log
    assert (sandbox / "runs/_logs/stopped_0").exists()
    assert "sleeping" not in log
    assert p.returncode == 1


def test_without_the_flag_a_rate_limit_still_stops_the_worker(sandbox):
    p, log = drive(sandbox, fail_kind="RateLimited", fail_times=1)
    assert attempts(sandbox) == 1
    assert (sandbox / "runs/_logs/stopped_0").exists()
    assert "sleeping" not in log
    assert p.returncode == 1


def test_the_reset_time_is_parsed_from_a_real_payload(sandbox):
    """Exercises the shipped bash function, not a Python lookalike: the regex
    lives inside a double-quoted `python -c` string, which is where escaping
    goes wrong unnoticed.

    `resets_at.{0,4}(\\d{9,})` greedily consumed the "': 1" before the digits and
    captured 789717800 instead of 1789717800 -- a reset in January 1995. That is
    silent: it fails the "is it in the future" test, so the wait degrades to
    blind 15-minute retries through an outage instead of one sleep to the reset."""
    rid = "s3_T5000_sonnet_gate_313"
    d = sandbox / "runs" / rid
    d.mkdir(parents=True)
    (d / "error.json").write_text(json.dumps({
        "kind": "RateLimited",
        "detail": "rate limit rejected: {'status': 'rejected', "
                  "'resets_at': 1789717800, 'type': 'five_hour'}"}))

    text = (sandbox / "experiments" / "run_arms.sh").read_text()
    start = text.index("reset_epoch_for()")
    end = text.index("\n}", start) + 2
    (sandbox / "fn.sh").write_text(text[start:end] + '\nreset_epoch_for "$1"\n')

    r = subprocess.run(["bash", "fn.sh", rid], cwd=sandbox, capture_output=True, text=True)
    assert r.stdout.strip() == "1789717800", (r.stdout, r.stderr)


def test_a_missing_reset_time_yields_empty_not_garbage(sandbox):
    """No resets_at in the payload means fall back to the fixed wait, which the
    caller signals by an empty string rather than a zero."""
    rid = "s0_T5000_sonnet_control_300"
    d = sandbox / "runs" / rid
    d.mkdir(parents=True)
    (d / "error.json").write_text(json.dumps({"kind": "RateLimited", "detail": "no time given"}))
    text = (sandbox / "experiments" / "run_arms.sh").read_text()
    start = text.index("reset_epoch_for()")
    end = text.index("\n}", start) + 2
    (sandbox / "fn.sh").write_text(text[start:end] + '\nreset_epoch_for "$1"\n')
    r = subprocess.run(["bash", "fn.sh", rid], cwd=sandbox, capture_output=True, text=True)
    assert r.stdout.strip() == "", (r.stdout, r.stderr)


def test_a_clean_row_needs_no_retry_machinery(sandbox):
    p, log = drive(sandbox, fail_kind="", fail_times=0, extra=("--auto-resume",))
    assert attempts(sandbox) == 1
    assert not (sandbox / "runs/_logs/stopped_0").exists()
    assert (sandbox / "runs/s0_T5000_sonnet_control_300/verdict.json").exists()
    assert p.returncode == 0
