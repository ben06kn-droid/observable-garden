"""The real-data sandbox, rule by registered rule.

Each test names the pre-registration line it enforces. The panels are built from
the fetched data where it is present and skipped where it is not, so the suite
runs on a machine that has neither.

The cost estimator's known-answer test is `tests/test_adr_costs.py` and is not
repeated here; what is tested here is that the panel uses it, at the registered
window and floor.
"""
import datetime as dt
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent

from environments.real_panel import (ADR_HOME, ADR_SPREAD_SESSIONS, ETF_BORROW_BPS_YR,  # noqa: E402
                                     ETF_COST_BPS, build_adr_panel, build_etf_panel)
from environments.real_sandbox import RealSandbox  # noqa: E402
from environments.sandbox import Distribution, Sandbox, Specification  # noqa: E402

ETF_DIR = REPO / "data" / "raw" / "etf_insample"
ADR_DIR = REPO / "data" / "raw"
have_etf = pytest.mark.skipif(not list(ETF_DIR.glob("*.csv")) if ETF_DIR.exists() else True,
                              reason="the in-sample ETF export is not on this machine")
have_adr = pytest.mark.skipif(not (ADR_DIR / "ASML_5min_adj.csv.gz").exists(),
                              reason="the ADR bars are not on this machine")


@pytest.fixture(scope="module")
def etf():
    return build_etf_panel()


@pytest.fixture(scope="module")
def adr():
    return build_adr_panel(names=["ASML", "SAP", "NOK", "AZN", "NVO", "ERIC"])


# -- the sandbox contract ----------------------------------------------------

@have_etf
def test_the_contract_matches_the_synthetic_sandbox(etf):
    """Same searcher-visible API as environments.sandbox.Sandbox."""
    sb = RealSandbox(etf)
    for name in ("get_data", "evaluate", "submit", "num_features", "num_periods",
                 "num_assets", "transcript", "submission", "returns_matrix",
                 "base_feature_columns"):
        assert hasattr(sb, name), name
        assert hasattr(Sandbox, name), name


@have_etf
def test_every_evaluate_is_logged_with_its_full_return_stream(etf):
    """`environments/sandbox.py`: 'Every call is logged with its full return
    stream, regardless of whether the searcher goes on to use the result.'"""
    sb = RealSandbox(etf)
    w = np.zeros(sb.num_features); w[0] = 1.0
    r1 = sb.evaluate(Specification(weights=w, name="a"))
    sb.evaluate(Specification(weights=-w, name="b"))          # result ignored
    assert len(sb.transcript) == 2
    for e in sb.transcript:
        assert e.return_stream.shape == (sb.num_periods,)
    assert sb.returns_matrix().shape == (sb.num_periods, 2)
    assert r1.n_periods == sb.num_periods


@have_etf
def test_there_is_no_out_of_sample_data_to_reach(etf):
    """The no-out-of-sample variant: the synthetic sandbox grades from held-out
    data it holds; this one holds none, and grading is a separate entry point
    (`prereg/agent-on-real-data.md`, 'The holdout is never on the machine the
    agent runs on')."""
    sb = RealSandbox(etf)
    assert not hasattr(sb, "oos_sharpe_for_grading")
    assert hasattr(Sandbox, "oos_sharpe_for_grading")          # the contrast is the point
    assert not any("oos" in k.lower() for k in vars(sb))
    src = (REPO / "environments" / "real_sandbox.py").read_text()
    assert "grade_real" not in src.replace("experiments/grade_real.py", "")
    for p in (REPO / "environments").glob("*.py"):
        assert "import grade_real" not in p.read_text(), p


@have_etf
def test_submit_takes_a_distribution(etf):
    sb = RealSandbox(etf)
    w = np.zeros(sb.num_features); w[0] = 1.0
    with pytest.raises(TypeError):
        sb.submit(Specification(weights=w, name="x"), 1.0)
    sb.submit(Specification(weights=w, name="x"), Distribution.degenerate(0.5))
    assert sb.submission[1].mean == 0.5


