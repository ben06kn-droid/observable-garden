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
