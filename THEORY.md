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

## Terminology

This file and SCOPE.md use the repository's vocabulary; the note addressed to
López de Prado & Porcu uses theirs. The mapping, so the two agree:

| here | in the note | source |
|---|---|---|
| evaluated specification, logged column | trial | L&P fn. 1: a trial occurs whenever a Sharpe ratio is computed |
| menu `C(D)` | candidate set `S(D)` | eq. (1), where `S` is written as fixed |
| `sr_sel` | `ŜR_c` | S1 |
| realized-menu null `F_C` | `F_{M_K}` for the observed candidate set | eq. (2) |
| process null `F_P` | `F_{M_K}` under the second reading of Definition 1 | Definition 1; S1 |
| least-favorable null (White) | the boundary `s₁ = … = s_K = 0` of `H₀^FW` | S7.3, eqs. (15)–(16) |
| naive / recursive / full-class bootstrap | three numerical DSR-EO implementations | S8.3–S8.4 |
| anti-conservative | liberal | S7.1 |
| `p = P*(M ≥ sr_sel)` | `p^ex_K = 1 − F_{M_K}(ŜR_c)`, reject when DSR ≥ 1−α | eqs. (13)–(14) |

`K` is always the logged menu size with correlated trials, never an effective
count: see the effective-N result in SCOPE.md §10 for why shrinking `K` for
correlation double-counts it.

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

**The same trade-off, priced on the estimation side.** Efron (2014) draws this
line for standard errors after model selection. Berk et al.'s intervals are
conservative but cover "regardless of the preceding model-selection
procedure", which he notes is the appropriate choice when it is difficult to
say what procedure was used; his own bootstrap-smoothing methods assume the
selection procedure is known and are correspondingly tighter. Those are tiers
two and three of the record hierarchy in another field: procedure unknown, so
take the declared-class bound and pay its conservatism (P3); procedure known
and re-executable, so replay it and pay nothing (P6, and the procedure-level
bootstrap). The analogue is structural rather than an identity — Efron sets
standard errors for an estimate, not a critical value for a search-adjusted
maximum — but it prices the same trade-off, and it was reached independently
there.
Implemented at two tiers. Where the class can be enumerated from base returns,
`estimator/full_class.py` builds it: equal-weight feature subsets of size at
most `d`, 210 columns at K=20, d=2; 1,350 at d=3. Where it cannot — crossover
rules, whose positions are signs of moving-average differences rather than
weight vectors — transcript format v3 takes the class as supplied return
streams (`spec_class="explicit"`), checked by specification id and then column
by column, and the gate runs the Reality Check directly on them (prereg/E20.md).

**Caveat.** Declaring `Θ` after seeing results is itself snooping. For agents,
a tool grammar fixes `Θ` in advance, which is the practical point.

**Evidence.** E17 (SCOPE.md §16), K=20, d=2, eight anchor rules, n=500 each:
full-class type-I 2.0–3.8%, never significantly above 5%. It is conservative
where the search does not chase winners (2.0–2.8% for rules from loser to
τ = 1) and matches the recursive null under winner anchoring.

E20 (SCOPE.md §21) tested the route itself, on a class that cannot be
enumerated from base returns: crossover rules, supplied as return streams.
Comparing the class maximum against the search's own pick on the *same*
nullified surrogates, `sr_sel ≤ max_Θ` held on every one of 4 million shift
comparisons, with no violation beyond 10⁻¹⁰. The resulting test was valid
(type-I 1.9–2.5%) and conservative, its p-value exceeding the re-execution
gold standard's on more than 99% of draws by an average of 0.09 to 0.13.

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
  inequality is strict when the frozen anchor ranks third or lower in the
  replicate, `g` is strictly increasing, and the best pair beats the best
  single. It is not strict merely because the replicate's winner differs from
  `a`: if `a` ranks second, `max_{j≠a} g(z_a, z_j) = g(z_(2), z_(1))`, which
  is the bound.
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
The lemma therefore fixes the sign at ranks 1 and 2 (liberal) and at rank K
(conservative, by the mirror). It says nothing about the interior: those ranks
are decided by whether the rank-k process null stochastically exceeds the
uniform mixture of P4′, which has no closed form and is reported by Monte
Carlo. At K = 20, ω = 0.3 the limit gives 9.1%, 9.1%, 6.6%, 4.9%, 4.3% and
4.3% at ranks 1, 2, 3, 5, 10 and 20, crossing nominal between ranks 3 and 5.

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
grows faster when ω is small. Under exchangeability `F_C` does not depend on
the data, so the realized-menu test's limit type-I at level α has the closed
form

    1 − F_P(F_C⁻¹(1 − α)),

