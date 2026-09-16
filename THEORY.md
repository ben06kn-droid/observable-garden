# When a logged search transcript licenses a search-adjusted Sharpe test

Draft theory for the note on fixed versus adaptive candidate generation. Each
result is marked:

- **known:** an existing result, credited;
- **new:** this project's contribution, which needs a statistician's reading
  before it is claimed;
- **open:** stated but not established.

P4–P6 are the parts to have reviewed.

## Setup

- Base return columns `b_1, …, b_K` over `T` periods; single-feature Sharpe
  ratios `SR_1, …, SR_K`. Under the null that no feature carries an edge, and
  standard mixing conditions, `√T · (SR_1, …, SR_K) → Z ~ N(0, Ω)` (the delta
  method for studentized Sharpe ratios; Ledoit & Wolf 2008).
- A **search** is a map from data `D` to a menu `C(D)`, the set of evaluated
  specifications, plus a selection rule returning the reported Sharpe `sr_sel`.
- **Process null `F_P`:** the law of the selected Sharpe when the whole search,
  menu construction included, runs on null data.
- **Realized-menu null `F_C`:** the law of the maximum over the *observed* menu
  `C(D_obs)`, evaluated on null data.
- The **naive** (realized-menu) bootstrap demeans every logged column, which
  imposes the least-favorable null (White 2000), resamples time jointly, and
  estimates `F_C`. The **recursive** bootstrap replays the search's own
  decisions on each resample and estimates `F_P`. The **full-class** bootstrap
  estimates the law of the maximum over a declared class `Θ`.
- The test reports `p = P*(M ≥ sr_sel)` under whichever null is used.

## P1. Fixed menus are valid (known)

**Statement.** If `C = c(X, U)`, where `U` is randomness independent of the
returns and `X` is information independent of the return noise (in markets:
fixed before the evaluation sample is seen), then the realized-menu bootstrap
p-value satisfies `P(p ≤ α) ≤ α + o(1)` under the least-favorable null.

**Route.** Condition on `C`. The menu is then a fixed finite set of
specifications, and the Reality Check (White 2000) and its studentized
successor (Hansen 2005) apply. The Sharpe ratio is a smooth function of means,
which adds the delta-method step (Ledoit & Wolf 2008).

**Gap.** White's asymptotics hold the number of candidates fixed. GridSearch's
menus are comparable in size to `T`. Maximum-type bootstrap results in high
dimensions (Chernozhukov, Chetverikov & Kato 2013 for independent data; Zhang &
Wu 2017 for time series) are the theoretical cover. They concern maxima of
sums, so applying them to studentized Sharpe maxima needs its own argument.
Until that exists, the large-menu case is supported by simulation: SCOPE.md §1,
where menus of thousands of correlated candidates were calibrated.

## P2. Sub-maximal selection is conservative (known)

**Statement.** If `sr_sel ≤ max_{c ∈ C} SR_c` for a menu `C` whose maximum
null is valid, the test that compares `sr_sel` with that null is valid and
conservative.

**Route.** `p(s) = P*(M ≥ s)` is nonincreasing in `s`, so
`p(sr_sel) ≥ p(max_C SR_c)`. This covers greedy selection over a fixed lattice
and the gate's non-maximal submissions.

## P3. The full-class bound (known ingredients, new as a transcript-sufficiency tier)

**Statement.** If every specification the search *could* have produced lies in
a class `Θ` declared before the search, the realized-menu bootstrap over all of
`Θ` gives a valid test, however adaptive the search was.

**Route.** `sr_sel ≤ max_Θ SR_θ`. `Θ` is fixed independently of the data, so P1
applies to `max_Θ`, and P2 gives validity.

**Why it matters.** It is the tier between "returns only" and "re-executable":
a transcript plus a class declaration suffices, with no replay. It is the
Sullivan–Timmermann–White (1999) move, testing the whole rule universe, and the
analogue of simultaneous post-selection inference (Berk et al. 2013).
Implemented for equal-weight feature subsets of size at most `d` in
`estimator/full_class.py`: 210 columns at K=20, d=2; 1,350 at d=3.

**Caveat.** Declaring `Θ` after seeing results is itself snooping. For agents,
a tool grammar fixes `Θ` in advance, which is the practical point.

