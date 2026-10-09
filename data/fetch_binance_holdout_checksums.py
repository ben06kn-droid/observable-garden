"""Fix the identity of the chosen Binance variant's holdout now, without reading it (draft
`prereg/binance-panel.md`, section j; author, 2026-10-09). Also hash every derived in-sample
CSV for the dataset ledger.

1. **The holdout's identity.** For each of the 50 contracts (4h, formation 2021-01) and
   each holdout month from 2025-04 to 2026-09:
   - the bucket listing gives the monthly 4h kline file and funding file, and their sizes;
   - only each file's `.CHECKSUM` is downloaded, a line of text with its SHA-256;
   - **no data zip is downloaded**, and the code refuses any URL that does not end in
     `.CHECKSUM`.
   At grading, each holdout file fetched on the holdout host must match the hash recorded
   here.
2. **The derived in-sample CSVs.** The SHA-256 and row count of every file in
   `data/raw/binance_4h_2021-01/`.

    python -m data.fetch_binance_holdout_checksums
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from data import fetch_binance as fb
from data import fetch_binance_daily as fd          # installs the retrying _get

FORMATION = "2021-01"
HOLDOUT_MONTHS = fb.months("2025-04", "2026-09")
OUT_HOLDOUT = fb.REPO / "data" / "binance_4h_2021-01_holdout_checksums.json"
OUT_DERIVED = fb.REPO / "data" / "binance_4h_2021-01_derived_manifest.json"


def checksum_text(key: str) -> str:
    url = f"{fb.DATA}/{key}.CHECKSUM"
    if not url.endswith(".CHECKSUM"):
        raise fb.FetchRefused(f"{url}: only CHECKSUM files are fetched")
    return fb._get(url).decode().strip()


def contract(sym: str) -> dict:
    out = {"symbol": sym, "klines_4h": {}, "funding": {}}
    for kind, prefix, name in (("klines_4h", f"data/futures/um/monthly/klines/{sym}/4h/", f"{sym}-4h-{{m}}.zip"),
                               ("funding", f"data/futures/um/monthly/fundingRate/{sym}/", f"{sym}-fundingRate-{{m}}.zip")):
        keys = fb._listing(prefix)
        for m in HOLDOUT_MONTHS:
            key = prefix + name.format(m=m)
            if key not in keys:
                out[kind][m] = None
                continue
            text = checksum_text(key)
            out[kind][m] = {"key": key, "bytes": keys[key], "checksum_text": text,
                            "sha256": text.split()[0].lower()}
    return out


def derived() -> dict:
    d = fb.REPO / "data" / "raw" / f"binance_4h_{FORMATION}"
    files = {}
    for p in sorted(d.glob("*.csv")):
        b = p.read_bytes()
        files[p.name] = {"sha256": hashlib.sha256(b).hexdigest(), "rows": b.count(b"\n") - 1}
    combined = hashlib.sha256("".join(f"{k} {v['sha256']}\n" for k, v in files.items()).encode()).hexdigest()
    return {"directory": str(d.relative_to(fb.REPO)), "files": files, "n_files": len(files),
            "combined_sha256": combined,
            "combined_rule": "SHA-256 of the lines '<file name> <file SHA-256>\\n', sorted by name"}


def main(argv=None) -> int:
    for p in (OUT_HOLDOUT, OUT_DERIVED):
        if p.exists():
            raise SystemExit(f"{p} exists: written once")
    uni = json.loads((fb.REPO / "data" / "binance_4h_formations_manifest.json").read_text())["formations"][FORMATION]["universe"]
    with ThreadPoolExecutor(8) as ex:
        per = list(ex.map(contract, uni))
    n = sum(1 for c in per for k in ("klines_4h", "funding") for v in c[k].values() if v)
    absent = sum(1 for c in per for k in ("klines_4h", "funding") for v in c[k].values() if v is None)
    OUT_HOLDOUT.write_text(json.dumps({"recorded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                                       "formation": FORMATION, "months": HOLDOUT_MONTHS, "files_present": n,
                                       "contract_months_absent": absent, "contracts": per}, indent=1) + "\n")
    dv = derived()
    OUT_DERIVED.write_text(json.dumps(dv, indent=1) + "\n")
    print(f"holdout: {n} CHECKSUM texts recorded ({absent} contract-month files absent); no data zip downloaded")
    print(f"derived: {dv['n_files']} CSVs hashed; combined SHA-256 {dv['combined_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
