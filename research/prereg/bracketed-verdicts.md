# bracketed-verdicts (item 1): two p-values for a decision that cannot be replayed

**DRAFT — committed but not live.** Authorises nothing. Built in 7.2's verdict
path; validated in 7.3. Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
replay of an adaptive search's logged decisions inside a data-snooping null,
and no mixed replay/max-over-alternatives pricing. Not a proof of absence.

## Question

Some decisions in an agent's search cannot be replayed on a bootstrap replicate:
they were made on information the harness did not capture, or on reasoning that
cannot be regenerated for a world that never happened. Reporting a single
p-value for such a run requires choosing what to do with those decisions, and
either choice is an assumption. What does it cost to report both?

## Design

For every decision the gate cannot replay, two p-values are computed on the same
resampled index, so they are paired replicate by replicate:

- **`p_frozen`** — the decision is held at its realized value. `fixed-sequence-replay`
  (7.1) predicts this is **liberal**, because freezing a data-chosen stopping
  point conditions the replicate on an event that has not happened to it.
- **`p_upper`** — the decision is priced at the maximum over its alternatives.

**Which bound `p_upper` uses, and why it changes.** Until `7.3` confirms that
local-max pricing is conservative, `p_upper` is the **declared-class** p-value.
P3 makes that valid with no conjecture: the class is fixed before the search, the
null is the maximum over it, and nothing inside moves the bar. After 7.3 confirms
the conjecture, `p_upper` becomes the tighter **local-max** value. The
pre-registration records that the bracket is only as good as its two ends:
**7.1's sign result licenses the lower end, 7.3's conjecture test licenses the
upper end**, and neither has reported.

**New verdict state, `DEPENDS_ON_JUDGMENT`.** Returned when the bracket straddles
α. It names the decision responsible and carries its own exit code, alongside the
existing PASS / FAIL / INADMISSIBLE / UNDECIDABLE / DEGENERATE codes in
`garden/cli.py`.

This mirrors the lower/upper bracket SPA already reports: a range whose width is
the part of the answer the data do not settle.

## Decision rules

Per `prereg/README.md` as amended, with the pass-rate-under-correctness figure
beside each.

1. **The bracket contains the truth (primary, validated in 7.3).** On scripted
   searchers where a true p-value is computable by full policy replay, the
   interval `[p_frozen, p_upper]` contains it on at least 95% of draws.
   *A correct procedure passes this 95% of the time by construction at n = 2,000
   when coverage is exactly 0.95; the rule is therefore read one-sided, on the
   lower Wilson end of the coverage rate falling below 0.95.*
   - *Holds:* the bracket is usable as reported.
   - *Fails low:* coverage is below nominal, which means one end is wrong.
     7.1's sign result says which end to suspect: if `p_frozen` is not liberal,
     the lower end is not a lower bound.
   - *Fails high:* coverage above 0.95 means the bracket is wider than it needs
     to be. Reported as the cost of the conjecture, not as a defect.
2. **`p_upper` is valid on its own (one-sided).** Certifying on `p_upper` alone
   controls type-I at α: the lower Wilson end of its s0 rejection rate does not
   exceed nominal. *Passes 0.9749 / 0.9664 at α = 0.05 / 0.01 for a correct
   procedure.* This is the rule that makes the bracket safe to act on before 7.3
   reports — a run whose whole bracket lies below α certifies with no conjecture.
   - *Fails high:* P3 is violated somewhere upstream; nothing else in this file
     is readable until that is found.
   - *Fails low:* conservative, as P3 predicts, reported with its size.
3. **Bracket width, reported not gated.** The distribution of `p_upper − p_frozen`
   across runs, and the share of runs landing in `DEPENDS_ON_JUDGMENT`. This is
   the measured size of what judgment contributes, and it is what
   `pivotal-interrogation` (item 7) spends agent calls to resolve.

## Cost

Free. Both ends are computed from nulls the gate already prices; no additional
bootstrap and no agent calls. The `DEPENDS_ON_JUDGMENT` path costs one extra
field in the Verdict.

## Amendment 1 — 2026-09-30, registered before 6.5. No fall-through to the class tier at α

**Registered:**

> **A `DEPENDS_ON_JUDGMENT` verdict does not fall through to the declared-class tier
> at α.** A bracketed run is not re-tested against the class gate and certified if
> that passes. **The holdout tier is the resolution**, not the other in-sample tier.

**The argument, which is about selection and not about either test's validity.**
Both tiers are valid tests on their own. An **OR** of them is not, once the choice of
which to apply is made **after seeing the data** — and that is exactly what
fall-through is: the class tier is consulted *because* the replay tier declined.

Consider the agent the rule has to survive: one that **follows its declared rule when
the rule is clearing, and rewrites it when the rule is about to stop a search that
looks promising.** Under fall-through that agent gets the replay tier when its rule
held and the class tier when it did not. Each test alone rejects a true null with
probability α; the agent faces the **union**, and because it chooses which branch it
lands in by looking at the data, its false-certification probability approaches
**2α**. Nothing in either tier's construction prevents this — the leakage is in the
disjunction, not in the tests.

**The 7.3 agent cell shows the agent that does this is not hypothetical.** Trigger
changes bound on **25% of s0 runs and 47.5% of s3 runs**, and check 4's decomposition
found that the class tier's entire apparent power advantage lay on exactly the runs
the replay tier declined — 14 of its extra rejections on the 19 bracketed s3 runs,
against 12 rejections on the 21 runs both tiers priced. **Fall-through would have
converted that decline into a certificate on about half the arm.**

**What replaces it.** A bracketed run reports its bracket — the fixed-sequence p as
the liberal end, the declared-class p as the conservative end — and the commitment
result beside it, and it is **resolved out of sample**. That is slower and it is the
only resolution that does not buy certainty with size.