evaluated by Monte Carlo in `experiments/limit_model.py`. Alongside it,
sup|F_P − F_C| is the uniform distortion of the p-value distribution (López de
Prado & Porcu, eq. 12), which the type-I rate at a single α does not capture.

| ω | K | limit type-I | E19(c) measured | sup\|F_P − F_C\| |
|---|---|---|---|---|
| 0 | 10 | 10.0% | 10.0% | 0.142 |
| 0 | 20 | 15.6% | 14.2% | 0.273 |
| 0 | 40 | 24.1% | 22.4% | 0.416 |
| 0 | 80 | 35.9% | 36.2% | 0.548 |
| 0.3 | 10 | 7.3% | 7.0% | 0.048 |
| 0.3 | 20 | 9.2% | 8.4% | 0.086 |
| 0.3 | 40 | 11.3% | 12.0% | 0.129 |
| 0.3 | 80 | 13.7% | 14.0% | 0.169 |

Every measured value lies inside its 95% interval, and the pre-registered
trend test found growth in K at both correlations (p = 0.0001; SCOPE.md §19).

**Outside additive scoring.** The lemma needs a symmetric, nondecreasing pair
statistic, which crossover rules do not provide: a rule's position is the sign
of a difference of moving averages, not a weight vector. E20 (SCOPE.md §21)
predicted the direction anyway, without a guarantee, and found it: paired on
the same draws, winner-anchored search rejected where loser-anchored did not
on 47 draws against 1 (single asset) and 36 against 0 (five-asset panel), both
p < 10⁻⁴, with loser-anchoring conservative in both worlds. The asymmetry
therefore survives where the proof does not. Its size does not: naive type-I
was 5.9% and 5.2% against nominal 5%, about a point, and the two worlds were
not distinguishable from each other (Fisher p = 0.335).

**At depth 3 (E18, SCOPE.md §17).** Winner anchoring inflated naive type-I to
10.4% (n = 1,000), and the naive p-value was at most the recursive one on
every draw. A random round-2 anchor still re-anchors round 3 on the round-2
winner. The pre-registered test found that not detectably inflated (5.3%;
minimum detectable rate about 6.9%). In paired p-values, though, the naive
p-value was at most the recursive one on 99.9% of draws, so the direction
the lemma suggests is present at a size of a point or less.

## P4′. The realized-menu null is a uniform mixture over anchor ranks (new)

**Statement.** Under the exchangeable scoring of P4, freeze the anchor at its
value on the real data. In a replicate its rank is uniform on 1..K and
independent of that replicate's order statistics, so

    F_C = (1/K) Σ_k F_P(k),

where `F_P(k)` is the process null of the search that anchors on the rank-k
feature.

*Proof.* Conditional on the replicate's order statistics, the frozen index is
exchangeable with every other index, so its rank is uniform and independent of
them. The realized-menu maximum is the rank-k process maximum on the event
that the frozen anchor has rank k; average over k. ∎

**Corollary 4.1.** A uniformly random anchor is exactly calibrated under the
realized-menu test: its process null *is* the mixture, so the test has exact
level. Monte Carlo of the limit, with an independently drawn rank per draw:
5.00% ± 0.02 at K=20, ω=0.3 (`experiments/limit_model.py`), and E17 measured
5.0% at τ = 0.

**Corollary 4.2.** Ranks 1 and 2 are liberal and rank K conservative, by P4.
Interior ranks are decided by the mixture criterion and have no closed form.
Limit values at K=20, ω=0.3, against E17b's measurements (SCOPE.md §18):