**Evidence.** E17 (SCOPE.md §16), K=20, d=2, eight anchor rules, n=500 each:
full-class type-I 2.0–3.8%, never significantly above 5%. It is conservative
where the search does not chase winners (2.0–2.8% for rules from loser to
τ = 1) and matches the recursive null under winner anchoring.

## P4. Winner anchoring is anti-conservative; loser anchoring is conservative (new)

**Lemma.** Let `g` be symmetric and nondecreasing in each argument, and let
`z ∈ R^K` with order statistics `z_(1) ≥ z_(2) ≥ … ≥ z_(K)`. For any fixed
index `a`:

    max_{j≠a} g(z_a, z_j)  ≤  g(z_(1), z_(2))

*Proof.* If `a` is the top index, `max_{j≠a} z_j = z_(2)`, so equality holds.
Otherwise `z_a ≤ z_(2)` and every `z_j ≤ z_(1)`, so
`g(z_a, z_j) ≤ g(z_(2), z_(1)) = g(z_(1), z_(2))`. ∎

**Mirror.** For any fixed index `a` (K ≥ 2):

    max_{j≠a} g(z_a, z_j)  ≥  g(z_(K), z_(1))

*Proof.* If `a` is not the top index, take `j` = the top index:
`g(z_a, z_(1)) ≥ g(z_(K), z_(1))` because `z_a ≥ z_(K)`. If `a` is the top
index, take `j` = the bottom index: `g(z_(1), z_(K)) = g(z_(K), z_(1))`. ∎

**Application.** Take equal-variance, equicorrelated base columns with
correlation `ω`. The limiting Sharpe statistic of an equal-weight pair is
`g(x, y) = (x + y) / √(2 + 2ω)`, which satisfies the lemma. Consider the
two-step search that evaluates all singles, anchors on one feature, and
evaluates every pair containing the anchor.

- **Winner anchor.** The process null maximum is `M_P = max(Z_(1), g(Z_(1), Z_(2)))`,
  because each replicate anchors on its own winner. The realized-menu maximum
  is `M_C = max(Z_(1), max_{j≠a} g(Z_a, Z_j))` with `a` frozen at the observed
  winner. By the lemma, `M_P ≥ M_C` on every draw. So `F_P` stochastically
  dominates `F_C`, and the naive p-value is at most the process p-value. The
  inequality is strict whenever the replicate's winner differs from `a` and the
  best pair beats the best single.
- **Loser anchor.** Here `M_P = max(Z_(1), g(Z_(K), Z_(1)))`. By the mirror,
  `M_C ≥ M_P` on every draw, so the naive test is conservative. The effect is
  small because `Z_(1)` usually dominates both.

**Status and evidence.** Exact in the Gaussian limit under exchangeability,
which is e15's design. At finite `T` the pair's Sharpe also depends on the
realized correlation of the two columns, so the reduction to `g(z_a, z_j)` is
an approximation. E16 measured it with both nulls on common resampled indices,
n = 500 draws (SCOPE.md §15):

| anchor | draws in the predicted direction | replicates violating the inequality |
|---|---|---|
| winner | 500/500 | 0.1% |
| loser | 500/500 | 0.0% |

Outside exchangeability the lemma's hypothesis fails: with unequal
correlations the pair statistic's denominator depends on which pair is
formed, so the search can prefer a weaker but less correlated partner. E19
(SCOPE.md §20) measured how far the conclusion survives that, under a
single-factor correlation with loadings on √ρ ± 0.15, n = 500 per cell:

| structure | K | replicates with M_P ≥ M_C | naive type-I | recursive | full-class |
|---|---|---|---|---|---|
| heterogeneous correlation | 20 | 99.894% | 0.088 | 0.048 | 0.048 |
| heterogeneous correlation | 80 | 99.908% | 0.142 | 0.050 | 0.050 |

Violations are real but rare and small (at most 8 replicates of 1,500 in a
draw, worst gap −0.195), and none reversed an ordering: the naive p-value was
at most the recursive one on every draw. So the conclusion holds where the
proof does not. Block correlation and unequal volatilities remain untested;
in the limit, volatility spread moves naive type-I by under a point.

**Between the endpoints.** The lemma's order statistics also cover
fixed-rank anchors. In the application's setting, the search anchored on the
rank-k feature submits

    max(Z_(1), g(Z_(1), Z_(2)))   for k = 1
    max(Z_(1), g(Z_(k), Z_(1)))   for k ≥ 2

