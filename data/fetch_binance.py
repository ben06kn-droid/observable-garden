"""One fetch of the Binance USDT-margined perpetual panel (draft `prereg/binance-panel.md`).

Everything is from data.binance.vision, futures/um, MONTHLY files, each verified against
its published `.CHECKSUM` (SHA-256) before use. Raw zips are kept, verified, in a quarantine
directory OUTSIDE the repository under `~/Desktop` (refused by every loader); only derived
in-sample CSVs are written under `data/raw/binance_insample/` (gitignored).

1. **Universe, point in time** (`FORMATION_MONTH` 2021-10, before the warm-up starts):
   every symbol in the futures/um klines listing that is a USDT-quoted perpetual (no `_`
   delivery suffix), whose base is not a stablecoin and which is not a composite index
   contract, with a 1d kline for EVERY day of the formation month showing trades. Ranked by
   the month's summed quote volume (USDT); the top `TOP_N` = 50, held fixed.
2. **In-sample data** for those 50: 4h klines and funding-rate files for every month from
   `FIRST_MONTH` (2021-11, the warm-up) through `LAST_INSAMPLE_MONTH` (2025-03). A month
   with no file (after a delisting) is recorded as absent.
3. **Holdout, counted only:** for months 2025-04 onward, the listing's file names and sizes
   and the text of each `.CHECKSUM` file (a hash, no data) are recorded. No holdout zip is
   downloaded, opened or parsed.

    python -m data.fetch_binance
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DATA = "https://data.binance.vision"
FORMATION_MONTH = "2021-10"
FIRST_MONTH, LAST_INSAMPLE_MONTH = "2021-11", "2025-03"
HOLDOUT_FIRST_MONTH = "2025-04"
TOP_N = 50
STABLE_BASES = {"USDC", "BUSD", "TUSD", "USDP", "DAI", "FDUSD", "PAX", "UST", "USTC", "SUSD"}
INDEX_CONTRACTS = {"DEFIUSDT", "BTCDOMUSDT", "FOOTBALLUSDT", "BLUEBIRDUSDT"}
REPO = Path(__file__).resolve().parent.parent
INSAMPLE_DIR = REPO / "data" / "raw" / "binance_insample"
MANIFEST = REPO / "data" / "binance_manifest.json"
QUARANTINE = Path.home() / "Desktop" / "og-quarantine" / "binance"
KLINE_COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
              "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
MONTH = re.compile(r"-(\d{4}-\d{2})\.zip$")


class FetchRefused(RuntimeError):
    pass


def _get(url: str) -> bytes:
    from experiments.audit_new_panels import _get as get
    return get(url)


def months(first: str, last: str) -> list[str]:
    y, m = map(int, first.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= last:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def eligible(symbol: str) -> bool:
    """USDT-quoted perpetual, not a stablecoin base, not a composite index contract."""
    if "_" in symbol or not symbol.endswith("USDT") or symbol in INDEX_CONTRACTS:
        return False
    return symbol[:-4] not in STABLE_BASES


def verified(path_in_bucket: str) -> bytes:
    """The zip's bytes, after its SHA-256 matches the published CHECKSUM; else refuse."""
    blob = _get(f"{DATA}/{path_in_bucket}")
    want = _get(f"{DATA}/{path_in_bucket}.CHECKSUM").decode().split()[0].strip().lower()
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        raise FetchRefused(f"{path_in_bucket}: SHA-256 {got} is not the published {want}")
    return blob


def parse_klines(blob: bytes) -> list[list]:
    """Rows of (open_time ms, open, high, low, close, volume, quote_volume, count); a header
    row, present in some months, is skipped; microsecond times are refused."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    rows = []
    for ln in z.read(z.namelist()[0]).decode().strip().splitlines():
        f = ln.split(",")
        if not f[0].strip().isdigit():
            continue
        t = int(f[0])
        if not 1e12 <= t < 1e13:
            raise FetchRefused(f"open time {t} is not in milliseconds")
        rows.append([t, float(f[1]), float(f[2]), float(f[3]), float(f[4]), float(f[5]),
                     float(f[7]), int(float(f[8]))])
    return rows


def parse_funding(blob: bytes) -> list[list]:
    """Rows of (calc_time ms, funding_interval_hours, rate), by header name."""
    z = zipfile.ZipFile(io.BytesIO(blob))
    lines = z.read(z.namelist()[0]).decode().strip().splitlines()
    head = [h.strip() for h in lines[0].split(",")]
    if not head[0].isdigit():
        ix = {h: i for i, h in enumerate(head)}
        body = lines[1:]
    else:
        ix = {"calc_time": 0, "funding_interval_hours": 1, "last_funding_rate": 2}
        body = lines
    need = ("calc_time", "funding_interval_hours", "last_funding_rate")
    if any(k not in ix for k in need):
        raise FetchRefused(f"funding header {head} lacks {need}")
    out = []
    for ln in body:
        f = ln.split(",")
        out.append([int(f[ix["calc_time"]]), float(f[ix["funding_interval_hours"]]),
                    float(f[ix["last_funding_rate"]])])
    return out


def _listing(prefix: str) -> dict:
    from experiments.audit_new_panels import list_prefix
    _, keys = list_prefix(prefix)
    return dict(keys)


def formation(symbols: list[str]) -> list[dict]:
    """Each eligible symbol's formation-month quote volume and trading days (1d klines)."""
    def one(sym):
        key = f"data/futures/um/monthly/klines/{sym}/1d/{sym}-1d-{FORMATION_MONTH}.zip"
        if key not in _listing(f"data/futures/um/monthly/klines/{sym}/1d/"):
            return None
        blob = verified(key)
        rows = parse_klines(blob)
        _save(key, blob)
        days = {dt.datetime.fromtimestamp(r[0] / 1000, dt.timezone.utc).date() for r in rows if r[7] > 0}
        return {"symbol": sym, "quote_volume": sum(r[6] for r in rows), "trading_days": len(days),
                "zip_sha256": hashlib.sha256(blob).hexdigest()}
    with ThreadPoolExecutor(16) as ex:
        return [r for r in ex.map(one, symbols) if r]


