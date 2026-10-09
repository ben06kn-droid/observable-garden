# Version 2, second exploratory pilot: DRAFT, NOT LIVE

**Status: DRAFT for the author's review.** It is not committed as live and nothing has
been run.
- It is kept in `docs/` because prereg files were off-limits during the write-up work.
- On approval it would be appended to `prereg/ml-v2-exploratory-2026-10-08.md` as a
  dated section, committed alone before any script.

## Why a second round, and what changes

**From the refit records** (`b5826e8`; laptop refits of 140 already-read pilot panels;
descriptive):
- **The L penalty sits at its largest value (3) in most refits.** That is 87–95% of
  version 2's refits on planted panels and 96–98% on null panels, against 77% and 93%
  for version 1.
  - The smallest L value (0.3) is chosen in 0–3% of version 2's refits.
  - **So the L grid is stuck at its upper boundary.**
- **No other block is stuck at a boundary.** Q, I and S choose "off" in 42–77% of
  refits. "Off" is a legitimate choice, not a boundary of a continuous grid.
  - Their smallest non-off value is chosen in at most 12% of refits (I, expanding
    memory, planted).
- **Product plants (level 1.5, n = 50):**
  - version 2's rolling-252 memory captures little: median net capture 0.055, against
    0.312 for rolling 756 and 0.512 for expanding;
  - it chooses I off in 46% of refits, against version 1's 4%;
  - on the 11 panels only version 1 certified, version 1 chose I = 1 in 63% of refits,
    and version 2's expanding memory did so in 18%.
  - The 3-fold choice with version 1's design equals version 1's leave-one-year-out
    choice in 75% of refits for I, and 92% for L.

**The revision, applied to version 2 only.** Version 1 is unchanged.
- **The L grid becomes {1, 3, 10, 30}** (was {0.3, 1, 3}).
- **Why:**
  - the largest value was chosen in 87–98% of refits, so the grid is extended upward
    by two steps of the same ratio;
  - the smallest, chosen in 0–3%, is dropped.
- **Q, I and S are unchanged.**
- **The memory settings are unchanged.** The product finding concerns the rolling-252
  memory, but averaging over memories is the author's standing decision, so it is
  reported, not acted on.

## Design

**Streams, each as one declared strategy** (the supplied-streams tier, B = 1,000):
- version 2's base view (P, X, V; h 5; market; always) under grid G3, the grid carried
  forward, with the revised L grid;
- version 1;
- the plain ridge.

There is no menu and no class tier.

**Two cost arms, on the same panels.** The fits are shared, and only the streams' costs
differ.
1. **Registered:** the ETF costs, 5 bps one-way and 50 bps a year borrow.
2. **High-cost: both rates multiplied by 5.0,** so 25 bps one-way and 250 bps a year
   borrow.
   - **How the multiplier is set, from null-only quantities:** version 1's median cost
     drag on the first pilot's 100 level-0 panels at registered cost was 0.197 Sharpe
     (`fe7c7ca`, R4, null).
   - Cost drag is proportional to cost while the stream's volatility barely moves, so
     1.0 / 0.197 = 5.08. That is rounded to 5.0.
   - The pilot reports version 1's median cost drag on its own level-0 panels in the
     high-cost arm, as a check.

**Panels, on the seed block 698000–698999** (`seed_block_check`: NO COLLISION,
2026-10-09):
- **Planted:** 7 shapes × 50 seeds at levels 1.0 and 1.5 (698000–698349, 50 per shape,
  in the first pilot's shape order).
- **Level 0:** 100 panels (698400–698499), in three versions: the registered cost, the
  high cost, and zero cost.
- **The paired bootstrap seed:** 698999, B = 10,000.

## Reads, once, in order

**R1, level, per cost arm:** each stream on the level-0 panels, at zero cost and at that
arm's cost. A stream fails iff the lower Wilson end of its zero-cost rate exceeds 0.05.

**R2, power:** each stream by shape × level × cost arm, pooled, fast and slow.

**R3, descriptive:**
- capture, turnover and cost drag per arm;
- the L penalty's distribution under the revised grid;
- capture by memory setting.

## Rules, stated now, per cost arm, both branches

**Replacement, in each arm separately.** Version 2's base view replaces version 1 **in
that arm** iff:
- its pooled certification rate at levels 1.0–1.5 over all seven shapes (700 paired
  panels) exceeds version 1's, with a paired 95% interval (B = 10,000, seed 698999)
  excluding zero; and
- the base view holds level.

**Otherwise version 1 stays in that arm.**

**If the arms disagree,** the report states both branches and the decision returns to
the author. No arm is preferred by rule.

**The fairness flag (not a rule), per arm:** the same paired difference on version 1's
original four shapes (400 panels). If its lower end is below −0.05, the report says
version 2 wins only where the plant uses its new inputs, and the decision returns to
the author.

**Detectability at 80% power** (a normal approximation; p01 is the share of panels
version 1 certifies and version 2 does not):

| comparison | n | p01 = 0 | 0.02 | 0.05 | 0.10 |
|---|---|---|---|---|---|
| replacement, per arm | 700 | 0.011 | 0.027 | **0.039** | 0.053 |
| fairness flag, per arm | 400 | 0.019 | 0.039 | 0.055 | 0.073 |

## Platform and cost

- **Box only,** with the Linux LightGBM pin and the v2 inputs pin (`3ff15481…6700`),
  both hash-checked. A box smoke runs first.
- **The task times:** a planted task fits version 2's base view under 3 memories and
  version 1, at two levels, and prices both arms. That is about 220 s on the laptop,
  times 1.7 on the box under load. A level-0 task is about 110 s on the laptop.
- **Total:** about 88,000 laptop cell-seconds, or about 24 cell-hours.
  - On 180 workers the run is about 15 minutes plus a tail of about 6.
  - With setup and the smoke, **about 45 box minutes, roughly $7.**
- **The code needed,** written after approval and committed before any run:
  - the L grid as a version-2 parameter (in `learn2/`, version 1 untouched);
  - a cost multiplier in the runner;
  - a runner and a reader on the first pilot's pattern, the reader tested on made-up rows.
