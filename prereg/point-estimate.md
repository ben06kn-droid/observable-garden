# A point estimate beside a certified verdict — DRAFT, NOT LIVE

**Status: DRAFT (2026-10-06, America/Chicago).** Nothing in this file is live. No seed
in it has been run, and no smoke has been done. It goes live only by its own dated live
commit, after the smoke and with every `[GAP]` resolved.

**Question.** Among certified submissions, does a bootstrap bias correction **matched to
the search procedure** estimate the submission's true Sharpe without overstating it?
And is it more accurate than the raw score (E0) and than halving (EH)?

**Where it comes from.** The exploratory note `prereg/estimators-exploratory-2026-10-06.md`
(output `6726871`, reading `4ddfc23`). On 100 design panels per level, EBs was near-unbiased
for extend-while-improving at every level. EB was near-unbiased for the class argmax at
the planted levels. EB applied to a non-exhaustive searcher read low. Those are
hypotheses, and this cell tests them on fresh seeds, conditional on certification. The
conditional tabulation the note's addendum defines (`8c933a3`) has not been run.

## Prior art. Nothing here is a new method

- **The bootstrap estimate of bias**, subtracting the mean over resamples of (resampled
  statistic minus original statistic), is textbook: Efron & Tibshirani (1993), *An
  Introduction to the Bootstrap*, ch. 10, "Estimates of bias" (Springer/Chapman & Hall;
  DOI 10.1007/978-1-4899-4541-9).
- **Replaying the whole data-analysis procedure on each resample**, so that the
  selection step's own variability enters the bootstrap, is Faraway (1992), "On the
  Cost of Data Analysis", *Journal of Computational and Graphical Statistics* 1(3),
  213-229 (DOI 10.1080/10618600.1992.10474582).
- EB is the first applied to a class-maximum selection, and EBs is the second applied
  to a scripted searcher. **This draft claims no new method.** What it would measure is
  how these known corrections behave, conditional on this gate's certificate, on these
  panels.

## Definitions, by reference to the code at `b2e3a40`

All are computed in `experiments/estimators_2026_10_06.py`, `level_pass`, exactly as
committed at `b2e3a40`. Per panel and level:

- **S(m)** is the member's realized annualised net Sharpe from the kernel's streams.
  **S\*_b(m)** is its Sharpe on stationary-bootstrap replicate b of the **un-demeaned**
  stream, using the class null's own index draws (B = 1,000).
- **The class null** is the centred replicate Sharpe. `M_b` is its maximum over the
  class, and `p_class = (1 + #{M_b >= S}) / (B + 1)`.
- **E0 = S** and **EH = 0.5 S**.
- **EB = S - mean_b [S\*_b(m_b) - S(m_b)]**, where m_b is the argmax of S\*_b over the
  class.
- **EBs = S - mean_b [S\*_b(m_b^s) - S(m_b^s)]**, where m_b^s is the submission of the
  **searcher's own procedure replayed on replicate b**. That is the searcher's
  `_search` on S\*_b with `meta_steps` equal to its realized number of moves, as
  `planted_fast.run_levels` replays it for the trigger null.
- **Roles.**
  - **EBs is the replay-tier estimate**: it needs the procedure to be replayable.
  - **EB is the fallback when no replay exists**, for example a bracketed or
    undecidable agent run.
  - **EB reads low for a non-exhaustive searcher.** It corrects for the class maximum's
    selection, which is larger than a partial search's. The exploratory run found
    -0.097 to -0.178 for extend-while-improving (`4ddfc23`, c).
  - For the class argmax, the search is the exhaustive maximum, so EB *is* its
    procedure-matched estimate.
- **Naming, stated so it is not misread.** "Replay-tier estimate" names EBs's role,
  not its arithmetic. EBs is computed on the un-demeaned replicates drawn with the
  class null's index draws. It does not use the replay tier's centred null replicates.

## Display rule

**The estimate is reported only beside a certified verdict.** It is never shown beside
an uncertified one, and no certificate is ever conditioned on it.
- **Certified** means certified by the **class tier at alpha = 0.05**, the certifying
  tier in 7.5. `[GAP: whether a replay-tier certificate also licenses display.
  Proposed: no. The class tier conditions every rule below, and conditioning on the
  replay tier's verdict is reported as a secondary readout.]`
- The displayed estimate is:
  - EBs where the procedure replays;
  - otherwise EB, labelled "reads low for a non-exhaustive search".

## The confirmatory cell

