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

## Amendments

**1 — 2026-09-19, before any arm B or C run.** The sizing smoke above is
skipped, deliberately. The instance bills $1.64/hour, so a five-fold sizing miss
of the kind `oblivious-calibration` suffered costs about $10 rather than a lost
window, and both arms checkpoint every 25 draws, so a run that overruns resumes
rather than restarts. The cost of the smoke exceeded what it would buy.

The laptop measurement stands in its place and is recorded here: **34.0 s per
draw** at B = 10,000, measured end to end over 2 draws with `--workers 2`,
implying 47.2 CPU-hours for arm B's 5,000 draws, about 1.5 hours on 32 cores.
Arm C is projected at roughly 22 CPU-hours on the same basis.

What this gives up, stated rather than glossed: that measurement used two
workers, so it does not exercise the memory and core contention of 32 workers
each holding a (5000, 50, 40) panel — which is the specific failure the smoke
existed to catch. If the instance's per-draw cost departs materially from 34 s,
that is the likely reason, and each run's own COST block records the measured
figure.

**2 — 2026-09-20, before the arm it adds runs. Arm D, the exhaustive searcher.**
Arms B and C cannot answer this pre-registration's question, for the reason
Deviation 1 records. Arm D is the control that can.

**Why it can.** `ExhaustiveClass` submits the argmax over the declared class, so
`sr_sel = max_Θ SR_θ` exactly. P2's inequality then binds with equality and its
conservatism vanishes. What remains is P1: the class is fixed before the data is
seen, so the statistic is the maximum over a data-independent menu, and P1
predicts the bootstrap p-value is exactly calibrated up to `o(1)`. **Exactness is
predicted here, by P1, which is why exactness rules are admissible in this arm
and were not in arm B.** Any excess rejection at α = 0.01 is then a property of
the bootstrap — the `o(1)`, at B = 10,000, in the tail — which is what this
pre-registration set out to measure.

**Design.** s0, arm B's configuration exactly: K = 40, M = 50, T = 5,000,
sigma = 1, class `SubsetClass(max_size=3, signed=True)`, 82,240 members.

- n = 2,000 draws on **seeds 100000–101999**, arm B's first 2,000, so every draw
  and every bootstrap null is identical to one arm B already computed and the
  three searchers are exactly paired.
- B = 10,000, matching arm B and `watch.open`.
- A paired **B = 50,000** subsample on the first 500 of those draws.
- Recorded per draw, so no later arm has to recompute a null: the observed class
  maximum, the p-value, and the null-max quantiles at 0.90 / 0.95 / 0.99 / 0.999.
  Arm B stored only `null_max_mean`, which is why arm D cannot reuse it and must
  pay for the bootstrap again.

- **The unsigned sublattice, for rule 4.** The observed maximum over the
  *unsigned* sublattice (10,700 members, what `Greedy` and `Adaptive` can reach)
  is stored alongside the signed one. Because arm D recomputes each draw's `M_b`
  on arm B's seeds, all four statistics can be scored against the **same signed
  class null** at no extra cost, and the four p-values are stored per draw.

Finding the class maximum is free — 7 ms against ~160 s for the bootstrap, and
the unsigned pass is another 1 ms — so arm D costs what arm B cost per draw and
nothing more.

**The observed statistic is the replicate statistic.** Not merely both "a Sharpe":
`full_class_observed_max` applies the same variance estimator (`ddof=1`, via the
same `T/(T-1)` rescaling), the same annualization, and the same two guards
(`VARIANCE_FLOOR`, `SHARPE_CAP`) in the same order and against the same reference
variance as `full_class_null_max`. Verified by feeding the null engine an
identity resample and requiring the variances to agree: they match to 9.4e-16
(`tests/test_exhaustive_class.py`). Without this the arm would compare two
slightly different statistics and attribute the difference to the bootstrap.

**Tolerance for the p-value's discreteness.** `p = (1 + #{M_b >= sr}) / (B + 1)`
is conservative by construction: the attainable rejection probability under
exact uniformity is `(floor(α(B+1) - 1) + 1) / (B + 1)`, which at B = 10,000 is
0.0099990, 0.0499950 and 0.0999900 against nominal 0.01, 0.05 and 0.10 —
shortfalls of 1.0e-6, 5.0e-6 and 1.0e-5. At n = 2,000 the sampling standard
error at 1% is 0.0022, so the discreteness is four orders of magnitude below the
noise. **A rate below nominal by no more than the shortfall above is not a
failure of rules 1 or 2**; the halt is one-sided and only an excess triggers
it.

