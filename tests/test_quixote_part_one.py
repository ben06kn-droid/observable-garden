"""Part one's last three items: the consistency check, `pick`, and twins.

The milestone standard applies where a scripted counterpart exists: `pick` by
Sharpe over every feature must be `extend_best`, bit for bit.
"""
import numpy as np
import pytest

from environments.dgp import DGPConfig, generate
from environments.sandbox import Sandbox
from garden.spec_class import SubsetClass
from quixote.consistency import check_picks, contradicted_steps
from quixote.grammar import Grammar, Move
from quixote.session import Session
from quixote.statistics import MINIMISED, STATISTICS, better, evaluate
from quixote.twins import (DESTROYS, K_FOR_ALPHA, Masking, block_permutation,
                           joint_time_permutation, twin_p_value, twins)


def _fixture(seed=0, K=8, T=600, s=1):
    cfg = DGPConfig(M=20, T=T, T_oos=200, K=K, s=s, rho=0.0, sigma=1.0, seed=seed)
    data = generate(cfg)
    cls = SubsetClass(max_size=3, signed=False)
    sb = Sandbox(data, periods_per_year=cfg.periods_per_year)
    return sb, cls, sb.base_feature_columns(), float(np.sqrt(cfg.periods_per_year))


# -- the statistic library ---------------------------------------------------

def test_the_library_is_fixed_and_computable_from_base_columns_alone():
    """ROADMAP 7.2: the statistic comes from a fixed, committed library, and the
    Replayable contract means a replicate must be able to recompute it."""
    assert set(STATISTICS) == {"sharpe", "volatility", "autocorr_1", "autocorr_5",
                               "corr_with_best"}
    stream = np.random.default_rng(0).normal(size=400)
    for name in STATISTICS:
        v = evaluate(name, stream, 1.0, best_stream=np.random.default_rng(1).normal(size=400))
        assert np.isfinite(v), name
    with pytest.raises(ValueError, match="IC is deliberately absent"):
        evaluate("ic", stream)


def test_smaller_is_better_where_it_should_be():
    assert MINIMISED == {"volatility", "corr_with_best"}
    assert better("sharpe", 1.0, 0.5) and not better("sharpe", 0.5, 1.0)
    assert better("volatility", 0.1, 0.2) and not better("volatility", 0.2, 0.1)
    assert better("sharpe", 1.0, float("nan"))           # a defined value beats NaN
    assert not better("sharpe", float("nan"), 1.0)


# -- pick --------------------------------------------------------------------

def test_pick_by_sharpe_over_everything_is_extend_best_bit_for_bit():
    """The milestone standard, where a counterpart exists: a pick whose rule is
    'best Sharpe among all features' must be the greedy extension exactly."""
    _, cls, base, ann = _fixture()
    g = Grammar(cls, base, ann)
    for support in ((), ((0, 1.0),), ((1, 1.0), (3, 1.0))):
        a = g.apply(support, Move("pick", statistic="sharpe", among=tuple(range(g.K))))
        b = g.apply(support, Move("extend_best"))
        assert a == b, support


def test_pick_counts_every_candidate_it_ranged_over():
    """A pick is a trial per candidate, not one trial: breadth is what the rule
    could have chosen."""
    _, cls, base, ann = _fixture()
    g = Grammar(cls, base, ann)
    _, _, n = g.apply((), Move("pick", statistic="volatility", among=(0, 1, 2)))
    assert n == 3
    _, _, n_all = g.apply((), Move("pick", statistic="sharpe", among=tuple(range(g.K))))
    assert n_all == g.K


def test_pick_selects_by_its_own_statistic_not_by_sharpe():
    _, cls, base, ann = _fixture()
    g = Grammar(cls, base, ann)
    among = (0, 1, 2, 3)
    chosen, _ = g.pick_choice((), Move("pick", statistic="volatility", among=among))
    vols = {j: evaluate("volatility", g.stream(((j, 1.0),)), ann) for j in among}
    assert chosen[0][0] == min(vols, key=vols.get)       # volatility is minimised


