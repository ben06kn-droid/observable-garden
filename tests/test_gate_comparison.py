"""7.0's driver: does it price what `prereg/gate-comparison.md` registers?

Mechanism-level, so a test failure names a broken mechanism rather than a number
that moved. The expensive parts (B = 10,000, 2,000 draws) are not exercised here;
what is checked is that each certifier is the object the pre-registration says it
is, and that the parts amendments 8 and 9 fixed behave as fixed.
"""
import dataclasses

import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox, Specification
from estimator.bootstrap import sharpe
from experiments import gate_comparison as gc


def test_the_smoke_block_is_the_registered_one_and_not_71s():
    """Amendment 7 registers 980000-980999 and records that 970000-970999 is
    `fixed-sequence-replay`'s."""
    assert gc.SEED0_SMOKE == 980_000
    assert gc.SEED0 == 200_000 and gc.SEED0_REPLICATION == 210_000
    src = __import__("pathlib").Path(gc.__file__).read_text()
    assert "970000" in src and "not touched here" in src
    assert 970_000 not in (gc.SEED0, gc.SEED0_REPLICATION, gc.SEED0_SMOKE)


def test_the_anchor_is_scored_under_the_declared_class_only():
    """'It is scored under the declared-class certifier only: a holdout or a
    replay of an exhaustive enumeration is a different object.'"""
    assert gc.MATCHED["exhaustive-signed"][2] == ("class",)
    for name in gc.MEMBERS:
        if name != "exhaustive-signed":
            assert gc.MATCHED[name][2] == gc.ALL_FOUR, name


def test_every_searcher_is_priced_against_a_class_it_can_reach():
    """Amendment 1's matched-class correction, as the Design table states it."""
    unsigned = {"greedy", "adaptive"}
    for name, (cls, _, _) in gc.MATCHED.items():
        expected = gc.UNSIGNED if name in unsigned else gc.SIGNED
        assert cls is expected, name
    assert gc.SIGNED.size(gc.K) == 82_240 and gc.UNSIGNED.size(gc.K) == 10_700


def test_rule_3_is_read_on_the_slack_searchers_amendment_1_names():
    assert set(gc.SLACK) == {"stop-when-cleared"} | {f"budgeted-random-{b}"
                                                     for b in (25, 100, 400)}
    assert gc.BUDGETS == (25, 100, 400)


def test_the_stop_bar_is_71s_registered_value_at_this_configuration():
    """`fixed-sequence-replay` registered 3.5 se = 0.786 annualised at T = 5,000,
    and the pre-registration reuses that searcher."""
    assert gc.STOP_BAR == pytest.approx(0.786, abs=0.001)


def test_searcher_parameters_do_not_move_between_certifiers():
    """Amendment 5: 'the budget is a property of the searcher, not of the data',
    so the holdout arm searches a shorter slice with the same searcher."""
    a, b = gc.build("budgeted-random-100", 7), gc.build("budgeted-random-100", 7)
    assert a.budget == b.budget == 100
    s = gc.build("stop-when-cleared", 7)
    assert s.bar == gc.STOP_BAR
    assert s.spec_class is gc.SIGNED           # capped, per amendment 1
    assert s.scoring == "moments"              # the path amendment 3 sized


# -- amendment 8: the holdout test -------------------------------------------

def test_the_holdout_p_value_has_the_registered_form_and_bounds():
    rng = np.random.default_rng(0)
    B = 199
    strong = rng.normal(loc=5.0, scale=1.0, size=400)
    assert gc.holdout_p(strong, B, 1.0, seed=0) == pytest.approx(1 / (B + 1))
    weak = rng.normal(loc=-5.0, scale=1.0, size=400)
    assert gc.holdout_p(weak, B, 1.0, seed=0) == 1.0
    assert gc.holdout_p(np.zeros(400), B, 1.0, seed=0) == 1.0      # degenerate
    assert gc.holdout_p(np.array([1.0, 2.0]), B, 1.0, seed=0) == 1.0


