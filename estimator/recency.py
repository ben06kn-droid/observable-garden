"""The recency-weighted certificate (`prereg/recency-weight-exploratory-2026-10-09.md`,
sections a-f, with amendment 1 at 190d75e). Behind a flag: with `h=None` every function
here calls the current, unweighted code unchanged, so the registered reads are untouched.
`learn/stream_tier.py` (a pinned blob) is not modified.

- weights w_t = 2^(-(T - t)/h) over the scored rows, the last row weighted 1;
- the weighted Sharpe: weighted mean over the reliability-weighted sd, annualised;
- the null: each stream centred by its UNWEIGHTED mean (amendment 1), stationary-bootstrap
  index sets as now, weights attached to POSITION; p = (1 + #{S_b >= S}) / (B + 1);
  the as-written centring (the weighted mean) is kept beside, only to measure its size,
  labelled "superseded";
- the class maximum, the same construction with all members resampled jointly, carried by
  weighted counts W[s, b] = sum of w_t over the positions t that drew row s;
- L90 from `quixote.confidence` on the weighted statistic and the weighted null;
- the performance line: the UNWEIGHTED net Sharpe over the last k scored rows, with a
  bootstrap 90% interval; descriptive, it never gates.
"""
from __future__ import annotations

import numpy as np

CENTRINGS = ("unweighted", "weighted_superseded")
DAILY_H, FOURH_H = 1260, 10950
PERF_ROWS = {252.0: (252, 756), 2190.0: (2190, 6570)}


def weights(n: int, h: float | None) -> np.ndarray:
    """w_t = 2^(-(n - 1 - t)/h), t = 0..n-1; all ones when h is None."""
    if h is None:
        return np.ones(n)
    return np.power(2.0, -(n - 1 - np.arange(n, dtype=float)) / float(h))


def weighted_sharpe(x: np.ndarray, w: np.ndarray, ppy: float) -> float:
    x = np.asarray(x, float)
    V1, V2 = w.sum(), (w * w).sum()
    m = float((w * x).sum() / V1)
    var = float((w * (x - m) ** 2).sum() / (V1 - V2 / V1))
    return m / np.sqrt(var) * np.sqrt(ppy) if var > 0 else 0.0


def _centre(x: np.ndarray, w: np.ndarray, centring: str) -> np.ndarray:
    if centring not in CENTRINGS:
        raise ValueError(f"centring {centring!r} not in {CENTRINGS}")
    c = x.mean() if centring == "unweighted" else (w * x).sum() / w.sum()
    return x - c


def stream_test(stream: np.ndarray, L: int, ppy: float, B: int, seed: int,
                h: float | None = None, centring: str = "unweighted") -> dict:
    """The supplied-streams tier at a given block length. h None: the current computation,
    unchanged (`experiments.binance_insample_read.stream_test`). Otherwise the weighted
    statistic and null of the note. h = inf gives equal weights through the weighted code."""
    from estimator.bootstrap import stationary_bootstrap_indices
    from quixote.confidence import confidence
    if h is None:                         # the current computation, call for call
        from learn import stream_tier
        table = stream_tier.table_from_streams(np.asarray(stream, float)[None, :], ppy)
        rng = np.random.default_rng(seed)
        rows = [stationary_bootstrap_indices(len(stream), L, rng) for _ in range(B)]
        M_b = np.asarray(table.null_max(rows), float)
        S = float(table.sharpe(((0, 1.0),)))
        p = (1 + int(np.sum(M_b >= S))) / (B + 1)
        return {"S": S, "p": p, "null_max": M_b, "block_length": int(L), "h": None, "centring": "unweighted",
                "confidence": confidence(S, M_b, ppy=float(ppy), tier="declared stream")}
    x = np.asarray(stream, float)
    n = len(x)
    w = weights(n, h)
    S = weighted_sharpe(x, w, ppy)
    x0 = _centre(x, w, centring)
    rng = np.random.default_rng(seed)
    M_b = np.array([weighted_sharpe(x0[stationary_bootstrap_indices(n, L, rng)], w, ppy) for _ in range(B)])
    p = (1 + int(np.sum(M_b >= S))) / (B + 1)
    return {"S": S, "p": p, "null_max": M_b, "block_length": int(L), "h": float(h), "centring": centring,
            "n_eff": float(w.sum() ** 2 / (w * w).sum()),
            "confidence": confidence(S, M_b, ppy=float(ppy), tier="declared stream, recency-weighted")}


def weighted_counts(idx_list, w: np.ndarray) -> np.ndarray:
    """(T, B): W[s, b] = the sum of w_t over the positions t whose draw in replicate b is s."""
    T = len(w)
    W = np.empty((T, len(idx_list)))
    for b, idx in enumerate(idx_list):
        W[:, b] = np.bincount(idx, weights=w, minlength=T)
    return W


