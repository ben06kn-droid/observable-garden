"""The panel format a user brings: one `.npz` file.

Arrays (T rows, M assets, K features):

- `returns` (T, M): simple returns. NaN means the asset cannot be traded in that row.
- `features` (T, M, K): what a rule may look at in row t. Must use data up to row t only.
- `feature_names` (K,): one name per feature.
- `periods_per_year`: a scalar (252 for daily rows).
- optional `delay` (default 1): features at row t earn `returns[t + 1 + delay]`.
  With delay 1 a signal formed at the close of row t is traded at the close of t+1 and held
  to the close of t+2; delay 0 trades at the close of t itself (usually not implementable).
- optional `cost_bps` (default 5): one-way cost per unit of turnover, in basis points.
- optional `borrow_bps_yr` (default 50): borrow cost on short weight, basis points a year.
- optional `row_labels` (T,): dates or indices, used by `split`.
- optional `asset_names` (M,).

`load(path)` validates the file and returns the engine's panel object (a `RealPanel`) that
the sandbox and the harness read. A book is dollar-neutral at gross 1 over the tradable assets,
as in every registered panel.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

REQUIRED = ("returns", "features", "feature_names", "periods_per_year")


class PanelError(ValueError):
    """A panel file that does not follow the format."""


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path) -> dict:
    """The raw arrays, validated, as a dict (no engine object)."""
    path = Path(path)
    if not path.exists():
        raise PanelError(f"no panel file at {path}")
    with np.load(path, allow_pickle=False) as z:
        d = {k: z[k] for k in z.files}
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise PanelError(f"{path.name} lacks {missing}; a panel needs {list(REQUIRED)}")
    R = np.asarray(d["returns"], float)
    X = np.asarray(d["features"], float)
    if R.ndim != 2 or X.ndim != 3 or X.shape[:2] != R.shape:
        raise PanelError(f"returns must be (T, M) and features (T, M, K); got {R.shape} and {X.shape}")
    K = X.shape[2]
    names = [str(s) for s in np.asarray(d["feature_names"]).reshape(-1)]
    if len(names) != K:
        raise PanelError(f"{len(names)} feature_names for {K} features")
    delay = int(d.get("delay", 1))
    if delay < 0:
        raise PanelError("delay must be >= 0")
    if R.shape[0] < 3 + delay:
        raise PanelError("too few rows")
    out = {"returns": R, "features": X, "feature_names": names,
           "periods_per_year": float(d["periods_per_year"]), "delay": delay,
           "cost_bps": float(d.get("cost_bps", 5.0)), "borrow_bps_yr": float(d.get("borrow_bps_yr", 50.0))}
    T, M = R.shape
    out["row_labels"] = ([str(s) for s in np.asarray(d["row_labels"]).reshape(-1)]
                         if "row_labels" in d else [str(i) for i in range(T)])
    out["asset_names"] = ([str(s) for s in np.asarray(d["asset_names"]).reshape(-1)]
                          if "asset_names" in d else [f"a{j}" for j in range(M)])
    if len(out["row_labels"]) != T or len(out["asset_names"]) != M:
        raise PanelError("row_labels must have T entries and asset_names M entries")
    return out


def to_engine(d: dict, features: list[int] | None = None, name: str = "user-panel"):
    """The engine's `RealPanel`: the features of row t paired with the return they earn,
    `returns[t + 1 + delay]`. `features` keeps only those feature columns (a class over a subset
    of the panel's features)."""
    from environments.real_panel import RealPanel
    R, X = d["returns"], d["features"]
    names = list(d["feature_names"])
    if features is not None:
        X = X[:, :, features]
        names = [names[k] for k in features]
    lag = 1 + d["delay"]
    T, M = R.shape
    earned = R[lag:]                                   # what a weight formed at row t earns
    Xk = np.nan_to_num(X[:T - lag])
    tradable = np.isfinite(earned)
    ppy = d["periods_per_year"]
    keep = slice(0, T - lag)
    return RealPanel(
        name=name, assets=list(d["asset_names"]), feature_names=names, features=Xk,
        returns=np.nan_to_num(earned), tradable=tradable, periods_per_year=ppy,
        cost_rate=np.full((T - lag, M), d["cost_bps"] * 1e-4),
        borrow_rate=np.full((T - lag, M), d["borrow_bps_yr"] * 1e-4 / ppy),
        session_start=np.zeros(T - lag, bool), session_end=np.zeros(T - lag, bool),
        flat_overnight=False,
        meta={"row_labels": d["row_labels"][keep], "earned_labels": d["row_labels"][lag:],
              "delay": d["delay"]})


def load(path, features: list[int] | None = None):
    """Validate the file and return the engine panel (`RealPanel`)."""
    return to_engine(read(path), features=features, name=Path(path).stem)


def save(path, returns, features, feature_names, periods_per_year, *, delay=1, cost_bps=5.0,
         borrow_bps_yr=50.0, row_labels=None, asset_names=None) -> str:
    """Write a panel file; returns its SHA-256."""
    arrays = {"returns": np.asarray(returns, float), "features": np.asarray(features, float),
              "feature_names": np.asarray([str(s) for s in feature_names]),
              "periods_per_year": np.asarray(float(periods_per_year)), "delay": np.asarray(int(delay)),
              "cost_bps": np.asarray(float(cost_bps)), "borrow_bps_yr": np.asarray(float(borrow_bps_yr))}
    if row_labels is not None:
        arrays["row_labels"] = np.asarray([str(s) for s in row_labels])
    if asset_names is not None:
        arrays["asset_names"] = np.asarray([str(s) for s in asset_names])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, **arrays)
    read(path)                                          # it must load
    return sha256(path)


