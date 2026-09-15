"""The gate: transcript loading, engine parity with the validated estimator,
verdict logic, CLI exit codes, and preflight's analytic power."""
import json

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from environments.dgp import DGPConfig, generate
from environments.sandbox import Distribution, Sandbox, Specification
from estimator.bootstrap import null_max_bootstrap as reference_bootstrap
from estimator.bootstrap import sharpe, stationary_bootstrap_indices
from estimator.deflated_sharpe import effective_N
from garden import TranscriptError, audit, from_matrix, from_sandbox, load_csv, load_npz, preflight
from garden._engine import null_max_bootstrap
from garden.audit import effective_breadth
from garden.cli import main
from garden.report import render_verdict
from garden.examples import EXAMPLES, build as build_example, load as load_example
from garden.power import bootstrap_p_value, critical_value, null_max_critical_value

PPY = 252
ANN = np.sqrt(PPY)
B_FAST = 2000


def noise(T, N, seed):
    return np.random.default_rng(seed).standard_normal((T, N)) * 0.01


def with_sharpe(col, target):
    """Shift a column's mean so its annualized in-sample Sharpe is exactly `target`."""
    col = col - col.mean()
    return col + target / ANN * col.std(ddof=1)


def oblivious_audit(R, j, **kw):
    return audit(from_matrix(R, j, menu_kind="oblivious", periods_per_year=PPY), B=B_FAST, seed=0, **kw)


def fail_case():
    R = noise(2520, 10, 8)
    R[:, 0] = with_sharpe(R[:, 0], 0.0)
    return R, 0


def pass_case():
    R = noise(2520, 10, 9)
    R[:, 3] = with_sharpe(R[:, 3], 3.0)
    return R, 3


def inadmissible_case():
    R = noise(250, 500, 10)
    R[:, 0] = with_sharpe(R[:, 0], 0.0)
    return R, 0


# -- transcript -------------------------------------------------------------

def test_menu_kind_defaults_to_unknown():
    t = from_matrix(noise(100, 3, 0), submitted_index=1)
    assert t.menu_kind == "unknown" and t.submitted == "spec_1"


def test_npz_round_trip(tmp_path):
    t = from_matrix(noise(50, 4, 1), 2, spec_ids=["a", "b", "c", "d"], menu_kind="oblivious", periods_per_year=52)
    t.save(tmp_path / "t.npz")
    u = load_npz(tmp_path / "t.npz")
    np.testing.assert_array_equal(u.returns, t.returns)
    assert list(u.spec_ids) == ["a", "b", "c", "d"]
    assert (u.submitted, u.menu_kind, u.periods_per_year) == ("c", "oblivious", 52)


def test_csv_loader(tmp_path):
    R = noise(30, 3, 2)
    pd.DataFrame(R, columns=["x", "y", "z"], index=pd.date_range("2020-01-01", periods=30)).to_csv(tmp_path / "t.csv")
    t = load_csv(tmp_path / "t.csv", submitted="y", menu_kind="oblivious")
    np.testing.assert_allclose(t.returns, R)
    assert t.submitted_index == 1


def test_unequal_length_streams_are_rejected_not_aligned(tmp_path):
    df = pd.DataFrame(noise(30, 3, 3), columns=["x", "y", "z"])
    df.loc[:4, "z"] = np.nan
    df.to_csv(tmp_path / "t.csv")
    with pytest.raises(TranscriptError, match="same periods"):
        load_csv(tmp_path / "t.csv", submitted="x")


def test_submitted_must_be_in_transcript():
    with pytest.raises(TranscriptError):
        from_matrix(noise(30, 3, 0), submitted_index=3)


