"""Transcript format v3: a class supplied as return streams, for specifications that are not sums of base
columns (prereg/E20.md). Membership is by id, then column by column."""
import numpy as np
import pytest

from garden.audit import audit
from garden.spec_class import ExplicitClass, parse
from garden.transcript import Transcript, TranscriptError, load_npz

T, M, N = 300, 12, 5


def make_class(seed=0):
    rng = np.random.default_rng(seed)
    positions = rng.choice([-1.0, 0.0, 1.0], size=(T, M))
    asset = np.repeat(rng.normal(0, 0.01, size=(T, 1)), M, axis=1)
    class_returns = positions * asset
    class_ids = np.array([f"rule_{i}" for i in range(M)])
    return class_returns, class_ids, positions, asset


def make_transcript(seed=0, logged=range(N), submitted="rule_0", **kwargs):
    class_returns, class_ids, positions, asset = make_class(seed)
    cols = list(logged)
    fields = dict(returns=class_returns[:, cols], spec_ids=class_ids[cols], submitted=submitted,
                  menu_kind="adaptive", spec_class="explicit", spec_class_source="sandbox",
                  class_returns=class_returns, class_ids=class_ids)
    fields.update(kwargs)
    return Transcript(**fields)


def test_parse_explicit_forms():
    assert parse("explicit") == ExplicitClass(n_members=None)
    assert parse("explicit").name == "explicit"
    assert parse("explicit:members=12") == ExplicitClass(n_members=12)
    assert parse("explicit:members=12").name == "explicit:members=12"
    assert parse("explicit:members=12").size() == 12
    for bad in ("explicit:members=0", "explicit:members=x", "explicit:bogus=1"):
        with pytest.raises(ValueError):
            parse(bad)


def test_valid_explicit_transcript():
    t = make_transcript()
    assert t.spec_class == "explicit" and t.spec_class_source == "sandbox"
    assert t.class_returns.shape == (T, M) and t.n_specs == N


def test_declared_member_count_is_checked():
    with pytest.raises(TranscriptError, match="declares 99 members"):
        make_transcript(spec_class="explicit:members=99")


def test_class_returns_and_ids_are_required():
    with pytest.raises(TranscriptError, match="needs class_returns and class_ids"):
        make_transcript(class_returns=None)
    with pytest.raises(TranscriptError, match="needs class_returns and class_ids"):
        make_transcript(class_ids=None)


def test_source_is_required_for_a_declared_class():
    with pytest.raises(TranscriptError, match="spec_class_source"):
        make_transcript(spec_class_source=None)


def test_logged_specs_must_be_in_the_class_by_id():
    class_returns, class_ids, _, _ = make_class()
    ids = list(class_ids[:N])          # a Python list: numpy's fixed-width strings would truncate the id
    ids[2] = "rule_not_in_class"
    with pytest.raises(TranscriptError, match="fall outside the declared class"):
        Transcript(returns=class_returns[:, :N], spec_ids=ids, submitted="rule_0", menu_kind="adaptive",
                   spec_class="explicit", spec_class_source="attested",
                   class_returns=class_returns, class_ids=class_ids)


def test_submitted_spec_must_be_in_the_class():
    class_returns, class_ids, _, _ = make_class()
    ids = list(class_ids[:N])          # a Python list: numpy's fixed-width strings would truncate the id
    ids[0] = "rule_not_in_class"
    with pytest.raises(TranscriptError, match="submitted specification"):
        Transcript(returns=class_returns[:, :N], spec_ids=ids, submitted="rule_not_in_class",
                   menu_kind="adaptive", spec_class="explicit", spec_class_source="attested",
                   class_returns=class_returns, class_ids=class_ids)


def test_logged_columns_must_match_their_class_column():
    class_returns, class_ids, _, _ = make_class()
    logged = class_returns[:, :N].copy()
    logged[5, 3] += 0.5
    with pytest.raises(TranscriptError, match="do not match their class column"):
        Transcript(returns=logged, spec_ids=class_ids[:N], submitted="rule_0", menu_kind="adaptive",
                   spec_class="explicit", spec_class_source="sandbox",
                   class_returns=class_returns, class_ids=class_ids)


def test_ids_must_be_unique_and_shaped():
    class_returns, class_ids, _, _ = make_class()
    dupes = class_ids.copy()
    dupes[1] = dupes[0]
    with pytest.raises(TranscriptError, match="class_ids must be unique"):
        make_transcript(class_ids=dupes)
    with pytest.raises(TranscriptError, match="class_ids"):
        make_transcript(class_ids=class_ids[:-1])


def test_positions_and_asset_returns_are_optional_but_consistent():
    class_returns, class_ids, positions, asset = make_class()
    t = make_transcript(class_positions=positions, asset_returns=asset)
    assert t.class_positions.shape == (T, M)

    with pytest.raises(TranscriptError, match="supplied together"):
        make_transcript(class_positions=positions)
    with pytest.raises(TranscriptError, match="does not reproduce class_returns"):
        make_transcript(class_positions=positions, asset_returns=asset + 0.5)
    with pytest.raises(TranscriptError, match="class_positions must be"):
        make_transcript(class_positions=positions[:, :-1], asset_returns=asset[:, :-1])


def test_round_trip_through_npz(tmp_path):
    class_returns, class_ids, positions, asset = make_class()
    t = make_transcript(class_positions=positions, asset_returns=asset)
    path = tmp_path / "explicit.npz"
    t.save(path)
    back = load_npz(path)
    assert back.spec_class == "explicit" and back.spec_class_source == "sandbox"
    np.testing.assert_array_equal(back.class_returns, class_returns)
    np.testing.assert_array_equal(back.class_ids, class_ids)
    np.testing.assert_array_equal(back.class_positions, positions)


def test_audit_uses_the_whole_class_for_an_adaptive_search():
    t = make_transcript(seed=3)
    verdict = audit(t, B=200, seed=0)
    assert verdict.method == "full_class"
    assert verdict.class_size == M
    assert verdict.status in ("PASS", "FAIL", "INADMISSIBLE", "DEGENERATE")
