# A learned pipeline certified as one declared strategy, 2026-10-07 (America/Chicago). EXPLORATORY DESIGN NOTE

**Exploratory, not a registration.** Nothing here is live, and nothing in it has been run
on the project's data. It records the design before any code is built in the
repository. Tests, thresholds and seeds are registered later, after the pilot.

## Where the design came from

The design came from a **stress test run outside the repository, on a synthetic stand-in
panel**. That panel has the planted panel's dimensions (3,019 days, 40 assets, 40
features in 14 families), but its features and returns are invented. The script is kept
at **`scratch/ml_stress_test.py`**, which is non-evidence material.
- **It is not project evidence and is never cited as such.** Its numbers are not
  recorded in `EXPERIMENTS.md`.
- **The pilot on the pinned planted panel decides** whether the design goes forward.
- The script is the reference implementation of the pipeline below.

## a. Certification: one declared strategy through the existing class bootstrap

A walk-forward pipeline forms each day's positions from earlier data only. Its net
return stream is therefore the stream of **one strategy fixed in advance**, and it is
priced as a class with one member: the stationary bootstrap of the demeaned stream, the
class tier's own null. A menu of several declared pipelines is priced jointly, with the
maximum taken over their streams.
- **Validity:** fixed menus are valid (P1).
- **No placebo twins.**
- **Outputs:** the verdict, confidence `C0`, the lower bounds `L_g` and the confidence
  curve, as for any class (`quixote/confidence.py`).
- **The only new risk is leakage** of later data into a position. The leak test (d)
  targets it.

**Prior art, checked against Crossref on 2026-10-07** (DOI, title, authors, journal,
volume, issue, pages and year match):
- White, H. (2000), "A Reality Check for Data Snooping", *Econometrica* 68(5), 1097–1126,
  DOI 10.1111/1468-0262.00152. It covers the bootstrap of out-of-sample performance
  streams and of their maximum over a menu.
- Giacomini, R. & White, H. (2006), "Tests of Conditional Predictive Ability",
  *Econometrica* 74(6), 1545–1578, DOI 10.1111/j.1468-0262.2006.00718.x. It covers
  testing a forecasting method with its estimation procedure included.

Only the metadata was checked; the papers' text was not re-read for this note. **Nothing
new is claimed.**

## b. The pipeline, exactly as `run()` implements it in `scratch/ml_stress_test.py`

**Inputs.**
- **Features:** the 40 features, standardised across assets each day (demeaned and
  divided by their cross-sectional SD).
- **Family averages:** the mean of each family's member features, re-standardised
  across assets. There are 14 families, the complete-linkage families at tau 0.8 with
  sizes 2, 2, 4, 2, 6, 4, 6, 2, 2, 2, 2, 2, 2, 2.
- **Family quadratics:** each family average squared, then re-standardised (14).
- **Family pairwise products:** each pair of family averages multiplied, then
  re-standardised (91).
- **Target:** the day's return row, demeaned and standardised across assets. On the
  repository's panels a row's return is already the return its positions earn (signal
  at the close of t, held from t+1 to t+2).

**Walk-forward.**
- Years are chunks of 252 days, with the last chunk running to the end.
- The first window is three years, with an annual refit. Positions are formed from year
  four, so nine years are scored.
- **Two-day embargo:** each year's training data drops its last two days, and the trees'
  training window ends two days before the test year.

**Component A, block ridge.** A ridge on three blocks:
- the 40 features (L);
- the 14 family quadratics (Q);
- the 91 family products (I).

**One penalty per block**, scaled by the number of training rows, is chosen from a
grid of 48: L in {0.3, 1, 3}; Q in {0.3, 1, 3, off}; I in {1, 3, 10, off}, where "off" is
a penalty of 1e6. The choice minimises the leave-one-year-out error inside the training
window, computed exactly from per-year Gram matrices. The ridge is refit every year.