def test_the_else_branch_fires_when_the_premise_fails():
    """ROADMAP 7.2: `else` is what the rule does when its premise fails on a
    replicate; without one the harness falls back to the best of `among`."""
    _, cls, base, ann = _fixture()
    g = Grammar(cls, base, ann)
    # corr_with_best is undefined with nothing held: the premise fails
    m = Move("pick", statistic="corr_with_best", among=(0, 1, 2), else_statistic="volatility")
    chosen, used = g.pick_choice((), m)
    assert used == "volatility"
    vols = {j: evaluate("volatility", g.stream(((j, 1.0),)), ann) for j in (0, 1, 2)}
    assert chosen[0][0] == min(vols, key=vols.get)
    # and with no else, Sharpe decides
    chosen2, used2 = g.pick_choice((), Move("pick", statistic="corr_with_best", among=(0, 1, 2)))
    assert used2 == "sharpe"
    assert chosen2 == g.apply((), Move("pick", statistic="sharpe", among=(0, 1, 2)))[0]


def test_pick_is_refused_without_a_candidate_set():
    with pytest.raises(ValueError, match="names the candidate set"):
        Move("pick", statistic="sharpe")
    with pytest.raises(ValueError, match="only pick does"):
        Move("extend_best", among=(1, 2))


# -- the consistency check ---------------------------------------------------

def test_a_consistent_pick_is_recorded_replayable():
    sb, cls, base, ann = _fixture()
    sess = Session.on_sandbox(sb, cls)
    g = Grammar(cls, base, ann)
    rule_choice, _ = g.pick_choice((), Move("pick", statistic="sharpe", among=(0, 1, 2)))
    sess.propose(Move("pick", statistic="sharpe", among=(0, 1, 2),
                      choice=rule_choice[0][0]))
    sess.accept()
    assert sess.log.records[-1].replayable
    checks = check_picks(sess.log, cls, base, ann)
    assert len(checks) == 1 and checks[0].agrees
    assert "Consistent" in checks[0].reason()
    assert contradicted_steps(checks) == frozenset()


def test_a_pick_that_contradicts_its_rule_is_rejected_as_declared():
    """ROADMAP 7.2: 'A pick that contradicts its rule is rejected as declared and
    priced locally.' Rejected as declared means not replayable; the pricing is
    separate and, until 7.3, off."""
    sb, cls, base, ann = _fixture()
    sess = Session.on_sandbox(sb, cls)
    g = Grammar(cls, base, ann)
    rule_choice, _ = g.pick_choice((), Move("pick", statistic="sharpe", among=(0, 1, 2)))
    wrong = next(j for j in (0, 1, 2) if j != rule_choice[0][0])
    sess.propose(Move("pick", statistic="sharpe", among=(0, 1, 2), choice=wrong))
    sess.accept()
    rec = sess.log.records[-1]
    assert not rec.replayable                            # rejected as declared
    assert rec.support_after[0][0] == rule_choice[0][0]  # the harness still ran the rule
    checks = check_picks(sess.log, cls, base, ann)
    assert not checks[0].agrees
    assert "REJECTED AS DECLARED" in checks[0].reason()
    assert contradicted_steps(checks) == frozenset({0})


def test_the_check_is_free_because_the_harness_runs_the_rule():
    """Nothing extra is evaluated to check a pick: the rule's selection was
    computed in order to execute it."""
    sb, cls, base, ann = _fixture()
    sess = Session.on_sandbox(sb, cls)
    before = len(sb.transcript)
    sess.propose(Move("pick", statistic="sharpe", among=(0, 1, 2), choice=0))
    with_check = len(sb.transcript) - before
    sb2, cls2, _, _ = _fixture()
    sess2 = Session.on_sandbox(sb2, cls2)
    sess2.propose(Move("pick", statistic="sharpe", among=(0, 1, 2)))
    without_check = len(sb2.transcript)
    assert with_check == without_check


# -- twins and masking -------------------------------------------------------