- **Seeds.** `[GAP: n per level. Proposed 2,000, the block 670000-671999]`, with the
  one-shot **replication block 672000-673999**. Both were checked on 2026-10-06 against
  every pre-registration, live and removed (`experiments.seed_block_check --ranges
  670000-671999` and `672000-673999`): **NO COLLISION**. Index i is seed 670000 + i at
  every level, so the levels share each seed's residual draw.
- **Panels:**
  - `environments/planted_panel.py` on the pinned X (SHA-256
    `4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`);
  - levels 0, 0.5, 1.0 and 1.5;
  - B = 1,000.
- **The fast kernel** (`environments/planted_fast.py`) is used. Its equivalence to the
  registered path `planted_edge.run_level` is tested in three places:
  - `tests/test_planted_fast.py` on the synthetic base, 3 seeds x 3 levels: streams to
    1e-12 relative, Sharpes to 1e-10, and
    `test_run_levels_equals_run_level_on_every_level`;
  - on the pinned X, design seeds 640060-640062 at levels 0, 1.0 and 1.5, B = 1,000:
    largest difference 3.3e-16, with argmax, supports, move counts and both p-values
    identical (ROADMAP, "the factorised kernel");
  - reproducing stage 1's stored class max, null mean and extend-while-improving
    submission on seed 600000 at all four levels, inside both of today's exploratory
    runs (`4d0c7e1`, `6726871`).

  The cell repeats that last check at start and **stops on any difference above
  1e-9**.
- **Searchers:**
  - **the class argmax** (estimate EB);
  - **every scripted searcher of 7.5 stage 1**, each estimated by its own EBs:
    `stop-when-cleared`, `extend-while-improving`, `cleared-restart`,
    `lookahead-stop-when-cleared`, `random-extend-while-improving` and
    `second-best-while-improving` (`searchers.meta_adaptive.registered_71`, through
    `planted_edge._searchers`).

  Stage 1 found three of them (stop-when-cleared, cleared-restart and
  lookahead-stop-when-cleared) near-identical. All six run, every rule is read per
  searcher, and the dependence is stated with the result.
- **Per submission:** S, p_class, E0, EH, EB, EBs (searchers), in-sample SR_pop, and
  holdout SR_pop (`planted_panel.truth`). **Every per-panel row is saved**, unlike
  `b2e3a40`.

## Rules

**The estimate under test:** EB for the class argmax, and EBs for each searcher.
**The primary target** is the holdout SR_pop: the submission's exact population Sharpe
on the holdout, with no per-run sampling noise. In-sample SR_pop is reported beside it.
**Each rule is read on certified submissions only**, per submission type and planted
level. Level 0 is discussed under detectability.

**R1 (no overstatement, one-sided).** For each certified submission,
`e = estimate - holdout SR_pop`.
- **The rule fails high iff the lower end of the one-sided 95% interval for mean(e)
  exceeds the margin.** The interval is a t interval, with a percentile bootstrap over
  panels reported beside it.
- **The margin:** `[GAP: margin. Proposed +0.10 Sharpe]`. The reasons:
  - it is about 0.4 of the exploratory unconditional RMSE of EB and EBs (0.24-0.29);
  - it is a fifth of the step between adjacent planted levels (0.5);
  - it is above the smallest detectable overstatement at the proposed n (see below).
- **Passes:** the estimate does not overstate by more than the margin among certified
  submissions. Reported with the upper end of the interval as the largest
  overstatement not ruled out.
- **Fails high:** a one-shot **replication on 672000-673999**, with the same submission
  type, levels and settings.
  - **Fails again:** the estimate overstates beside a certificate. It is not displayed
    for that submission type, and the conditional bias is reported with its interval.
  - **Replication holds:** reported as one failure of two.

**R2 (accuracy, paired by panel).** For each certified submission,
`d = (estimate - holdout SR_pop)^2 - (E0 - holdout SR_pop)^2`, and the same with EH in
place of E0.
- **The rule passes at a level iff the upper end of the one-sided 95% interval for
  mean(d) is below `[GAP: margin. Proposed 0]`, for both comparisons.** A margin of 0
  means a lower RMSE with confidence, not merely a lower point estimate.
- It must pass at each of 0.5, 1.0 and 1.5. That is an intersection-union test, so the
  conjunction needs no multiplicity adjustment.
- **Passes:** the estimate is more accurate than both the raw score and halving beside
  a certificate, at every planted level.
- **Fails** at a level or against one comparator: reported, with the paired difference
  and its interval, as "not shown to be more accurate than E0 (or EH) at level x".
  Display is then not argued on accuracy at that level; R1 still governs whether it is
  shown at all.
