"""The declared class as a table of net-of-cost streams, computed once.

**Why this exists.** On a real panel the sandbox scores a specification *net of
costs*, and costs are not linear in the weights, so there is no (T, K) basis
whose signed sums reproduce the statistic the search optimises. The replay path
summed base columns and therefore priced a different statistic: the agent pilot's
identity-replicate guard failed on all three replay-arm logs with realized-against-
replayed score gaps around 7.4, three orders of magnitude past float accumulation
(`prereg/agent-pilot.md` amendment 3).

The fix is to stop reconstructing the statistic and store it. Every member of the
declared class gets its net stream computed **once** on the panel, into a
`(T, N)` table. Then:

- `RealSandbox.evaluate` scores by **lookup** in the table;
- a replay scores a candidate by **resampling rows** of the same table;
- a full-class null takes the max over members, chunked, from the same table.

All three read the same numbers, so they are the same statistic **by
construction** rather than to a tolerance. That is what makes the guard pass
bit-identically instead of nearly.

**Memory, stated rather than discovered.** The table is `T x N` float64:

| panel | T | class | N | table |
|---|---|---|---|---|
| ADR (K = 22) | 36,404 | signed, depth 3 | 13,288 | **3.87 GB** |
| ETF (K = 40) | 4,276 | signed, depth 3 | **82,240** | **2.81 GB** |

Neither fits comfortably in a worker's resident set, so the table lives on disk
as a `numpy` memmap and **every pass over members is chunked**: resident memory
is `T x chunk`, which at the default chunk of 512 is 149 MB for the ADR panel and
17 MB for the ETF panel. `max_sharpe` walks members in chunks exactly as
`garden/_full_class_engine.py` does, and a replay touches only the handful of
candidate members a move asks about, so it never materialises a chunk at all.

Building the ETF table is the expensive direction — 82,240 net-stream
computations — and it is done once per panel and cached with a manifest carrying
the panel's own hash, so a table can never be silently reused across panels.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

CHUNK = 512
TABLES_DIR = Path(__file__).resolve().parent.parent / "data" / "class_tables"


def members_in_order(spec_class, K: int) -> list[tuple[tuple[int, float], ...]]:
    """Every class member as a support, in `garden/_full_class_engine.py`'s own
    enumeration order: by size, then by `SubsetClass.members`' order within a
    size. Sharing the order is what lets a table index and a full-class null
    index mean the same thing."""
    out = []
    for m in range(1, min(spec_class.max_size, K) + 1):
        idx, signs = spec_class.members(K, m)
        for row in range(idx.shape[0]):
            out.append(tuple((int(idx[row, c]), float(signs[row, c]))
                             for c in range(m)))
    return out


def canonical(support) -> tuple[tuple[int, float], ...]:
    """A support's canonical form: sorted by feature index. Two supports that
    hold the same signed features are one member of the class, however the search
    happened to order them."""
    return tuple(sorted(((int(k), float(s)) for k, s in support), key=lambda p: p[0]))


def _panel_hash(panel) -> str:
    h = hashlib.sha256()
    for arr in (panel.features, panel.returns, panel.cost_rate, panel.borrow_rate):
        h.update(np.ascontiguousarray(np.asarray(arr, dtype=float)).tobytes()[:1 << 20])
        h.update(str(np.asarray(arr).shape).encode())
    return h.hexdigest()[:16]


@dataclass
class ClassTable:
    """`(T, N)` net-of-cost streams, one column per declared-class member."""
    streams: np.ndarray                     # memmap or array, (T, N)
    members: list
    index: dict                             # canonical support -> column
    panel_hash: str
    periods_per_year: float
    path: str | None = None

    @property
    def T(self) -> int:
        return int(self.streams.shape[0])

    @property
    def N(self) -> int:
        return int(self.streams.shape[1])

    @property
    def annualization(self) -> float:
        return float(np.sqrt(self.periods_per_year))

    def column(self, support) -> int:
        key = canonical(support)
        if key not in self.index:
            raise KeyError(f"support {key} is not a member of the tabulated class")
        return self.index[key]

    def stream(self, support, rows=None) -> np.ndarray:
        col = self.streams[:, self.column(support)]
        return np.asarray(col if rows is None else col[rows], dtype=float)

    # -- the one statistic -------------------------------------------------

    def sharpe(self, support, rows=None, demeaned: bool = False) -> float:
        """The member's annualised Sharpe on `rows`.

        `demeaned` subtracts the member's **full-sample** mean before resampling
        statistics are taken, which is how the null is imposed: the same
        `S0 = x - mean(x)` the column-based path applies, done on the stored
        stream instead of on a reconstruction of it.
        """
        x = self.stream(support, rows)
        if demeaned:
            x = x - float(self.streams[:, self.column(support)].mean())
        return self._sharpe_of(x)

    def _sharpe_of(self, x: np.ndarray) -> float:
        """`RealSandbox.evaluate`'s own statistic, element for element.

        **Deliberately not `estimator.bootstrap.sharpe`.** That one guards: a
        variance floor sends a degenerate column to 0, and `SHARPE_CAP` censors
        `|Sharpe|` at 100 annualised. Those guards are right for a bootstrap over
        a simulated panel, where Sharpes are of order 1 and a degenerate
        resample is the thing being guarded against.

        On the ADR panel they are not. Its registered annualisation is 5-minute
        bars — `periods_per_year = 19,152`, so `sqrt` is about 138 — and the
        live search reaches Sharpe **107**. Scoring the table through the
        guarded estimator returned **exactly 100.0** for every good candidate,
        so the replay priced a **censored** statistic while the search optimised
        an uncensored one, and the identity guard failed at a gap of 7.42 for a
        third distinct reason. Censoring the null is the same error the table was
        built to remove, one level up.

        So the table scores what the sandbox scores. Whether the ADR panel's
        annualisation or the cap should change is 7.4's decision and is recorded
        in `prereg/agent-pilot.md`, not settled here.
        """
        x = np.asarray(x, dtype=float)
        std = float(x.std(ddof=1))
        return float(x.mean() / std * self.annualization) if std > 0 else 0.0

    def scorer(self, rows=None, demeaned: bool = False):
        """A `score_fn(support, statistic)` for `quixote.grammar.Grammar`.

        This is the whole point: the live search and every replicate take their
        numbers from the same table, so the grammar cannot be scoring one thing
        while the null prices another.
        """
        def score_fn(support, statistic="sharpe"):
            if statistic != "sharpe":
                raise ValueError(
                    f"unknown statistic {statistic!r}; a class table stores net "
                    "streams and scores Sharpe. A statistic computed from a "
                    "feature basis is not available here, because no such basis "
                    "reproduces a net-of-cost statistic.")
            return self.sharpe(support, rows, demeaned=demeaned)
        return score_fn

    def max_sharpe(self, rows=None, demeaned: bool = False,
                   chunk: int = CHUNK) -> tuple[float, int]:
        """The largest Sharpe over the whole class, and which member attains it.

        Chunked over members, as `garden/_full_class_engine.py` is, so resident
        memory is `len(rows) x chunk` rather than the table.

        **The chunk is part of the computation, not a tuning knob.** numpy reduces
        a `(T, chunk)` block in a different order from a `(T, 1)` one, so the
        winning member's Sharpe can differ in its last bits between chunk sizes.
        Which member wins does not change; the value does, at the 1e-16 level. A
        caller that needs two runs to agree bit for bit must hold the chunk fixed,
        which is why `CHUNK` is a module constant rather than a per-call choice.

        The replay path is unaffected: it scores one candidate at a time from a
        single stored column, which is the same reduction the sandbox's own
        `evaluate` performs.
        """
        best, best_j = float("-inf"), -1
        mu = self.streams.mean(axis=0) if demeaned else None
        for start in range(0, self.N, chunk):
            stop = min(start + chunk, self.N)
            block = np.asarray(self.streams[:, start:stop], dtype=float)
            if rows is not None:
                block = block[rows, :]
            if demeaned:
                block = block - np.asarray(mu[start:stop], dtype=float)
            # the sandbox's statistic, as `_sharpe_of` explains
            std = block.std(axis=0, ddof=1)
            s = np.where(std > 0, block.mean(axis=0) / np.where(std > 0, std, 1.0),
                         0.0) * self.annualization
            j = int(np.argmax(s))
            if float(s[j]) > best:
                best, best_j = float(s[j]), start + j
        return best, best_j


def streams_for(panel, supports) -> np.ndarray:
    """`(n, T)` net streams for `n` members, in ONE pass over the panel.

    `RealPanel.weights_from` walks periods in a Python loop, because the book is
    stateful: a name that is not tradable in a period keeps the weight it had,
    and a flat-overnight panel opens and closes each session flat. Calling it
    once per member walks that loop once per member — 13,288 x 36,404 iterations
    for the ADR table, which measured **8.6 hours** and 6% done at half an hour.

    The loop is sequential in time and **embarrassingly parallel across
    members**, so it is walked once with the whole chunk carried through it.
    Batched, the ADR table takes about **3 minutes** instead of 8.6 hours.

    **How exactly it agrees with the per-member path, measured rather than
    claimed.** The arithmetic is the same operations on the same elements, but a
    row of a `(n, M)` block and a standalone `(M,)` vector are not reduced with
    the same pairwise blocking, so the two differ by up to **7e-18 absolute** on
    a stream of order 1e-3 — about 1e-14 relative, roughly one ulp. Two
    consequences, both recorded rather than discovered:

    - **the table is the definition** of a member's net stream once it exists.
      `RealSandbox.evaluate` reads it, every replicate reads it, and the
      identity-replicate guard compares table against table, so the guard's
      agreement is exact;
    - the kernel is **invariant to the chunk size for n >= 2** (checked in
      `tests/test_class_table.py`), but a single-member call takes numpy's
      one-row path and lands on the other side of that 7e-18. A table is
      therefore built in chunks and never one column at a time.

    Weights are never materialised: each period's contribution to the stream is
    accumulated as the loop passes, so memory is the chunk's `(n, M)` state plus
    its `(n, T)` output.

    Weights are never materialised: each period's contribution to the stream is
    accumulated as the loop passes, so memory is the chunk's `(n, M)` state plus
    its `(n, T)` output.
    """
    T, M, K = panel.features.shape
    n = len(supports)
    Wf = np.zeros((K, n))
    for j, support in enumerate(supports):
        for k, sign in support:
            Wf[k, j] = sign

    out = np.empty((n, T))
    held = np.zeros((n, M))
    prev = np.zeros((n, M))
    flat = bool(panel.flat_overnight)
    for t in range(T):
        free = panel.tradable[t]
        if flat and panel.session_start[t]:
            held = np.zeros((n, M))
        target = np.where(free, (panel.features[t] @ Wf).T, 0.0)
        if free.any():
            target = target - target[:, free].mean(axis=1, keepdims=True) * free
            gross = np.abs(target[:, free]).sum(axis=1, keepdims=True)
            nz = gross[:, 0] > 0
            target[nz] = target[nz] / gross[nz]
        new = np.where(free, target, held)
        if flat and panel.session_end[t]:
            new = np.zeros((n, M))
        out[:, t] = ((new * panel.returns[t]).sum(axis=1)
                     - (np.abs(new - prev) * panel.cost_rate[t]).sum(axis=1)
                     - (np.clip(-new, 0, None) * panel.borrow_rate[t]).sum(axis=1))
        held = prev = new
    return out


def table_path(name: str, spec_class, K: int) -> Path:
    return TABLES_DIR / f"{name}_{spec_class.name.replace(':', '_')}_K{K}.npy"


def build_class_table(panel, spec_class, name: str, path: Path | None = None,
                      chunk: int = CHUNK, rebuild: bool = False,
                      progress=None) -> ClassTable:
    """Compute every member's net stream once, into a memmap, with a manifest.

    The manifest carries the panel's hash, so a table built on one panel can
    never be silently reused on another; a mismatch rebuilds rather than
    returning the wrong numbers.
    """
    K = panel.features.shape[2]
    path = Path(path) if path is not None else table_path(name, spec_class, K)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = path.with_suffix(".json")
    members = members_in_order(spec_class, K)
    index = {canonical(s): i for i, s in enumerate(members)}
    T, N = panel.returns.shape[0], len(members)
    ph = _panel_hash(panel)

    if path.exists() and manifest_path.exists() and not rebuild:
        man = json.loads(manifest_path.read_text())
        if (man.get("panel_hash") == ph and man.get("shape") == [T, N]
                and man.get("class") == spec_class.name):
            streams = np.lib.format.open_memmap(path, mode="r")
            return ClassTable(streams=streams, members=members, index=index,
                              panel_hash=ph,
                              periods_per_year=float(panel.periods_per_year),
                              path=str(path))

    streams = np.lib.format.open_memmap(path, mode="w+", dtype=np.float64,
                                        shape=(T, N))
    for start in range(0, N, chunk):
        stop = min(start + chunk, N)
        streams[:, start:stop] = streams_for(panel, members[start:stop]).T
        streams.flush()
        if progress is not None:
            progress(stop, N)
    manifest_path.write_text(json.dumps(
        {"name": name, "class": spec_class.name, "K": K, "shape": [T, N],
         "panel_hash": ph, "periods_per_year": float(panel.periods_per_year),
         "dtype": "float64", "bytes": int(T * N * 8),
         "sha256_first_mb": hashlib.sha256(
             np.ascontiguousarray(streams[:, :min(N, 64)]).tobytes()[:1 << 20]
         ).hexdigest()[:16]}, indent=1))
    streams.flush()
    return ClassTable(streams=np.lib.format.open_memmap(path, mode="r"),
                      members=members, index=index, panel_hash=ph,
                      periods_per_year=float(panel.periods_per_year), path=str(path))