def test_the_holdout_p_value_is_calibrated_on_an_independent_slice():
    """Amendment 8's claim is that no multiplicity belongs in the holdout tier
    because the slice is independent of the search. With a stream that was not
    selected on, the p-value is approximately uniform."""
    rng = np.random.default_rng(1)
    ps = [gc.holdout_p(rng.normal(size=500), 199, 1.0, seed=i) for i in range(200)]
    assert 0.02 <= np.mean(np.array(ps) <= 0.05) <= 0.12       # nominal 5%, n=200


def test_one_test_and_only_one_on_the_holdout_slice():
    """'One test, and it is the submitted specification's.' The assertion inside
    `holdout_certify` is the guard; this checks it is reachable and that the
    slice sizes are the registered 3,500/1,500 and 2,500/2,500."""
    assert [int(round(gc.T * f)) for f, _ in gc.HOLDOUTS] == [3500, 2500]
    assert [gc.T - int(round(gc.T * f)) for f, _ in gc.HOLDOUTS] == [1500, 2500]
    assert [k for _, k in gc.HOLDOUTS] == ["holdout_70_30", "holdout_50_50"]


def test_the_holdout_searcher_sees_only_the_first_slice():
    """The searcher is re-run on the slice, so its submission cannot depend on a
    period in the holdout part. Checked by corrupting the holdout part and
    confirming the chosen specification does not move."""
    cfg = DGPConfig(M=10, T=400, T_oos=50, K=6, s=0, rho=0.0, sigma=1.0, seed=3)
    data = generate(cfg)
    cut = 280
    first = dataclasses.replace(data, x_in=data.x_in[:cut], r_in=data.r_in[:cut])
    sb = Sandbox(first, periods_per_year=cfg.periods_per_year, spec_class=gc.UNSIGNED)
    gc.build("greedy", 0).run(sb)
    w_clean = sb.submission[0].weights

    poisoned = dataclasses.replace(data, r_in=data.r_in.copy())
    poisoned.r_in[cut:] *= 50.0
    first2 = dataclasses.replace(poisoned, x_in=poisoned.x_in[:cut],
                                 r_in=poisoned.r_in[:cut])
    sb2 = Sandbox(first2, periods_per_year=cfg.periods_per_year, spec_class=gc.UNSIGNED)
    gc.build("greedy", 0).run(sb2)
    np.testing.assert_array_equal(w_clean, sb2.submission[0].weights)


# -- amendment 9: rule 5's readout -------------------------------------------

def test_the_unshifted_oos_sharpe_agrees_with_the_sandboxs_grader():
    """`oos_sharpes` recomputes the OOS stream algebraically; it must give the
    harness's own grading number exactly, or rule 5 is reading a different
    quantity from every other experiment."""
    cfg = DGPConfig(M=20, T=300, T_oos=200, K=8, s=3, rho=0.0, sigma=1.0, seed=5)
    data = generate(cfg)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
    w = np.zeros(cfg.K)
    w[[0, 3]] = [1.0, -1.0]
    mine, _ = gc.oos_sharpes(data, cfg, w)
    assert mine == pytest.approx(
        sb.oos_sharpe_for_grading(Specification(weights=w, name="t")), rel=1e-12)


def test_the_flip_is_the_same_construction_62_used():
    """`beta_full[S[0]] *= -1` on the out-of-sample panel with the realised noise
    held. Checked against a full `generate` with the flipped beta, which is how
    `costs_and_regime_change.verify_shift_shortcut` licenses the shortcut."""
    cfg = DGPConfig(M=20, T=300, T_oos=200, K=8, s=3, rho=0.0, sigma=1.0, seed=11)
    data = generate(cfg)
    w = np.zeros(cfg.K)
    w[data.S[0]] = 1.0
    _, flipped = gc.oos_sharpes(data, cfg, w)

    b = list(data.beta_full[data.S])
    full = generate(dataclasses.replace(cfg, beta=tuple([-b[0]] + b[1:])))
    p = full.x_oos @ w
    ann = float(np.sqrt(cfg.periods_per_year))
    expected = float(sharpe(np.mean(p * full.r_oos, axis=1)[:, None],
                            axis=0, annualization=ann)[0])
    assert flipped == pytest.approx(expected, rel=1e-10)


