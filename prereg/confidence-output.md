# confidence-output: a graded confidence beside the verdict, and whether it is calibrated

**DRAFT, committed and not live, except two sections.**
- "Stage-1 secondary analysis" is **LIVE from 2026-10-04 (America/Chicago)**. It
  authorises that analysis's reader and its one run on `30ee870`'s file.
- **"V2 — LIVE" is LIVE from 2026-10-05 (America/Chicago)**, pre-registration only. It
  authorises the V2 cell on 620000–620999, together with the V1 and V3 readouts on
  that block.

Nothing else here authorises anything. The rest goes live only by a dated commit after
review.

## Question

The gate says PASS or FAIL at α. A user also wants to know how sure the gate is and
of what: a lower bound on the submission's Sharpe, a whole confidence curve, and a
plain "probability this makes money over five years". Each of these can be derived
from the replicates the gate already draws. **Are they calibrated?** Do the bounds
cover as often as they claim, is the class maximum's error distribution what the
null says, and do stated horizon probabilities match realized outcomes?

## Definitions, for one priced run

The run's **submitted score** is `S`, its in-sample net Sharpe, annualised. The
certifying (class) tier's replicates are `M_b`, b = 1..B: the class maximum of the
demeaned net Sharpe on replicate b, exactly as `p_class` uses them (B = 1,000).
Quantiles are `np.quantile(M_b, g)` with the default linear method, which is how the
stage-1 driver stored them.

1. **Deflated confidence** `C0 = 1 − p_class`, where
   `p_class = (1 + #{M_b ≥ S})/(B + 1)`.
2. **Lower bounds** `L_g = S − quantile_g(M_b)`, for g ∈ {0.90, 0.95, 0.99}.
3. **Confidence curve** `C(s) = 1 − (1 + #{M_b ≥ S − s})/(B + 1)`, on the fixed grid
   s ∈ {−1.00, −0.95, …, 3.00} (81 points, annualised Sharpe units). `C` is
   nonincreasing in s, and **`C(0) = C0` exactly**: the curve is the deflated
   confidence evaluated at every shifted bar, with the same `+1`.