| anchor rank | 1 | 2 | 3 | 5 | 10 | 20 |
|---|---|---|---|---|---|---|
| limit type-I | 9.1% | 9.1% | 6.6% | 4.9% | 4.3% | 4.3% |
| measured | 9.5% | 9.7% | 6.3% | 3.9% | 3.8% | 3.7% |
| sup·\|F_P − F_C\| | 0.087 | 0.087 | 0.038 | 0.004 | 0.015 | 0.015 |

The Kolmogorov distance is the uniform distortion of the p-value distribution
(López de Prado & Porcu, eq. 12), and it is what vanishes at the calibrated
interior rank rather than the type-I rate alone.

## P5. Greedy search and the lattice optimum (new, corrected)

**Setting.** Scores are exchangeable: a size-`m` subset's limiting statistic is
`(Σ_{k∈S} z_k) / c_m`, where `c_m` depends only on `m`. Under equicorrelation,
`c_m = √(m(1 + (m−1)ω))`. The best size-`m` subset is then the top-`m` set,
with value `r_m = (z_(1) + … + z_(m)) / c_m`.

**Statement.**

1. Greedy forward selection extends the top-`m` set to the top-`(m+1)` set at
   every step. Beam search of any width keeps the top-`m` set *within its
   beam* at every level, since the beam is the best `w` supports of that size
   and the top-`m` set is the best of them. Either way the search visits
   `r_1, r_2, …, r_d`.
2. **Without early stopping,** the selected value `max_{m≤d} r_m` equals the
   maximum over the full lattice of subsets of size at most `d`.
3. **With early stopping** (stop when a step does not improve), the selected
   value is the first local maximum of `r_1, …, r_d`. It is always at most the
   lattice maximum, and equal whenever the first local maximum is global. At
   `d = 2` it is always equal.

**Consequences, in two parts.** *Validity* needs no limit argument and holds
at finite `T`: greedy and beam search only ever evaluate members of `Θ_d`, so
`sr_sel ≤ max_{Θ_d}` exactly, and P3 with P2 gives a valid test. *Coincidence*
is the limit statement: the process null of greedy or beam search equals the
full-class null except on the event where `r_m` is not unimodal. Only the
second needs exchangeability, and only the second is approximate. This explains SCOPE.md §5's
observation that recursive p-values were identical across beam widths: in this
limit every width returns the same value.

**Exploratory size of the gap** (Gaussian limit, K = 20, ω = 0.3, 2×10⁶ draws,
reproduced by `experiments/limit_model.py`):

| d | greedy below lattice maximum | `r_m` not unimodal | 99.9th-percentile shortfall |
|---|---|---|---|
| 2 | 0 | 0 | 0 |
| 3 | 0.19% | 0.57% | 0.043 |
| 4 | 0.28% | 0.80% | 0.066 |

The last column reports a quantile of the shortfall among draws that fall
short. An earlier version printed the sample maximum (0.054 and 0.083); a
maximum over draws is seed-dependent and grows with the draw count, so it
cannot reproduce and should not have been tabulated. That version also carried
a "within the top 5% of lattice maxima" column, dropped here because the
script does not compute it.

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

## P6. When is the recursive bootstrap consistent? (ingredients known, one case sketched, one open)

**Statement.** If the finite-`T` map from the data to the search's selected
value converges to a limit map continuous except on a set of limit-law
probability zero, the recursive bootstrap consistently estimates `F_P`.

**Route, stated properly.** Two ingredients, and the plain continuous mapping
theorem is neither of them.

- The map applied inside a replicate is the **finite-`T`** map — sample means
  over sample standard deviations, and a pair statistic divided by a sample
  covariance — not the limit map `g`. Plain CMT does not cover that. The
  *extended* continuous mapping theorem does (van der Vaart 1998, Thm
  18.11(i); van der Vaart & Wellner 1996, Thm 1.11.1), and it requires the
  finite-`T` maps to converge to `g` uniformly on compacts. That holds here
  because the sample covariance converges, and the maps are deterministic
  given `T`, which is the fixed-map form those theorems assume.