because the winner's best partner is the runner-up, and every other feature's
best partner is the winner. Ranks 1 and 2 submit the same value. Rank 2's
process maximum therefore equals the winner's, and the lemma makes its naive
test anti-conservative too. After rank 2 the submitted value falls with k.
The naive rate has no closed form here; a Monte Carlo of the limit (K = 20,
ω = 0.3) gives 9.1%, 9.1%, 6.6%, 4.9%, 4.3% and 4.3% at ranks 1, 2, 3, 5,
10 and 20.

Evidence (SCOPE.md §16, §18):

- **E17** drew the anchor with probability proportional to exp(τ z_k). Naive
  type-I rose from 3.6% (loser) through 5.0% (random) to 7.0% (winner), and
  its pre-registered trend test decided for graded coupling across rules
  (p = 0.0001).
- **E17b** fixed the anchor's rank, with the limit values above registered in
  advance. It measured 9.5%, 9.7%, 6.3%, 3.9%, 3.8% and 3.7%, each inside its
  95% interval around the limit value. The pre-registered outcome was graded:
  rank 3 fell below rank 2 (34–0) and stayed above rank 10 (25–0).

**Breadth.** In the same limit, the gap between the search's value, set by
the top two order statistics, and the frozen menu's maximum grows with K, and
grows faster when ω is small. The limit predicted naive type-I of 10.1%,
15.5%, 24.2% and 35.7% at K = 10, 20, 40 and 80 with ω = 0, and 7.3%, 9.1%,
11.3% and 13.7% at ω = 0.3. E19(c) (SCOPE.md §19) measured 10.0%, 14.2%,
22.4% and 36.2%, and 7.0%, 8.4%, 12.0% and 14.0%, on draws nested across K.
Every value lies inside its 95% interval, and the pre-registered trend test
found growth in K at both correlations (p = 0.0001).

**At depth 3 (E18, SCOPE.md §17).** Winner anchoring inflated naive type-I to
10.4% (n = 1,000), and the naive p-value was at most the recursive one on
every draw. A random round-2 anchor still re-anchors round 3 on the round-2
winner. The pre-registered test found that not detectably inflated (5.3%;
minimum detectable rate about 6.9%). In paired p-values, though, the naive
p-value was at most the recursive one on 99.9% of draws, so the direction
the lemma suggests is present at a size of a point or less.

## P5. Greedy search and the lattice optimum (new, corrected)

**Setting.** Scores are exchangeable: a size-`m` subset's limiting statistic is
`(Σ_{k∈S} z_k) / c_m`, where `c_m` depends only on `m`. Under equicorrelation,
`c_m = √(m(1 + (m−1)ω))`. The best size-`m` subset is then the top-`m` set,
with value `r_m = (z_(1) + … + z_(m)) / c_m`.

**Statement.**

1. Greedy forward selection, and beam search of any width, extends the top-`m`
   set to the top-`(m+1)` set at every step, so it visits `r_1, r_2, …, r_d`.
2. **Without early stopping,** the selected value `max_{m≤d} r_m` equals the
   maximum over the full lattice of subsets of size at most `d`.
3. **With early stopping** (stop when a step does not improve), the selected
   value is the first local maximum of `r_1, …, r_d`. It is always at most the
   lattice maximum, and equal whenever the first local maximum is global. At
   `d = 2` it is always equal.

**Consequences.** The process null of greedy or beam search is at most the
full-class null, so by P2 the full-class test stays valid. The two coincide
except on the event where `r_m` is not unimodal. This explains SCOPE.md §5's
observation that recursive p-values were identical across beam widths: in this
limit every width returns the same value.

**Exploratory size of the gap** (Gaussian limit, K = 20, ω = 0.3, 10⁶ draws):

| d | greedy below lattice maximum | within the top 5% of lattice maxima | `r_m` not unimodal | largest shortfall |
|---|---|---|---|---|
| 2 | 0 | 0 | 0 | none |
| 3 | 0.19% | 0.19% | 0.57% | 0.054 |
| 4 | 0.28% | 0.32% | 0.79% | 0.083 |

So "the full-class null costs greedy search no power" holds exactly at `d = 2`
or without early stopping, and approximately at larger `d`. E18 checks how
closely recursive rates coincide across beam widths at `d = 3`.

At finite `T`, even `d = 2` is not exact. In E17 (SCOPE.md §16) the
winner-anchored search's recursive and full-class p-values differed on 36 of
500 draws, each time by one replicate in 1,501 and always with the
full-class null larger; no rejection decision differed.

