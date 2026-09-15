# Scope of the validated claim, and the boundary of "it's all in the transcript"

The proposal's central claim is that an agent's search is auditable *because
it's logged*: "every backtest, every dropped feature, every parameter sweep
sits in the transcript... its trial count and correlation structure can be
read off." Experiment 1 (spec §4.1) tests this as a pass/fail gate: under a
pure null, every searcher's p-value should be Uniform(0,1), regardless of
how hard or how sequentially it searched.

That claim survives for search whose candidate menu is fixed in advance and
fails for search that decides what to try next based on what it's already
seen — and the reason it fails is sharper than "the naive bootstrap has a
bug." **A logged transcript licenses a valid correction only when the
candidate set is fixed. When the search generates candidates conditional on
its own earlier results, the transcript is not enough — you additionally
need either an algebraic property of the specification class strong enough
to reconstruct untried candidates, or a re-executable environment.**
Observability of what was tried is necessary but not sufficient; this
document works out exactly where the line is, with a fix on one side of it
and an open problem on the other.

## 1. The actual sufficient condition, stated precisely

The spec frames the bootstrap's advantage over closed-form DSR as "no
independence assumption" (§1.2–1.3). That's true but understates what's
actually being relied on. Define, for a search run on null noise realization
`ω`, the **candidate menu** `C(ω)` — the set of specifications that get
`evaluate()`'d.

**Data-oblivious menu.** `C` is data-oblivious if `C(ω)` is measurable with
respect to some σ-field independent of the return-generating randomness —
i.e. which specifications get tried does not depend, even indirectly, on the
realized in-sample returns. (The trial *count* `K`, `subset_sizes`, and an
independently-seeded PRNG for thinning are allowed; realized Sharpe values
feeding back into which columns appear next is not.)

**Claim.** If `C` is data-oblivious, joint-row stationary bootstrapping of
the observed `R` matrix, restricted to columns in the realized `C`,
consistently estimates the null distribution of `max_{n∈C} SR_n` — for *any*
`N = |C|` and *any* correlation structure among those columns. Conditional on
a fixed, data-independent menu, the observed columns are just "the null
process, evaluated at `N` fixed linear functionals," which is exactly the
object block-bootstrap theory (Politis & Romano 1994; Politis & White 2004)
targets. Correlation among columns is not an obstacle — that's the entire
point of resampling rows jointly. **Non-obliviousness is.**

This is why Honest (`N=1`), Greedy (`N=K`, fixed given `K`), and GridSearch
(`N` up to thousands, heavily correlated overlapping subsets, but *which*
subsets appear is fixed given `K`/`subset_sizes` and a seed uncorrelated with
any realized Sharpe) are all calibrated on a properly powered check (n=200
null draws, matched seeds): KS p = 0.777, 0.118, 0.174 respectively —
despite spanning three orders of magnitude in `N` and a wide range of trial
correlation. Independence was never the load-bearing assumption; obliviousness
of the menu is, and it's strictly weaker.

## 2. Why Adaptive violates it, and the exact mechanism

Adaptive's round-`(r+1)` menu is `{support_r(ω) ∪ {j} : j ∈ remaining}`, where
`support_r(ω)` is the argmax of round `r`'s *realized* Sharpes. This is
manifestly not oblivious: which candidates even get tried in round 2 is a
discontinuous function of the very null noise under test.

On the same 200 null draws used above: naive-bootstrap KS statistic for
Adaptive = **0.2052** (KS p ≈ 0.0000) against a critical value at n=200 of
≈0.096 — over double the threshold, not a marginal miss.

**The specific mechanism.** `Specification` is linear, and every
specification in a draw shares the same noise realization, so a pair's
return series is *exactly* `single(a) + single(b)`, elementwise — confirmed
to floating-point precision (`max abs diff = 2.2e-16`) — and demeaning
distributes over the sum, so this survives null-imposition too. The naive
bootstrap (`estimator/bootstrap.py`) resamples the *observed* transcript's
fixed weight vectors: in every replicate, round 2's candidates stay "feature
`W_orig` + feature `j`" for the *specific* `W_orig` that won round 1 on the
real, unresampled data. On fresh null data, a *different* feature would
generically win round 1. Freezing the anchor denies every replicate's round 2
the thing the real search actually had — the freedom to build on top of
whichever feature *that draw's own noise* favored — so the naive bootstrap
explores a strictly narrower space than the procedure it's nulling, which
under-estimates the true null max and biases p-values downward.

## 3. The fix, and its real dependency (found before it became a problem)

`estimator/recursive_bootstrap.py` re-derives each round's selection inside
every replicate instead of freezing it, via a `replay(base_columns)` method
every searcher implements (the `Replayable` protocol, `searchers/base.py`).
On the same matched 200 draws: recursive-bootstrap KS statistic for Adaptive
= **0.0876** (KS p = 0.088), *below* the n=200 critical value of 0.096 —
passes, where naive's 0.2052 fails by a factor of two.

That n=200 result is close enough to its critical value (0.088 vs. 0.096)
that it's worth not resting on. At n=500 (`experiments/e4_adaptive_n500.py`,
properly powered — neither result lands anywhere near its critical value of
0.061):

| estimator | KS stat | type-I rate at α=0.05 (95% CI) |
|---|---|---|
| naive | 0.164 | 0.136 (0.109–0.169) — decisively excludes nominal 5% |
| recursive | 0.041 | 0.034 (0.021–0.054) — consistent with nominal 5% |

Naive fails at nearly 3x its nominal rate; recursive is not distinguishable
from correctly calibrated. The fix holds with room to spare, not only at a
boundary case.

**But look at how `replay` gets round 2's candidate for a counterfactual
winner it never evaluated.** Say round 1's real winner was feature 7, but
this replicate's *own* resampled data favors feature 3. `replay` needs
`single(3) + single(j)` for various `j` — a pair the real search never ran,
for a winner the real search never had. It gets this by *summing* the
already-logged `single(3)` and `single(j)` columns. That sum is only equal
to what `evaluate()` would have returned because `Specification` is linear.
**This means the transcript alone is not what makes the fix work — the
transcript plus an algebraic property of the specification class is what
makes it work.** A specification with a threshold, a lookback window, or any
interaction term would break the reconstruction, and nothing in the logged
transcript would let you recover what `(3, j)` scores. This is a genuine
weakening of "it's all in the transcript," not a footnote, and it's the
reason SCOPE.md exists as a separate document rather than a clean two-line
result: the boundary is not "adaptive search is unfixable," it's "adaptive
search needs *more than the log* unless the specification class cooperates."

**Validating the fix against something that doesn't need that dependency.**
`estimator/procedure_level_bootstrap.py` is the version with no
reconstruction requirement: it circularly shifts `r_in` in time relative to
`x_in` (destroying the feature-return relationship while preserving each
series' own autocorrelation and cross-feature correlation exactly — a
standard surrogate-data technique) and literally *re-executes* the
searcher's `run()` against each nullified draw, B times. Correct for any
searcher by construction, linearity or not, because it bootstraps the
procedure rather than reconstructing its output.

Compared against the cheap recursive bootstrap on 20 independent draws
(`experiments/e3_procedure_level_validation.py`, `K=20, M=60, T=600, B∈{300,500}`):
mean(`mean_null_max_recursive - mean_null_max_procedure`) = **+0.019**
(SD 0.043), with the sign flipping roughly evenly across draws — consistent
with pure Monte Carlo noise, not a systematic bias. The reconstruction is
sound where it's available; it just isn't available in general.

## 4. Isolating the exact cause: adaptive selection vs. adaptive candidate generation

Everything above argues, from the mechanism, that it's specifically the
*menu* being data-dependent — not how a searcher picks among an oblivious
menu — that breaks the naive bootstrap. `searchers/diagnostic.py`'s
`LatticeAdaptive` tests this as a one-variable-changed experiment: it
evaluates the *full* fixed lattice (every subset up to `max_features`)
unconditionally every run — an oblivious menu, identical in shape to
GridSearch's uncapped transcript — then *selects* the submitted spec with
the exact same sequential greedy rule as Adaptive. Selection is just as
sequentially data-dependent as Adaptive's; only candidate generation is not.

Naive-bootstrap null calibration, Adaptive vs. LatticeAdaptive, same 200
null draws (`K=20, M=60, T=600, B=1500`):

| searcher | KS stat | KS p | type-I rate at α=0.05 (95% Wilson CI) |
|---|---|---|---|
| Adaptive | 0.2106 | 0.0000 | 0.120 (0.082–0.172) |
| LatticeAdaptive | 0.0999 | 0.0344 | 0.065 (0.038–0.108) |

Adaptive's type-I-rate CI excludes the nominal 5% entirely (0.082–0.172).
LatticeAdaptive's *includes* it (0.038–0.108) — on the operationally
relevant statistic (how often this would actually fool someone using
α=0.05), LatticeAdaptive is not distinguishable from correctly calibrated,
while Adaptive clearly is broken. The KS test, which is sensitive to the
whole distribution's shape rather than just the α=0.05 tail, still flags a
small residual deviation for LatticeAdaptive (p=0.034) that a larger
`n_draws` would be needed to characterize — reported rather than rounded
away, per the type of honesty this document is trying to model.

One check this result leans on — and an earlier version of this document
got it wrong, worth stating plainly rather than quietly fixing. The first
30-draw check found LatticeAdaptive's greedy selection (which examines only
`K + (K-1) + (K-2)` of the full lattice's combos, restricted to the same
round-by-round path structure as Adaptive) landing exactly on the true
full-lattice maximum every time, and this document originally claimed that
as a general property. It isn't one: greedy forward selection is a
heuristic with no optimality guarantee, and a direct counterexample turned
up during the dose-response follow-up work (`K=20, M=50, T=500, seed=70022`)
— greedy's pick scored 1.9956 while an unselected triple already sitting in
the same transcript scored 2.0148. Measured properly
(`tests/test_lattice_greedy_optimality.py`) over 60 further draws: this
happens about 1.7% of the time, with small gaps (~0.01–0.02 Sharpe) when it
does.

This mattered beyond one test's wording: `deflate()`'s default `sr_sel`
(max over the whole transcript) silently relies on exactly this "always
equal" assumption, and the original table above was computed that way. The
comparison was rerun with `sr_sel` passed explicitly as each searcher's own
submitted value (`experiments/e2_lattice_control.py`, now fixed) — the
numbers came back **identical** to four decimal places. At a ~1.7% mismatch
rate with sub-0.02 gaps, not enough draws are affected to move the aggregate
KS statistic or type-I rate at n=200. The original conclusion holds; the bug
was real and worth fixing on principle (a rarer or larger-gap version of it
elsewhere could easily have mattered), but it did not happen to distort this
particular result.

If LatticeAdaptive is far closer to calibrated than Adaptive on the
statistic that actually matters, adaptive candidate generation is the
dominant driver of the naive bootstrap's failure — not adaptive selection.
That's the one-sentence version of everything above, demonstrated rather
than argued from the mechanism alone.

## 5. A monotone dose-response, not a one-searcher artifact

