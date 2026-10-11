"""The ETF recent panel's fetch and host cut, on synthetic Yahoo-shaped responses only (no network)."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest

from data import etf_recent_cut as C
from data import fetch_etf_recent as F
from data.fetch_etf import TICKERS

FETCH_UTC = "2026-10-12T15:00:00+00:00"
ALL = C.sessions(dt.date(2005, 1, 3), dt.date(2026, 10, 12))


def chart(days, adj=None, vol=None) -> bytes:
    ts = [int(dt.datetime(d.year, d.month, d.day, 14, 30, tzinfo=dt.timezone.utc).timestamp()) for d in days]
    adj = adj if adj is not None else [100.0 + 0.01 * i for i in range(len(days))]
    vol = vol if vol is not None else [1_000_000] * len(days)
    return json.dumps({"chart": {"result": [{"timestamp": ts, "indicators": {
        "quote": [{"volume": vol}], "adjclose": [{"adjclose": adj}]}}], "error": None}}).encode()


def write_raw(tmp: Path, special: dict | None = None) -> Path:
    raw = tmp / "raw"
    raw.mkdir()
    special = special or {}
    rec = {"registration": F.REGISTRATION, "fetch_start_utc": FETCH_UTC, "tickers": {}}
    for tk in TICKERS:
        body = special.get(tk, chart(ALL))
        e = {"url": "u", "http": "200"}
        if body is None:
            e["http"] = "404"
        else:
            (raw / f"{tk}.json").write_bytes(body)
            e["sha256"] = hashlib.sha256(body).hexdigest()
        rec["tickers"][tk] = e
    (raw / "fetch.json").write_text(json.dumps(rec))
    return raw


def test_last_session_before_fetch_day():
    assert C.last_session_before(dt.date(2026, 10, 12)) == dt.date(2026, 10, 9)
    assert C.last_session_before(dt.date(2028, 1, 3)) == dt.date(2027, 12, 31)


def test_clean_cut_hashes_and_counts(tmp_path):
    raw = write_raw(tmp_path)
    out = tmp_path / "insample"
    rec = C.cut(raw, out)
    assert rec["n_included"] == 40 and rec["refused"] is None
    assert rec["last_fetched_session"] == "2026-10-09"
    n_in = len(C.sessions(dt.date(2005, 1, 3), dt.date(2024, 12, 31)))
    assert n_in == 5033
    stored = json.loads((tmp_path / "insample.cut.json").read_text())
    for tk in TICKERS:
        p = out / f"{tk}.csv"
        assert hashlib.sha256(p.read_bytes()).hexdigest() == stored["csv_sha256"][tk]
        lines = p.read_text().splitlines()
        assert lines[0] == "date,adjclose,volume" and len(lines) - 1 == n_in == stored["rows"][tk]
        assert lines[-1].startswith("2024-12-31,")
        assert stored["per_ticker"][tk]["holdout_rows"] == len([d for d in ALL if dt.date(2025, 1, 1) <= d <= dt.date(2026, 10, 9)])
        assert stored["per_ticker"][tk]["bars_after_last_session"] == 1          # 2026-10-12 itself
    comb = hashlib.sha256("\n".join(f"{t} {stored['csv_sha256'][t]}" for t in sorted(TICKERS)).encode()).hexdigest()
    assert stored["combined_sha256"] == comb
    assert stored["rule"]["3"] == "item 3: not verified"
    with pytest.raises(C.CutRefused):
        C.cut(raw, out)                                                    # made once


def test_holdout_values_never_parsed(tmp_path):
    adj = [100.0 if d < dt.date(2025, 1, 1) else "NOT_A_NUMBER" for d in ALL]
    vol = [1_000_000 if d < dt.date(2025, 1, 1) else {"bad": 1} for d in ALL]
    raw = write_raw(tmp_path, {"SPY": chart(ALL, adj, vol)})
    rec = C.cut(raw, tmp_path / "insample")
    assert "SPY" in rec["included"]
    assert "NOT_A_NUMBER" not in (tmp_path / "insample" / "SPY.csv").read_text()


def test_gap_in_formation_window_fails_rule_1(tmp_path):
    days = [d for d in ALL if d != dt.date(2010, 6, 15)]
    adj = [100.0] * len(ALL)
    adj[ALL.index(dt.date(2008, 3, 3))] = None                              # a null close is missing too
    raw = write_raw(tmp_path, {"EWH": chart(days), "EWZ": chart(ALL, adj)})
    rec = C.cut(raw, tmp_path / "insample")
    for tk in ("EWH", "EWZ"):
        assert not rec["per_ticker"][tk]["included"] and rec["per_ticker"][tk]["reason"].startswith("1:")
    assert rec["n_included"] == 38 and not (tmp_path / "insample" / "EWH.csv").exists()


def test_low_median_fails_rule_2(tmp_path):
    vol = [400_000 if d <= dt.date(2014, 12, 31) else 5_000_000 for d in ALL]
    raw = write_raw(tmp_path, {"TIP": chart(ALL, vol=vol)})
    rec = C.cut(raw, tmp_path / "insample")
    t = rec["per_ticker"]["TIP"]
    assert not t["included"] and "2:" in t["reason"] and t["median_volume_2005_2014"] == 400_000


def test_no_data_ticker_refuses(tmp_path):
    raw = write_raw(tmp_path, {"GLD": None, "IYR": json.dumps({"chart": {"result": None}}).encode()})
    with pytest.raises(C.CutRefused, match="no data"):
        C.cut(raw, tmp_path / "insample")
    assert not (tmp_path / "insample").exists()
    rec = json.loads((tmp_path / "insample.cut.json").read_text())
    assert rec["per_ticker"]["GLD"]["status"] == "no data" and rec["refused"]


def test_fewer_than_30_refuses(tmp_path):
    vol = [100] * len(ALL)
    raw = write_raw(tmp_path, {tk: chart(ALL, vol=vol) for tk in TICKERS[:11]})
    with pytest.raises(C.CutRefused, match="fewer than 30"):
        C.cut(raw, tmp_path / "insample")
    assert not (tmp_path / "insample").exists()


def test_gap_after_2014_refuses(tmp_path):
    days = [d for d in ALL if d < dt.date(2020, 3, 2) or d > dt.date(2020, 3, 20)]
    raw = write_raw(tmp_path, {"XLE": chart(days)})
    with pytest.raises(C.CutRefused, match="after 2014"):
        C.cut(raw, tmp_path / "insample")
    rec = json.loads((tmp_path / "insample.cut.json").read_text())
    assert rec["per_ticker"]["XLE"]["first_missing_2015_2024"] == "2020-03-02"


def test_raw_hash_mismatch_refuses(tmp_path):
    raw = write_raw(tmp_path)
    (raw / "SPY.json").write_bytes(chart(ALL[:-1]))
    with pytest.raises(C.CutRefused, match="SHA-256"):
        C.cut(raw, tmp_path / "insample")


def test_refusals_until_live(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "registration_live", lambda *a: False)
    monkeypatch.setattr(C, "registration_live", lambda *a: False)
    with pytest.raises(SystemExit, match="REFUSED"):
        F.main(["--out", str(tmp_path / "raw")])
    with pytest.raises(SystemExit, match="REFUSED"):
        C.main(["--raw", str(tmp_path / "raw"), "--out", str(tmp_path / "insample")])
    assert not (tmp_path / "raw").exists()


def test_fetch_records_hashes_and_one_retry(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(F, "registration_live", lambda *a: True)
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    calls = {}

    def fake_curl(url, out):
        tk = url.split("/chart/")[1].split("?")[0]
        calls[tk] = calls.get(tk, 0) + 1
        if tk == "VNQ":
            return "429"
        if tk == "IWM" and calls[tk] == 1:
            return "500"
        out.write_bytes(chart(ALL[:10]))
        return "200"

    monkeypatch.setattr(F, "curl", fake_curl)
    F.main(["--out", str(tmp_path / "raw")])
    rec = json.loads((tmp_path / "raw" / "fetch.json").read_text())
    assert rec["registration"] == F.REGISTRATION
    assert len(rec["tickers"]["IWM"]["attempts"]) == 2 and rec["tickers"]["IWM"]["http"] == "200"
    assert calls["VNQ"] == 2 and "error" in rec["tickers"]["VNQ"]
    spy = rec["tickers"]["SPY"]
    assert spy["sha256"] == hashlib.sha256((tmp_path / "raw" / "SPY.json").read_bytes()).hexdigest()
    assert "period1=1104537600" in spy["url"] and "includeAdjustedClose=true" in spy["url"]
    printed = capsys.readouterr().out
    assert "100.0" not in printed and "1000000" not in printed
    with pytest.raises(SystemExit, match="REFUSED"):
        F.main(["--out", str(tmp_path / "raw")])                         # one fetch
