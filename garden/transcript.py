"""The transcript format the gate reads: every evaluated specification's
return stream on a common time index, which one was submitted, and whether
the menu of specifications was fixed before any results were seen."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from environments.sandbox import Sandbox

MENU_KINDS = ("oblivious", "adaptive", "unknown")


class TranscriptError(ValueError):
    pass


@dataclass
class Transcript:
    returns: np.ndarray          # (T, N), one column per evaluated specification
    spec_ids: np.ndarray         # (N,) str
    submitted: str
    menu_kind: str = "unknown"
    periods_per_year: int = 252

    def __post_init__(self):
        self.returns = np.asarray(self.returns, dtype=float)
        if self.returns.ndim != 2:
            raise TranscriptError(f"returns must be a (T, N) matrix, got shape {self.returns.shape}")
        T, N = self.returns.shape
        if N == 0 or T < 3:
            raise TranscriptError(f"need at least one specification and three periods, got T={T}, N={N}")
        if not np.isfinite(self.returns).all():
            raise TranscriptError(
                "returns contain NaN or inf. Every specification must be evaluated on the same periods, "
                "because the bootstrap resamples one shared time index; streams of unequal length or on "
                "different subsamples are rejected rather than silently aligned (see OPEN_QUESTIONS.md)."
            )
        self.spec_ids = np.asarray(self.spec_ids).astype(str)
        if self.spec_ids.shape != (N,):
            raise TranscriptError(f"expected {N} spec_ids, one per column, got shape {self.spec_ids.shape}")
        if len(set(self.spec_ids.tolist())) != N:
            raise TranscriptError("spec_ids must be unique")
        self.submitted = str(self.submitted)
        if self.submitted not in self.spec_ids:
            raise TranscriptError(f"submitted spec {self.submitted!r} is not among the transcript's spec_ids")
        if self.menu_kind not in MENU_KINDS:
            raise TranscriptError(f"menu_kind must be one of {MENU_KINDS}, got {self.menu_kind!r}")
        self.periods_per_year = int(self.periods_per_year)
        if self.periods_per_year < 1:
            raise TranscriptError("periods_per_year must be positive")

    @property
    def n_periods(self) -> int:
        return self.returns.shape[0]

    @property
    def n_specs(self) -> int:
        return self.returns.shape[1]

    @property
    def submitted_index(self) -> int:
        return int(np.flatnonzero(self.spec_ids == self.submitted)[0])

    def save(self, path) -> None:
        np.savez_compressed(
            path, returns=self.returns, spec_ids=self.spec_ids, submitted=np.array(self.submitted),
            menu_kind=np.array(self.menu_kind), periods_per_year=np.array(self.periods_per_year),
        )


def from_matrix(R, submitted_index: int, spec_ids=None, menu_kind: str = "unknown",
                periods_per_year: int = 252) -> Transcript:
    R = np.asarray(R, dtype=float)
    n = R.shape[1] if R.ndim == 2 else 0
    ids = np.asarray(spec_ids if spec_ids is not None else [f"spec_{i}" for i in range(n)]).astype(str)
    if not 0 <= submitted_index < len(ids):
        raise TranscriptError(f"submitted_index {submitted_index} is out of range for {len(ids)} specifications")
    return Transcript(R, ids, ids[submitted_index], menu_kind, periods_per_year)


def load_npz(path) -> Transcript:
    with np.load(path, allow_pickle=False) as z:
        missing = {"returns", "spec_ids", "submitted"} - set(z.files)
        if missing:
            raise TranscriptError(f"{path} is missing required field(s): {', '.join(sorted(missing))}")
        return Transcript(
            returns=z["returns"],
            spec_ids=z["spec_ids"],
            submitted=z["submitted"].item(),
            menu_kind=z["menu_kind"].item() if "menu_kind" in z.files else "unknown",
            periods_per_year=z["periods_per_year"].item() if "periods_per_year" in z.files else 252,
        )


def load_csv(path, submitted: str, menu_kind: str = "unknown", periods_per_year: int = 252) -> Transcript:
    """Wide CSV: the first column labels periods, every other column is one specification."""
    df = pd.read_csv(path, index_col=0)
    try:
        R = df.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except ValueError as exc:
        raise TranscriptError(f"{path}: non-numeric return values ({exc})") from exc
    return Transcript(R, df.columns.astype(str).to_numpy(), submitted, menu_kind, periods_per_year)


def from_sandbox(sandbox: Sandbox, menu_kind: str = "unknown") -> Transcript:
    if sandbox.submission is None:
        raise TranscriptError("the sandbox has no submission")
    spec, _ = sandbox.submission
    log = sandbox.transcript
    matches = [e.call_index for e in log if np.array_equal(e.spec.weights, spec.weights)]
    if not matches:
        raise TranscriptError("the submitted specification was never evaluated, so it is not in the transcript")
    ids = [f"{e.call_index}:{e.spec.name}" if e.spec.name else str(e.call_index) for e in log]
    return Transcript(sandbox.returns_matrix(), ids, ids[matches[0]], menu_kind, sandbox.periods_per_year)
