"""experiments/run_arms.sh — shell-level invariants, one per defect that bit us.

The runner is bash 3.2 (macOS ships nothing newer as /usr/bin/env bash), and its
sharpest failures are invisible to `bash -n`: they need the loop body to actually
execute, sometimes only on a path taken once in a batch. These lint the source so
the next instance is caught without a live run.
"""
import re
from pathlib import Path

SCRIPT = Path("experiments/run_arms.sh")
LINES = SCRIPT.read_text().splitlines()


def test_no_local_statement_references_a_name_it_declares():
    """bash 3.2: `local k="$1" log="w_$k"` cannot see k from the same statement.
    Under `set -u` that aborts the function. It stayed hidden in the parallel
    path because the caller's loop variable was also named k, so the reference
    resolved to that global; --only-worker had no such caller and died."""
    bad = []
    for i, line in enumerate(LINES, 1):
        m = re.match(r"\s*local\s+(.*)", line)
        if not m:
            continue
        declared: list[str] = []
        for part in m.group(1).split():
            name, sep, rhs = part.partition("=")
            if sep:
                for d in declared:
                    if re.search(r"\$\{?" + re.escape(d) + r"\b", rhs):
                        bad.append(f"line {i}: {name} reads {d} from the same local")
            declared.append(name)
    assert not bad, "\n".join(bad)


def test_no_bash4_only_builtins():
    """mapfile/readarray are bash 4+. The schedule loop died on its first line
    the one time mapfile was used here."""
    for i, line in enumerate(LINES, 1):
        assert not re.match(r"\s*(mapfile|readarray)\b", line), f"line {i}: {line.strip()}"


def test_unset_safety_is_on():
    assert any(re.match(r"set -[a-z]*u", ln) for ln in LINES), "set -u must stay on"


# --workers 1 leaving runs/_logs/ untouched is checked by running the script,
# not by linting it: a source-level version of that test was fragile enough that
# it would have failed on refactors rather than on defects.
