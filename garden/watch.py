"""garden watch: a search's running standing against a bar fixed before it started.

STEP 0 -- CONTRACT ONLY. The types and signatures below are the agreed surface;
`open`, `evaluate` and `submit` raise NotImplementedError until step 1. The
invariants they must satisfy are written as tests now (tests/test_watch.py),
skipped until the implementation lands, so the contract cannot drift silently.

What it is
----------
A wrapper on `environments.sandbox.Sandbox` that gives a searcher a running view
of where it stands against a search-adjusted bar, and runs `garden.audit` at
submit time. It is the agent-facing form of the gate.

The constraint it is built around
---------------------------------
Any feedback watch gives makes the next candidate depend on realized results, so
a watched search's menu is adaptive *by construction* and the realized-menu tier
is unavailable to it -- permanently, not pending better estimation. Watch
therefore runs in the declared-class tier (THEORY.md P3):

    the searcher declares Theta before it sees anything,
    the null is the maximum over Theta,
    and the bar is fixed from that moment.

Nothing the searcher does inside Theta moves the bar. That is what makes
unlimited querying safe here and is the whole reason watch can exist: the
literature's adaptive-query problem (Blum & Hardt's Ladder; Hardt's error
scaling in the number of running-best updates) prices *repeated access to a
holdout*. Watch never grants that. It answers every query from one null
distribution computed once, before any evaluation.

So watch adds enforcement, standing, diagnostics and a verdict at submit -- not
a per-query price. The only lever that changes power is the size of Theta at
declaration, which is what `garden preflight` sizes.

Class kinds: SubsetClass now, ExplicitClass deferred
----------------------------------------------------
`full_class_null_max` is moment-based and takes a `SubsetClass` (it needs
`.members(K, m)` and `.max_size`), so that is the class kind watch prices at
open, and `SubsetClass.contains(weights)` is what makes `evaluate`-time
membership refusal cheap.

`ExplicitClass` is **deferred, not excluded**, and the distinction matters. It
is a second code path, not a limitation of the declared-class tier: `garden.audit`
already prices an explicit class by running the Reality Check directly on the
supplied `class_returns`, and `garden.transcript` already checks membership by
spec id rather than by weight vector. Watch could do both -- draw the bar once
at open from the class streams, and refuse by id in `evaluate` -- and the tier
argument (bar fixed before any evaluation, nothing inside Theta moves it) is
untouched by which kind of class it is.

It is deferred because it is a distinct path to build and test, not because it
cannot work, and step 4 should not rediscover that. An LLM agent's natural class
is closer to ExplicitClass than to SubsetClass: a tool grammar emits rules, most
of which are not equal-weight feature subsets. See OPEN_QUESTIONS.md.

Non-goals (stated here so they are not quietly relaxed later)
-------------------------------------------------------------
- No realized-menu verdicts for a watched search, ever.
- No recursive tier unless the searcher is scripted and re-executable; then
  watch may offer it at submit as a *second*, labeled verdict.
- No claim about trading costs, regime change, or look-ahead in the features.
- Not a Thresholdout. A noisy reusable holdout is a different estimator with
  different guarantees; if wanted it is a separate module that feeds a declared
  class for a certified second stage.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from environments.sandbox import Sandbox, Specification
from garden.audit import Verdict
from garden.spec_class import SubsetClass

# Watch always records this menu_kind: a watched search is adaptive by
# construction, and this is what routes garden.audit() to the full-class branch.
WATCHED_MENU_KIND = "adaptive"

OpenStatus = ("OK", "INADMISSIBLE")


@dataclass
class WatchState:
    """What `open` returns: the bar, and whether searching is worth starting.

    `bar` is the null-maximum distribution over the whole declared class, drawn
    once. `critical_value` is the Sharpe a submission must strictly exceed.
    Both are fixed at open and never recomputed."""
    status: str                     # "OK" | "INADMISSIBLE"
    critical_value: float
    bar: np.ndarray                 # (B,) null maximum over Theta
    power_at_reference: float       # analytic, single pre-specified strategy (SCOPE.md 13)
    class_name: str
    class_size: int
    n_features: int
    n_periods: int
    periods_per_year: int
    alpha: float
    reference_sharpe: float
    power_floor: float
    block_length: int
    B: int
    variance_floor_binds: int
    sharpe_cap_binds: int
    reasons: list[str] = field(default_factory=list)
    # Set when status is INADMISSIBLE: the largest class that would clear the floor.
    admissible_class_size: int | None = None

    def to_dict(self) -> dict:
        out = {k: v for k, v in asdict(self).items() if k != "bar"}
        out["bar_mean"] = float(np.mean(self.bar))
        out["bar_band"] = [float(np.quantile(self.bar, 0.05)), float(np.quantile(self.bar, 0.95))]
        return out


@dataclass
class WatchReport:
    """What `evaluate` returns: this candidate, and where the search stands.

    `cleared` is the invariant that matters -- it must equal the final verdict's
    PASS for this same specification. It is computed against the bar fixed at
    open, so it cannot be moved by anything the search has done since."""
    in_class: bool
    sr_is: float
    cleared: bool
    margin_to_bar: float            # sr_is - critical_value; positive means clearing
    best_so_far: float
    best_so_far_cleared: bool
    n_evaluated: int
    n_class: int
    critical_value: float
    call_index: int
    spec_name: str
    diagnostics: dict = field(default_factory=dict)   # step 2; empty until then

    def to_dict(self) -> dict:
        return asdict(self)


class Watch:
    """Opened by `watch.open(...)`, not constructed directly."""

    def __init__(self, sandbox: Sandbox, state: WatchState):
        self._sandbox = sandbox
        self.state = state
        self._reports: list[WatchReport] = []
        self._best = -np.inf
        self._off_tier_reason: str | None = None

    @property
    def log(self) -> list[WatchReport]:
        return list(self._reports)

    @property
    def sandbox(self) -> Sandbox:
        """The wrapped sandbox. Exposed so a harness can build a transcript; a
        searcher under watch should go through `evaluate`/`submit`."""
        return self._sandbox

    def evaluate(self, spec: Specification) -> WatchReport:
        """Evaluate one specification and report standing against the fixed bar.

        Never touches out-of-sample data -- it delegates to `Sandbox.evaluate`,
        whose contract already guarantees that. Refuses a specification outside
        the declared class rather than silently taking the run off-tier."""
        raise NotImplementedError("step 1")

    def status(self) -> WatchReport:
        """The most recent report, without evaluating anything. This is the tool
        an agent polls; the control arm of the experiment is denied it."""
        raise NotImplementedError("step 1")

    def submit(self, spec: Specification, predicted_oos) -> Verdict:
        """Submit, then return the full audit verdict on the resulting transcript."""
        raise NotImplementedError("step 1")


def open(
    sandbox_or_base_returns,
    spec_class: SubsetClass,
    alpha: float = 0.05,
    reference_sharpe: float = 1.0,
    power_floor: float = 0.20,
    periods_per_year: int = 252,
    B: int = 10_000,
    block_length: int | None = None,
    seed: int | None = 0,
) -> Watch:
    """Price the bar over `spec_class` and decide whether the search is worth starting.

    This is the only moment the design is still changeable, so it is the only
    moment an INADMISSIBLE verdict is useful: it is returned *before* any
    evaluation, with the largest class size that would clear the power floor.

    `spec_class` must be a SubsetClass (see the tier note in the module
    docstring). Accepts either a configured Sandbox or a (T, K) base-return
    matrix; in the latter case a Sandbox is built around it with the class
    enforced, so `spec_class_source` records "sandbox"."""
    raise NotImplementedError("step 1")