Everything above establishes the mechanism on two points (Adaptive,
LatticeAdaptive). The natural objection: maybe it's specific to one
searcher's quirks, not a general property of adaptive candidate generation.
`experiments/e5_dose_response.py` tests this directly with a scalar dose —
beam width `k` (`searchers/dose_response.py`'s `BeamAdaptive`), which
interpolates continuously between the two existing endpoints: `k=K` keeps
every candidate at every round (≈ LatticeAdaptive), `k=1` is exactly
Adaptive. Plus two structural variants holding `k=1` fixed: `DepthAdaptive`
(one more round) and `NeighborAdaptive` (round 2 anchors on the feature most
correlated with round 1's winner, not the winner itself — same *amount* of
data-dependence, a different rule generating it). **Correction (§14):** a bug
made NeighborAdaptive anchor on the round-1 winner itself, so throughout this
section it was Adaptive under another name. Its row and every conclusion drawn
from it below are void; §14 reruns the comparison with the bug fixed.

Prediction, stated before running: naive's type-I rate decreases
monotonically in `k`. Falsifiers, stated before running: flat in `k` means
the mechanism story is wrong; non-monotone means something's confounded
with beam width; only the original Adaptive breaking means the result is
narrow. Paired seeds throughout (every variant sees the identical null draw
at each index), n=150, `K=20, M=50, T=500, B=300` — scoped down from the
originally requested n=500/B=2000 for tractability (procedure-level's
B-full-re-runs cost makes the full spec's 5 variants × 500 draws × 2000
replicates × 3 methods a many-hour job; naive and recursive, where the
dose-response signal actually lives, get the full sweep, procedure-level
gets a validation spot-check as described below).

**Superseded by E18 (§17).** The run described in this section used n=150
and B=300 and had the anchor bug. E18 reran the dose axis on the same K, M and
T with n=500 draws and B=1,500, pre-registered. Its table replaces the
original:

| variant | naive type-I (95% CI) | recursive type-I (95% CI) |
|---|---|---|
| LatticeAdaptive | 0.054 (0.037–0.077) | 0.054 (0.037–0.077) |
| BeamAdaptive(16) | 0.060 (0.042–0.084) | 0.054 (0.037–0.077) |
| BeamAdaptive(4) | 0.080 (0.059–0.107) | 0.054 (0.037–0.077) |
| BeamAdaptive(2) | 0.084 (0.063–0.112) | 0.054 (0.037–0.077) |
| Adaptive (k=1) | 0.092 (0.070–0.121) | 0.054 (0.037–0.077) |
| DepthAdaptive | 0.096 (0.073–0.125) | 0.058 (0.041–0.082) |

The shape is the same and the levels are lower. The original table is kept
below because the rest of this section discusses its numbers.

Original run (n=150, B=300):

| variant | dose (mean divergence) | naive type-I (95% CI) | recursive type-I (95% CI) |
|---|---|---|---|
| LatticeAdaptive | 0.000 | 0.060 (0.032–0.110) | 0.060 (0.032–0.110) |
| BeamAdaptive(16) | 0.331 | 0.067 (0.037–0.118) | 0.060 (0.032–0.110) |
| BeamAdaptive(4) | 0.876 | 0.093 (0.056–0.151) | 0.060 (0.032–0.110) |
| BeamAdaptive(2) | 0.932 | 0.107 (0.067–0.166) | 0.060 (0.032–0.110) |
| Adaptive (k=1) | 0.950 | 0.127 (0.083–0.189) | 0.060 (0.032–0.110) |
| DepthAdaptive | 0.950 | 0.133 (0.088–0.197) | 0.060 (0.032–0.110) |
| NeighborAdaptive (bug: was Adaptive, see §14) | 0.950 | 0.127 (0.083–0.189) | 0.060 (0.032–0.110) |

(figures: `figures/e5_dose_response_primary.png`, `figures/e5_divergence_diagnostic.png`)

**Strictly monotone, no falsifier triggered.** Naive's type-I rate climbs
0.060 → 0.067 → 0.093 → 0.107 → 0.127 as `k` shrinks from 20 to 1 — every
step in the predicted direction, landing almost exactly on the qualitative
labels predicted in advance (none / slight / moderate / substantial / max).
The effect is not narrow to one searcher: BeamAdaptive(2)'s CI already
excludes nominal 5% entirely, two steps before reaching the original
Adaptive.

**Recursive's five points are one measurement, not five — checked
directly, not assumed, because five-way exact agreement earned exactly
that suspicion.** Recursive reads 0.060 at every single dose-axis point.
Before reporting that as "flat at nominal across five independent checks,"
the two innocent explanations and the bad one all got checked:

- *Is `beam_width` actually reaching the recursive path?* Instrumented
  `BeamAdaptive(2)._search` directly on one resampled replicate: 94
  candidate evaluations (exactly `K + 2(K-1) + 2(K-2)` for beam=2, not the
  full lattice's ~1140), round-1 beam size exactly 2. Mechanically correct.
- *Do the p-values actually differ, with rejection counts only coincidentally
  matching?* No — loaded the raw arrays and checked directly: recursive's
  p-value array is **elementwise identical** across LatticeAdaptive,
  BeamAdaptive(16/4/2), Adaptive, and NeighborAdaptive (the last trivially:
  the anchor bug made it Adaptive, §14) (DepthAdaptive
  differs, correlation 1.000, because its extra round changes the
  achievable support size). Traced to the source: `M_b` itself is
  identical to floating-point precision across all four searchers on
  every one of 300 tested bootstrap replicates (max abs diff = 0.0).
- *Why, mechanically, if beam_width is respected?* Greedy forward selection
  (any beam width 1–K; NeighborAdaptive's correlation rule was never actually
  exercised, §14)
  finds the TRUE global optimum over subsets of size ≤3 on this DGP with
  very high probability — measured at 1/300 mismatches (0.3%) on fresh iid
  draws and 0/300 on bootstrap replicates of one draw (both well below the
  ~1.7% rate §3's earlier, noisier 60-draw check suggested). Since `sr_sel`
  and each replicate's `M_b` value both reduce to "the achievable global
  optimum," and that quantity doesn't depend on which greedy rule computes
  it, all five max_features=3 variants' recursive p-values coincide by
  construction on this DGP.

So: not a bug, but the five-point reading genuinely is n=150, once — not
n=750. Reported properly: type-I = 0.060, 95% Wilson CI (0.032, 0.110),
**consistent with nominal** (the interval contains 0.05 comfortably), not
"equal to" it and not five independent confirmations of it. This does not
undermine recursive's validity — that rests on the separately-run,
properly-powered n=500 check on Adaptive alone (§3, KS D=0.041, type-I
0.034, CI 0.021–0.054) and on the oblivious-menu argument that makes
LatticeAdaptive/Greedy/GridSearch provably correct regardless of sample
size (§1). It does mean the dose-response sweep's OWN evidence for
recursive's correctness is thinner than it first looked, and the honest
sample size for recursive here is n=150, once.

**A related, smaller check on that same n=150, B=300 baseline reading.**
Both naive and recursive read 0.060 for LatticeAdaptive — expected (§1: an
oblivious menu makes them mathematically identical) — but 0.060 sits about
one Wilson-CI standard error above nominal 0.05. Pushed to B=10,000 on a
reduced n=60 to check whether this moves toward 0.05, as finite-B p-value
discreteness or slight nullification leakage would predict
(`experiments/e5c_baseline_diagnostic.py`): type-I = **0.083** (95% CI
0.036–0.181), KS stat 0.056 (KS p = 0.987, comfortably uniform). The point
estimate moved further from 0.05, not toward it — but the CI at n=60 is
wide enough to contain both 0.05 and the original 0.060 comfortably, so
this is not evidence of a real drift either direction. Net: no evidence of
a systematic B-driven bias (the KS test stays excellent at B=10,000), and
the 0.06-vs-0.05 gap at n=150 is most parsimoniously ordinary sampling
noise rather than a real, fixable leak — stated as inconclusive-but-
reassuring rather than resolved, since resolving it properly would need a
substantially larger n than this diagnostic used.

**Structural axis, corrected.** DepthAdaptive (0.133) runs slightly hotter
than Adaptive (0.127) — selection compounding over an extra round, in the
predicted direction, though the CIs overlap too much to call this decisive on
its own. The original version of this paragraph concluded that
NeighborAdaptive, anchoring round 2 on feature correlation rather than
Sharpe-argmax, "lands exactly on Adaptive's rate" because any data-dependent
rule with the same amount of data-dependence inflates equally. That was a
bug, not a finding: `_anchor` set the winner's correlation to −inf before
taking absolute values, so |−inf| won, the anchor was always the winner, and
NeighborAdaptive was Adaptive. Identical rates were identity, not evidence.
Rerun with the bug fixed and three more anchor rules (§14), the conclusion
reverses: the rule matters, and only the anchor built on the selection
statistic's own winner inflated the naive bootstrap.

**Two diagnostics, compared honestly — the predicted winner didn't win.**
`estimator/divergence.py`'s Jaccard divergence rate (what fraction of the
real transcript's round-1 beam a bootstrap replicate's own beam fails to
reproduce) is a *rate*, bounded at 1, and it saturates: 0.000 → 0.331 →
0.876 → 0.932 → 0.950 across the dose axis, compressing BeamAdaptive(2)
through NeighborAdaptive (whose figures are Adaptive's; §14) into a narrow band while their type-I rates keep
separating by a further ~4 points. The predicted fix was a *magnitude*:
`beam_entropy`, the Shannon entropy of the round-1 beam's distribution
across replicates, normalized by `log(C(K, beam_width))` since raw entropy
isn't comparable across beam widths with differently-sized outcome spaces
(unnormalized, larger beams score higher for no reason but having more
possible subsets to land on — confirmed by computing it both ways before
settling on the normalized version).

Measured against naive's type-I rate across all 7 variants: divergence
Pearson r = 0.901 (Spearman 0.972); normalized entropy Pearson r = 0.861
(Spearman 0.935). **Entropy does not track type-I more tightly than
divergence on this sample — contrary to the prediction, stated before
computing either correlation.** Both are strong, both directionally
correct, neither is decisively better; entropy has its own saturation
problem in a different place (BeamAdaptive(16) and BeamAdaptive(4) score
0.6669 and 0.6668 — visually identical — while their type-I rates differ
by 2.6 points). Worth being precise about why: `C(20,16) = C(20,4)`
exactly (binomial symmetry), so those two variants' outcome spaces are the
same size by construction of choosing `beam=16` with `K=20` — an artifact
of this experiment's parameter choice, not a general property of the
entropy diagnostic. A different `K` (or a beam width not symmetric to
another tested one) would not reproduce this specific tie, but the
broader point stands: neither diagnostic is a clean linear predictor of
exact inflation magnitude, and reporting the one that happened to score
higher without checking the other would have been the wrong way to settle
that (figure: `figures/e5_divergence_diagnostic.png`, both panels).

**A bug found and fixed during this work, worth stating precisely.** An
earlier draft of §4's LatticeAdaptive comparison relied on `deflate()`'s
default `sr_sel` (max over the whole transcript), based on a claim —
verified on only 30 draws — that this always equals a searcher's own
greedy submission. It doesn't, in general: a direct counterexample turned
up while building this section (`K=20, M=50, T=500, seed=70022`), where an
unselected triple sitting in LatticeAdaptive's own transcript scored 2.0148
against the greedy pick's 1.9956. Measured properly, this happens on
~1.7% of draws with small (~0.01–0.02) gaps. §4's original numbers were
rerun with `sr_sel` passed explicitly and came back identical to four
decimal places — the conclusion wasn't distorted here — but every
experiment from this section onward passes `sr_sel` explicitly rather than
relying on the default, and the over-claiming test that asserted "always
equal" was replaced with one that measures the actual rate
(`tests/test_lattice_greedy_optimality.py`).

**Next.** The build spec's Experiment 2 (predictive power under the
alternative — comparing naive Sharpe, closed-form DSR, and bootstrap
deflation as predictors of out-of-sample Sharpe under `s=3`, the genuine-
signal configuration) has not been started. Everything above is null-
calibration work (`s=0`); it establishes that the estimator doesn't cry
wolf, not that it has power to detect real decay when there's something to
detect. That's the natural next block of work.

## 6. Prior art: this is White's Reality Check, not a new estimator

Section 1's bootstrap — demean every column, resample the time index
jointly across all of them, track the maximum per replicate, read off a
p-value from where the observed statistic lands in that null distribution
— is **White, H. (2000), "A Reality Check for Data Snooping,"
Econometrica 68(5), 1097–1126**, implemented independently here against
this project's own sandbox and DGP rather than adapted from published code.
`estimator/bootstrap.py` is a Reality Check test, with annualized Sharpe as
the per-candidate performance statistic, re-estimated in every replicate,
and a zero benchmark (§11 shows why the re-estimation matters). That should be stated
plainly rather than left for a reader to notice, because a reader who
recognizes the method and finds no citation reasonably concludes either
carelessness or an attempt to pass off known work as new — and either
conclusion is fatal to everything else in this document.

What is not simply a replication of White (2000):

- **The obliviousness boundary** (§§1–5 above) — White's original theorem
  is stated for a fixed candidate set; this project characterizes exactly
  what "fixed" has to mean for a *logged* transcript to license the
  correction (data-oblivious menus, §1), demonstrates the failure mode when
  it doesn't hold (Adaptive, §2), and fixes it where the specification
  class permits reconstruction (recursive bootstrap, §3), validated
  against a reconstruction-free gold standard (procedure-level bootstrap,
  §3, §5).
- **The effective-N double-counting result** (§10's bias table; a
  dedicated write-up with the literature check is planned) — a property of
  the closed-form DSR baseline, not of the Reality Check itself.
- **The pinned-selector power decomposition** (§10) — isolating the pure
  multiple-testing cost of search breadth from the benefit of having
  searched, which is a question about *using* the test, not a variant of
  the test.

Related prior art, for context on where this sits in the literature:

- **Sullivan, R., Timmermann, A. & White, H. (1999), "Data-Snooping,
  Technical Trading Rule Performance, and the Bootstrap," Journal of
  Finance 54(5)** — the Reality Check applied to a universe of technical
  trading rules across roughly a century of Dow Jones data. GridSearch's
  large-`N`, heavily-correlated regime (§1) is structurally the same
  setup: many overlapping, correlated candidate rules evaluated against
  one series.
- **Hansen, P.R. (2005), "A Test for Superior Predictive Ability,"
  Journal of Business & Economic Statistics 23(4)** — the higher-power
  successor to the Reality Check. Where White recenters every candidate
  at its own sample mean under the null (so hopeless candidates still
  contribute to the resampled maximum), Hansen's SPA excludes candidates
  sufficiently far below the benchmark from recentering, tightening the
  test. Not yet implemented here; it is the obvious check on whether the
  power collapse in §10 is a property of the problem or of the Reality
  Check's conservatism.
- **Romano, J.P. & Wolf, M. (2005), "Stepwise Multiple Testing as
  Formalized Data Snooping," Econometrica 73(4)** — a stepwise procedure
  that can reject more than one candidate as significant, for context on
  how the single-maximum framing here relates to the broader
  multiple-testing family.
- **López de Prado, M. & Porcu, E. (2025), "The Deflated Sharpe Ratio: A
  Unified Framework for Search-Adjusted Performance Inference," SSRN
  7198158** — frames the deflated Sharpe ratio as judging reported
  performance against what the research process could have produced
  without skill, and unifies its implementations, including DSR-L (the
  original location benchmark, the closed form this project uses as a
  baseline) and DSR-LS (which adds the dispersion of the selected maximum).
  In those terms, this project's bootstrap is a nonparametric construction
  of the search null from a logged transcript. (The DSR-L and DSR-LS
  descriptions here come from summaries of the paper's abstract; SSRN blocks
  automated access, so they have not yet been checked against the paper.)
- **Bailey, D.H., Borwein, J., López de Prado, M. & Zhu, Q.J., "The
  Probability of Backtest Overfitting," Journal of Computational Finance
  (published online 2016, doi:10.21314/JCF.2016.322)** — also works from the
  matrix of trial returns, estimating
  the probability that the in-sample winner underperforms out of sample by
  combinatorially symmetric cross-validation (CSCV). A different question
  from this project's significance test on the same object, and a necessary
  citation for anyone working from a trial matrix.
- **Nikolopoulos, S.D. (2026), "Spurious Predictability in Financial
  Machine Learning," arXiv:2604.15531** — a falsification audit for machine
  learning backtest workflows. It defines effective multiplicity K_eff as the
  spectral participation ratio of the correlation matrix of in-sample
  statistics, the same quantity this project reports as effective breadth,
  and shows E[max] = Θ(√log K_eff) under structured correlated search. There
  K_eff scales a maximum of unit-variance statistics, where no double
  counting arises; this project's anti-conservativeness result (§10) is
  specific to plugging it into DSR-L, whose cross-sectional variance term
  already shrinks as trials correlate. The paper treats the Reality Check and
  SPA as the appropriate layer for a search-adjusted p-value and does not
  analyze searches that build on their own best results.
- **Miao, J., Pritchard, J.K. & Zou, J. (2026), "The Agentic Garden of
  Forking Paths," arXiv:2607.01507** — logs every specification fitted by
  persona-conditioned AI agents over ten sequential rounds, and defines the
  m-value, the probability that a plausible analysis path yields a result at
  least as extreme as the reported one, estimated by an "Agentic Bootstrap"
  over agent-sampled paths. The closest prior work to this project's agent
  arm: it builds a reference distribution from logged agent search, but in
  general empirical research rather than backtests, without a data-snooping
  test, and without analyzing the order in which agents try specifications.
- **Politis, D.N. & Romano, J.P. (1994), "The Stationary Bootstrap,"
  Journal of the American Statistical Association 89(428)** — already
  cited in §1 as the resampling theory the joint row-bootstrap rests on;
  named here again because it is the mechanism underneath White (2000)
  itself, not an independent addition on top of it.

`estimator_build_spec.md` §1.2 originally presented Bailey & López de
Prado's closed-form deflated Sharpe ratio as the prior art this project
improves on. That is corrected there. The closed form is a parametric
shortcut for approximately the quantity the Reality Check estimates
non-parametrically, and it stays in this repository as a baseline. White
(2000) is the actual predecessor, and this project's contribution sits
inside that framework rather than beside it.

## 7. This is a known phenomenon, not a novel one

- **Leeb & Pötscher (2005)**, *Model Selection and Inference: Facts and
  Fiction*, Econometric Theory — proves the sampling distribution of a
  post-model-selection estimator cannot in general be consistently estimated
  by any procedure that treats the selected model as fixed, because the map
  from data to "which model was selected" is discontinuous in the data.
- **Efron (2014)**, *Estimation and Accuracy after Model Selection*, JASA —
  the prescription: the bootstrap must re-run the *selection step* inside
  every replicate, not just resample data underlying an already-fixed
  selected model. `recursive_bootstrap.py` does this via reconstruction;
  `procedure_level_bootstrap.py` does it literally, with no dependency.
- **Berk, Brown, Buja, Zhang & Zhao (2013)**, *Valid Post-Selection
  Inference* (PoSI), and **Lee, Sun, Sun & Taylor (2016)**, *Exact
  Post-Selection Inference, with Application to the Lasso* — the
  selective-inference program: conditioning on a data-dependent selection
  event changes the correct reference null distribution, and substituting
  the marginal/unconditional null is systematically anti-conservative. This
  is the analytic alternative to re-simulation (§8, route 2).
- **Benjamini & Yekutieli (2005)**, *False Discovery Rate–Adjusted Multiple
  Confidence Intervals for Selected Parameters* — the same principle inside
  the multiple-comparisons framing this project otherwise sits in.

## 8. What's validated, what's fixed, and what's still open

**Validated at n=200, properly powered, matched seeds:** the naive bootstrap
is correctly calibrated for any search whose candidate menu is data-oblivious
— any trial count from 1 to several thousand, any correlation among
candidates including exact duplicates — covering Honest/Greedy/GridSearch-
shaped agent behavior: an agent that decides its *menu* up front, even a
huge and correlated one, and reports the best result.

**Fixed, with a known dependency:** sequential search where later trials are
chosen conditional on earlier realized outcomes (Adaptive) is calibrated
under the recursive bootstrap *provided* the specification class is
algebraically rich enough to reconstruct untried candidates from already-
logged ones (linearity, here). Validated independently against a
reconstruction-free gold standard (§3). This is not guaranteed for a general
searcher, and is not guaranteed at all for an LLM agent.

**Still open, stated rather than hidden:** the procedure-level bootstrap is
the fully general fix, but it requires re-running the search B times. A
scripted searcher's `run()` is cheap and deterministic, so this costs
B× the compute. An LLM agent is neither: re-running it B times means B×
the token cost, and the agent isn't deterministic, so "re-running the same
procedure" doesn't even mean the same thing it means for code. Three
candidate routes past this, none yet tried:

1. **A surrogate searcher** fitted to the agent's own selection behavior —
   approximate the agent's decision policy with something cheap and
   deterministic enough to re-run B times, trading exactness for
   tractability.
2. **Conditional selective inference** (Lee, Sun, Sun & Taylor 2016-style) —
   an analytic correction conditioning on the realized selection event
   directly, rather than re-simulating it at all.
3. **Plain sample splitting** — reserve part of the in-sample data purely
   for the agent's exploration and a separate slice purely for evaluating
   whatever it finally selects, sidestepping the multiple-testing correction
   entirely at the cost of using less data for search and less for
   evaluation.

Which of these actually works against a real agent is a genuinely open
question. Finding the exact boundary of the transcript-only claim — and
having three concrete routes past it, rather than one clean result that
would have quietly assumed obliviousness — is the more interesting thing to
have going into Phase 2.

## 9. Experiment 2: predictive power under the alternative — a complicated result

Everything above is null-calibration (`s=0`): it shows the estimator
doesn't cry wolf. It says nothing about whether deflation actually predicts
out-of-sample Sharpe better than the alternatives — the number a reviewer
of the original proposal would ask for first. Before spending this
experiment's budget, a cheap precondition check
(`experiments/e6_pilot_signal_landscape.py`) confirmed the `s=3` DGP isn't
degenerately unimodal the way `s=0`'s search landscape turned out to be
(§5): GridSearch at `N ∈ {10,100,1000}` picks a different support on 100%
of 20 draws, and realized decay grows monotonically with `N` (0.26 → 0.93
→ 1.13). Worth running the full sweep.

`experiments/e7_predictive_power.py`: `N ∈ {10,100,1000} × ρ ∈
{0,0.3,0.6,0.9}`, `K=40`, `s=3`, sigma calibrated per `ρ` so the oracle
ceiling stays fixed at Sharpe 1.0 across the grid, n=100 draws/cell,
GridSearch as the trial-budget knob. Four predictors of `SR_OOS` compared:
naive `SR_IS`, closed-form DSR (raw `N` and effective `N`), bootstrap
deflation.

**Per-draw RMSE: closed-form (raw N) wins, not bootstrap — reported
straight, not the hoped-for headline.** In 11 of 12 grid cells, closed-form
DSR with the raw (uncorrected) trial count has the lowest RMSE against
`SR_OOS`, narrowly but consistently ahead of bootstrap deflation; the
effective-N variant is usually worse than both. Every predictor's R² is
negative at every grid point, deflated ones included — none of them beat
predicting the flat mean of `SR_OOS` for every draw. Deflation clearly
improves on naive `SR_IS` (whose RMSE is far worse throughout), but at this
configuration none of the three corrections has positive per-draw
predictive power; `SR_OOS`'s own measurement noise (`T_oos=300`) likely
swamps the differences between methods that are all noisy statistics of a
noisy quantity.

**Decay tracking tells a different, more favorable story — a different
criterion, not a contradiction.** Averaged over draws, bootstrap's
predicted decay (`SR_IS - SR_deflated`) sits closer to realized decay
(`SR_IS - SR_OOS`) than closed-form's does, at every one of the 12 grid
points — e.g. at `N=1000, ρ=0`: realized 1.784, bootstrap 1.838 (off by
0.054), closed-form 2.075 (off by 0.291). Bootstrap is the better estimate
of *average* decay; closed-form is the better *per-draw point predictor* on
RMSE. Those are different properties — an unbiased-but-noisier estimator
can lose on RMSE to a biased-but-stabler one when per-draw noise dominates,
which is the regime `SR_OOS` measurement noise appears to put this
experiment in. Reported as two separate findings rather than collapsed
into one "which method wins" verdict, because they don't agree and
forcing an answer would hide that.

**The ρ=0 "free" consistency check did not pass cleanly, and the reason
was checked rather than assumed.** Spec §4.4's premise: at ρ=0, bootstrap
and closed-form should agree. They don't — mean(bootstrap − closed-form)
is +0.051, +0.117, +0.237 at `N=10/100/1000`, growing with `N`, not flat.
Two hypotheses were checked, one ruled out and one confirmed:

- *Trial-Sharpe skewness growing with N, breaking closed-form's Gaussian
  assumption more as N grows* — checked directly (15 draws per N,
  `scipy.stats.skew` on the trial-Sharpe vector): skewness is 0.170, 0.005,
  −0.015 at `N=10/100/1000` — flat to slightly declining, not growing.
  Ruled out.
- *"ρ=0" does not mean "trials independent" for a combinatorial searcher* —
  checked directly: mean absolute off-diagonal trial correlation at ρ=0 is
  **0.098 at N=100 and 0.099 at N=1000** — nowhere near zero. GridSearch's
  candidate subsets share constituent features (the pair `{a,b}` and the
  pair `{a,c}` both carry feature `a`'s contribution), so trials are
  correlated by construction regardless of the feature-level `ρ` parameter.
  Confirmed: `ρ=0` does not buy independent trials for this searcher, so
  the premise behind treating it as a clean agreement check was already
  weaker than the spec's framing suggested.

This explains *that* the two methods should be expected to diverge even at
`ρ=0` for a combinatorial searcher — closed-form's raw-N formula assumes
independence that isn't actually present. It does **not** explain why the
gap *grows* with `N`, since the measured correlation level itself is flat
across `N` (0.098 → 0.099). That part is still open, stated as such rather
than forced into the tidy story the first hypothesis would have been.

**Net assessment.** This is not the clean "bootstrap beats the
alternatives" result that would most simply close the gap the project
still has (§8: a rigorous negative result, a fix, a boundary, a
dose-response — no single number yet showing the method beats what it's
meant to replace). It's a real, mixed result: deflation beats naive
prediction; bootstrap tracks average decay better than closed-form;
closed-form has lower per-draw variance and wins on RMSE anyway; the
ρ=0 baseline check surfaced a genuine, partially-explained anomaly rather
than a clean pass. Reported in full rather than led with the more flattering
half of it.

## 10. Experiment 2 rerun with both DGP fixes: bias is the metric that actually distinguishes the three corrections

*Figures: `figures/e9_decay_vs_N.png` (spec §4.3's decay-vs-trial-budget
figure, one panel per ρ) and `figures/e9_bias_vs_rho.png` (spec §4.4's
correlation-sensitivity figure, all three methods at N=1000). Both are
built directly from the results table below — `experiments/
plot_predictive_power.py`, no new experiment runs.*

Two changes, made in a specific order because the order is what makes them
defensible. First, a criterion was written down and checked *before*
touching the DGP or looking at any RMSE (§9's own instinct, made explicit):
target SD across draws must exceed the ~0.917 Lo(2002) measurement-noise
floor a 300-period OOS realization carries. It failed for **both**
equicorrelation and a new heterogeneous Σ_x (`environments/dgp.py`'s
`heterogeneous_correlation` — a single-factor structure with per-feature
loadings drawn once, replacing the exchangeability that's harmless under
`s=0` but collapses the achievable-Sharpe spread under `s>0`): target SD
0.005–0.21 against a 0.917 floor, everywhere. That settled which fix was
load-bearing: analytic scoring (`analytic_sharpe`, the same closed-form
algebra as the oracle formula, generalized to any weight vector — derived
independently, verified against simulation, `tests/test_analytic_sharpe.py`)
is necessary, not optional. Heterogeneous Σ_x is a real but smaller,
ρ-dependent improvement on top, mattering most at high ρ.

Both fixes applied, same grid, n=100/cell (`experiments/
e9_predictive_power_v2.py`):

**RMSE narrows and the winner stops being clean.** With the noise-free
target, closed-form(raw) and bootstrap are now close throughout — each
wins some cells, neither by much (e.g. `N=1000, ρ=0.9`: raw 0.665 vs boot
0.667; `N=1000, ρ=0`: raw 0.429 vs boot 0.388, boot wins here). The
previous experiment's clean raw-N win was partly an artifact of comparing
against a noisy target that rewarded low-variance predictors regardless of
bias; with that noise gone, the two are close to tied on RMSE.

**R² is still deeply negative — for a different reason than before, worth
naming rather than leaving as a loose end.** Target SD is now 0.02–0.21
(exact, no measurement noise) while RMSE sits at 0.4–0.7 for every
predictor: the between-draw variation in true achievable Sharpe is modest
*by construction* (`calibrate_sigma` fixes the oracle ceiling at the same
target across every draw, so how much any search's outcome can vary from
draw to draw is bounded), not because of leftover noise. R² divides a
large error by a small target variance and comes out triple-digit negative
almost everywhere — a property of this experimental design's fixed-ceiling
choice, not evidence the estimators lack predictive power. RMSE and bias
are the metrics that mean something here; R² does not, and reporting it
without this caveat would be misleading in the other direction from the
original noise-floor problem.

**Bias is the metric that actually distinguishes the three corrections —
the reframing this section is named for, checked point by point rather
than assumed.** Bias = mean(predicted decay − realized decay); positive
means over-deflates (too conservative), negative means under-deflates
(anti-conservative).

| | bias(raw) | bias(effective-N) | bias(bootstrap) |
|---|---|---|---|
| ρ=0, N=10→1000 | +0.063 → +0.262 (growing) | −0.013 → −0.466 | +0.029 → +0.017 |
| ρ=0.3, N=10→1000 | +0.015 → +0.097 (small) | −0.348 → −0.937 | +0.010 → −0.030 |
| ρ=0.6, N=10→1000 | +0.007 → +0.017 (~flat) | −0.373 → −0.825 | +0.008 → −0.031 |
| ρ=0.9, N=10→1000 | −0.005 → −0.023 (~zero) | −0.280 → −0.561 | −0.004 → −0.022 |

**Bootstrap is the only one of the three that's close to unbiased,
everywhere on this grid** — bias stays within roughly ±0.03–0.08 across
every `(N, ρ)` cell, an order of magnitude smaller than either alternative's
worst case. That part of the predicted reframing holds cleanly.

**Effective-N is substantially anti-conservative throughout, and does get
much worse once trials are correlated at all — but the shape isn't
monotone in ρ, and that's reported rather than smoothed over.** Its bias
is small at ρ=0 (−0.01 to −0.47) and jumps immediately once ρ≥0.3 (−0.28
to −0.94). But holding `N=1000` fixed and reading across ρ: −0.47 (ρ=0) →
**−0.94 (ρ=0.3, the worst point)** → −0.83 (ρ=0.6) → −0.56 (ρ=0.9) — it
peaks at moderate correlation and eases somewhat by ρ=0.9, not
monotonically worst at the highest correlation tested. A plausible
mechanism, not yet verified: the eigenvalue-based effective-N shrinks
toward 1 as ρ→1 (near-duplicate trials collapse to "one effective trial"),
which caps how little deflation it can apply at the extreme end even as it
remains badly anti-conservative throughout. Stated as a hypothesis because
it hasn't been checked the way every other claim in this document has.

**Raw-N is conservative, but only where trials aren't too correlated —
the "widens with trial count" part of the prediction holds conditionally,
not unconditionally.** At ρ=0, raw's bias grows clearly with N (+0.063 →
+0.180 → +0.262). At ρ=0.3 the same direction holds but far more weakly
(+0.015 → +0.056 → +0.097). By ρ=0.6–0.9 the bias is near zero and even
flips slightly negative at the highest `N`. Raw-N's over-deflation is real
at low correlation and fades as correlation rises — which makes sense
given raw-N was already known to over-correct by ignoring correlation
(§1): at high ρ, "ignoring correlation" costs it less because there's
less independent breadth to over-penalize in the first place.

**The ρ=0 consistency check replicates exactly, confirming it's a property
of the searcher, not the Σ_x variant.** +0.033, +0.102, +0.245 at
`N=10/100/1000` — essentially identical to the original grid's +0.051,
+0.117, +0.237 (§9's explanation: `heterogeneous_correlation` returns the
identity at ρ≤0, same as equicorrelation there, so nothing about this
specific comparison should have changed, and it didn't). The still-open
question from §9 — why the gap *grows* with `N` — remains open here too.

**Net assessment.** The honest headline is the one proposed before this
section was written, and the data supports it with real texture rather
than rubber-stamping it: bootstrap deflation is the only one of the three
corrections that is close to unbiased for average decay across this
entire grid. Closed-form with the raw trial count is conservative, but the
size of that conservatism depends on correlation in a way the closed form
doesn't account for, shrinking toward zero as trials get more correlated.
The eigenvalue-based "sophisticated" alternative is substantially
anti-conservative everywhere trials are correlated at all — which is the
regime real searches live in — and that's true even though its exact
severity doesn't increase monotonically with correlation. None of the
three has much per-draw predictive power in the R²/RMSE sense on this
grid, for a reason tied to this design's fixed oracle ceiling rather than
to any estimator's quality.

**Experiment 2, as specified, is done.** §4.2 (predictive power: RMSE/R²
across all three corrections), §4.3 (scaling: decay tracked against trial
budget, `figures/e9_decay_vs_N.png`), and §4.4 (correlation sensitivity,
folded in rather than run separately, `figures/e9_bias_vs_rho.png`) are
all covered by the single grid in this section. What's genuinely left open
is stated above rather than implied: why the ρ=0 consistency gap grows
with `N` (§9), and whether effective-N's non-monotone-in-ρ anti-
conservatism has the eigenvalue-shrinkage explanation offered here or a
different one — both flagged as unverified, not folded into the headline.

**A conflation caught and corrected: "power rises with correlation" was
never a finding about the estimator.** An earlier draft of this section
reported power (frac. `p<0.05`) rising from 0.16 at ρ=0 to 0.43 at ρ=0.9
and explained it via rising alignment between the submitted spec and the
true signal (0.254 → 0.927). Both numbers are real, but the framing was
wrong: power is a function of effect size, and mean true OOS Sharpe of the
submitted spec — computed from data already on disk, no reanalysis needed
— rises sixfold across the same axis:

| ρ | 0.0 | 0.3 | 0.6 | 0.9 |
|---|---|---|---|---|
| mean true SR_OOS, N=1000 | 0.205 | 0.613 | 0.810 | 0.926 |
| within-cell SD, N=1000 | 0.202 | 0.105 | 0.071 | 0.041 |

"Alignment climbs 0.254→0.927" and "true OOS Sharpe climbs 0.205→0.926"
aren't an explanation and an observation — in this linear DGP, `SR ∝`
alignment, so they're one fact stated twice. The genuinely explanatory
number is the row underneath: **within-cell SD collapses from 0.20 to
0.04.** At high ρ, heterogeneous Σ_x means essentially every path through
the feature space arrives at nearly the same place near the ceiling —
there is almost nothing left to get wrong. That's why detection gets
easier (there's more effect size to detect) and why exact identification
simultaneously gets rarer and stops mattering (§ above). Reported
correctly, this is a property of the DGP's difficulty gradient across ρ,
not evidence the estimator's sensitivity improves with correlation — that
would license a conclusion about the method the data doesn't support.

**Stated as a limitation, not folded into a rising trend that reads
better than it is: power at ρ=0 is 0.04, 0.07, 0.16 at `N=10/100/1000`.**
At `N=10`, power (0.040) is *below* nominal α=0.05 — the estimator does
not reliably detect a real signal in the cleanest, hardest regime at this
effect size. That is not a bug. `SR_OOS_true≈0.15-0.21` at ρ=0 is a weak
alternative sitting under enormous overfitting noise (§ below), and a
correctly conservative test has limited power against a weak alternative
by construction — the same property that makes the null-calibration work
in §§1-7 trustworthy in the first place. Stated plainly so it isn't
mistaken for the headline number.

**The deconfounded power axis is signal strength, not correlation** —
spec §2.2's own difficulty knob (target oracle Sharpe swept over
`{0.5, 1.0, 2.0}`), holding ρ=0 fixed so there is no correlated-noise
substitute inflating effect size for free
(`experiments/e10_power_vs_signal_strength.py`):

| target oracle Sharpe | 0.5 | 1.0 | 2.0 |
|---|---|---|---|
| power, N=10 | 0.050 | 0.090 | 0.160 |
| power, N=1000 | 0.060 | 0.110 | 0.350 |
| mean true SR_OOS, N=10 | 0.048 | 0.120 | 0.442 |
| mean true SR_OOS, N=1000 | 0.054 | 0.210 | 0.882 |

With ρ held fixed, power tracks effect size cleanly and monotonically at
both trial budgets — the curve the earlier, confounded ρ-sweep was
mistaken for. And at the weakest tested signal (target=0.5, true
`SR_OOS≈0.05`), power sits right at nominal α regardless of `N` — a search
budget cannot buy power against an effect this weak in the clean regime;
only a stronger true signal or (per the ρ-axis result above) a more
forgiving correlation structure can.

**A second confound, caught on the same review that caught the first
one: the table above still isn't a clean read on `N`.** Power rises with
`N` at fixed target Sharpe in the table above (e.g. target=2.0:
0.160→0.350) — but `deflate()`'s p-value is `P(M_b ≥ sr_sel)`, and adding
columns to the transcript can only make `M_b` stochastically *larger*
holding `sr_sel` fixed, so `p` should rise and power should *fall* as `N`
grows, always, if `sr_sel` genuinely doesn't change. Power rising means
`sr_sel` wasn't fixed: GridSearch finds a materially better specification
at larger `N` (more of the search space gets tried), so "search finds the
signal better" and "search costs you at test time" were still tangled
into one number — exactly the same shape of error the ρ-confound was, one
level down.

**Isolated properly**: `searchers/diagnostic.py`'s `PinnedSelector` builds
the identical combinatorial menu GridSearch does — same transcript size
and correlation structure growing with `N` — but always submits the true
signal triple, regardless of what any trial in that menu finds. For a
fixed draw this makes the submitted Sharpe exactly `N`-invariant by
construction (checked directly before running anything at scale: constant
to six decimals across `N=10/100/1000`, locked in as a regression test);
only the transcript around it grows. Whatever power does now is purely
the bootstrap's response to a larger transcript
(`experiments/e11_power_vs_N_pinned.py`, same ρ=0, same target-Sharpe
levels, n=100/cell):

| | N=10 | N=100 | N=1000 |
|---|---|---|---|
| power, target Sharpe=1.0 (mean pinned SR_IS=1.017) | 0.150 | 0.060 | 0.020 |
| power, target Sharpe=2.0 (mean pinned SR_IS=2.020) | 0.690 | 0.420 | 0.260 |

Power falls monotonically in `N` at both signal levels, exactly as
predicted before running this — a ~7.5× relative drop at the moderate
signal, ~2.65× at the strong one. **This is the pure multiple-testing
cost of having looked**, decoupled from the benefit of having looked:
holding the quality of what you found completely fixed, reporting it out
of a 1000-trial search rather than a 10-trial one costs you most of your
power to have it recognized as real. It's also the answer to why the
original (unpinned) table above showed power *rising* with `N`: that
number is the *net* of two real, opposing forces — search quality
improving with `N` (pushing power up) and the multiple-testing penalty
growing with `N` (pushing power down) — and in that specific experiment
the first force happened to dominate the second. That net-effect number
is not wrong, and it's the one an actual practitioner whose search
quality floats with budget would experience — but it is not "the
estimator's sensitivity," and reporting it as a rising power curve
without this decomposition would have handed a reviewer a claim the data
doesn't support.

Two separable curves, together: power rises in true effect size at fixed
search extent (this section's first table, both `N` levels move the same
direction). Power falls in trial count at fixed effect size (the table
just above). Both are real; neither is the other; a real searcher's
observed power is their sum.

The ρ axis stays exactly where §10's main table already puts it to best
use: showing the three corrections' bias diverge, which it does cleanly —
effective-N's error peaks at ρ=0.3 (−0.937), the signature of
double-counting correlation that raw-N ignores and effective-N
over-corrects for in the opposite direction.

**The single cell that makes the argument this whole project exists to
make, currently sitting as one row in a twelve-row grid — elevated here on
its own.** `ρ=0, N=1000`, mean over 100 draws:

| | value |
|---|---|
| Reported in-sample Sharpe | 2.028 |
| Oracle ceiling (no strategy can legitimately exceed this) | 1.000 |
| True out-of-sample Sharpe | 0.205 |
| Realized decay | 1.823 |
| Bootstrap-predicted decay | 1.840 (off by **+0.017**) |
| Raw-N DSR-predicted decay | 2.085 (off by +0.262) |
| Effective-N DSR-predicted decay | 1.357 (off by −0.466) |

A search reports 2.03 — double the population ceiling, a theoretically
impossible number given what's known about this DGP, and exactly the kind
of number that gets published because nobody can see the trial count
behind it. The truth is 0.21. Reading only the transcript, the bootstrap
calls the decay to within 0.017 on a decay of 1.82. Raw-N over-corrects by
14% of the decay; effective-N leaves roughly a quarter of the overfitting
standing. One cell, one table — this is the number a reviewer of the
original proposal would ask for first, and it was sitting unremarked in
row 3 of 12 until asked what the rest of the grid produced.

## 11. Sharpe is a fragile statistic for data-snooping corrections over sparse strategies

**The same 10,000-rule menu produced critical values from 2.03 to 155
across 20 data seeds.** Same rules, same sample length, same test; only the
simulated prices changed. A bar that moves by a factor of 75 is not measuring
the search.

The cause is the statistic. A Reality Check that re-estimates each
candidate's Sharpe ratio inside every bootstrap replicate can be dominated
by candidates that are rarely in the market. A resample that catches few of
such a rule's active periods can shrink its standard deviation faster than
its mean, and the ratio explodes. A handful of those rules then set the null
maximum, and the verdict is decided by the arithmetic of near-empty
resamples rather than by the breadth of the search. Realistic trading-rule
universes (band filters, breakouts, event rules) contain exactly such
rules. None of the experiments in §§1–10 are affected: `Specification` is
linear in continuous features, so every candidate there takes a position in
every period.

**Evidence**, found while building the gate's bundled examples
(`garden/examples.py`): a 10,000-rule moving-average crossover grid with
band filters, 4 years of simulated daily prices, 20 data seeds.

- The critical value at α=0.05 ranged from **2.03 to 155** across seeds.
- On one seed, the top decile of bootstrap null maxima came from rules in
  the market on a median **0.3%** of days, against a median of 30% across
  all rules, and the argmax search submitted a rule active on 2.9% of days.
  In a 10-year, 368-rule band grid, the argmax search submitted a rule
  active on 0.2% of days: five days in ten years.
- `estimator.bootstrap.sharpe` returned **1.2×10¹⁵** on one replicate, a
  resample with no active periods where floating-point round-off left a
  nonzero standard deviation.

Dropping band filters, so every rule is long-short or long-only and the
least active rule trades on at least 16% of days, brought the critical
value to 1.60–1.74 across the same 20 seeds.

**Why the published formulations don't fail this way, and why neither is
free.** White (2000) used a non-studentized statistic, mean performance,
which has no denominator to collapse. But a non-studentized maximum is
dominated by high-variance candidates, including poor ones, which is
Hansen's (2005) reason for studentizing. Hansen studentizes by a standard
deviation estimated once from the full sample and held fixed across
replicates, which cannot collapse either. This project's estimator
re-estimates the standard deviation inside every replicate, the only one of
the three formulations whose denominator can go to zero. White's mean-based
statistic and Hansen's fixed studentization both look incidental until a
menu contains sparse rules; for that case they are load-bearing.

**What follows.** Filtering rules by how often they trade would make the
menu data-dependent (§1), so the gate cannot fix this by exclusion. It
detects it and refuses instead: status DEGENERATE (exit code 4) when more
than half of the top 10% of replicates, the ones that set the critical
value, take their maximum from a resample with fewer than 50 distinct active
periods, or when excluding those resamples would change the verdict.

Calibration took two pre-registered runs. e13
(`experiments/e13_degeneracy_calibration.py`) defined a broken bar as a
verdict that flips under fixed studentization. Only 23 transcripts met that
definition, and its rule chose thresholds that also refused 343 of 397
sparse transcripts whose verdicts agreed, many with critical values no more
distorted than dense ones (median 1.01× the fixed-studentization value in the
368-rule grid). e14 (`experiments/e14_degeneracy_recalibration.py`, committed
before it ran, fresh seeds, 9,000 dense and 2,200 sparse transcripts) called
a bar broken when the verdict flips or the critical value falls outside the
central 99% of the dense ratio, [0.959, 1.105], and allowed at most 10%
refusals of sound bars. Its rule chose the thresholds above:

| population | refused | 95% CI |
|---|---|---|
| dense transcripts | 0 of 9,000 | upper bound 0.033% |
| sparse, broken bar | 792 of 882 (89.8%) | 87.6–91.6% |
| sparse, sound bar | 54 of 1,318 (4.1%) | 3.2–5.3% |

In the 368-rule grid, where e13 over-refused, that is 148 of 187 broken bars
and 3 of 813 sound ones. The chosen support threshold, 50, is the largest
value in e14's grid, so a larger one might do slightly better; testing that
would need fresh seeds again. Phase 2's SPA, implemented with Hansen's
fixed full-sample studentization, is the natural structural fix and should
be run against the band-filter grid above. Whether the gate should offer a
mean-return statistic is logged in `OPEN_QUESTIONS.md`.

## 12. Type-M exaggeration as a function of power

**Passing results from low-power searches overstate the edge by up to an
order of magnitude, and the gate's own power figure cannot tell you how
much.** Bootstrap `sr_deflated` is unbiased unconditionally (§10: mean error
−0.005 across 1,200 draws). Conditional on passing it is not, and a pooled
figure hides how much: across §10's grid the 369 passes overstated the true
Sharpe by 1.84×, but passes come mostly from high-power cells, so that
number describes the regime where exaggeration is mildest.

`experiments/e12_type_m_by_power.py` measures it where the gate's warning
fires. §10's regime (ρ=0, K=40, T=600, GridSearch, argmax submission) at one
breadth, N=100, sweeping target oracle Sharpe so power moves from near α to
high. Each cell draws until it has 200 passes; a draw's bootstrap stops as
soon as it cannot pass, which gives the same pass/fail as the full B=1500
and makes failing draws nearly free. Prediction, stated in the script
before running: both the ratio and the gap fall monotonically as power
rises.

| target Sharpe | draws | search power (95% CI) | true Sharpe of passing picks | deflated ÷ true (95% CI) | deflated − true (95% CI) | gate single-strategy power (median) |
|---|---|---|---|---|---|---|
| 0.5 | 3,471 | 0.058 (0.050–0.066) | 0.067 | 11.94 (10.02–14.66) | +0.728 (+0.704 to +0.755) | 0.001 |
| 1.0 | 2,136 | 0.094 (0.082–0.107) | 0.262 | 3.11 (2.78–3.53) | +0.553 (+0.515 to +0.594) | 0.003 |
| 1.5 | 1,218 | 0.164 (0.144–0.186) | 0.543 | 1.55 (1.42–1.72) | +0.299 (+0.244 to +0.356) | 0.008 |
| 2.0 | 672 | 0.298 (0.264–0.333) | 0.820 | 1.10 (1.02–1.18) | +0.079 (+0.017 to +0.141) | 0.015 |
| 3.0 | 303 | 0.660 (0.605–0.711) | 1.411 | 0.75 (0.70–0.79) | −0.357 (−0.437 to −0.277) | 0.076 |
| 4.0 | 226 | 0.885 (0.837–0.920) | 2.038 | 0.67 (0.64–0.71) | −0.672 (−0.764 to −0.577) | 0.774 |

**The prediction holds on both rows.** Two things it did not predict:

- **The bias changes sign near 30% power.** Below it, a pass requires the
  winner's noise to land far out in the tail, so its deflated Sharpe
  overstates the truth. Above it, the winner is mostly signal, its reported
  Sharpe carries little selection luck, and subtracting the mean null
  maximum over-deflates it. "Conditional on passing, sr_deflated is
  upward-biased" is true only in the low-power regime, which is where the
  gate's warning fires.
- **The gate's single-strategy power is not on the search-power axis.**
  Computed at the passing pick's own true Sharpe, it read 0.1%–7.6% in the
  cells where search power was 6%–66%. The search passes because it
  selects a lucky pick, not because that pick's true edge would usually
  clear the bar. So the gate cannot index this table with its own power
  figure: doing so would print 12× for a search whose real exaggeration is
  1.6×. The warning quotes the curve and says it cannot place the search on
  it.

Scope: one DGP, one breadth, one searcher. The monotone shape is the
general part (it is the standard type-M result); the crossover near 30% and
the exact ratios belong to this configuration.

## 13. Single-strategy power is not a bound on search power

The gate prints power for a single pre-specified strategy. An earlier draft
called it a lower bound on search power, reasoning that a search's maximum
can only raise the reported Sharpe. That holds within one transcript, where
the null maximum is shared, but the comparison is across designs, and
measured it fails. Matched cells, same DGP (ρ=0, K=40, M=60, T=600), n=100
each: GridSearch submitting its best spec (e10, plus N=100 cells run for
this comparison with e10's seeds) against the pinned selector submitting the
true signal triple (e11):

| N | target Sharpe | search power | single-strategy (pinned) power | search − pinned | z | mean true Sharpe of search's pick |
|---|---|---|---|---|---|---|
| 10 | 1.0 | 0.09 | 0.15 | −0.06 | −1.3 | 0.120 |
| 100 | 1.0 | 0.11 | 0.06 | +0.05 | +1.3 | 0.145 |
| 1,000 | 1.0 | 0.11 | 0.02 | +0.09 | +2.6 | 0.210 |
| 10 | 2.0 | 0.16 | 0.69 | −0.53 | −9.0 | 0.442 |
| 100 | 2.0 | 0.26 | 0.42 | −0.16 | −2.4 | 0.732 |
| 1,000 | 2.0 | 0.35 | 0.26 | +0.09 | +1.4 | 0.882 |

The sign depends on breadth. The edge here sits in one feature triple among
10,700 candidate subsets. A 10-specification search rarely contains it (its
pick's mean true Sharpe is 0.12 and 0.44 against oracle ceilings of 1.0 and
2.0), so it forgoes most of the edge and detects far less often than a
strategy pinned to it. A 1,000-specification search reaches specifications
carrying part of the edge and adds selection luck on top, so it detects
more often. The bundled `overwide` example, whose rules all share exposure
to one crossover signal, is on the "more often" side: 6 of 20 seeds passed
at 7–11% single-strategy power. Which side a real search is on depends on
where the edge sits in its menu, which the transcript does not reveal, so
the gate prints the single-strategy figure and states no direction.
INADMISSIBLE does not need the bound: it only ever replaces FAIL.

## 14. Which anchor rule distorts the naive bootstrap: coupling to the selection statistic

**Adaptivity alone does not distort the naive bootstrap. Only the menu built
around the selection statistic's own winner did.** Four searchers differing
only in round 2's anchor rule, with max_features=2 so the anchor is the only
data-dependent step in the menu: n=500 paired null draws, K=20, M=50, T=500,
ρ=0.3 (equicorrelated features), B=1500. Pre-registered and committed before
running (`experiments/e15_anchor_coupling.py`), after fixing the bug that had
made §5's NeighborAdaptive identical to Adaptive.

| anchor rule | coupling to the selection statistic | naive type-I (95% CI) | naive KS p | recursive type-I (95% CI) | recursive KS p |
|---|---|---|---|---|---|
| winner (round-1 Sharpe argmax) | maximal | **0.082** (0.061–0.109) | 0.0015 | 0.046 (0.031–0.068) | 0.358 |
| neighbor (most correlated with the winner) | intended weaker | 0.036 (0.023–0.056) | 0.321 | 0.038 (0.024–0.059) | 0.441 |
| random (searcher's own seed; oblivious control) | none | 0.040 (0.026–0.061) | 0.683 | 0.040 (0.026–0.061) | 0.608 |
| worst (round-1 loser) | opposite | 0.032 (0.020–0.051) | 0.116 | 0.038 (0.024–0.059) | 0.420 |

Exact McNemar tests on the paired naive rejections, winner against each rule:
23–0 against neighbor (p = 2.4×10⁻⁷), 21–0 against random (p = 9.5×10⁻⁷), and
25–0 against worst (p = 6.0×10⁻⁸). Every discordant draw is one the winner rule
rejected and the other did not. On recursive p-values no rule differs from
winner (p = 0.45–0.66).

**Against the pre-registered predictions.** Held: random's CI contains 5%, so
the control is intact; worst is at or below 5%; recursive is near 5% for all
four. Failed: the strict order winner > neighbor > random, since neighbor
(0.036) came out below random (0.040). Neighbor is decisively distinguishable
from winner, so §5's "the rule doesn't matter" is refuted, not rescued.

**Why neighbor did not land in between (measured afterwards; exploratory).**
With equicorrelated features, every feature is equally correlated with the
winner in expectation, and the "most correlated neighbor" is picked by
sampling noise. Over 200 of e15's seeds, the anchor's rank among the 20
single-feature Sharpes averaged **11.0 for neighbor and 10.7 for random**
(uncoupled: 10.5), against 1 for winner and 20 for worst. Its correlation with
the winner averaged 0.36 against random's 0.30, which is just the maximum of 19
noisy correlations spread 0.23–0.36. In this design the fixed neighbor rule
carried essentially no coupling, so the graded middle of the prediction was
not tested. Paired, neighbor minus random is −0.004 (95% CI −0.010 to +0.002).

**What this establishes.** A menu chosen by a data-dependent rule that is
uncoupled from the selection statistic (neighbor, here) or coupled against it
(worst) keeps the naive bootstrap at nominal. A menu built on the statistic's
own argmax inflates it: 8.2% with one extension round, against 12.7% for
Adaptive's two rounds on the same settings in §5. The recursive bootstrap
corrects all four. Whether the distortion grades with coupling strength or
switches on only for the argmax needs rules with genuine intermediate
coupling (OPEN_QUESTIONS.md). e5's saved NeighborAdaptive arrays and figures
are Adaptive's and have not been regenerated.

## 15. E16: winner-anchoring's distortion is the pointwise dominance the order-statistic lemma predicts

**For a search that builds round 2 on its round-1 winner, the process null
maximum was at least the realized-menu maximum in 99.9% of bootstrap
replicates, and the naive p-value was at most the recursive one in all 500
draws.** Pre-registered in `prereg/E16.md` and committed before running
(`experiments/e16_pointwise_dominance.py`): winner- and worst-anchored
two-step searches (max_features=2), n=500 fresh seeds (20000–20499), e15's
configuration (K=20, M=50, T=500, ρ=0.3 equicorrelated, s=0), B=1500. Both
nulls were built on the same resampled time indices, so each replicate's
two maxima compare directly.

| anchor | draws in the predicted direction (95% CI) | exact ties | replicates: M_P > M_C / equal / M_P < M_C | naive type-I (95% CI) | recursive type-I (95% CI) |
|---|---|---|---|---|---|
| winner (predicted p_naive ≤ p_recursive) | 500/500 (0.992–1.000) | 3.0% | 68.5% / 31.5% / 0.1% | 10.2% (7.8–13.2) | 4.6% (3.1–6.8) |
| worst (predicted p_naive ≥ p_recursive) | 500/500 (0.992–1.000) | 6.6% | 0.0% / 86.3% / 13.7% | 4.2% (2.8–6.3) | 4.8% (3.2–7.0) |

Pre-registered gate: the winner fraction, 1.000, is at least 0.90, so the
lemma is supported as the mechanism behind §14 and E17–E22 proceed.

For the winner rule, the process maximum is strictly larger in 68.5% of
replicates, those where the resampled data's own winner differs from the
frozen anchor and the best pair beats the best single. The remaining 0.1%
are finite-sample departures from the exchangeable limit, too rare to
reverse any draw's p-value ordering. The worst rule mirrors it: the
realized-menu maximum is never below the process maximum and is strictly
above it in only 13.7% of replicates, because the singles maximum usually
dominates both menus. That is why worst-anchoring's conservatism is small
(naive 4.2% against recursive 4.8%). The fresh-seed naive type-I for the
winner rule, 10.2%, is consistent with e15's 8.2%.

## 16. E17: the naive bootstrap's distortion rises with how strongly the anchor tracks performance

**Across eight anchor rules running from loser-anchored to winner-anchored,
naive type-I rose from 3.6% to 7.0% in step with coupling, and the
pre-registered trend test decided for graded coupling (p = 0.0001).**
Pre-registered in `prereg/E17.md` and launched from the commit that added it
(254cdda, clean; recorded in the data file under its pre-rewrite hash
0cfcf52, see `prereg/COMMIT_MAP.md`; `experiments/e17_graded_coupling.py`). `GumbelAnchored(τ)`
with max_features=2 draws round 2's anchor with probability proportional to
exp(τ z_k). n=500 draws paired across all eight levels (seeds 30000–30499),
e15's configuration (K=20, M=50, T=500, ρ=0.3 equicorrelated, s=0), B=1500,
with the naive, recursive and full-class nulls on common resampled indices. κ
is the anchor's normalized Sharpe rank on the real data (1 best, 0 worst).

| τ | mean κ | naive type-I (95% CI) | KS p | recursive type-I (95% CI) | KS p | full-class type-I (95% CI) | KS p |
|---|---|---|---|---|---|---|---|
| −∞ (loser) | 0.000 | 0.036 (0.023–0.056) | 0.094 | 0.040 (0.026–0.061) | 0.401 | 0.020 (0.011–0.036) | <0.001 |
| −2 | 0.103 | 0.036 (0.023–0.056) | 0.086 | 0.040 (0.026–0.061) | 0.360 | 0.020 (0.011–0.036) | <0.001 |
| −1 | 0.217 | 0.038 (0.024–0.059) | 0.172 | 0.042 (0.028–0.063) | 0.513 | 0.020 (0.011–0.036) | <0.001 |
| 0 (random) | 0.502 | 0.050 (0.034–0.073) | 0.395 | 0.050 (0.034–0.073) | 0.395 | 0.024 (0.014–0.041) | <0.001 |
| 1 | 0.780 | 0.062 (0.044–0.087) | 0.953 | 0.042 (0.028–0.063) | 0.530 | 0.028 (0.017–0.046) | 0.001 |
| 2 | 0.904 | 0.068 (0.049–0.094) | 0.244 | 0.036 (0.023–0.056) | 0.680 | 0.032 (0.020–0.051) | 0.033 |
| 4 | 0.964 | 0.070 (0.051–0.096) | 0.034 | 0.040 (0.026–0.061) | 0.584 | 0.038 (0.024–0.059) | 0.213 |
| +∞ (winner) | 1.000 | 0.070 (0.051–0.096) | 0.009 | 0.038 (0.024–0.059) | 0.635 | 0.038 (0.024–0.059) | 0.635 |

Within-draw permutation trend tests across τ (one-sided, 10,000
permutations): naive, the primary test, p = 0.0001; recursive p = 0.80;
full-class p = 0.0001.

**Against the pre-registered predictions.**

- Held: κ rises monotonically with τ. Naive point estimates are
  nondecreasing in τ and at or below 5% for every τ ≤ 0. Recursive and
  full-class are not significantly above 5% at any τ.
- Missed: τ = +∞ was predicted to reproduce e15 and E16 at roughly 8–10%. It
  gave 7.0% (5.1–9.6). The three fresh-seed estimates of the winner rule, 41,
  51 and 35 rejections of 500 (e15, E16, E17), do not differ significantly
  (χ² = 3.37, 2 df, p = 0.19; not pre-registered). Pooled, they give 8.5%.
- Decision: trend p = 0.0001 < 0.01, so the note claims graded coupling.

**What the trend test does and does not show (exploratory, computed after
the decision).** The primary statistic rewards any increase across the eight
levels, and part of the evidence comes from the conservative half. Restricted
to τ ≤ 0 (3.6% → 5.0%) the trend gives p = 0.0002; restricted to τ ≥ 0,
p = 0.0001; among the coupled levels τ ≥ 1 alone (6.2% → 7.0%), only
p = 0.02. Paired McNemar tests put the clearest steps between loser and
random (7–0, p = 0.016) and between random and τ = 1 (6–0, p = 0.031); τ = 1
against winner is 5–1 (p = 0.22).

Within a level, the inflation concentrates on draws whose anchor sits at the
top. At τ = 1, 119 of 500 draws happened to anchor on the winner; they
rejected 9.2% of the time, against 5.2% for the rest. At τ = 2 it was 8.2%
(219 draws) against 5.7%. Pooled across levels, so that a draw counts once
per level, naive rejection conditional on the anchor's rank was 7.8% at rank
1 (n = 1,195), 8.7% at rank 2 (n = 323), 4.8% at rank 3 (n = 165), 6.2% at
ranks 4–5 (n = 243), and 2.8–3.8% from rank 6 down. Conditioning on the
anchor's rank selects draws, so these are not the type-I rates of any rule.
They suggest that a rule's inflation tracks how often it anchors among the
top few features, and anchors further down behave like the loser rule. A
plausible mechanism, not tested: an anchor ranked second pairs with the
winner, so the real menu already contains the best pair, exactly as under
winner anchoring, while the frozen menu does not follow the replicate's own
top features.

**Full-class.** Within a draw the full-class null is identical at every
level (same class, block length and resampled indices), so its p-value
moves only with `sr_sel`; it was nonincreasing in `sr_sel` on every draw. It
is conservative where the search does not chase winners, 2.0–2.8% at τ ≤ 1
with KS rejecting uniformity, because the selected pair is often well below
the class maximum (P3). It converges to the recursive null as the anchor
approaches the winner. At τ = +∞ the two p-values differ on 36 of 500 draws,
each time by exactly one replicate in 1,501 and always with the full-class
p larger; no rejection decision differs. P5 says the winner-anchored search
reaches the class maximum exactly at d = 2 in the Gaussian limit; the 36
single-replicate differences are finite-T departures of the same kind as
E16's 0.1% (§15). For the gate, the full-class verdict's cost is this
conservatism for searches that do not chase winners, a power cost E22
measures.

**Recursive** stays flat at 3.6–5.0% (trend p = 0.80). At τ = 0 its
p-values equal naive's on every draw, as they must: the random anchor comes
from the searcher's own seed, so the menu is data-oblivious and replay
rebuilds it unchanged.

**What this changes.** The note's P4 section can claim more than the two
endpoints: across intermediate rules, naive type-I rose with coupling, which
the planned winner-chasing audit's κ relies on. What E17 cannot support is
that intermediate coupling of an individual anchor produces intermediate
inflation; the exploratory breakdown points instead to a step near the top of
the ranking. That decides how the audit should summarize κ from a transcript
(the share of anchors among the top few features, or a mean rank), so it
needs its own pre-registered test before the audit is calibrated
(OPEN_QUESTIONS.md). The class enforcement added to `environments/sandbox.py`
after launch (575678a) has no effect without a declared class.

## 17. E18: search depth, re-anchoring, and whether recursive nulls coincide across beam widths

**At depth 3, the winner-anchored search inflated naive type-I to 10.4%,
while random and neighbor anchors stayed below what 1,000 draws can detect.
Greedy and beam searches reached the full-class maximum on 99.1–99.7% of
bootstrap replicates, and their recursive rejection decisions agreed on every
draw.** Pre-registered in `prereg/E18.md` and launched from the commit after
it (ab90365, clean; recorded in the data file under its pre-rewrite hash
eaf3782, see `prereg/COMMIT_MAP.md`; `experiments/e18_depth.py`). K=20, M=50,
T=500, ρ=0.3 equicorrelated, s=0, B=1500. The four anchor rules ran on n=1,000
draws (seeds 40000–40999) and the other searchers on the first 500 of them,
with the naive, recursive and full-class nulls on common resampled indices.
Wall time was 82 minutes on 32 cores.

| searcher | n | mean κ | naive type-I (95% CI) | KS p | recursive (95% CI) | KS p | full-class (95% CI) | KS p |
|---|---|---|---|---|---|---|---|---|
| winner | 1,000 | 1.000 | **0.104** (0.087–0.124) | <0.001 | 0.059 (0.046–0.075) | 0.592 | 0.059 (0.046–0.075) | 0.558 |
| neighbor | 1,000 | 0.475 | 0.050 (0.038–0.065) | 0.749 | 0.048 (0.036–0.063) | 0.714 | 0.019 (0.012–0.029) | <0.001 |
| random | 1,000 | 0.498 | 0.053 (0.041–0.069) | 0.559 | 0.047 (0.036–0.062) | 0.428 | 0.022 (0.015–0.033) | <0.001 |
| gumbel0 | 1,000 | 0.499 | 0.064 (0.050–0.081) | 0.880 | 0.055 (0.042–0.071) | 0.649 | 0.027 (0.019–0.039) | <0.001 |
| lattice | 500 | – | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 |
| beam16 | 500 | – | 0.060 (0.042–0.084) | 0.565 | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 |
| beam4 | 500 | – | 0.080 (0.059–0.107) | 0.103 | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 |
| beam2 | 500 | – | 0.084 (0.063–0.112) | 0.008 | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 |
| adaptive | 500 | – | 0.092 (0.070–0.121) | 0.001 | 0.054 (0.037–0.077) | 0.300 | 0.054 (0.037–0.077) | 0.300 |
| depth (d=4) | 500 | – | 0.096 (0.073–0.125) | <0.001 | 0.058 (0.041–0.082) | 0.274 | 0.058 (0.041–0.082) | 0.258 |

**Against the pre-registered readings.**

1. **Identity.** `winner` and `adaptive` gave identical p-values on their 500
   shared draws. Held.
2. **Random-rule consistency.** random 5.3% (4.1–6.9) and gumbel0 6.4%
   (5.0–8.1) each lie inside the other's interval. Held.
3. **Depth re-anchoring.** Predicted (a), partly inflated, for both rules.
   **Missed: both are (c), not detectably inflated.** neighbor had 50/1,000
   rejections (binomial p = 0.52) and random 53/1,000 (p = 0.35). McNemar
   separated each from winner (54–0 and 51–0, p < 10⁻¹⁵). A true rate below
   about 6.9% is not excluded.
4. **P5's mechanism.** Replicates on which the replayed value equals the
   full-class maximum: lattice 99.13%, beam16 99.70%, beam4 99.70%, beam2
   99.67%, adaptive 99.13%, all at or above 99%. On none of the 3.75 million
   dose-axis replicates was the replayed value above the class maximum. Held.
5. **P5's consequence.** Recursive rejection decisions of lattice and every
   beam width agreed with adaptive's on all 500 draws. Exact p-value
   agreement was 1.000 for lattice and 0.962–0.964 for the beams. Held.
6. **Nominal nulls.** No recursive or full-class rate is significantly above
   5%. The highest, winner's 5.9% for both, has binomial p = 0.11. Held.
7. **Dose axis.** Naive type-I 0.054 → 0.060 → 0.080 → 0.084 → 0.092 is
   nondecreasing. Held. In adjacent McNemar tests every discordant draw
   points the predicted way (lattice–beam16 0–3, p = 0.25; beam16–beam4
   0–10, p = 0.002; beam4–beam2 0–2, p = 0.50; beam2–adaptive 0–4,
   p = 0.13).

**The gray result: gumbel0 (not a registered test).** Reading 3 was
registered for neighbor and random only. gumbel0 is random's rule with
independent anchor draws, and under the same binomial rule it would have
counted as inflated: 64/1,000, p = 0.028, one rejection above the threshold
of 63. Pooled with random, it is 117/2,000 (5.85%, p = 0.048). Paired within
each rule, the naive p-value was at most the recursive one on 99.9% of draws
for both random and gumbel0. Every draw where only one of the two nulls
rejected was a naive rejection (6–0, p = 0.031; 9–0, p = 0.004). So the
direction the pre-registration predicted is present in the paired p-values,
and its size at α = 5% is at the edge of what n = 1,000 detects. The
registered outcome (c) stands, and the note says "not detectably inflated".
The neighbor rule does not show the same dominance (naive ≤ recursive on 68%
of draws, 2–0), because its replay re-selects the anchor from resampled
correlations (THEORY.md P6).

**P5 at depth 3, against the Gaussian limit.** The replayed value fell below
the class maximum on 0.87% of replicates for greedy search (adaptive and
lattice) and on 0.30–0.33% for beams of width 2 to 16; at d = 4, DepthAdaptive
fell below on 0.95%. THEORY.md's Gaussian limit predicts 0.19% at d = 3 and
0.28% at d = 4 for greedy search, and no difference between widths, since in
the limit every width returns the same value. At finite T, then, greedy's
shortfall is 3–5 times the limit's, and width 2 already removes about two
thirds of it. The 99% threshold held with room; the limit's magnitudes did
not. LatticeAdaptive selects with Adaptive's greedy rule, so the two had
identical recursive p-values and replicate counts; their `sr_sel` differed by
at most 9×10⁻¹⁶. Each beam's recursive p-value differed from adaptive's on
18–19 of 500 draws, always by one replicate in 1,501.

**Full-class against recursive.** The full-class p-value was at least the
recursive one on every draw of every searcher (P2, P3). For greedy, beam and
depth searches it was at most two replicates larger and never changed a
decision. For the anchor rules that do not chase winners it was far more
conservative (1.9–2.7% type-I, differing from recursive in 2.5–2.9% of
decisions), as in E17.

**Against earlier numbers.**

- **Dose axis.** It replaces §5's table (n=150, B=300, anchor bug) with the
  same shape at lower levels. Adaptive is 9.2% here against 12.7% there
  (Fisher p = 0.22).
- **Adaptive in §3.** That run's 13.6% (e4) is not like-for-like. The script's
  settings are K=25, M=60, T=600, and its block length is chosen on the
  transcript. Its naive `sr_sel` is the transcript maximum rather than the
  searcher's own selection, but for Adaptive those are the same value: E18b
  (below) swapped only that rule on E18's draws and no p-value changed. The
  rates differ (Fisher p = 0.036, not pre-registered). A rough limit
  calculation attributes about a point of that to K and leaves the rest at
  roughly 1.6 standard errors, so much of the gap may be noise
  (OPEN_QUESTIONS.md).
- **Depth.** The winner rule at d = 3 (10.4%) is not significantly above the
  d = 2 estimates pooled across e15, E16 and E17 (8.5%; Fisher p = 0.11,
  different seeds). DepthAdaptive's 9.6% against Adaptive's 9.2% is 3–1 paired
  (p = 0.63).

**What this changes for the note.** P5's consequence holds at d = 3 at the
level that matters: recursive verdicts for greedy search at any beam width,
and full-class verdicts, agreed on every draw. The replicate-level mismatch is
several times the Gaussian limit, so the note quotes the measured values, not
the limit's. For depth re-anchoring, the registered outcome is (c), not
detectably inflated, with the paired direction reported as exploratory
(OPEN_QUESTIONS.md).

**E18b: the scoring rule does not explain the gap to e4.** Pre-registered in
`prereg/E18b.md` and launched from its commit (8383b11, clean;
`experiments/e18b_scoring_rule.py`). On E18's 500 adaptive draws, with E18's
block lengths and resampled indices, the naive null was compared against the
largest Sharpe in the transcript instead of Adaptive's selected value.

- **Reproduction held.** Under E18's rule the p-values equal E18's stored ones
  on every draw.
- **No change, as predicted.** The two `sr_sel` values never differed by more
  than 4.4×10⁻¹⁵. Naive type-I was 0.092 (0.070–0.121) under both rules, with
  no discordant draws (McNemar 0–0). Early-stopping greedy search selects its
  own transcript maximum.

So the scoring rule is not the source of the gap between 9.2% and e4's 13.6%.
What remains may be mostly noise plus a small effect of K (OPEN_QUESTIONS.md).

## 18. E17b: naive inflation grades with the anchor's rank, as the Gaussian limit predicts

**Anchoring round 2 on the second-best feature inflated the naive bootstrap
as much as anchoring on the winner. The third-best gave an intermediate rate,
and from the fifth down the naive test was at or below nominal. Every rank's
rate lay inside its 95% interval around the limit value fixed before
running.** Pre-registered in `prereg/E17b.md` and launched from its commit
(db6b64e, clean; `experiments/e17b_anchor_rank.py`).

- `RankAnchor(k)` fixes round 2's anchor at the k-th best single feature,
  k ∈ {1, 2, 3, 5, 10, 20}, with max_features=2.
- n=1,000 draws paired across ranks (seeds 50000–50999), in E17's
  configuration: K=20, M=50, T=500, ρ=0.3 equicorrelated, s=0, B=1500.
- Naive and recursive nulls on common resampled indices.

| anchor rank | mean κ | limit | naive type-I (95% CI) | KS p | recursive type-I (95% CI) | KS p | naive p ≤ recursive p |
|---|---|---|---|---|---|---|---|
| 1 | 1.000 | 9.1% | 0.095 (0.078–0.115) | <0.001 | 0.048 (0.036–0.063) | 0.326 | 100% |
| 2 | 0.947 | 9.1% | 0.097 (0.080–0.117) | <0.001 | 0.048 (0.036–0.063) | 0.277 | 100% |
| 3 | 0.895 | 6.6% | 0.063 (0.050–0.080) | <0.001 | 0.042 (0.031–0.056) | 0.203 | 99.4% |
| 5 | 0.789 | 4.9% | 0.039 (0.029–0.053) | 0.439 | 0.039 (0.029–0.053) | 0.394 | 32.2% |
| 10 | 0.526 | 4.3% | 0.038 (0.028–0.052) | 0.559 | 0.043 (0.032–0.057) | 0.487 | 5.1% |
| 20 | 0.000 | 4.3% | 0.037 (0.027–0.051) | 0.559 | 0.043 (0.032–0.057) | 0.487 | 5.5% |

**Decision.** U, rank 2 against rank 3: 34–0 (p < 10⁻¹⁰). L, rank 3
against rank 10: 25–0 (p < 10⁻⁷). Both are significant, so the outcome is
**graded**, as predicted. The winner-chasing audit therefore summarizes a
transcript by a graded function of anchor rank, not by a count.

**Secondary readings.**

1. **Rank 1 against rank 2:** 1–3 (p = 0.63). No difference, as the limit
   predicts. The two searches submitted the same value on 93.8% of draws (not
   pre-registered): those where the winner's best partner was the runner-up.
2. **Naive against 5%:** significantly above at ranks 1, 2 and 3 (binomial
   p < 0.001, < 0.001 and 0.038), not at 5, 10 or 20.
3. **Recursive:** not significantly above 5% at any rank. Held.
4. **Monotonicity:** failed narrowly. Rank 2's 97 rejections are two more
   than rank 1's 95; every other step is nonincreasing (rank 5 against 10 is
   1–0, and 10 against 20 is 1–0).
5. **Naive p against recursive p:** naive was at most recursive on every draw
   at ranks 1 and 2, as P4's lemma predicts for both, and on 99.4% at rank 3.
   From rank 5 down the order mostly reversed, the mirror's direction.

**Against the limit (not a registered test).** The limit table was fixed
before running.

- **Every rank:** each observed rate lies inside its Wilson interval, and no
  rank's rate differs from its limit value by a two-sided binomial test
  (p = 0.16–0.75). At the bottom ranks, finite-T rates sit slightly below the
  limit (3.7–3.9% against 4.3–4.9%).
- **Nesting:** rejections were nested across ranks. Apart from 3 draws
  between ranks 1 and 2, every draw that rejected with a lower-ranked anchor
  also rejected with each higher-ranked one.
- **Winner rule:** across four fresh seed blocks (e15, E16, E17, E17b) its
  naive type-I was 41/500, 51/500, 35/500 and 95/1,000. These are homogeneous
  (χ² = 4.02, 3 df, p = 0.26), and pooled they give 8.9% against the limit's
  9.1%.

**What this settles.**

- **The P4 curve.** The lemma's order statistics give the whole curve, not
  only its endpoints (THEORY.md P4). A search anchored on the rank-k feature,
  k ≥ 2, submits max(Z_(1), g(Z_(k), Z_(1))), so ranks 1 and 2 coincide and
  inflation declines from there. E17's exploratory hint of a step near the top
  was the steep part of this curve.
- **The audit.** Mean κ is a poor summary, because the curve is far from
  linear in κ: 9.7% at κ = 0.95, 6.3% at 0.89, 3.9% at 0.79, then flat and
  slightly conservative. The audit should map each anchor's rank to its
  inflation, and the limit curve matched within sampling error here. How
  anchors in different rounds of one search combine is untested
  (OPEN_QUESTIONS.md).
- **Scope.** One configuration: K=20, ρ=0.3, depth 2, exchangeable features.
  E19(c) moves K and ρ for the winner rule. Other ranks under those changes,
  and features that are not exchangeable (E19), are untested.
