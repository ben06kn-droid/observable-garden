"""The Binance version-2 design script on a SYNTHETIC Binance-shaped panel (no real data):
alignment, settings arithmetic, and the whole quantities path end to end; no mean or
Sharpe is stored."""
import datetime as dt

import numpy as np
import pytest

from environments import binance_panel as bp
from experiments import binance_design_v2 as D


def test_kline_columns_align_and_blank_after_death():
    times = np.arange(0, 10 * 1000, 1000, dtype=np.int64)
    kl = [[t, 0, 0, 0, 1.0, 100.0 + i, 0, 7 + i] for i, t in enumerate(times.tolist()) if i != 3]
    c = D.kline_columns(times, kl, dead=8)
    assert np.isnan(c["volume"][3]) and c["volume"][2] == 102.0 and c["count"][4] == 11
    assert np.isnan(c["volume"][8:]).all() and np.isnan(c["count"][9])


def test_settings_in_rows_and_the_time_matched_alternative():
    s = D.settings(1388, 365.0)
    cf, tm = s["carried_forward"], s["time_matched_not_run"]
    assert cf["first_scored_row"] == 763 and cf["scored_rows"] == 625
    assert cf["years"]["roll756"] == pytest.approx(756 / 365)
    assert tm["first_scored_row"] == round(756 * 365 / 252) + 7 and tm["scored_rows"] == 1388 - tm["first_scored_row"]
    s4 = D.settings(6000, 2190.0)                    # x8.69: 756 rows become 6570
    assert s4["time_matched_not_run"]["scored_rows"] == 0


@pytest.fixture(scope="module")
def raw():
    rng = np.random.default_rng(5)
    M, T = 8, bp.WARM + 900 + bp.LAG
    spec = bp.daily_spec("2020-10")
    times = np.arange(T, dtype=np.int64) * 86_400_000
    rp = 0.02 * rng.standard_normal((T, M))
    rp[0] = 0.0
    alive = np.ones((T, M), bool)
    alive[700:, 7] = False
    rp[700:, 7] = 0.0
    fund = 1e-4 * rng.standard_normal((T, M))
    r = rp - fund
    panel = bp.panel_from_arrays(times, [f"S{j}" for j in range(M)], r, alive, rp=rp, spec=spec)
    live_n = alive.sum(axis=1)
    market = (rp * alive).sum(axis=1) / live_n
    close = np.where(alive, np.exp(np.cumsum(rp, axis=0)), np.nan)
    vol = np.where(alive, np.exp(rng.standard_normal((T, M))) * 1e6, np.nan)
    cnt = np.where(alive, rng.integers(1000, 5000, (T, M)).astype(float), np.nan)
    info = {f"S{j}": {"dead_bar": 700 if j == 7 else None, "alive_earned": alive[bp.WARM + bp.LAG:, j].tolist(),
                      "funding_rows": 3 * T} for j in range(M)}
    return {"panel": panel, "info": info, "universe": {"formation": "synthetic", "universe": M}, "spec": spec,
            "WARM": bp.WARM, "LAG": bp.LAG, "rp": rp, "market": market, "alive": alive, "close": close,
            "volume": vol, "count": cnt, "funding": fund}


def test_the_quantities_path_end_to_end_stores_no_mean_or_sharpe(raw):
    q = D.quantities("1d-2020-09", raw, B_null=200)
    assert q["blocks"]["available"] == ["P", "X", "V", "F"]
    assert q["blocks"]["V"] == ["logvol_ratio", "count_ratio", "amihud21"]
    se = q["stream"]
    assert se["rows"] == 900 - 763 and se["gross_80"] == pytest.approx(se["net_80"] + se["cost_drag_sharpe"])
    assert set(q["seconds"]) == {"blocks", "fit_roll756", "fit_expand"}
    def keys(x):
        if isinstance(x, dict):
            for k, v in x.items():
                yield k
                yield from keys(v)
        elif isinstance(x, list):
            for v in x:
                yield from keys(v)
    assert not {"mean", "mean_return", "sharpe", "p", "score", "p_value"} & set(keys(q))
    lk = D.job_leak("1d-2020-09", raw)
    assert lk["leak_view"][0]["identical_up_to_t"] and lk["leak_view"][0]["changed_after_t"]
    assert lk["base_book_sha256"] == q["book_sha256"]
    bl = D.job_block_leak("1d-2020-09", raw)["block_leak"]
    assert all(x[0]["identical_up_to_t"] and x[0]["changed_after_t"] for x in bl.values())


def test_the_report_renders_from_synthetic_results(raw):
    import json
    q = D.quantities("1d-2020-09", raw, B_null=100)
    lk = {"leak_view": [{"t": 1, "identical_up_to_t": True, "changed_after_t": True}], "base_book_sha256": q["book_sha256"]}
    bl = {"block_leak": {"X(r)": [{"identical_up_to_t": True, "changed_after_t": True}]}}
    res = {}
    for v in D.VARIANTS:
        res[("main", v)], res[("leak", v)], res[("block_leak", v)] = q, lk, bl
    L = D.report(res, json.loads(D.V1_TABLE.read_text()))
    assert any(x.startswith("COMPARISON") for x in L) and sum(x.split()[:1] == ["v2"] for x in L) == 4
    assert "bit-for-bit repeat (positions, separate process): True" in "\n".join(L)


def test_configure_sets_and_resets_the_calendar_variant():
    from learn2 import learner as Ln
    try:
        cfg = D.configure("4h-cal")
        assert Ln.FIRST == 2190 and Ln.MEMORIES["roll2190"] == 2190 and D.MEMORIES == ("roll2190", "expand")
        s = D.settings(7116, 2190.0, 1, cfg)["carried_forward"]
        assert s["first_scored_row"] == 2197 and s["scored_rows"] == 7116 - 2197 and s["refits"] == len(range(2197, 7116, 252))
        D.configure("4h")
        assert Ln.FIRST == 756 and D.MEMORIES == ("roll756", "expand")
    finally:
        D.configure("4h")
