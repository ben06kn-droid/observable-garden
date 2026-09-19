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

from garden.spec_class import ExplicitClass, SubsetClass
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
    class_returns: np.ndarray | None = None     # (T, M) every member of an explicit class
    class_ids: np.ndarray | None = None         # (M,) str, the id of each class column
    class_positions: np.ndarray | None = None   # (T, M) optional: the position each member held
    asset_returns: np.ndarray | None = None     # (T, M) optional: the return each member's asset earned

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
        if isinstance(declared, ExplicitClass):
            self._validate_explicit_class(T, N, declared)
            return
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

    def _validate_explicit_class(self, T: int, N: int, declared: ExplicitClass) -> None:
        """An explicit class is checked by id, then column by column. Matching float columns without ids
        would be fragile: correlated rules routinely produce near-duplicate return streams."""
        if self.class_returns is None or self.class_ids is None:
            raise TranscriptError(
                'spec_class "explicit" needs class_returns and class_ids: the return stream and id of every '
                "specification the search could have produced"
            )
        self.class_returns = np.asarray(self.class_returns, dtype=float)
        self.class_ids = np.asarray(self.class_ids).astype(str)
        if self.class_returns.ndim != 2 or self.class_returns.shape[0] != T:
            raise TranscriptError(f"class_returns must be (T={T}, M), got shape {self.class_returns.shape}")
        M = self.class_returns.shape[1]
        if not np.isfinite(self.class_returns).all():
            raise TranscriptError("class_returns contain NaN or inf")
        if self.class_ids.shape != (M,):
            raise TranscriptError(f"expected {M} class_ids, one per class column, got shape {self.class_ids.shape}")
        if len(set(self.class_ids.tolist())) != M:
            raise TranscriptError("class_ids must be unique")
        if declared.n_members is not None and declared.n_members != M:
            raise TranscriptError(
                f"spec_class declares {declared.n_members} members but class_returns has {M} columns"
            )

        position = {cid: i for i, cid in enumerate(self.class_ids.tolist())}
        if self.submitted not in position:
            raise TranscriptError(
                f"the submitted specification {self.submitted!r} is outside the declared class, "
                "so the full-class test cannot certify it"
            )
        missing = [s for s in self.spec_ids.tolist() if s not in position]
        if missing:
            raise TranscriptError(
                f"{len(missing)} logged specification(s) fall outside the declared class, e.g. {missing[0]!r}. "
                "Membership is by id: every logged spec_id must appear among class_ids"
            )
        columns = np.array([position[s] for s in self.spec_ids.tolist()])
        gap = np.abs(self.returns - self.class_returns[:, columns]).max(axis=0)
        tolerance = RECONSTRUCTION_RTOL * max(float(np.abs(self.returns).max()), np.finfo(float).tiny)
        bad = np.flatnonzero(gap > tolerance)
        if bad.size:
            raise TranscriptError(
                f"{bad.size} logged specification(s) do not match their class column, e.g. "
                f"{self.spec_ids[bad[0]]!r} (largest gap {gap[bad[0]]:.3g}, tolerance {tolerance:.3g})"
            )
        self._validate_class_positions(T, M, tolerance)

    def _validate_class_positions(self, T: int, M: int, tolerance: float) -> None:
        """Positions and their assets' returns are optional, and let the gate rebuild returns itself (for
        shift nulls, non-additive-scoring's prereg, f298103). Supplied together or not at all."""
        if self.class_positions is None and self.asset_returns is None:
            return
        if self.class_positions is None or self.asset_returns is None:
            raise TranscriptError("class_positions and asset_returns must be supplied together")
        self.class_positions = np.asarray(self.class_positions, dtype=float)
        self.asset_returns = np.asarray(self.asset_returns, dtype=float)
        for name, arr in (("class_positions", self.class_positions), ("asset_returns", self.asset_returns)):
            if arr.shape != (T, M):
                raise TranscriptError(f"{name} must be (T={T}, M={M}), got shape {arr.shape}")
            if not np.isfinite(arr).all():
                raise TranscriptError(f"{name} contains NaN or inf")
        gap = float(np.abs(self.class_returns - self.class_positions * self.asset_returns).max())
        if gap > tolerance:
            raise TranscriptError(
                f"class_positions times asset_returns does not reproduce class_returns "
                f"(largest gap {gap:.3g}, tolerance {tolerance:.3g})"
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
    def declared_class(self) -> SubsetClass | ExplicitClass | None:
        return parse_class(self.spec_class)

    def save(self, path) -> None:
        arrays = {
            "returns": self.returns, "spec_ids": self.spec_ids, "submitted": np.array(self.submitted),
            "menu_kind": np.array(self.menu_kind), "periods_per_year": np.array(self.periods_per_year),
            "format_version": np.array(FORMAT_VERSION), "spec_class": np.array(self.spec_class),
            "spec_class_source": np.array(self.spec_class_source or ""),
        }
        for name in ("base_returns", "spec_members", "eval_order",
                     "class_returns", "class_ids", "class_positions", "asset_returns"):
            if getattr(self, name) is not None:
                arrays[name] = getattr(self, name)
        np.savez_compressed(path, **arrays)


def from_matrix(R, submitted_index: int, spec_ids=None, menu_kind: str = "unknown", periods_per_year: int = 252,
                *, base_returns=None, spec_members=None, eval_order=None, spec_class: str = "none",
                spec_class_source: str | None = None, class_returns=None, class_ids=None,
                class_positions=None, asset_returns=None) -> Transcript:
    R = np.asarray(R, dtype=float)
    n = R.shape[1] if R.ndim == 2 else 0
    ids = np.asarray(spec_ids if spec_ids is not None else [f"spec_{i}" for i in range(n)]).astype(str)
    if not 0 <= submitted_index < len(ids):
        raise TranscriptError(f"submitted_index {submitted_index} is out of range for {len(ids)} specifications")
    return Transcript(R, ids, ids[submitted_index], menu_kind, periods_per_year, base_returns=base_returns,
                      spec_members=spec_members, eval_order=eval_order, spec_class=spec_class,
                      spec_class_source=spec_class_source, class_returns=class_returns, class_ids=class_ids,
                      class_positions=class_positions, asset_returns=asset_returns)


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
            class_returns=optional("class_returns"),
            class_ids=optional("class_ids"),
            class_positions=optional("class_positions"),
            asset_returns=optional("asset_returns"),
        )


