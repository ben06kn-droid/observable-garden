"""Exploratory fetch for the DAILY-bar alternative (draft `prereg/binance-panel.md`, item C2).

For each formation month in `FORMATIONS` (2020-09, 2021-01, 2021-10): the same point-in-time
rule as the 4h universe (`data.fetch_binance`: eligible USDT perpetuals, a 1d kline with
trades on every day of the formation month, top 50 by the month's quote volume, held fixed);
then 1d klines and funding for those contracts from the month AFTER formation through
2025-03, each zip verified against its published CHECKSUM and quarantined under ~/Desktop.
Derived CSVs go to `data/raw/binance_daily_<formation>/`. Nothing on or after 2025-04-01 is
fetched.

    python -m data.fetch_binance_daily
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from data import fetch_binance as fb

FORMATIONS = ("2020-09", "2021-01", "2021-10")


def _retrying(fn, tries: int = 5):
    """A network call retried with backoff; the CHECKSUM verification is unchanged."""
    import time

    def call(*a, **k):
        for i in range(tries):
            try:
                return fn(*a, **k)
            except fb.FetchRefused:
                raise
            except Exception:
                if i == tries - 1:
                    raise
                time.sleep(2 ** i)
    return call


fb._get = _retrying(fb._get)
MANIFEST = fb.REPO / "data" / "binance_daily_manifest.json"


def next_month(m: str) -> str:
    y, mm = map(int, m.split("-"))
    return f"{y + (mm == 12):04d}-{mm % 12 + 1:02d}"


def formation_for(month: str, cand: list[str]) -> list[dict]:
    old = fb.FORMATION_MONTH
    fb.FORMATION_MONTH = month
    try:
        return fb.formation(cand)
    finally:
        fb.FORMATION_MONTH = old


def fetch_daily(sym: str, first: str, outdir) -> dict:
    rec = {"symbol": sym, "klines": {}, "funding": {}}
    kl_keys = fb._listing(f"data/futures/um/monthly/klines/{sym}/1d/")
    fr_keys = fb._listing(f"data/futures/um/monthly/fundingRate/{sym}/")
    kl, fr = [], []
    for m in fb.months(first, fb.LAST_INSAMPLE_MONTH):
        for kind, key, keys, parse, out in (
                ("klines", f"data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{m}.zip", kl_keys, fb.parse_klines, kl),
                ("funding", f"data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip", fr_keys, fb.parse_funding, fr)):
            if key in keys:
                blob = fb.verified(key)
                fb._save(key, blob)
                rows = parse(blob)
                out += rows
                rec[kind][m] = {"sha256": hashlib.sha256(blob).hexdigest(), "rows": len(rows)}
            else:
                rec[kind][m] = None
    cut = int(dt.datetime(2025, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    if any(r[0] >= cut for r in kl + fr):
        raise fb.FetchRefused(f"{sym}: a row on or after 2025-04-01")
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / f"{sym}_1d.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
        w.writerows(sorted(kl))
    with open(outdir / f"{sym}_funding.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["calc_time", "funding_interval_hours", "rate"])
        w.writerows(sorted(fr))
    return rec


def main(argv=None) -> int:
    from experiments.audit_new_panels import list_prefix
    if MANIFEST.exists():
        raise SystemExit(f"{MANIFEST} exists: fetched once")
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    prefixes, _ = list_prefix("data/futures/um/monthly/klines/")
    cand = [s for s in sorted(p.rstrip("/").split("/")[-1] for p in prefixes) if fb.eligible(s)]
    out = {"fetched_at_utc": fetched_at, "formations": {}}
    for f in FORMATIONS:
        y, m = map(int, f.split("-"))
        n_days = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.date(y, m, 1)).days
        form = formation_for(f, cand)
        uni = fb.rank_universe(form, n_days)
        first = next_month(f)
        outdir = fb.REPO / "data" / "raw" / f"binance_daily_{f}"
        with ThreadPoolExecutor(8) as ex:
            per = list(ex.map(lambda s: fetch_daily(s, first, outdir), [u["symbol"] for u in uni]))
        out["formations"][f] = {"full_month_traders": sum(x["trading_days"] == n_days for x in form),
                                "universe": [u["symbol"] for u in uni], "first_month": first,
                                "formation": sorted(form, key=lambda x: -x["quote_volume"]), "symbols": per}
        print(f"formation {f}: {out['formations'][f]['full_month_traders']} full-month traders; "
              f"universe {len(uni)}; data from {first}", flush=True)
    MANIFEST.write_text(json.dumps(out, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