**Decision rules.** Per `prereg/README.md`: exactness is claimed, the
proposition predicting it is named above, and each rule states both directions.

1. **Exactness at 1% (primary).** The Wilson 95% interval for the rejection rate
   at α = 0.01 contains 0.01.
   - **Holds:** B = 10,000 resolves the 1% tail. The agent arm's stored 1%
     numbers stand, and Phase 6 proceeds.
   - **Fails high:** the tail is under-resolved and the bootstrap over-rejects
     where it matters most. B rises to 50,000 for every later Phase 6 and
     Phase 7 cell before anything else runs, and the agent arm's 1% figures are
     relabelled as under-resolved. This is the original fails-high branch, now
     attached to a searcher that can actually trigger it.
   - **Fails low:** the bootstrap is conservative even against the class
     maximum, which P1 does not predict and which no searcher-position argument
     can explain. Report it, and treat the declared-class tier's stated size as
     an upper bound rather than a rate.
2. **Exactness at 5% and 10%.** The same intervals contain 0.05 and 0.10. Both
   directions reported. A failure at 1% with 5% and 10% holding is the tail
   signature; a failure at every level is a bootstrap problem, not a tail one.
3. **Uniformity.** KS against U(0,1) does not reject at 0.05. Admissible here and
   not in arm B for the same reason as rule 1. A rejection with rules 1 and 2
   holding locates the departure away from the tested levels and is reported,
   not gating.
4. **Secondary — P2's ordering, and what confines Adaptive.** Predicted
   direction: conservative, by P2. One-sided, per `prereg/README.md`, and
   **no halt is attached** — this rule decomposes a known effect, it does not
   gate anything.
   - *Ordering.* On every paired draw, all four scored against the same signed
     class null:
     `p_exhaustive-signed ≤ p_exhaustive-unsigned ≤ p_adaptive ≤ p_greedy`.
     Reported as the share of draws satisfying the full chain, and the share
     satisfying each link. P2 predicts all four links on every draw; the
     one-sided reading is that no link may be violated in the *liberal*
     direction, and the chain holding is not itself evidence of anything beyond
     P2 being correctly implemented.
   - *Decomposition.* Arm B measured Adaptive at 1.0% against a nominal 5%.
     The gap between `p_exhaustive-signed` and `p_exhaustive-unsigned` is the
     cost of **confinement** to the sublattice; the gap between
     `p_exhaustive-unsigned` and `p_adaptive` is the cost of **sub-maximal
     search within it**. Reported as rejection rates at 10/5/1% for all four,
     on the paired draws, so the 1.0% is split into its two parts.
   - *Failure.* A liberal violation of any link falsifies P2 as implemented and
     is investigated before arm D's primary rules are read, since they rest on
     the same equality.

5. **Tail resolution, superseding arm C's rule 3 as the evidence.** On the 500
   paired draws, the rejection rate at α = 0.01 under B = 50,000 lies inside the
   B = 10,000 Wilson interval from the same draws. Arm C asks this of searchers
   whose p-values are almost all near 1, where neither bootstrap size produces
   rejections to compare; arm D asks it where rejections occur at the nominal
   rate. **Arm C's rule 3 is still reported exactly as written** — it was
   pre-registered and it ran — and this rule supersedes it as the evidence on
   which the tail-resolution question is decided. If the two bootstrap sizes
   disagree here, B = 50,000 is the figure to trust and rule 1's fails-high
   branch applies.

**Cost.** To be stated from the measured per-draw figure after the worker-scaling
diagnosis, not from arm B's 159.7 s — that number is itself the thing under
investigation. At 159.7 s it would be 2,000 × 159.7 / 32 ≈ 2.8 h for the
B = 10,000 pass and roughly 3.5 h for the 500-draw B = 50,000 pass. Not launched
until the scaling curve is in and the budget rescaled.

**3 — 2026-09-20, before arm D runs. What rule 4's chain actually rests on.**
Amendment 2's rule 4 presents its four-term ordering as though P2 guaranteed
every link. P2 does not. Amendment 2's text stands as committed; this states
what each link rests on and what a violation of it means. All statements are
about p-values scored against the **same signed class null**, where
`p = (1 + #{M_b >= sr}) / (B + 1)` is nonincreasing in `sr`, so each ordering
below is the image of an ordering on submitted Sharpes.

