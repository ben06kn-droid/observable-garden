"""`quixote sancho --panel PANEL.npz [--config CONFIG.json] --out OUT_DIR` (and `python -m sancho.cli`).

Runs Sancho on a panel in the quixote panel format (examples/README.md): `returns` (T, M) row
returns, `features` (T, M, K), `periods_per_year`, optional `delay` (default 1), `cost_bps`
(default 5, one-way) and `borrow_bps_yr` (default 50). Feature row t earns returns[t + 1 + d].

Sancho's inputs: the X block (return structure, `sancho.blocks.build_X` on the row returns and
their equal-weight market), and the panel's features as block P when K is 40 (the registered
feature layout the family map assumes). It writes OUT_DIR/sancho.json: the net stream from the
first scored row, its in-sample net Sharpe and turnover, and the config's SHA-256 and whether it
is the default. A non-default config prints one line saying the registered results do not
apply to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from sancho import config as _config
from sancho import learner as Ln
from sancho import views as Vw
from sancho.blocks import build_X

EXIT_USAGE = 64


def inputs_from_npz(path: str | Path) -> tuple[Ln.Inputs, dict]:
    z = np.load(path, allow_pickle=False)
    for k in ("returns", "features", "periods_per_year"):
        if k not in z:
            raise ValueError(f"{path}: the panel has no `{k}` (see examples/README.md)")
    r = np.asarray(z["returns"], float)
    F = np.asarray(z["features"], float)
    if r.ndim != 2 or F.ndim != 3 or F.shape[:2] != r.shape:
        raise ValueError(f"{path}: returns must be (T, M) and features (T, M, K); got {r.shape}, {F.shape}")
    ppy = float(z["periods_per_year"])
    d = int(z["delay"]) if "delay" in z else 1
    if d not in (0, 1):
        raise ValueError(f"{path}: delay must be 0 or 1")
    cost = float(z["cost_bps"]) if "cost_bps" in z else 5.0
    borrow = float(z["borrow_bps_yr"]) if "borrow_bps_yr" in z else 50.0
    lag = 1 + d
    T, M = r.shape
    n = T - lag
    r0 = np.nan_to_num(r)
    earned = r0[lag:]
    market = np.nanmean(np.where(np.isfinite(r), r, np.nan), axis=1)
    market = np.nan_to_num(market)
    X = build_X(r0, market)[:n]
    P = F[:n] if F.shape[2] == 40 else None
    inp = Ln.Inputs(P=P, earned=earned, cost_rate=np.full((n, M), cost * 1e-4),
                    borrow_rate=np.full((n, M), borrow * 1e-4 / ppy), ppy=ppy, d=d, blocks={"X": X})
    return inp, {"rows": n, "assets": M, "features": int(F.shape[2]), "delay": d, "cost_bps": cost,
                 "borrow_bps_yr": borrow, "P_used": P is not None}


def main(argv=None) -> int:
    from sancho import model
    ap = argparse.ArgumentParser(prog="quixote sancho", description="Run Sancho, the fixed model, on a panel.")
    ap.add_argument("--panel", required=True)
    ap.add_argument("--config", help="a Sancho config (default: the registered version-2 sancho/config.json)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    try:
        cfg = _config.load(a.config)
        inp, about = inputs_from_npz(a.panel)
    except (OSError, ValueError, KeyError) as e:
        print(f"quixote sancho: {e}", file=sys.stderr)
        return EXIT_USAGE
    if cfg.notice():
        print(cfg.notice())
    try:
        book, first, meta = model.run(inp, cfg)
    except RuntimeError as e:
        print(f"quixote sancho: {e}", file=sys.stderr)
        return EXIT_USAGE
    T = inp.earned.shape[0]
    rows = np.arange(first, T)
    if len(rows) < 2:
        print(f"quixote sancho: the panel is too short ({T} usable rows; the first scored row is {first})",
              file=sys.stderr)
        return EXIT_USAGE
    s = Vw.net_stream(book, inp, rows)
    sd = float(np.std(s, ddof=1))
    sharpe = float(np.mean(s) / sd * np.sqrt(inp.ppy)) if sd > 0 else 0.0
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rec = {"config_sha256": meta["config_sha256"], "is_default": meta["is_default"], "view": meta["view"],
           "panel": str(a.panel), "panel_about": about, "first_scored_row": int(first),
           "net_sharpe_in_sample": sharpe, "turnover": Vw.turnover_stats(book, inp, rows),
           "stream": [float(x) for x in s]}
    (out / "sancho.json").write_text(json.dumps(rec, indent=1))
    print(f"sancho: {len(rows)} scored rows from row {first}; in-sample net Sharpe {sharpe:+.3f}; "
          f"config {meta['config_sha256'][:12]} ({'default' if meta['is_default'] else 'NON-DEFAULT'}); "
          f"written {out / 'sancho.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
