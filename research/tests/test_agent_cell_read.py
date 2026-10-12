"""The check-1 reader, validated on synthetic rows with the same schema.

Never validated on the 80 real runs: a rule is read once, and a reader exercised on
the data it will read has already spent the reading.

Amendment 11 fixes the quantity: check 1's type-I rate is the false-certification
rate over ALL runs, a run that issued no certificate counting as a non-rejection.
Bracketed rows are therefore part of the fixture, not an edge case.
"""
import numpy as np
import pytest

from experiments.agent_cell_read import read_check1


def _priced(ps, kinds=("init", "extend_best", "stop")):
    return [{"index": i, "run_id": f"r{i}", "p_certifying": float(p),
             "p_upper": None, "status": "CERTIFIED" if p < 0.05 else "FAIL",
             "B": 200, "triggers_changed": False, "decision_kinds": list(kinds)}
            for i, p in enumerate(ps)]


def _bracketed(n, start=1000, kinds=("init", "extend_best")):
    """Runs that issued NO certificate: no position, a logged change, bracketed."""
    return [{"index": start + i, "run_id": f"b{i}", "p_certifying": None,
             "p_upper": None, "status": "DEPENDS_ON_JUDGMENT", "B": 200,
             "triggers_changed": True, "decision_kinds": list(kinds)}
            for i in range(n)]


# -- the rule: false certification over every run -----------------------------

def test_a_bracketed_run_counts_as_a_non_rejection_and_stays_in_the_denominator():
    """Amendment 11. The denominator is every run; a run that certified nothing is
    a non-rejection, which is what it does in deployment. Dropping it would
    condition the answer on agent behaviour."""
    rng = np.random.default_rng(0)
    rows = _priced(rng.uniform(size=60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "REFUSED" not in out
    assert "Runs: 80" in out
    assert "20 run(s) counted as NON-REJECTIONS" in out
    # the denominator is 80, not 60
    assert "/80" in out
    assert "VERDICT, CHECK 1" in out


def test_the_rate_is_over_all_runs_not_over_the_priced_ones():
    """4 certificates out of 80 is 0.05; out of 60 it would be 0.0667. The rule must
    read the first.

    The four positions sit between 0.01 and 0.05, so they certify at the 5% level and
    NOT at the 1% level. Using 0.001 instead would make the 1% rate 4/80 = 0.05 too,
    whose lower Wilson end exceeds 0.01 and legitimately fails high -- a property of
    the rule, not of the denominator this test is about."""
    ps = [0.02] * 4 + list(np.linspace(0.2, 1.0, 56))
    rows = _priced(ps) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "certified   4/80  =  0.0500" in out
    assert "VERDICT, CHECK 1: HOLDS" in out          # one-sided, at nominal


def test_a_leaking_arm_fails_high_on_the_lower_wilson_end():
    ps = [0.001] * 20 + list(np.linspace(0.2, 1.0, 40))
    rows = _priced(ps) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "FAILS HIGH" in out
    assert "VERDICT, CHECK 1: FAILS HIGH" in out


def test_an_arm_that_certifies_nothing_holds():
    rows = _priced(np.linspace(0.3, 1.0, 60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "certified   0/80" in out
    assert "VERDICT, CHECK 1: HOLDS" in out


# -- the descriptive readouts -------------------------------------------------

def test_the_shape_readouts_are_on_positions_only_with_the_conditioning_stated():
    rng = np.random.default_rng(1)
    rows = _priced(rng.uniform(size=60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "DESCRIPTIVE, positions only" in out
    assert "Read on the 60 runs that carry a position, NOT on all 80." in out
    assert "DID NOT" in out and "change a trigger" in out
    assert "These readouts gate nothing." in out
    assert "Per decision kind" in out


def test_a_ks_rejection_with_the_rate_inside_its_interval_is_a_shape_departure():
    rows = _priced(np.linspace(0.40, 0.60, 60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "REJECTS at 0.05" in out
    assert "VERDICT, CHECK 1: HOLDS" in out
    assert "SHAPE DEPARTURE" in out


def test_the_declared_class_readout_says_pending_when_it_was_never_computed():
    """Amendment 11 adds it on all runs and records that this arm never computed
    it. Reported as pending rather than silently omitted."""
    rows = _priced(np.linspace(0.2, 1.0, 60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "the declared-class p-value (the bracket's upper end)" in out
    assert "NOT AVAILABLE on these runs" in out
    assert "no model, no seat" in out


def test_the_declared_class_readout_is_read_when_it_is_present():
    rng = np.random.default_rng(2)
    rows = _priced(rng.uniform(size=60)) + _bracketed(20)
    for i, r in enumerate(rows):
        r["p_upper"] = 0.6 + 0.004 * i          # conservative, as expected
    out = read_check1(rows, n_registered=80)
    assert "NOT AVAILABLE" not in out
    assert "/80" in out


def test_the_bracket_rate_is_named_as_a_check_3_readout():
    rows = _priced(np.linspace(0.2, 1.0, 60)) + _bracketed(20)
    out = read_check1(rows, n_registered=80)
    assert "CHECK-3 readout" in out


def test_an_arm_of_a_different_size_is_read_and_says_so():
    """The rate is over the runs present; the reader must not pretend n = 80."""
    rows = _priced(np.linspace(0.2, 1.0, 30)) + _bracketed(10)
    out = read_check1(rows, n_registered=80)
    assert "the arm holds 40 runs, not the registered 80" in out
    assert "/40" in out