- **Stated in advance:** unconditionally, EH had the lowest RMSE at level 0.5 in the
  exploratory run (`6726871`):
  - class argmax: 0.239 against EB's 0.262;
  - extend-while-improving: 0.204 against EBs's 0.250.

  **The R2 comparison against EH at level 0.5 may fail.** Whether conditioning on the
  certificate changes that is what task 2's tabulation would show; it has not run.

**R3 (procedure match; the predicted sign only).** **EB applied to a non-exhaustive
searcher is biased low**: mean(EB - SR_pop) < 0, for every scripted searcher, at every
level, against both targets. It is reported on all panels and on certified panels.
- **Holds** (negative): EB is a conservative fallback for those searchers, and its
  display label stands.
- **Fails** (non-negative) for a searcher or level: EB is not shown to read low there,
  and the fallback label is revised before any live use. Reported with the bias and
  its interval.

**What is reported in every case:**
- the full per-submission, per-level table;
- the per-panel rows;
- the number certified;
- the unconditional figures beside the conditional ones.

## Detectability at the planned n

The smallest overstatement R1 detects (one-sided 0.05, 80% power) is
`2.486 sigma_c / sqrt(n_c)`, where `n_c` is the number certified and `sigma_c` is the
spread of `e` among certified submissions.
- **sigma_c:** `[GAP: the conditional spread from task 2, which does not exist yet.
  b2e3a40 saved no per-panel rows (8c933a3)]`.
- **Placeholder sigma = 0.25.** This is the unconditional RMSE of EB and EBs, whose
  bias is near zero (`6726871`). **Labelled:** conditioning on certification may change
  it in either direction.
- **n_c** is projected from stage 1's class-tier certification rates on 2,000 panels
  per level (`30ee870`, already read). The class argmax's count compares its score with
  the null's 95% quantile, because its p-value is not stored there.

| level | searchers certified of 2,000 | smallest detectable | class argmax | smallest detectable |
|---|---|---|---|---|
| 0 | 0 | none | about 1 | none |
| 0.5 | 80-122 | 0.056-0.069 | about 412 | 0.031 |
| 1.0 | 333-478 | 0.028-0.034 | about 1,400 | 0.017 |
| 1.5 | 820-952 | 0.020-0.022 | about 1,973 | 0.014 |

- **At level 0.5, 100 panels say nothing.** That is the exploratory run's n: the
  searchers certify 4-6 of 100, so sigma_c / sqrt(n_c) is above 0.1 and the smallest
  detectable overstatement is above 0.25. At 1,000 panels, the searchers' 40-61
  certified give 0.080-0.098, at the proposed margin itself. **Hence the proposal of
  2,000 panels per level**, which puts every searcher's smallest detectable
  overstatement at 0.5 (0.056-0.069) below the 0.10 margin.
  - Level 0.5 could instead be dropped from the rules and kept as descriptive, with
    rules at 1.0 and 1.5 only. That would allow 1,000 panels. `[GAP: proposed to keep
    0.5 at 2,000 panels]`.
- **At level 0 essentially nothing is certified at any feasible n.** Stage 1 had 0 of
  2,000 for the searchers and about 1 for the argmax. R1 and R2 are unreadable there and
  are reported with n_c. Level 0 enters only R3 and the unconditional readout.
- **R2's detectability** depends on the spread of the paired squared-error differences,
  which only per-panel rows give: `[GAP: from task 2]`.

## Cost (no smoke yet; re-measured by the smoke before the live commit)

- **Per seed-level:** about 41.5 CPU-s for the pass and extend-while-improving's
  replay. That is measured: 16,610 CPU-s over 400 seed-levels, c7a.48xlarge, `6726871`.
  The other five searchers' replays add roughly 33-52 s per level, from the trigger-
  replay nulls measured for all six on the laptop (ROADMAP, the factorised kernel).
  That is **about 85 CPU-s per seed-level, about 340 per seed** over four levels.
- **The box** (c7a.48xlarge, 192 vCPU, 369 GB):
  - 2,000 seeds is about 190 CPU-hours, about **1 hour** of compute at ~190 workers;
  - plus about 15 minutes of boot, pull and the one-off kernel table build;
  - **about $12** at $9.85/h;
  - memory is not a constraint (about 0.35 GB per worker for S\*).
- **The laptop** (8 GB) is memory-bound. Today's laptop runs made about 1.2 CPU-minutes
  of progress per wall minute on 2 workers, which is about **160 hours** for 2,000
  seeds. The laptop is for the smoke and the reader only.
