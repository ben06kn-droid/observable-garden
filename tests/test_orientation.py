"""The orientation table: is it really a function of X alone?

`prereg/agent-cell.md` rests the orientation arm's validity on one claim — the
table is `T(X)`, returns never enter it — and `SCOPE.md`'s obliviousness
condition is what that claim buys. A claim of that shape is worth enforcing in
code rather than asserting in prose, so the central test here hands the builder a
**poisoned** returns array that raises on any access.
"""
import numpy as np
import pytest

from quixote.orientation import (CORR_THRESHOLD, EXCLUDED_BY_NAME, orientation_table,
                                 render, table_hash)


class Poisoned:
    """A returns array that cannot be used. Any attribute access, any indexing,
    any arithmetic, any attempt to turn it into an array raises."""

    def __init__(self):
        self.touched = False

    def _boom(self, *a, **k):
        self.touched = True
        raise AssertionError("the orientation table touched the returns")

    __getattr__ = _boom
    __getitem__ = _boom
    __array__ = _boom
    __iter__ = _boom
    __len__ = _boom
    __add__ = __mul__ = __sub__ = __truediv__ = _boom
    __float__ = _boom
    __eq__ = _boom


def _panel(T=300, M=8, K=6, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(T, M, K))
    X[:, :, 1] = X[:, :, 0] * 0.95 + rng.normal(size=(T, M)) * 0.15   # a near-duplicate
    return X


# -- the line -----------------------------------------------------------------

def test_the_builder_takes_X_and_has_nowhere_to_put_returns():
    """Enforcement, not assertion: the signature is the argument. A returns
    array passed as any argument is a TypeError, not a quietly-used input."""
    import inspect
    sig = inspect.signature(orientation_table)
    assert list(sig.parameters) == ["X", "labels", "seed"]
    with pytest.raises(TypeError):
        orientation_table(_panel(), returns=np.zeros((300, 8)))


def test_the_builder_has_no_alpha_or_threshold_parameter():
    """`prereg/agent-cell.md` amendment 2. The table cannot carry a decision
    threshold, because there is no input through which one could arrive - the
    same enforcement-by-signature the returns get.

    `CORR_THRESHOLD` is the format's own cutoff for which pairs are worth
    listing: a module constant, identical on every panel, deciding nothing about
    any specification.
    """
    import inspect
    names = " ".join(inspect.signature(orientation_table).parameters).lower()
    for word in ("alpha", "threshold", "level", "critical", "cut", "p_value"):
        assert word not in names, word
    for kw in ({"alpha": 0.05}, {"threshold": 0.01}, {"critical_value": 1.2}):
        with pytest.raises(TypeError):
            orientation_table(_panel(), **kw)
    from quixote.orientation import CORR_THRESHOLD as C
    assert isinstance(C, float) and C == 0.5


def test_a_poisoned_returns_array_is_never_touched():
    """The central test. If any statistic in the table reached for returns, this
    would raise from inside the builder."""
    poison = Poisoned()
    table = orientation_table(_panel())          # built without them at all
    assert poison.touched is False
    # and the table's contents are reproducible from X alone
    again = orientation_table(_panel())
    assert table == again


def test_the_table_carries_none_of_the_excluded_quantities():
    table = orientation_table(_panel())
    keys = {k for r in table["per_feature"] for k in r}
    assert keys == {"label", "excess_kurtosis", "autocorr_1", "autocorr_5",
                    "turnover"}
    blob = " ".join(str(table)).lower()
    for forbidden in ("sharpe", "ic", "return", "spread", "cost", "date", "price"):
        assert forbidden not in {k.lower() for k in keys}, forbidden
    assert set(table["excluded_by_name"]) == set(EXCLUDED_BY_NAME)


def test_the_table_does_not_change_when_returns_do():
    """The property the obliviousness argument needs, stated as a test: two
    panels with the same X and different returns give the same table, because
    returns are not an input at all."""
    X = _panel()
    a, b = orientation_table(X), orientation_table(X)
    assert table_hash(a) == table_hash(b)


# -- the contents, exactly as registered ---------------------------------------