def test_from_sandbox_matches_log_and_submission():
    data = generate(DGPConfig(M=20, T=200, T_oos=50, K=8, s=0, rho=0.0, sigma=1.0, seed=3))
    sandbox = Sandbox(data, periods_per_year=PPY)
    specs = [Specification(np.eye(8)[k], name=f"f{k}") for k in range(5)]
    results = [sandbox.evaluate(s) for s in specs]
    sandbox.submit(specs[2], Distribution.degenerate(results[2].sharpe))

    t = from_sandbox(sandbox, menu_kind="oblivious")
    np.testing.assert_array_equal(t.returns, sandbox.returns_matrix())
    assert t.submitted_index == 2
    assert sharpe(t.returns, annualization=ANN)[2] == pytest.approx(results[2].sharpe)


# -- engine and critical value ----------------------------------------------

def test_engine_reproduces_validated_estimator():
    R = noise(300, 25, 4)
    ref = reference_bootstrap(R, B=200, annualization=ANN, seed=5)
    new = null_max_bootstrap(R, B=200, annualization=ANN, seed=5, track_index=7, chunk=16)
    assert new.block_length == ref.block_length
    np.testing.assert_allclose(new.M_b, ref.M_b, rtol=1e-10, atol=1e-12)

    idx = stationary_bootstrap_indices(300, new.block_length, np.random.default_rng(5))
    Rd = R - R.mean(axis=0)
    assert new.tracked[0] == pytest.approx(sharpe(Rd[idx], annualization=ANN)[7])


def test_engine_parity_with_long_blocks():
    R = np.cumsum(noise(400, 12, 6), axis=0) * 0.1 + noise(400, 12, 7)
    ref = reference_bootstrap(R, B=150, block_length=12, seed=8)
    new = null_max_bootstrap(R, B=150, block_length=12, seed=8)
    np.testing.assert_allclose(new.M_b, ref.M_b, rtol=1e-10, atol=1e-12)


def test_audit_survives_a_column_that_never_trades():
    R = noise(500, 6, 16)
    R[:, 2] = 0.0
    v = oblivious_audit(R, 0)
    assert v.block_length >= 1 and np.isfinite(v.null_max_mean)


@pytest.mark.parametrize("B,alpha", [(10, 0.05), (19, 0.05), (99, 0.05), (1000, 0.05), (2000, 0.01)])
def test_critical_value_agrees_with_p_value_everywhere(B, alpha):
    null = np.random.default_rng(B).standard_normal(B)
    c = critical_value(null, alpha)
    for sr in np.concatenate([null, null + 1e-9, null - 1e-9, np.linspace(-4, 4, 200)]):
        assert (bootstrap_p_value(null, sr) < alpha) == (sr > c)


def test_effective_breadth_matches_eigenvalue_definition():
    R = noise(80, 30, 6)
    R[:, 1] = R[:, 0]
    assert effective_breadth(R) == pytest.approx(effective_N(R), rel=1e-8)
    R_wide = noise(40, 60, 7)
    assert effective_breadth(R_wide) == pytest.approx(effective_N(R_wide), rel=1e-8)


# -- verdicts ---------------------------------------------------------------

def test_fail_when_nothing_found_by_a_powered_search():
    v = oblivious_audit(*fail_case())
    assert v.status == "FAIL" and v.exit_code == 1
    assert v.power_at_reference >= v.power_floor and v.sr_reported <= v.critical_value


def test_pass_on_a_strong_edge():
    v = oblivious_audit(*pass_case())
    assert v.status == "PASS" and v.exit_code == 0 and v.submitted_rank == 1
    assert v.sr_reported > v.critical_value
    assert not any("overstate the edge" in r for r in v.reasons)
    assert any("not used in the correction" in r for r in v.reasons)


def test_inadmissible_when_search_is_too_wide_for_the_sample():
    v = oblivious_audit(*inadmissible_case())
    assert v.status == "INADMISSIBLE" and v.exit_code == 2 and v.power_at_reference < 0.2


