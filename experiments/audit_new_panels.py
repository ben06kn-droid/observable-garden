"""New-panels audit (`prereg/new-panels-audit-2026-10-06.md`): metadata and in-sample rows
only. No row on or after a cut is read; no holdout value is printed, stored or
summarised.

    python -m experiments.audit_new_panels binance-listing --out runs/new_panels_audit
    python -m experiments.audit_new_panels binance-insample --out runs/new_panels_audit
    python -m experiments.audit_new_panels french --out runs/new_panels_audit
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
DATA = "https://data.binance.vision"
NS = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
BINANCE_CUT = "2025-04"          # holdout from 2025-04-01 00:00 UTC; months < this are in-sample
FRENCH_URL = ("https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
              "{n}_Industry_Portfolios_daily_CSV.zip")
FRENCH_START, FRENCH_CUT = 20100101, 20200101


def _ctx():
    import ssl
    import certifi                         # the python.org build ships without CA certs
    return ssl.create_default_context(cafile=certifi.where())


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "observable-garden-audit"})
    with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r:
        return r.read()


def list_prefix(prefix: str, delimiter: str | None = "/"):
    """(common prefixes, [(key, size)]) under a prefix, following pagination."""
    prefixes, keys, marker = [], [], ""
    while True:
        url = f"{BUCKET}?prefix={prefix}" + (f"&delimiter={delimiter}" if delimiter else "") \
            + (f"&marker={marker}" if marker else "")
        root = ET.fromstring(_get(url))
        prefixes += [p.find("s3:Prefix", NS).text for p in root.findall("s3:CommonPrefixes", NS)]
        for c in root.findall("s3:Contents", NS):
            keys.append((c.find("s3:Key", NS).text, int(c.find("s3:Size", NS).text)))
        if root.find("s3:IsTruncated", NS).text != "true":
            return prefixes, keys
        nm = root.find("s3:NextMarker", NS)
        marker = nm.text if nm is not None else (keys[-1][0] if keys else prefixes[-1])


MONTH = re.compile(r"-(\d{4}-\d{2})\.zip$")


def symbol_months(symbol: str, kind: str = "klines", interval: str = "1h") -> dict:
    base = f"data/futures/um/monthly/{kind}/{symbol}/" + (f"{interval}/" if interval else "")
    _, keys = list_prefix(base)
    zips = {k: s for k, s in keys if k.endswith(".zip")}
    sums = {k[:-len(".CHECKSUM")] for k, _ in keys if k.endswith(".zip.CHECKSUM")}
    months = sorted(MONTH.search(k).group(1) for k in zips if MONTH.search(k))
    return {"symbol": symbol, "months": months,
            "first": months[0] if months else None, "last": months[-1] if months else None,
            "n_months": len(months),
            "missing_checksum": sorted(k for k in zips if k not in sums),
            "insample_bytes": sum(s for k, s in zips.items()
                                  if MONTH.search(k) and MONTH.search(k).group(1) < BINANCE_CUT)}


def binance_listing(out: Path) -> dict:
    sym_prefixes, _ = list_prefix("data/futures/um/monthly/klines/")
    symbols = sorted(p.rstrip("/").split("/")[-1] for p in sym_prefixes)
    with ThreadPoolExecutor(16) as ex:
        kl = list(ex.map(symbol_months, symbols))
    kl = [k for k in kl if k["months"]]                  # symbols with 1h monthly klines
    fr_prefixes, _ = list_prefix("data/futures/um/monthly/fundingRate/")
    fr_symbols = sorted(p.rstrip("/").split("/")[-1] for p in fr_prefixes)
    with ThreadPoolExecutor(16) as ex:
        fr = list(ex.map(lambda s: symbol_months(s, "fundingRate", ""), fr_symbols))
    rec = {"klines_1h": kl, "fundingRate": [{k: v for k, v in f.items() if k != "months"}
                                            for f in fr]}
    out.mkdir(parents=True, exist_ok=True)
    (out / "binance_listing.json").write_text(json.dumps(rec, indent=1))
    return rec


def binance_insample(out: Path, symbols=("BTCUSDT", "ETHUSDT", "BNBUSDT")) -> str:
    """In-sample months only: layout, timestamp units, missing hours."""
    L = []
    for sym in symbols:
        info = symbol_months(sym)
        months = [m for m in info["months"] if m < BINANCE_CUT]
        rows, headers, units, opens = 0, Counter(), Counter(), []
        for m in months:
            z = zipfile.ZipFile(io.BytesIO(_get(
                f"{DATA}/data/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{m}.zip")))
            text = z.read(z.namelist()[0]).decode()
            lines = text.strip().splitlines()
            first = lines[0].split(",")
            if not first[0].isdigit():
                headers[",".join(first)] += 1
                lines = lines[1:]
            else:
                headers["(no header)"] += 1
            for ln in lines:
                f = ln.split(",")
                t = int(f[0])
                units["ms" if 1e12 <= t < 1e13 else "us" if 1e15 <= t < 1e16 else "other"] += 1
                opens.append(t if t < 1e13 else t // 1000)
                rows += 1
        opens = sorted(set(opens))
        span = (opens[-1] - opens[0]) // 3_600_000 + 1
        gaps = [(a, b) for a, b in zip(opens, opens[1:]) if b - a != 3_600_000]
        L.append(f"{sym}: in-sample months {months[0]}..{months[-1]} ({len(months)}); rows "
                 f"{rows}; distinct hours {len(opens)} of {span} in the span; missing hours "
                 f"{span - len(opens)}; non-hourly steps {len(gaps)}")
        L.append(f"   headers: {dict(headers)}; open-time units: {dict(units)}")
    text = "\n".join(L)
    out.mkdir(parents=True, exist_ok=True)
    (out / "binance_insample.txt").write_text(text + "\n")
    return text


def french(out: Path) -> str:
    """49 industries, daily, value-weighted: in-sample rows only; rows on or after the cut
    are counted from their date field and never parsed into values."""
    raw = zipfile.ZipFile(io.BytesIO(_get(FRENCH_URL.format(n=49))))
    text = raw.read(raw.namelist()[0]).decode("latin-1").splitlines()
    # the first data block is "Average Value Weighted Returns -- Daily"
    start = next(i for i, ln in enumerate(text) if "Value Weighted Returns" in ln)
    header = next(i for i in range(start, len(text)) if text[i].strip().startswith(","))
    cols = [c.strip() for c in text[header].split(",")[1:]]
    ins, n_before, n_after = [], 0, 0
    for ln in text[header + 1:]:
        f = ln.split(",")
        d = f[0].strip()
        if not d.isdigit() or len(d) != 8:
            break                                   # end of the value-weighted block
        if int(d) >= FRENCH_CUT:
            n_after += 1                            # counted only; its values never parsed
            continue
        if int(d) < FRENCH_START:
            n_before += 1
            continue
        ins.append((d, [float(x) for x in f[1:]]))
    miss = Counter()
    for d, vals in ins:
        for c, v in zip(cols, vals):
            if v <= -99.99 or v == -999:
                miss[c] += 1
    alt = {}
    for n in (30, 17):
        try:
            req = urllib.request.Request(FRENCH_URL.format(n=n), method="HEAD",
                                         headers={"User-Agent": "observable-garden-audit"})
            with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r:
                alt[n] = f"exists ({r.headers.get('Content-Length')} bytes)"
        except Exception as e:
            alt[n] = f"not found ({e})"
    L = [f"French 49 industries, daily, value-weighted: {len(cols)} portfolio columns",
         f"   in-sample 2010-01-01..2019-12-31: {len(ins)} days ({ins[0][0]}..{ins[-1][0]})",
         f"   missing values (-99.99) in-sample: "
         + (", ".join(f"{c} {n}" for c, n in miss.items()) if miss else "none; all 49 complete"),
         f"   rows before 2010-01-01 (unused): {n_before}",
         f"   rows on or after 2020-01-01: {n_after} (count only)",
         f"   30-industry daily file: {alt[30]}; 17-industry daily file: {alt[17]}"]
    text = "\n".join(L)
    out.mkdir(parents=True, exist_ok=True)
    (out / "french.txt").write_text(text + "\n")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["binance-listing", "binance-insample", "french"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if a.what == "binance-listing":
        rec = binance_listing(out)
        print(f"{len(rec['klines_1h'])} symbols with 1h klines; "
              f"{len(rec['fundingRate'])} with funding-rate files")
    elif a.what == "binance-insample":
        print(binance_insample(out))
    else:
        print(french(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