**Links 1 and 2 — deterministic, from set inclusion.**
`p_exhaustive-signed ≤ p_exhaustive-unsigned ≤ p_adaptive`. The signed class
contains the unsigned sublattice, and the sublattice contains everything
`Adaptive` can construct, so each term is a maximum over a superset of the next.
Expected on **100% of draws**. A violation is an implementation bug — in the
member enumeration, the weight construction, or the pairing of nulls — and not a
statistical result. **Investigate before reading arm D's primary rules**, which
rest on the same equality between `sr_sel` and the class maximum.

**Link 3 — also deterministic, which amendment 2 did not establish and this
amendment does.** `p_adaptive ≤ p_greedy`. Checked against the implementation
rather than assumed:

- `searchers/scripted.py:48-51`, inside `_greedy_forward_selection`: all `K`
  singles are evaluated unconditionally, `for k in range(K)`, and the best is
  kept. There is no early exit from that sweep.
- `searchers/scripted.py:62`: an extension round breaks unless
  `round_best_score > best_score`, so `best_score` begins at the maximum single
  and is monotone non-decreasing thereafter.
- `Adaptive.__init__` takes `max_features` and `seed` only. It has **no trial
  budget** — unlike `GridSearch`, which takes `max_trials` — so no budget can
  truncate the singles sweep. Arm B ran `Adaptive(max_features=3, seed=seed)`.
- `Greedy.run` evaluates the same `K` singles through the same sandbox and
  submits the best, so the two searchers' single-feature Sharpes are identical
  values, not merely equal in distribution.

Therefore `sr_adaptive >= sr_greedy` on every draw, with equality exactly when
no extension improves on the best single. Link 3 takes the same treatment as
links 1 and 2: expected on 100% of draws, a violation is an implementation bug,
and it is investigated before the primary rules are read.

**What this changes in rule 4.** Nothing in its readouts, its one-sidedness, or
its lack of a halt. The decomposition it reports — confinement against
sub-maximal search — is unaffected. What changes is the standard of evidence: no
link is descriptive, so "the share of draws satisfying the chain" is a
correctness check expected to read 100%, not a measurement with an interesting
distribution. Any figure below 100% on any link stops arm D.

**4 — 2026-09-20, before arm D runs. B is not a calibration knob, and rule 1's
remedy was wrong.**

Amendment 2's rule 1 says of a high rejection rate at 1%: *"the tail is
under-resolved and the bootstrap over-rejects where it matters most. B rises to
50,000 for every later Phase 6 and Phase 7 cell."* That remedy is wrong, and so
is the reasoning behind it, which this pre-registration repeated from 6.1's
original gate.

**Finite B affects reproducibility, not calibration.** `p = (1 + #{M_b >= sr}) /
(B + 1)` is valid at every B. Under the null the observed statistic and its B
replicates are exchangeable, so the rank is uniform on `0..B` and
`P(p <= α) = floor(α(B+1)) / (B+1) <= α` for any B — conservative by at most one
grid step, never liberal. Verified here by direct simulation, 400,000 draws per
row:

| B | rejection rate at α=0.05 | at α=0.01 | attainable level |
|---|---|---|---|
| 99 | 0.0396 | 0.0000 | 0.0400 / 0.0000 |
| 999 | 0.0489 | 0.0088 | 0.0490 / 0.0090 |
| 9,999 | 0.0499 | 0.0099 | 0.0499 / 0.0099 |
| 10,000 | 0.0502 | 0.0100 | 0.0500 / 0.0100 |
| 50,000 | 0.0502 | 0.0099 | 0.0500 / 0.0100 |

B coarsens the grid a p-value can land on; it does not bias the rate. What
finite B does do is move an *individual* p-value: its Monte Carlo standard
deviation is `sqrt(p(1-p)/B)`, which at p = 0.01 is 0.00099 at B = 10,000 and
0.00044 at B = 50,000 — 9.9% and 4.4% of the threshold. That is a statement
about whether a verdict near α would survive a different bootstrap seed, which
is reproducibility, and it averages out across draws.

*Literature.* The exact-level result for Monte Carlo tests is standard — Dwass
(1957) and Barnard (1963) for the construction, Besag & Clifford (1989, 1991)
for the sequential variants, Davison & Hinkley (1997) §4.2 for the textbook
statement. **None has been read from full text here**, per this repository's
convention; the simulation above is what the claim rests on, and the citations
are to be checked before the write-up asserts them.