def class_null(X_chunks, T: int, L: int, ppy: float, B: int, seed: int, h: float | None,
               centring: str = "unweighted") -> tuple[np.ndarray, np.ndarray]:
    """(observed weighted Sharpe of every member, replicate maxima) for streams given as an
    iterable of (n, T) chunks, all resampled jointly with the same index sets."""
    from estimator.bootstrap import stationary_bootstrap_indices
    w = weights(T, h)
    V1, V2 = w.sum(), (w * w).sum()
    rng = np.random.default_rng(seed)
    W = weighted_counts([stationary_bootstrap_indices(T, L, rng) for _ in range(B)], w)
    ann = np.sqrt(ppy)
    obs, M_b = [], np.full(B, -np.inf)
    for X in X_chunks:
        X = np.asarray(X, float)
        m_obs = (X @ w) / V1
        v_obs = ((X - m_obs[:, None]) ** 2 @ w) / (V1 - V2 / V1)
        obs.append(np.where(v_obs > 0, m_obs / np.sqrt(np.where(v_obs > 0, v_obs, 1.0)), 0.0) * ann)
        c = X.mean(axis=1, keepdims=True) if centring == "unweighted" else m_obs[:, None]
        X0 = X - c
        mean = (X0 @ W) / V1
        var = ((X0 * X0) @ W - V1 * mean * mean) / (V1 - V2 / V1)
        pos = var > 0
        rep = np.where(pos, mean / np.sqrt(np.where(pos, var, 1.0)), 0.0) * ann
        M_b = np.maximum(M_b, rep.max(axis=0))
    return np.concatenate(obs), M_b


def price_class(panel, cache, bc: np.ndarray, seed: int, B: int, alpha: float, feature_names,
                h: float | None = None, centring: str = "unweighted") -> dict:
    """The class maximum. h None: `experiments.french_insample_read.price_class`, unchanged.
    Otherwise the weighted construction on the fast kernel's streams."""
    from experiments import french_insample_read as FR
    if h is None:
        r = FR.price_class(panel, cache, bc, seed, B, alpha, feature_names)
        r.update({"h": None, "centring": "unweighted"})
        return r
    import environments.planted_fast as pf
    from environments.class_table import CHUNK
    from estimator.bootstrap import select_block_length
    from quixote.confidence import confidence
    T = panel.features.shape[0]
    L = int(select_block_length(bc - bc.mean(axis=0)))
    F = pf.feature_returns(panel)
    chunks = (pf.streams(cache, F, s0, min(s0 + CHUNK, cache.N)) for s0 in range(0, cache.N, CHUNK))
    obs, M_b = class_null(chunks, T, L, panel.periods_per_year, B, seed, h, centring)
    j = int(np.argmax(obs))
    S = float(obs[j])
    p = (1 + int(np.sum(M_b >= S))) / (B + 1)
    conf = confidence(S, M_b, ppy=float(panel.periods_per_year), tier="class, recency-weighted")
    member = cache.members[j]
    w = weights(T, h)
    return {"test": "class maximum, recency-weighted", "alpha": alpha, "n_rows": T, "N": cache.N, "B": B,
            "seed": seed, "block_length": L, "h": float(h), "centring": centring,
            "n_eff": float(w.sum() ** 2 / (w * w).sum()), "S": S, "p": p, "certified": bool(p < alpha),
            "L90": conf["L"]["0.90"], "confidence": conf,
            "best_member": {"index": j, "support": [[int(k), float(sg)] for k, sg in member],
                            "features": [f"{'+' if sg > 0 else '-'}{feature_names[int(k)]}" for k, sg in member]}}


def levels(p_stream: float, p_class: float) -> dict:
    """Both registered levels from the same p-values (section d)."""
    return {"96% level": {"stream": p_stream < 0.04, "class": p_class < 0.01},
            "90% level": {"stream": p_stream < 0.08, "class": p_class < 0.02}}


def performance_line(stream: np.ndarray, ppy: float, L: int, B: int, seed: int, rows=None) -> dict:
    """The UNWEIGHTED net Sharpe over the last k scored rows, with the 5% and 95% points
    over stationary-bootstrap resamples of those rows. Descriptive; never gates."""
    from estimator.bootstrap import stationary_bootstrap_indices
    rows = rows or PERF_ROWS.get(float(ppy), (252, 756))
    x = np.asarray(stream, float)
    ann = np.sqrt(ppy)
    sh = lambda y: float(y.mean() / y.std(ddof=1) * ann) if y.std(ddof=1) > 0 else 0.0
    out = {}
    rng = np.random.default_rng(seed)
    for k in rows:
        y = x[-k:]
        reps = np.array([sh(y[stationary_bootstrap_indices(len(y), L, rng)]) for _ in range(B)])
        lo, hi = np.quantile(reps, [0.05, 0.95])
        out[str(k)] = {"rows": int(len(y)), "S": sh(y), "ci90": [float(lo), float(hi)]}
    return {"label": "performance line, descriptive (unweighted; never gates)", "B": B, "seed": seed,
            "block_length": int(L), "lines": out}
