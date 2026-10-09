# The recency-weighted certificate on planted panels: validation plan, 2026-10-09 (America/Chicago)

**Status: PLAN with registered expectations, committed alone before the planted code.
NOT RUN.** No planted panel has been drawn on the seeds below, and no box has been used.
It belongs to `prereg/recency-weight-exploratory-2026-10-09.md` (`d7d36df`) and its
amendment 1 (`190d75e`). Points needing the author are marked [AUTHOR].

**Code so far (not the planted runner):**
- `estimator/recency.py` (`0337e1c`): the statistic, both centrings, the class maximum by
  weighted counts, L90, the levels and the performance line.
- `tests/test_recency.py`: 7 tests on synthetic data, all passing. They cover the flag-off
  path (bit for bit), the equal-weights limit (to 1e-10), the two centrings differing at
  finite h, and the class kernel.
- **The unweighted path is unchanged**, shown on one committed log (`6eb1885`): the
  French in-sample read (`runs/french_insample/2026-10-07`) re-priced through the flag-off
  path reproduces every recorded field bit for bit. That covers the stream's S, p, L90,
  block length and confidence curve, and the class's S, p, L90, block length and best
  member.

## 1. What is tested

The statistic, not a learner. The declared stream is a fixed member's own stream, with a
planted drift. So any difference between weighted and unweighted certification is due
to the weighting alone.

## 2. Panels

- **The pool:** the ETF in-sample panel behind the planted panels (`environments.planted_panel`):
  3,019 rows, 40 assets, the pinned X, its residual returns E, and 82,240 class members.
- **Long panels by row resampling:** the panel's rows are a stationary bootstrap of the
  pool's rows (block length 7, as the planted panels use), drawn to the target length.
  Features, residuals and their pairing move together, so each member's stream at a long
  row is its stream at the drawn pool row.
- **Gross streams.** No costs: a row-resampled panel has no meaningful turnover at block
  joins. Every member's stream is its gross return on the pool row, demeaned over the
  pool. Each pool row is drawn with equal probability, so **every member has exactly zero
  population mean: an exact null.**
- **The declared stream:** the gross stream of one member, the panel's planted member
  (drawn per panel, as `planted_panel.planted_member`).
- **The planted edge:** a deterministic drift μ_t = β · p(t) · sd_pool / sqrt(252) added
  to the declared stream, where sd_pool is that stream's pool standard deviation and p(t)
  the profile:
  - **null:** p = 0;
  - **constant:** p = 1;
  - **decaying:** p = 1 for the first half of the rows, then linear to 0 at the last row;
  - **emerging:** p = 0 for the first half, then linear from 0 to 1 at the last row.

  β is the edge's annualised Sharpe at full strength (approximately; the drift adds to a
  stream whose own Sharpe is exactly 0).
- **Lengths:** 20 years (5,040 rows) and 40 years (10,080 rows). Rows are daily, so
  h = 1,260 rows, and the effective lengths are 12.7 and 14.4 years.

| arm | length | profile | β | panels | seeds |
|---|---|---|---|---|---|
| N20 | 20 y | null | 0 | 1,000 | 702000–702999 |
| N40 | 40 y | null | 0 | 1,000 | 703000–703999 |
| C20 | 20 y | constant | 0.5 | 400 | 704000–704399 |
| D20 | 20 y | decaying | 0.5 | 400 | 704400–704799 |
| E20 | 20 y | emerging | 1.0 | 400 | 704800–705199 |
| smoke and dry run | 2 y and 20 y | all | — | 10 | 705900–705909, never read |

- The blocks were checked with `experiments.seed_block_check` on 2026-10-09: NO COLLISION
  for 702000–702999, 703000–703999 and 704000–705999.
- Each panel seed spawns its children: the panel's row draw, the planted member, and each
  test's bootstrap seed, as `planted_panel.children` does.
- **Why these β:** at 20 years, each arm's normal-approximation rates are near the middle
  of their range, where differences are most visible (section 4).

## 3. The tests run on each panel

All at B = 5,000, with the block length by Politis–White on the panel's base columns
(the class rule), as now. h = 1,260 rows.

| | stream | class maximum (82,240 members) |
|---|---|---|
| unweighted (the current statistic) | every arm | — (its size is already registered elsewhere) |
| weighted, fixed centring (amendment 1) | every arm | N20, N40 |
| weighted, centring as written, **"superseded, kept beside"** | N20, N40 | N20, N40 |

- Both levels are read from each p: the 96% level (stream p < 0.04, class p < 0.01) and the
  90% level (stream p < 0.08, class p < 0.02).
- **[AUTHOR] The class tier is in the null arms only.** At 20 years its bar is far above
  these β, so its power would be near 0 in every edge arm and would show nothing.