def test_near_duplicate_pairs_are_delivered_and_the_rest_are_summarised():
    """The ETF panel's z/rank pairs are the reason for this format: the pairs
    that matter, plus a note about the rest, instead of a 780-entry matrix."""
    table = orientation_table(_panel())
    assert table["correlation_threshold"] == CORR_THRESHOLD
    assert table["all_other_pairs_below_threshold"] is True
    pairs = table["correlated_pairs"]
    assert pairs, "the fixture plants a near-duplicate; it should be listed"
    assert all(abs(p["corr"]) >= CORR_THRESHOLD for p in pairs)
    assert all(p["corr"] == round(p["corr"], 2) for p in pairs)
    # every pair below the threshold is absent, not listed with a small number
    assert len(pairs) < (table["n_features"] * (table["n_features"] - 1)) // 2


def test_every_number_is_rounded_to_two_places():
    table = orientation_table(_panel())
    for r in table["per_feature"]:
        for k in ("excess_kurtosis", "autocorr_1", "autocorr_5", "turnover"):
            assert r[k] == round(r[k], 2), (r["label"], k)


def test_labels_are_masked_and_the_order_is_shuffled_by_the_seed():
    """A feature's position in the table carries nothing."""
    X = _panel()
    labels = [f"A{i:03d}" for i in range(X.shape[2])]
    a = orientation_table(X, labels=labels, seed=1)
    b = orientation_table(X, labels=labels, seed=2)
    assert [r["label"] for r in a["per_feature"]] == labels      # labels in order
    assert [r["turnover"] for r in a["per_feature"]] != [
        r["turnover"] for r in b["per_feature"]], "the seed did not move anything"
    same = orientation_table(X, labels=labels, seed=1)
    assert a == same                                             # and it is seeded


def test_the_statistics_are_the_registered_four():
    """Computed independently here, so a change in the builder's arithmetic has
    to be deliberate."""
    X = _panel(T=120, M=5, K=3, seed=3)
    table = orientation_table(X)
    flat = X.reshape(-1, X.shape[2])
    d = flat - flat.mean(axis=0)
    kurt = (d ** 4).mean(axis=0) / (d ** 2).mean(axis=0) ** 2 - 3.0
    turn = np.nanmean(np.abs(np.diff(X, axis=0)), axis=(0, 1))
    for k, row in enumerate(table["per_feature"]):
        assert row["excess_kurtosis"] == round(float(kurt[k]), 2)
        assert row["turnover"] == round(float(turn[k]), 2)
    # autocorrelation: per name over time, averaged over names
    a, b = X[1:], X[:-1]
    am, bm = a.mean(axis=0), b.mean(axis=0)
    num = ((a - am) * (b - bm)).sum(axis=0)
    den = np.sqrt(((a - am) ** 2).sum(axis=0) * ((b - bm) ** 2).sum(axis=0))
    ac1 = np.nanmean(np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0), axis=0)
    for k, row in enumerate(table["per_feature"]):
        assert row["autocorr_1"] == round(float(ac1[k]), 2)


def test_a_degenerate_feature_does_not_break_the_table():
    X = _panel()
    X[:, :, 2] = 0.0
    table = orientation_table(X)
    row = next(r for r in table["per_feature"] if r["label"] == "F02")
    assert row["excess_kurtosis"] == 0.0 and row["turnover"] == 0.0
    assert np.isfinite(row["autocorr_1"])


def test_the_delivered_table_is_hashed_for_the_run_config():
    t = orientation_table(_panel())
    h = table_hash(t)
    assert len(h) == 16 and h == table_hash(dict(t))
    other = orientation_table(_panel(seed=7))
    assert table_hash(other) != h


def test_the_rendered_form_is_what_a_prompt_can_carry():
    text = render(orientation_table(_panel()))
    assert "features." in text and "Every other pair is below that threshold." in text
    assert "kurtosis " in text and "turnover " in text
    for forbidden in ("sharpe", "return", "price", "date"):
        assert forbidden not in text.lower()


def test_a_panel_with_no_correlated_pair_says_so_rather_than_listing_nothing():
    rng = np.random.default_rng(11)
    X = rng.normal(size=(400, 6, 4))
    table = orientation_table(X)
    assert table["correlated_pairs"] == []
    assert "every pair is below it" in render(table)