def test_underpowered_pass_stays_pass_with_type_m_warning():
    R = noise(250, 500, 11)
    R[:, 0] = with_sharpe(R[:, 0], 8.0)
    v = oblivious_audit(R, 0)
    assert v.status == "PASS" and v.power_at_reference < v.power_floor
    assert any("overstate the edge" in r for r in v.reasons)


def test_unknown_menu_is_undecidable_with_labeled_p_value_and_routes():
    v = audit(from_matrix(noise(500, 20, 12), 0), B=B_FAST, seed=0)
    assert v.status == "UNDECIDABLE" and v.exit_code == 3
    assert v.p_value_is_lower_bound and 0 < v.p_value <= 1
    text = "\n".join(v.reasons)
    assert "Routes forward" in text and "garden explain menu" in text


def test_rerun_hook_gives_adaptive_search_a_verdict():
    T = 500
    R = noise(T, 20, 13)
    j = int(np.argmax(sharpe(R, annualization=ANN)))

    def rerun(shift):
        return float(sharpe(noise(T, 20, 10_000 + shift), annualization=ANN).max())

    v = audit(from_matrix(R, j, menu_kind="adaptive"), B=B_FAST, seed=0, rerun=rerun, rerun_B=100)
    assert v.status != "UNDECIDABLE" and not v.p_value_is_lower_bound
    assert v.method == "procedure_level" and v.B == 100


def test_non_maximal_submission_is_flagged_conservative():
    R = noise(1000, 10, 14)
    j = int(np.argsort(sharpe(R))[-3])
    v = oblivious_audit(R, j)
    assert v.submitted_rank == 3
    assert any("conservative" in r for r in v.reasons)


def test_verdict_json_is_serializable():
    d = oblivious_audit(*pass_case()).to_dict()
    assert json.loads(json.dumps(d))["status"] == "PASS"


# -- degeneracy check -------------------------------------------------------

def sparse_dominated_case(submitted_sharpe):
    """30 noise columns plus 200 rules that trade on 3 days each: a resample catching one of a rule's
    active days can give it an exploding Sharpe (SCOPE.md §11)."""
    rng = np.random.default_rng(17)
    T = 1000
    sparse = np.zeros((T, 200))
    for k in range(200):
        sparse[rng.choice(T, size=3, replace=False), k] = rng.normal(0.0, 0.01, 3)
    R = np.concatenate([noise(T, 30, 17), sparse], axis=1)
    R[:, 0] = with_sharpe(R[:, 0], submitted_sharpe)
    return R, 0


SCREEN = {"support_min": 10, "q_min": 0.25}


def test_degenerate_when_sparse_columns_own_the_null_maximum():
    v = oblivious_audit(*sparse_dominated_case(0.0), tail_share_max=0.05, **SCREEN)
    assert v.status == "DEGENERATE" and v.exit_code == 4
    assert v.degenerate_share > 0.05
    assert all(int(cid.split("_")[1]) >= 30 for cid in v.degenerate_columns)
    assert "Routes forward" in "\n".join(v.reasons)


def test_degenerate_when_excluding_degenerate_resamples_flips_the_verdict():
    v = oblivious_audit(*sparse_dominated_case(3.0), tail_share_max=1.0, **SCREEN)
    assert v.status == "DEGENERATE" and v.screened_status == "PASS"


def test_degeneracy_share_prints_on_a_clean_verdict():
    v = oblivious_audit(*fail_case(), tail_share_max=0.05, **SCREEN)
    assert v.status == "FAIL" and v.degenerate_replicates == 0
    assert "Degenerate tail share" in render_verdict(v)


# -- CLI --------------------------------------------------------------------

def _save(tmp_path, name, R, j, menu="oblivious"):
    path = tmp_path / f"{name}.npz"
    from_matrix(R, j, menu_kind=menu, periods_per_year=PPY).save(path)
    return str(path)


