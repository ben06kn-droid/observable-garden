"""The book-ticker check of the cost rule's half-spread estimator (draft
`prereg/binance-panel.md`; the author's request of 2026-10-09). Laptop; in-sample only; no
return, Sharpe or p-value is computed.

Three contracts of the chosen universe (4h, formation 2021-01), of different liquidity:
BTCUSDT (rank 1 by formation-month quote volume), VETUSDT (rank 26), ZENUSDT (rank 50).
Four days each, inside 2023-05 to 2024-04: 2023-06-14, 2023-09-13, 2023-12-13, 2024-03-13.
Only those twelve daily book-ticker files are downloaded. Each is verified against its
published CHECKSUM and quarantined.

For each contract-day:
- **quoted:** the time-weighted quoted half-spread, (ask - bid) / (2 mid). Each update is
  weighted by the time until the next one, and the day's last update by the time to the
  day's end;
- **EDGE:** the rule's estimate for the month containing the day: half of EDGE on the
  contract's 4h bars opening in the 30 days before the month starts;
- **Abdi-Ranaldo:** the named fallback, on the same bars.
Each is shown raw and floored at 1 bp, in bps.

**Pre-committed test, fixed before any book-ticker file is read.** EDGE is "clearly
biased" iff, for at least two of the three contracts, the median over the four days of the
floored EDGE half-spread and the median of the floored quoted half-spread:
- differ by more than 1 bp, AND
- have a ratio outside [0.5, 2].
If so, the rule uses Abdi-Ranaldo, which is put to the same test. If both fail, the
estimator choice returns to the author.

    python -m experiments.binance_spread_check --out runs/binance_spread_check/2026-10-09
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import zipfile
from pathlib import Path

import numpy as np

CONTRACTS = ("BTCUSDT", "VETUSDT", "ZENUSDT")
DAYS = ("2023-06-14", "2023-09-13", "2023-12-13", "2024-03-13")
FORMATION = "2021-01"


def quoted_half_spread(blob: bytes, day: str) -> dict:
    """Time-weighted quoted half-spread (a proportion) over one UTC day of book-ticker
    updates."""
    import pandas as pd
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = z.namelist()[0]
    with z.open(name) as fh:
        first = fh.readline().decode()
    header = 0 if not first.split(",")[0].strip().isdigit() else None
    cols = ["update_id", "best_bid_price", "best_bid_qty", "best_ask_price", "best_ask_qty",
            "transaction_time", "event_time"]
    d0 = int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    d1 = d0 + 86_400_000
    num, den, n, prev_t, prev_h = 0.0, 0.0, 0, None, None
    with z.open(name) as fh:
        for ch in pd.read_csv(fh, header=header, names=None if header == 0 else cols,
                              usecols=["best_bid_price", "best_ask_price", "transaction_time"],
                              chunksize=5_000_000):
            t = ch["transaction_time"].to_numpy(np.int64)
            b = ch["best_bid_price"].to_numpy(float)
            a = ch["best_ask_price"].to_numpy(float)
            hs = (a - b) / (a + b)                     # (a - b) / (2 mid)
            ok = (a > 0) & (b > 0) & (a >= b)
            t, hs = t[ok], hs[ok]
            if prev_t is not None and t.size:
                w0 = max(t[0] - prev_t, 0)
                num += prev_h * w0
                den += w0
            w = np.clip(np.diff(t), 0, None).astype(float)
            num += float((hs[:-1] * w).sum())
            den += float(w.sum())
            n += t.size
            if t.size:
                prev_t, prev_h = int(t[-1]), float(hs[-1])
    if prev_t is not None:
        w = max(d1 - prev_t, 0)
        num += prev_h * w
        den += w
    return {"half_spread": num / den if den > 0 else float("nan"), "updates": n}


def estimates_for(sym: str, day: str) -> dict:
    from environments import binance_costs as K
    from environments import binance_panel as bp
    from experiments.binance_design_v2_4h import spec_for
    symbols, directory, spec, _ = spec_for(f"4h-{FORMATION}")
    times = bp.grid(spec)
    kl, _ = bp.load_symbol(sym, directory, "4h")
    pos = {t: i for i, t in enumerate(times.tolist())}
    O, H, L, C = (np.full((len(times), 1), np.nan) for _ in range(4))
    tr = np.zeros((len(times), 1), bool)
    for r in kl:
        i = pos.get(r[0])
        if i is not None:
            O[i, 0], H[i, 0], L[i, 0], C[i, 0] = r[1], r[2], r[3], r[4]
            tr[i, 0] = r[7] > 0 and r[5] > 0
    d = dt.date.fromisoformat(day)
    ms = int(dt.datetime(d.year, d.month, 1, tzinfo=dt.timezone.utc).timestamp() * 1000)
    out = {}
    for est in ("edge", "abdi_ranaldo"):
        starts, hs = K.monthly_half_spreads(times, O, H, L, C, tr, est)
        out[est] = float(hs[starts.index(ms), 0])
    return out


def verdict(rows: list[dict], key: str) -> dict:
    floor = 1.0
    per = {}
    for sym in CONTRACTS:
        r = [x for x in rows if x["contract"] == sym]
        q = float(np.median([max(x["quoted_bps"], floor) for x in r]))
        e = float(np.median([max(x[f"{key}_bps"], floor) for x in r]))
        per[sym] = {"quoted_floored_median": q, "estimate_floored_median": e, "diff_bps": e - q,
                    "ratio": e / q, "fails": bool(abs(e - q) > 1.0 and not 0.5 <= e / q <= 2.0)}
    n = sum(v["fails"] for v in per.values())
    return {"per_contract": per, "contracts_failing": n, "clearly_biased": n >= 2}


def main(argv=None) -> int:
    from data import fetch_binance as fb
    from data import fetch_binance_daily as fd   # noqa: F401  (retrying _get)
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    if (out / "spread_check.json").exists():
        raise SystemExit("exists; not overwriting")
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for sym in CONTRACTS:
        for day in DAYS:
            key = f"data/futures/um/daily/bookTicker/{sym}/{sym}-bookTicker-{day}.zip"
            blob = fb.verified(key)
            fb._save(key, blob)
            q = quoted_half_spread(blob, day)
            del blob
            e = estimates_for(sym, day)
            rows.append({"contract": sym, "day": day, "updates": q["updates"],
                         "quoted_bps": q["half_spread"] * 1e4, "edge_bps": e["edge"] * 1e4,
                         "abdi_ranaldo_bps": e["abdi_ranaldo"] * 1e4})
            print(f"{sym} {day}: quoted {q['half_spread'] * 1e4:.3f} bps ({q['updates']} updates); "
                  f"EDGE {e['edge'] * 1e4:.3f}; Abdi-Ranaldo {e['abdi_ranaldo'] * 1e4:.3f}", flush=True)
    res = {"rows": rows, "edge": verdict(rows, "edge")}
    if res["edge"]["clearly_biased"]:
        res["abdi_ranaldo"] = verdict(rows, "abdi_ranaldo")
    from scipy.stats import spearmanr
    for k in ("edge", "abdi_ranaldo"):
        res[f"spearman_{k}"] = float(spearmanr([r["quoted_bps"] for r in rows], [r[f"{k}_bps"] for r in rows])[0])
    L = ["Book-ticker check of the half-spread estimator (in-sample days; bps)", "=" * 80,
         f"{'contract':<9} {'day':<11} {'quoted':>8} {'EDGE':>8} {'A-R':>8} {'updates':>10}"]
    for r in rows:
        L.append(f"{r['contract']:<9} {r['day']:<11} {r['quoted_bps']:>8.3f} {r['edge_bps']:>8.3f} "
                 f"{r['abdi_ranaldo_bps']:>8.3f} {r['updates']:>10}")
    for k in ("edge", "abdi_ranaldo"):
        if k in res:
            v = res[k]
            L.append(f"{k}: " + "; ".join(f"{s} floored median est {x['estimate_floored_median']:.2f} vs quoted "
                                           f"{x['quoted_floored_median']:.2f} (diff {x['diff_bps']:+.2f}, ratio "
                                           f"{x['ratio']:.2f}) {'FAILS' if x['fails'] else 'ok'}"
                                           for s, x in v["per_contract"].items())
                     + f" -> clearly biased: {v['clearly_biased']}")
    L.append(f"Spearman (12 contract-days, raw): EDGE {res['spearman_edge']:.2f}; Abdi-Ranaldo {res['spearman_abdi_ranaldo']:.2f}")
    (out / "spread_check.txt").write_text("\n".join(L) + "\n")
    (out / "spread_check.json").write_text(json.dumps(res, indent=1))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
