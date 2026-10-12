"""The French in-sample read's runner: start-up refusals, and the dry path (`run_read`) on a
SYNTHETIC panel with a small class. Never run on the French panel here."""
import datetime as dt
import hashlib

import numpy as np
import pytest

from experiments import french_insample_read as R


def _days(start, n):
    d, out = dt.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


@pytest.fixture(scope="module")
def synthetic():
    from environments.french_panel import panel_from_returns
    rng = np.random.default_rng(11)
    T, M = 1300 + 255, 12
    r = np.round(0.01 * rng.standard_normal((T, M)), 4)
    return panel_from_returns(_days("2001-01-01", T), [f"s{j}" for j in range(M)], r)


@pytest.fixture(scope="module")
def dry(synthetic, tmp_path_factory):
    from environments.class_table import members_in_order
    from garden.spec_class import SubsetClass
    members = members_in_order(SubsetClass(max_size=1, signed=True), 40)
    return members, R.run_read(synthetic, members, cache_dir=tmp_path_factory.mktemp("c"),
                               B=200, seeds=(1, 2), cache_name="dry")


def test_the_dry_path_runs_both_tests_in_order_with_all_recorded_fields(dry):
    _, rec = dry
    assert rec["repeat_bit_identical"] is True
    assert list(k for k in rec if k in ("i_stream", "ii_class")) == ["i_stream", "ii_class"]
    for k, alpha in (("i_stream", 0.04), ("ii_class", 0.01)):
        t = rec[k]
        assert t["alpha"] == alpha and t["certified"] == (t["p"] < alpha)
        assert 0 < t["p"] <= 1 and t["B"] == 200
        c = t["confidence"]
        assert t["L90"] == c["L"]["0.90"] and len(c["curve"]) > 0 and c["S"] == t["S"]


def test_the_stream_score_is_the_net_streams_sharpe(synthetic, dry):
    from learn import inputs as I
    from learn import ridge_stack
    _, rec = dry
    res = ridge_stack.run(synthetic, "ridge_stack")
    s = I.net_stream(res["positions"], synthetic, res["scored_rows"])
    assert rec["i_stream"]["S"] == pytest.approx(I.sharpe(s, 252.0), rel=1e-9)
    assert rec["i_stream"]["window_rows"] == [int(res["scored_rows"][0]), int(res["scored_rows"][-1])]


def test_the_class_maximum_and_its_member_match_the_registered_streams(synthetic, dry):
    from environments.class_table import streams_for
    members, rec = dry
    X = streams_for(synthetic, members)
    sh = X.mean(axis=1) / X.std(axis=1, ddof=1) * np.sqrt(252)
    t = rec["ii_class"]
    assert t["S"] == pytest.approx(sh.max(), rel=1e-9)
    assert t["best_member"]["index"] == int(np.argmax(sh))
    k, sg = t["best_member"]["support"][0]
    assert t["best_member"]["features"][0] == ("+" if sg > 0 else "-") + synthetic.feature_names[k]
    assert t["N"] == 80 and t["window_rows"] == [0, synthetic.features.shape[0] - 1]


def test_every_refusal_fires(tmp_path):
    w, lib, x = tmp_path / "w.whl", tmp_path / "l.dylib", tmp_path / "x.npy"
    for f in (w, lib, x):
        f.write_bytes(b"stand-in")
    bad = "\n".join(R.refusals("0" * 40, str(w), platform_name="Linux x86_64", lib=lib, x_path=x))
    for needle in ("platform Linux", "macOS pin", "dylib", "pinned French X", "is not the expected"):
        assert needle in bad
    assert "no wheel file" in "\n".join(R.refusals("0" * 40, None, lib=lib, x_path=x))


def test_a_good_setup_passes_the_file_and_platform_checks(tmp_path, monkeypatch):
    w, lib, x = tmp_path / "w.whl", tmp_path / "l.dylib", tmp_path / "x.npy"
    for f, b in ((w, b"w"), (lib, b"l"), (x, b"x")):
        f.write_bytes(b)
    monkeypatch.setattr(R, "WHEEL_SHA256", hashlib.sha256(b"w").hexdigest())
    monkeypatch.setattr(R, "LIB_SHA256", hashlib.sha256(b"l").hexdigest())
    monkeypatch.setattr(R, "X_SHA256", hashlib.sha256(b"x").hexdigest())
    head = R._git("rev-parse", "HEAD").stdout.strip()
    rest = R.refusals(head, str(w), platform_name="Darwin arm64", lib=lib, x_path=x)
    assert not any(k in r for r in rest for k in ("platform", "SHA-256", "blob", "ancestor", "expected")), rest


def test_the_registered_constants():
    assert R.REGISTRATION == "de9da1b914bcd2522ef95ddc4be4231eb47b1af0"
    assert (R.SEED_STREAM, R.SEED_CLASS, R.B) == (693000, 693001, 5000)
    assert (R.ALPHA_STREAM, R.ALPHA_CLASS) == (0.04, 0.01)
    from environments.french_panel import PINNED_X_SHA256
    assert R.X_SHA256 == PINNED_X_SHA256
