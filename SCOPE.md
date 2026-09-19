# What is validated, and where "it's all in the transcript" stops

The claim this project tests is that an agent's search is auditable *because it
is logged*: every backtest and every discarded candidate sits in a transcript,
so the trial count and correlation structure can be read off it. That claim
survives for search whose candidate menu is fixed in advance, and fails for
search that decides what to try next from what it has already seen.

**A logged transcript licenses a valid correction only when the candidate set
is data-oblivious.** When the search generates candidates from its own earlier
results, the transcript is not enough: you additionally need either an
algebraic property of the specification class strong enough to reconstruct
untried candidates, or a re-executable environment, or a class declared in
advance. Observability of what was tried is necessary and not sufficient.

Sections are referred to by name, not number, so that citations from
`THEORY.md`, `prereg/` and the gate's own output survive edits to this file.
Experiments are named in `EXPERIMENTS.md`, which records the commit each was
pre-registered at; their data files are in `figures/`.

## The obliviousness condition

Define, for a search run on null noise realization `ω`, the **candidate menu**
`C(ω)`: the set of specifications that get `evaluate()`'d.

**Data-oblivious menu.** `C` is data-oblivious if `C(ω)` is measurable with
respect to some σ-field independent of the return-generating randomness — which
specifications get tried does not depend, even indirectly, on the realized
in-sample returns. A trial count, subset sizes, and an independently-seeded PRNG
are allowed; realized Sharpe values feeding back into which columns appear next
are not.

**Claim.** If `C` is data-oblivious, joint-row bootstrapping of the observed `R`
matrix, restricted to the realized `C`, consistently estimates the null
distribution of `max_{n∈C} SR_n` — for any `N = |C|` and any correlation
structure. Conditional on a fixed menu, the observed columns are the null
process evaluated at `N` fixed linear functionals, which is what block-bootstrap
theory targets (Politis & Romano 1994). Correlation among columns is not an
obstacle; that is the point of resampling rows jointly. **Non-obliviousness is.**

This is why Honest (`N=1`), Greedy (`N=K`) and GridSearch (`N` up to thousands,
heavily correlated) are all calibrated at n=200 null draws with matched seeds —
KS p = 0.777, 0.118, 0.174 — despite spanning three orders of magnitude in `N`.
Independence was never the load-bearing assumption. Obliviousness is, and it is
strictly weaker.

**Why Adaptive violates it.** Adaptive's round-`(r+1)` menu is
`{support_r(ω) ∪ {j}}`, where `support_r(ω)` is the argmax of round `r`'s
realized Sharpes: which candidates are tried is a discontinuous function of the
very noise under test. On the same 200 draws its naive-bootstrap KS statistic is
**0.2052** against a critical value of 0.096.

The mechanism is specific. The naive bootstrap resamples the observed
transcript's fixed weight vectors, so in every replicate round 2's candidates
stay "the feature that won round 1 *on the real data*, plus `j`". On fresh null
data a different feature would generically win. Freezing the anchor denies every
replicate the freedom the real search had, so the bootstrap explores a strictly
narrower space than the procedure it is nulling, and biases p-values downward.

## The two repairs

**Recursive.** `estimator/recursive_bootstrap.py` re-derives each round's
selection inside every replicate via a `replay()` method. At n=500, properly
powered:

| estimator | KS stat | type-I at α=0.05 (95% CI) |
|---|---|---|
| naive | 0.164 | 0.136 (0.109–0.169) |
| recursive | 0.041 | 0.034 (0.021–0.054) |

Naive fails at nearly 3× nominal; recursive is indistinguishable from
calibrated. **But the repair has a dependency.** To get round 2's candidate for
a counterfactual winner it never evaluated, `replay` sums already-logged
columns, which equals what `evaluate()` would have returned *only because
`Specification` is linear*. A threshold, a lookback window or an interaction
term breaks the reconstruction, and nothing in the log recovers it. The
transcript plus an algebraic property of the class is what makes this work — not
the transcript alone.

**Procedure-level.** `estimator/procedure_level_bootstrap.py` needs no
reconstruction: it circularly shifts `r_in` against `x_in` and literally
re-executes the searcher against each nullified draw. Correct for any searcher
by construction. Against recursive on 20 independent draws, the mean difference
in null max is **+0.019** (SD 0.043) with the sign flipping evenly — Monte Carlo
noise, not bias. The reconstruction is sound where available; it just is not
available in general.

**It is generation, not selection.** `LatticeAdaptive` evaluates the full fixed
lattice unconditionally — an oblivious menu — then selects with Adaptive's exact
greedy rule. On the same 200 draws:

| searcher | KS stat | type-I at α=0.05 (95% Wilson CI) |
|---|---|---|
| Adaptive | 0.2106 | 0.120 (0.082–0.172) |
| LatticeAdaptive | 0.0999 | 0.065 (0.038–0.108) |

