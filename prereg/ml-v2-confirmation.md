# Version 2 confirmation: DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE.** It is committed for the author's review. It is not a
registration, and nothing in it binds until a separate, dated commit makes it live.
- No code for this test exists yet, and nothing has been run.
- No holdout row is involved.

**Where it comes from.** The second exploratory pilot (`9e4f6a7`; note section `4688d5e`;
outcome `ec50498`) found version 2's base view ahead of version 1 in both cost arms. Three
of its settings were chosen on that pilot's results. This confirmation tests the chosen
configuration, named in advance, on fresh panels.

**Revised 2026-10-09 (still DRAFT):** the claims are now H (high-cost superiority) and R
(registered-cost non-inferiority, margin 0.03); see section 4.

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

## 4. The two claims (revised 2026-10-09; still DRAFT)

Both claims use the pooled certification rate at levels 1.0 and 1.5 over the seven shapes
(n = 1,120 paired panels), and version 2 minus version 1.

**Each is judged on a 97.5% paired bootstrap interval** (Bonferroni over the pair; B =
10,000, `default_rng(699999)`, panels resampled with replacement).

**Claim H: high cost (×5.0), superiority.**
- **H holds iff the lower end of its 97.5% interval exceeds 0.**
- Holds: "At five times the registered costs, version 2 certifies more planted edges than
  version 1."
- Does not hold: "Not shown at high costs at n = 1,120."

**Claim R: registered cost, non-inferiority with margin 0.03.**
- **R holds iff the lower end of its 97.5% interval exceeds −0.03.**
- Holds: "At registered costs, version 2 certifies no fewer planted edges than version 1,
  beyond a margin of 0.03."
- Does not hold: "Non-inferiority at registered costs is not shown at n = 1,120."
- **Why the margin is 0.03.** It is under half the second pilot's high-cost gain
  (0.077 / 2 = 0.0385). It is also far smaller than the gap between version 1 and the
  plain ridge at registered cost in that pilot (0.366 − 0.231 = 0.135). So a loss inside
  the margin is small next to what either learned predictor adds over a plain ridge.
- **The margin is fixed here, before any confirmation outcome exists.**

**Version 2 replaces version 1 iff level holds AND H holds AND R holds.**

**The four joint outcomes, with level held:**

| H | R | in plain words |
|---|---|---|
| holds | holds | Version 2 is better under heavy costs, and no worse beyond 0.03 at registered costs. **Version 2 replaces version 1.** |
| holds | does not hold | Better under heavy costs, possibly worse otherwise. **Version 2 is not adopted as the default.** It is offered only for high-cost panels. |
| does not hold | holds | No worse, and no gain shown. **Version 1 stays.** |
| does not hold | does not hold | Neither is shown. **Version 1 stays.** |

**If level fails, both claims are void and version 1 stays.**

## 5. Sizing and power (planning inputs only)

**The sample size is kept at n = 1,120 paired panels per arm** (7 shapes × 80 seeds × 2
levels).

The figures below use the second exploratory pilot **only as a planning input.** Its
settings were chosen on its own results, so its gains are optimistic. In its registered
arm, version 1 alone certified p01 = 0.0586 of the paired panels.

**Claim R** (normal approximation; one-sided α = 0.0125; margin 0.03):

| true difference | power at the pilot's p01 = 0.0586 | at p01 = 0.05 | at p01 = 0.10 |
|---|---|---|---|
| 0 | **0.755** | 0.825 | 0.501 |
| +0.01 | **0.935** | 0.964 | 0.752 |
| +0.02 | **0.989** | 0.995 | 0.908 |

**So if the two versions are truly equal at registered cost, R is shown about three times
in four.**

**Claim H:** at the pilot's high-cost gain (+0.077, with p01 = 0 or 0.01) its power is
above 0.99. At half that gain (+0.0385, p01 = 0.01) it is 0.999.

## 6. Secondary, descriptive

No claim rests on these.
- **Superiority at registered cost:** version 2 minus version 1 at registered cost, with
  its 97.5% interval.
  - The pilot's +0.037 is **at the edge of detectability** at this n (0.036 at p01 =
    0.0586), and is **likely optimistic**, since three settings were chosen on that
    pilot.
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
  5. The read runs once: level, then claims H and R and the joint outcome, then the
     secondaries.
     Its output is committed unedited.
- **Projected cost:**
  - A planted seed task covers two levels. It runs version 2 with 2 memories, version 1,
    the plain ridge, one class pass, and tiers in both arms: about 190 s on the laptop.
  - A level-0 task is about 110 s.
  - In all, about 150,000 laptop cell-seconds. At the box's 1.7× under load on 180
    workers, that is about 25 minutes of run plus a tail.
  - With setup, the smoke and the dry run, about **50 box minutes, roughly $9.**
