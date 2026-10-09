# ML arm, version 2: exploratory design, 2026-10-08 (America/Chicago). EXPLORATORY

**No claim rests on this note.** It records version 2's design and the author's decisions,
before any version-2 code is written.
- **Version 1 stays the baseline:** ridge_stack as pinned at `fce5627`. Its four `learn/`
  blobs stay byte-identical, and version 2 does not modify them.
- **Version 2 lives in a new package, `learn2/`.**
- **No real-panel outcome is read** anywhere in this work. Binance stays held unread
  (`4f5fdd8`), French is not touched, and no box is used.

## The author's decisions

1. **Agents choose views only.** Fit settings are **averaged, never chosen.**
2. **A larger menu:** views over information blocks, horizon, target and regime.
3. **A regime lever** is added.
4. **French:** a no-delay (d = 0) test comes later, as a labelled paper result, with the
   second look on French counted.
5. **Binance:** the fee is 5 bps as an assumption. The venue is not accessible to a US
   resident.
6. **Memory settings:** rolling 252 rows, rolling 756 rows, and expanding from 756 rows,
   as in version 1.
   - All three are first scored after 756 rows plus the embargo, so the nine variants
     share one scored window.
   - They refit every 252 rows.
   - Panels too short for these values declare their own three values later.
7. **Nested out-of-fold penalties:** 3 blocked folds within each training window, with the
   embargo removed at each fold edge (as version 1's trees already do). The rule is the
   same for every memory setting.
8. **The S block is kept as in version 1** (state × family interactions, when P is
   active), and the trees keep the 3 market states as inputs. Regimes gate positions on
   top, after the fit.
9. **The averaged book is not rescaled.** Turnover and cost drag are reported **per unit
   of gross held** (Σ|Δw| / Σ gross, the fast/slow label's definition) beside the raw
   figures, so version 2's averaged book and version 1's unit-gross book are compared on
   the same footing.
10. **On planted ETF panels, blocks X and V come from the REAL ETF data** behind the pinned
    rows, not from the panel's returns. The decision and its reason are under "Blocks on
    planted panels" below.
11. **Market series:**
    - The regime states use the equal-weighted average of the panel's own returns, as
      `learn/inputs.py` does in version 1.
    - Block X uses the real ETF panel's declared market, SPY's real return column.

## A. Timing

- **Each panel declares its delay d in {0, 1}:** feature row t earns the return of row
  t + 1 + d.
- **ETF and French keep d = 1.** Their builders and pins are unchanged. `learn2` reads
  the delay as `panel.meta.get("delay", 1)`.
- **d = 0 is exercised only on synthetic and planted panels for now.**
- **The row return known at the close of row t** is the earned return of row t − 1 − d.
  Every `learn2` input uses only those returns, at rows ≤ t. (Version 1's lag of 2 is the
  d = 1 case.)

## B. Input blocks

Every block uses rows ≤ t only and is standardised cross-sectionally (a z-score per row,
missing values 0). Ranks, where used, are average ranks for ties.

**P: the registered 40,** as the panel supplies them.

**X: cross-asset, 10 columns.** Inputs at row t:
- r: the row returns known at t;
- m: the declared market series;
- the trailing window: the 252 rows ending at t.

| # | column | definition |
|---|---|---|
| 1, 2 | beta × market, 1 and 5 rows | β_i = cov(r_i, m) / var(m) over the window; times m_t, and times Σ m over the last 5 rows |
| 3–8 | PC_k loading × PC_k return, k = 1, 2, 3; 1 and 5 rows | C = the correlation matrix of the window's returns, each asset standardised by its window mean and sd; v_k its k-th eigenvector (eigenvalues descending); the loading of asset i is v_k,i; the component return is f_k = Σ_i v_k,i · (r_i − mean_i) / sd_i at the row, and Σ of f_k over the last 5 rows; the column is v_k,i times f_k (1 row) and times Σ f_k (5 rows); the eigenvector's sign is arbitrary and the product does not depend on it |
| 9, 10 | own return net of beta × market, 1 and 5 rows | r_i,t − β_i m_t, and Σ (r_i − β_i m) over the last 5 rows |

- A column is 0 until its window holds 252 rows.
- The window's means and standard deviations use ddof 1.
- An asset whose window has zero variance gets a loading and a beta of 0.

**V: volume and flow, where the panel has the fields** (5 columns at most):

| # | column | definition | needs |
|---|---|---|---|
| 1 | log volume ratio | log(v_t) − log(mean of v over rows t−20..t) | volume |
| 2 | taker-buy share, last row | taker_buy_volume_t / volume_t − 0.5 | taker-buy volume (Binance) |
| 3 | taker-buy share, 21-row mean | mean over rows t−20..t of (taker share − 0.5) | taker-buy volume (Binance) |
| 4 | trade-count ratio | log(n_t) − log(mean of n over rows t−20..t) | trade count (Binance) |
| 5 | Amihud | mean over rows t−20..t of |r| / (price × volume) | volume and price |

A panel uses the columns its fields allow. **The ETF data has volume and adjusted close, so
ETF V has 2 columns: 1 and 5.** Binance would have all five.

**F: funding, where present** (3 columns):
- the last funding rate known at t;
- its mean over rows t−20..t;
- its change, rate_t − rate_{t−1}.

**Blocks on planted panels (decision 10).**
- On planted ETF panels, P is the real pinned X at the real row t. The returns are
  resampled residuals plus the plant.
- **X and V are built from the real ETF data** (prices, volume, SPY as X's market) at the
  real rows behind the pinned P rows, with the warm-up history before them.
- They are built once, hashed, and **pinned alongside P.** A plant cannot move them.
- **The lead-lag and volume-conditioned planted rules** (H) build their positions from
  these same columns, so a planted X or V edge is exactly visible to the learner.
- **The author's reason:** the residuals E are block-resampled, so they keep real
  short-range serial and cross-asset dependence within blocks. X computed from E, or from
  planted returns, would then predict the panel's own returns at level 0. That would:
  - (a) break the null that the level test relies on; and
  - (b) amount to reading real ETF lead-lag structure through the planted panels.
- **Checked on 2026-10-08:**
  - `environments.planted_panel.make_draw` resamples E with the Politis–Romano
    stationary bootstrap (`estimator.bootstrap.stationary_bootstrap_indices`): geometric
    block lengths with mean `BLOCK_LENGTH` = 7 rows, uniformly random starts, circular
    wrap.
  - E is the in-sample earned returns with each asset's time mean removed
    (`planted_panel.residual`). It is not market-residualised.
  - So within a block, consecutive rows are consecutive real rows, and **the concern is
    right.**
- With real-row X and V, at level 0 the X and V columns are independent of the panel's
  resampled returns by construction, as P is.
- **The leak test still exercises the X and V code** on its own inputs.
- **The regime states** on planted panels come from the panel's own returns. That is E's
  market, which a dollar-neutral plant cannot move, as in version 1.

## C. Views

A view = (information, horizon, **neutrality**, regime). (The lever was changed from target
to neutrality on 2026-10-08; see "Change: neutrality replaces the target lever" below.)
- **Information:** any non-empty subset of the panel's available blocks. The ETF panel has
  P, X and V, so 7 subsets.
- **Horizon h ∈ {1, 5, 20} rows.** The target is the forward h-row return: the sum of the
  earned returns of rows t … t+h−1, which are the row returns of t+1+d … t+h+d. **The
  embargo is h + 1 + d rows.**
- **Target, for every view:** version 1's cs of that forward h-row return, demeaned
  across assets and divided by the cross-sectional SD each row. Under group neutrality it
  is demeaned within the asset's group instead (see below).
- **Neutrality:** market or group (see below).
- **Regime:** always, or one of 6 gated regimes: market vol high or low, trailing market
  return up or down, dispersion high or low.
  - The states are `learn/inputs.py`'s three (vol, sum, dispersion), from the panel's own
    returns, with lag 1 + d.
  - Each is split at its expanding median (rows ≤ t).
  - A regime is off until its state is warm (non-zero).
  - **A regime view's positions are 0 while its state is off.** Entries and exits are
    costed.
  - **The regime gates positions only.** It does not change the fit.
- **On the ETF panel:** 7 × 3 × 2 × 7 = **294 views**.

## Change: neutrality replaces the target lever (author, 2026-10-08, before any code)

**Why.** As first specified, the target lever (raw or net of the equal-weighted market)
was nearly a no-op.
- Positions are demeaned.
- A per-row market component is orthogonal to cross-sectionally standardised columns.
- So raw and net would differ only through the square, product and tree terms.

**Now:**
- **Every view's target is version 1's cs(forward h-row return).**
- **The second lever is NEUTRALITY,** with two choices:
  - **market:** the target is cs(forward h-row return), and positions are demeaned across
    all assets, then scaled to unit gross.
  - **group:** the target is the forward h-row return demeaned **within the asset's
    group**, then divided by the row's cross-sectional SD of those group-demeaned values.
    Positions (the prediction) are demeaned within each group, then scaled to unit gross
    overall.
- **The menu sizes are unchanged:** 7 × 3 × 2 × 7 = 294 views on ETF.
- **Part 5's nested menus:**
  1. the base view;
  2. information × horizon (21);
  3. plus neutrality (42);
  4. plus regime (294).
- **No dedicated planted rule for neutrality in the pilot.** The neutrality lever's value is
  measured only by level and by its effect on the bar.

**The groups: an exact rule.** The groups at row t use rows ≤ t only.
1. **Returns:** the same returns block X uses (on planted ETF panels, the real ETF row
   returns behind the pinned rows), over the trailing 252 rows ending at t.
2. **Correlation:** the 252-row correlation matrix (ddof 1). An asset with zero variance in
   the window has correlation 0 with every other asset. The distance is d = 1 − ρ.
3. **Clustering:** average linkage (UPGMA) agglomerative clustering. Each cluster is
   identified by its smallest asset index.
   - Each step merges the pair of clusters with the smallest average distance.
   - **Ties are broken by asset index:** the pair whose (smaller id, larger id) is
     lexicographically smallest.
   - Merging stops at **5 clusters.**
4. **Small groups are merged:** any cluster with fewer than 3 assets goes into its nearest
   cluster, by average distance, with ties to the smaller id.
   - Small clusters are processed in order of size, then of id, until every group has 3 or
     more assets.
5. **Labels:** groups are numbered by their smallest asset index. Before 252 rows of
   history there are no groups.
6. **Recomputed at each refit:** the groups used by a fit, for its training targets, and
   by the positions until the next refit, are those at the refit row.
   - Groups are computed for every row and looked up at the refit row.

On planted ETF panels the per-row groups are a fixed real input, built once, hashed and
pinned with X and V, like P.

**Two choices the author's rule left open, settled here:**
- **The SD divided by** under group neutrality is that of the group-demeaned values across
  all assets in the row.
- **Groups do not change between refits.** A view's group positions until the next refit
  use the refit row's groups, so that the fit and the positions share one grouping.

## D. The learner

There is one learner per (information, horizon, neutrality, memory). It is version 1's
ridge_stack structure, re-implemented in `learn2`; version 1's code is not imported for
the fit.
- **Ridge blocks:**
  - L, linear over the active columns;
  - when P is active, also Q (the 14 family squares), I (the 91 family products) and S (the
    3 states × 14 families, as in version 1).
- **Penalties:** version 1's grid restricted to the active blocks.
  - L: {0.3, 1, 3}.
  - Q: {0.3, 1, 3, off}.
  - I and S: {1, 3, 10, off}.
  - Each is chosen by nested out-of-fold error over **3 blocked folds** within the
    training window, with the embargo at each fold edge.
- **Trees:** the registered settings (50 trees, depth 2, learning rate 0.1, minimum leaf
  200, deterministic, 1 thread). They take the active columns plus the 3 states. Their
  out-of-fold predictions use the same 3 blocked folds.
- **Stack:** non-negative weights on (ridge out-of-fold, tree out-of-fold).
- **Walk-forward:** the first scored row is 756 + embargo. Refits come every 252 rows
  after that.
  - Each refit trains on the rows whose targets are realised before it.
  - For the rolling settings, only the last 252 or 756 of those rows are used.
  - The 64-row warm-up drop is kept.
- **Conventions settled before coding (2026-10-08):**
  - **The embargo:** a refit at row s trains on rows t ≤ s − (h + 1 + d) only. For h = 1
    and d = 1 that is version 1's rule: its last 2 rows before each refit are removed.
  - **Trees are refit at every refit,** not every second one as in version 1, since each
    tree fit is small. Their out-of-fold predictions use the same 3 blocked folds.
  - **The ridge's out-of-fold predictions for the stack** are nested. For each fold, the
    penalties are chosen by the other two folds alone (each fitted on one and scored on the
    other, with the embargo at the edges). The penalties for the final fit are chosen over
    all 3 folds.
  - **A view's first scored row is 756 + h + 1 + d.** A menu's streams are compared on
    their common window, from the latest first row in the menu.
- **Every refit whose chosen penalty sits at a grid edge is reported,** for any block at
  its smallest or largest value; "off" counts as the largest.
- **The prediction is turned into a target position:** demeaned across assets and scaled to
  unit gross.

## E. Fit settings are averaged, never chosen

- **Nine variants:** trading rate a ∈ {1.0, 0.3, 0.1} × the three memory settings.
  - A variant's book is new = (1 − a) · old + a · target.
  - The book starts from 0 at the first scored row.
- **The view's book is the equal-weight average of the nine variants' books,** then
  regime-gated. It is not rescaled, and it is costed once, on the averaged book.
- **Stored per view, as the robustness reading:** the nine variants' pairwise position
  correlations (positions only).
- **Caching:** the fit depends on (information, horizon, neutrality, memory) only. Rates
  and regimes are applied afterwards, and the fits are cached by that key.

## F. The menu tier

- **The p-value of a chosen view** = (1 + #{b : max over ALL views of the demeaned
  replicate Sharpe ≥ the chosen view's observed Sharpe}) / (B + 1).
  - The replicate rows are a joint stationary bootstrap.
  - The block length uses the class tier's rule on the base feature columns over the
    common scored window.
  - With one view this equals the supplied-streams tier, and that is tested.
- **The base view,** priced as one declared strategy for the head-to-head with version 1:
  all available blocks, h = 5, market-neutral, always.

## G. Checks

- **A leak test for every block and for a sample of views:** positions up to row t must be
  bit-identical when all data after row t is replaced.
- **A bit-for-bit repeat of fits.**

## H. Planted rules: three new shapes

They are added to `environments/planted_rules.py` **without changing any existing draw.**
Every existing shape's features, positions and scale stay bit-identical, and that is
tested.
- **Lead-lag:** an X column, drawn uniformly from the 10. Positions are its z-score,
  demeaned, unit gross.
- **Volume-conditioned:** a P column a, and a V column b drawn from those the panel has.
  The P column is used only on assets whose V_b exceeds that row's cross-sectional median;
  the other assets get 0. Then the positions are demeaned and scaled to unit gross on rows
  with any active asset.
- **Regime-only:** a P column a and one of the 6 gated regimes, both drawn. Positions are
  z_a while the regime is on, and 0 otherwise.
  - The regime is read from the residual market E, as the existing gated rule does. A
    dollar-neutral plant cannot move it, and on planted panels it equals the learner's
    state input.
- **As for every planted rule:** net-targeted planting (`planted_scale`), the fast/slow
  label at turnover 0.5, and tests.

## Compute

On one panel the fit cells number 7 × 3 × 2 × 3 = **126.** The 9 variants per view and the
294 views reuse them. Part 4 measures the seconds per cell, and Part 5 projects a pilot
from that.

## Order of work

1. This note, committed alone.
2. `learn2/`, with tests on synthetic arrays.
3. A cost-only smoke on level-0 planted ETF panels (a fresh checked seed block).
4. Outcome-free design quantities: the script is committed before its run.
5. Stop and report. The pilot needs the author's go.

## Addendum, 2026-10-08: points settled during the build

Three corrections and clarifications, recorded before the version-2 code is committed.
1. **Group clustering arithmetic.** Average-linkage distances are kept by the
   Lance–Williams update: the size-weighted mean of the merged clusters' distances. In
   exact arithmetic that equals the mean of the pairwise distances. Ties are taken at
   float64 equality, and broken by asset index as stated.
   - The literal rule (the mean recomputed at each step) is kept as
     `learn2.blocks.cluster_bruteforce`.
   - The two agree on untied inputs, which is tested. On inputs built to tie exactly, the
     two arithmetics can resolve a tie differently: 5 of 80 such synthetic cases.
   - **The definition is the incremental one.**
2. **The regime-only plant and the learner's states: a correction.** The note said the
   plant's regime equals the learner's state input on planted panels. That holds for the
   **vol** and **sum** states, which are built from the equal-weighted market, and a
   dollar-neutral plant cannot move that market. It does **not** hold exactly for the
   **dispersion** state, the cross-sectional SD of returns, which the plant moves
   slightly.
   - The same was recorded for the existing gated rule at `92f7ea1`: the correlation
     with the gate moved from 0.463 to 0.469.
   - A regime-only plant on a dispersion regime is therefore seen through a slightly
     moved state.
3. **The volume-conditioned plant.** The P column is demeaned **within the active assets**
   (those above the row's median of V_b). The inactive assets are exactly 0. The
   positions are then scaled to unit gross.

**And an observation from building the real-ETF groups.** The group rule (5 clusters,
groups under 3 merged) collapses on the real ETF data. On the last in-sample row it
leaves **2 groups, of 7 and 33 assets.** Average linkage isolates small outlying
clusters, which the merge step then absorbs. The distribution over all rows is reported
with the build. The rule is as the author specified, and it is not changed here.

## Design changes before the pilot, 2026-10-08 (author). No outcome has been read

These are **design changes**. No real-panel outcome, and no planted-panel outcome, has been
read: the only version-2 numbers so far are the smoke (cost only) and the null-only design
quantities (`ff0ea89`).

1. **Groups cluster on market-residual returns.** At row t, the window is the trailing 252
   real ETF row returns.
   - Each asset's return is replaced by its residual on the real market (SPY), r_u − β_t ·
     m_u. Here β_t is the asset's OLS beta fitted on that same window: one beta per
     window.
   - The correlation of those residuals feeds the same linkage, cut (5), merge (under 3)
     and tie rules as before.
   - The inputs file is re-pinned.
   - **If the rule still rarely reaches 4–5 groups, it is kept and reported. It is not
     tuned further.**
2. **Three trading-rate grids.** The fits do not depend on the rate, so the base view, and
   the menu where it is computed, are scored under:
   - **G1** {1.0, 0.3, 0.1}, as built;
   - **G2** {0.5, 0.2, 0.1};
   - **G3** {0.3, 0.1, 0.03}.

   Each grid's outcome-free base-view turnover and cost drag are reported beside version
   1's now, before the pilot.
3. **The dispersion-regime plant moving its own state slightly** (addendum, item 2) is
   accepted, and recorded.

## The version-2 pilot, 2026-10-08 (America/Chicago). EXPLORATORY: no claim rests on it

This section is committed alone, before the pilot script.

**The outcome-free figures it rests on** (`a570241`): the base view's turnover and cost drag
under each grid, on level-0 panels 696010–696012, with version 1 for comparison.

| | turnover per row | per unit gross | cost per year | cost drag (Sharpe) |
|---|---|---|---|---|
| G1 {1.0, 0.3, 0.1} | 0.127 | 0.184 | 0.0161 | 0.273 |
| G2 {0.5, 0.2, 0.1} | 0.077 | 0.113 | 0.0097 | 0.169 |
| G3 {0.3, 0.1, 0.03} | 0.045 | 0.072 | 0.0057 | 0.107 |
| version 1 | 0.164 | 0.164 | 0.0207 | 0.247 |

The re-pinned groups (`59fe966`, SHA-256 `3ff15481…6700`) give 4 groups on 2,947 rows, 3
on 1,279, 2 on 44 and 5 on 6, out of 4,276.

### Panels: seed block 697000–697999

The block was re-checked against every pre-registration: **NO COLLISION**.

**Planted:** 7 shapes × 50 seeds, each seed at levels 0.5, 1.0, 1.5 and 2.5 (one residual
draw and one set of rule features per seed).

| shape | seeds |
|---|---|
| U | 697000–697049 |
| corner | 697050–697099 |
| product | 697100–697149 |
| gated | 697150–697199 |
| lead-lag | 697200–697249 |
| volume-conditioned | 697250–697299 |
| regime-only | 697300–697349 |

**Level 0:** 100 panels, 697400–697499, at the registered cost, and the same panels at zero
cost.

**Seeds:**
- Each panel's tiers use its own seed.
- **The paired bootstrap** for the rules uses `default_rng(697999)`, B = 10,000.

### Streams and menus

**Single streams, each priced as one declared strategy** through the supplied-streams
tier (B = 1,000, block length by the class rule), each on its own scored window:
- version 2's base view under G1, G2 and G3 (all blocks, h = 5, market-neutral, always),
  from row 763;
- version 1 (ridge_stack at `fce5627`), from row 756;
- the plain ridge (version 1's control), from row 756.

**Beside them,** on the at-cost panels: the class tier (the fast kernel's class maximum
against the class null, B = 1,000, the whole window).

**The full menu, 294 views, under each grid,** is computed on 380 panels:
- the 100 level-0 panels, at cost and at zero cost;
- the first 20 seeds of each shape at levels 1.0 and 1.5: 280 panels.

**Menu streams** share one window, from row 778 (756 + 20 + 1 + 1). A menu's tier is the
joint-bootstrap maximum over its views' demeaned streams (B = 1,000, the class rule's
block length).

**The nested menus:**

| menu | views |
|---|---|
| base | 1 |
| information × horizon (market, always) | 21 |
| + neutrality (always) | 42 |
| + regime | 294 |

**The tiered scheme, per grid:** certified iff any of these holds:
- the base view's single-stream p < 0.02;
- the 42-menu maximum's p < 0.02;
- the 294-menu maximum's p < 0.01.

**Each shape's natural view, for R3, defined now:**

| shape | information must include | regime |
|---|---|---|
| U, corner, product | P | always |
| gated | P | vol_high (the rule's gate is the vol state above its expanding median) |
| lead-lag | X | always |
| volume-conditioned | P and V | always |
| regime-only | P | the drawn regime |

Horizon and neutrality are free. A winning view "matches" iff its information includes the
required blocks and its regime is the required one.

### Reads, once, in this order

**R1, level,** zero cost then at cost, on the 100 level-0 panels. It covers:
- each single stream;
- the menu maximum for the 21-, 42- and 294-view menus, under each grid (certified iff the
  best view's menu-tier p < 0.05);
- the tiered scheme, under each grid;
- the class tier, at cost only.

**A stream or scheme fails level iff the lower Wilson end of its rate exceeds 0.05.** At
n = 100 that is 10 or more certifications. A true rate of 0.123 or more is detected with
80% power, and a scheme exactly at 0.05 fails with probability 0.028.

**R2, power of the single streams,** by shape × level, pooled, fast and slow, with Wilson
intervals and cell counts, and the class tier beside them. Cells with fewer than 5 panels
are marked thin.

**R3, the menu, on the 280 panels, by shape** (and pooled), under each grid. Certification
rates of:
- (a) the base view alone at 5%;
- (b) the menu maximum over 21, 42 and 294 views at 5%;
- (c) the tiered scheme.

Also: which view wins (the menu maximum's view), and whether it matches the shape's natural
view.

**R4, descriptive,** planted panels against null:
- capture: population net and gross Sharpe of the base view's book over its window, as a
  share of the plant's;
- turnover and cost drag, raw and per unit gross;
- the share of refits with a penalty at a grid edge (planted panels, not only level 0);
- the robustness reading: the mean pairwise correlation of the nine variants' positions.

### Rules stated now, both branches

**Grid.**
- Among the grids whose base view holds level (R1, zero cost), the one with the **highest
  pooled certification rate at levels 0.5–1.5** (7 shapes × 50 × 3 = 1,050 panels) is
  carried forward. **Ties go to the slower grid** (G3 before G2 before G1).
- If no grid holds level, none is carried forward and version 1 stays.

**Replacement.** With the carried grid, version 2's base view **replaces version 1 iff**:
- its pooled rate at 0.5–1.5 over all seven shapes exceeds version 1's;
- the paired 95% interval for the difference excludes zero (B = 10,000, seed 697999); and
- the base view holds level.

**Otherwise version 1 stays.**

**Fairness flag (not a rule).** The same paired difference is computed on version 1's
original four shapes alone (600 panels). If its lower end is below −0.05, the report says
**version 2 wins only where the plant uses its new inputs, and the decision returns to the
author.**

**Menu pricing: descriptive only.** (a), (b) and (c) are reported side by side. **No scheme
is chosen by rule in this pilot.**

### Detectability, stated before the run

Paired difference in certification rate, 80% power, normal approximation. p01 is the share
of panels the comparator certifies and the candidate does not. The assumption is stated,
not estimated.

| comparison | n | p01 = 0 | 0.02 | 0.05 | 0.10 |
|---|---|---|---|---|---|
| replacement (7 shapes × 50 × levels 0.5–1.5) | 1,050 | 0.008 | 0.021 | **0.031** | 0.043 |
| fairness flag (4 original shapes) | 600 | 0.013 | 0.030 | 0.043 | 0.058 |
| R3, one shape (20 seeds × 2 levels) | 40 | 0.164 | 0.197 | 0.234 | 0.281 |
| R3, pooled | 280 | 0.027 | 0.049 | 0.068 | 0.089 |

- **R3 per-shape rates** have a 95% Wilson half-width of about 0.15 at a rate of 0.5
  (n = 40).
- **R2 cells** have about 0.13 (n = 50).
- **R3 by shape is therefore coarse.** Only differences of about 0.2 or more between
  schemes are detectable.

### Platform

- **The pilot runs on the box only,** with the Linux LightGBM pin (wheel SHA-256
  `d23e922a…ebb7`, installed `lib_lightgbm.so` `573d57e8…616a`).
- **The pinned inputs** are copied with their hashes checked on arrival:
  - the ETF P pin (`4b461070…b7ba`);
  - the re-pinned v2 inputs (`3ff15481…6700`).
- **Laptop and box numbers are not mixed.**

## The author's decisions after the version-2 pilot, 2026-10-08 (America/Chicago)

The pilot read (`fe7c7ca`) was accepted as printed. Version 2 did not replace version 1:
the difference was +0.013 [−0.010, +0.036], and the fairness flag fired. On that basis
the author decided:
1. **Version 1 stays the registered model** (ridge_stack at `fce5627`).
2. **The 294-view menu is not taken to registration.** On the 280 menu panels (grid G3),
   the menu maximum certified fewer panels than the base view alone:

   | scheme | certified, of 280 |
   |---|---|
   | 21-view menu maximum | 90 |
   | 42-view menu maximum | 106 |
   | 294-view menu maximum | 94 |
   | tiered scheme | 108 |
   | **base view alone** | **114** |

3. **The view levers are retained only for a later, behavioural agent cell.**
4. **Version 2 gets one further exploratory round.** Its design is to be proposed, and
   nothing is run before the author's go.

## The second version-2 pilot, 2026-10-09 (America/Chicago). EXPLORATORY: no claim rests on it

The author accepted the draft (`06c3c16`) with changes. This section is committed alone,
before any script.

### What changes from the first pilot, and why

1. **The L penalty grid becomes {1, 3, 10, 30}, for version 2 only.** Version 1 is
   unchanged.
   - **The reason:** in the refit records (`b5826e8`; laptop refits of 140 already-read
     pilot panels), version 2's L penalty sat at its largest value (3) in **87–95% of its
     refits on planted panels**, and 96–98% on null panels.
   - Its smallest value (0.3) was chosen in 0–3%.
   - Q, I and S are unchanged. Their smallest non-off value is chosen in at most 12% of
     refits, and "off" is a legitimate choice.
2. **The trading-rate grid is fixed at G3** {0.3, 0.1, 0.03}, as the first pilot carried
   forward.
3. **Two memory sets, scored from the same stored fits:**
   - **M1** = rolling 252, rolling 756 and expanding, as built;
   - **M2** = rolling 756 and expanding only.
   - **Why M2 is included:** on product plants at level 1.5, rolling 252 captured a
     median **0.055** of the plant, against **0.312** for rolling 756 and **0.512** for
     expanding (`b5826e8`).
   - **Caveat:** planted edges are constant, so a longer memory is favoured by
     construction. This says nothing about edges that decay.
4. **Per-refit records are stored this time:** penalties and stack weights for every
   refit of version 2 (per memory) and of version 1, and capture per memory setting. No
   later refit should be needed.

### Streams, cost arms, panels

**Streams, each as one declared strategy** (the supplied-streams tier, B = 1,000):
- version 2's base view (P, X, V; h 5; market; always) under G3 and the revised L grid,
  for memory set M1 and for M2;
- version 1;
- the plain ridge.

There is no menu and no class tier.

**Two cost arms, on the same panels.** The fits are shared; only the streams' costs
differ.
- **Registered:** 5 bps one-way, 50 bps a year borrow.
- **High-cost: both rates × 5.0,** so 25 bps one-way and 250 bps a year borrow.
  - The multiplier was set from a null-only quantity: version 1's median cost drag on the
    first pilot's 100 level-0 panels at registered cost was 0.197 Sharpe (`fe7c7ca`, R4),
    and 1.0 / 0.197 = 5.08, rounded to 5.0.
  - Version 1's median drag in the high-cost arm is reported as a check.

**Panels, on the seed block 698000–698999** (`seed_block_check`: NO COLLISION):
- **Planted:** 7 shapes × 50 seeds at levels 1.0 and 1.5, seeds 698000–698349, in the
  first pilot's shape order (U, corner, product, gated, lead-lag, volume-conditioned,
  regime-only; 50 seeds each).
- **Level 0:** 100 panels, 698400–698499, at the registered cost, the high cost and zero
  cost.
- **The paired bootstrap:** seed 698999, B = 10,000.

### Reads, once, in order

**R1, level, per cost arm:** each stream on the 100 level-0 panels, at zero cost and at
that arm's cost. A stream fails iff the lower Wilson end of its **zero-cost** rate
exceeds 0.05: at n = 100, 10 or more certifications.

**R2, power:** each stream by shape × level × arm, pooled, fast and slow. Cells with
fewer than 5 panels are marked thin.

**R3, descriptive:**
- capture, turnover and cost drag per arm and memory set;
- the L penalty's distribution under the revised grid, and the other blocks';
- capture by memory setting;
- version 1's median cost drag in the high-cost arm.

### Rules, per cost arm, both branches

1. **Memory set.** Among M1 and M2, those whose base view holds level are eligible. The
   one with the **higher pooled certification rate at levels 1.0 and 1.5** (700 panels) is
   carried forward, **with ties to M1.**
   - If neither holds level, none is carried forward, and version 1 stays in that arm.
2. **Replacement.** With the carried memory set, version 2's base view replaces version 1
   in that arm iff:
   - its pooled rate at 1.0–1.5 over all seven shapes (700 paired panels) exceeds
     version 1's, with a paired 95% interval (B = 10,000, seed 698999) excluding zero;
     and
   - it holds level.

   **Otherwise version 1 stays in that arm.**
3. **The fairness flag (not a rule):** the same paired difference on version 1's original
   four shapes (400 panels). If its lower end is below −0.05, the report says version 2
   wins only where the plant uses its new inputs, and the decision returns to the author.
4. **If the two cost arms disagree** on the memory set or on replacement, the report
   states both, and **the decision returns to the author.**

### Detectability, stated before the run

80% power, normal approximation; p01 is the share of panels version 1 certifies and
version 2 does not.

| comparison | n | p01 = 0 | 0.02 | 0.05 | 0.10 |
|---|---|---|---|---|---|
| replacement, per arm | 700 | 0.011 | 0.027 | **0.039** | 0.053 |
| fairness flag, per arm | 400 | 0.019 | 0.039 | 0.055 | 0.073 |

At n = 100, level detects a true rate of 0.123 or more, and one exactly at 0.05 fails
with probability 0.028.

### Platform, and the same box session

- **Box only,** with the Linux LightGBM pin and the v2 inputs pin (`3ff15481…6700`), both
  hash-checked, and a box smoke first.
- **In the same session, after the pilot is fetched and before the box stops:** the French
  holdout grading's step 0 (`2c0f25b`), as its commands set out
  (`docs/french_step0_box_commands.md`). It reads no holdout row.

## The second pilot's outcome, 2026-10-09. EXPLORATORY

The author accepted the read as printed. The raw outputs were committed before the read at
`4a0e621`; the read is at `9e4f6a7` (`runs/ml_v2_pilot2/2026-10-09/read.txt`).

**As printed:**
- **Level:** no stream fails. At zero cost: v2 M1 3/100, v2 M2 2/100, version 1 0/100,
  plain ridge 1/100.
- **The registered arm:**
  - memory set carried: **M2**;
  - "v2 base M2 - version 1 **+0.037 [+0.009, +0.066]** -> version 2 replaces version 1";
  - fairness +0.025 [−0.018, +0.068], no flag.
- **The high-cost arm (×5.0):**
  - memory set carried: **M2**;
  - "**+0.077 [+0.057, +0.097]** -> version 2 replaces version 1";
  - fairness +0.075 [+0.050, +0.102], no flag.
- **"the two cost arms agree".**

**The configuration carried forward** to a confirmation:
- version 2's base view: P, X, V; h 5; market-neutral; always;
- **memory set M2:** rolling 756 and expanding;
- **rate grid G3:** {0.3, 0.1, 0.03};
- **L penalty grid {1, 3, 10, 30};**
- everything else as built: Q {0.3, 1, 3, off}, I and S {1, 3, 10, off}, 3 embargoed
  folds, trees, and a non-negative stack.

**Caveats:**
- **This pilot is exploratory.**
- **Three settings were chosen on pilot results:** the memory set, the rate grid and the
  L grid. So the gain over version 1 measured here is **optimistic** for the
  configuration as chosen. A confirmation on fresh seeds is needed before any claim.
- **L still sits at its top value (30)** in 44–65% of version 2's refits on planted panels
  (by memory), and 68–72% on null panels. **The L grid is not to be widened again.**
- **Lead-lag certifications were lower** than in the first pilot: 9 of 50 at level 1.5 in
  the registered arm, against 22 of 50 under G3 in the first pilot. The seeds were
  different, so this is not a paired comparison.
