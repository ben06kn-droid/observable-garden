"""garden audit: the verdict on a finished search."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable, Literal

import numpy as np

from estimator.bootstrap import sharpe
from garden._engine import null_max_bootstrap
from garden._fmt import pct
from garden.power import bootstrap_p_value, bootstrap_power, critical_value
from garden.transcript import Transcript

Status = Literal["PASS", "FAIL", "INADMISSIBLE", "UNDECIDABLE", "DEGENERATE"]
EXIT_CODES = {"PASS": 0, "FAIL": 1, "INADMISSIBLE": 2, "UNDECIDABLE": 3, "DEGENERATE": 4}

# Degeneracy check (SCOPE.md §11), chosen by experiments/e13_degeneracy_calibration.py's pre-registered rule:
# no refusals across 3,000 dense transcripts; all 23 sparse transcripts whose verdict flips under fixed
# studentization refused.
SUPPORT_MIN = 5
Q_MIN = 0.0
TAIL_SHARE_MAX = 0.001

ROUTES_FORWARD = (
    "Routes forward:\n"
    " 1. Sample splitting — search on part A, evaluate the single selected spec on held-out part B. "
    "No correction needed. Always available.\n"
    " 2. Re-executable search — pass rerun= to garden.audit() and the procedure-level bootstrap applies, "
    "with no reconstruction requirement.\n"
    " 3. Recursive bootstrap (estimator.recursive_bootstrap) — if your specifications are linear in a "
    "fixed base set."
)

DEGENERATE_ROUTES = (
    "Routes forward:\n"
    " 1. Redefine the menu before seeing any results so it leaves out rules that rarely trade, then rerun the "
    "search. Dropping them after looking would make the menu data-dependent.\n"
    " 2. Use a statistic whose denominator cannot collapse: mean return (White 2000) or Sharpe studentized by "
    "the full-sample standard deviation (Hansen 2005). The gate does not offer one yet (OPEN_QUESTIONS.md)."
)

POWER_SCOPE = (
    "This is power for a single pre-specified strategy, not for the search. A search broad enough to reach "
    "strategies carrying an edge can detect more often; one too narrow to reach them detects less often "
    "(SCOPE.md §13)."
)

SCOPE_NOTE = (
    "Corrects for search breadth only. Trading costs, regime change and look-ahead bias are not checked, and "
    "specifications considered but never evaluated are invisible, so this is a lower bound on the correction "
    "required."
)


@dataclass
class Verdict:
    status: Status
    p_value: float
    p_value_is_lower_bound: bool
    sr_reported: float
    sr_deflated: float
    null_max_mean: float
    null_max_band: tuple[float, float]     # 5th-95th percentile of the null maximum
    critical_value: float
    alpha: float
    n_trials: int
    n_periods: int
    periods_per_year: int
    submitted: str
    submitted_rank: int
    method: str                            # "reality_check" | "procedure_level"
    B: int
    block_length: int
    effective_breadth: float               # reported only, never used in the correction
    reference_sharpe: float
    power_at_reference: float              # single pre-specified strategy, not search power (SCOPE.md §13)
    power_floor: float
    menu_kind: str
    degenerate_share: float                # share of Reality Check replicates whose maximum was degenerate
    degenerate_replicates: int
    screen_replicates: int
    degenerate_columns: list[str]          # spec ids that most often set a degenerate maximum
    screened_status: str | None            # verdict with degenerate resamples excluded (Reality Check path)
    variance_floor_binds: int
    sharpe_cap_binds: int
    reasons: list[str]

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.status]

    def to_dict(self) -> dict:
        return {k: _json_safe(v) for k, v in asdict(self).items()}


def _json_safe(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, (list, tuple)):
        return [_json_safe(i) for i in x]
    return x


def effective_breadth(R: np.ndarray) -> float:
    """Participation ratio N^2 / sum(eig^2) of the trial correlation matrix. sum(eig^2) is the
    squared Frobenius norm, computed from whichever Gram matrix is smaller, so N=10,000 is cheap."""
    T, N = R.shape
    if N <= 1:
        return float(N)
    sd = R.std(axis=0, ddof=1)
    live = sd > 0
    Z = np.zeros_like(R)
    Z[:, live] = (R[:, live] - R[:, live].mean(axis=0)) / sd[live]
    G = Z.T @ Z if N <= T else Z @ Z.T
    return float(N ** 2 / (np.sum(G * G) / (T - 1) ** 2))


def _classify(p: float, power: float, alpha: float, power_floor: float) -> str:
    if p < alpha:
        return "PASS"
    return "INADMISSIBLE" if power < power_floor else "FAIL"


def audit(
    transcript: Transcript,
    alpha: float = 0.05,
    B: int = 10_000,
    reference_sharpe: float = 1.0,
    power_floor: float = 0.20,
    block_length: int | None = None,
    seed: int | None = 0,
    rerun: Callable[[int], float] | None = None,
    rerun_B: int = 200,
    support_min: int = SUPPORT_MIN,
    q_min: float = Q_MIN,
    tail_share_max: float = TAIL_SHARE_MAX,
) -> Verdict:
    """Verdict on whether the submitted specification survives correction for the search that produced it.

    rerun: for a menu that is not data-oblivious, a callable that re-executes the whole search (candidate
    generation and selection included) on data whose returns are circularly shifted by `shift` periods
    relative to everything its signals are computed from, and returns the annualized in-sample Sharpe of the
    specification it would submit. It replaces the Reality Check null with the procedure-level one
    (estimator/procedure_level_bootstrap.py), which needs re-executability but no reconstruction.

    support_min, q_min, tail_share_max: the degeneracy check (SCOPE.md §11). A replicate's maximum is
    degenerate when its column's resample has fewer than support_min distinct active periods, or a standard
    deviation below q_min times the full-sample one. The verdict is DEGENERATE when the share of degenerate
    maxima exceeds tail_share_max, or when excluding degenerate resamples would change the verdict.
    """
    R = transcript.returns
    T, N = R.shape
    ann = math.sqrt(transcript.periods_per_year)
    j = transcript.submitted_index
    trial_sr = sharpe(R, axis=0, annualization=ann)
    sr = float(trial_sr[j])
    rank = int(1 + np.sum(trial_sr > sr))
    boot = null_max_bootstrap(R, B=B, block_length=block_length, annualization=ann, seed=seed, track_index=j,
                              support_min=support_min, q_min=q_min)

    oblivious = transcript.menu_kind == "oblivious"
    if not oblivious and rerun is not None:
        shifts = np.random.default_rng(seed).integers(1, T, size=rerun_B)
        null = np.array([float(rerun(int(s))) for s in shifts])
        method = "procedure_level"
    else:
        null = boot.M_b
        method = "reality_check"

    p = bootstrap_p_value(null, sr)
    c = critical_value(null, alpha)
    null_mean = float(null.mean())
    sr_deflated = sr - null_mean
    power = bootstrap_power(boot.tracked, reference_sharpe, c)
    breadth = effective_breadth(R)
    tested_status = _classify(p, power, alpha, power_floor)

    degenerate_k = int(boot.argmax_degenerate.sum())
    share = degenerate_k / B
    worst = Counter(boot.argmax_column[boot.argmax_degenerate].tolist()).most_common(3)
    degenerate_columns = [str(transcript.spec_ids[k]) for k, _ in worst]
    screened_status = None
    if method == "reality_check":
        c_screened = critical_value(boot.M_b_screened, alpha)
        screened_status = _classify(bootstrap_p_value(boot.M_b_screened, sr),
                                    bootstrap_power(boot.tracked, reference_sharpe, c_screened), alpha, power_floor)
    over_limit = share > tail_share_max
    flips = screened_status is not None and screened_status != tested_status

    if not oblivious and rerun is None:
        status = "UNDECIDABLE"
    elif method == "reality_check" and (over_limit or flips):
        status = "DEGENERATE"
    else:
        status = tested_status

    reasons: list[str] = []
    if status == "PASS":
        reasons.append(f"The reported {sr:.2f} clears the critical value of {c:.2f}: it survives correction "
                       f"for the {N:,} specifications this search evaluated.")
        if power < power_floor:
            reasons.append(f"PASS — but power against a single pre-specified strategy with true Sharpe "
                           f"{reference_sharpe:.1f} is only {pct(power)}. Passes from low-power searches overstate "
                           f"the edge: in this project's measurements a passing result's deflated Sharpe was 12x "
                           f"the truth at 6% search power, 3.1x at 9% and 1.6x at 16%, with no overstatement by "
                           f"about 30% (SCOPE.md §12). The single-strategy figure does not say which of those "
                           f"regimes this search is in, so treat {sr_deflated:.2f} as an upper bound on the true "
                           f"edge, not an estimate of it.")
            reasons.append(POWER_SCOPE)
    elif status == "FAIL":
        reasons.append(f"A search of this shape produces a best-of-set Sharpe of {null_mean:.2f} on average "
                       f"with nothing to find. The reported {sr:.2f} does not clear the critical value of "
                       f"{c:.2f}.")
    elif status == "INADMISSIBLE":
        reasons.append(f"Power: {pct(power)} against a single pre-specified strategy with true Sharpe "
                       f"{reference_sharpe:.2f}, below the {pct(power_floor)} floor. Such a strategy would usually "
                       f"fail this search's critical value of {c:.2f}, so not clearing it says little about "
                       f"whether an edge exists. The problem is the design, not the result: run `garden "
                       f"preflight` to size a search that can certify something.")
        reasons.append(POWER_SCOPE)
    elif status == "DEGENERATE":
        causes = []
        if over_limit:
            causes.append(f"{degenerate_k:,} of {B:,} replicates ({share:.1%}, above the {tail_share_max:.1%} "
                          f"limit) took their null maximum from a degenerate resample")
        if flips:
            causes.append(f"excluding degenerate resamples changes the verdict from {tested_status} to "
                          f"{screened_status}")
        reasons.append("The test statistic broke on this menu: " + "; and ".join(causes) + ". A resample is "
                       f"degenerate when a column has fewer than {support_min} distinct active periods in it or "
                       f"its standard deviation falls below {q_min:g} of the full-sample value. Sharpe "
                       f"re-estimated in every replicate explodes there, so the critical value of {c:.2f} "
                       f"measures near-empty resamples rather than the search (SCOPE.md §11).")
        described =[f"{cid} (active on {pct(float((R[:, k] != 0).mean()))} of periods)"
                     for cid, (k, _) in zip(degenerate_columns, worst)]
        reasons.append("Columns that most often set a degenerate maximum: " + ", ".join(described) + ".")
        reasons.append(DEGENERATE_ROUTES)
    else:
        if transcript.menu_kind == "adaptive":
            reasons.append("Adaptive menu, specification class not reconstructable: which specifications were "
                           "evaluated depended on earlier results, so the transcript alone does not license a "
                           "correction.")
        else:
            reasons.append("menu_kind is 'unknown', so the gate cannot assume the menu was fixed in advance. "
                           "If every specification was chosen before any result was seen, declare "
                           "menu_kind='oblivious'. Decision tree: `garden explain menu`.")
        reasons.append(f"Reality Check p-value, shown for reference: {p:.3f}. An adaptive menu biases it "
                       f"downward, so treat it as a lower bound on the true p-value, and {sr_deflated:.2f} as "
                       f"an upper bound on the deflated Sharpe. In this project's adaptive-search experiments "
                       f"a nominal 5% test rejected 12.7–13.6% of true nulls (SCOPE.md §3, §5).")
        if over_limit or flips:
            reasons.append("This Reality Check null is also dominated by degenerate resamples (SCOPE.md §11), so "
                           "the reference p-value above is unreliable in either direction, not only a lower "
                           "bound.")
        reasons.append(ROUTES_FORWARD)

    if status != "DEGENERATE" and degenerate_k and not (status == "UNDECIDABLE" and (over_limit or flips)):
        reasons.append(f"{degenerate_k:,} of {B:,} replicates took their maximum from a degenerate resample; "
                       f"that is within the {tail_share_max:.1%} limit, and excluding them leaves the verdict "
                       f"unchanged.")
    if method == "procedure_level":
        reasons.append(f"Null from re-executing the search on {rerun_B} time-shifted surrogates "
                       f"(procedure-level bootstrap): valid for an adaptive menu, no reconstruction needed. "
                       f"The smallest attainable p-value at this B is {1 / (rerun_B + 1):.3f}.")
    elif oblivious:
        reasons.append("Menu check: PASS — data-oblivious, so the Reality Check is valid for any trial count "
                       "and correlation structure.")
    if rank > 1:
        reasons.append(f"The submitted spec ranked {rank:,} of {N:,} by in-sample Sharpe. The test compares it "
                       f"against the null distribution of the maximum, so for a non-maximal pick the p-value "
                       f"is conservative.")
    reasons.append(f"Effective breadth {breadth:,.1f} of {N:,} (participation ratio of the trial correlations) "
                   f"is reported for information and not used in the correction: the bootstrap already "
                   f"resamples trials jointly, and shrinking N as well would count their correlation twice "
                   f"(SCOPE.md §10).")
    reasons.append(SCOPE_NOTE)

    return Verdict(
        status=status, p_value=p, p_value_is_lower_bound=status == "UNDECIDABLE",
        sr_reported=sr, sr_deflated=sr_deflated, null_max_mean=null_mean,
        null_max_band=(float(np.percentile(null, 5)), float(np.percentile(null, 95))),
        critical_value=c, alpha=alpha, n_trials=N, n_periods=T, periods_per_year=transcript.periods_per_year,
        submitted=transcript.submitted, submitted_rank=rank, method=method, B=len(null),
        block_length=int(boot.block_length), effective_breadth=breadth, reference_sharpe=reference_sharpe,
        power_at_reference=power, power_floor=power_floor, menu_kind=transcript.menu_kind,
        degenerate_share=share, degenerate_replicates=degenerate_k, screen_replicates=B,
        degenerate_columns=degenerate_columns, screened_status=screened_status,
        variance_floor_binds=boot.floor_binds, sharpe_cap_binds=boot.cap_binds, reasons=reasons,
    )
