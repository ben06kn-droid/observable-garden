"""The book-ticker check's quoted-spread weighting and its pre-committed verdict."""
import io
import zipfile

import pytest

from experiments import binance_spread_check as S

D0 = 1_686_700_800_000          # 2023-06-14 00:00 UTC


def _zip(lines, header=True):
    h = ["update_id,best_bid_price,best_bid_qty,best_ask_price,best_ask_qty,transaction_time,event_time"] if header else []
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "\n".join(h + lines))
    return buf.getvalue()


def test_time_weighted_half_spread():
    # 99.9/100.1 (half-spread 0.001) for 6 h, then 99.8/100.2 (0.002) for the last 18 h
    lines = [f"1,99.9,1,100.1,1,{D0},{D0}", f"2,99.8,1,100.2,1,{D0 + 6 * 3600_000},{D0}"]
    for h in (True, False):
        q = S.quoted_half_spread(_zip(lines, h), "2023-06-14")
        assert q["half_spread"] == pytest.approx(0.25 * 0.001 + 0.75 * 0.002) and q["updates"] == 2


def test_the_verdict_rule():
    rows = []
    for sym, q, e in (("BTCUSDT", 0.05, 0.5), ("VETUSDT", 2.0, 6.0), ("ZENUSDT", 4.0, 4.5)):
        rows += [{"contract": sym, "quoted_bps": q, "edge_bps": e} for _ in range(4)]
    v = S.verdict(rows, "edge")
    assert not v["per_contract"]["BTCUSDT"]["fails"]          # both floored to 1 bp
    assert v["per_contract"]["VETUSDT"]["fails"] and not v["per_contract"]["ZENUSDT"]["fails"]
    assert v["contracts_failing"] == 1 and not v["clearly_biased"]
