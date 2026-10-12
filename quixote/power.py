"""`quixote power`: the detection floor, before a search is run.

For a class of N members and Y years of rows, the smallest annualised Sharpe the gate can
certify at the given alpha (the class's critical value), and the true Sharpe a single rule would
need for an 80% chance of clearing it. Built on `garden.preflight`, under its worst case:
members independent of one another. Correlated members act like fewer members, so on real
features the floor is lower than this; `quixote run` prints the bar measured on your panel.
Returns are taken as serially uncorrelated, which overstates power when they are not.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Floor:
    size: int
    years: float
    periods: int
    periods_per_year: int
    alpha: float
    bar: float                  # the smallest Sharpe the gate can certify
    sharpe_for_80pct: float     # the true Sharpe needed for 80% power
    scenario: str = "independent members (the worst case)"

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    def render(self) -> str:
        return (f"class of {self.size:,} members, {self.years:g} years ({self.periods:,} rows at "
                f"{self.periods_per_year}/year), alpha {self.alpha:g}, {self.scenario}:\n"
                f"  smallest Sharpe the gate can certify (the bar): {self.bar:.3f}\n"
                f"  true Sharpe needed for 80% power:                {self.sharpe_for_80pct:.3f}\n"
                "Correlated members act like fewer members, so on real features the bar is lower; "
                "`quixote run` prints the bar measured on your panel.")


def floor(size: int, years: float, *, alpha: float = 0.05, periods_per_year: int = 252) -> Floor:
    from garden.preflight import preflight
    if size < 1 or years <= 0:
        raise ValueError("need a class size >= 1 and years > 0")
    n = max(3, int(round(years * periods_per_year)))
    pf = preflight(int(size), n, reference_sharpe=1.0, periods_per_year=int(periods_per_year), alpha=alpha)
    s = pf.scenarios[0]
    return Floor(size=int(size), years=float(years), periods=n, periods_per_year=int(periods_per_year),
                 alpha=alpha, bar=float(s.critical_value), sharpe_for_80pct=float(s.required_sharpe))
