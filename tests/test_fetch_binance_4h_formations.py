"""The 4h formation fetch's checksum reuse and gap count, with the network faked."""
import hashlib

import pytest

from data import fetch_binance as fb
from data import fetch_binance_4h_formations as F


def test_missing_bars_counts_holes_between_first_and_last():
    rows = [[t * F.BAR_MS] for t in (0, 1, 2, 5, 6)]
    assert F.missing_bars(rows) == 2 and F.missing_bars([]) == 0


def test_checked_blob_reuses_only_a_matching_quarantined_copy(tmp_path, monkeypatch):
    good, other = b"zip-bytes", b"stale"
    want = hashlib.sha256(good).hexdigest()
    calls = []

    def fake_get(url):
        calls.append(url)
        return f"{want}  x.zip".encode() if url.endswith(".CHECKSUM") else good
    monkeypatch.setattr(fb, "_get", fake_get)
    monkeypatch.setattr(fb, "QUARANTINE", tmp_path)
    key = "data/futures/um/monthly/klines/AUSDT/4h/AUSDT-4h-2021-01.zip"
    (tmp_path / key).parent.mkdir(parents=True)
    (tmp_path / key).write_bytes(good)
    assert F.checked_blob(key) == (good, True) and len(calls) == 1
    (tmp_path / key).write_bytes(other)
    assert F.checked_blob(key) == (good, False) and (tmp_path / key).read_bytes() == good
    monkeypatch.setattr(fb, "_get", lambda url: f"{want}  x".encode() if url.endswith(".CHECKSUM") else b"bad")
    (tmp_path / key).write_bytes(other)
    with pytest.raises(fb.FetchRefused):
        F.checked_blob(key)