def test_cli_exit_codes_match_verdicts(tmp_path, capsys):
    B = ["--B", "1000"]
    assert main(["audit", _save(tmp_path, "pass", *pass_case()), *B]) == 0
    assert main(["audit", _save(tmp_path, "fail", *fail_case()), *B]) == 1
    assert main(["audit", _save(tmp_path, "inad", *inadmissible_case()), *B]) == 2
    assert main(["audit", _save(tmp_path, "unk", *fail_case(), menu="unknown"), *B]) == 3
    assert "VERDICT: UNDECIDABLE" in capsys.readouterr().out


def test_cli_json_output(tmp_path, capsys):
    main(["audit", _save(tmp_path, "pass", *pass_case()), "--B", "500", "--json"])
    assert json.loads(capsys.readouterr().out)["status"] == "PASS"


def test_cli_usage_and_input_errors_do_not_collide_with_verdict_codes(tmp_path, capsys):
    assert main(["audit"]) == 64
    assert main(["audit", "--no-such-flag"]) == 64
    assert main(["audit", str(tmp_path / "missing.npz")]) == 64
    assert main(["preflight", "--specs", "10", "--periods", "500"]) == 64


def test_cli_csv_requires_submitted(tmp_path, capsys):
    pd.DataFrame(noise(30, 2, 0), columns=["a", "b"]).to_csv(tmp_path / "t.csv")
    assert main(["audit", str(tmp_path / "t.csv")]) == 64


def test_cli_default_thresholds_refuse_a_degenerate_menu(tmp_path, capsys):
    assert main(["audit", _save(tmp_path, "sparse", *sparse_dominated_case(0.0)), "--B", "2000"]) == 4
    assert "VERDICT: DEGENERATE" in capsys.readouterr().out


# -- preflight --------------------------------------------------------------

def test_preflight_critical_value_is_exact_under_independence():
    c = null_max_critical_value(100, 2520, PPY, 0.05, rho=0.0)
    assert c == pytest.approx(norm.ppf(0.95 ** (1 / 100)) * np.sqrt(PPY / 2520))


def test_preflight_equicorrelated_critical_value_matches_simulation():
    rng = np.random.default_rng(15)
    n_specs, rho, draws = 50, 0.4, 400_000
    maxima = np.sqrt(rho) * rng.standard_normal(draws) + np.sqrt(1 - rho) * norm.ppf(rng.random(draws) ** (1 / n_specs))
    simulated = np.quantile(maxima, 0.95) * np.sqrt(PPY / 2520)
    assert null_max_critical_value(n_specs, 2520, PPY, 0.05, rho=rho) == pytest.approx(simulated, rel=0.01)


def test_preflight_perfect_correlation_is_one_trial():
    assert null_max_critical_value(1000, 2520, PPY, 0.05, rho=1.0) == pytest.approx(
        null_max_critical_value(1, 2520, PPY, 0.05))


def test_preflight_correlation_lowers_the_bar_and_breadth_raises_it():
    indep, corr = preflight(n_specs=1000, n_periods=2520, reference_sharpe=1.0, rho=0.5).scenarios
    assert corr.critical_value < indep.critical_value and corr.power > indep.power
    required = [s for _, s in indep.breadth_table]
    assert required == sorted(required)


# -- bundled examples -------------------------------------------------------

@pytest.mark.parametrize("name,expected", [("null_grid", "FAIL"), ("real_edge", "PASS"),
                                           ("overwide", "INADMISSIBLE")])
def test_bundled_examples_return_their_documented_verdicts(name, expected):
    t = load_example(name)
    assert f"{t.n_specs:,}" in EXAMPLES[name]
    assert audit(t, B=1000, seed=0).status == expected


@pytest.mark.parametrize("name", sorted(EXAMPLES))
def test_bundled_artifacts_regenerate_from_their_seed(name):
    np.testing.assert_array_equal(load_example(name).returns, build_example(name, seed=0).returns)


def test_cli_audits_a_bundled_example(capsys):
    assert main(["audit", "--example", "real_edge", "--B", "500"]) == 0
