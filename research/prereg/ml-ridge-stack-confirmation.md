# ridge_stack confirmation: a registration, 2026-10-07 (America/Chicago)

**Status: LIVE.** The author approved this text, with edits a–f, on 2026-10-07. It is
committed alone, before any code for this test is written or run.
- Amendments are append-only and dated.

**Where it comes from.** The exploratory pilot (`prereg/ml-pipeline-exploratory-2026-10-07.md`;
outcome at `85f293a`) carried ridge_stack forward under its registered rule. This
document would test one predictor, named in advance, on fresh panels.

## 1. The predictor

**ridge_stack, exactly as at commit `fce5627fb53e5551aa8768a770aba3ce73ef8fb7`.**
- **The pinned files**, with blob hashes at that commit:

  | file | blob |
  |---|---|
  | `learn/ridge_stack.py` | `2c09b25701038964c97a193f66a5203f99bf0915` |
  | `learn/inputs.py` | `c52ff6d12a71f2c536de8e2bdc3478cc5c00e124` |
  | `learn/trees.py` | `e21f38706067bacf251ef8494fbd8674fc20b1c4` |
  | `learn/stream_tier.py` | `107abb472bb23b606877673e8b80ec75bf3eba95` |

- **Settings:** unchanged.
  - Blocks L40, Q14, I91, S42.
  - The 192-point penalty grid, with nested out-of-fold penalties.
  - LightGBM: 50 trees, depth 2, learning rate 0.1, minimum leaf 200, deterministic,
    1 thread.
  - Non-negative stack weights.
  - Positions: five-day trailing mean, demeaned, unit gross.
  - Walk-forward: 252-row years, first scored year 3, embargo 2 rows, warm-up 64 rows
    dropped.
- **Priced as ONE declared strategy** through the supplied-streams tier. No menu, no
  maximum over predictors.
- **Run beside it, descriptive only:**
  - the control: the L-block ridge, penalty 1.0;
  - the class tier: the fast kernel's class maximum against its class null.
- **mv_combine is not run.**
- The runner calls `learn.ridge_stack.run(panel, "ridge_stack")`. Its start-up checks
  are in section 7.

## 2. Panels: seed block 689000–689999

**Collision check:** `experiments/seed_block_check --ranges 689000-689999` reports **NO
COLLISION** against every pre-registration, master-seed draws and the pilot's blocks
(685000–687999).
- 688000–688999 was considered first and **rejected**: it contains a draw of master seed
  20261010.

**Seeds:**

| use | seeds | levels |
|---|---|---|
| U | 689000–689099 | 1.5; the first 50 (689000–689049) also at 1.0 and 2.5 |
| corner | 689100–689199 | 1.5; 689100–689149 also at 1.0 and 2.5 |
| product | 689200–689299 | 1.5; 689200–689249 also at 1.0 and 2.5 |
| state-gated | 689300–689399 | 1.5; 689300–689349 also at 1.0 and 2.5 |
| level 0 | 689400–689799 | 0; each panel at the registered cost and at zero cost |
| dry run and box smoke | 689900–689909 | never read |
| paired bootstrap | 689999 | — |

**How seeds are used:**
- One seed's levels share its residual draw and its rule features. Rule features come
  from `environments.planted_rules.draw_features(seed, shape)`.
- The plant is net-targeted (`planted_scale`). The fast/slow label is turnover > 0.5,
  fixed at `c356992`.
- At zero cost, `cost_rate` and `borrow_rate` are set to zero.

## 3. Pricing, the bootstrap window and the block length

The windows and the block-length rule are fixed here.

**The supplied-streams tier** (ridge_stack, and the control beside it):
- **Stream:** the net stream on the scored rows **756–3018 (2,263 rows)**, the book
  starting from zero at row 756.
- **Replicates:** B = 1,000, `default_rng(panel seed)`.
- **Block length:** one per panel, by the class rule: the median, over the base feature
  columns demeaned on rows 756–3018, of each column's Politis–White optimal
  stationary-bootstrap block length (`estimator.bootstrap.select_block_length`).
  - In the pilot it ranged over 1–27, median 3.
