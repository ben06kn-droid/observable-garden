"""The French 49-industry fetch split, loader and panel builder, on synthetic text only."""
import datetime as dt

import numpy as np
import pytest

from data import fetch_french as ff
from data import french_loader as fl
from data.etf_loader import HoldoutRefused
from environments import french_panel as fp


def _days(start, n):
    d, out = dt.date.fromisoformat(start), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def _text(dates, M=3, seed=0, poison_after=True):
    rng = np.random.default_rng(seed)
    head = ["This file was created using the 202608 CRSP database.", "",
            "  Average Value Weighted Returns -- Daily",
            "," + ",".join(f"Ind{j}" for j in range(M))]
    body = []
    for d in dates:
        ds = d.strftime("%Y%m%d")
        if int(ds) >= ff.CUT and poison_after:
            body.append(ds + "," + ",".join(["not-a-number"] * M))   # never parsed
        else:
            body.append(ds + "," + ",".join(f"{x:.2f}" for x in rng.normal(0, 1, M)))
    tail = ["", "  Average Equal Weighted Returns -- Daily", "," + ",".join(f"Ind{j}" for j in range(M)),
            dates[0].strftime("%Y%m%d") + "," + ",".join(["1.00"] * M)]
    return "\n".join(head + body + tail)


def test_the_split_keeps_253_warm_up_rows_and_only_counts_holdout_lines():
    dates = _days("2008-06-02", 3000)
    s = ff.split_text(_text(dates))
    ds = [d.strftime("%Y%m%d") for d in dates]
    i = ds.index("20100104")
    assert s["first_scored"] == "20100104"
    assert s["first_feature_row"] == ds[i - 2]
    assert s["warm_start"] == ds[i - 2 - 253]
    assert s["rows"][0][0] == s["warm_start"] and s["rows"][-1][0] == s["last_insample"]
    assert int(s["last_insample"]) < ff.CUT
    assert s["n_holdout_lines"] == sum(int(d) >= ff.CUT for d in ds)   # poisoned lines: counted, not parsed
    assert s["n_unused_before"] == i - 2 - 253
    assert len(s["rows"]) == len([d for d in ds if int(d) < ff.CUT]) - s["n_unused_before"]


def test_missing_value_codes_are_counted_per_industry():
    dates = _days("2008-06-02", 700)
    lines = _text(dates).splitlines()
    k = next(i for i, ln in enumerate(lines) if ln.startswith("201006"))   # inside the rows kept
    f = lines[k].split(",")
    f[2] = "-99.99"
    lines[k] = ",".join(f)
    s = ff.split_text("\n".join(lines))
    assert s["missing"] == {"Ind1": 1}


def test_the_loader_refuses_holdout_dates_and_quarantined_paths(tmp_path):
    p = tmp_path / "f.csv"
    p.write_text("date,A,B\n2019-12-31,0.1,0.2\n2020-01-02,0.3,0.4\n")
    with pytest.raises(HoldoutRefused):
        fl.load_insample(p)
    with pytest.raises(HoldoutRefused):
        fl.load_insample(fl.Path.home() / "Desktop" / "og-quarantine" / "x.csv")
    p.write_text("date,A,B\n2019-12-30,1.0,-2.0\n2019-12-31,0.5,0.25\n")
    d, cols, R = fl.load_insample(p)
    assert cols == ["A", "B"] and np.allclose(R, [[0.01, -0.02], [0.005, 0.0025]])


def test_the_panel_uses_the_equal_weighted_market_and_the_etf_timing():
    dates = _days("2008-12-29", 600)
    rng = np.random.default_rng(1)
    r = 0.01 * rng.standard_normal((600, 6))
    p = fp.panel_from_returns(dates, [f"i{j}" for j in range(6)], r)
    assert p.features.shape == (600 - 253 - 2, 6, 40)
    assert np.allclose(p.returns[0], r[253 + 2])                      # earns t + 2
    assert p.meta["dates"][0] == dates[253] and p.meta["earned_dates"][0] == dates[255]
    from environments.real_panel import _etf_base_signals
    sig = _etf_base_signals(np.cumsum(np.log1p(r), axis=0), r, r.mean(axis=1))
    j = p.feature_names.index("beta252_z")
    from environments.real_panel import _zscore
    assert np.allclose(p.features[:, :, j], _zscore(sig["beta252"])[253:598])
    assert np.allclose(p.cost_rate, 5e-4) and np.allclose(p.borrow_rate, 50e-4 / 252)
    assert not np.isnan(p.features).any()


def test_average_ranks_give_exact_ties_their_mean_rank_and_match_rank_without_ties():
    from environments.real_panel import _rank
    x = np.array([[0.01, 0.02, 0.02, -0.01, np.nan], [3.0, 1.0, 2.0, 5.0, 4.0]])
    out = fp.rank_average(x)
    # row 0: valid n = 4; ranks -0.01:0, 0.01:1, 0.02 tie at (2+3)/2 = 2.5
    assert np.allclose(out[0], [2 * 1 / 3 - 1, 2 * 2.5 / 3 - 1, 2 * 2.5 / 3 - 1, -1.0, 0.0])
    assert np.array_equal(out[1], _rank(x[1:2])[0])
    assert out[0, 1] == out[0, 2]                         # independent of order
    y = x.copy()
    y[0, [1, 2]] = y[0, [2, 1]]
    assert np.array_equal(fp.rank_average(y), out)


def test_the_panel_ranks_use_average_ranks_and_the_etf_rank_is_unchanged():
    dates = _days("2008-12-29", 600)
    rng = np.random.default_rng(2)
    r = np.round(0.01 * rng.standard_normal((600, 6)), 4)  # quantised, as the library's data
    p = fp.panel_from_returns(dates, [f"i{j}" for j in range(6)], r)
    from environments.real_panel import _etf_base_signals
    sig = _etf_base_signals(np.cumsum(np.log1p(r), axis=0), r, r.mean(axis=1))
    j = p.feature_names.index("ret1_rank")
    assert np.array_equal(p.features[:, :, j], fp.rank_average(sig["ret1"])[253:598])


def test_the_pin_is_written_once_and_refused_on_mismatch(tmp_path, monkeypatch):
    dates = _days("2008-12-29", 600)
    r = 0.01 * np.random.default_rng(3).standard_normal((600, 4))
    monkeypatch.setattr(fp, "build_french_panel",
                        lambda pinned=False: fp.panel_from_returns(dates, list("abcd"), r))
    f = tmp_path / "x.npy"
    sha = fp.pin_features(f)
    with pytest.raises(SystemExit, match="written once"):
        fp.pin_features(f)
    X = fp.pinned_features(f, sha, (345, 4, 40))
    assert X.shape == (345, 4, 40)
    with pytest.raises(SystemExit, match="refused"):
        fp.pinned_features(f, "0" * 64, (345, 4, 40))
    with pytest.raises(SystemExit, match="no pinned"):
        fp.pinned_features(f, "", (345, 4, 40))