**Measured at d = 3 and 4 (E18, SCOPE.md §17), n = 500.** The replayed value
fell below the full-class maximum on 0.87% of replicates for greedy search
and on 0.30–0.33% for beams of width 2 to 16, and at d = 4 on 0.95%. It was
never above. The limit predicts 0.19% and 0.28%, with no difference between
widths, so finite-T departures are larger than the early-stopping effect the
table isolates. Recursive rejection decisions agreed across every beam width
and with the full-class null on all 500 draws. The consequence holds for
verdicts; for the size of the mismatch, quote the measured values, not the
limit.

## P6. When is the recursive bootstrap consistent? (known ingredients, one open case)

**Statement.** If the map from `Z` to the search's selected value is continuous
except on a set of limit-law probability zero, the recursive bootstrap
consistently estimates `F_P`. The route is stationary-bootstrap consistency
(Politis & Romano 1994) plus the continuous mapping theorem.

**Covered.** Under the P4 and P5 scoring, the selected value is a function of
order statistics. Early stopping makes it discontinuous only where `r_{m+1} = r_m`
ties, which have probability zero under a continuous limit law.

**Open.** Anchor rules based on other statistics, such as the most-correlated
neighbor, are not functions of `Z` alone. Under equicorrelation, the population
correlations with the winner tie exactly, so the anchor is chosen by
estimation noise in the sample correlations. That noise lives at a different
scale from the Sharpe limit, and neither the continuous mapping argument nor
standard bootstrap results cover it (compare Andrews 2000 on bootstrap failure
at irregular points). e15's measured coupling agrees: the fixed neighbor
rule's anchor had mean Sharpe rank 11.0 of 20, against 10.7 for a random
anchor (SCOPE.md §14). e15 found no calibration problem for this rule; that is
evidence, not a proof.

E19(b) (SCOPE.md §20) moved the rule toward the regular case by separating
the population correlations, and only partly succeeded: the anchor is the
highest-loading feature on 27.6% of draws against 6.8% under equicorrelation,
and replicate anchor stability rises to 0.192 from 0.088, so most replicates
still choose the anchor by estimation noise. Across that increase in
separation the recursive bootstrap stayed calibrated (type-I 4.4% and 5.0%,
n = 500 each) and coupling was unchanged (mean κ 0.480 against 0.483). More
evidence, still not a proof, and the exact-tie case remains open: a design
that separates the correlations fully would be needed to test the regular
case.

## Prior work checked for P4, P5 and the coupling κ

Read from full text, not summaries:

- **Nikolopoulos (2026)** scales the expected maximum over correlated
  candidates by an effective multiplicity, and treats the Reality Check and SPA
  as the right layer for a search-adjusted p-value. It does not analyze
  searches that build on their own best results, and it has no measure based
  on the order of evaluations.
- **Miao, Pritchard & Zou (2026)** log AI agents' analysis paths and build a
  reference distribution, the m-value, from them. They run no data-snooping
  test and do not analyze the order in which agents try specifications.
- **Liu, Qu, Gaboardi, Garg & Ullman (2024)** define the adaptivity of a data
  analysis as its rounds of query dependence, bounded by static analysis of
  program code. That is a measure of depth, not of how strongly the next query
  depends on the performance of earlier ones. The text contains nothing on
  argmax selection, specification search or multiple testing.

None of the three states the winner-anchoring direction (P4) or the greedy and
lattice identity (P5) for data-snooping tests, or measures coupling from
evaluation order. The note plan's literature check (§3.1) is broader than
these papers and is not finished, so the note should not yet claim that
nothing anticipates P4.

## Evidence map

| Result | Status | Evidence so far | Planned |
|---|---|---|---|
| P1 | known | SCOPE.md §1 (null calibration of oblivious searchers) | E21 |
| P2 | known | none needed | none |
| P3 | ingredients known, tier new | `estimator/full_class.py` and tests; E17 full-class null (SCOPE.md §16); E19(c) up to 3,240 members (SCOPE.md §19) | E21, E22 |
| P4 | new | e15 (SCOPE.md §14), E16 (SCOPE.md §15); E17 graded across rules (SCOPE.md §16); E17b graded by rank, matching the limit (SCOPE.md §18); E18 at depth 3 (SCOPE.md §17); E19(c) growth in K (SCOPE.md §19); E19 off-exchangeability (SCOPE.md §20) | block correlation, unequal volatilities |
| P5 | new, corrected | exploratory limit check above; E17 at d = 2; E18 at d = 3 and 4 (SCOPE.md §17) | E22 |
| P6 | ingredients known, one case open | e15 neighbor rule calibrated empirically; E19(b) calibrated as separation rises (SCOPE.md §20) | a design that separates the correlations fully |