4. **Replay-tier versions, audit only.** The same three quantities, with `M_b`
   replaced by the trigger-replay replicates `N_b`, the procedure's own statistic on
   each replicate (`p_trigger`'s replicates). They are reported beside the class
   versions and never instead of them, as the tier rule requires.
5. **Horizon readout** `P_H`, the stated probability that the realized net Sharpe
   over the next H years is positive, with **H = 5** to match the planted holdout
   (2018–2022, 1,257 trading days).
   - Read `1 − C(s)` as a distribution function over the submission's population
     Sharpe, discretised on the grid. Grid point `s_k` gets mass
     `C(s_{k−1}) − C(s_k)`. Mass below the grid goes on −1.00 and mass above it on
     3.00.
   - Then `P_H = Σ_k mass_k · Φ( s_k √H / √(1 + s_k²/(2·252)) )`.

   The Φ term is the probability that an H-year annualised Sharpe estimate is
   positive when the true Sharpe is `s_k`, under i.i.d. daily returns (the Lo 2002
   standard error).

## What each rests on, and its limits

**P7 (proposed here, not in `THEORY.md` yet): simultaneous lower bounds by inverting
the centred class maximum.** Let `D = max_{θ∈Θ} (Ŝ_θ − SR_θ)`: the largest estimation
error over the declared class, where `SR_θ` is each member's in-sample population
Sharpe. Suppose `P(D ≤ q_g) ≥ g`.
- Then `SR_θ ≥ Ŝ_θ − q_g` holds for **every** θ at once with probability at least g,
  and so for whichever member the search submits, however adaptively it was chosen.
  That is `L_g`'s coverage.
- `C0 = C(0)` is the confidence that the submission's population Sharpe exceeds 0.
- `C(s)` is the confidence that the submission's population Sharpe exceeds s.

**The route:**
- The demeaned stationary bootstrap's class maximum `M_b` estimates the law of `D`
  to first order. Demeaning each stream centres it at its own population mean.
- This is P3's construction, used for a confidence set rather than a test: the
  least-favourable null `SR_θ = 0` is replaced by centring at each `SR_θ`.
- The selected member's error is at most `D`. So, as in P2, the bound is
  conservative for any submission that does not carry the class's largest error.

**Limits, stated with the definitions:**
- **Stationarity.** Every quantity is about the in-sample population Sharpe of the
  process that generated the sample. `P_H` additionally assumes the next H years
  come from the **same** process. A regime change breaks `P_H` and not `L_g`
  (`costs-and-regime-change`: under a flipped β, the PASS − FAIL gap fell from +0.46
  to +0.08).
- **Not a posterior.** `C(s)` is a confidence curve. It carries no prior and does not
  say "the probability that SR > s given the data". `P_H` treats `1 − C` as if it
  were a distribution in order to integrate. It is a **stated** number whose only
  warrant is V3's reliability check, and it is labelled that way wherever it is
  printed.
- **Simultaneous, so conservative for a single member.** The bounds cover the whole
  class at once (the "deflated" in deflated confidence). For one submission they are
  predicted to over-cover. That is P2's direction, and V1 measures how far.
- **First order only.** The demeaned replicate drops the Sharpe ratio's own variance
  term (`SR²/2` per period). At an annual SR of 1.5 on daily data that term inflates
  the standard deviation by about 0.2%, which is negligible here and stated rather
  than assumed.
- **The class gap of P1 applies.** Bootstrap validity for maxima over 82,240
  correlated members rests on simulation evidence, not a theorem.
- **Net of the panel's registered costs**, and nothing else is modelled. `P_H` uses
  i.i.d. daily noise. Autocorrelated returns make its Φ term too narrow or too wide.

## Validation rules (to register)

### V1: coverage of `L_g`

- **Statement.** For each searcher, level and g: the share of runs whose submission's
  in-sample population Sharpe is ≥ `L_g`, with Wilson 95%.
- **One-sided, with both branches reported:**
  - **Fails low (liberal)** iff the upper Wilson end < g. A failure halts every
    confidence output on the affected tier until it is explained.
  - **Conservative** iff the lower Wilson end > g. This is predicted by P7 and P2,
    and is reported with its size, not as a failure.
  - Otherwise within tolerance of g.
- **Detectability**, the coverage shortfall detectable at 80% (one-sided 0.05):

  | n | g = 0.90 | g = 0.95 | g = 0.99 |
  |---|---|---|---|
  | 2,000 | 0.017 | 0.013 | 0.006 |
  | 1,000 | 0.024 | 0.018 | 0.009 |

- **Tightness, registered beside coverage** (added 2026-10-04). Per tier, row
  (searcher, or the class argmax on the class tier), level and g: the median and
  quartiles of the gap `SR_pop − L_g` between the submission's in-sample population
  Sharpe and its lower bound. Coverage says whether the bound holds; the gap says how
  much it gives away. Descriptive, with no rule. A bound can cover at 1.000 and still
  be too loose to use, and this is what shows it.
- **Replay tier:** the same, as audit.
- **Family:** per searcher × level × g × tier, reported in full. No family-wise pass
  rate is claimed. A fail-low triggers the one-shot replication on the next fresh
  block, as in `planted-edge`.

### V2: the calibration cell, on a fresh seed block

- **Statement.** Per panel and level, compute
  `D = max over all 82,240 members of (realized Sharpe − in-sample population Sharpe)`.
  The realized Sharpes come from the class pass, the population Sharpes from the
  closed form (`planted_panel.population_from_moments`). Set it against the null
  quantiles: `r_g = #{D ≤ quantile_g(M_b)}/n` for g ∈ {0.90, 0.95, 0.99}, and the PIT
  value `u = #{M_b < D}/B`.
- **The exactness rule.** It names P7's route, the demeaned bootstrap's maximum
  estimating the law of `D`.
  - **Exact** iff the Wilson 95% interval of `r_g` contains g, per level and g.
  - **Fails low** iff the upper end < g. P7's premise then fails on this design;
    every `L_g`, `C0` and `C(s)` is withdrawn pending a cause.
  - **Conservative** iff the lower end > g.
- **The predicted direction, registered: slightly conservative**, for a reason
  specific to this design.
  - The planted DGP holds X fixed and draws only the residual. The deterministic,
    X-driven part of each member's per-period return (the planted overlap less costs)
    therefore does not vary between draws.
  - The stationary bootstrap resamples time, so it also varies that part. Its
    replicates are slightly wider than `D`'s sampling distribution.
  - The size is set by that part's share of each member's per-period variance. It is
    small at level 0, where it is costs only, and grows with the planted scale.
  - The `SR²/2` term pushes the other way and is about 0.2% at most.
- **Secondary:** a KS test of `u` against uniform, per level, descriptive.
- **The read stops after V2 on any fail-low** (confirmed 2026-10-04). If any V2 test
  fails low, P7's premise fails on this design and every confidence output is
  withdrawn pending a cause, so V1 and V3 are not printed. This mirrors stage 1's
  stop on rule 1 (`experiments/confidence_cell_read.py`).
- **The live marker is the line `## V2 — LIVE`** (confirmed 2026-10-04). The
  registered run (`experiments/confidence_cell.py` on 620000–620999) refuses unless
  this file contains it, so V2 can only run after its own dated live commit.
- **Design:**
  - **1,000 fresh panels on 620000–620999, at levels 0, 1.0 and 1.5 only**, on the
    pinned X, B = 1,000. This uses the same generator and the same class pass as stage
    1. Level 0.5 is dropped for cost; its power was 0.0484, so it adds few certified
    submissions to V1 or V3.
  - **Seed check, 2026-10-04 (America/Chicago):** `experiments.seed_block_check
    --exclude prereg/confidence-output.md --ranges 620000-620999,981000-981999` scanned
    36 files, 109 explicit ranges and 8 master seeds (5,000 draws each): **NO
    COLLISION**. The smoke seeds first proposed, 980191–980381, **collided** with 7.5's
    registered smoke block 980000–980999 (`prereg/planted-edge.md`). They are replaced
    by this file's own smoke block, **981000–981999**, of which the smoke uses
    981000–981190.
  - The six registered searchers also run (realized, with their trigger-replay nulls
    as audit), so that V1 and V3 are measured **confirmatorily** on the same block.
  - Each record stores `D`, `u`, the class-tier `M_b` and replay-tier `N_b` on the
    81-point grid, and `C(s)`, `L_g`, `C0` and `P_5` per searcher.

### V3: reliability of the horizon readout, descriptive

- Per submission: `P_5`, against whether its **realized holdout Sharpe** is > 0. The
  holdout is the planted process continued into 2018–2022.
- Bin `P_5` into deciles. For each bin, give the realized frequency with its Wilson
  interval, and give the Brier score overall. Report all submissions and certified
  ones separately, per level.
- **No pass/fail rule.** A reliability diagram on one design is not a calibration
  claim for real markets. Two further figures are reported beside it:
  - the in-sample-to-holdout shift in **population** Sharpe (`truth.holdout −
    truth.in_sample`), which measures how stationary even the planted design is;
  - the same reliability computed against the holdout **population** Sharpe > 0, to
    separate noise from drift.

## Stage-1 secondary analysis: V1, class tier, on data already read — LIVE, 2026-10-04 (America/Chicago)

**SECONDARY, ON DATA ALREADY READ.** This section is separate from the rest of the
file so that it can go live on its own.
- **Data:** `runs/planted_edge_scripted/draws.jsonl` at `30ee870` (2,000 seeds,
  600000–601999, SHA-256 `cd7e9f8f…259ce1`), read once for stage 1 at `8660508`.
  None of the quantities below was computed in that read.
- **Rows:** the six registered searchers, plus the **class argmax**, at levels 0, 0.5,
  1.0 and 1.5. That is 7 rows × 4 levels × 2 values of g = **56 tests**.
- **Definitions, per run:**
  - `L_g = S − q_g`. `S` is the searcher's `score`, or `class_max` for the argmax row.
  - `q_g` is the stored `null_max_q`: `q_0.95 = null_max_q["0.05"]` and
    `q_0.99 = null_max_q["0.01"]`, each `np.quantile(M_b, 1 − α)` as the driver
    stored it.
  - **Covered** iff the in-sample population Sharpe (`truth.in_sample`, or
    `class_argmax_truth.in_sample`) is ≥ `L_g`.
  - A run with no submission (support `None`) is excluded and counted.
- **Rule, per row, level and g:** k covered of n, the rate, and its Wilson 95%.
  - **Fails low iff the upper Wilson end < g.**
  - **Conservative** iff the lower end > g.
  - Otherwise within.
  - Detectable shortfall at n = 2,000 and 80%: 0.013 (g = 0.95), 0.006 (g = 0.99).
- **Predicted:** conservative on every searcher row (P7 with P2). The argmax rows are
  nearest g, since the class argmax is the member most likely to carry the class's
  largest error.
- **What a fail-low does here:** it is reported, and it becomes a registered
  prediction that V2's confirmatory V1 also fails low on that row. **No replication is
  run off this analysis.** It is secondary, and its data are already read.
- **No family-wise pass rate is claimed.** The 56 tests share panels and replicates.

## What the existing stage-1 file can and cannot give

`runs/planted_edge_scripted/draws.jsonl` (`30ee870`, read at `8660508`) stores, per
searcher and level:
- `score`, `p_class`, `p_trigger`, and `truth.in_sample` and `truth.holdout`;
- `holdout_realized`;
- **of `M_b` only** its 0.95 and 0.99 quantiles (`null_max_q`) and its mean.

| readout | from the stage-1 file? |
|---|---|
| `C0`, both tiers | **yes**: `1 − p_class` and `1 − p_trigger` |
| **V1, class tier, g = 0.95 and 0.99** | **yes**, as a **declared secondary analysis**: `L_g = score − null_max_q`, against `truth.in_sample`. The class argmax rows can be computed too. |
| V1 at g = 0.90 | **no**: the 0.90 quantile was not stored |
| V1, replay tier | **no**: only `p_trigger` was stored, not the `N_b` quantiles |
| V2 | **no**: `D` needs every member's realized and population Sharpe, which were not stored |
| V3 | **no**: `C(s)` needs the distribution of `M_b`, and two quantiles and a mean do not give it |

**The secondary analysis is declared, not confirmatory.** The stage-1 file has
already been read. The V1 quantities were not computed in that read, but they are
computed on read data after the fact, and are labelled that way. The confirmatory V1
is V2's block.

## Cost

- **Smoke plan, not run:** 191 panels on 981000–981190, at levels 0, 1.0 and 1.5,
  191 workers, on a c7a.48xlarge, **cost only**.
  - One wave takes about 890–940 s: three levels, each a 243 s class pass plus 50 s of
    trigger nulls, as measured in stage 1's box smoke.
  - With boot, that is **about 20 minutes, about $3.5**.
  - It checks memory: the stored grids add little, and peak RSS should stay near stage
    1's 1,035 MB per worker.
- **V2 projected from that measurement:**
  - **mean throughput:** 1,000 seeds × ~890 s / 191 workers ≈ **1.29 h, about $13**;
  - **upper bound:** 6 waves × ~940 s ≈ **1.57 h, about $15.5**;
  - plus the fetch window.
- **The threshold rule as in stage 1:** the mean projection decides, with the upper
  bound reported beside it. No seat cost.

## Build items, before the live commit

1. The confidence fields in the verdict and in `price_runs`' `class_p`: `C0`, `L_g`,
   `C(s)` and `P_5`, both tiers.
2. The V2 driver and its reader, tested on synthetic files.
3. Tests:
   - `C` is nonincreasing on the grid;
   - `C(0) = C0` exactly, both tiers;
   - `L_g` equals the quantile arithmetic;
   - `P_5` matches a direct numerical integration;
   - the V2 driver's class pass equals `planted_edge.run_level`'s on a synthetic base.

## V2 — LIVE, 2026-10-05 (America/Chicago)

**Only V2 goes live**, together with the V1 and V3 readouts measured on its block.
The rest of this file's draft stays a draft. This commit is pre-registration only.

**What goes live:**
- **Design.** Planted panels from `environments/planted_panel.py`.
  - The features are the pinned X, SHA-256
    `4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`, shape
    (4276, 40, 40), refused on mismatch with no rebuild.
  - Returns and costs come from the 40 in-sample CSVs (combined SHA-256
    `ce4bc21e64b47d09714308560fa25f39540714dcfba6fb89ab3ee2d34e69df2a`).
  - The residual is resampled in joint-time blocks of length 7.
  - Six registered scripted searchers, class-capped to `SubsetClass(3, signed=True)`
    (82,240 members).
- **Levels: 0, 1.0 and 1.5.**
- **Seeds: 620000–620999.** 1,000 panels, each at all three levels. Checked
  2026-10-04 with `experiments.seed_block_check`: no collision.
- **B = 1,000** for both tiers, on identical replicates per panel and level.
- **V2** (the exactness rule), **V1** (coverage of `L_g` for g in {0.90, 0.95, 0.99},
  both tiers, with the tightness readout) and **V3** (reliability of `P_5`), exactly
  as written in the sections above.
- **The read stops after V2 on any fail-low.**

**Registered now:**

| item | value |
|---|---|
| seeds | **620000–620999** |
| smoke | **981000–981999**, cost only; the smoke uses 981000–981190 |
| levels | **0, 1.0, 1.5** |
| B | **1,000**, both tiers |
| g | 0.90, 0.95, 0.99 |
| grid | s = −1.00, −0.95, …, 3.00 (81 points); H = 5 |
| code, by file | `experiments/confidence_cell.py` `a64ca42`; `experiments/confidence_cell_read.py` `ec6d8ae`; `quixote/confidence.py` `93393f7`; `environments/planted_panel.py` `c5e3860`; `experiments/planted_edge.py` `87b70e2` (only `StreamCache`, `_searchers`, `_sharpe`, `_sharpe_rows` and `peak_rss_mb` are imported); `environments/class_table.py` `6e7f538`; `estimator/bootstrap.py` `063416a`; `searchers/meta_adaptive.py` `761e64d`; `experiments/_resume.py` `d8fb254` |
| launch | `cloud/run.sh` `8e923c5` (exact-match tmux targets); `cloud/wait_fetch_stop.sh` `6f55a07` (results fetched before the stop) |
| platform | x86_64, EC2 c7a.48xlarge (`i-0e0c1484de3c755ad`), shutdown behaviour **Stop**. Every record carries its platform, and the launch writes the commit hash to the log. |
| workers | **191** |

**Box smoke, the sizing measurement:**

| item | value |
|---|---|
| panels | 191 (981000–981190), all three levels, B = 1,000 |
| run | 2026-10-05, 22:18–22:34 UTC, at `3737147`; records `517f027` |
| per seed, three levels | wall mean **900 s** (median 900, max 934) |
| peak RSS per worker | **1,037 MB** |
| projected for 1,000 seeds, **mean throughput** | **1.31 h, $12.89** at $9.85/h |
| projected, **upper bound** (6 rounds × the slowest seed) | **1.56 h, $15.33** |
| against the $25 threshold | **under: $12.89 against $25** |

**The cost threshold is $25 on the mean-throughput projection.** The upper bound is
reported beside it and decides nothing. **If the mean projection exceeds $25, the run
does not launch.** It stops and is reported, and no lever (fewer seeds, a smaller B,
fewer levels) is applied automatically. The draft's projection was about $13 (mean)
and about $15.5 (upper).

**Before the read:**
1. The results (`runs/confidence_cell/draws.jsonl`) and the run's log are fetched and
   committed.
2. That commit is checked for exactly 1,000 complete lines on 620000–620999, with no
   truncated line, without opening or summarising any rule quantity.
3. **The reader is pinned to one exact commit: `experiments/confidence_cell_read.py`
   at `ec6d8ae`.** It is committed, and tested on synthetic files in the results'
   format, before it opens the results.
   - The hash is fixed in this live commit. If the reader changes before the live
     commit, this line is updated to the new hash in the live commit itself, and never
     afterwards.
   - The read runs only if the working tree's reader is byte-identical to that
     commit's: `git diff --quiet ec6d8ae -- experiments/confidence_cell_read.py`.
   - It refuses anything but 620000–620999 at three levels of six searchers.

The read cites both commits.

**The read, once, after all 1,000 seeds, in this order:**
1. **V2**, per level and g. If any test fails low, the read stops there: every `L_g`,
   `C0` and `C(s)` is withdrawn pending a cause, and V1 and V3 are not printed.
2. Otherwise **V1**: the class tier with the argmax rows, then the replay tier as
   audit, each with tightness.
3. Then **V3**.

The output is committed as `runs/confidence_cell/read.txt`.

## V2 — run record, 2026-10-05 (America/Chicago): the first launch did not start; the relaunch ran

**First launch, 2026-10-05 23:41 UTC: nothing ran.** The V2 flag was set on the
session-level chain (`chain.sh`). The chain's `git pull` on the box then failed: the
smoke files committed at `517f027` collided with the box's own untracked copies of
them. The chain ended at 23:44:14 UTC **without starting V2**, so no registered seed
was touched. Its log is `runs/confidence_cell/chain_first_attempt.log`.

The four colliding files were byte-identical to the committed ones (SHA-256 checked),
and were moved aside on the box, not deleted. The box's self-stop was cancelled
before it fired.

**Relaunch, 23:52:09 UTC, under the same go:** V2 alone, at the live commit `697bef8`,
with its own self-stop and the laptop fetch-then-stop. **Exit 0.** All 1,000 seeds on
620000–620999 are complete (checked by seed count only). The results and the log are
committed unread with this note. Nothing differs from the registered run apart from
the session it ran in.

## V2 read — 2026-10-05 (America/Chicago). CLOSED

**Read once** by the pinned reader (`experiments/confidence_cell_read.py` at `ec6d8ae`,
byte-identical, checked before the run), on the results committed before any read
(`0edab26`: 1,000 seeds, 620000–620999, SHA-256 `d762314a…6537357`). The run was at the
live commit `697bef8`; its first launch did not start, as recorded under "V2 — run
record". The output is `afdcb53` (`runs/confidence_cell/read.txt`). Nothing below goes
beyond that file.

**V2, the exactness rule: 8 EXACT, 1 CONSERVATIVE, none fails low.**

| level | g = 0.90 | g = 0.95 | g = 0.99 |
|---|---|---|---|
| 0 | 0.9250 [0.9070, 0.9397] **CONSERVATIVE** | 0.9530 [0.9381, 0.9645] EXACT | 0.9870 [0.9779, 0.9924] EXACT |
| 1.0 | 0.9110 [0.8917, 0.9271] EXACT | 0.9470 [0.9313, 0.9593] EXACT | 0.9840 [0.9742, 0.9901] EXACT |
| 1.5 | 0.9070 [0.8874, 0.9235] EXACT | 0.9460 [0.9302, 0.9584] EXACT | 0.9840 [0.9742, 0.9901] EXACT |

The read did not stop. The predicted direction was "slightly conservative"; one test
of nine is conservative, and the others contain g.

**V1, coverage of `L_g`, on 1,000 submissions per row.**
- **Class tier:** every searcher row is conservative, with coverage 0.999–1.000 at
  every level and g. **Tightness:** the median `SR_pop − L_g` is +0.67 to +0.79 at
  level 0, +0.86 to +1.09 at 1.0 and +0.90 to +1.13 at 1.5.
- **The class-argmax rows** cover 0.981–1.000. They are conservative except level 0
  at g = 0.99 (0.9960, within). Their median gap is narrower: +0.41 to +0.61 at level
  0, and +0.76 to +1.03 at the planted levels.
- **Replay tier (audit):** every row is conservative except random-extend-while-
  improving at 0.99 on levels 0 and 1.0 (0.9940 and 0.9960, within). Coverage is
  0.947–1.000; the median gap is +0.36 to +0.67 at level 0 and +0.53 to +0.89 at the
  planted levels.

**V3, reliability of `P_5` (class tier), descriptive.**
- **Level 0:** the Brier score against the realized holdout is 0.3089. Observed shares
  positive are 0.32–0.39 in every bin with more than 4 submissions, against mean P_5
  of 0.058–0.538. No submission is certified at level 0.
- **Level 1.0:** Brier 0.2563 over all submissions and 0.0349 over the 1,145 certified.
- **Level 1.5:** Brier 0.1869 over all and 0.0203 over the 2,619 certified.
- At the planted levels the observed share exceeds the bin's mean P_5 in every bin.
- The mean shift from in-sample to holdout population Sharpe is −0.0023, +0.0319 and
  +0.0452 by level.

**Limits, stated with the result:**
- **The 0.99 intervals contain g only barely.** The upper ends are 0.9924 at level 0
  and 0.9901 at 1.0 and 1.5. Coverage of the class maximum's error at 0.99 sits at the
  low edge of exact.
- **KS rejects uniformity of the PIT at every level** (D = 0.0810, 0.0680, 0.0630;
  p = 0.0000, 0.0002, 0.0007). Mean u is 0.4548–0.4706, below 0.5. The bootstrap
  maximum's distribution is not exactly the law of D, even where the three
  registered quantiles pass.
- **`P_5` on the class tier understates at every level, and is a floor, not a
  calibrated probability**, for the outcome it is defined on: a realized 5-year
  holdout Sharpe above 0.
  - In every bin with more than 4 submissions, at every level, the observed share is
    at or above the bin's mean P_5.
  - The single exception is level 0's top bin: mean P 0.605, 0 of 4.
  - **Against the holdout population Sharpe at level 0 it overstates.** Every bin there
    observed 0, against mean P_5 of 0.058 to 0.605, because every population Sharpe at
    level 0 is negative. "Floor" therefore describes the realized outcome, not the
    population sign.
- Scripted searchers only, on synthetic returns over the real features, and the
  holdout is the planted process continued. This is not a regime change.

**Cost:** 1,000 seeds in about 1 h 26 min of wall time (23:52–01:18 UTC) at 191
workers, about $14. The smokes and the idle gate came to about $17 more.

**V2 is closed.** The rest of this file's draft stays a draft.

## Replay-tier V3 — a declared secondary analysis on data already read — LIVE, 2026-10-05 (America/Chicago)

**SECONDARY, ON DATA ALREADY READ.** The V2 read (`afdcb53`) printed V3 for the class
tier only. This registers **V3 for the replay tier's `P_5`** (`conf_replay`) on the same
file (`0edab26`, SHA-256 checked):
- the same bins (deciles of P_5);
- the same outcomes (realized holdout Sharpe > 0, and holdout population Sharpe > 0);
- the same subsets (all submissions, and those certified by the class tier,
  `p_class < 0.05`);
- the Brier score;
- per level.

**Descriptive, with no rule.** Its reader is committed and tested on synthetic files
before it opens the results, and runs once. This section authorises that analysis
alone.