**Rule 1's fails-high branch is replaced.** An excess rejection rate at α = 0.01
in arm D implicates the **bootstrap approximation in the tail** — finite T, the
block-length selection, the studentization that re-estimates each candidate's
standard deviation inside every replicate — and not B. Raising B would buy
precision on an individual p-value while leaving the rate exactly where it was.
The remedy is to investigate those three, in that order, and B is implicated
**only** if rule 6 below shows a signed shift. Everything else in rule 1 stands:
the halt, its one-sidedness, and the relabelling of the agent arm's 1% figures.

**6. Secondary — reproducibility, on the paired B = 50,000 subsample.** The
**verdict flip rate**: the share of the 500 paired draws whose reject/accept
decision differs between B = 10,000 and B = 50,000, at α = 0.05 and at α = 0.01.
Reported with the signed mean of `p_50k − p_10k`, overall and for draws with
`p_10k < 0.05`. No halt.

- *Signed shift near zero* confirms Monte Carlo noise and leaves B exonerated.
- *A signed shift away from zero* means the two bootstrap sizes disagree
  systematically rather than noisily, which would implicate B after all and is
  the only thing that reopens rule 1's B remedy.
- *The flip rate is the number that matters operationally.* A non-trivial rate
  at α = 0.05 or 0.01 is what would justify the gate reporting a Monte Carlo
  interval on its p-value, or marking a near-threshold verdict as marginal
  rather than returning a bare PASS or FAIL.

Observed already on arms B and C, as background and not as a pre-registered
result: the signed mean over all 500 paired draws is −0.000055 (greedy, t =
−1.23) and +0.000039 (adaptive, t = +0.28), both indistinguishable from zero,
and the flip rate is **0 of 500 at both levels for both searchers**. That last
figure is uninformative for the same reason arm C's rule 3 was — almost no
p-value lies near a threshold. Arm D puts them there.

## Deviations

**1 — 2026-09-20, after arm B reported.** Rules 1 and 2 were the wrong shape for
what the procedure claims, and both "failed" in the conservative direction. The
rules are left exactly as committed; this records what they do and do not
license.

**What the rules asked.** Rule 1 asked whether the Wilson interval at α = 0.01
*contains* 0.01, and rule 2 asked whether the p-values are uniform. Both are
tests of **exactness**. The declared-class tier does not claim exactness. P3
claims validity — rate ≤ α — and P2 says any searcher submitting less than the
class maximum comes in strictly under it. So a searcher that does not reach the
class maximum is *predicted* to sit below nominal with p-values massed near 1,
and both rules were built to reject exactly that prediction.

**What arm B observed**, reported as measured and unchanged:

| searcher | α=0.01 | α=0.05 | KS stat | KS p |
|---|---|---|---|---|
| greedy | 0.0002 (0.000–0.001) | 0.0002 (0.000–0.001) | 0.8692 | 0.0000 |
| adaptive | 0.0018 (0.001–0.003) | 0.0100 (0.008–0.013) | 0.3737 | 0.0000 |

**The halt does not apply.** Rule 1's only failure branch is "fails high: the
gate is liberal at 1%", and the halt attaches to that branch. Both observed
failures are low. A conservative gate cannot certify noise, so nothing
downstream inherits a defect, and Phase 6 continues.

**A design fault in arm B, not only in the rules.** The bar is the signed class,
82,240 members. `Greedy` and `Adaptive` build specifications with
`_one_hot_sum`, which is unsigned, so they can only reach the 10,700-member
unsigned sublattice — 13% of the class — and `Greedy` submits a single feature
against a bar dominated by triples. The searchers were mismatched to the class
they were priced against, which inflates the measured conservatism by an amount
this arm cannot separate from the gate's own. Deviation 2 adds the searcher that
removes the mismatch.

**What arm B therefore does and does not establish.** It establishes that the
declared-class tier is not liberal at 1% for these searchers, and it measures
how far under nominal two specific searchers land. It does **not** answer the
question the pre-registration was written to ask — whether B = 10,000 resolves
the bootstrap tail at 1% — because nine rejections in 5,000 draws cannot
distinguish a resolution failure from ordinary conservatism. Arm C inherits the
same limitation: it compares two bootstrap sizes on p-values that are almost all
near 1.