def tiny(seed: int = 7, T: int = 600, M: int = 12) -> dict:
    """A small synthetic daily panel: a common factor, idiosyncratic noise, and eight
    features (momentum, reversal and volatility in z and rank form), with a weak edge
    planted in one of them. Returns the arrays `save` takes."""
    rng = np.random.default_rng(seed)
    f = 0.008 * rng.standard_normal(T)
    eps = 0.012 * rng.standard_normal((T, M))
    R = f[:, None] + eps
    # cumulative log price, and simple trailing statistics
    lp = np.cumsum(np.log1p(R), axis=0)

    def trail(x, n):
        out = np.full_like(x, np.nan)
        out[n:] = x[n:] - x[:-n]
        return out

    mom = trail(lp, 60)
    rev = -trail(lp, 5)
    vol = np.full_like(R, np.nan)
    for t in range(20, T):
        vol[t] = R[t - 20:t].std(axis=0)

    def z(x):
        with np.errstate(all="ignore"), __import__("warnings").catch_warnings():
            __import__("warnings").simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(x, axis=1, keepdims=True)
            s = np.nanstd(x, axis=1, keepdims=True)
        return np.where(s > 0, (x - m) / np.where(s > 0, s, 1.0), 0.0)

    def rank(x):
        out = np.zeros_like(x)
        for t in range(x.shape[0]):
            row = x[t]
            ok = np.isfinite(row)
            if ok.sum() > 1:
                r = np.argsort(np.argsort(row[ok]))
                out[t, ok] = r / (ok.sum() - 1) - 0.5
        return out

    raw = {"mom60": mom, "rev5": rev, "vol20": vol, "noise": rng.standard_normal((T, M))}
    feats, names = [], []
    for nm, x in raw.items():
        feats += [z(x), rank(x)]
        names += [f"{nm}_z", f"{nm}_rank"]
    F = np.nan_to_num(np.stack(feats, axis=2))
    # plant a weak edge: row t's rev5 rank tilts the return two rows later
    R[2:] += 0.0012 * F[:-2, :, names.index("rev5_rank")]
    labels = [f"t{t:04d}" for t in range(T)]
    return {"returns": R, "features": F, "feature_names": names, "periods_per_year": 252,
            "delay": 1, "row_labels": labels, "asset_names": [f"A{j:02d}" for j in range(M)]}