@have_etf
def test_a_declared_class_is_enforced(etf):
    from garden.spec_class import SubsetClass
    sb = RealSandbox(etf, spec_class=SubsetClass(max_size=2, signed=True))
    w = np.zeros(sb.num_features); w[:3] = 1.0
    with pytest.raises(ValueError, match="outside the declared class"):
        sb.evaluate(Specification(weights=w, name="too wide"))


# -- the daily ETF panel's registered rules ---------------------------------

@have_etf
def test_etf_in_sample_ends_where_the_split_says(etf):
    """`prereg/agent-on-real-data.md`: 'In-sample: 2005-01-01 to 2022-12-31.'"""
    assert max(etf.meta["dates"]) <= dt.date(2022, 12, 31)
    assert etf.features.shape[2] == 40                      # K = 40 (etf-features.md)
    assert len(etf.feature_names) == 40
    assert all(n.endswith(("_z", "_rank")) for n in etf.feature_names)


@have_etf
def test_etf_timing_is_signal_at_t_held_from_t_plus_one_to_t_plus_two(etf):
    """`prereg/agent-on-real-data.md`: 'signal computed at the close of day t ...
    position held from the close of t+1 to the close of t+2.' So the return a
    weight earns at row t is the panel's own r[t+2], never r[t] or r[t+1]."""
    from data.etf_loader import load_panel
    panel = load_panel()
    dates = etf.meta["dates"]
    tk = etf.assets[0]
    d_all, adj, _ = panel[tk]
    pos = {d: i for i, d in enumerate(d_all)}
    for row in (0, 5, 100):
        i = pos[dates[row]]
        expected = adj[i + 2] / adj[i + 1] - 1.0
        assert etf.returns[row, 0] == pytest.approx(expected, rel=1e-12)


@have_etf
def test_etf_costs_are_five_bps_one_way_and_fifty_bps_borrow(etf):
    """`prereg/agent-on-real-data.md`'s execution table: 5 bps one-way per unit
    of turnover, 50 bps a year on short notional, charged daily."""
    assert np.allclose(etf.cost_rate, ETF_COST_BPS * 1e-4)
    assert np.allclose(etf.borrow_rate, ETF_BORROW_BPS_YR * 1e-4 / 252)
    w = np.zeros((2, len(etf.assets)))
    w[0, 0], w[0, 1] = 0.5, -0.5                            # one long, one short
    panel = etf
    small = type(panel)(**{**panel.__dict__, "returns": np.zeros((2, len(panel.assets))),
                           "cost_rate": panel.cost_rate[:2], "borrow_rate": panel.borrow_rate[:2],
                           "features": panel.features[:2], "tradable": panel.tradable[:2],
                           "session_start": panel.session_start[:2],
                           "session_end": panel.session_end[:2]})
    stream = small.net_stream(w)
    # turnover 1.0 in, 1.0 out; borrow on 0.5 short for one period
    assert stream[0] == pytest.approx(-(1.0 * ETF_COST_BPS * 1e-4)
                                      - 0.5 * ETF_BORROW_BPS_YR * 1e-4 / 252, rel=1e-9)
    assert stream[1] == pytest.approx(-(1.0 * ETF_COST_BPS * 1e-4), rel=1e-9)


@have_etf
def test_the_panel_is_dollar_neutral_at_gross_one(etf):
    """`prereg/etf-features.md`: 'demeaned and scaled to gross exposure 1.'"""
    w = np.zeros(len(etf.feature_names)); w[0] = 1.0
    wt = etf.weights_from(etf.scores_for_weights(w))
    rows = wt[:50]
    assert np.allclose(rows.sum(axis=1), 0.0, atol=1e-12)
    assert np.allclose(np.abs(rows).sum(axis=1), 1.0, atol=1e-12)


# -- the five-minute ADR panel's registered rules ---------------------------

@have_adr
def test_adr_session_is_76_traded_bars_with_the_first_and_last_dropped(adr):
    """`prereg/adr-universe.md` as amended: 'US regular session, 09:35-15:55 ET
    traded, first and last bars dropped', so 76 bars a session."""
    assert adr.meta["bars_per_session"] == 76
    assert adr.features.shape[0] == 76 * len(adr.meta["sessions"])
    assert adr.meta["traded_window"].startswith("09:35-15:50")


