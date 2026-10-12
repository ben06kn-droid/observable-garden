"""The class: the set of rules a search may draw from, fixed in one file before the search.

A class file is JSON, one of:

    {"kind": "subsets", "features": ["mom60_z", "rev5_rank"] | "all", "max_size": 3, "signed": true}
    {"kind": "streams", "file": "streams.npz"}          # supplied return streams, array "streams" (N, T)

A subsets class holds every equal-weight combination of up to `max_size` of the listed features,
each long (and, if `signed`, short). The gate prices a search against the whole class, so the
class must be fixed before the first evaluation: **a class changed after results are seen is a
search over classes**, and the gate cannot see that search. That is why the harness hashes the
class file before the first evaluation and writes the hash into the log, and why `quixote audit`
refuses a log whose class hash differs from the class file it is given.

`load(path, panel=...)` returns the class with its size, its SHA-256 and, given a panel, its
**bar**: the class tier's critical Sharpe at the given alpha on that panel, from the class's
own null maxima under a stationary bootstrap of the panel's rows.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BAR_MAX_CELLS = 5_000_000          # members x rows above which the bar is not computed on load


class ClassError(ValueError):
    """A class file that does not follow the format, or does not fit the panel."""


@dataclass
class LoadedClass:
    kind: str
    sha256: str
    size: int
    spec_class: object | None = None          # garden.spec_class.SubsetClass for kind "subsets"
    features: list[int] | None = None        # panel feature columns the class draws from
    feature_names: list[str] | None = None
    streams: np.ndarray | None = None        # (N, T) for kind "streams"
    bar: float | None = None                 # the class tier's critical Sharpe on the panel
    alpha: float | None = None
    B: int | None = None
    path: str = ""
    spec: dict = field(default_factory=dict)

    def describe(self) -> str:
        what = (f"subsets of up to {self.spec_class.max_size} of {len(self.features)} features, "
                f"{'signed' if self.spec_class.signed else 'long only'}" if self.kind == "subsets"
                else "supplied return streams")
        bar = (f"bar {self.bar:.3f} (the class tier's critical annualised Sharpe at alpha "
               f"{self.alpha:g}, B {self.B})" if self.bar is not None else "bar not computed")
        return f"class {Path(self.path).name}: {what}; size {self.size:,}; {bar}; sha256 {self.sha256[:12]}"


def file_sha256(path) -> str:
    """The class's hash: its file's bytes, plus the streams file's for a streams class."""
    path = Path(path)
    h = hashlib.sha256(path.read_bytes())
    spec = json.loads(path.read_text())
    if spec.get("kind") == "streams":
        sf = (path.parent / spec["file"]) if not Path(spec["file"]).is_absolute() else Path(spec["file"])
        h.update(hashlib.sha256(sf.read_bytes()).digest())
    return h.hexdigest()


