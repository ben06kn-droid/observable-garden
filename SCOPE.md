# Scope of the validated claim, and why Adaptive fails

Experiment 1 (spec §4.1) is designed as a pass/fail gate: under a pure null,
every searcher's p-value should be Uniform(0,1). Honest, Greedy, and
GridSearch pass. Adaptive — the searcher spec §3.1 calls "the one that
matters most" because it reproduces a real agent's sequential structure —
does not (README, "Days 7-9"). This document states precisely what is and
isn't proven by the searchers that pass, and gives a mechanistic,
literature-grounded account of why Adaptive fails, verified directly against
this codebase rather than asserted by analogy.

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
any realized Sharpe) are all calibrated — KS p = 0.167, 0.992, 0.966 over 100
null draws — despite spanning three orders of magnitude in `N` and a wide
range of trial correlation. Independence was never the load-bearing
assumption; obliviousness of the menu is, and it's strictly weaker.

## 2. Why Adaptive violates it, and the exact mechanism

Adaptive's round-`(r+1)` menu is `{support_r(ω) ∪ {j} : j ∈ remaining}`, where
`support_r(ω)` is the argmax of round `r`'s *realized* Sharpes. This is
manifestly not oblivious: which candidates even get tried in round 2 is a
discontinuous function of the very null noise under test.

**The specific mechanism, not just an appeal to the general principle.**
`Specification` is linear, and every specification in a draw shares the same
noise realization, so a pair's return series is *exactly*
`single(a) + single(b)`, elementwise — confirmed to floating-point precision
(`max abs diff = 2.2e-16`) — and demeaning distributes over the sum, so this
survives null-imposition too. That makes the failure mode exact and
checkable: `estimator/bootstrap.py`'s `null_max_bootstrap`, as specified,
resamples the *observed* transcript's fixed weight vectors. In every
replicate, round 2's candidates stay "feature `W_orig` + feature `j`" for
the *specific* `W_orig` that won round 1 on the real, unresampled data. But
on fresh null data — a real second run, or a faithful bootstrap replicate of
one — a *different* feature would generically win round 1. Freezing the
anchor denies every replicate's round 2 the thing the real search actually
had: the freedom to build on top of whichever feature *that draw's own
noise* favored. The naive bootstrap explores a strictly narrower space than
the procedure it's supposed to be nulling, so it **underestimates** the true
null max — which biases p-values downward (anti-conservative), exactly the
observed direction (excess mass of `p<0.05`: e.g. 0.163–0.175 across two
independent 80-draw checks against a nominal 0.05).

**Direct empirical confirmation** (`experiments/verify_selective_inference_theory.py`).
Because of the additive-linearity property above, the fix is directly
testable: build an "oracle" bootstrap that re-derives each round's winner
from every replicate's *own* resampled singles — reconstructing any
hypothetical pair by summing the appropriate bootstrapped single columns,
without touching raw asset-level data — instead of reusing the observed
`W_orig`.

- Single draw: `mean_null_max` = 0.0609 (naive) vs **0.0695 (oracle)** — larger,
  exactly as the mechanism predicts.
- Calibration, 80 pure-null draws, `K=30`: naive KS p = **0.0010** (fails);
  oracle KS p = **0.5575** (passes); `frac(p<0.05)` drops from 0.163 to 0.075,
  near the nominal 0.05.

Re-deriving the selection inside the bootstrap, instead of freezing it at its
observed value, is sufficient to restore calibration. This isn't circumstantial
correlational evidence for the mechanism — it's a controlled intervention on
the specific quantity (which round's winner is held fixed vs re-derived) that
the mechanism says is the cause, with the predicted effect on both magnitude
and direction.

## 3. This is a known phenomenon, not a novel one

- **Leeb & Pötscher (2005)**, *Model Selection and Inference: Facts and
  Fiction*, Econometric Theory — proves the sampling distribution of a
  post-model-selection estimator cannot in general be consistently estimated
  by any procedure that treats the selected model as fixed, because the map
  from data to "which model was selected" is discontinuous in the data. This
  is the formal version of what §2 shows constructively for this case.
- **Efron (2014)**, *Estimation and Accuracy after Model Selection*, JASA —
  the prescription: the bootstrap must re-run the *selection step* inside
  every replicate, not just resample data underlying an already-fixed
  selected model. That is exactly what the oracle bootstrap does, and exactly
  why it works.
- **Berk, Brown, Buja, Zhang & Zhao (2013)**, *Valid Post-Selection
  Inference* (PoSI), and **Lee, Sun, Sun & Taylor (2016)**, *Exact
  Post-Selection Inference, with Application to the Lasso* — the selective-
  inference program: conditioning on a data-dependent selection event
  changes the correct reference null distribution, and substituting the
  marginal/unconditional null is systematically anti-conservative.
- **Benjamini & Yekutieli (2005)**, *False Discovery Rate–Adjusted Multiple
  Confidence Intervals for Selected Parameters* — the same principle inside
  the multiple-comparisons framing this project otherwise sits in.

## 4. What is and isn't validated

**Validated, cleanly, by experiment 1:** the bootstrap null-maximum estimator
is correctly calibrated for any search whose candidate menu is data-oblivious
— fixed given the search's own configuration, independent of realized
outcomes — for any trial count from 1 to several thousand and any degree of
correlation among candidates, including exact duplicates (§6 test 4) and
heavily overlapping subsets (GridSearch). This is a strictly more general
claim than "works when trials are independent," which is what the spec's own
framing under-sells, and it is the operative case for Greedy- or
GridSearch-shaped agent behavior: an agent that decides its *menu* up front
(even a huge, correlated one) and then reports the best result is correctly
handled.

**Not currently validated:** search where later trials are chosen
conditional on earlier trials' *realized outcomes* within the same run —
Adaptive, and by extension the sequential tool-calling loop of a real LLM
agent (spec §3.3), where each `evaluate()` call is informed by the results of
previous ones. This is precisely the structure spec §3.1 identifies as load-
bearing for the eventual agent experiments, not a corner case being set aside.

This isn't a reason to abandon the approach — it's the exact boundary the
project's own Hypothesis section anticipates probing ("whether adaptive data
analysis repairs it... whether a Thresholdout-style query budget restores
calibration"). §2's oracle-bootstrap result is a first positive existence
proof that a bootstrap-based fix is possible for sequential search using only
the transcript already being logged — no raw asset-level data, no change to
what gets recorded — provided the round's continuation can be reconstructed
from earlier columns.

## 5. What's still open

The oracle bootstrap solves a narrow case: additive, linear specifications
where round `r+1`'s candidates are exact sums of already-logged round-0
columns, so any hypothetical continuation is reconstructable without
re-running the sandbox. A real agent's search need not have this property —
a later specification is not guaranteed to be a fixed linear function of
earlier evaluated ones. Generalizing the fix means either:

(a) a general recursive bootstrap that re-executes the searcher's *decision
rule* on resampled underlying (asset-level) data each replicate — well-
defined for a scripted searcher (the rule is known code), structurally
harder to define for an LLM agent (the "rule" is the model's own weights and
context); or
(b) an explicit selective-inference correction (Lee et al. 2016-style)
tailored to the specific sequential structure, conditioning on the realized
selection event rather than re-simulating it.
