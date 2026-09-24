"""Local-max pricing and fidelity-driven pricing, both off until 7.3 licenses them.

Two rules from ROADMAP 7.2 that price a decision the gate cannot take at face
value, by replacing it in every replicate with the best of its admissible
alternatives at that step and replaying the rest of the sequence normally:

- **local-max pricing** — for a step the agent could not state as a rule, or a
  `pick` whose choice contradicts the rule it declared;
- **fidelity-driven pricing** — for every move of a *type* whose measured
  fidelity, the rate at which the declared rule predicts the agent's choice, sits
  below a pre-registered tolerance (7.3's check 2).

**Neither is licensed.** Both rest on the conjecture that anchoring later moves
on a local maximum is conservative (P4), and **7.3 tests that conjecture; it has
not reported.** So:

- both flags default to **off**, and with them off nothing here changes a null;
- with a flag **on**, every verdict says the pricing is unlicensed, names the
  experiment that would license it, and records which steps were priced.

**When this changes nothing, and why.** For a searcher whose continuation is
already greedy extension, the best admissible one-step move *is* the move it
logged: at a support reached greedily a swap cannot beat the best single feature
and a flip of an unsigned feature is strictly worse. So pricing such a step is a
no-op, exactly as 7.1 found for the fill against greedy continuations
(`tests/test_quixote_pricing.py` pins this). These rules bite on a continuation
the local max does not dominate, which is the case 7.3 is built to exercise.

Nothing in this module asserts the conjecture. If 7.3 finds local-max pricing
liberal anywhere, ROADMAP 7.2 already registers the consequence: rejected picks
drop the run to the declared-class tier instead.
"""
from __future__ import annotations

from dataclasses import dataclass, field

LICENSED_BY = None          # 7.3 has not reported; nothing licenses these yet
UNLICENSED_NOTE = (
    "{which} priced {n} step(s) locally: at each, every replicate takes the best "
    "admissible one-step move instead of the logged one. THIS IS NOT LICENSED. It "
    "rests on the conjecture that anchoring later moves on a local maximum is "
    "conservative (THEORY.md P4), which 7.3's scripted runs test and which has not "
    "reported. Until it does, a verdict that depends on this pricing is not a "
    "certification; ROADMAP 7.2's registered fallback is the declared-class tier.")


@dataclass(frozen=True)
class PricingOptions:
    """Off by default. `fidelity_rates` maps a move kind to its measured
    fidelity; a kind at or below `fidelity_tolerance` is priced locally from its
    first occurrence onward, which is 7.3's check 2 applied to the certifying
    null."""
    local_max: bool = False
    fidelity: bool = False
    fidelity_rates: dict = field(default_factory=dict)
    fidelity_tolerance: float = 0.0

    @property
    def enabled(self) -> bool:
        return self.local_max or self.fidelity

    def low_fidelity_kinds(self) -> set:
        if not self.fidelity:
            return set()
        return {k for k, v in self.fidelity_rates.items() if v <= self.fidelity_tolerance}


DEFAULT = PricingOptions()


def steps_to_price(log, options: PricingOptions = DEFAULT) -> tuple[frozenset, list[str]]:
    """Which steps get local pricing, and the sentences a verdict must carry.

    With both flags off this is empty and says nothing, which is the point: the
    default build prices no step this way.
    """
    if not options.enabled:
        return frozenset(), []

    steps, reasons = set(), []
    records = list(log.records)
    if options.local_max:
        unreplayable = [i for i, r in enumerate(records) if not r.replayable]
        steps.update(unreplayable)
        if unreplayable:
            reasons.append(UNLICENSED_NOTE.format(which="local-max pricing",
                                                  n=len(unreplayable)))
    if options.fidelity:
        low = options.low_fidelity_kinds()
        first = {}
        for i, r in enumerate(records):
            first.setdefault(r.move.kind, i)
        hit = [i for i, r in enumerate(records)
               if r.move.kind in low and i >= first[r.move.kind]]
        steps.update(hit)
        if hit:
            kinds = ", ".join(sorted(low))
            reasons.append(
                UNLICENSED_NOTE.format(which="fidelity-driven pricing", n=len(hit))
                + f" The kinds priced are those at or below the tolerance "
                  f"{options.fidelity_tolerance}: {kinds}.")
    return frozenset(steps), reasons