@have_adr
def test_adr_is_flat_overnight_and_opens_on_its_own_bar(adr):
    """`prereg/adr-features.md` section 4: 'Flat overnight. Every position opens
    at or after 09:35 and is closed by 15:55.'"""
    assert adr.flat_overnight
    w = np.zeros(len(adr.feature_names)); w[0] = 1.0
    wt = adr.weights_from(adr.scores_for_weights(w))
    assert np.allclose(wt[adr.session_end], 0.0)            # closed by the last traded bar
    nb = adr.meta["bars_per_session"]
    for s in np.flatnonzero(adr.session_start)[:3]:
        prev = wt[s - 1] if s else np.zeros(wt.shape[1])
        assert np.allclose(prev, 0.0)                       # nothing is carried across


@have_adr
def test_adr_transition_bars_are_not_traded(adr):
    """`prereg/adr-universe.md`: 'Bars between a name's continuous end and its
    auction end are flagged TRANSITION and are not traded', two bars for the
    Euronext/Xetra/London names and one for the Nordic ones."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    nb = adr.meta["bars_per_session"]
    for mi, tk in enumerate(adr.assets):
        mic, tzname, (hh, mm), n_trans = ADR_HOME[tk]
        day = adr.meta["sessions"][10]
        cont = dt.datetime.combine(day, dt.time(hh, mm), ZoneInfo(tzname)).astimezone(et)
        rows = [10 * nb + b for b in range(nb)]
        blocked = 0
        for r in rows:
            b = r - 10 * nb
            start = dt.datetime.combine(day, dt.time(9, 35), et) + dt.timedelta(minutes=5 * b)
            if cont <= start < cont + dt.timedelta(minutes=5 * n_trans):
                assert not adr.tradable[r, mi], (tk, start)
                blocked += 1
        assert blocked == n_trans, (tk, blocked, n_trans)


@have_adr
def test_adr_missing_bars_hold_the_position_and_return_zero(adr):
    """`prereg/adr-features.md` section 4: a missing regular-session bar 'carries
    the price forward with zero return; the name's position is held and not
    re-traded in that bar.'"""
    missing = ~adr.present          # a bar with no data, not a TRANSITION bar
    assert missing.any(), "this fixture has no missing bar to test"
    assert np.all(adr.returns[missing] == 0.0)
    assert not np.any(adr.tradable[missing])
    w = np.zeros(len(adr.feature_names)); w[0] = 1.0
    wt = adr.weights_from(adr.scores_for_weights(w))
    # a TRANSITION bar is untradable but does have a return: it accrues to the
    # position held (prereg/adr-features.md section 4)
    transition = (~adr.tradable) & adr.present
    assert transition.any() and np.any(adr.returns[transition] != 0.0)
    rows, cols = np.nonzero(missing)
    inner = [(r, c) for r, c in zip(rows, cols)
             if r > 0 and not adr.session_start[r] and not adr.session_end[r]]
    for r, c in inner[:20]:
        assert wt[r, c] == wt[r - 1, c]                      # frozen, not re-traded


@have_adr
def test_adr_gap_feature_is_missing_on_ex_dates_including_ULs_two(adr):
    """`prereg/adr-features.md` section 5 and amendment 1 A4: the gap is missing
    on each name's ex-dates, and on UL's 2025-12-08 and 2025-12-09."""
    ex = adr.meta["ex_dates"]
    assert "2025-12-08" in ex["UL"] and "2025-12-09" in ex["UL"]
    gap_cols = [i for i, n in enumerate(adr.feature_names) if n.startswith("gap")]
    nb = adr.meta["bars_per_session"]
    for mi, tk in enumerate(adr.assets):
        days = [d for d in adr.meta["sessions"] if d.isoformat() in ex.get(tk, ())]
        if not days:
            continue
        si = adr.meta["sessions"].index(days[0])
        assert np.allclose(adr.features[si * nb:(si + 1) * nb, mi, gap_cols], 0.0)
        break