def rank_universe(form: list[dict], n_days: int, top: int = TOP_N) -> list[dict]:
    """Full-month traders, ranked by formation-month quote volume; ties by symbol."""
    full = [f for f in form if f["trading_days"] == n_days]
    return sorted(full, key=lambda f: (-f["quote_volume"], f["symbol"]))[:top]


def _save(key: str, blob: bytes) -> None:
    p = QUARANTINE / key
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(blob)


def fetch_symbol(sym: str) -> dict:
    """In-sample 4h klines and funding for one symbol, verified; derived CSVs written."""
    rec = {"symbol": sym, "klines": {}, "funding": {}}
    kl_keys = _listing(f"data/futures/um/monthly/klines/{sym}/4h/")
    fr_keys = _listing(f"data/futures/um/monthly/fundingRate/{sym}/")
    kl, fr = [], []
    for m in months(FIRST_MONTH, LAST_INSAMPLE_MONTH):
        k = f"data/futures/um/monthly/klines/{sym}/4h/{sym}-4h-{m}.zip"
        if k in kl_keys:
            blob = verified(k)
            _save(k, blob)
            rows = parse_klines(blob)
            kl += rows
            rec["klines"][m] = {"sha256": hashlib.sha256(blob).hexdigest(), "rows": len(rows)}
        else:
            rec["klines"][m] = None
        f = f"data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{m}.zip"
        if f in fr_keys:
            blob = verified(f)
            _save(f, blob)
            rows = parse_funding(blob)
            fr += rows
            rec["funding"][m] = {"sha256": hashlib.sha256(blob).hexdigest(), "rows": len(rows)}
        else:
            rec["funding"][m] = None
    cut = int(dt.datetime(2025, 4, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    if any(r[0] >= cut for r in kl) or any(r[0] >= cut for r in fr):
        raise FetchRefused(f"{sym}: an in-sample file holds a row on or after 2025-04-01")
    INSAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INSAMPLE_DIR / f"{sym}_4h.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["open_time", "open", "high", "low", "close", "volume", "quote_volume", "count"])
        w.writerows(sorted(kl))
    with open(INSAMPLE_DIR / f"{sym}_funding.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["calc_time", "funding_interval_hours", "rate"])
        w.writerows(sorted(fr))
    # holdout: names, sizes and CHECKSUM text only
    ho = {}
    for kind, keys in (("klines", kl_keys), ("funding", fr_keys)):
        hk = sorted(k for k in keys if k.endswith(".zip") and MONTH.search(k)
                    and MONTH.search(k).group(1) >= HOLDOUT_FIRST_MONTH)
        ho[kind] = [{"key": k, "bytes": keys[k],
                     "checksum": _get(f"{DATA}/{k}.CHECKSUM").decode().split()[0]} for k in hk]
    rec["holdout_counted_only"] = ho
    return rec


def main(argv=None) -> int:
    from experiments.audit_new_panels import list_prefix
    for p in (MANIFEST, INSAMPLE_DIR):
        if p.exists():
            raise SystemExit(f"{p} exists: the fetch happens once")
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    prefixes, _ = list_prefix("data/futures/um/monthly/klines/")
    listed = sorted(p.rstrip("/").split("/")[-1] for p in prefixes)
    cand = [s for s in listed if eligible(s)]
    y, m = map(int, FORMATION_MONTH.split("-"))
    n_days = ((dt.date(y + (m == 12), m % 12 + 1, 1)) - dt.date(y, m, 1)).days
    form = formation(cand)
    uni = rank_universe(form, n_days)
    with ThreadPoolExecutor(8) as ex:
        per = list(ex.map(fetch_symbol, [u["symbol"] for u in uni]))
    man = {"fetched_at_utc": fetched_at, "source": DATA, "formation_month": FORMATION_MONTH,
           "rule": {"top_n": TOP_N, "stable_bases_excluded": sorted(STABLE_BASES),
                    "index_contracts_excluded": sorted(INDEX_CONTRACTS),
                    "full_month_trading_days": n_days},
           "listed_symbols": len(listed), "eligible_candidates": len(cand),
           "formation": sorted(form, key=lambda f: -f["quote_volume"]),
           "universe": [u["symbol"] for u in uni],
           "insample_months": [FIRST_MONTH, LAST_INSAMPLE_MONTH], "symbols": per,
           "quarantine": str(QUARANTINE)}
    MANIFEST.write_text(json.dumps(man, indent=1) + "\n")
    n_ho = sum(len(s["holdout_counted_only"][k]) for s in per for k in ("klines", "funding"))
    print(json.dumps({"fetched_at_utc": fetched_at, "eligible_candidates": len(cand),
                      "formation_full_month": sum(f["trading_days"] == n_days for f in form),
                      "universe": man["universe"], "holdout_files_counted_only": n_ho}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
