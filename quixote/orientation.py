"""The orientation table: the structure of the features, and nothing else.

An agent is handed this before its first `evaluate`. The question the arm asks is
whether an agent that knows the map searches better — shorter, fewer duplicates,
better priors — without the gate's false-certification rate moving.

**THE LINE, which is the whole design.** `T(X)` is a function of the feature
matrix `X` **alone**. Returns, prices, and anything derived from them never enter
it. `SCOPE.md`'s obliviousness condition asks that the candidate menu `C(ω)` be
"measurable with respect to some σ-field independent of the return-generating
randomness", and spells out what is allowed: "A trial count, subset sizes, and an
independently-seeded PRNG are allowed; realized Sharpe values feeding back into
which columns appear next are not." A menu chosen as a function of `T(X)` and the
agent's prior is measurable w.r.t. `σ(X, prior)`. The gate's nulls hold `X` fixed
and resample the return-driven part, so such a menu is fixed across replicates —
which is exactly the fixed-menu case White's theorem covers. Under `s0`, where
returns are independent of `X` by construction, it is oblivious unconditionally.

**Enforced, not asserted.** `orientation_table` takes `X` and nothing else: there
is no parameter through which a return could arrive.
`tests/test_orientation.py` passes a returns array as a **poisoned sentinel** that
raises on any access, and asserts the builder never touches it.

**Orientation consumes no evaluation budget and is not a trial.** It is delivered
in the prompt before the session opens; nothing is evaluated to produce it, and
it adds nothing to the transcript, the candidate count, or the breadth the null
is taken over.

**What the table holds**, registered exactly (`prereg/agent-cell.md`):

- pairwise feature correlations pooled over the panel, 2dp, delivered as the
  list of pairs with `|corr| >= 0.5` plus a note that every other pair is below
  it — which keeps the ETF panel's z/rank near-duplicates visible at a fraction
  of the tokens the full 780-pair matrix would cost;
- per-feature cross-sectional volatility, pooled, 2dp;
- per-feature autocorrelation at lags 1 and 5, 2dp;
- per-feature turnover of a unit position path, `mean |x_t - x_{t-1}|`, because
  costs are charged on turnover and turnover is an X-only quantity.

**Excluded by name**, and the exclusion is the point: feature means signed
against anything, a Sharpe of any kind, IC, correlation with returns, spread or
cost levels (price-derived), dates.

Labels are masked and the **feature order is shuffled by the masking seed**, so a
feature's position in the table carries nothing.
"""
from __future__ import annotations

import hashlib
import json

import numpy as np

CORR_THRESHOLD = 0.5
DP = 2

EXCLUDED_BY_NAME = (
    "feature means signed against anything", "Sharpe of any kind",
    "information coefficient", "correlation with returns",
    "spread or cost levels (price-derived)", "dates",
)


def _pooled(X: np.ndarray) -> np.ndarray:
    """(T, M, K) -> (T*M, K), every observation stacked."""
    X = np.asarray(X, dtype=float)
    if X.ndim != 3:
        raise ValueError(f"expected a (T, M, K) feature array, got shape {X.shape}")
    T, M, K = X.shape
    return X.reshape(T * M, K)


def _correlations(X: np.ndarray) -> np.ndarray:
    flat = _pooled(X)
    sd = flat.std(axis=0)
    live = sd > 0
    C = np.eye(flat.shape[1])
    if live.sum() >= 2:
        sub = np.corrcoef(flat[:, live], rowvar=False)
        idx = np.where(live)[0]
        C[np.ix_(idx, idx)] = np.nan_to_num(sub)
    return C


def _cross_sectional_vol(X: np.ndarray) -> np.ndarray:
    """Mean over periods of the cross-sectional sd. On a panel whose features are
    cross-sectionally z-scored this is 1.0 by construction for every feature; it
    is reported anyway, because a table that silently dropped a line where it
    happened to be uninformative would not be the same table on every panel."""
    X = np.asarray(X, dtype=float)
    return np.nanmean(np.nanstd(X, axis=1, ddof=0), axis=0)