Adaptive's interval excludes nominal 5%; LatticeAdaptive's contains it. Adaptive
candidate *generation* is the dominant driver, not adaptive selection.

## Winner-chasing

Adaptivity alone does not distort the naive bootstrap. **Only a menu built
around the selection statistic's own winner does.** Eight experiments establish
this; each was pre-registered before it ran, at the commit EXPERIMENTS.md gives.

| experiment | what it varied | result |
|---|---|---|
| `anchor-coupling` | four round-2 anchor rules, n=500 | winner 8.2% (0.061–0.109); neighbor 3.6%, random 4.0%, worst 3.2%. McNemar 23–0, 21–0, 25–0 against winner. Recursive corrects all four. |
| `pointwise-dominance` | the P4 lemma's mechanism | the process null ≥ the realized-menu null on 99.9% of replicates; naive p ≤ recursive p on 500/500 draws |
| `graded-coupling` | anchor drawn ∝ exp(τz), eight levels | naive type-I rose 3.6% → 7.0% with coupling; pre-registered trend test p = 0.0001 |
| `anchor-rank` | anchor fixed at rank k, n=1,000 | 9.5, 9.7, 6.3, 3.9, 3.8, 3.7% at ranks 1, 2, 3, 5, 10, 20 — every one inside its 95% interval around the limit fixed in advance (9.1, 9.1, 6.6, 4.9, 4.3, 4.3) |
| `search-depth` | depth 3, four rules, n=1,000 | winner 10.4%; random and neighbor not detectably inflated. Greedy and beam reached the class maximum on 99.1–99.7% of replicates and their recursive decisions agreed on every draw |
| `feature-count` | K ∈ {10,20,40,80} | naive rose 10.0% → **36.2%** at ρ=0, and 7.0% → 14.0% at ρ=0.3. Recursive and full-class stayed 4.0–5.2% throughout |
| `unequal-correlation` | one-factor loadings | dominance 99.894% and 99.908%; naive 8.8% and 14.2%, both matching the limit; corrections 4.4–5.0% |
| `non-additive-scoring` | crossover rules, n=2,000 | the sign survives where the lemma does not: winner rejected where loser did not on 47 draws against 1, and 36 against 0, both p < 10⁻⁴ — but absolute inflation is only about a point |

**What this establishes.** Inflation grades with how strongly the anchor tracks
performance, follows the anchor's rank along the curve the order statistics
predict, grows with the number of candidates, survives the loss of
exchangeability, and survives scoring that is not a weighted sum at all. Both
corrections stay nominal everywhere tested. Anchoring on a loser is
*conservative*, which is the mirror the same lemma predicts.

The dose-response run that first suggested this (`dose-response-beam`, n=150,
B=300) is **void**: a bug made its NeighborAdaptive anchor on the round-1 winner,
so it was Adaptive under another name. `search-depth` re-ran the dose axis
pre-registered at n=500 and B=1,500 and found the same shape at lower levels
(0.054 → 0.060 → 0.080 → 0.084 → 0.092, nondecreasing).

## Effective breadth

Shrinking the trial count for correlation, when the closed-form deflated Sharpe
already absorbs it, counts the correlation twice and leaves real overfitting
standing. Bias = mean(predicted decay − realized decay); negative is
anti-conservative:

| | bias(raw N) | bias(effective N) | bias(bootstrap) |
|---|---|---|---|
| ρ=0, N=10→1000 | +0.063 → +0.262 | −0.013 → −0.466 | +0.029 → +0.017 |
| ρ=0.3 | +0.015 → +0.097 | −0.348 → −0.937 | +0.010 → −0.030 |
| ρ=0.6 | +0.007 → +0.017 | −0.373 → −0.825 | +0.008 → −0.031 |
| ρ=0.9 | −0.005 → −0.023 | −0.280 → −0.561 | −0.004 → −0.022 |

**Bootstrap is the only one of the three close to unbiased everywhere on this
grid.** Raw-N is conservative, and less so as correlation rises, because
ignoring correlation costs less when there is less independent breadth to
over-penalize. Effective-N is substantially anti-conservative wherever trials
are correlated at all — which is the regime real searches live in — peaking at
ρ=0.3 rather than at the highest correlation, plausibly because the
eigenvalue-based count shrinks toward 1 as ρ→1.

The gate therefore reports effective breadth for information and never uses it
in the correction.

## The headline cell

`ρ=0, N=1000`, mean over 100 draws:

| | value |
|---|---|
| Reported in-sample Sharpe | 2.028 |
| Oracle ceiling — no strategy can legitimately exceed this | 1.000 |
| True out-of-sample Sharpe | 0.205 |
| Realized decay | 1.823 |
| Bootstrap-predicted decay | 1.840 (off by **+0.017**) |
| Raw-N DSR-predicted decay | 2.085 (off by +0.262) |
| Effective-N DSR-predicted decay | 1.357 (off by −0.466) |