## References

Checked against publisher metadata (Crossref, or the publisher's own page
tags) except where an entry says otherwise:

- Andrews, D.W.K. (2000). Inconsistency of the bootstrap when a parameter is on
  the boundary of the parameter space. *Econometrica* 68(2), 399–405.
- Bailey, D.H. & López de Prado, M. (2014). The deflated Sharpe ratio:
  correcting for selection bias, backtest overfitting, and non-normality.
  *Journal of Portfolio Management* 40(5), 94–107.
- Bailey, D.H., Borwein, J., López de Prado, M. & Zhu, Q.J. The probability
  of backtest overfitting. *Journal of Computational Finance*, published online
  19 September 2016, doi:10.21314/JCF.2016.322. Volume, issue and pages not
  yet confirmed from publisher metadata.
- Berk, R., Brown, L., Buja, A., Zhang, K. & Zhao, L. (2013). Valid
  post-selection inference. *Annals of Statistics* 41(2), 802–837.
- Chernozhukov, V., Chetverikov, D. & Kato, K. (2013). Gaussian approximations
  and multiplier bootstrap for maxima of sums of high-dimensional random
  vectors. *Annals of Statistics* 41(6), 2786–2819.
- Efron, B. (2014). Estimation and accuracy after model selection. *Journal of
  the American Statistical Association* 109(507), 991–1007.
- Hansen, P.R. (2005). A test for superior predictive ability. *Journal of
  Business & Economic Statistics* 23(4), 365–380.
- Hsu, P.-H., Hsu, Y.-C. & Kuan, C.-M. (2010). Testing the predictive ability
  of technical analysis using a new stepwise test without data snooping bias.
  *Journal of Empirical Finance* 17(3), 471–484.
- Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the
  Sharpe ratio. *Journal of Empirical Finance* 15(5), 850–859.
- Leeb, H. & Pötscher, B.M. (2005). Model selection and inference: facts and
  fiction. *Econometric Theory* 21(1), 21–59.
- Liu, J., Qu, W., Gaboardi, M., Garg, D. & Ullman, J. (2024). Program
  analysis for adaptive data analysis. *Proceedings of the ACM on Programming
  Languages* 8(PLDI), 914–938.
- López de Prado, M. & Porcu, E. The deflated Sharpe ratio: a unified
  framework for search-adjusted performance inference. SSRN 7198158,
  doi:10.2139/ssrn.7198158. Title, authors and DOI confirmed; the SSRN listing
  is reported as dated September 2025 while Crossref registers 2026. SSRN
  blocks automated access, so the paper's definitions of DSR-L, DSR-LS and
  DSR-EO have not been read directly: confirm them against the paper.
- Miao, J., Pritchard, J.K. & Zou, J. (2026). The agentic garden of forking
  paths. arXiv:2607.01507.
- Nikolopoulos, S.D. (2026). Spurious predictability in financial machine
  learning. arXiv:2604.15531.
- Politis, D.N. & Romano, J.P. (1994). The stationary bootstrap. *Journal of
  the American Statistical Association* 89(428), 1303–1313.
- Romano, J.P. & Wolf, M. (2005). Stepwise multiple testing as formalized data
  snooping. *Econometrica* 73(4), 1237–1282.
- Sullivan, R., Timmermann, A. & White, H. (1999). Data-snooping, technical
  trading rule performance, and the bootstrap. *Journal of Finance* 54(5),
  1647–1691.
- Tibshirani, R.J., Taylor, J., Lockhart, R. & Tibshirani, R. (2016). Exact
  post-selection inference for sequential regression procedures. *Journal of
  the American Statistical Association* 111(514), 600–620.
- White, H. (2000). A reality check for data snooping. *Econometrica* 68(5),
  1097–1126.
- Zhang, D. & Wu, W.B. (2017). Gaussian approximation for high dimensional
  time series. *Annals of Statistics* 45(5), 1895–1919.
