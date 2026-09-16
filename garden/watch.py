"""garden watch: a search's running standing against a bar fixed before it started.

What it is
----------
A wrapper on `environments.sandbox.Sandbox` that gives a searcher a running view
of where it stands against a search-adjusted bar, and runs `garden.audit` at
submit time. It is the agent-facing form of the gate.

Usage
-----
    cls = SubsetClass(max_size=2)
    sandbox = Sandbox(data, periods_per_year=252, spec_class=cls)
    w = watch.open(sandbox, cls)
    if w.state.status == "INADMISSIBLE":
        ...                      # redesign now; w.state.admissible_class_size says how narrow
    r = w.evaluate(spec)         # as often as wanted; the bar does not move
    v = w.submit(spec, predicted_oos)

`open` takes a configured Sandbox. The step 0 contract also offered a bare
(T, K) base-return matrix; that is not implementable against the real Sandbox,
whose `evaluate` computes `x_in @ weights` across assets and so needs the full
(T, M, K) panel, which a (T, K) matrix of per-feature returns cannot
reconstruct. Build the Sandbox first, passing the class to it so membership is
enforced and `spec_class_source` records "sandbox".

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

from environments.sandbox import Distribution, Sandbox, Specification
from garden._full_class_engine import full_class_null_max
from garden.audit import Verdict, audit
from garden.power import analytic_power, critical_value, null_max_critical_value, required_sharpe
from garden.spec_class import SubsetClass
from garden.transcript import from_sandbox

_IMPLEMENTED = True

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

    def __init__(self, sandbox: Sandbox, state: WatchState, seed: int | None = 0):
        self._sandbox = sandbox
        self.state = state
        self._seed = seed
        self._reports: list[WatchReport] = []
        self._best = -np.inf

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
        the declared class rather than silently taking the run off-tier: the
        Sandbox raises, and the refusal is re-raised with the class named.

        Nothing here recomputes the bar. `cleared` compares this specification's
        in-sample Sharpe against the critical value fixed at open, which is why
        the search can call this as often as it likes."""
        result = self._sandbox.evaluate(spec)      # raises if outside the class
        sr = float(result.sharpe)
        self._best = max(self._best, sr)
        c = self.state.critical_value
        report = WatchReport(
            in_class=True,
            sr_is=sr,
            cleared=sr > c,
            margin_to_bar=sr - c,
            best_so_far=self._best,
            best_so_far_cleared=self._best > c,
            n_evaluated=len(self._reports) + 1,
            n_class=self.state.class_size,
            critical_value=c,
            call_index=result.call_index,
            spec_name=spec.name,
        )
        self._reports.append(report)
        return report

    def status(self) -> WatchReport:
        """The most recent report, without evaluating anything. This is the tool
        an agent polls; the control arm of the experiment is denied it."""
        if not self._reports:
            raise ValueError("nothing evaluated yet, so there is no standing to report")
        return self._reports[-1]

    def submit(self, spec: Specification, predicted_oos) -> Verdict:
        """Submit, then return the full audit verdict on the resulting transcript.

        The transcript records menu_kind="adaptive", which is what routes
        `audit` to the full-class branch -- the only tier a watched search is
        entitled to."""
        if not isinstance(predicted_oos, Distribution):
            predicted_oos = Distribution.degenerate(float(predicted_oos))
        self._sandbox.submit(spec, predicted_oos)
        transcript = from_sandbox(self._sandbox, menu_kind=WATCHED_MENU_KIND)
        return audit(
            transcript,
            alpha=self.state.alpha,
            B=self.state.B,
            reference_sharpe=self.state.reference_sharpe,
            power_floor=self.state.power_floor,
            block_length=self.state.block_length,
            seed=self._seed,
        )


def largest_admissible_class_size(
    n_periods: int, periods_per_year: int, reference_sharpe: float,
    alpha: float, power_floor: float, ceiling: int,
) -> int | None:
    """The largest number of specifications whose analytic power at
    `reference_sharpe` still clears `power_floor`, or None if even one does not.

    Power falls monotonically in breadth at fixed sample length, so this is a
    binary search rather than a sweep. Independent trials are assumed, which is
    the worst case: correlated specifications act like fewer of them, so this is
    a conservative floor on how wide the class may be."""
    def power_at(n: int) -> float:
        c = null_max_critical_value(n, n_periods, periods_per_year, alpha, 0.0)
        return analytic_power(reference_sharpe, c, n_periods, periods_per_year)

    if power_at(1) < power_floor:
        return None
    lo, hi = 1, max(1, ceiling)
    if power_at(hi) >= power_floor:
        return hi
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if power_at(mid) >= power_floor:
            lo = mid
        else:
            hi = mid - 1
    return lo


