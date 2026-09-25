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


def test_a_column_is_the_panels_own_net_stream_to_within_one_ulp(tmp_path):
    """The batched kernel and the per-member path are the same arithmetic on the
    same elements, reduced with different pairwise blocking. The module measures
    the gap at 7e-18 absolute and makes the table the definition; this holds it
    to that, so a regression that changed the numbers materially would fail."""
    table, panel = _table(tmp_path)
    K = panel.features.shape[2]
    for support in (((0, 1.0),), ((1, -1.0),), ((0, 1.0), (2, -1.0))):
        w = np.zeros(K)
        for k, s in support:
            w[k] = s
        expected = panel.stream_for_scores(panel.scores_for_weights(w))
        got = table.stream(support)
        assert np.max(np.abs(got - expected)) < 1e-16
        assert np.max(np.abs(got - expected)) <= 1e-14 * np.max(np.abs(expected))


def test_the_kernel_is_invariant_to_the_chunk_it_was_built_in(tmp_path):
    """Chunk invariance for n >= 2 is what lets a table be built in pieces. A
    single-member call takes numpy's one-row path and is deliberately not part of
    the claim, which is why a table is never built one column at a time."""
    from environments.class_table import streams_for
    _, panel = _table(tmp_path)
    members = members_in_order(CLS, panel.features.shape[2])[:12]
    whole = streams_for(panel, members)
    pieces = np.vstack([streams_for(panel, members[i:i + 4]) for i in (0, 4, 8)])
    np.testing.assert_array_equal(whole, pieces)


def test_building_the_same_table_twice_gives_the_same_bytes(tmp_path):
    """Determinism is what the guard's exactness rests on."""
    a, panel = _table(tmp_path)
    first = np.array(a.streams)
    b = build_class_table(panel, CLS, "synthetic", path=tmp_path / "t.npy",
                          rebuild=True)
    np.testing.assert_array_equal(np.array(b.streams), first)


def test_a_support_is_the_same_member_whatever_order_it_was_built_in(tmp_path):
    table, _ = _table(tmp_path)
    assert table.column(((0, 1.0), (2, -1.0))) == table.column(((2, -1.0), (0, 1.0)))


def test_a_non_member_is_refused_rather_than_approximated(tmp_path):
    table, _ = _table(tmp_path)
    with pytest.raises(KeyError, match="not a member"):
        table.column(((0, 1.0), (1, 1.0), (2, 1.0)))     # depth 3 in a depth-2 class


def test_the_table_is_reused_only_for_the_panel_it_was_built_on(tmp_path):
    table, panel = _table(tmp_path)
    first = np.array(table.streams[0])           # a COPY: the memmap is the file,
    again = build_class_table(panel, CLS, "synthetic", path=tmp_path / "t.npy")
    assert again.panel_hash == table.panel_hash     # and a rebuild rewrites the file
    np.testing.assert_array_equal(again.streams[0], first)
    other = _panel(seed=99)
    rebuilt = build_class_table(other, CLS, "synthetic", path=tmp_path / "t.npy")
    assert rebuilt.panel_hash != table.panel_hash
    assert not np.array_equal(np.array(rebuilt.streams[0]), first)


# -- the sandbox scores by lookup -------------------------------------------

def test_evaluate_by_lookup_matches_evaluate_by_computation(tmp_path):
    """Lookup and computation agree to the one-ulp gap the kernel's docstring
    measures, and a lookup is self-consistent: what `evaluate` returns is exactly
    what every replicate will read, which is the property the guard needs."""
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
        assert b.sharpe == pytest.approx(a.sharpe, rel=1e-12)
        assert np.max(np.abs(plain.transcript[-1].return_stream
                             - looked.transcript[-1].return_stream)) < 1e-16
        # self-consistency: the logged stream IS the table's column
        np.testing.assert_array_equal(looked.transcript[-1].return_stream,
                                      table.stream(support))


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


def test_the_table_scores_the_sandboxs_statistic_not_the_guarded_estimator(tmp_path):
    """The third distinct cause the pilot's guard exposed. `estimator.bootstrap.
    sharpe` censors |Sharpe| at SHARPE_CAP = 100 annualised, which is right for a
    simulated panel at Sharpe ~1 and wrong for the ADR panel, whose registered
    5-minute annualisation puts the live search at 107: every good candidate came
    back as exactly 100.0, so the replay priced a CENSORED statistic while the
    search optimised an uncensored one."""
    from estimator.bootstrap import SHARPE_CAP
    from estimator.bootstrap import sharpe as guarded

    table, panel = _table(tmp_path)
    huge = np.full(500, 1.0) + np.random.default_rng(0).normal(scale=0.01, size=500)
    ann = 138.0                                   # sqrt(19152), the ADR panel's
    t = ClassTable(streams=huge[None, :], members=[((0, 1.0),)],
                   index={((0, 1.0),): 0}, panel_hash="x",
                   periods_per_year=ann ** 2)
    raw = t.sharpe(((0, 1.0),))
    assert raw > SHARPE_CAP                       # the sandbox would report this
    assert guarded(huge[:, None], axis=0, annualization=ann)[0] == SHARPE_CAP
    assert raw != SHARPE_CAP                      # the table does not censor it


def test_a_zero_variance_stream_scores_zero_as_the_sandbox_does(tmp_path):
    t = ClassTable(streams=np.zeros((1, 50)), members=[((0, 1.0),)],
                   index={((0, 1.0),): 0}, panel_hash="x", periods_per_year=252)
    assert t.sharpe(((0, 1.0),)) == 0.0


def test_the_guard_compares_the_best_pair_on_both_sides(tmp_path):
    """A search whose LAST move did not improve still submits its best. The guard
    used to compare the log's last support against the replay's best, so such a
    run failed for that reason alone - which is how the ETF pilot's first run
    came back UNDECIDABLE with a gap of 0.0092, the size of its final losing
    move."""
    from quixote.replay import identity_check
    table, panel = _table(tmp_path)
    sb = RealSandbox(panel, spec_class=CLS, class_table=table)
    sess = Session.on_sandbox(sb, CLS, name_prefix="t")
    sess.propose(Move("init"))
    sess.accept()
    sess.propose(Move("extend_best"))
    sess.accept()
    best_support, best_score = sess.submission()

    # a deliberately worsening move, accepted: the last support is not the best.
    # A flip always has a candidate, where an extension at a full support does
    # not (this class is depth 2).
    held = sess.support[0][0]
    sess.propose(Move("flip", feature=held))
    sess.accept()
    assert sess.support != best_support
    assert sess.score < best_score
    assert sess.submission() == (best_support, best_score)

    base = sb.base_feature_columns()
    ann = float(np.sqrt(panel.periods_per_year))
    guard = identity_check(sess.log, CLS, base, ann, score_fn=table.scorer(None))
    assert guard.realized_support == tuple(best_support)
    assert guard.realized_score == pytest.approx(best_score, rel=1e-12)