def _autocorr(X: np.ndarray, lag: int) -> np.ndarray:
    """Per feature: the time-series autocorrelation within each name, averaged
    over names. X-only, and nothing about the order of names enters it."""
    X = np.asarray(X, dtype=float)
    T, M, K = X.shape
    if T <= lag + 1:
        return np.zeros(K)
    a, b = X[lag:], X[:-lag]
    am, bm = a.mean(axis=0), b.mean(axis=0)
    num = ((a - am) * (b - bm)).sum(axis=0)
    den = np.sqrt(((a - am) ** 2).sum(axis=0) * ((b - bm) ** 2).sum(axis=0))
    with np.errstate(invalid="ignore", divide="ignore"):
        per_name = np.where(den > 0, num / np.where(den > 0, den, 1.0), 0.0)
    return np.nanmean(per_name, axis=0)


def _turnover(X: np.ndarray) -> np.ndarray:
    """`mean |x_t - x_{t-1}|` of a unit position path, per feature, averaged over
    names. Costs are charged on turnover, and turnover is a property of X."""
    X = np.asarray(X, dtype=float)
    if X.shape[0] < 2:
        return np.zeros(X.shape[2])
    return np.nanmean(np.abs(np.diff(X, axis=0)), axis=(0, 1))


def orientation_table(X: np.ndarray, labels=None, seed: int | None = None) -> dict:
    """The orientation table for a feature panel.

    **X only.** There is no parameter through which a return, a price or a date
    could arrive, which is the enforcement of this module's whole argument.

    `labels` are the masked feature labels; `seed` shuffles the delivered order so
    that a feature's position carries nothing. Both default to a plain ordering
    for tests that do not care.
    """
    X = np.asarray(X, dtype=float)
    K = X.shape[2]
    labels = list(labels) if labels is not None else [f"F{i:02d}" for i in range(K)]
    if len(labels) != K:
        raise ValueError(f"{len(labels)} labels for {K} features")

    order = (np.random.default_rng(seed).permutation(K) if seed is not None
             else np.arange(K))
    C = _correlations(X)
    vol, ac1, ac5, turn = (_cross_sectional_vol(X), _autocorr(X, 1),
                           _autocorr(X, 5), _turnover(X))

    pairs = []
    for i in range(K):
        for j in range(i + 1, K):
            if abs(C[i, j]) >= CORR_THRESHOLD:
                pi, pj = int(np.where(order == i)[0][0]), int(np.where(order == j)[0][0])
                a, b = sorted([labels[pi], labels[pj]])
                pairs.append({"pair": [a, b], "corr": round(float(C[i, j]), DP)})
    pairs.sort(key=lambda p: (-abs(p["corr"]), p["pair"]))

    per_feature = []
    for pos, k in enumerate(order):
        per_feature.append({
            "label": labels[pos],
            "volatility": round(float(vol[k]), DP),
            "autocorr_1": round(float(ac1[k]), DP),
            "autocorr_5": round(float(ac5[k]), DP),
            "turnover": round(float(turn[k]), DP),
        })

    return {
        "n_features": K,
        "correlated_pairs": pairs,
        "correlation_threshold": CORR_THRESHOLD,
        "all_other_pairs_below_threshold": True,
        "per_feature": per_feature,
        "excluded_by_name": list(EXCLUDED_BY_NAME),
    }


def table_hash(table: dict) -> str:
    """The delivered table's hash, recorded per run in the run config."""
    return hashlib.sha256(
        json.dumps(table, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:16]


def render(table: dict) -> str:
    """The table as the agent receives it. Compact on purpose: the pair list plus
    one line per feature, rather than a K x K matrix."""
    L = [f"{table['n_features']} features."]
    pairs = table["correlated_pairs"]
    if pairs:
        L.append(f"Feature pairs with |correlation| >= {table['correlation_threshold']}:")
        L += [f"  {p['pair'][0]} and {p['pair'][1]}: {p['corr']:+.2f}" for p in pairs]
        L.append("Every other pair is below that threshold.")
    else:
        L.append(f"No pair of features has |correlation| >= "
                 f"{table['correlation_threshold']}; every pair is below it.")
    L.append("Per feature — volatility, autocorrelation at lags 1 and 5, turnover:")
    for r in table["per_feature"]:
        L.append(f"  {r['label']}: vol {r['volatility']:.2f}, ac1 {r['autocorr_1']:+.2f}, "
                 f"ac5 {r['autocorr_5']:+.2f}, turnover {r['turnover']:.2f}")
    return "\n".join(L)