def load_csv(path, submitted: str, menu_kind: str = "unknown", periods_per_year: int = 252) -> Transcript:
    """Wide CSV: the first column labels periods, every other column is one specification."""
    df = pd.read_csv(path, index_col=0)
    try:
        R = df.apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except ValueError as exc:
        raise TranscriptError(f"{path}: non-numeric return values ({exc})") from exc
    return Transcript(R, df.columns.astype(str).to_numpy(), submitted, menu_kind, periods_per_year)


def load_benchmark(path, n_periods: int | None = None) -> np.ndarray:
    """A benchmark return series: first column labels periods, one column of returns.

    One value per period, on the same index as the transcript. It is subtracted from
    every specification's stream before the bootstrap demeans anything, so the null
    becomes zero excess return over this series rather than zero return."""
    df = pd.read_csv(path, index_col=0)
    if df.shape[1] != 1:
        raise TranscriptError(
            f"{path}: a benchmark needs exactly one return column after the period labels, "
            f"got {df.shape[1]}"
        )
    try:
        b = df.iloc[:, 0].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise TranscriptError(f"{path}: non-numeric benchmark values ({exc})") from exc
    if not np.isfinite(b).all():
        raise TranscriptError(f"{path}: benchmark contains NaN or inf")
    if n_periods is not None and b.shape[0] != n_periods:
        raise TranscriptError(
            f"{path}: benchmark has {b.shape[0]:,} periods but the transcript has {n_periods:,}. "
            "Both must be on the same time index; the bootstrap resamples one shared index."
        )
    return b


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
