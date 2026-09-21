# How a pre-registration is written here

One file per experiment, named for it, committed before it runs and removed once
it has reported — the commit is recorded in `EXPERIMENTS.md`, so a removed
pre-registration is still checkable with `git show <commit>:prereg/<file>`.

Four sections: **Question**, **Design**, **Decision rules**, **Cost**.
Amendments and deviations are appended, dated, never edited in.

## Decision rules must match what the procedure claims

This is the rule `calibration-at-1pct` broke, and it cost an arm.

**A validity claim gets a one-sided rule.** Where the theory claims only
`rate ≤ α` — P2 and P3 are the examples, since a searcher submitting less than
the class maximum is *predicted* to come in under nominal — the rule is that the
**upper** end of the interval does not exceed α by more than a stated tolerance.
Never that the interval contains α.

**An exactness rule needs a proposition behind it.** "The interval contains α"
and "KS does not reject uniformity" test exactness, and are admissible only
where the theory predicts exactness. The pre-registration must **name the
proposition that predicts it**. Under P1 an oblivious menu is exactly calibrated
and a KS test is appropriate; under P3 with a sub-maximal searcher it is not, and
will reject whatever the bootstrap does.

**Every rule states a branch for each direction of failure.** A rule with only a
"fails high" branch leaves a real outcome unhandled, and what to do about it then
gets decided after the numbers are in — which is the thing pre-registration
exists to prevent. Say what a low failure means and whether it gates.

## Sizing

Cost is measured end to end at the worker count the real run will use, not
extrapolated from a component sum or a low-worker measurement. Two misses are on
record: `oblivious-calibration` sized from a 4-draw smoke and came in 5× low, and
`calibration-at-1pct` arm B sized from a 2-worker laptop run and came in 4.7×
low, because the workload is memory-bandwidth bound and 32 concurrent workers
contend. See `ROADMAP.md`'s Compute section for the standing pre-launch smoke.

## Amendment 1 — 2026-09-20. The one-sided validity rule was mis-specified.

The wording above — *"the upper end of the interval does not exceed α by more
than a stated tolerance"* — is **wrong**, and it is left in place above because
this file's own convention is that originals stay intact and corrections are
appended.

**Why it is wrong.** The upper end of a Wilson interval at n = 2,000 sits well
above the point estimate, so demanding it stay under `α + tolerance` demands a
point estimate well *below* nominal. At the tolerances the drafts used:

| α | tolerance | rule passes iff | i.e. observed rate | an exactly valid test passes |
|---|---|---|---|---|
| 0.05 | 0.5 pp | k ≤ 90 | ≤ 4.50% | **16.5%** of the time |
| 0.01 | 0.2 pp | k ≤ 14 | ≤ 0.70% | **10.4%** of the time |

A rule that a correctly calibrated procedure fails 84% of the time is not a
validity rule; it is a test for conservatism wearing one's clothes. Concretely,
`calibration-at-1pct` arm D's anchor — which is **exactly calibrated**, k = 110
at α = 0.05 and k = 19 at α = 0.01, with KS not rejecting — fails it at both
levels, upper ends 6.59% and 1.48%. Verified with `scipy.stats.binom.cdf` and
`estimator.metrics.wilson_ci`.

**The corrected rule.** A validity claim fails high **iff the LOWER end of the
Wilson 95% interval exceeds nominal** — that is, only when liberality has been
demonstrated rather than merely not excluded. The **upper** end is still
reported, as *the largest liberality the data do not rule out*, which is the
honest thing it measures. No tolerance parameter appears, because there is
nothing left for it to do.

**Every such rule must state its detectable liberality at the registered n**, so
that "passes" is never read as "is valid" when the experiment could not have
detected the failure. At n = 2,000:

| α | rule fires at | true rate detected with 80% power | false-fire rate if exactly valid |
|---|---|---|---|
| 0.05 | k ≥ 120 (6.00%) | **6.44%** | 2.51% |
| 0.01 | k ≥ 29 (1.45%) | **1.67%** | 3.36% |

So at n = 2,000 a one-sided validity rule sees a procedure that rejects at 6.4%
against a nominal 5%, and is blind to one rejecting at 5.5%. Any pre-registration
claiming more than that from 2,000 draws is overclaiming, and must either raise n
or say what it cannot see.

Applied by appended amendment to `gate-comparison` rule 2,
`fixed-sequence-replay` rule 1, and `heterogeneous-correlation-fat-tails`
rule 2. No result already reported changes: arm D's rules were exactness rules
under P1, not validity rules, and are unaffected.

## Amendment 2 — 2026-09-21. State how often a correct procedure passes.

Before any rule goes live, compute **how often a procedure that is behaving
correctly would pass it**, and write that number into the file beside the rule.

The reason is amendment 1's failure mode generalised. That rule looked
reasonable and a correct procedure failed it 84% of the time; nobody noticed
until the number was computed. A rule whose pass rate under correctness is not
written down has not been checked, however carefully its branches are worded.

At n = 2,000 the standard rules come out as:

| rule | passes if the procedure is correct |
|---|---|
| validity, lower Wilson end > nominal, α = 0.05 | 0.9749 |
| validity, lower Wilson end > nominal, α = 0.01 | 0.9664 |
| exactness, interval contains nominal, α = 0.05 | 0.9548 |
| exactness, interval contains nominal, α = 0.01 | 0.9455 |
| KS at 0.05 | 0.9500 |

These compose. A file making many such checks must also state the **family**
rate, and carry the one-shot replication branch on a registered fresh seed
block that `heterogeneous-correlation-fat-tails` amendment 2(b) established.

**No novelty claims.** No pre-registration, ROADMAP entry or write-up in this
repository describes a method as novel, new, first or unprecedented. Where prior
art matters, either cite what a search found or write "prior art not yet
searched". Novelty is settled separately and deliberately, not asserted in
passing.

## 7.4 ADR amendments and the ancestor guard

`data/adr_guard.py` refuses to build 7.4 features unless every registration
commit it lists is an ancestor of HEAD and `prereg/adr-features.md` and
`prereg/adr-universe.md` have no uncommitted changes.

**Every new ADR amendment must be added to the guard's `REGISTRATION_COMMITS`
in the commit that follows it**, by its full hash. The guard cannot name the
commit that contains it, so the amendment and its guard entry are always two
commits. Until the second one lands, the guard still passes on the older list,
so the new amendment is not enforced. Nothing may run on the panel in between.