def load(path, panel_arrays: dict | None = None, *, alpha: float = 0.05, B: int = 500,
         seed: int = 0, compute_bar: bool = True) -> LoadedClass:
    """Read and check a class file. `panel_arrays` is `quixote.panel.read(...)` output; with it,
    feature names are resolved against the panel and the bar is computed (when small enough)."""
    from garden.spec_class import SubsetClass
    path = Path(path)
    try:
        spec = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise ClassError(f"cannot read class file {path}: {e}") from None
    kind = spec.get("kind")
    sha = file_sha256(path)
    if kind == "subsets":
        max_size, signed = int(spec.get("max_size", 3)), bool(spec.get("signed", False))
        if max_size < 1:
            raise ClassError("max_size must be >= 1")
        feats = spec.get("features", "all")
        if panel_arrays is not None:
            names = list(panel_arrays["feature_names"])
            if feats == "all":
                idx = list(range(len(names)))
            else:
                unknown = [f for f in feats if f not in names]
                if unknown:
                    raise ClassError(f"class features {unknown} are not in the panel")
                idx = [names.index(f) for f in feats]
            fnames = [names[k] for k in idx]
        else:
            if feats == "all":
                idx, fnames = None, None
            else:
                idx, fnames = list(range(len(feats))), list(feats)
        sc = SubsetClass(max_size=max_size, signed=signed)
        K = len(idx) if idx is not None else None
        size = sc.size(K) if K is not None else -1
        lc = LoadedClass("subsets", sha, size, spec_class=sc, features=idx, feature_names=fnames,
                         path=str(path), spec=spec)
    elif kind == "streams":
        sf = Path(spec["file"]) if Path(spec["file"]).is_absolute() else path.parent / spec["file"]
        with np.load(sf, allow_pickle=False) as z:
            S = np.asarray(z["streams"], float)
        if S.ndim != 2:
            raise ClassError("a streams file holds an array 'streams' of shape (N, T)")
        lc = LoadedClass("streams", sha, int(S.shape[0]), streams=S, path=str(path), spec=spec)
    else:
        raise ClassError(f"class kind must be 'subsets' or 'streams', not {kind!r}")
    if compute_bar and panel_arrays is not None:
        lc.bar, lc.alpha, lc.B = class_bar(lc, panel_arrays, alpha=alpha, B=B, seed=seed)
    return lc


def table_for(lc: LoadedClass, panel_arrays: dict):
    """The class's net streams on the panel, as an in-memory `ClassTable` (every member's
    stream computed once, as the registered runs did). Kind 'subsets' only."""
    from environments.class_table import ClassTable, _panel_hash, canonical, members_in_order, streams_for
    from quixote.panel import to_engine
    panel = to_engine(panel_arrays, features=lc.features)
    K = panel.features.shape[2]
    members = members_in_order(lc.spec_class, K)
    streams = np.empty((len(members), panel.returns.shape[0]))
    for s0 in range(0, len(members), 512):                # in chunks, never one column at a time
        streams[s0:s0 + 512] = streams_for(panel, members[s0:s0 + 512])
    table = ClassTable(streams=streams, members=members,
                       index={canonical(s): i for i, s in enumerate(members)},
                       panel_hash=_panel_hash(panel), periods_per_year=float(panel.periods_per_year))
    return panel, table


def null_maxima(streams: np.ndarray, ppy: float, B: int, seed: int, block_basis=None):
    """The class's null maxima: the largest demeaned annualised Sharpe over the members on each
    of B stationary-bootstrap resamples of the rows (block length by Politis-White on the basis)."""
    from environments.class_table import ClassTable
    from estimator.bootstrap import select_block_length, stationary_bootstrap_indices
    basis = streams.T if block_basis is None else block_basis
    L = int(select_block_length(basis - basis.mean(axis=0)))
    rng = np.random.default_rng(seed)
    T = streams.shape[1]
    rows = [stationary_bootstrap_indices(T, L, rng) for _ in range(B)]
    t = ClassTable(streams=streams, members=[], index={}, panel_hash="", periods_per_year=ppy)
    return t.null_max(rows), L, rows


def class_bar(lc: LoadedClass, panel_arrays: dict, *, alpha: float = 0.05, B: int = 500, seed: int = 0):
    """(bar, alpha, B), or (None, alpha, B) when the class is too large to price on load."""
    T = panel_arrays["returns"].shape[0]
    if lc.size * T > BAR_MAX_CELLS:
        return None, alpha, B
    if lc.kind == "subsets":
        panel, table = table_for(lc, panel_arrays)
        streams, ppy = np.asarray(table.streams), panel.periods_per_year
        from environments.real_sandbox import RealSandbox
        basis = RealSandbox(panel).base_feature_columns()
    else:
        streams, ppy, basis = lc.streams, float(panel_arrays["periods_per_year"]), None
    M, _, _ = null_maxima(streams, ppy, B, seed, basis)
    return float(np.quantile(M, 1 - alpha)), alpha, B