- **How the class maximum is computed on a long panel:** each member's pool stream is
  computed once (gross, from the fast kernel's tables on the pool). A replicate's weighted
  moments are aggregated to pool rows: the weight of pool row i in replicate b is the sum
  of w_t over the positions t whose resampled long row was drawn from i. The drift is
  added exactly for the planted member. No long-panel table is ever built.

## 4. Registered expectations, stated before any run

**Size (null arms), one-sided on the lower 95% Wilson end.** A rate "fails" iff the lower
Wilson end of its certification rate exceeds the level.
1. **Fixed centring, stream:** the rate does not fail at either level, in N20 or N40.
2. **Fixed centring, class:** the rate does not fail at either level, in N20 or N40.
3. **Superseded centring, stream:** expected to fail.
   - The normal-approximation iid rates (amendment 1) are 0.113 / 0.166 at 20 years, and
     0.153 / 0.205 at 40 years, at the 96% / 90% levels.
   - Its rate is expected to exceed the fixed centring's in both arms. Paired difference:
     the 95% paired bootstrap interval (B 10,000) lies above 0.
4. **Superseded centring, class:** expected to exceed the fixed centring's rate in both
   arms, by the same paired interval. No numerical prediction is registered: a maximum
   over 82,240 correlated members is not covered by the single-stream approximation.

**Power (edge arms, stream), paired weighted − unweighted certification rate at the 96%
level.** The expectation holds iff the 95% paired bootstrap interval lies on the stated
side of 0.

| arm | expected sign | normal-approx rates (unweighted / weighted) | expected difference |
|---|---|---|---|
| E20 emerging | weighted > unweighted | 0.26 / 0.50 | +0.24 |
| D20 decaying | weighted < unweighted | 0.47 / 0.20 | −0.27 |
| C20 constant | weighted < unweighted (the stated cost) | 0.69 / 0.51 | −0.17 |

At the 90% level the same differences are reported, with no separate expectation.

**Both branches for each expectation:**
- **It holds:** "the weighted certificate behaves as stated on planted panels of this
  kind".
- **It fails:** reported as it is, with its interval. A failure of expectation 1 or 2 (the
  fixed centring's size) blocks any registration that would use the weighted statistic,
  until the author decides.

## 5. Detectability at these n

**Size, one-sided Wilson test.** The probability that a rate fails, by true rate:

| level | n | false alarm at the level | true rate → probability of failing |
|---|---|---|---|
| stream 0.04 | 1,000 | 0.026 | 0.05 → 0.35; 0.06 → 0.84; 0.07 → 0.99 |
| stream 0.08 | 1,000 | 0.030 | 0.10 → 0.64; 0.11 → 0.92; 0.12 → 0.99 |
| class 0.01 | 1,000 | 0.026 | 0.02 → 0.78; 0.025 → 0.96 |
| class 0.02 | 1,000 | 0.033 | 0.03 → 0.60; 0.035 → 0.87; 0.04 → 0.97 |

So an inflation to 1.5× the level is detected with probability about 0.85 at the 96% level,
and an inflation to 1.25× is not reliably detected.

**Paired differences, n = 400.** With about 30% discordant pairs, the standard error is about
0.025. A difference of about 0.06 is detected with 80% power, and the expected differences
(0.17–0.27) are detected with probability near 1.

**These rates are normal approximations with iid returns.** The planted streams have the
pool's dependence (block length 7), so the realised rates will differ. The expectations
are about signs and Wilson ends, not about matching these numbers.

## 6. Cost

Measured on the laptop (Darwin arm64, one thread) on random data of the same shapes:
- **A weighted stream null at B = 5,000:** 7.3 s at 20 years, 14.6 s at 40 years. The
  unweighted one takes the same.
- **The weighted class null:** about 0.6 min per panel and centring, plus 7–15 s for the
  aggregated weights. The members' pool streams are built once and shared by all panels:
  2 GB, held as a memory map.

| arm | panels | per panel (one core) | total, one core |
|---|---|---|---|
| N20 (3 stream tests, 2 class tests) | 1,000 | about 110 s | 31 h |
| N40 (the same) | 1,000 | about 150 s | 42 h |
| C20, D20, E20 (2 stream tests each) | 1,200 | about 15 s | 5 h |
| **total** | 3,200 | | **about 78 core-hours** |

- **The laptop (8 cores, 8 GB):** about 10–12 hours if memory allows 6–8 workers sharing
  the memory-mapped pool streams. Overnight is feasible.
- **The box (c7a.48xlarge, 180 workers; the measured slowdown under load 1.7×):** about 45
  minutes of run plus setup, about 1.2 box-hours, roughly $12–15.
- **Nothing runs on the box,** per the author's instruction. Where it runs is the author's
  choice [AUTHOR].

## 7. What this does not test

- **A learner.** The declared stream is a fixed member's own stream. Whether recency
  weighting helps a learned stream (Sancho, version 2) is not tested here.
- **Costs.** All streams are gross.
- **Daily rows only.** The 4h half-life (10,950 rows) is not tested here.
- **Profiles other than the three.**

## [AUTHOR] points

1. The class tier in the null arms only.
2. The β values (0.5, 0.5, 1.0) and n (1,000 per null arm, 400 per edge arm).
3. Where it runs: the laptop overnight, or the box (about $12–15).
4. Whether a 10-year null arm is also wanted, to tie these results to the French
   in-sample window (n_eff 8.7 years).

## Amendment 1, 2026-10-09 (America/Chicago): the author's answers, and two non-stationary null arms

**Answers to the [AUTHOR] points:**
1. **The class tier is in the null arms only:** yes.
2. **β and n:** as written.
3. **Where:** on the box, and only on the author's own typed go. In the same box session,
   the three version-2 confirmation logs left on its disk (`logs/v2c_smoke.log`,
   `logs/v2c_run.log`, `logs/v2c_dry.log`) are fetched one file at a time. The rsync exit
   status is reported for each, and each file is checked against what the confirmation's
   run record (`1ba8df7`) recorded about it.
4. **No 10-year null arm.**

**Addition: two non-stationary null arms.** The row-resampled panels are stationary by
construction. So nothing else in this plan checks the note's section c (the null mixes
periods). These two arms do.
- **Stream tier only;** 40 years (10,080 rows); 1,000 panels each.
- Each panel runs the weighted statistic with the fixed centring, and the unweighted
  statistic, on the same bootstrap index sets. A failure can then be attributed to the
  weights or to the block length.

**How the shift is applied.** The registered block-length rule measures dependence on the
panel's base columns, not on the declared stream. A shift applied to the declared stream
alone would be invisible to it. **So each shift is applied to every stream on the panel,
the declared stream and the base columns alike,** as a change in the market would be.
Each stream's population mean stays exactly 0.

| arm | shift | seeds |
|---|---|---|
| NV40, volatility shift | every stream multiplied by 2 on the oldest 75% of rows (rows 0 to 7,559) | 706000–706999 |
| NA40, dependence shift | on the most recent 25% of rows only (rows 7,560 to 10,079): y_t = (x_t + 0.3·x_{t−1} + 0.3·x_{t−2}) / sqrt(1.18) | 707000–707999 |

- **NA40's division by sqrt(1 + 0.3² + 0.3²) is proposed** in place of the author's
  unscaled form.
  - Without it, the recent rows' variance also rises by about 18%, which mixes a
    volatility shift into the dependence shift.
  - With it, the marginal variance is unchanged when x is serially uncorrelated, and the
    mean is still exactly 0.
  - **[AUTHOR]:** the scaled form or the unscaled one.
- **Seed blocks** checked with `experiments.seed_block_check` on 2026-10-09: NO COLLISION
  for 706000–706999 and 707000–707999.
- **Block length:** by the registered rule (the Politis–White median of the base columns)
  on the whole window.
  - **In every panel of every arm,** the Politis–White median on the last n_eff rows is
    also recorded beside it: 3,634 rows at 40 years, 3,208 at 20 years. So the comparison
    exists wherever it is needed.

**Expectations:**
- **NV40:** the weighted fixed-centring rate does not fail at either level (the lower 95%
  Wilson end at or below 0.04, and at or below 0.08). The unweighted rate is reported
  beside it, with no expectation.
- **NA40: no expectation is registered.** Both branches:
  - **It does not fail:** the weighted certificate's size holds under this dependence
    shift on these panels.
  - **It fails:** the weighted reads' block-length rule is reopened before any real
    registration uses the weighted statistic. The unweighted rate and the two recorded
    Politis–White medians are read beside it, to attribute the failure to the weights or
    to the block length.

**Detectability (n = 1,000; the one-sided Wilson test):**

| level | true rate → probability of failing |
|---|---|
| 0.04 | 0.05 → 0.35; 0.06 → 0.84; 0.07 → 0.99 |
| 0.08 | 0.10 → 0.64; 0.11 → 0.92; 0.12 → 0.99 |

**The updated cost table** (one core; to be re-measured by the smoke):

| arm | panels | per panel | total, one core |
|---|---|---|---|
| N20 | 1,000 | about 110 s | 31 h |
| N40 | 1,000 | about 150 s | 42 h |
| C20, D20, E20 | 1,200 | about 15 s | 5 h |
| NV40, NA40 (2 stream tests each, plus 2 Politis–White medians) | 2,000 | about 35 s | 19 h |
| **total** | 5,200 | | **about 97 core-hours** |

On the box (180 workers, 1.7× under load), that is about 55 minutes of run, about 1.4
box-hours with setup, roughly $15–18.