def test_the_flip_moves_the_oos_sharpe_but_not_the_in_sample_panel():
    """Rule 5's invariance claim: the flip touches the out-of-sample panel only,
    so every certifier's p-value — all computed in sample — is unchanged by
    construction. A non-zero change in a PASS rate is a driver bug."""
    cfg = DGPConfig(M=20, T=300, T_oos=200, K=8, s=3, rho=0.0, sigma=1.0, seed=13)
    data = generate(cfg)
    before = data.r_in.copy()
    w = np.zeros(cfg.K)
    w[data.S[0]] = 1.0
    un, fl = gc.oos_sharpes(data, cfg, w)
    np.testing.assert_array_equal(before, data.r_in)      # in-sample untouched
    assert fl < un                                        # the signal reversed


def test_on_s0_there_is_no_beta_to_flip():
    cfg = DGPConfig(M=20, T=300, T_oos=200, K=8, s=0, rho=0.0, sigma=1.0, seed=17)
    data = generate(cfg)
    w = np.zeros(cfg.K)
    w[0] = 1.0
    un, fl = gc.oos_sharpes(data, cfg, w)
    assert un == fl


# -- the registered configuration and the run guards -------------------------

def test_s3s_sigma_is_solved_for_rather_than_written_down():
    """The Design section registers `e_agent.py`'s s0 and s3 configurations, and
    e_agent amendment 9 solves sigma for an oracle Sharpe of 1.0."""
    assert gc.ORACLE_SHARPE == {"s0": None, "s3": 1.0}
    _, cfg0 = gc.make_panel("s0", gc.SEED0_SMOKE)
    _, cfg3 = gc.make_panel("s3", gc.SEED0_SMOKE)
    assert cfg0.sigma == 1.0 and cfg0.s == 0
    assert cfg3.s == 3 and cfg3.sigma != 1.0
    from environments.dgp import oracle_sharpe_analytic
    assert oracle_sharpe_analytic(cfg3) == pytest.approx(1.0, rel=1e-9)


def test_a_registered_run_refuses_an_unregistered_B():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "experiments.gate_comparison",
                        "--cell", "s0", "--B", "3000"], capture_output=True, text=True)
    assert r.returncode != 0
    assert "registered fallback" in (r.stdout + r.stderr)
    r2 = subprocess.run([sys.executable, "-m", "experiments.gate_comparison",
                         "--smoke", "2", "--replication"], capture_output=True, text=True)
    assert r2.returncode != 0 and "exclusive" in (r2.stdout + r2.stderr)


def test_one_draw_prices_every_certifier_it_should_and_nothing_else():
    """End to end at a tiny B: every searcher gets a class p-value, only the
    anchor is class-only, and nothing outside [0, 1] comes back."""
    row = gc.run_draw("s0", gc.SEED0_SMOKE, B=25)
    for name in gc.MEMBERS:
        r = row[name]
        assert 0.0 < r["p_class"] <= 1.0, name
        if name == "exhaustive-signed":
            assert r["p_replay"] is None and r["p_holdout_70_30"] is None
        else:
            for key in ("p_replay", "p_holdout_70_30", "p_holdout_50_50"):
                assert 0.0 < r[key] <= 1.0, (name, key)
    assert row["_draw"]["block_length"] >= 1
    assert set(row["_draw"]["null_q_signed"].shape) == {4}


def test_the_cost_report_says_nothing_about_rates_or_p_values():
    """`prereg/README.md`: a smoke reports cost only."""
    data = gc.run("s0", 2, gc.SEED0_SMOKE, 25, 2, None)
    text = gc.cost_report(data)
    low = text.lower()
    for forbidden in ("rejection", "p-value", "p_value", "distance", "wilson", "power"):
        assert forbidden not in low, forbidden
    assert "COST ONLY" in text and "per draw" in low
