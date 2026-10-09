# Version 2 confirmation: DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE.** It is committed for the author's review. It is not a
registration, and nothing in it binds until a separate, dated commit makes it live.
- No code for this test exists yet, and nothing has been run.
- No holdout row is involved.

**Where it comes from.** The second exploratory pilot (`9e4f6a7`; note section `4688d5e`;
outcome `ec50498`) found version 2's base view ahead of version 1 in both cost arms. Three
of its settings were chosen on that pilot's results. This confirmation tests the chosen
configuration, named in advance, on fresh panels.

## 1. The predictor

**Version 2's base view, exactly as configured at the second pilot** (code unchanged
since `704241a`; HEAD at drafting `f79bc4c`):
- **The view:** blocks P, X and V; horizon 5; market-neutral; always.
- **Memory set M2:** rolling 756 and expanding, averaged.
- **Rate grid G3:** {0.3, 0.1, 0.03}, averaged.
- **L penalty grid {1, 3, 10, 30}.** Q is {0.3, 1, 3, off}; I and S are {1, 3, 10, off}.
  The rest as built: 3 embargoed folds, trees, a non-negative stack, the 64-row warm-up.
- **Pinned by blob hashes** at `f79bc4c`:

  | file | blob |
  |---|---|
  | `learn2/__init__.py` | `4154f7f48affe0885fb361ffc309d09b0a4a566d` |
  | `learn2/timing.py` | `bf55de9216cb7c822372b5d00ac67ddac6dfb652` |
  | `learn2/blocks.py` | `7c39985f8fbb29eca16a268aecdf064ebf46b176` |
  | `learn2/states.py` | `9060fdf0364fa4f00befeee79213b5a12de06bc6` |
  | `learn2/learner.py` | `522627305a0f7b6ddb48f708c54b6709c129c363` |
  | `learn2/views.py` | `232a79fb8ddb1f87a7ce7c42da1110b3d0a225df` |
  | `environments/etf_v2_inputs.py` | `4c7837153bba98b302092b4f5265818a6eb1a226` (inputs pin `3ff15481…6700`) |
  | `environments/planted_rules.py` | `9b83867e3c4cf472c50651e0bf1ab050c1864171` |

  Version 1's four `learn/` blobs, as pinned for the ridge_stack confirmation, are also
  pinned.
- **Priced as ONE declared strategy** through the supplied-streams tier.

**Beside it, descriptive:**
- version 1 (ridge_stack at `fce5627`);
- the plain ridge;
- the class tier. It runs at the registered cost only, because its kernel tables carry
  the registered costs.

## 2. Panels: fresh seeds

The blocks 699000–699999 and 700000–700999 were checked: NO COLLISION
(`experiments.seed_block_check`, 2026-10-09).

| use | seeds | levels |
|---|---|---|
| U | 699000–699079 | 1.0, 1.5 |
| corner | 699080–699159 | 1.0, 1.5 |
| product | 699160–699239 | 1.0, 1.5 |
| gated | 699240–699319 | 1.0, 1.5 |
| lead-lag | 699320–699399 | 1.0, 1.5 |
| volume-conditioned | 699400–699479 | 1.0, 1.5 |
| regime-only | 699480–699559 | 1.0, 1.5 |
| level 0 | 700000–700399 | 0; zero, registered and high cost |
| smoke and dry run | 699900–699909 | never read |
| paired bootstrap | 699999 | — |

That is **1,120 paired planted panels** (7 shapes × 80 seeds × 2 levels) and 400 level-0
panels.

**Cost arms:**
- **registered:** 5 bps one-way, 50 bps a year borrow;
- **high:** both × 5.0, as in the second pilot.

## 3. Level, read first

- **The read:** each stream's certification rate on the 400 level-0 panels at zero cost,
  then at the registered and the high cost, with Wilson 95% intervals.
- **Version 2 fails level iff the lower Wilson end of its ZERO-cost rate exceeds 0.05:**
  29 or more certifications of 400.
  - A true rate of 0.083 or more is detected with 80% power.
  - A rate exactly at 0.05 fails with probability 0.031.
- **If version 2 fails level, both power claims below are void, and that is the result.**
  Their numbers are shown, labelled void.

## 4. The primary and the co-primary

**Primary, registered costs:** version 2 minus version 1, in the pooled certification
rate at levels 1.0 and 1.5 over the seven shapes (n = 1,120 paired).

**Co-primary, high costs (×5.0):** the same difference, on the same panels.

