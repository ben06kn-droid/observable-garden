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

## 8. Experiment 2: predictive power under the alternative — a complicated result

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
still has (§7: a rigorous negative result, a fix, a boundary, a
dose-response — no single number yet showing the method beats what it's
meant to replace). It's a real, mixed result: deflation beats naive
prediction; bootstrap tracks average decay better than closed-form;
closed-form has lower per-draw variance and wins on RMSE anyway; the
ρ=0 baseline check surfaced a genuine, partially-explained anomaly rather
than a clean pass. Reported in full rather than led with the more flattering
half of it.

## 9. Experiment 2 rerun with both DGP fixes: bias is the metric that actually distinguishes the three corrections

*Figures: `figures/e9_decay_vs_N.png` (spec §4.3's decay-vs-trial-budget
figure, one panel per ρ) and `figures/e9_bias_vs_rho.png` (spec §4.4's
correlation-sensitivity figure, all three methods at N=1000). Both are
built directly from the results table below — `experiments/
plot_predictive_power.py`, no new experiment runs.*

Two changes, made in a specific order because the order is what makes them
defensible. First, a criterion was written down and checked *before*
touching the DGP or looking at any RMSE (§8's own instinct, made explicit):
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
+0.117, +0.237 (§8's explanation: `heterogeneous_correlation` returns the
identity at ρ≤0, same as equicorrelation there, so nothing about this
specific comparison should have changed, and it didn't). The still-open
question from §8 — why the gap *grows* with `N` — remains open here too.

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
with `N` (§8), and whether effective-N's non-monotone-in-ρ anti-
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

*[PENDING_E10_RESULTS]*

The ρ axis stays exactly where §9's main table already puts it to best
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
