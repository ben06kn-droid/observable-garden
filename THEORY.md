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

Outside exchangeability (heterogeneous volatilities, block correlation) the
lemma's hypothesis fails; E19 probes how far the conclusion survives.

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

## Evidence map

| Result | Status | Evidence so far | Planned |
|---|---|---|---|
| P1 | known | SCOPE.md §1 (null calibration of oblivious searchers) | E21 |
| P2 | known | none needed | none |
| P3 | ingredients known, tier new | `estimator/full_class.py` and tests | E17 (full-class null), E21, E22 |
| P4 | new | e15 (SCOPE.md §14), E16 (SCOPE.md §15) | E17, E19 |
| P5 | new, corrected | SCOPE.md §5 identical recursive rates; exploratory limit check above | E18, E22 |
| P6 | ingredients known, one case open | e15 neighbor rule calibrated empirically | E19(b) |

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
