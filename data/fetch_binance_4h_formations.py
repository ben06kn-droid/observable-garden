"""Exploratory fetch: 4h klines for the 2020-09 and 2021-01 formation universes (draft
`prereg/binance-panel.md`; the author's request of 2026-10-09, three 4h variants side by
side).

The universes are the daily formations' (`data/binance_daily_manifest.json`): the same
point-in-time rule as the 4h universe, held fixed from the month after formation. For each
contract, the monthly 4h kline zips from that month through 2025-03:
- each zip is verified against its published CHECKSUM;
- a zip already in the quarantine is reused only when its bytes match that CHECKSUM;
- a new zip is quarantined under ~/Desktop, as all raw files are;
- in-sample months only; nothing on or after 2025-04-01 is fetched or kept.
Derived CSVs go to `data/raw/binance_4h_<formation>/`: `{SYM}_4h.csv` (the standard eight
columns), `{SYM}_4h_taker.csv` (the taker-buy columns), and `{SYM}_funding.csv`, copied
from the daily formation's funding CSV (the same verified funding zips; funding does not
depend on the bar).

Bars missing from the monthly files are counted and recorded, not filled. The daily-file
fill (decision B2) was applied to the 2021-10 4h universe only. These two formations are
exploratory, and their gaps are carried as the panel builder carries any gap.

    python -m data.fetch_binance_4h_formations
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor

from data import fetch_binance as fb
from data import fetch_binance_daily as fd             # installs the retrying _get
from data import rebuild_binance_taker as rt

FORMATIONS = ("2020-09", "2021-01")
MANIFEST = fb.REPO / "data" / "binance_4h_formations_manifest.json"
BAR_MS = 4 * 3600 * 1000


def checked_blob(key: str) -> tuple[bytes, bool]:
    """(bytes, reused): the quarantined copy if it matches the published CHECKSUM, else a
    fresh verified download, quarantined."""
    want = fb._get(f"{fb.DATA}/{key}.CHECKSUM").decode().split()[0].strip().lower()
    p = fb.QUARANTINE / key
    if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == want:
        return p.read_bytes(), True
    blob = fb._get(f"{fb.DATA}/{key}")
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        raise fb.FetchRefused(f"{key}: SHA-256 {got} is not the published {want}")
    fb._save(key, blob)
    return blob, False


def missing_bars(rows: list[list]) -> int:
    if not rows:
        return 0
    ts = sorted(r[0] for r in rows)
    return int((ts[-1] - ts[0]) // BAR_MS + 1 - len(set(ts)))


def fetch_symbol(sym: str, first: str, outdir, daily_dir) -> dict:
    rec = {"symbol": sym, "klines": {}}
    keys = fb._listing(f"data/futures/um/monthly/klines/{sym}/4h/")
    rows = []
    for m in fb.months(first, fb.LAST_INSAMPLE_MONTH):
        key = f"data/futures/um/monthly/klines/{sym}/4h/{sym}-4h-{m}.zip"
        if key not in keys:
            rec["klines"][m] = None
            continue
        blob, reused = checked_blob(key)
        r = rt.parse_klines_taker(blob)
        rows += r
        rec["klines"][m] = {"sha256": hashlib.sha256(blob).hexdigest(), "rows": len(r), "reused": reused}
    if any(r[0] >= rt.CUT for r in rows):
        raise fb.FetchRefused(f"{sym}: a row on or after 2025-04-01")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / f"{sym}_4h.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
        w.writerows(sorted(r[:8] for r in rows))
    rec["taker_sha256"] = rt.write_taker(outdir / f"{sym}_4h_taker.csv", rows)
    shutil.copyfile(daily_dir / f"{sym}_funding.csv", outdir / f"{sym}_funding.csv")
    rec["funding_from"] = str((daily_dir / f"{sym}_funding.csv").relative_to(fb.REPO))
    rec["missing_bars_between_first_and_last"] = missing_bars(rows)
    rec["first_open"] = min(r[0] for r in rows) if rows else None
    return rec


def main(argv=None) -> int:
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists: fetched once")
    daily = json.loads(fd.MANIFEST.read_text())["formations"]
    out = {"fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "formations": {}}
    for f in FORMATIONS:
        fm = daily[f]
        outdir = fb.REPO / "data" / "raw" / f"binance_4h_{f}"
        ddir = fb.REPO / "data" / "raw" / f"binance_daily_{f}"
        with ThreadPoolExecutor(8) as ex:
            per = list(ex.map(lambda s: fetch_symbol(s, fm["first_month"], outdir, ddir), fm["universe"]))
        out["formations"][f] = {"universe": fm["universe"], "first_month": fm["first_month"],
                                "full_month_traders": fm["full_month_traders"], "symbols": per}
        n = sum(1 for p in per for v in p["klines"].values() if v)
        reused = sum(1 for p in per for v in p["klines"].values() if v and v["reused"])
        gaps = {p["symbol"]: p["missing_bars_between_first_and_last"] for p in per if p["missing_bars_between_first_and_last"]}
        print(f"formation {f}: {len(per)} contracts from {fm['first_month']}; {n} monthly 4h zips verified "
              f"({reused} reused from the quarantine, {n - reused} downloaded); missing bars {gaps}", flush=True)
    MANIFEST.write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