A search reports 2.03 — double the population ceiling, a theoretically
impossible number given the DGP, and exactly the kind of number that gets
published because nobody can see the trial count behind it. The truth is 0.21.
Reading only the transcript, the bootstrap calls the decay to within 0.017.

Neither correction has much *per-draw* predictive power on this grid: R² is
deeply negative for every predictor, because `calibrate_sigma` fixes the oracle
ceiling across draws, so between-draw variance in achievable Sharpe is small by
construction. RMSE and bias are the metrics that mean something here; R² is not.

## The cost of breadth

**Breadth is not free.** Holding the quality of the finding completely fixed —
`PinnedSelector` builds the identical menu but always submits the true signal
triple, so submitted Sharpe is `N`-invariant by construction — power falls
monotonically in breadth:

| | N=10 | N=100 | N=1000 |
|---|---|---|---|
| power, target Sharpe 1.0 | 0.150 | 0.060 | 0.020 |
| power, target Sharpe 2.0 | 0.690 | 0.420 | 0.260 |

This is the pure multiple-testing cost of having looked, decoupled from the
benefit of having looked. A real searcher's observed power is the sum of the
two, and they pull in opposite directions.

**Single-strategy power is not a bound on search power.** The gate prints power
for one pre-specified strategy. Measured against a real search the sign depends
on breadth: a 10-specification search rarely contains the edge and detects less
often than a strategy pinned to it; a 1,000-specification search reaches
specifications carrying part of the edge and detects more. Which side a search
is on depends on where the edge sits in its menu, which the transcript does not
reveal, so the gate prints the figure and states no direction.

**A lucky pass overstates the edge, worst where the warning fires.** Conditional
on passing, exaggeration falls monotonically with power — 11.94× at 6% search
power, 3.11× at 9%, 1.55× at 16%, 1.10× at 30%, and *below* 1 above that, as
over-deflation takes over near 30% power. The gate cannot index this curve with
its own power figure, because single-strategy power read 0.1–7.6% in cells where
search power was 6–66%; it quotes the curve and says it cannot place the search
on it.

## Sparse strategies

**The same 10,000-rule menu produced critical values from 2.03 to 155 across 20
data seeds.** Same rules, same sample length; only the simulated prices changed.
A bar that moves by a factor of 75 is not measuring the search.

The cause is the statistic. A Reality Check that re-estimates each candidate's
Sharpe inside every replicate can be dominated by rules rarely in the market: a
resample catching few active periods shrinks the standard deviation faster than
the mean, and the ratio explodes — `sharpe()` returned **1.2×10¹⁵** on one
replicate. On one seed the top decile of null maxima came from rules active on a
median 0.3% of days. Dropping band filters brought the critical value to
1.60–1.74 across the same seeds.

White (2000) used a non-studentized mean, which has no denominator to collapse;
Hansen (2005) studentizes by a full-sample standard deviation held fixed across
replicates. Both look incidental until a menu contains sparse rules. Filtering
by trading frequency would make the menu data-dependent, so the gate cannot fix
this by exclusion: it detects and refuses instead (**DEGENERATE**). Thresholds
were set by a pre-registered recalibration on fresh seeds:

| population | refused | 95% CI |
|---|---|---|
| dense transcripts | 0 of 9,000 | upper bound 0.033% |
| sparse, broken bar | 792 of 882 (89.8%) | 87.6–91.6% |
| sparse, sound bar | 54 of 1,318 (4.1%) | 3.2–5.3% |

None of the linear-specification results above are affected: every candidate
there takes a position in every period.

## Oblivious searchers

The control the adaptive results needed. Across 56 cells — menu sizes from 175
to 10,700, correlation 0 to 0.9, n=1,000 draws each — **no cell's KS test
rejects uniformity after Holm correction, and every type-I interval contains
5%.** Honest and Greedy are never liberal, so the bootstrap itself is sound.
Oblivious generation with adaptive selection held more strongly than registered:
zero discordant pairs in all eight paired cells.

At ω=0.9 the participation ratio collapses to 1.1 even with 10,700 logged
columns and the test stays calibrated anyway — joint resampling has already
accounted for the duplication. The Sharpe guards never bound anywhere.

Recorded because it was wrong: the pre-registration put this at 33 CPU-hours
from a 4-draw smoke, and it took **7.73 hours on 32 cores**. Sizing a run from a
smoke that small is not reliable.

## The agent arm

Everything above is scripted search. This is the arm the project exists for:
searchers whose every evaluation is logged because the searcher is an agent.
661 runs across five pre-registered batches, $177 and 29.6 hours of wall time.
`prereg/AGENT_PROMPTS.md` fixes the prompts, arms and analysis; the per-batch
summaries, per-run tables and archived transcripts are in `runs/`, and
`python -m experiments.analyze_agent` regenerates every number here.

