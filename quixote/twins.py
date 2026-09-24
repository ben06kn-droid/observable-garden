"""Placebo twins, and the masking that keeps them indistinguishable.

`prereg/twin-calibration.md` (item 5). A twin is a dataset in which the null
holds **by construction**; the same agent is re-run on K of them and the real
run's rank among them is the p-value:

    p = (1 + #{twins with p_k <= p_real}) / (K + 1)

which is exact under exchangeability (Phipson & Smyth 2010, opened in full), and
is the same `(1 + #)/(K + 1)` form the gate's bootstrap p-values already use.
**K = 19 for alpha = 0.05 and K = 99 for alpha = 0.01**, the registered values,
whose attainable levels are exactly 1/20 and 1/100.

**What a twin destroys is what the test can detect**, so each construction says
so:

- `joint_time_permutation` permutes the time index of every column together. It
  destroys serial structure, including the volatility clustering the
  pre-registration names as a limit, and keeps each period's cross-section intact.
- `block_permutation` permutes contiguous blocks instead, which keeps serial
  structure inside a block and is **approximate**, as the pre-registration says:
  the seams are where a twin could be detected.

**Masking.** Identifiers are replaced by opaque labels so memorised history
cannot break exchangeability, while the *structural* metadata a theory-driven
`pick_prior` needs — whether a name has a home market, that market's closing
time, sector, liquidity band — is exposed without identity. The
pre-registration records this tension and leaves the resolution to 7.4; what is
here is the mechanism, not that resolution.

Nothing in this module runs an agent, and nothing here certifies: sequential
stopping is deliberately absent, since `prereg/twin-calibration.md` registers
that every certification runs the full K until Besag & Clifford's two open
checks are resolved.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

K_FOR_ALPHA = {0.05: 19, 0.01: 99}      # registered; attainable levels 1/20, 1/100
DESTROYS = {
    "joint_time_permutation": "serial structure, including volatility clustering; "
                              "each period's cross-section survives",
    "block_permutation": "serial structure across block seams only; approximate, "
                         "and the seams are where a twin is detectable",
}


def joint_time_permutation(base: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One permutation applied to every column, so the cross-section of each
    period stays together (`prereg/twin-calibration.md`: 'the same permutation
    across names so cross-sectional structure survives')."""
    base = np.asarray(base, dtype=float)
    return base[rng.permutation(base.shape[0]), :]


def block_permutation(base: np.ndarray, rng: np.random.Generator, block: int = 21) -> np.ndarray:
    base = np.asarray(base, dtype=float)
    T = base.shape[0]
    starts = list(range(0, T, block))
    order = rng.permutation(len(starts))
    return np.concatenate([base[starts[i]:starts[i] + block] for i in order], axis=0)[:T]


def twins(base: np.ndarray, K: int, seed: int | None = None,
          construction: str = "joint_time_permutation", **kw) -> list[np.ndarray]:
    """K placebo twins of one base matrix. K is the caller's, and the registered
    values are in `K_FOR_ALPHA`."""
    if construction not in DESTROYS:
        raise ValueError(f"unknown twin construction {construction!r}; "
                         f"the registered ones are {sorted(DESTROYS)}")
    fn = {"joint_time_permutation": joint_time_permutation,
          "block_permutation": block_permutation}[construction]
    rng = np.random.default_rng(seed)
    return [fn(base, rng, **kw) for _ in range(K)]


def twin_p_value(p_real: float, p_twins) -> float:
    """The real run's rank among its twins, in the form the pre-registration
    fixes. With K twins the smallest attainable value is 1/(K+1)."""
    p_twins = list(p_twins)
    return (1 + sum(1 for p in p_twins if p <= p_real)) / (len(p_twins) + 1)


@dataclass
class Masking:
    """Opaque labels for identities, structural metadata without them.

    `structure` carries, per masked label, only the fields a theory-driven pick
    is allowed to reason about. The mapping back is the harness's; an agent-facing
    view never holds it.
    """
    labels: dict = field(default_factory=dict)          # real id -> masked label
    structure: dict = field(default_factory=dict)       # masked label -> metadata
    _reverse: dict = field(default_factory=dict, repr=False)

    ALLOWED_FIELDS = ("has_home_market", "home_close_et", "sector", "liquidity_band")

    @classmethod
    def build(cls, identities, metadata: dict | None = None, seed: int | None = None) -> "Masking":
        rng = np.random.default_rng(seed)
        order = rng.permutation(len(identities))        # labels carry no ordering either
        labels, structure = {}, {}
        for pos, i in enumerate(order):
            real = list(identities)[int(i)]
            label = f"A{pos:03d}"
            labels[real] = label
            meta = dict((metadata or {}).get(real, {}))
            bad = set(meta) - set(cls.ALLOWED_FIELDS)
            if bad:
                raise ValueError(f"metadata for {real!r} carries identifying fields {sorted(bad)}; "
                                 f"only {list(cls.ALLOWED_FIELDS)} may cross the mask")
            structure[label] = meta
        return cls(labels=labels, structure=structure,
                   _reverse={v: k for k, v in labels.items()})

    def mask(self, real_id: str) -> str:
        return self.labels[real_id]

    def unmask(self, label: str) -> str:
        """Harness-only. An agent-facing view does not hold this object."""
        return self._reverse[label]

    def agent_view(self) -> dict:
        """What an agent may see: labels and structural metadata, no identities
        and no way back."""
        return {label: dict(meta) for label, meta in self.structure.items()}