@have_adr
def test_adr_costs_use_the_registered_estimator_window_and_floor(adr):
    """`prereg/adr-features.md` amendment 1 A1/A2: Abdi-Ranaldo on 5-minute bars
    over the 20 sessions before the one priced, floored at max(one cent, 2 bps),
    plus $0.005 a share. The estimator's own known-answer test is
    tests/test_adr_costs.py; this checks the panel uses it as registered."""
    from data.adr_costs import FLOOR_BPS
    assert ADR_SPREAD_SESSIONS == 20
    assert np.all(adr.cost_rate > 0)
    assert np.all(adr.cost_rate >= FLOOR_BPS * 1e-4 / 2)     # at least half the floor
    assert adr.meta["fee_per_share"] == 0.005
    assert adr.meta["spread_sessions"] == 20


@have_adr
def test_adr_charges_at_least_two_half_spreads_a_day_for_a_held_name(adr):
    """`prereg/adr-features.md` amendment 1: 'Flat overnight implies at least two
    half-spreads and two fees per held name per session.'"""
    nb = adr.meta["bars_per_session"]
    w = np.zeros(len(adr.feature_names)); w[0] = 1.0
    wt = adr.weights_from(adr.scores_for_weights(w))
    prev = np.vstack([np.zeros((1, wt.shape[1])), wt[:-1]])
    turn = np.abs(wt - prev)
    for s in range(3):
        rows = slice(s * nb, (s + 1) * nb)
        held = np.abs(wt[rows]).max(axis=0)
        traded_in_out = turn[rows].sum(axis=0)
        for mi in np.flatnonzero(held > 0):
            assert traded_in_out[mi] >= 2 * held[mi] - 1e-12, adr.assets[mi]


@have_adr
def test_the_ancestor_guard_runs_before_any_adr_feature_is_built(monkeypatch):
    """`prereg/adr-features.md`: 'The feature-building code refuses to run unless
    this commit is an ancestor of HEAD.'"""
    from data import adr_guard
    called = {"n": 0}
    real = adr_guard.require_registered_features

    def spy(**kw):
        called["n"] += 1
        return real(**kw)

    monkeypatch.setattr(adr_guard, "require_registered_features", spy)
    build_adr_panel(names=["ASML"])
    assert called["n"] == 1

    def refuse(**kw):
        raise adr_guard.RegistrationRefused("registration missing")

    monkeypatch.setattr(adr_guard, "require_registered_features", refuse)
    with pytest.raises(adr_guard.RegistrationRefused):
        build_adr_panel(names=["ASML"])


# -- offline grading ---------------------------------------------------------

def test_grading_refuses_until_the_submissions_are_sealed():
    """`prereg/agent-on-real-data.md`: 'Holdout grading refuses unless ... a
    sealed-submissions commit ... is an ancestor.'"""
    from experiments.grade_real import GradingRefused, require_sealed_submissions
    with pytest.raises(GradingRefused, match="not in this repository"):
        require_sealed_submissions("0" * 40)


def test_grading_refuses_a_sealed_archive_or_the_desktop(tmp_path):
    from experiments.grade_real import load_holdout
    from data.etf_loader import HoldoutRefused
    p = tmp_path / "holdout.tar.gz.enc"
    p.write_bytes(b"x")
    with pytest.raises(HoldoutRefused):
        load_holdout(p)
    with pytest.raises(HoldoutRefused):
        load_holdout(Path.home() / "Desktop")


def test_grading_scores_a_submission_on_plaintext_holdout_rows(tmp_path):
    """Grading works on a plaintext directory, which is what the author's
    decrypt-to-temporary-directory step produces."""
    from experiments.grade_real import grade, load_holdout
    rng = np.random.default_rng(0)
    days = [dt.date(2023, 1, 1) + dt.timedelta(days=i) for i in range(400)]
    for tk in ("SPY", "AAA", "BBB"):
        px = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
        (tmp_path / f"{tk}.csv").write_text(
            "date,adjclose,volume\n" + "".join(f"{d},{p},1000\n" for d, p in zip(days, px)))
    holdout = load_holdout(tmp_path)
    w = np.zeros(40); w[0] = 1.0
    rows = grade([{"name": "s", "weights": w.tolist()}], holdout)
    assert rows[0]["n_periods"] == 400
    assert rows[0]["net_sharpe"] <= rows[0]["gross_sharpe"] + 1e-9    # costs only subtract