**The gate holds when the searcher is an agent.** Over 421 searches on pure
noise, 15 returned PASS — 3.6%, at or below a nominal 5%, across both models and
every arm. On a real edge, PASS ran 60–70%, above the 46% single-strategy power
`preflight` reports at the reference Sharpe. That is not liberality: a searcher
that can reach the edge submits the best of its neighbourhood, so what it
reports carries more than the reference strategy does. The noise arm is the
control that makes the edge number readable.

**Stated belief is a fixed function of the in-sample number, and deaf to the
search.** Pooled over the s0 Sonnet cells (n=329), stated mean regresses on
submitted in-sample Sharpe at +0.399 and on log evaluation count at −0.023, on
top of a model-specific intercept. An agent reports roughly a prior plus half of
whatever it found, and the breadth that produced it barely enters.

**Telling an agent its trial count does not change that, and neither does
assigning it.** The count arm ends every `evaluate` result with the running
total: stated mean 0.45, identical to the control's, on a higher median
evaluation count. The budget arm caps evaluations at 20, 60 and 180 and the caps
bind (medians 19, 55, 98.5); across that ninefold change in breadth, stated
confidence moves 0.35 → 0.40 → 0.41, the wrong way and far less than the breadth
warrants.

**Showing an agent the bar changes how much it searches, in a model-specific
direction, and barely what it believes.** Sonnet searched harder under the gate
arm in every batch (81→137, 84→156, 79→125, 76→115.5 median evaluations). Opus,
on the same task as the last of those, searched *less*: 93→81. Fable did not
move: 45→46.5. Fable is closer to calibrated than either — stated mean
0.05–0.11, deflation gap 0.085–0.161 against Sonnet's 0.36–0.50 — but by stating
low confidence generally rather than by responding to its own search.

**Scope.** One synthetic panel with a known oracle, T=5000, one declared class,
three models. No real data, and no agent has been told INADMISSIBLE at open;
both are `ROADMAP.md` 6.5 and 6.6.

## Prior art

**The verdict engine is White's Reality Check (2000)**, implemented
independently here against this project's own sandbox: demean every column,
resample the time index jointly, track the maximum, read off a p-value. That
correction is twenty-six years old and is the right tool; nothing here replaces
it. Stating this plainly matters, because a reader who recognizes the method and
finds no citation reasonably concludes either carelessness or an attempt to pass
off known work as new.

What sits inside that framework and is not a replication:

- **The obliviousness boundary.** White's theorem holds the specification set
  fixed; this project characterizes what "fixed" requires when the
  specifications were themselves chosen from the evaluation data, demonstrates
  the failure, and supplies repairs.
- **The record hierarchy.** Transcript-only, transcript-plus-declared-class, and
  re-executable are three tiers with different requirements (`THEORY.md`, P3).
- **Sizing a search before running it.** `preflight` says in advance whether the
  intended breadth can certify anything.
- **The effective-N double-counting result**, a property of the closed-form
  baseline rather than of the Reality Check.

That the failure mode is real is not novel, and the theory naming it predates
this work: Leeb & Pötscher (2005) prove post-selection distributions cannot be
consistently estimated by treating the selected model as fixed; Efron (2014)
prescribes re-running the selection step inside every replicate, which is
exactly what the two repairs do; Berk et al. (2013) and Lee et al. (2016) are
the selective-inference alternative to re-simulation. `THEORY.md` places the
sign and size results against White, Hansen, Romano & Wolf, Hsu–Hsu–Kuan, Dwork
et al., Blum & Hardt and the deflated-Sharpe literature, each read from full
text, and carries the reference list.

## Validated and open

**Validated.** The naive bootstrap is correctly calibrated for any search whose
menu is data-oblivious — any trial count, any correlation, including exact
duplicates. Both repairs restore calibration under winner-chasing everywhere
tested, including a class that defeats reconstruction entirely.

**Fixed, with a known dependency.** Recursive calibration for adaptive search
holds *provided* the specification class is algebraically rich enough to
reconstruct untried candidates. This is not guaranteed for a general searcher,
and not at all for an LLM agent.

**Open.** The procedure-level bootstrap is the fully general fix, but it
requires re-running the search B times — which for an agent means B× the token
cost against a non-deterministic procedure, so "re-running the same procedure"
does not even mean the same thing. Three routes, none yet tried: a surrogate
searcher fitted to the agent's selection behavior; conditional selective
inference, correcting analytically rather than re-simulating; or plain sample
splitting. Which works against a real agent is genuinely open.

Question-by-question status is in `OPEN_QUESTIONS.md`; what is scheduled next is
in `ROADMAP.md`.