def test_twins_keep_each_columns_values_and_the_cross_section_of_a_period():
    """`prereg/twin-calibration.md`: the same permutation across names, so each
    period's cross-section survives while serial structure does not."""
    base = np.random.default_rng(0).normal(size=(300, 6))
    t = joint_time_permutation(base, np.random.default_rng(1))
    for k in range(base.shape[1]):
        np.testing.assert_allclose(np.sort(t[:, k]), np.sort(base[:, k]))
    rows = {tuple(np.round(r, 12)) for r in base}
    assert all(tuple(np.round(r, 12)) in rows for r in t)      # whole rows moved together


def test_the_registered_K_gives_the_registered_attainable_level():
    assert K_FOR_ALPHA == {0.05: 19, 0.01: 99}
    assert twin_p_value(0.0, [0.5] * 19) == pytest.approx(1 / 20)
    assert twin_p_value(0.0, [0.5] * 99) == pytest.approx(1 / 100)
    assert twin_p_value(1.0, [0.5] * 19) == pytest.approx(1.0)


def test_the_twin_p_value_is_exact_under_exchangeability():
    """K+1 exchangeable runs: the real run's rank is uniform on the attainable
    grid, so the rate at the attainable level is at most that level."""
    rng = np.random.default_rng(0)
    K = 19
    fired = 0
    for _ in range(4000):
        draws = rng.uniform(size=K + 1)
        fired += twin_p_value(draws[0], draws[1:]) <= 1 / (K + 1)
    assert fired / 4000 <= 1 / (K + 1) + 0.01


def test_each_construction_says_what_it_destroys():
    assert set(DESTROYS) == {"joint_time_permutation", "block_permutation"}
    assert "volatility clustering" in DESTROYS["joint_time_permutation"]
    assert "approximate" in DESTROYS["block_permutation"]
    with pytest.raises(ValueError, match="registered ones"):
        twins(np.zeros((10, 2)), 2, construction="rotate")


def test_block_permutation_keeps_structure_inside_a_block():
    base = np.arange(120).reshape(60, 2).astype(float)
    t = block_permutation(base, np.random.default_rng(0), block=10)
    assert t.shape == base.shape
    steps = np.diff(t[:, 0])
    assert np.sum(steps == 2) >= 50          # most consecutive pairs still adjacent


def test_masking_hides_identity_and_exposes_only_structural_metadata():
    """`prereg/twin-calibration.md`: tickers and dates masked, structural
    metadata without identity, so a theory-driven pick stays possible."""
    meta = {"ASML": {"has_home_market": True, "home_close_et": "11:30", "sector": "tech",
                     "liquidity_band": "high"},
            "ARM": {"has_home_market": False}}
    m = Masking.build(["ASML", "ARM"], meta, seed=0)
    view = m.agent_view()
    assert set(view) == set(m.labels.values())
    assert not any(t in str(view) for t in ("ASML", "ARM"))
    assert view[m.mask("ASML")]["home_close_et"] == "11:30"
    assert m.unmask(m.mask("ARM")) == "ARM"               # harness-only
    assert all(k in Masking.ALLOWED_FIELDS for v in view.values() for k in v)


def test_masking_refuses_metadata_that_would_identify_a_name():
    with pytest.raises(ValueError, match="identifying fields"):
        Masking.build(["ASML"], {"ASML": {"ticker": "ASML", "has_home_market": True}})


def test_sequential_stopping_is_absent_on_purpose():
    """`prereg/twin-calibration.md`: every certification runs the full K until
    Besag & Clifford's two open checks are resolved."""
    import importlib
    import sys
    importlib.import_module("quixote.twins")
    # `quixote/__init__.py` re-exports the `twins` FUNCTION, which shadows the
    # submodule attribute, so the module is reached through sys.modules.
    tw = sys.modules["quixote.twins"]
    src = " ".join(__import__("pathlib").Path(tw.__file__).read_text().lower().split())
    assert "sequential stopping is deliberately absent" in src
    assert not hasattr(tw, "sequential_twin_p_value")
