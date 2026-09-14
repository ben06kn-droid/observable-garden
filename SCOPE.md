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
data-dependence, a different rule generating it).

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

| variant | dose (mean divergence) | naive type-I (95% CI) | recursive type-I (95% CI) |
|---|---|---|---|
| LatticeAdaptive | 0.000 | 0.060 (0.032–0.110) | 0.060 (0.032–0.110) |
| BeamAdaptive(16) | 0.331 | 0.067 (0.037–0.118) | 0.060 (0.032–0.110) |
| BeamAdaptive(4) | 0.876 | 0.093 (0.056–0.151) | 0.060 (0.032–0.110) |
| BeamAdaptive(2) | 0.932 | 0.107 (0.067–0.166) | 0.060 (0.032–0.110) |
| Adaptive (k=1) | 0.950 | 0.127 (0.083–0.189) | 0.060 (0.032–0.110) |
| DepthAdaptive | 0.950 | 0.133 (0.088–0.197) | 0.060 (0.032–0.110) |
| NeighborAdaptive | 0.950 | 0.127 (0.083–0.189) | 0.060 (0.032–0.110) |

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
  BeamAdaptive(16/4/2), Adaptive, and NeighborAdaptive (DepthAdaptive
  differs, correlation 1.000, because its extra round changes the
  achievable support size). Traced to the source: `M_b` itself is
  identical to floating-point precision across all four searchers on
  every one of 300 tested bootstrap replicates (max abs diff = 0.0).
- *Why, mechanically, if beam_width is respected?* Greedy forward selection
  (any beam width 1–K, or NeighborAdaptive's correlation-based rule)
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

**Structural axis confirms it's data-dependence, not the specific rule.**
DepthAdaptive (0.133) runs slightly hotter than Adaptive (0.127) — selection
compounding over an extra round, in the predicted direction, though the
CIs overlap too much to call this decisive on its own. NeighborAdaptive
(0.127) lands exactly on Adaptive's rate despite anchoring round 2 on
feature *correlation* rather than Sharpe-argmax: a completely different
selection rule produces the same inflation, because it has the same
*amount* of realized-data-dependence. That's the direct answer to "is it
Sharpe-argmax specifically, or any data-dependent rule" — it's the latter.

**Two diagnostics, compared honestly — the predicted winner didn't win.**
`estimator/divergence.py`'s Jaccard divergence rate (what fraction of the
real transcript's round-1 beam a bootstrap replicate's own beam fails to
reproduce) is a *rate*, bounded at 1, and it saturates: 0.000 → 0.331 →
0.876 → 0.932 → 0.950 across the dose axis, compressing BeamAdaptive(2)
through NeighborAdaptive into a narrow band while their type-I rates keep
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

## 6. This is a known phenomenon, not a novel one

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
  is the analytic alternative to re-simulation (§6, route 2).
- **Benjamini & Yekutieli (2005)**, *False Discovery Rate–Adjusted Multiple
  Confidence Intervals for Selected Parameters* — the same principle inside
  the multiple-comparisons framing this project otherwise sits in.

## 7. What's validated, what's fixed, and what's still open

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