def open(
    sandbox: Sandbox,
    spec_class: SubsetClass,
    alpha: float = 0.05,
    reference_sharpe: float = 1.0,
    power_floor: float = 0.20,
    B: int = 10_000,
    block_length: int | None = None,
    seed: int | None = 0,
) -> Watch:
    """Price the bar over `spec_class` and decide whether the search is worth starting.

    This is the only moment the design is still changeable, so it is the only
    moment an INADMISSIBLE verdict is useful: it is returned *before* any
    evaluation, naming the largest class size that would clear the power floor.

    Takes a configured `Sandbox`. The step 0 contract also offered a bare
    (T, K) base-return matrix; that is not implementable against the real
    Sandbox, whose `evaluate` needs the full (T, M, K) asset panel to compute
    `x_in @ weights` across assets, and a (T, K) matrix of per-feature returns
    cannot reconstruct it. Build the Sandbox, then open a watch on it.

    Pass the class to the Sandbox as well (`Sandbox(..., spec_class=cls)`) so
    membership is enforced at `evaluate` and `spec_class_source` records
    "sandbox" -- fixed before the search by construction, which is the tier's
    premise. `open` refuses a Sandbox carrying a different class."""
    if not isinstance(spec_class, SubsetClass):
        raise ValueError(
            f"watch prices its bar with the moment engine, which takes a SubsetClass; got "
            f"{type(spec_class).__name__}. An ExplicitClass is a deferred second code path, "
            f"not a limitation of the tier -- see OPEN_QUESTIONS.md."
        )
    enforced = getattr(sandbox, "spec_class", None)
    if enforced is not None and enforced != spec_class:
        raise ValueError(f"the sandbox enforces {enforced.name}, not {spec_class.name}")

    base = sandbox.base_feature_columns()            # (T, K), adds nothing to the transcript
    T, K = base.shape
    ppy = sandbox.periods_per_year
    ann = np.sqrt(ppy)
    class_size = spec_class.size(K)

    bar, L, floor_binds, cap_binds = full_class_null_max(
        base, spec_class, B=B, block_length=block_length, annualization=ann, seed=seed)
    c = critical_value(bar, alpha)
    power = analytic_power(
        reference_sharpe, null_max_critical_value(class_size, T, ppy, alpha, 0.0), T, ppy)

    admissible = None
    reasons = []
    if power >= power_floor:
        status = "OK"
        reasons.append(
            f"Class {spec_class.name} holds {class_size:,} specifications. Power for a single "
            f"pre-specified strategy at Sharpe {reference_sharpe:.2f} is {power:.1%}, above the "
            f"{power_floor:.0%} floor. The bar is fixed from now on: nothing evaluated inside the "
            f"class moves it."
        )
    else:
        status = "INADMISSIBLE"
        admissible = largest_admissible_class_size(
            T, ppy, reference_sharpe, alpha, power_floor, ceiling=class_size)
        reasons.append(
            f"Class {spec_class.name} holds {class_size:,} specifications, leaving {power:.1%} power "
            f"at Sharpe {reference_sharpe:.2f}, below the {power_floor:.0%} floor. A search this wide "
            f"could not certify an edge even if it found one."
        )
        reasons.append(
            f"At most {admissible:,} specifications would clear the floor on {T} periods."
            if admissible is not None else
            f"No class size clears the floor on {T} periods, not even a single pre-specified "
            f"specification. Lengthen the sample or raise the reference Sharpe."
        )
        reasons.append("Returned before any evaluation, while the design can still be changed.")
    reasons.append(
        "Power is for a single pre-specified strategy, not for the search (SCOPE.md §13), and "
        "assumes independent specifications, which is the worst case."
    )

    state = WatchState(
        status=status, critical_value=c, bar=bar, power_at_reference=power,
        class_name=spec_class.name, class_size=class_size, n_features=K, n_periods=T,
        periods_per_year=ppy, alpha=alpha, reference_sharpe=reference_sharpe,
        power_floor=power_floor, block_length=L, B=B,
        variance_floor_binds=floor_binds, sharpe_cap_binds=cap_binds,
        reasons=reasons, admissible_class_size=admissible,
    )
    return Watch(sandbox, state, seed=seed)
