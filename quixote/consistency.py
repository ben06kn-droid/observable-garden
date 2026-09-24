"""The consistency check: does the agent's stated choice match its stated rule?

ROADMAP 7.2: "For every `pick`, the harness confirms the agent's choice is what
the declared rule selects on the realized data. A pick that contradicts its rule
is rejected as declared and priced locally."

It is **free**, because the harness executes the move: the rule's selection is
computed anyway, so comparing it with the choice the agent names costs one
comparison. A contradicted pick is not an error and does not stop the run; it is
**recorded as not replayable**, which is what makes it eligible for local pricing
when 7.3 licenses that (`quixote/pricing.py`). Until then the verdict reports it
and prices nothing.

What the check can and cannot see: it verifies the *choice*, not the reason. An
agent that names a rule it did not use but whose selection happens to coincide
passes here; that is what 7.3's fidelity measurement is for, and the two are
different questions.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quixote.grammar import Grammar


@dataclass(frozen=True)
class PickCheck:
    step: int
    statistic: str                 # the statistic the rule actually ran under
    declared_statistic: str        # what the pick named; differs if `else` fired
    agent_choice: int | None
    rule_choice: int | None
    agrees: bool

    def reason(self) -> str:
        if self.agent_choice is None:
            return (f"step {self.step}: pick by {self.declared_statistic} was executed by the "
                    "harness, with no separate choice to check.")
        if self.agrees:
            return (f"step {self.step}: pick by {self.declared_statistic} selected feature "
                    f"{self.rule_choice}, which is what the agent named. Consistent.")
        return (f"step {self.step}: pick declared {self.declared_statistic}, whose rule selects "
                f"feature {self.rule_choice} on the realized data, but the agent named "
                f"{self.agent_choice}. REJECTED AS DECLARED: the step is recorded as not "
                "replayable, and is priced locally only where that pricing is enabled and "
                "licensed.")


def _added(before, after) -> int | None:
    held = {k for k, _ in before}
    extra = [k for k, _ in after if k not in held]
    return extra[0] if extra else None


def check_picks(log, spec_class, base: np.ndarray, annualization: float = 1.0) -> list[PickCheck]:
    """Re-derive every pick's rule on the realized data and compare.

    Audits a finished log. `Session.propose` runs the same comparison at the
    moment of the move, which is where a contradicted pick gets flagged.
    """
    g = Grammar(spec_class, base, annualization)
    out = []
    for i, r in enumerate(log.records):
        if r.move.kind != "pick":
            continue
        before = r.information.support_before
        chosen, name = g.pick_choice(before, r.move)
        rule_choice = _added(before, chosen) if chosen else None
        agent = r.move.choice
        out.append(PickCheck(step=i, statistic=name, declared_statistic=r.move.statistic,
                             agent_choice=agent, rule_choice=rule_choice,
                             agrees=(agent is None or agent == rule_choice)))
    return out


def contradicted_steps(checks: list[PickCheck]) -> frozenset:
    return frozenset(c.step for c in checks if not c.agrees)
