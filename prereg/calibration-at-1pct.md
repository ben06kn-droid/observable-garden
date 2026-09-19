# calibration-at-1pct: is the gate calibrated at 1%, not just at 5%?

To be committed before running. Code: `experiments/calibration_at_1pct.py`.

## Observed before this pre-registration

On 2026-09-19, while auditing the new manifest, rejection counts were computed
over the 419 graded s0 runs at three levels:

| α | rejections | rate |
|---|---|---|
| 0.10 | 29 | 6.9% |
| 0.05 | 15 | 3.6% |
| 0.01 | 3 | 0.72% |

**These are observed, not pre-registered.** They were produced by counting stored
p-values against three fixed thresholds, which admits no researcher degrees of
freedom, but they were seen before this file existed and no gate can honestly be
built on them afterwards. They are background.

They are also not the evidence. At n = 419 a true rate of 1% has a Wilson
half-width of about 0.95 points, so the interval around 0.72% comfortably
contains both 1% and 0.1%: **the agent runs cannot resolve the 1% tail at all.**
That is the reason the scripted arm below exists, and it is what this
pre-registration turns on.

## Question

A gate used for an allocation decision is run at 1%, not 5%. At 1% the empirical
check has five times fewer events and more of the answer comes from the
bootstrap's tail, where B = 10,000 replicates may not resolve the quantile. Two
things are unknown:

- Is the declared-class null calibrated at 1%, or only at 5%?
- Is B = 10,000 enough to place a 1% critical value?

## Design

**Arm A — the existing s0 runs, re-scored.** Every graded s0 run carries its
p-value as a column of `runs/<batch>/runs.csv`. Report, per model and pooled:
the rejection rate at α ∈ {0.10, 0.05, 0.01} with Wilson 95% intervals, and a
one-sample Kolmogorov–Smirnov test of the p-values against U(0,1).

Each run has a distinct `seed_index` and therefore a distinct DGP draw, so the
p-values are independent and KS applies. Agents in the gate and pushed arms saw
a 5% bar during their search; that changes behaviour, not the validity of the
p-value under the null, and the KS test covers every α at once rather than
privileging the level they were shown. Sonnet (n = 329) and Fable (n = 90) are
reported separately and never pooled with the scripted arm.

**Arm B — scripted, high count.** The agent arm's own configuration: s0, K = 40,
M = 50, T = 5,000, sigma = 1, declared class `SubsetClass(max_size=3,
signed=True)` — the same 82,240-member class the agents were held to — priced by
the moment-based full-class engine, B = 10,000, matching what `watch.open` gave
every agent run.

- Searchers: `Greedy` and `Adaptive`, both oblivious-menu in the sense that
  matters here; the point is the null, not the search.
- n = 5,000 draws per searcher, seeds 100000–104999, used by no earlier
  experiment.
- Readouts per searcher: rejection rate at α ∈ {0.05, 0.01} with Wilson
  intervals, and KS against U(0,1).

At n = 5,000 a true rate of 1% has a Wilson half-width of about 0.3 points, so
the arm can separate 1% from 1.6%.

**Arm C — tail resolution.** The first 500 draws of arm B, re-run at B = 50,000,
everything else identical. This asks whether B = 10,000 places the 1% critical
value, by comparing the two rejection rates on the same draws.

## Decision rules

Fixed now, in order. Arm A gates nothing: it is underpowered at 1% by
construction and is reported for completeness.

1. **Calibration at 1% (primary).** For each searcher in arm B, the Wilson 95%
   interval for the rejection rate at α = 0.01 contains 0.01.
   - **Holds:** the declared-class tier is stated as calibrated at 1% as well as
     at 5%, and the rest of Phase 6 proceeds.
   - **Fails high:** the gate is liberal at 1%. Nothing else in Phase 6 runs
     until it is understood, since every later verdict inherits the null.
2. **Uniformity.** No searcher's KS test rejects at 0.05 in arm B. A rejection
   with rule 1 holding means the distortion is somewhere other than the 1% tail,
   and is reported rather than gating.
3. **Tail resolution.** In arm C, the rejection rate at α = 0.01 under
   B = 50,000 lies inside the B = 10,000 Wilson interval from the same 500
   draws.
   - **Fails:** B = 10,000 does not resolve the 1% quantile. B rises to 50,000
     for every later Phase 6 cell before anything else runs, and the agent arm's
     stored 1% numbers are labelled as under-resolved.

The conjunction that would be worst, and is called now so it cannot be explained
away later: **rule 1 failing high while the 5% rate stays nominal.** That is the
signature of an under-resolved tail rather than a broken null, and rule 3 is what
separates the two.

## Cost

Arm A is seconds and local: it reads five CSV files.

Arms B and C are EC2. Their cost will be **measured by a smoke of at least 50
draws before launch, and the measurement recorded here**, not estimated from
components. `oblivious-calibration` sized itself from a 4-draw smoke, came out
low by a factor of five, and took 7.7 hours on 32 cores instead of "a little
over an hour"; the rule since then is an end-to-end measurement at a draw count
large enough to mean something.
