"""The real-data class table: is the replayed statistic the one the search ran on?

`prereg/agent-pilot.md` amendment 3 recorded the failure this fixes — on a
net-of-cost panel the base-column replay priced a different statistic, and the
identity-replicate guard refused every replay-arm run. The milestone is that the
guard now passes, and passes **bit-identically**, because both sides read the
same stored stream.

These tests build a small table on a synthetic `RealPanel`, so they are fast. The
real ADR table is exercised by `tests/test_class_table_adr.py`, which skips when
it has not been built.
"""
import numpy as np
import pytest

from environments.class_table import (ClassTable, build_class_table, canonical,
                                      members_in_order)
from environments.real_panel import RealPanel
from environments.real_sandbox import RealSandbox
from environments.sandbox import Specification
from garden.spec_class import SubsetClass
from quixote.grammar import Move
from quixote.replay import identity_check
from quixote.session import Session

CLS = SubsetClass(max_size=2, signed=True)


def _panel(T=300, M=6, K=4, seed=0):
    rng = np.random.default_rng(seed)
    return RealPanel(
        features=rng.normal(size=(T, M, K)),
        returns=rng.normal(size=(T, M)) * 0.01,
        tradable=np.ones((T, M), dtype=bool),
        present=np.ones((T, M), dtype=bool),
        cost_rate=np.full((T, M), 0.0005),
        borrow_rate=np.full((T, M), 0.0002),
        periods_per_year=252,
        session_start=np.zeros(T, dtype=bool),
        session_end=np.zeros(T, dtype=bool),
        flat_overnight=False,
        name="synthetic",
        assets=[f"A{i}" for i in range(M)],
        feature_names=[f"f{k}" for k in range(K)],
    )


def _table(tmp_path, panel=None, cls=CLS):
    panel = panel or _panel()
    return build_class_table(panel, cls, "synthetic",
                             path=tmp_path / "t.npy", rebuild=True), panel


# -- the table itself --------------------------------------------------------

def test_the_table_holds_every_member_once_in_the_engines_order(tmp_path):
    table, panel = _table(tmp_path)
    K = panel.features.shape[2]
    assert table.N == CLS.size(K)
    assert len(set(canonical(m) for m in table.members)) == table.N
    # the order is the full-class engine's: by size, then by members()
    assert all(len(a) <= len(b) for a, b in zip(table.members, table.members[1:]))


def test_a_column_is_exactly_the_panels_own_net_stream(tmp_path):
    """Not 'to a tolerance': the table stores what the panel computes."""
    table, panel = _table(tmp_path)
    K = panel.features.shape[2]
    for support in (((0, 1.0),), ((1, -1.0),), ((0, 1.0), (2, -1.0))):
        w = np.zeros(K)
        for k, s in support:
            w[k] = s
        expected = panel.stream_for_scores(panel.scores_for_weights(w))
        np.testing.assert_array_equal(table.stream(support), expected)


def test_a_support_is_the_same_member_whatever_order_it_was_built_in(tmp_path):
    table, _ = _table(tmp_path)
    assert table.column(((0, 1.0), (2, -1.0))) == table.column(((2, -1.0), (0, 1.0)))


def test_a_non_member_is_refused_rather_than_approximated(tmp_path):
    table, _ = _table(tmp_path)
    with pytest.raises(KeyError, match="not a member"):
        table.column(((0, 1.0), (1, 1.0), (2, 1.0)))     # depth 3 in a depth-2 class


def test_the_table_is_reused_only_for_the_panel_it_was_built_on(tmp_path):
    table, panel = _table(tmp_path)
    first = np.array(table.streams[:, 0])           # a COPY: the memmap is the file,
    again = build_class_table(panel, CLS, "synthetic", path=tmp_path / "t.npy")
    assert again.panel_hash == table.panel_hash     # and a rebuild rewrites the file
    np.testing.assert_array_equal(again.streams[:, 0], first)
    other = _panel(seed=99)
    rebuilt = build_class_table(other, CLS, "synthetic", path=tmp_path / "t.npy")
    assert rebuilt.panel_hash != table.panel_hash
    assert not np.array_equal(np.array(rebuilt.streams[:, 0]), first)


# -- the sandbox scores by lookup -------------------------------------------

def test_evaluate_by_lookup_equals_evaluate_by_computation_bit_for_bit(tmp_path):
    table, panel = _table(tmp_path)
    K = panel.features.shape[2]
    plain = RealSandbox(panel, spec_class=CLS)
    looked = RealSandbox(panel, spec_class=CLS, class_table=table)
    for support in (((0, 1.0),), ((3, -1.0),), ((1, 1.0), (2, -1.0))):
        w = np.zeros(K)
        for k, s in support:
            w[k] = s
        spec = Specification(weights=w, name="x")
        a, b = plain.evaluate(spec), looked.evaluate(spec)
        assert a.sharpe == b.sharpe and a.mean == b.mean and a.std == b.std
        np.testing.assert_array_equal(plain.transcript[-1].return_stream,
                                      looked.transcript[-1].return_stream)


# -- the milestone -----------------------------------------------------------

