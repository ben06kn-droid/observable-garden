"""Restore the taker-buy columns to the derived Binance kline files (draft
`prereg/binance-panel.md`, correction of 2026-10-09). No download.

`fetch_binance.parse_klines` dropped the archive's `taker_buy_volume` and
`taker_buy_quote_volume` columns when the in-sample CSVs were written. Every raw zip was
kept in the quarantine. This script re-reads those zips; each one's SHA-256 must equal the
hash recorded in its manifest when it was fetched. It writes, beside each derived kline
CSV, a `{SYM}_{bar}_taker.csv` with (open_time, taker_buy_volume, taker_buy_quote_volume).

The existing derived CSVs are not rewritten. As a check, the rebuilt rows' first eight
fields must equal the existing CSV's rows exactly, or the symbol is refused.

Sources: the 4h in-sample universe (`data/binance_manifest.json`), the 4h fills
(`data/binance_fill_manifest.json`, runs decided "filled", their missing days only), and
the three daily formations (`data/binance_daily_manifest.json`). Any row on or after
2025-04-01 is refused.

    python -m data.rebuild_binance_taker
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import zipfile
from pathlib import Path

from data import fetch_binance as fb

CUT = int(dt.datetime(2025, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
TAKER_MANIFEST = fb.REPO / "data" / "binance_taker_manifest.json"


class RebuildRefused(RuntimeError):
    pass


def parse_klines_taker(blob: bytes) -> list[list]:
    """Rows of (open_time ms, open, high, low, close, volume, quote_volume, count,
    taker_buy_volume, taker_buy_quote_volume): `fetch_binance.parse_klines`'s eight fields
    plus the two taker-buy columns, by position (the archive's 12-column layout). A header
    row is skipped; microsecond times and short rows are refused."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    rows = []
    for ln in z.read(z.namelist()[0]).decode().strip().splitlines():
        f = ln.split(",")
        if not f[0].strip().isdigit():
            if [x.strip() for x in f[:12]] != fb.KLINE_COLS:
                raise RebuildRefused(f"unexpected header {f}")
            continue
        if len(f) < 11:
            raise RebuildRefused(f"a kline row has {len(f)} fields, not 12")
        t = int(f[0])
        if not 1e12 <= t < 1e13:
            raise RebuildRefused(f"open time {t} is not in milliseconds")
        rows.append([t, float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5]),
                     float(f[7]), int(float(f[8])), float(f[9]), float(f[10])])
    return rows


def quarantined(key: str, sha256: str, root: Path | None = None) -> bytes:
    """The quarantined zip's bytes, refused unless its SHA-256 is the recorded one."""
    p = (root or fb.QUARANTINE) / key
    if not p.exists():
        raise RebuildRefused(f"{key}: not in the quarantine")
    blob = p.read_bytes()
    got = hashlib.sha256(blob).hexdigest()
    if got != sha256:
        raise RebuildRefused(f"{key}: SHA-256 {got} is not the recorded {sha256}")
    return blob


def read_derived(path: Path) -> list[list]:
    with open(path, newline="") as fh:
        rd = csv.reader(fh)
        next(rd)
        return [[int(r[0])] + [float(x) for x in r[1:7]] + [int(r[7])] for r in rd]


def write_taker(path: Path, rows: list[list]) -> str:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "taker_buy_volume", "taker_buy_quote_volume"])
        w.writerows(sorted([r[0], r[8], r[9]] for r in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rebuild(sym: str, keys_sha: list[tuple[str, str]], derived: Path, out: Path,
            root: Path | None = None) -> dict:
    """Taker rows for one derived CSV from its recorded zips; refused unless the rebuilt
    eight fields equal the derived rows exactly."""
    rows = []
    for key, sha in keys_sha:
        rows += parse_klines_taker(quarantined(key, sha, root))
    if any(r[0] >= CUT for r in rows):
        raise RebuildRefused(f"{sym}: a row on or after 2025-04-01")
    have = read_derived(derived)
    if sorted(r[:8] for r in rows) != sorted(have):
        raise RebuildRefused(f"{sym}: the rebuilt rows differ from {derived.name}")
    return {"symbol": sym, "zips": len(keys_sha), "rows": len(rows), "taker_csv": out.name,
            "taker_sha256": write_taker(out, rows)}


def rebuild_fill(sym: str, runs: list[dict], derived: Path, out: Path, root: Path | None = None) -> dict:
    keep = {r[0] for r in read_derived(derived)}
    rows = []
    n = 0
    for run in runs:
        if run.get("decision") != "filled":
            continue
        for day in run["days"]:
            key = f"data/futures/um/daily/klines/{sym}/4h/{sym}-4h-{day}.zip"
            rows += [r for r in parse_klines_taker(quarantined(key, run["files"][day], root)) if r[0] in keep]
            n += 1
    if sorted(r[:8] for r in rows) != sorted(read_derived(derived)):
        raise RebuildRefused(f"{sym}: the rebuilt fill rows differ from {derived.name}")
    return {"symbol": sym, "zips": n, "rows": len(rows), "taker_csv": out.name,
            "taker_sha256": write_taker(out, rows)}


def main(argv=None) -> int:
    if TAKER_MANIFEST.exists():
        raise SystemExit(f"{TAKER_MANIFEST} exists: rebuilt once")
    rec = {"rebuilt_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "4h": [], "4h_fill": [], "daily": {}}
    man = json.loads(fb.MANIFEST.read_text())
    for s in man["symbols"]:
        sym = s["symbol"]
        ks = [(f"data/futures/um/monthly/klines/{sym}/4h/{sym}-4h-{m}.zip", v["sha256"])
              for m, v in sorted(s["klines"].items()) if v]
        rec["4h"].append(rebuild(sym, ks, fb.INSAMPLE_DIR / f"{sym}_4h.csv", fb.INSAMPLE_DIR / f"{sym}_4h_taker.csv"))
    fill = json.loads((fb.REPO / "data" / "binance_fill_manifest.json").read_text())
    for s in fill["symbols"]:
        d = fb.INSAMPLE_DIR / f"{s['symbol']}_4h_fill.csv"
        if d.exists():
            rec["4h_fill"].append(rebuild_fill(s["symbol"], s["runs"], d,
                                               fb.INSAMPLE_DIR / f"{s['symbol']}_4h_fill_taker.csv"))
    daily = json.loads((fb.REPO / "data" / "binance_daily_manifest.json").read_text())["formations"]
    for f, fm in daily.items():
        d = fb.REPO / "data" / "raw" / f"binance_daily_{f}"
        rec["daily"][f] = []
        for s in fm["symbols"]:
            sym = s["symbol"]
            ks = [(f"data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip", v["sha256"])
                  for m, v in sorted(s["klines"].items()) if v]
            rec["daily"][f].append(rebuild(sym, ks, d / f"{sym}_1d.csv", d / f"{sym}_1d_taker.csv"))
    TAKER_MANIFEST.write_text(json.dumps(rec, indent=1) + "\n")
    n = len(rec["4h"]) + len(rec["4h_fill"]) + sum(len(v) for v in rec["daily"].values())
    z = sum(x["zips"] for x in rec["4h"] + rec["4h_fill"]) + sum(x["zips"] for v in rec["daily"].values() for x in v)
    print(f"taker columns restored: {n} files from {z} quarantined zips, each at its recorded SHA-256; "
          "every rebuilt row matched its derived CSV")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