- **Certified:** p < 0.05, where p = (1 + #{M_b ≥ S}) / (B + 1).

**The class tier:**
- The fast kernel's class maximum over its 82,240 members, on the **whole in-sample
  window, rows 0–3018 (3,019 rows)**.
- **Replicates:** B = 1,000, `default_rng(panel seed)`.
- **Block length:** the same rule, on the base columns of rows 0–3018.
  - In the pilot it ranged over 1–26, median 4.
- **Certified:** p < 0.05.
- It is not computed on the zero-cost panels, because its kernel tables carry the
  registered costs.

**The block length is a fixed RULE, not a fixed number.** It is chosen per panel, from that
panel's base columns over the tier's own window, by the median Politis–White rule the class
tier uses. No number is substituted for it.

**The two tiers price different windows, on purpose** (2,263 rows against 3,019).
- The pipeline needs its first training window: the first three 252-row years, rows
  0–755, before it can score a row.
- The class tier needs no training window, because its members are fixed rules that can
  be priced from row 0.
- Each tier is priced on the window it would actually operate on. **This is the operating
  comparison**, as in the pilot, and it is not equalised.

## 4. Level, read first

**The read:** ridge_stack's certification rate on the **400 zero-cost level-0 panels**,
then on the 400 at cost, with Wilson 95% intervals. The control and the class tier (at
cost) are reported beside it.
- **ridge_stack fails level iff the lower Wilson end of its zero-cost rate exceeds 0.05.**
  At n = 400 that means **29 or more certifications**.
  - The lower end is 0.0489 at 28 and 0.0510 at 29.
- **Detectable:** a true rate of **0.083 or more**, with 80% power.
- A predictor exactly at 0.05 fails with probability **0.031**.

**Both branches:**
- **Fails:** the power claim (section 5) is **not made**, whatever its interval. The level
  failure is reported, and section 5's numbers are shown, labelled as void.
- **Holds:** reported, with the interval's upper end as the largest excess not ruled
  out. Section 5 is read.

## 5. Power, primary

**The quantity:** the pooled certification rate at **level 1.5** over the four rules,
n = **400** panels (4 x 100). **ridge_stack minus the class tier**, paired by panel.

**The interval:** a paired bootstrap over panels.
- B = 10,000, `default_rng(689999)`, panels resampled with replacement.
- The interval is the 2.5th and 97.5th percentiles of the resampled mean difference.

**Decision line: the claim holds iff the LOWER end of the 95% paired interval for
ridge_stack minus the class tier exceeds zero.**
- **Otherwise it does not hold, and the report says the confirmation failed at this n**
  (n = 400). The difference and its interval are reported.
- **If level fails (section 4), the primary is void, and that is the reported result.**
  The primary's numbers are shown, labelled void. No claim is made from them in either
  direction.

**Both branches, with level held:**
- **Holds:** "On these four planted rule shapes at net level 1.5, ridge_stack, named in
  advance and priced as one declared strategy, certifies more panels than the class
  tier."
  - It is stated with the difference, its interval, and the limits in section 8.
- **Does not hold:** "The confirmation failed at n = 400." The difference and its
  interval are reported. No further reading of the failure is registered.

**What the primary shows, and what it does not.**
- **It shows an operating gain:** more certifications of planted non-linear edges at held
  level, with each tier priced as it would operate.
- **It does not show that the non-linear layers caused the gain.** Part of the gain comes
  from the single-strategy bar: one declared stream, against the class tier's maximum
  over 82,240 members.
- **The control comparison (section 6, secondary) is the read on what the non-linear
  layers add.** The control is a linear ridge priced at the same single-strategy bar.

**Detectable at n = 400, 80% power** (normal approximation to the paired difference;
z = 1.960 + 0.842):

| discordance assumed (class certifies, ridge_stack does not) | smallest detectable difference |
|---|---|
| p01 = 0.03 | **0.045** |
| p01 = 0 (the approximation is poor) | 0.019 |
| p01 = 0.02 | 0.039 |
| p01 = 0.05 | 0.055 |
| p01 = 0.10 | 0.073 |

- **p01 = 0.03 is the pilot's discordance at level 1.5:** 6 of 200 panels.
- **It is used only as a planning input.** The pilot was exploratory, ran on a different
  block, had 50 panels per rule, and selected ridge_stack. Nothing about the confirmation
  is inferred from it. The pilot's own difference is not used to size anything.

## 6. Secondary, descriptive

No claim rests on these.
- **The primary difference per rule:** ridge_stack minus the class tier, at level 1.5,
  n = 100 each, with the same paired bootstrap.
  - At p01 = 0.03 the smallest detectable difference per rule is 0.112.
- **Against the control:** ridge_stack minus the control, pooled and per rule, at 1.5.
- **Levels 1.0 and 2.5:** certification rates for ridge_stack, the control and the class
  tier, with Wilson intervals. 50 panels per rule, the first 50 seeds of each rule's
  block.
- **Capture:** ridge_stack's (and the control's) population net and gross Sharpe over
  its scored window, as a share of the plant's over the same window. Each cell shows
  medians and ranges, beside:
  - the linear shadow share on the same panels;
  - the design-block 5a figure.
