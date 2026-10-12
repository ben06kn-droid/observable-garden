"""The taker-column rebuild on synthetic zips in a temporary quarantine (no real file)."""
import csv
import hashlib
import io
import zipfile

import pytest

from data import fetch_binance as fb
from data import rebuild_binance_taker as R

T0 = 1_640_995_200_000          # 2022-01-01


def _zip(rows, header=True):
    lines = ([",".join(fb.KLINE_COLS)] if header else []) + [",".join(map(str, r)) for r in rows]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("x.csv", "\n".join(lines))
    return buf.getvalue()


def _row(i, t0=T0):
    t = t0 + i * 14_400_000
    return [t, 1.0 + i, 2.0, 0.5, 1.5, 100.0 + i, t + 14_399_999, 150.0 + i, 7 + i, 40.0 + i, 60.0 + i, 0]


def test_the_parser_keeps_the_taker_columns_with_and_without_a_header():
    rows = [_row(i) for i in range(3)]
    for h in (True, False):
        got = R.parse_klines_taker(_zip(rows, header=h))
        assert got[1] == [rows[1][0], 2.0, 2.0, 0.5, 1.5, 101.0, 151.0, 8, 41.0, 61.0]
        assert [g[:8] for g in got] == fb.parse_klines(_zip(rows, header=h))


def test_the_parser_refuses_short_rows_odd_headers_and_microseconds():
    with pytest.raises(R.RebuildRefused, match="fields"):
        R.parse_klines_taker(_zip([_row(0)[:9]], header=False))
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("x.csv", "time,o,h\n" + ",".join(map(str, _row(0))))
    with pytest.raises(R.RebuildRefused, match="header"):
        R.parse_klines_taker(bad.getvalue())
    r = _row(0)
    r[0] = r[0] * 1000
    with pytest.raises(R.RebuildRefused, match="milliseconds"):
        R.parse_klines_taker(_zip([r]))


def _setup(tmp_path, rows, derived_rows=None):
    q = tmp_path / "q"
    key = "data/futures/um/monthly/klines/AUSDT/4h/AUSDT-4h-2022-01.zip"
    blob = _zip(rows)
    (q / key).parent.mkdir(parents=True)
    (q / key).write_bytes(blob)
    d = tmp_path / "AUSDT_4h.csv"
    with open(d, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
        w.writerows(derived_rows if derived_rows is not None else
                    [[r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[8]] for r in rows])
    return q, key, hashlib.sha256(blob).hexdigest(), d


def test_rebuild_writes_the_taker_file_and_checks_the_hash_and_the_rows(tmp_path):
    rows = [_row(i) for i in range(4)]
    q, key, sha, d = _setup(tmp_path, rows)
    out = tmp_path / "AUSDT_4h_taker.csv"
    rec = R.rebuild("AUSDT", [(key, sha)], d, out, root=q)
    assert rec["rows"] == 4 and out.read_text().splitlines()[2] == f"{rows[1][0]},41.0,61.0"
    with pytest.raises(R.RebuildRefused, match="recorded"):
        R.rebuild("AUSDT", [(key, "0" * 64)], d, out, root=q)
    with pytest.raises(R.RebuildRefused, match="not in the quarantine"):
        R.rebuild("AUSDT", [(key.replace("01.zip", "02.zip"), sha)], d, out, root=q)


def test_rebuild_refuses_a_mismatch_with_the_derived_csv_and_a_holdout_row(tmp_path):
    rows = [_row(i) for i in range(4)]
    derived = [[r[0], r[1], r[2], r[3], r[4] + 1e-9, r[5], r[7], r[8]] for r in rows]
    q, key, sha, d = _setup(tmp_path, rows, derived)
    with pytest.raises(R.RebuildRefused, match="differ"):
        R.rebuild("AUSDT", [(key, sha)], d, tmp_path / "t.csv", root=q)
    late = [_row(i, t0=R.CUT) for i in range(2)]
    q2, key2, sha2, d2 = _setup(tmp_path / "b", late)
    with pytest.raises(R.RebuildRefused, match="2025-04-01"):
        R.rebuild("AUSDT", [(key2, sha2)], d2, tmp_path / "t2.csv", root=q2)