**Both claims share one family:** each is judged on a **97.5%** paired bootstrap interval
(Bonferroni over the two; B = 10,000, `default_rng(699999)`, panels resampled with
replacement).

**A claim holds iff the lower end of its 97.5% interval exceeds zero, and level held.**

**Each branch, in plain words:**
- **Registered holds:** "At registered costs, on these planted shapes, version 2
  certifies more panels than version 1." Otherwise: "Not shown at registered costs at
  n = 1,120."
- **High holds:** "At five times the registered costs, version 2 certifies more panels
  than version 1." Otherwise: "Not shown at high costs at n = 1,120."

**The four joint outcomes:**

| registered | high | what is said |
|---|---|---|
| holds | holds | Version 2 certifies more planted edges than version 1 at both cost levels. |
| holds | does not hold | The gain is shown at registered costs only. At high costs it is not shown. |
| does not hold | holds | The gain is shown only when costs are high. That is consistent with version 2's lower turnover rather than better prediction, and is stated as such. |
| does not hold | does not hold | The confirmation failed at n = 1,120. Version 1 stays. |

## 5. Sizing and detectability

The size is set from the pilot **only as a planning input**. The pilot was exploratory,
its settings were chosen on its own results, and its gain is optimistic.

**The registered primary:**
- **The pilot's numbers:** the gain was +0.037. On the pilot's 700 paired panels,
  version 1 alone certified p01 = 0.0586 of them and version 2 alone 0.0957.
- **The sample needed:** at one-sided α = 0.0125 (the 97.5% interval) and 80% power, a
  difference of 0.037 under p01 = 0.0586 needs n ≈ 1,061 paired panels. That is 76 seeds
  per shape at two levels. **The draft uses 80 seeds per shape: n = 1,120.**
- **Detectable at n = 1,120:**

  | p01 | 0 | 0.02 | 0.05 | 0.0586 | 0.10 |
  |---|---|---|---|---|---|
  | smallest detectable difference | 0.009 | 0.023 | 0.034 | **0.036** | 0.046 |

  **So the pilot's +0.037 is at the edge of detection.** A true gain below it would
  usually be missed.

**The high-cost co-primary:** the pilot's gain was +0.077 with p01 = 0 (version 1 alone
certified no panel). That needs only n ≈ 114, or 146 at p01 = 0.01, so it is not the
constraint.

## 6. Secondary, descriptive

No claim rests on these.
- the same difference on version 1's **original four shapes** alone (U, corner, product,
  gated), per arm;
- the difference **by shape**, per arm;
- **version 2 against the class tier**, at registered cost;
- **capture** (population net and gross Sharpe as a share of the plant's, over the same
  window), per arm;
- **cost drag,** and turnover per unit gross, per arm;
- version 2's **penalty choices and capture by memory**, stored per refit.

## 7. What it shows, and what it does not

**What it shows:** whether version 2's configuration, chosen in a pilot, keeps an advantage
over version 1 in certifying planted edges, on fresh seeds.

**What it does not show:**
- **The planted shapes are invented, and constant through time.** A constant edge favours
  long memory by construction, and nothing here says how either version handles edges that
  decay or change.
- **Three of the seven shapes** (lead-lag, volume-conditioned, regime-only) use inputs that
  version 1 cannot see: X, V and the regime gate on the residual market. Part of any gain
  there is access, not learning. The original-four-shapes secondary separates it.
- **Nothing about real data.** No real panel, and no holdout row, is involved.

## 8. Platform, order of work, cost

- **Box only,** with the Linux LightGBM pin and the v2 inputs pin, both hash-checked. The
  start-up refusals are as in the second pilot, plus this file's live commit as an
  ancestor of HEAD.
- **Order:**
  1. This file goes live, committed alone.
  2. The runner and reader are committed, the reader tested on made-up rows.
  3. A box smoke, then the run, with a dry run on 699900–699909 alongside.
  4. The raw outputs are committed before the read.
  5. The read runs once: level, then the primary and co-primary, then the secondaries.
     Its output is committed unedited.
- **Projected cost:**
  - A planted seed task covers two levels. It runs version 2 with 2 memories, version 1,
    the plain ridge, one class pass, and tiers in both arms: about 190 s on the laptop.
  - A level-0 task is about 110 s.
  - In all, about 150,000 laptop cell-seconds. At the box's 1.7× under load on 180
    workers, that is about 25 minutes of run plus a tail.
  - With setup, the smoke and the dry run, about **50 box minutes, roughly $9.**