- **Fast and slow:** every rate and capture cell is also split by the fast/slow label.
  Cells with fewer than 5 panels are marked THIN.
- **Either tier, at level 0:** on the 400 level-0 panels at cost, the rate at which EITHER
  tier certifies (the class tier OR ridge_stack). It is reported with its Wilson interval,
  beside each tier's own rate.
  - **No rule attaches to it.**
  - If both tiers are offered to agents, pricing the stream jointly with the class is a
    design question for the tool build. It is not settled here.
- **ridge_stack's diagnostics:** penalties by block (labelled L, Q, I, S; "off" printed
  as off), stack weights, turnover, and the share of days the gross cap binds.

## 7. Platform, order of work, and what is not read

- **Box only:** c7a.48xlarge, Linux x86_64. LightGBM 4.7.0 from
  `lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`, SHA-256
  `d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7`, verified before
  install. Laptop and box numbers are not mixed.
- **The runner refuses to start unless all of these hold:**
  - **Pinned code:** the four `learn/` blob hashes in section 1 match HEAD's.
  - **LightGBM:** `lightgbm.__version__` is 4.7.0.
  - **The wheel:** the wheel file given to the runner has SHA-256
    `d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7`.
  - **The installed library:** `lib_lightgbm.so` has SHA-256
    `573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a`. This is the value
    recorded by the pilot from that wheel on the box (`302c447`).
  - **A clean tree at the registered commit:**
    - no tracked changes;
    - this registration's commit is an ancestor of HEAD;
    - HEAD equals the commit named on the command line, the one that carries the
      committed runner.
  - **The platform:** Linux x86_64.
- **No holdout quantity is computed or read.** The state-gated holdout gate's known
  defect (`f41583b`) therefore does not arise.
- **Order:**
  1. This document is committed alone.
  2. The runner and the reader are committed next. The reader is tested on synthetic
     rows before any result exists.
  3. On the box, from 689900–689909:
     - a box smoke: the leak test and a bit-for-bit repeat for ridge_stack and the
       control;
     - a dry run with the checker. It prints no outcome.
  4. The run.
  5. The raw outputs and the run record are committed before the read.
  6. The read runs once, in the order level, primary, secondary, and its output is
     committed unedited.

## 8. Limits, stated in advance

- **The rule shapes are invented.** No claim is made that real edges take them.
- **The bars differ:** ridge_stack is one declared strategy, and the class tier is the
  maximum over 82,240 members. Part of any difference is that lower bar.
- **The two tiers price different windows** (section 3).
- **Only in-sample certification is tested.** No holdout performance is claimed.

## 9. Estimated box time and cost

Scaled from the pilot's measured task times on this box:
- **Pilot task times (medians under 150-worker load):**
  - a planted task: 420 s for three levels and four predictors;
  - a level-0 task: 241 s;
  - ridge_stack: 55 s per panel; the control: 5 s per panel.
- **This run's tasks:**
  - 200 seeds at three levels, about 320 s each;
  - 200 seeds at one level, about 120 s;
  - 400 level-0 seeds at cost and zero cost, about 175 s.
- **Total:** about 160,000 worker-seconds, or **about 20–25 minutes on 150 workers**,
  including the tail.
- **With setup, the box smoke (about 9 min) and the dry run (about 5 min):** about **45–50
  box minutes**.
- **Cost:** at the c7a.48xlarge on-demand rate of about $9.85/hour (US East; not checked
  today), **about $8**, and under $10.
