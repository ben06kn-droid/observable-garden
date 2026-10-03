"""What an agent on a 7.5 planted panel is shown: the masked view.

`prereg/planted-edge.md` build item 3, "Masking". Instruments are opaque labels, dates
are period indices, and **feature names are masked too**, as `F00`-`F39`, by a seeded
permutation per panel: `planted_panel.masking_permutation`, child [1]'s stream after the
member draw.

**The index order is masked, not only the names.** An agent names a feature by its
integer index (`evaluate(features=[...])`, `flip(feature=...)`, `pick(among=[...])`), and
every support it is shown is a list of indices. In 6.5 no real feature name reached
any agent: on 2026-10-03, a scan of all 87 ETF run files found none of the 40 names in
any prompt, tool call, tool result or assistant text. What did cross was a **stable
index**. Index 32 was `beta252_z` on every panel, so "convergence on one feature" could
be convergence on one index. Relabelling alone would leave that in place, so the view
permutes the feature AXIS: masked index `j` is true feature `perm[j]`, and its label is
`F{j:02d}`.

**The view is a `RealPanel`**, so the sandbox, the grammar, the session log and every
tool result are in masked indices, with no translation layer for a leak to slip
through. The harness maps back with `FeatureMask.to_true` for pricing and truths, and
nothing reachable from a tool holds the mask.

- **Features**: `X[..., perm]`, names `F00`, `F01`, ...
- **Instruments**: labelled `A000`, ... by a second permutation, drawn next from the
  same child [1] stream. Rows are not reordered, so costs, tradability and the planted
  weights keep their positions. No tool exposes an instrument; the labels exist for
  `get_data`.
- **Meta**: none of the panel's. No dates, no tickers, no file paths.
- Returns, costs and session flags are untouched: masking changes what is shown, not
  what is earned.

*A choice to record at the stage-2 live commit:* the registration fixes the feature
permutation's stream and says nothing on the instrument labels. Drawing them next from
child [1] keeps every per-panel random choice on one registered stream.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import comb

import numpy as np

from environments import planted_panel as pp


@dataclass(frozen=True)
class FeatureMask:
    """`perm[j]` is the true index of masked feature `j`. Harness-only."""
    perm: tuple

    @classmethod
    def for_seed(cls, seed: int, K: int) -> "FeatureMask":
        return cls(tuple(int(k) for k in pp.masking_permutation(seed, K)))

    @property
    def K(self) -> int:
        return len(self.perm)

    @staticmethod
    def label(j: int) -> str:
        return f"F{int(j):02d}"

    def to_true(self, support) -> tuple:
        """A masked support, as the agent's log holds it, in true indices."""
        return tuple((self.perm[int(k)], float(s)) for k, s in support)

    def to_masked(self, support) -> tuple:
        inv = np.argsort(self.perm)
        return tuple((int(inv[int(k)]), float(s)) for k, s in support)


def asset_permutation(seed: int, K: int, M: int) -> np.ndarray:
    """The instrument-label permutation: child [1]'s stream after the member draw and
    the feature permutation. Asserts it continues the registered stream exactly."""
    rng = np.random.default_rng(pp.children(seed)[1])
    rng.integers(8 * comb(K, 3))                     # the member draw, consumed
    perm = rng.permutation(K)                        # the feature permutation
    if not np.array_equal(perm, pp.masking_permutation(seed, K)):
        raise AssertionError("child [1]'s stream no longer matches masking_permutation")
    return rng.permutation(M)


def agent_view(panel, seed: int):
    """`(masked panel, FeatureMask)` for the panel of `seed`. `panel` is a draw's
    in-sample `RealPanel` (true order). The masked panel is what the agent's sandbox
    holds; the mask stays with the harness."""
    T, M, K = panel.features.shape
    mask = FeatureMask.for_seed(seed, K)
    q = asset_permutation(seed, K, M)
    view = replace(
        panel, name="planted",
        feature_names=[FeatureMask.label(j) for j in range(K)],
        features=np.ascontiguousarray(panel.features[:, :, list(mask.perm)]),
        assets=[f"A{int(q[i]):03d}" for i in range(M)],
        meta={"masked": True})
    return view, mask
