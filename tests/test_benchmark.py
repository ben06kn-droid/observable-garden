"""--benchmark: the null becomes zero excess return over a declared series.

The default null is zero return, which asks whether a result beats not trading.
Over a rising market a long-only grid can clear a breadth-corrected bar on the
benchmark's own return with no timing edge at all, so the benchmark is what
turns the verdict into the market-relative question.
"""
import numpy as np
import pytest

from estimator.bootstrap import sharpe
from garden.audit import audit
from garden.preflight import preflight
from garden.report import render_preflight, render_verdict
from garden.transcript import TranscriptError, from_matrix, load_benchmark


def _t(seed=0, T=400, N=6, menu_kind="oblivious"):
    rng = np.random.default_rng(seed)
    return from_matrix(rng.normal(0.0, 0.01, (T, N)), 0, menu_kind=menu_kind)


# -- the arithmetic -----------------------------------------------------------

def test_a_zero_benchmark_changes_nothing():
    t = _t()
    plain = audit(t, B=300, seed=0)
    zeroed = audit(t, B=300, seed=0, benchmark=np.zeros(t.n_periods), benchmark_name="zeros.csv")
    assert zeroed.sr_reported == pytest.approx(plain.sr_reported)
    assert zeroed.critical_value == pytest.approx(plain.critical_value)
    assert zeroed.null_max_mean == pytest.approx(plain.null_max_mean)
    assert zeroed.status == plain.status
    assert plain.benchmark is None and zeroed.benchmark == "zeros.csv"


def test_subtracting_a_series_from_itself_leaves_no_edge():
    """Every column is the benchmark, so excess return is exactly zero."""
    b = np.random.default_rng(1).normal(0.0, 0.01, 300)
    t = from_matrix(np.column_stack([b, b, b]), 0, menu_kind="oblivious")
    v = audit(t, B=300, seed=0, benchmark=b, benchmark_name="self")
    assert v.sr_reported == pytest.approx(0.0, abs=1e-9)


def test_the_reported_sharpe_is_the_excess_sharpe():
    rng = np.random.default_rng(2)
    T = 400
    bench = rng.normal(0.0005, 0.01, T)
    R = rng.normal(0.0, 0.01, (T, 4)) + bench[:, None]       # every rule carries the benchmark
    v = audit(from_matrix(R, 2, menu_kind="oblivious"), B=300, seed=0,
              benchmark=bench, benchmark_name="b")
    assert v.sr_reported == pytest.approx(
        float(sharpe(R[:, 2] - bench, annualization=np.sqrt(252))))


# -- the refusals -------------------------------------------------------------

def test_a_benchmark_of_the_wrong_length_is_refused():
    with pytest.raises(ValueError, match="one return per period"):
        audit(_t(T=300), B=100, benchmark=np.zeros(299))


def test_a_non_finite_benchmark_is_refused():
    b = np.zeros(300)
    b[5] = np.nan
    with pytest.raises(ValueError, match="NaN or inf"):
        audit(_t(T=300), B=100, benchmark=b)


def test_a_benchmark_is_refused_on_a_class_enumerated_from_features():
    """base_returns holds features, not specification returns. A specification is
    a weighted sum of them, so subtracting the benchmark from each column would
    deduct it once per feature rather than once per specification -- three times
    over for a three-feature rule. Refuse rather than correct by the wrong
    multiple; the explicit-class path, whose columns are specification streams,
    is the one that can take a benchmark."""
    rng = np.random.default_rng(3)
    T, K = 300, 5
    base = rng.normal(0.0, 0.01, (T, K))
    members = np.zeros((4, K))
    for i in range(4):
        members[i, i] = 1.0
    t = from_matrix(base @ members.T, 0, menu_kind="adaptive", base_returns=base,
                    spec_members=members, spec_class="subsets:max_size=3,signs=both",
                    spec_class_source="attested")
    with pytest.raises(ValueError, match="once per feature"):
        audit(t, B=100, benchmark=np.zeros(T))


# -- what it says -------------------------------------------------------------

def test_the_verdict_states_the_null():
    t = _t()
    v = audit(t, B=300, seed=0, benchmark=np.zeros(t.n_periods), benchmark_name="spy.csv")
    assert any("zero excess return over spy.csv" in r for r in v.reasons), v.reasons
    assert "spy.csv" in render_verdict(v)


def test_effective_breadth_is_undefined_when_every_column_is_constant():
    """Subtracting a benchmark from a menu whose columns all equal it leaves no
    variance anywhere, so there are no trial correlations to take a participation
    ratio of. The expression divided by zero and returned inf, which reads as
    infinite breadth. NaN says undefined, and the verdict says why."""
    b = np.random.default_rng(7).normal(0.0, 0.01, 300)
    t = from_matrix(np.column_stack([b, b, b]), 0, menu_kind="oblivious")
    v = audit(t, B=200, seed=0, benchmark=b, benchmark_name="self")
    assert np.isnan(v.effective_breadth)
    assert any("Effective breadth is undefined" in r for r in v.reasons), v.reasons
    assert "undefined" in render_verdict(v)
    assert v.to_dict()["effective_breadth"] is None       # _json_safe nulls non-finite


def test_preflight_carries_the_benchmark():
    plain, withb = preflight(44, 8266, 1.0), preflight(44, 8266, 1.0, benchmark="spy.csv")
    assert plain.benchmark is None and withb.benchmark == "spy.csv"
    assert any("Null: zero return" in r for r in plain.reasons), plain.reasons
    assert any("zero excess return over spy.csv" in r for r in withb.reasons), withb.reasons
    assert "spy.csv" in render_preflight(withb)


# -- the loader ---------------------------------------------------------------

def _csv(tmp_path, text, name="b.csv"):
    p = tmp_path / name
    p.write_text(text)
    return p


def test_load_benchmark_reads_one_return_column(tmp_path):
    p = _csv(tmp_path, "Date,ret\n1,0.01\n2,-0.02\n3,0.00\n")
    np.testing.assert_allclose(load_benchmark(p), [0.01, -0.02, 0.0])


def test_load_benchmark_refuses_extra_columns(tmp_path):
    p = _csv(tmp_path, "Date,a,b\n1,0.01,0.02\n2,0.0,0.0\n")
    with pytest.raises(TranscriptError, match="exactly one return column"):
        load_benchmark(p)


def test_load_benchmark_refuses_non_numeric(tmp_path):
    p = _csv(tmp_path, "Date,ret\n1,0.01\n2,oops\n")
    with pytest.raises(TranscriptError, match="non-numeric"):
        load_benchmark(p)


def test_load_benchmark_checks_the_length_against_the_transcript(tmp_path):
    p = _csv(tmp_path, "Date,ret\n1,0.01\n2,0.02\n")
    with pytest.raises(TranscriptError, match="same time index"):
        load_benchmark(p, n_periods=3)