- Bootstrap consistency is needed for the **joint** law of all `K` Sharpe
  ratios, not one at a time. With `K` fixed it follows from the delta method
  applied to the joint mean and covariance limit (Ledoit & Wolf 2008),
  together with stationary-bootstrap consistency (Politis & Romano 1994).

**Covered.** Under the P4 and P5 scoring the selected value is a function of
order statistics of `Z`. Early stopping makes it discontinuous only where
`r_{m+1} = r_m`, which has probability zero under a continuous limit law.

**Sketched: the correlation-anchored rule under equicorrelation.** The
neighbor rule's anchor is not a function of `Z`. Under equicorrelation the
population correlations with the winner tie exactly, so the anchor is an
argmax over a parameter that is tied in the population, and bootstraps are
known to misestimate such argmax laws (Andrews 2000 is the right family). An
earlier version of this section said the correlation noise "lives at a
different scale" from the Sharpe limit. That was wrong: `√T(ρ̂ − ω)` and
`√T·SR` are both `O(1)`. The obstruction is non-regularity, not scale.

The anchor's identity enters the submitted value only through `Z_a`, and two
premises make that harmless in the limit:

1. **Selection is asymptotically independent of `Z`.** `Z` is a mean over a
   standard deviation, so it depends on the sample covariance only at
   `O_p(T^{-1/2})`; asymptotically it is a function of the sample mean vector
   alone. For iid Gaussian data the sample mean and sample covariance are
   exactly independent, and for symmetric innovations asymptotically so, the
   cross-covariance being a third moment. The anchor, a function of the sample
   correlations, is therefore asymptotically independent of `Z` given the
   winner.
2. **Non-winners are exchangeable.** Under equicorrelation, conditional on the
   winner's identity, the remaining coordinates of `Z` are exchangeable, so
   the law of `Z_a` does not depend on which non-winner `a` is.

Together these give the submitted value the same limit law as under a
uniformly random anchor, which is data-oblivious and so covered by P1. The
same two premises hold inside a replicate in the limit, so the bootstrap law
of the value is also the random-anchor law and the recursive test is
consistent. This predicts what e15 measured: the fixed neighbor rule behaved
like a random anchor, mean anchor rank 11.0 of 20 against 10.7 (SCOPE.md §14).

At finite `T` the second premise fails inside a replicate. Resampling draws
from the empirical distribution, whose sample correlations are not
exchangeable, so the replicate's anchor is biased toward the neighbor observed
on the real data — E19(b) measured exactly that, anchor stability 0.088
against the 1/19 ≈ 0.053 a uniform anchor gives (SCOPE.md §20). Because the
value's law does not depend on *which* non-winner is the anchor, that identity
bias does not bias the value's law, and it vanishes as `ρ̂ → ω`. This is a
sketch resting on two named premises, not a proof; formalizing it is the open
task here.

**Open: partial separation.** E19(b)'s heterogeneous correlation is the regime
where both premises fail at once. The loadings differ, so `Z_a`'s law depends
on `a`'s loading and the non-winners are no longer exchangeable; and the
bootstrap is still biased about which `a` it picks (stability 0.192 against
0.088). The recursive bootstrap stayed calibrated there — type-I 4.4% and
5.0% at n = 500 each, coupling unchanged at mean κ 0.480 against 0.483 — but
that is evidence, and no argument is offered for it. The sketch above does not
reach this case.

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
| P3 | ingredients known, tier new | `estimator/full_class.py` and tests; E17 full-class null (SCOPE.md §16); E19(c) up to 3,240 members (SCOPE.md §19); E20 explicit class, exact on 4M shift comparisons (SCOPE.md §21) | E21, E22 |
| P4 | new | e15 (SCOPE.md §14), E16 (SCOPE.md §15); E17 graded across rules (SCOPE.md §16); E17b graded by rank, matching the limit (SCOPE.md §18); E18 at depth 3 (SCOPE.md §17); E19(c) growth in K (SCOPE.md §19); E19 off-exchangeability (SCOPE.md §20); E20 sign result outside additive scoring (SCOPE.md §21) | block correlation, unequal volatilities |
| P5 | new, corrected | exploratory limit check above; E17 at d = 2; E18 at d = 3 and 4 (SCOPE.md §17) | E22 |
| P6 | ingredients known; equicorrelated case sketched, partial separation open | e15 neighbor rule calibrated empirically; E19(b) calibrated as separation rises (SCOPE.md §20) | formalize the sketch's two premises; find an argument for partial separation |

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
- Blum, A. & Hardt, M. (2015). The Ladder: a reliable leaderboard for machine
  learning competitions. *Proceedings of the 32nd International Conference on
  Machine Learning* (PMLR 37), 1006–1014; arXiv:1502.04585. Title, authors and
  arXiv identifier confirmed from the arXiv API; the PMLR volume and pages
  from secondary sources, not the proceedings page.
