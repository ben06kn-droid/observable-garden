"""Pinned inputs for the chosen Binance variant: 4h bars, formation 2021-01 (draft
`prereg/binance-panel.md`). Each array set is built once on the laptop, hashed, and served
only at its hash; nothing is rebuilt on a mismatch.

- `binance_4h_2021-01_X.npy`: P, the registered 40 features (price-only), (T, 50, 40).
- `binance_4h_2021-01_v2.npz`: version 2's blocks X (10), V (5), F (3) and the groups.
- `binance_4h_2021-01_costs.npz`: the cost rule's (T, 50) per-row cost rates, the monthly
  half-spread table, and the month starts.

    python -m environments.binance_pins --estimator edge
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
PIN_DIR = REPO / "data" / "pinned"
NAME = "4h-2021-01"
FILES = {"X": PIN_DIR / "binance_4h_2021-01_X.npy", "v2": PIN_DIR / "binance_4h_2021-01_v2.npz",
         "costs": PIN_DIR / "binance_4h_2021-01_costs.npz"}
SHA256 = {"X": "e6ff168cc06dbe795b90d73edfeafad332f886417331f2e921404ad677e8e257",       # arm64, 2026-10-09
          "v2": "47c688ee76ba8e9f5070a31e4ff155a0d702e6e7a72bc99aee5c4e224206e6c5",
          "costs": "74be4b19b9fad50cc878aae82d4b616b1ec93f12026aedf8aa51a45033399789"}


def ohlc_grid(name: str = NAME):
    """(times, O, H, L, C, traded) on the variant's grid, NaN where no kline row."""
    from environments import binance_panel as bp
    from experiments.binance_design_v2_4h import spec_for
    symbols, directory, spec, _ = spec_for(name)
    times = bp.grid(spec)
    pos = {t: i for i, t in enumerate(times.tolist())}
    T, M = len(times), len(symbols)
    O, H, L, C = (np.full((T, M), np.nan) for _ in range(4))
    tr = np.zeros((T, M), bool)
    for j, s in enumerate(symbols):
        kl, _ = bp.load_symbol(s, directory, "4h")
        for r in kl:
            i = pos.get(r[0])
            if i is not None:
                O[i, j], H[i, j], L[i, j], C[i, j] = r[1], r[2], r[3], r[4]
                tr[i, j] = r[7] > 0 and r[5] > 0
    return times, O, H, L, C, tr


def build(estimator: str) -> dict:
    from environments import binance_costs as K
    from experiments.binance_design_v2_4h import build_blocks, raw_4h
    raw = raw_4h(NAME)
    blk = build_blocks(raw)
    times, O, H, L, C, tr = ohlc_grid(NAME)
    alive = raw["alive"]
    tr = tr & alive
    starts, hs = K.monthly_half_spreads(times, O, H, L, C, tr, estimator)
    hsf = K.fill_months(hs)
    rates = K.cost_rates(times, starts, hsf, alive, raw["WARM"], raw["LAG"])
    return {"X": np.ascontiguousarray(raw["panel"].features, dtype=np.float64),
            "v2": {"X": blk["X"], "V": blk["V"], "F": blk["F"], "G": blk["G"], "vnames": np.array(blk["vnames"])},
            "costs": {"rates": rates, "half_spread": hs, "half_spread_filled": hsf,
                      "month_starts": np.array(starts, np.int64), "estimator": np.array(estimator)}}


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pin(estimator: str) -> dict:
    for p in FILES.values():
        if p.exists():
            raise SystemExit(f"{p} exists; pins are written once")
    b = build(estimator)
    PIN_DIR.mkdir(parents=True, exist_ok=True)
    np.save(FILES["X"], b["X"])
    with open(FILES["v2"], "wb") as fh:
        np.savez(fh, **b["v2"])
    with open(FILES["costs"], "wb") as fh:
        np.savez(fh, **b["costs"])
    return {k: _sha(p) for k, p in FILES.items()}


def load(which: str, sha256: str | None = None):
    p = FILES[which]
    want = SHA256[which] if sha256 is None else sha256
    if not want:
        raise SystemExit(f"no pinned {which} is registered yet")
    if not p.exists() or _sha(p) != want:
        raise SystemExit(f"pinned {which} {p} missing or not SHA-256 {want}; refused")
    return np.load(p) if p.suffix == ".npy" else dict(np.load(p))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--estimator", required=True, choices=("edge", "abdi_ranaldo"))
    a = ap.parse_args()
    for k, v in pin(a.estimator).items():
        print(f"{k}: {FILES[k].name} SHA-256 {v}")
