"""Sandbox contract checks: no OOS leakage through the searcher-visible API,
every evaluate() call is logged, and the true oracle spec, when evaluated
through the sandbox, recovers (approximately) the oracle's own Sharpe."""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate, oracle_sharpe_analytic
from environments.sandbox import Sandbox, Specification, Distribution


def make_sandbox(**overrides):
    defaults = dict(M=200, T=2000, T_oos=1000, K=60, s=3, rho=0.2, sigma=2.0, seed=0)
    defaults.update(overrides)
    config = DGPConfig(**defaults)
    data = generate(config)
    return Sandbox(data, periods_per_year=config.periods_per_year), data, config


def test_get_data_excludes_oos():
    sandbox, data, config = make_sandbox()
    df = sandbox.get_data()
    assert len(df) == config.T * config.M
    assert set(df.columns) == {"t", "asset", "r"} | {f"f{k}" for k in range(config.K)}
    assert df["t"].max() == config.T - 1


def test_evaluate_logs_every_call_even_if_unused():
    sandbox, data, config = make_sandbox()
    for k in range(5):
        w = np.zeros(config.K)
        w[k] = 1.0
        sandbox.evaluate(Specification(weights=w, name=f"f{k}"))
    assert len(sandbox.transcript) == 5
    R = sandbox.returns_matrix()
    assert R.shape == (config.T, 5)


def test_evaluate_returns_summary_only_not_full_stream():
    sandbox, data, config = make_sandbox()
    result = sandbox.evaluate(Specification(weights=data.beta_full))
    assert isinstance(result.sharpe, float)
    assert not hasattr(result, "return_stream")


def test_oracle_spec_through_sandbox_matches_closed_form():
    sandbox, data, config = make_sandbox(M=500, T=5000)
    result = sandbox.evaluate(Specification(weights=data.beta_full, name="oracle"))
    analytic = oracle_sharpe_analytic(config)
    # Finite-sample: single draw of T periods, not the 10^6-period oracle limit.
    assert result.sharpe == pytest.approx(analytic, rel=0.25)


def test_submit_requires_distribution():
    sandbox, data, config = make_sandbox()
    spec = Specification(weights=data.beta_full)
    with pytest.raises(TypeError):
        sandbox.submit(spec, predicted_oos_sharpe=1.5)  # not a Distribution
    sandbox.submit(spec, predicted_oos_sharpe=Distribution.degenerate(1.5))
    assert sandbox.submission[0] is spec


def test_oos_grading_not_reachable_from_evaluate():
    sandbox, data, config = make_sandbox()
    # oos_sharpe_for_grading exists but is a distinct, clearly-labeled method;
    # evaluate() must never touch x_oos/r_oos.
    spec = Specification(weights=data.beta_full)
    in_sample = sandbox.evaluate(spec).sharpe
    graded = sandbox.oos_sharpe_for_grading(spec)
    assert in_sample != graded  # different draws, should not coincide exactly