**Component B, boosted trees.**
- LightGBM, 50 trees, depth 2 (4 leaves), learning rate 0.1, minimum leaf 200, max_bin
  63, fixed.
- One thread, deterministic mode, row-wise, seed 1.
- **Trained on the 40 features only**, not the family terms.
- Refit every second year. The last fit is used in between.

**Stack.**
- **Out-of-fold predictions** inside the training window: leave-one-year-out for the
  ridge, at the penalties chosen for that window; three blocked folds, each with the
  two-day gap, for the trees.
- The target is regressed on the two out-of-fold columns with **non-negative weights**:
  exact two-column NNLS, falling back to (1, 0) if both weights are zero.
- The weights are refit when the trees are refit, and held in between.
- The prediction is the weighted sum of the two components' predictions.

**Positions.** The predictions are averaged over the last five days (fewer at the start
of the scored span), demeaned across assets, and scaled to unit gross: the repository's
own position rule. **No setting is exposed to an agent**; an agent can call the pipeline
but cannot configure it.

**Costs.** In the repository the net stream is formed with **the panel's own cost and
borrow** (on the ETF panel, 5 bps one-way per unit of turnover and 50 bps a year on
short notional). The script's flat 1 bp turnover cost belongs to its synthetic scoring
and is not part of the pipeline.

## c. Three planted non-linear shapes for the generator

Each shape is planted as a multiple `c` of a rule's positions (demeaned, unit gross), as
the generator plants a member. Its truth comes in closed form.
1. **U-shape** in one feature: positions proportional to `x_a^2`.
2. **Corner** rule on two features from different families: positions proportional to
   `1[x_a > 0.8 and x_b > 0]`.
3. **Pure product** of two features: positions proportional to `x_a * x_b`.

**The linear shadow of each** is the largest population Sharpe over the 82,240 class
members under that plant. It is computed before registration. Pairs with a large shadow
are excluded by a rule fixed at registration.

## d. Tests, to be registered later

| test | what it checks |
|---|---|
| **Leak test** | Positions up to a random date are bit-identical when all data after that date are changed |
| **Level at zero cost** | At level 0 with costs set to zero, the rejection rate is consistent with nominal |
| **False certification** | At level 0 with costs: one-sided, on the lower Wilson end |
| **Certification rate by shape against the class tier** | On the three planted shapes, paired by panel, one-sided |
| **Repeatability** | The same inputs twice on the pinned platform give the same output, exactly |

Both branches will be stated for each. A failed leak or level test means the tier is not
shipped, and the failure is reported. A valid tier that adds nothing on the non-linear
shapes is recorded as a null finding.

## e. The rule carried forward

**A learned component may cost power, never validity.**

## Revision, 2026-10-07 (America/Chicago): resolutions, a second predictor, and two known tensions

Appended before any code. Still exploratory and not a registration.

### a. The six conflicts with the repository, resolved

1. **Costs:** the panel's own cost and borrow function (`RealPanel` `cost_rate` and
   `borrow_rate`; on the planted panel, 5 bps one-way per unit of turnover and 50 bps a
   year on short notional). The script's flat 1 bp is not used.
2. **Families:** the repository's map. These are the complete-linkage families at tau
   0.8 of the 40 single-feature weight paths (`6726871`): {0,1}, {2,3}, {4,5,24,25},
   {6,7}, {8,9,26,27,28,29}, {10,11,12,13}, {14,…,19}, {20,21}, {22,23}, {30,31},
   {32,33}, {34,35}, {36,37}, {38,39}. The map is a fixed input, not the script's
   consecutive blocks.
3. **Standardisation:** all 40 features are re-standardised across assets each day by
   the pipeline itself. The 20 rank features are not unit-variance as stored.
4. **Alignment unchanged.** A panel row's return is the return its positions earn
   (signal at the close of t, held from the close of t+1 to t+2). An input at row t
   uses features at rows up to t and row-returns at rows up to t-2.
