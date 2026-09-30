"""The check-1 reader, validated on synthetic rows with the same schema.

Not validated on the 80 real runs: a rule is read once, and a reader exercised on
the data it will read has already spent the reading.
"""
import numpy as np
import pytest

from experiments.agent_cell_read import read_check1


def _rows(ps, kinds=("init", "extend_best", "stop"), changed=False):
    return [{"index": i, "run_id": f"r{i}", "p_certifying": p, "status": "FAIL",
             "B": 200, "triggers_changed": changed, "decision_kinds": list(kinds)}
            for i, p in enumerate(ps)]


def test_a_uniform_arm_holds_and_says_what_n_buys():
    rng = np.random.default_rng(0)
    ps = list(np.clip(rng.uniform(size=80), 1e-6, 1.0))
    out = read_check1(_rows(ps))
    assert "VERDICT, CHECK 1: HOLDS" in out
    assert "KS against U(0,1)" in out
    assert "alpha = 0.05" in out and "alpha = 0.01" in out
    assert "does not fail high" in out
    assert "GROSS LEAKAGE AND NO MORE" in out
    # both branches are stated before the verdict
    assert "Fails high:" in out and "Holds:" in out


def test_a_leaking_arm_fails_high_on_the_lower_wilson_end():
    """Fails high iff the LOWER end exceeds nominal -- not the point estimate."""
    ps = [0.001] * 20 + list(np.linspace(0.2, 1.0, 60))
    out = read_check1(_rows(ps))
    assert "FAILS HIGH" in out
    assert "VERDICT, CHECK 1: FAILS HIGH" in out


def test_a_rate_at_nominal_does_not_fail_high():
    """4 of 80 is 0.05 exactly; a one-sided rule must not fire on it."""
    ps = [0.01] * 4 + list(np.linspace(0.2, 1.0, 76))
    out = read_check1(_rows(ps))
    assert "VERDICT, CHECK 1: HOLDS" in out


def test_the_per_kind_lowest_decile_fractions_are_reported():
    ps = [0.01] * 8 + list(np.linspace(0.2, 1.0, 72))
    rows = _rows(ps)
    for r in rows[:8]:
        r["decision_kinds"] = ["init", "pick"]        # the suspect kind
    out = read_check1(rows)
    assert "Per decision kind" in out
    assert "pick" in out and "extend_best" in out
    assert "a flat reading is 0.10 per kind" in out


def test_a_ks_rejection_with_the_rate_inside_its_interval_is_a_shape_departure():
    """Registered branch: reported with the ECDF, not as a size failure -- the way
    6.3 handled its one KS rejection."""
    # mass in the middle: badly non-uniform in shape, no excess below alpha
    ps = list(np.linspace(0.40, 0.60, 80))
    out = read_check1(_rows(ps))
    assert "REJECTS at 0.05" in out
    assert "VERDICT, CHECK 1: HOLDS" in out
    assert "SHAPE DEPARTURE" in out


def test_the_reader_REFUSES_when_the_registered_n_is_not_priced():
    """The registered n is part of the rule. A reading over whatever subset happens
    to be priced is not check 1, and the shortfall here is not random: the unpriced
    runs are exactly those where the agent changed a rule."""
    rng = np.random.default_rng(1)
    rows = _rows(list(rng.uniform(size=60)))
    rows += [{"index": 60 + i, "run_id": f"u{i}", "p_certifying": None,
              "status": "DEPENDS_ON_JUDGMENT", "B": 200, "triggers_changed": True,
              "decision_kinds": ["init", "extend_best"]} for i in range(20)]
    out = read_check1(rows)
    assert "REFUSED" in out
    assert "NOTHING IS READ" in out
    assert "20 of 80" in out
    assert "agent behaviour" in out
    # No rule QUANTITY is printed. The preamble legitimately quotes the rule's own
    # words -- "FAILS HIGH iff the LOWER end" -- so the test looks for the readouts
    # themselves, not for the vocabulary of the rule.
    for marker in ("KS against U(0,1)", "Per decision kind", "VERDICT, CHECK 1",
                   "Detectability at the registered n"):
        assert marker not in out, marker


def test_refusal_is_by_count_not_by_status_so_a_priced_bracket_would_read():
    """If a bracketed run were ever given a defensible position, the reader must
    read it rather than refusing on the status. The precondition is the COUNT."""
    rng = np.random.default_rng(2)
    rows = _rows(list(rng.uniform(size=80)))
    for r in rows[:20]:
        r["status"] = "DEPENDS_ON_JUDGMENT"
        r["triggers_changed"] = True
    out = read_check1(rows)
    assert "REFUSED" not in out
    assert "VERDICT, CHECK 1" in out
