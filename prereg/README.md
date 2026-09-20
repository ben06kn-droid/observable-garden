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