5. **The five-day average** of predictions before positions are formed is new to the
   repository, and is stated as such.
6. **Sharpe ratios use ddof 1**, as everywhere in the repository.

### b. "Platform-independent" withdrawn

The claim is **repeatability on one pinned platform**: this laptop, Darwin arm64,
Python 3.14.2, numpy 2.5.3, scipy 1.18.1, and LightGBM at the version pinned when it is
installed. BLAS summation order and LightGBM's floating-point arithmetic may differ on
other platforms. No claim is made about them.

### c. The certification bootstrap

**The bootstrap window is the scored days only.** The **block length is the class rule**
(`select_block_length`, as the class null uses it) applied to that window. Both are fixed
at registration.

### d. A second predictor: mv_combine, designed from theory and tested nowhere

**mv_combine was designed from theory on 2026-10-07 and has been tested nowhere, not
even on synthetic data.** It is specified below and built side by side with ridge_stack
(the stress test's stack, ported with the resolutions above) and a plain-ridge control.
- **Basis signals:**
  - 14 family signals (A), their squares (B) and their 91 pairwise products (C);
  - 42 family-by-state interactions (D), from three market states;
  - one tree portfolio (T).
- **Basis portfolios** are risk-sized (signal divided by the asset's trailing
  volatility), or not, as a switch. They are then demeaned, set to unit gross and
  averaged over five days.
- **The combination** is a mean-variance weight vector `b = (Sigma + diag(gamma))^-1 mu`
  on the 162 columns' net returns, with one ridge penalty per block, proportional to
  the block's variance. The penalty's scale is chosen by leave-one-year-out Sharpe
  inside the training window.
- **Positions** are the weighted sum, divided by its training mean gross and capped at a
  gross of 2.

The full specification is in the build request of 2026-10-07 (Part 2B), and the code
will follow it. **No new method is claimed.**

**Prior art, checked against Crossref on 2026-10-07.** For each: DOI, title, authors,
journal, volume, issue, pages and year. For the last three, the journal DOI was looked
up directly after the search returned working-paper versions. Only the metadata was
checked; none of the texts was re-read for this note.
- Kozak, S., Nagel, S. & Santosh, S. (2020), "Shrinking the cross-section", *Journal of
  Financial Economics* 135(2), 271–292, DOI 10.1016/j.jfineco.2019.06.008. A penalised
  mean-variance combination of many characteristic portfolios.
- Brandt, M. W., Santa-Clara, P. & Valkanov, R. (2009), "Parametric Portfolio Policies:
  Exploiting Characteristics in the Cross-Section of Equity Returns", *Review of
  Financial Studies* 22(9), 3411–3447, DOI 10.1093/rfs/hhp003. Weights as functions of
  characteristics, fitted on portfolio returns.
- Paulsen, D. & Söhl, J. (2020), "Noise fit, estimation error and a Sharpe information
  criterion", *Quantitative Finance* 20(6), 1027–1043, DOI 10.1080/14697688.2020.1718746.
  The in-sample Sharpe less effective parameters over time, as printed per refit.
- Grinold, R. C. (1994), "Alpha is Volatility Times IC Times Score", *The Journal of
  Portfolio Management* 20(4), 9–16, DOI 10.3905/jpm.1994.409482. Risk sizing.
- Gârleanu, N. & Pedersen, L. H. (2013), "Dynamic Trading with Predictable Returns and
  Transaction Costs", *The Journal of Finance* 68(6), 2309–2340, DOI 10.1111/jofi.12080.
  Smoothing positions against costs.
- Nagel, S. (2012), "Evaporating Liquidity", *Review of Financial Studies* 25(7),
  2005–2039, DOI 10.1093/rfs/hhs066. Returns to short-term reversal conditioned on market
  volatility, the motivation for the state interactions.

### e. Two known tensions, stated in advance

1. **The penalty against the planted edge.** mv_combine's penalty shrinks low-variance
   directions hardest. The generator plants its edge along a random rule, whatever that
   rule's variance. **So mv_combine may look worse on planted panels than it would on
   real data**, where edges need not sit in low-variance directions.
2. **Risk sizing against the planted edge.** Risk sizing assumes expected return scales
   with volatility; planted edges do not follow that.

**The pilot therefore reports mv_combine with risk sizing on and with it off.**

## Planted rules: eligible features and a fast/slow split, decided 2026-10-07 (America/Chicago), before any generator code

The author's decision, recorded before the generator is written.
1. **Eligible features: all 40, by a seeded uniform draw.** Corner and product draw their
   two features from different families. **Nothing is excluded, now or after the
   turnover report.**
2. **A fast/slow label, fixed now, from turnover alone.** A planted rule is **fast** if
   the mean daily turnover of its unit-gross position path on the pinned features
   exceeds **0.5** (the fraction of gross traded per day); otherwise it is **slow**.
   - The label is computed from the position path only, before any pipeline is fitted.
   - **The 0.5 threshold is not moved after the turnover table is seen.**
3. **Reporting.** Every pilot table is given three ways: pooled, fast only and slow
   only, with the draw count in each cell. A cell with fewer than 5 draws is printed and
   marked **thin**. It is not dropped or merged.
4. **What every plant records:** `c`, the population gross Sharpe and the population net
   Sharpe. `planted_scale` stays net-targeted, as in the repository. Capture is reported
   against both.
5. **The full turnover table** for all four rule shapes is reported as part of the build.
   It is descriptive and changes nothing above.

## Decisions, 2026-10-07 (America/Chicago), before any code

The author's decisions on the four open points, with additions. Recorded before code.

1. **ridge_stack's fourth block** (the 42 family-by-state columns, scaled by their
   training standard deviation and not re-standardised by day) takes the penalty values
   **{1, 3, 10, off}**, as the product block does. The grid becomes 3 x 4 x 4 x 4 = **192**.