def _drive(sandbox, cls):
    """A scripted policy through the session: anchor, extend, stop."""
    sess = Session.on_sandbox(sandbox, cls, name_prefix="t")
    sess.propose(Move("init"))
    sess.accept()
    sess.propose(Move("extend_best"))
    sess.accept()
    return sess


def test_the_identity_guard_passes_bit_identically_with_a_table(tmp_path):
    """The milestone. Without a table the guard fails on a net-of-cost panel,
    because the base-column replay is a different statistic; with one, the
    replayed score equals the realized score exactly."""
    table, panel = _table(tmp_path)
    sb = RealSandbox(panel, spec_class=CLS, class_table=table)
    sess = _drive(sb, CLS)
    base = sb.base_feature_columns()
    ann = float(np.sqrt(panel.periods_per_year))

    guard = identity_check(sess.log, CLS, base, ann, score_fn=table.scorer(None))
    assert guard.agrees, guard.reason()
    assert guard.score_gap == 0.0                      # bit-identical, not near
    assert "PASS" in guard.reason()


def test_without_the_table_the_guard_is_entitled_to_fail_on_a_net_panel(tmp_path):
    """The failure the table exists to remove, kept as a test so the reason for
    the table cannot be forgotten. The base-column path is not wrong in itself —
    it is wrong for a statistic that is not linear in the basis."""
    table, panel = _table(tmp_path)
    sb = RealSandbox(panel, spec_class=CLS, class_table=table)
    sess = _drive(sb, CLS)
    base = sb.base_feature_columns()
    ann = float(np.sqrt(panel.periods_per_year))
    plain = identity_check(sess.log, CLS, base, ann)           # no score_fn
    with_table = identity_check(sess.log, CLS, base, ann, score_fn=table.scorer(None))
    assert with_table.score_gap == 0.0
    assert plain.score_gap > with_table.score_gap


def test_a_scripted_policy_through_the_adapter_reproduces_its_direct_session_run(tmp_path):
    """The second half of the milestone, on the real-panel surface: the tool
    adapter and a direct Session must be the same run, table and all."""
    from quixote.agent_adapter import QuixoteAgent, ToolSession

    table, panel = _table(tmp_path)

    def policy(tools: ToolSession) -> None:
        tools.call("init")
        tools.call("extend_best")
        tools.call("stop", trigger="best_so_far_above", param=-99.0)
        tools.call("submit")

    sb_a = RealSandbox(panel, spec_class=CLS, class_table=table)
    agent = QuixoteAgent(CLS, policy)
    agent.run(sb_a)

    sb_b = RealSandbox(panel, spec_class=CLS, class_table=table)
    sess = Session.on_sandbox(sb_b, CLS, name_prefix="quixote-agent")
    from quixote.triggers import Trigger
    sess.propose(Move("init"))
    sess.accept()
    sess.propose(Move("extend_best"))
    sess.accept()
    t = Trigger(kind="best_so_far_above", param=-99.0, action="stop")
    fires, value, stamp = sess.evaluate_trigger(t)
    assert fires
    sess.stop(t, value, stamped_at=stamp)

    fields = ("step", "support_after", "score_after", "n_candidates", "trigger",
              "trigger_value", "replayable")
    assert ([tuple(getattr(r, f) for f in fields) for r in agent.log.records]
            == [tuple(getattr(r, f) for f in fields) for r in sess.log.records])
    assert [e.sharpe for e in sb_a.transcript] == [e.sharpe for e in sb_b.transcript]


# -- the full-class pass -----------------------------------------------------

def test_max_sharpe_is_chunked_and_agrees_with_the_direct_maximum(tmp_path):
    table, _ = _table(tmp_path)
    best, j = table.max_sharpe(chunk=7)
    direct = max(range(table.N), key=lambda c: table.sharpe(table.members[c]))
    assert j == direct
    assert best == pytest.approx(table.sharpe(table.members[direct]), rel=1e-12)
    # The chunk size changes which member wins nothing, but it is NOT bit-neutral:
    # numpy reduces a (T, 7) block and a (T, 1) block in different orders, so the
    # winning Sharpe can differ in its last bits. The chunk is therefore part of
    # the computation and is pinned, not tuned per call.
    other_chunk = table.max_sharpe(chunk=1)
    assert other_chunk[1] == j
    assert other_chunk[0] == pytest.approx(best, rel=1e-12)
    assert other_chunk[0] != best or True           # equality is not claimed


def test_resampling_rows_gives_the_same_answer_as_resampling_the_stream(tmp_path):
    """The replay's resampling is over rows of the table, and a member's score on
    those rows is that member's stored stream on those rows."""
    table, _ = _table(tmp_path)
    rng = np.random.default_rng(0)
    rows = rng.integers(0, table.T, size=table.T)
    support = table.members[5]
    from estimator.bootstrap import sharpe as _s
    expected = float(_s(table.stream(support)[rows][:, None], axis=0,
                        annualization=table.annualization)[0])
    assert table.sharpe(support, rows) == expected
    assert table.scorer(rows)("x" and support) == expected


def test_the_scorer_refuses_a_statistic_a_table_cannot_hold(tmp_path):
    table, _ = _table(tmp_path)
    with pytest.raises(ValueError, match="no such basis"):
        table.scorer()(table.members[0], "volatility")
