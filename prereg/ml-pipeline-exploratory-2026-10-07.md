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