2. **Warm-up.** Rows without a full 63-row history of realised returns for sigma are
   **dropped from every fit, for all three predictors alike, and the count dropped is
   printed.** The states stay zero until 252 rows of history, as specified.
3. **Linear shadow (the design quantity):**
   - a seeded sample of **100 feature choices per pair rule** (corner, product);
   - **all 40 features** for U and the state-gated rule;
   - on its own dedicated seed block, **685000–685999**, checked on 2026-10-07 against
     every pre-registration: NO COLLISION.

   The distribution is reported with its n.
4. **The state-gated rule.** Off days (volatility state at or below its expanding median)
   are **zero positions**; on days are **unit gross**. Trades into and out of the gate are
   costed like any other trade, and `planted_scale`'s net target is taken **over all
   days, on and off**.

**Additions.**
- **B. The fast/slow label, for a path that is not unit gross every day.** Turnover is
  the sum over days of |change in position| divided by the sum over days of gross. For
  unit-gross paths this equals the definition recorded at `c356992`. **This is a
  clarification, not a change**, and the 0.5 threshold is unchanged.
- **C. The plant and the dispersion state.**
  - The plant cannot move the volatility state: a dollar-neutral plant has zero
    equal-weighted market return.
  - **It can move the 21-row dispersion state**, which the pipelines see. **This is not
    removed.**
  - The turnover report gives, for each state-gated plant, the dispersion state with and
    without the plant, and its correlation with the gate both ways. This is a design
    quantity, and no pipeline is fitted for it.
- **E. The LightGBM pin.** **LightGBM 4.7.0**, wheel
  `lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl`, **SHA-256
  `129535462686f274df179133643118c5c5c5667167fe6c3a28d955f0b3c8e868`**. It is a pre-built
  wheel for this platform (nothing built from source), installed into `.venv` on
  2026-10-07. A test requires two fits with the registered tree settings to give
  bit-identical predictions.
