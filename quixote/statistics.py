"""The fixed statistic library `pick` may reason with.

ROADMAP 7.2: "`stat` comes from a fixed, committed library (exploration Sharpe,
autocorrelation at named lags, volatility, correlation with the current best,
IC)." A `pick` names one of these, the harness computes it, and a replicate
recomputes the same thing — which is what makes a data-driven *reason* replayable
rather than testimony.

Every statistic here is a function of **base columns alone**, which is what the
`Replayable` contract requires: a bootstrap replicate has resampled columns and
no panel, so a statistic it cannot recompute cannot appear in a reason.

**IC is deliberately absent, and this is a deviation from the list above.** An
information coefficient is a correlation between a feature's cross-section and
next period's cross-section of returns; it needs the (T, M, K) panel, which a
replay does not have. Including it would mean a reason that cannot be
re-evaluated on a replicate — the exact failure this library exists to prevent.
If 7.2 wants IC, the replay contract has to carry the panel, and that is a
different design decision, recorded here rather than made quietly.
"""
from __future__ import annotations

import numpy as np


def _sharpe(stream: np.ndarray, annualization: float = 1.0, **_) -> float:
    from estimator.bootstrap import sharpe as _s
    return float(_s(np.asarray(stream)[:, None], axis=0, annualization=annualization)[0])


def _volatility(stream: np.ndarray, annualization: float = 1.0, **_) -> float:
    return float(np.std(stream, ddof=1) * annualization)


def _autocorr(stream: np.ndarray, lag: int) -> float:
    x = np.asarray(stream, dtype=float)
    if x.size <= lag + 1:
        return float("nan")
    a, b = x[lag:], x[:-lag]
    va, vb = a.std(ddof=1), b.std(ddof=1)
    if va <= 0 or vb <= 0:
        return float("nan")
    return float(((a - a.mean()) @ (b - b.mean())) / ((a.size - 1) * va * vb))


def _corr_with_best(stream: np.ndarray, best_stream=None, **_) -> float:
    """Correlation with the stream of the support held when the pick was made.
    Undefined before anything is held, which is a premise failure the `else`
    branch exists for."""
    if best_stream is None:
        return float("nan")
    x, y = np.asarray(stream, dtype=float), np.asarray(best_stream, dtype=float)
    if x.std(ddof=1) <= 0 or y.std(ddof=1) <= 0:
        return float("nan")
    return float(((x - x.mean()) @ (y - y.mean())) / ((x.size - 1) * x.std(ddof=1) * y.std(ddof=1)))


STATISTICS = {
    "sharpe": lambda stream, **kw: _sharpe(stream, **kw),
    "volatility": lambda stream, **kw: _volatility(stream, **kw),
    "autocorr_1": lambda stream, **kw: _autocorr(stream, 1),
    "autocorr_5": lambda stream, **kw: _autocorr(stream, 5),
    "corr_with_best": lambda stream, **kw: _corr_with_best(stream, **kw),
}

# A pick maximises its statistic unless the statistic is one where "better" means
# smaller. Recorded here so a reason cannot be read two ways.
MINIMISED = frozenset({"volatility", "corr_with_best"})


def evaluate(name: str, stream: np.ndarray, annualization: float = 1.0,
             best_stream=None) -> float:
    if name not in STATISTICS:
        raise ValueError(f"unknown statistic {name!r}; the library is {sorted(STATISTICS)}. "
                         "IC is deliberately absent: it needs the panel, which a replicate "
                         "does not have.")
    return float(STATISTICS[name](stream, annualization=annualization, best_stream=best_stream))


def better(name: str, a: float, b: float) -> bool:
    """Is `a` a better value of this statistic than `b`?"""
    if np.isnan(a):
        return False
    if np.isnan(b):
        return True
    return a < b if name in MINIMISED else a > b
