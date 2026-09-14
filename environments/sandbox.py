"""The Sandbox contract: the same interface a scripted searcher (Phase 1) and
an LLM agent (Phase 2) both run against. Every evaluated specification's full
in-sample return stream is logged whether or not the searcher uses it — that
transcript is the R (T x N) matrix the bootstrap estimator consumes later.

Out-of-sample data is never exposed through this interface. `oos_sharpe_
for_grading` exists only for the harness to score a submission after the
fact; a searcher never calls it.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from environments.dgp import DGPData


@dataclass
class Specification:
    """A linear-in-features trading rule: signal[i, t] = weights . x[i, t, :].
    Zero weight on a feature means "not used". This is deliberately general —
    a GridSearch searcher's (subset, lookback, threshold) rule and a Greedy
    searcher's single-feature rule both compile down to a weight vector."""
    weights: np.ndarray   # (K,)
    name: str = ""

    def __post_init__(self):
        self.weights = np.asarray(self.weights, dtype=float)


@dataclass
class Distribution:
    """A predictive distribution over out-of-sample Sharpe. Gaussian by default
    (mean, std); `samples` lets a searcher instead hand back an empirical
    distribution (e.g. from its own bootstrap)."""
    mean: float
    std: float | None = None
    samples: np.ndarray | None = None

    @staticmethod
    def degenerate(value: float) -> "Distribution":
        """A point estimate with ~zero stated uncertainty — what a naive
        (undiscounted) searcher reports: it believes its in-sample number."""
        return Distribution(mean=value, std=1e-6)


@dataclass
class EvalResult:
    """What `evaluate` hands back to the searcher: in-sample Sharpe and summary
    stats only. The full return stream is logged but never returned here."""
    sharpe: float
    mean: float
    std: float
    n_periods: int
    call_index: int


@dataclass
class LogEntry:
    call_index: int
    spec: Specification
    return_stream: np.ndarray   # (T,) — full in-sample stream, always logged
    sharpe: float
    timestamp: float


class Sandbox:
    def __init__(self, data: DGPData, periods_per_year: int = 252):
        self._data = data
        self.periods_per_year = periods_per_year
        self._log: list[LogEntry] = []
        self._submission: tuple[Specification, Distribution] | None = None

    # -- searcher-visible API -------------------------------------------------

    def get_data(self) -> pd.DataFrame:
        """In-sample features + realized returns only, long format (t, asset)."""
        T, M, K = self._data.x_in.shape
        df = pd.DataFrame(
            self._data.x_in.reshape(T * M, K),
            columns=[f"f{k}" for k in range(K)],
        )
        df.insert(0, "asset", np.tile(np.arange(M), T))
        df.insert(0, "t", np.repeat(np.arange(T), M))
        df["r"] = self._data.r_in.reshape(T * M)
        return df

    def evaluate(self, spec: Specification) -> EvalResult:
        """Every call is logged with its full return stream, regardless of
        whether the searcher goes on to use the result. OOS data is never
        touched here."""
        signal = self._data.x_in @ spec.weights          # (T, M)
        R = (signal * self._data.r_in).mean(axis=1)       # (T,) portfolio return stream
        mean, std = float(R.mean()), float(R.std(ddof=1))
        sharpe = mean / std * np.sqrt(self.periods_per_year) if std > 0 else 0.0

        call_index = len(self._log)
        self._log.append(LogEntry(
            call_index=call_index, spec=spec, return_stream=R,
            sharpe=sharpe, timestamp=time.time(),
        ))
        return EvalResult(sharpe=sharpe, mean=mean, std=std, n_periods=len(R), call_index=call_index)

    def submit(self, spec: Specification, predicted_oos_sharpe: Distribution) -> None:
        if not isinstance(predicted_oos_sharpe, Distribution):
            raise TypeError("submit() requires a Distribution over out-of-sample Sharpe")
        self._submission = (spec, predicted_oos_sharpe)

    # -- problem-setup metadata (dimensions only, not a leak) ----------------

    @property
    def num_features(self) -> int:
        return self._data.x_in.shape[2]

    @property
    def num_periods(self) -> int:
        return self._data.x_in.shape[0]

    @property
    def num_assets(self) -> int:
        return self._data.x_in.shape[1]

    # -- harness-only, not part of the searcher-visible contract -------------

    @property
    def transcript(self) -> list[LogEntry]:
        return list(self._log)

    @property
    def submission(self) -> tuple[Specification, Distribution] | None:
        return self._submission

    def returns_matrix(self) -> np.ndarray:
        """(T, N) — one column per evaluate() call, in call order. This is the
        R matrix the bootstrap estimator takes as input."""
        if not self._log:
            return np.empty((self._data.r_in.shape[0], 0))
        return np.stack([entry.return_stream for entry in self._log], axis=1)

    def oos_sharpe_for_grading(self, spec: Specification) -> float:
        """Harness-only: the true out-of-sample Sharpe of a specification,
        computed from held-out data a searcher never sees through this class."""
        signal = self._data.x_oos @ spec.weights
        R = (signal * self._data.r_oos).mean(axis=1)
        std = float(R.std(ddof=1))
        if std == 0:
            return 0.0
        return float(R.mean() / std * np.sqrt(self.periods_per_year))