- Chernozhukov, V., Chetverikov, D. & Kato, K. (2013). Gaussian approximations
  and multiplier bootstrap for maxima of sums of high-dimensional random
  vectors. *Annals of Statistics* 41(6), 2786–2819.
- Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O. & Roth, A.
  (2015). The reusable holdout: preserving validity in adaptive data analysis.
  *Science* 349(6248), 636–638. The companion, Preserving statistical validity
  in adaptive data analysis, is *STOC 2015*, 117–126.
- Efron, B. (2014). Estimation and accuracy after model selection. *Journal of
  the American Statistical Association* 109(507), 991–1007.
- Freedman, D.A. (1983). A note on screening regression equations. *The
  American Statistician* 37(2), 152–155.
- Hansen, P.R. (2005). A test for superior predictive ability. *Journal of
  Business & Economic Statistics* 23(4), 365–380.
- Hardt, M. (2017). Climbing a shaky ladder: better adaptive risk estimation.
  arXiv:1706.02733. Single-authored, confirmed from the arXiv API; the m-class
  bounds sometimes attributed to this paper are Feldman, Frostig & Hardt's.
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
- López de Prado, M. & Fabozzi, F.J. (2026). The false discovery rate in
  finance: identification failure and search-adjusted estimation. SSRN
  6450418, doi:10.2139/ssrn.6450418. Title and authors confirmed via Crossref;
  the paper itself has not been opened from this repository, so cite it only
  for what that metadata supports.
- López de Prado, M., Lipton, A. & Zoonekynd, V. (2026). Sharpe ratio
  inference: a new standard for decision making and reporting. *Journal of
  Portfolio Management* 52(6), 6–50, doi:10.3905/jpm.2026.1.837. The page
  range is the main text's, confirmed via Crossref; the supplement's "50–66"
  refers to something else.
- López de Prado, M. & Porcu, E. (2026). The deflated Sharpe ratio: a unified
  framework for search-adjusted performance inference. SSRN 7198158,
  doi:10.2139/ssrn.7198158. Crossref registers 2026, deposited 30 August 2026,
  consistent with the 24 August 2026 version. The project owner has read the
  main text and supplement in full and confirmed the DSR-L, DSR-LS and DSR-EO
  definitions; SSRN blocks automated access, so they have not been checked
  from this repository.
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
- van der Vaart, A.W. (1998). *Asymptotic Statistics*. Cambridge University
  Press, doi:10.1017/cbo9780511802256. P6 cites the extended continuous
  mapping theorem as Thm 18.11(i). That theorem number was corroborated from
  papers and course notes citing it, not read in the book.
- van der Vaart, A.W. & Wellner, J.A. (1996). *Weak Convergence and Empirical
  Processes*. Springer, doi:10.1007/978-1-4757-2545-2. P6 cites the extended
  continuous mapping theorem as Thm 1.11.1, which is the numbering of this
  1996 edition; a second edition (2023, doi:10.1007/978-3-031-29040-4) may
  renumber it. Corroborated the same way, from secondary sources.
- White, H. (2000). A reality check for data snooping. *Econometrica* 68(5),
  1097–1126.
- Zhang, D. & Wu, W.B. (2017). Gaussian approximation for high dimensional
  time series. *Annals of Statistics* 45(5), 1895–1919.
