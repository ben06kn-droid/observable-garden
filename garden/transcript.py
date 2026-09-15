"""The transcript format the gate reads.

Version 1: every evaluated specification's return stream on a common time index (`returns`, one column
per specification), which one was submitted, whether the menu was fixed before any result was seen
(`menu_kind`), and periods per year.

Version 2 adds optional fields. They let the gate test an adaptive search against the whole class of
specifications it could have produced (THEORY.md, P3), and let an audit read the order of the search:

- `base_returns` (T, K): the return stream of every feature the search could have used, not only the
  ones it touched. If a usable feature is missing, the enumerated class is too small and the test is
  invalid. `from_sandbox` fills this from the sandbox; for a user-supplied file it is an attestation,
  like `menu_kind`.
- `spec_members` (N, K): each logged specification's weights on the base columns. The logged returns
  must equal `base_returns @ spec_members.T` to within RECONSTRUCTION_RTOL times the largest absolute
  logged return.
- `eval_order` (N,): the order in which the specifications were evaluated, a permutation of 0..N-1.
- `spec_class`: the declared class (garden.spec_class), "none" by default. Every row of `spec_members`,
  and in particular the submitted specification, must lie in it.
- `spec_class_source`: "sandbox" when the class came from a sandbox that enforced it during the search,
  so it was fixed in advance by construction; "attested" when it is only the supplier's claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from garden.spec_class import SubsetClass
from garden.spec_class import parse as parse_class

if TYPE_CHECKING:
    from environments.sandbox import Sandbox

MENU_KINDS = ("oblivious", "adaptive", "unknown")
CLASS_SOURCES = ("sandbox", "attested")
FORMAT_VERSION = 2
RECONSTRUCTION_RTOL = 1e-8


class TranscriptError(ValueError):
    pass


@dataclass
class Transcript:
    returns: np.ndarray          # (T, N), one column per evaluated specification
    spec_ids: np.ndarray         # (N,) str
    submitted: str
    menu_kind: str = "unknown"
    periods_per_year: int = 252
    base_returns: np.ndarray | None = None
    spec_members: np.ndarray | None = None
    eval_order: np.ndarray | None = None
    spec_class: str = "none"
    spec_class_source: str | None = None

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
        self._validate_version_2(T, N)

    def _validate_version_2(self, T: int, N: int) -> None:
        if self.base_returns is not None:
            self.base_returns = np.asarray(self.base_returns, dtype=float)
            if self.base_returns.ndim != 2 or self.base_returns.shape[0] != T or self.base_returns.shape[1] < 1:
                raise TranscriptError(f"base_returns must be (T={T}, K), got shape {self.base_returns.shape}")
            if not np.isfinite(self.base_returns).all():
                raise TranscriptError("base_returns contain NaN or inf")

        if self.spec_members is not None:
            if self.base_returns is None:
                raise TranscriptError("spec_members needs base_returns")
            self.spec_members = np.asarray(self.spec_members, dtype=float)
            K = self.base_returns.shape[1]
            if self.spec_members.shape != (N, K):
                raise TranscriptError(f"spec_members must be (N={N}, K={K}), got shape {self.spec_members.shape}")
            gap = np.abs(self.returns - self.base_returns @ self.spec_members.T).max(axis=0)
            tolerance = RECONSTRUCTION_RTOL * max(float(np.abs(self.returns).max()), np.finfo(float).tiny)
            bad = np.flatnonzero(gap > tolerance)
            if bad.size:
                raise TranscriptError(
                    f"returns do not equal base_returns @ spec_members.T for {bad.size} specification(s), e.g. "
                    f"{self.spec_ids[bad[0]]!r} (largest gap {gap[bad[0]]:.3g}, tolerance {tolerance:.3g})"
                )

        if self.eval_order is not None:
            self.eval_order = np.asarray(self.eval_order, dtype=np.int64)
            if self.eval_order.shape != (N,) or not np.array_equal(np.sort(self.eval_order), np.arange(N)):
                raise TranscriptError("eval_order must be a permutation of 0..N-1")

        try:
            declared = parse_class(self.spec_class)
        except ValueError as exc:
            raise TranscriptError(str(exc)) from exc
        if declared is None:
            self.spec_class = "none"
            if self.spec_class_source is not None:
                raise TranscriptError("spec_class_source is set but no spec_class is declared")
            return
        self.spec_class = declared.name
        if self.spec_class_source not in CLASS_SOURCES:
            raise TranscriptError(f"a declared spec_class needs spec_class_source, one of {CLASS_SOURCES}")
        if self.spec_members is None:
            raise TranscriptError("a declared spec_class needs base_returns and spec_members")
        if not declared.contains(self.spec_members[self.submitted_index]):
            raise TranscriptError(
                f"the submitted specification {self.submitted!r} is outside the declared class {declared.name}, "
                f"so the full-class test cannot certify it"
            )
        outside = [i for i in range(N) if not declared.contains(self.spec_members[i])]
        if outside:
            raise TranscriptError(
                f"{len(outside)} logged specification(s) fall outside the declared class {declared.name}, e.g. "
                f"{self.spec_ids[outside[0]]!r}"
            )

    @property
    def n_periods(self) -> int:
        return self.returns.shape[0]

    @property
    def n_specs(self) -> int:
        return self.returns.shape[1]

    @property
    def submitted_index(self) -> int:
        return int(np.flatnonzero(self.spec_ids == self.submitted)[0])

    @property
    def declared_class(self) -> SubsetClass | None:
        return parse_class(self.spec_class)

    def save(self, path) -> None:
        arrays = {
            "returns": self.returns, "spec_ids": self.spec_ids, "submitted": np.array(self.submitted),
            "menu_kind": np.array(self.menu_kind), "periods_per_year": np.array(self.periods_per_year),
            "format_version": np.array(FORMAT_VERSION), "spec_class": np.array(self.spec_class),
            "spec_class_source": np.array(self.spec_class_source or ""),
        }
        for name in ("base_returns", "spec_members", "eval_order"):
            if getattr(self, name) is not None:
                arrays[name] = getattr(self, name)
        np.savez_compressed(path, **arrays)


def from_matrix(R, submitted_index: int, spec_ids=None, menu_kind: str = "unknown", periods_per_year: int = 252,
                *, base_returns=None, spec_members=None, eval_order=None, spec_class: str = "none",
                spec_class_source: str | None = None) -> Transcript:
    R = np.asarray(R, dtype=float)
    n = R.shape[1] if R.ndim == 2 else 0
    ids = np.asarray(spec_ids if spec_ids is not None else [f"spec_{i}" for i in range(n)]).astype(str)
    if not 0 <= submitted_index < len(ids):
        raise TranscriptError(f"submitted_index {submitted_index} is out of range for {len(ids)} specifications")
    return Transcript(R, ids, ids[submitted_index], menu_kind, periods_per_year, base_returns=base_returns,
                      spec_members=spec_members, eval_order=eval_order, spec_class=spec_class,
                      spec_class_source=spec_class_source)


def load_npz(path) -> Transcript:
    with np.load(path, allow_pickle=False) as z:
        missing = {"returns", "spec_ids", "submitted"} - set(z.files)
        if missing:
            raise TranscriptError(f"{path} is missing required field(s): {', '.join(sorted(missing))}")

        def optional(name):
            return z[name] if name in z.files else None

        return Transcript(
            returns=z["returns"],
            spec_ids=z["spec_ids"],
            submitted=z["submitted"].item(),
            menu_kind=z["menu_kind"].item() if "menu_kind" in z.files else "unknown",
            periods_per_year=z["periods_per_year"].item() if "periods_per_year" in z.files else 252,
            base_returns=optional("base_returns"),
            spec_members=optional("spec_members"),
            eval_order=optional("eval_order"),
            spec_class=z["spec_class"].item() if "spec_class" in z.files else "none",
            spec_class_source=(z["spec_class_source"].item() or None) if "spec_class_source" in z.files else None,
        )


def load_csv(path, submitted: str, menu_kind: str = "unknown", periods_per_year: int = 252) -> Transcript:
    """Wide CSV: the first column labels periods, every other column is one specification."""
    df = pd.read_csv(path, index_col=0)
    try:
        R = df.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except ValueError as exc:
        raise TranscriptError(f"{path}: non-numeric return values ({exc})") from exc
    return Transcript(R, df.columns.astype(str).to_numpy(), submitted, menu_kind, periods_per_year)


def from_sandbox(sandbox: Sandbox, menu_kind: str = "unknown", spec_class: str | None = None) -> Transcript:
    """A version-2 transcript from a sandbox log. base_returns holds all of the sandbox's features. If the
    sandbox enforced a class during the search, that class is recorded with source "sandbox"; otherwise a
    `spec_class` passed here is recorded as "attested"."""
    if sandbox.submission is None:
        raise TranscriptError("the sandbox has no submission")
    spec, _ = sandbox.submission
    log = sandbox.transcript
    matches = [e.call_index for e in log if np.array_equal(e.spec.weights, spec.weights)]
    if not matches:
        raise TranscriptError("the submitted specification was never evaluated, so it is not in the transcript")
    ids = [f"{e.call_index}:{e.spec.name}" if e.spec.name else str(e.call_index) for e in log]

    enforced = getattr(sandbox, "spec_class", None)
    if enforced is not None:
        if spec_class is not None and parse_class(spec_class) != enforced:
            raise TranscriptError(f"the sandbox enforced {enforced.name}, not {spec_class}")
        declared, source = enforced.name, "sandbox"
    elif spec_class is not None and parse_class(spec_class) is not None:
        declared, source = spec_class, "attested"
    else:
        declared, source = "none", None

    return Transcript(
        sandbox.returns_matrix(), ids, ids[matches[0]], menu_kind, sandbox.periods_per_year,
        base_returns=sandbox.base_feature_columns(),
        spec_members=np.stack([e.spec.weights for e in log]),
        eval_order=np.array([e.call_index for e in log]),
        spec_class=declared, spec_class_source=source,
    )
