"""garden preflight: before a search, how much power will its intended breadth leave?"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from garden._fmt import pct
from garden.power import analytic_power, null_max_critical_value, required_sharpe

BREADTHS = (1, 10, 100, 1_000, 10_000)
TARGET_POWER = 0.80


@dataclass
class Scenario:
    label: str
    rho: float
    critical_value: float
    power: float
    required_sharpe: float
    breadth_table: list[tuple[int, float]]


@dataclass
class PreflightResult:
    n_specs: int
    n_periods: int
    periods_per_year: int
    reference_sharpe: float
    alpha: float
    power_floor: float
    scenarios: list[Scenario]
    reasons: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _scenario(label, rho, n_specs, n_periods, ppy, reference_sharpe, alpha) -> Scenario:
    c = null_max_critical_value(n_specs, n_periods, ppy, alpha, rho)
    table = [
        (n, required_sharpe(null_max_critical_value(n, n_periods, ppy, alpha, rho), n_periods, ppy, TARGET_POWER))
        for n in BREADTHS
    ]
    return Scenario(
        label=label, rho=rho, critical_value=c,
        power=analytic_power(reference_sharpe, c, n_periods, ppy),
        required_sharpe=required_sharpe(c, n_periods, ppy, TARGET_POWER),
        breadth_table=table,
    )


def preflight(n_specs: int, n_periods: int, reference_sharpe: float, periods_per_year: int = 252,
              alpha: float = 0.05, power_floor: float = 0.20, rho: float | None = None) -> PreflightResult:
    if n_specs < 1 or n_periods < 3 or periods_per_year < 1:
        raise ValueError("need n_specs >= 1, n_periods >= 3, periods_per_year >= 1")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    if rho is not None and not 0 <= rho <= 1:
        raise ValueError("rho must be in [0, 1]")

    args = (n_specs, n_periods, periods_per_year, reference_sharpe, alpha)
    scenarios = [_scenario("independent", 0.0, *args)]
    if rho is not None:
        scenarios.append(_scenario(f"ρ={rho:.2f}", rho, *args))
    indep = scenarios[0]
    powers = [s.power for s in scenarios]

    subject = f"Power for a single pre-specified strategy with true Sharpe {reference_sharpe:.2f}"
    if rho is None:
        power_line = f"{subject}: {pct(indep.power)}, assuming independent trials."
    else:
        power_line = (f"{subject}: {pct(indep.power)} assuming independent trials, "
                      f"{pct(scenarios[1].power)} at ρ={rho:.2f}.")
    if max(powers) < power_floor:
        floor_line = (f"Below the {pct(power_floor)} floor in every scenario: an audit of this search would "
                      f"likely return INADMISSIBLE. Narrow the search or lengthen the sample.")
    elif min(powers) < power_floor:
        floor_line = (f"Below the {pct(power_floor)} floor if trials are independent, above it at ρ={rho:.2f}: "
                      f"whether this design can certify anything depends on how correlated the "
                      f"specifications turn out to be.")
    else:
        floor_line = f"Above the {pct(power_floor)} floor."

    reasons = [
        f"{power_line} {floor_line}",
        "These are single-strategy figures, not search power. A search broad enough to reach strategies carrying "
        "an edge can detect more often; one too narrow to reach them detects less often (SCOPE.md §13).",
        "Independent trials are the worst case, since correlated trials act like fewer trials. Returns are "
        "assumed serially uncorrelated; autocorrelation widens the Sharpe's standard error and lowers power, "
        "which is not modeled here.",
        "Power depends jointly on the test, the data and the search. What transfers is the shape (rising "
        "with effect size, falling with breadth), not the exact thresholds.",
    ]
    return PreflightResult(
        n_specs=n_specs, n_periods=n_periods, periods_per_year=periods_per_year,
        reference_sharpe=reference_sharpe, alpha=alpha, power_floor=power_floor,
        scenarios=scenarios, reasons=reasons,
    )