- **F. Seed blocks.**
  - The linear shadow uses **685000–685999** (item 3).
  - The cost-only smoke uses **686000–686999**.
  - Both were checked against every pre-registration on 2026-10-07: NO COLLISION.

## The capture ceiling from effective parameters, written 2026-10-07 (America/Chicago), before any pilot

**A design quantity; no outcome was read.**
- **Source:** mv_combine's effective parameters, `trace(Sigma (Sigma + diag(gamma))^-1)`,
  on the two level-0 smoke panels (686000 and 686001; `runs/ml_smoke/2026-10-07`,
  `55d5441`), for each c in the grid and each refit. Their training windows run from 3 to
  10.74 years.
- **The formula:** the ceiling on the share of a planted edge captured is
  `1 / sqrt(1 + effective parameters / (T_years * Sharpe^2))`. It is computed per refit,
  then averaged over refits and panels; the range over refits is in brackets.
- **What it covers:** estimation noise only. It assumes the edge lies in the span of the
  basis, and says nothing about whether it does. The linear shadow (Part 5a) is a
  separate quantity.

| setting | c | true Sharpe 1.0 | 1.5 | 2.5 | mean effective parameters |
|---|---|---|---|---|---|
| risk sizing on | 0.25 | 0.598 [0.530–0.637] | 0.745 [0.684–0.778] | 0.880 [0.842–0.900] | 11.54 |
| risk sizing on | 0.5 | 0.669 [0.606–0.704] | 0.803 [0.752–0.829] | 0.913 [0.885–0.927] | 7.94 |
| risk sizing on | 1.0 | 0.740 [0.687–0.771] | 0.855 [0.817–0.876] | 0.940 [0.921–0.950] | 5.30 |
| risk sizing on | 2.0 | 0.808 [0.770–0.833] | 0.899 [0.875–0.914] | 0.960 [0.949–0.966] | 3.43 |
| risk sizing on | 4.0 | 0.868 [0.845–0.885] | 0.934 [0.921–0.944] | 0.975 [0.969–0.979] | 2.13 |
| risk sizing off | 0.25 | 0.560 [0.498–0.602] | 0.711 [0.653–0.749] | 0.860 [0.821–0.883] | 14.09 |
| risk sizing off | 0.5 | 0.635 [0.578–0.672] | 0.776 [0.728–0.806] | 0.899 [0.871–0.915] | 9.56 |
| risk sizing off | 1.0 | 0.713 [0.666–0.742] | 0.836 [0.801–0.857] | 0.930 [0.913–0.941] | 6.26 |
| risk sizing off | 2.0 | 0.789 [0.757–0.810] | 0.888 [0.867–0.900] | 0.955 [0.945–0.960] | 3.94 |
| risk sizing off | 4.0 | 0.857 [0.839–0.870] | 0.928 [0.918–0.936] | 0.972 [0.968–0.975] | 2.37 |

## Accepted as implemented, and one known defect, 2026-10-07 (America/Chicago)

The author reviewed `2800587..bb2bfa2`.

**Accepted as implemented:**
- **The tree series' two early rows.** At each tree refit, the two embargo rows between
  the out-of-fold window and the test year take the new booster's predictions. The
  out-of-sample extension of the tree column therefore starts two rows early. No
  unrealised data is used.
- **When the states start.** The states are non-zero from about row 315: 252 valid state
  values, the first available at row 64.
- **The nested solve is left unoptimised.** ridge_stack's out-of-fold penalties are chosen
  without the predicted year by a full nested leave-one-year-out, about 20 s of its
  roughly 30 s per panel on the laptop. The cheaper correct form (each leave-two-out solve
  once per pair of years) is not adopted now.

**Known defect, not fixed now: the state-gated rule's holdout gate restarts from zero.**
The gate's volatility state is rebuilt from the holdout segment's own data, so it is zero
(and the gate off) for about the first 316 holdout rows. **The pilot reads no holdout
quantity.** Before any run that does, the gate must continue from the in-sample state
history.
