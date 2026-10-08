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
