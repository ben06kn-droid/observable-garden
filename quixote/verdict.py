"""The Verdict Don Quixote returns.

It carries item 1's bracket and item 6's bits. Both are **declared here and
computed elsewhere**: the bracket's ends are licensed by experiments that have
not reported (7.1 for the lower, 7.3 for the upper), and filling them in now
would be asserting the thing under test. Fields that part two populates are
`None` and say so.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# PASS/FAIL/INADMISSIBLE/UNDECIDABLE/DEGENERATE come from garden.audit; this adds
# one state and one exit code. garden/cli.py's codes are 0/1/2/3/4 and 64.
DEPENDS_ON_JUDGMENT = "DEPENDS_ON_JUDGMENT"
# CERTIFIED is the replay tier's pass (ROADMAP 7.2: CERTIFIED / PASS / CONFIRMED,
# each labelled with its tier). It shares PASS's exit code: both mean the run
# cleared the bar it was priced against, and the tier is in the verdict.
CERTIFIED = "CERTIFIED"
EXIT_CODES = {"PASS": 0, CERTIFIED: 0, "FAIL": 1, "INADMISSIBLE": 2, "UNDECIDABLE": 3,
              "DEGENERATE": 4, DEPENDS_ON_JUDGMENT: 5}


@dataclass
class QuixoteVerdict:
    status: str
    alpha: float

    # -- item 1: the bracket ---------------------------------------------
    # p_frozen is licensed by 7.1's rule 2 (freezing must be liberal for it to
    # be a lower bound). p_upper is the declared-class p-value until 7.3
    # confirms local-max pricing; see prereg/bracketed-verdicts.md.
    p_frozen: float | None = None
    p_upper: float | None = None
    bracket_source: str = "unbuilt: 7.2 part two, pending 7.1 and 7.3"
    responsible_decision: str | None = None     # named when DEPENDS_ON_JUDGMENT
    # Picks whose named choice was not their rule's. The harness ran the rule, so
    # these are REPLAYABLE and do not bracket the run; they are reported because
    # the gap between a stated rule and the one in use is what 7.3 measures.
    contradicted_picks: int = 0

    # -- item 6: bits ------------------------------------------------------
    # Descriptive. Never enters the correction. Computed from the null-max MEAN,
    # which prereg/bits-of-selection.md registers and OPEN_QUESTIONS.md explains.
    effective_breadth: int | None = None
    bits: float | None = None
    bits_bracket: tuple[float, float] | None = None
    bits_ledger: tuple = ()

    # -- the certifying null (7.2 part two; the null 7.1 selected) ---------
    certifying_null: str | None = None
    p_certifying: float | None = None
    p_policy: float | None = None                # exact for a scripted policy
    realized_score: float | None = None
    fill_engaged: int | None = None              # replicates that used the fill
    fill_replicates: int | None = None

    # -- local-max and fidelity-driven pricing (quixote/pricing.py) ---------
    # Empty unless a flag is on, and a flag being on makes the verdict
    # unlicensed: 7.3 has not tested the conjecture both rules rest on.
    locally_priced_steps: tuple = ()
    pricing_licensed: bool | None = None

    # -- provenance --------------------------------------------------------
    n_moves: int = 0
    n_candidates: int = 0
    unreplayable_decisions: tuple = ()
    fingerprint: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.status]

    @property
    def bracket(self) -> tuple[float, float] | None:
        if self.p_frozen is None or self.p_upper is None:
            return None
        return (self.p_frozen, self.p_upper)

    def straddles(self) -> bool | None:
        b = self.bracket
        return None if b is None else (b[0] <= self.alpha <= b[1])

    @property
    def fill_share(self) -> float | None:
        if self.fill_engaged is None or not self.fill_replicates:
            return None
        return self.fill_engaged / self.fill_replicates

    def standard_reasons(self) -> list[str]:
        out = list(self.reasons)
        out.append("Bits are descriptive. They report how much the search "
                   "absorbed and never enter the correction.")
        if self.bracket is None and self.p_frozen is None:
            out.append("No bracket: its ends are licensed by fixed-sequence-replay "
                       "(lower) and 7.3's conjecture test (upper), neither of which "
                       "has reported. This build does not compute it.")
        elif self.bracket is None:
            out.append("Half a bracket: the lower end is fixed-sequence replay, which "
                       "7.1 licensed by measuring freezing as liberal. The upper end "
                       "waits on 7.3's local-max pricing and is not computed.")
        return out
