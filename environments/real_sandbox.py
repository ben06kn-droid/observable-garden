"""The real-data sandbox: the synthetic contract, over a registered real panel.

Same contract as `environments.sandbox.Sandbox`, and the same guarantees:

- `evaluate` never touches out-of-sample data, and **this class has no
  out-of-sample data to touch**. The synthetic sandbox holds `x_oos`/`r_oos` and
  exposes `oos_sharpe_for_grading` for the harness; this one holds a panel that
  ends where the in-sample period ends. Grading lives in
  `experiments/grade_real.py`, a separate entry point that this module does not
  import and cannot reach.
- every `evaluate` call is logged with its **full return stream**, whether or not
  the searcher uses the result;
- `submit` takes a `Distribution` over the out-of-sample Sharpe, not a number.

The stream a specification earns is **net of the panel's registered costs**, so
`evaluate` answers the question the null asks (ROADMAP 7.4: the class is priced
as an explicit class of net streams). Because costs are not linear in the
weights, `base_feature_columns` is a diagnostic basis, not one the class is
linear in, and it says so.
"""
from __future__ import annotations

import time

import numpy as np

from environments.real_panel import RealPanel
from environments.sandbox import Distribution, EvalResult, LogEntry, Specification


class RealSandbox:
    """`panel` is in-sample only. There is no out-of-sample attribute."""

    def __init__(self, panel: RealPanel, spec_class=None):
        self.panel = panel
        self.periods_per_year = panel.periods_per_year
        self.spec_class = spec_class
        self._log: list[LogEntry] = []
        self._submission: tuple[Specification, Distribution] | None = None

    # -- searcher-visible API ------------------------------------------------

    def get_data(self):
        """In-sample features and realized returns, long format (t, asset)."""
        import pandas as pd
        T, M, K = self.panel.features.shape
        df = pd.DataFrame(self.panel.features.reshape(T * M, K),
                          columns=self.panel.feature_names)
        df.insert(0, "asset", np.tile(np.array(self.panel.assets), T))
        df.insert(0, "t", np.repeat(np.arange(T), M))
        df["r"] = self.panel.returns.reshape(T * M)
        df["tradable"] = self.panel.tradable.reshape(T * M)
        return df

    def evaluate(self, spec: Specification) -> EvalResult:
        """The specification's net-of-cost stream. Logged in full, every time."""
        if self.spec_class is not None and not self.spec_class.contains(spec.weights):
            raise ValueError(f"specification {spec.name!r} is outside the declared class "
                             f"{self.spec_class.name}")
        R = self.panel.stream_for_scores(self.panel.scores_for_weights(spec.weights))
        mean, std = float(R.mean()), float(R.std(ddof=1))
        sharpe = mean / std * np.sqrt(self.periods_per_year) if std > 0 else 0.0
        call_index = len(self._log)
        self._log.append(LogEntry(call_index=call_index, spec=spec, return_stream=R,
                                  sharpe=sharpe, timestamp=time.time()))
        return EvalResult(sharpe=sharpe, mean=mean, std=std, n_periods=len(R),
                          call_index=call_index)

    def submit(self, spec: Specification, predicted_oos_sharpe: Distribution) -> None:
        if not isinstance(predicted_oos_sharpe, Distribution):
            raise TypeError("submit() requires a Distribution over out-of-sample Sharpe")
        self._submission = (spec, predicted_oos_sharpe)

    # -- problem-setup metadata (dimensions only) ---------------------------

    @property
    def num_features(self) -> int:
        return self.panel.features.shape[2]

    @property
    def num_periods(self) -> int:
        return self.panel.features.shape[0]

    @property
    def num_assets(self) -> int:
        return self.panel.features.shape[1]

    # -- harness-only --------------------------------------------------------

    @property
    def transcript(self) -> list[LogEntry]:
        return list(self._log)

    @property
    def submission(self) -> tuple[Specification, Distribution] | None:
        return self._submission

    def returns_matrix(self) -> np.ndarray:
        if not self._log:
            return np.empty((self.num_periods, 0))
        return np.stack([e.return_stream for e in self._log], axis=1)

    def base_feature_columns(self) -> np.ndarray:
        """(T, K): each feature's own net-of-cost stream, computed without
        touching the transcript.

        **Not a basis the class is linear in.** Turnover is a function of the
        combined weights, so a two-feature specification's costs are not the sum
        of its members'. These columns are for diagnostics and preflight; the
        class is priced as an explicit class of net streams.
        """
        K = self.num_features
        out = np.empty((self.num_periods, K))
        for k in range(K):
            w = np.zeros(K)
            w[k] = 1.0
            out[:, k] = self.panel.stream_for_scores(self.panel.scores_for_weights(w))
        return out
