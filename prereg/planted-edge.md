# 7.5 planted-edge: a known edge, on real features, in agent hands

**DRAFT — committed, not live. Nothing runs on it.** It replaces 7.4, withdrawn
2026-10-01 (`ROADMAP.md`, "7.4 withdrawn, 7.5 registered"). It goes live by a
dated commit once the build items below exist and pass their tests. Until then a
change is an edit to a draft, recorded in history, not an amendment.

## Question

**Does the gate certify a planted edge in agent hands, on real features, at the
registered error rate — and does the certified submission hold out of sample
against a known truth?**

6.5 and 7.4 could not answer this. Their panels contain no member the gate
should certify: 6.5's ETF class maximum is half the null level (class tier 0/40,
every p = 1.0000), and 7.4's class has no net-positive member. A test that can
only return FAIL measures behaviour, not the gate. Here the edge is planted, so
**the truth is known per specification**, and false certification, power,
recovery, the deflation gap and out-of-sample value are read against it.

## Design

### Panel

**Features: the real 40-ETF feature matrix X** (`environments/real_panel.build_etf_panel`,
K = 40, M = 40, the registered timing: a weight formed at the close of t earns
the close of t+1 to the close of t+2), unchanged, real costs and borrow.

| segment | calendar | rows | role |
|---|---|---|---|
| in-sample | 2005–2017 | 3,019, from 2006-01-04 (2005 is the 252-day warm-up) to 2017-12-29 | what the agent searches |
| planted holdout | 2018–2022 | the panel's rows in that span | the planted process continued; sealed |

**Both segments are already-open years** — inside 6.5's in-sample span
(2005-01-01 to 2022-12-31), which every 6.5 agent searched. **6.9's sealed
holdout, 2023-01-01 to 2025-12-31, is untouched**: nothing here reads it, and
`data/etf_loader.py` refuses its rows anyway.

**One freshly seeded semi-synthetic panel per run.** For panel seed `s`,
`SeedSequence(s).spawn(3)` gives three independent children: **[0]** the in-sample
bootstrap indices, **[1]** the planted member, **[2]** the holdout bootstrap indices.

### Returns: the residual, exactly

For a segment with earned-return matrix `R` (`RealPanel.returns`, T × M):

    E = R − 1 · mean_t(R)          (each asset demeaned over the segment's own rows)

**The resample is a joint-time stationary block bootstrap of the rows of E**: one
index sequence `idx` (`estimator.bootstrap.stationary_bootstrap_indices`) selects
whole days, so every asset moves with the same day and the cross-section's
correlation, dispersion and co-movement are carried as they occurred. Block length
**L = `select_block_length(E_in-sample)` = 7** (measured on the in-sample E,
2026-10-01). The same L is used for the holdout. Features are **not** resampled: X
stays in calendar order, so the residual is independent of X by construction, and
no real feature–return relation survives into the panel.

### The planted signal

**The planted member** `m*` is one member of the declared class, drawn **uniformly
from the 79,040 depth-3 members** of `SubsetClass(max_size=3, signed=True)` (in
`environments.class_table.members_in_order` order) with child [1]. **Depth 3 so that
reaching it is a search, not a single extension.** Its weight path
`w*_t = RealPanel.weights_from(X @ wf(m*))` is the sandbox's own, dollar-neutral,
gross 1.

    r̃_t = E[idx_t] + c_β · w*_t

so `m*` earns `c_β·‖w*_t‖²` gross per period above the residual, and every other
member earns `c_β·⟨w_m,t, w*_t⟩` through its overlap with `m*`.

**β is set ex ante, as a population net Sharpe.** For any member m on a segment,
with `Σ` the residual covariance of E and the registered cost model (ETF one-way
cost and borrow, as 6.5):

    d_t = c·⟨w_m,t, w*_t⟩ − cost_m,t − borrow_m,t
    SR_pop(m) = mean_t(d_t) / sqrt( mean_t(w_m,t' Σ w_m,t) + var_t(d_t) ) · sqrt(252)

**`c_β` solves `SR_pop(m*) = β`** (Brent, tolerance 1e-14), for β ∈ **{0.5, 1.0,
1.5}**; **β = 0 is `c = 0`**, for the reason measured below. On the preflight's first
panel `c` = 6.57e-3, 1.13e-2 and 1.61e-2 (and the `SR_pop(m*) = 0` scale would have
been 1.82e-3).

**Recorded per panel, every level:** `m*`, `c_β`, `SR_pop(m*)`, and the realized
in-sample and holdout Sharpe of `m*`.

**Paired across levels.** A seed fixes `idx`, `m*` and the holdout indices; only
`c_β` differs between levels. Every contrast between levels is therefore paired on
the same residual draw and the same planted member.

**The truth for every specification.** `SR_pop` is defined for **any** member, so
every submission has an exact population Sharpe on each segment: no sampling
noise, computed from X, Σ, c and the cost model. That is the outcome readouts 4
and 5 use.

**Is β = 0 a global null? Measured, not assumed.** Planting `c_0 > 0` gives every
member overlapping `m*` a gross edge, and a member with lower turnover than `m*`
could net positive. **It does.** On 7 design panels (640000–640006, 2026-10-01,
`runs/planted_edge_null_check.json`), with `c_0` set so that `SR_pop(m*) = 0`, the
largest population net Sharpe in the class is **+0.03 to +0.91**, and **62 to
23,022 members** are positive. A high-turnover `m*` needs a large `c_0` to cover its
own cost, and lower-turnover neighbours collect that gross edge more cheaply.
**"β = 0" defined as `SR_pop(m*) = 0` is not a null.**

**So the β = 0 level is the unplanted panel, `c = 0`** — the residual alone, where
every member has zero gross edge and positive cost, hence `SR_pop < 0` for every
member: a global null by construction. The planted levels 0.5, 1.0 and 1.5 keep the
population-Sharpe definition. **This departs from setting every level by `SR_pop(m*)`,
and is recorded as the reason.** Rule 1's definition of false certification is
nonetheless per specification, so it stays correct if any level's null is partial: **a certificate is false when the certified
submission's in-sample `SR_pop ≤ 0`**, whatever the level.

### The holdout, generated and sealed at registration

The planted process continues into 2018–2022: the same `m*` and `c_β`, the holdout
segment's own residual pool `E_holdout` (demeaned over 2018–2022), resampled with
child [2]. **Every registered panel's holdout returns are generated at the live
commit**, before any run, for every seed and level, written to an archive that is
encrypted and moved off the machine as 6.5's holdout was, with its SHA-256 recorded
in this file. Opened once, after every run is priced.

### Masking

Instruments are opaque labels and dates are period indices, per
`prereg/AGENT_PROMPTS_REAL.md` §4. **Feature names are masked too, which departs
from §4** ("Feature names are not masked"). The reason is particular to this panel:
the returns are synthetic, so a real name (`mom252_z`) carries real-world
associations — momentum works, low volatility works — that the planted process does
not honour, and an agent following them would be measured on its priors about
markets rather than on its search. Labels are `F00`–`F39` by a seeded permutation
per panel (child [1]'s stream, after the member draw).

### Scripted half, first

**The registered scripted searchers** (`searchers.meta_adaptive.registered_71`, the
six of `fixed-sequence-replay` amendment 6), each **class-capped**
(`set_class(SubsetClass(3, signed=True))`), at all four levels, **2,000 panels per
level**, paired, on the box. Each draw prices the submission at both tiers.

It produces three things, fixed before the agent half is read:

1. **The scripted power curve**, per searcher and level, at α = 0.05 and 0.01.
2. **The standing check** (Decision rules, last section): how often a correct
   procedure passes each rule, on these draws.
3. **"Nearest the class bar"**: **the level among {0.5, 1.0, 1.5} whose scripted
   power at α = 0.05, pooled over the six searchers, is nearest 50%**. Ties go to
   the lower level. That level is written into this file by a dated commit before
   any agent run.

### Agent half

**Three levels: β = 0, nearest-the-bar, 1.5.** claude-sonnet-5, thinking disabled,
`max_turns = 60`, `--defer-pricing`. **Sessions evaluate on the fly**
(`RealSandbox` with no class table): a session never builds, reads or waits on a
materialised class table. Pricing runs on the box from committed logs via
`experiments/price_runs.py`.

| arm | runs | purpose |
|---|---|---|
| **replay gate** | **20 per level, 60** | rules 1–5, the comparator for everything |
| **replay gate (reasoned pick)** | **sized in decisions: 14 per level, 42 to start** | check 2 (rule 6) |
| **unsaturable** | **20 per level, 60** | check 4 not predetermined |
| **prior-weighted α** | **definitions registered below; not run unless built and tested before live** | — |

**Reasoned-pick sizing.** Check 2 needs **10 accepted picks**, the low-n floor
(`prereg/README.md`), pooled over the three levels. 7.3's reasoned-pick arms
accepted **5 and 6 picks in 20 runs** (0.25–0.30 per run), so 10 picks implies
**about 40 runs**: the arm starts at **42 (14 per level)**, then adds blocks of 6
(2 per level) until 10 accepted picks are on record, capped at **60 (20 per
level)**. The stopping rule reads only **counts of accepted picks**, a harness
fact fixed before any fidelity is measured. At the cap with fewer than 10, check 2
reports **unmeasured with its count**. Meta moves (`restart`, `stop`) come from the
first 10 runs per level in seed order, 30 runs, which at 7.3's rates (5–7 restarts
and 7–8 stops per 10 runs) clears the floor for both.

**The unsaturable arm, and its preflight.** An agent that submits the class
maximum makes the two tiers price one statistic against near-identical nulls, so
check 4 is predetermined (7.3: 120 of 120). This arm caps the search so it cannot.
**A budget cap was preflighted first**, a deeper class held in reserve.

*Preflight* (`experiments/planted_edge_preflight.py`, `runs/planted_edge_preflight.txt`;
prototype generator, design seeds 640000–640019, paired across β = 1.0 and 1.5,
2026-10-01). The proxy runs the agent grammar's content moves with both signs, in the
order 6.5's agents most used — `init`, `extend_best` ×2, then `swap_worst` while it
improves — and a cap of k moves is a prefix of its path. **Saturated** means its best
support equals the realized class argmax.

| cap (content moves) | saturated, β = 1.0 | saturated, β = 1.5 | `m*` found, either |
|---|---|---|---|
| 2 | 0/20 | 0/20 | 0 |
| **3** | **4/20 = 0.20** | **3/20 = 0.15** | 0 |
| 4 | 7/20 = 0.35 | 6/20 = 0.30 | 0 |
| 6 | 10/20 = 0.50 | 8/20 = 0.40 | 1 |
| 12 (uncapped; it stops by itself at 4–5) | 10/20 = 0.50 | 8/20 = 0.40 | 1 |

**The cap: 3 content moves per session** — `init`, `extend_best`, `swap_worst`,
`flip`, `refine` and `pick` each count one; `declare_triggers`, `stop`, `restart`,
`pick_prior`, `predict` and `submit` do not. **The rule that chose it is not tuned
to these numbers: 3 is the smallest cap that can still reach a depth-3 member**
(cap 2 reaches depth 2 at most and saturates 0/20 by construction). At 3 the proxy
reaches the class argmax on **0.15–0.20** of panels, so **the cap leaves the
searcher unsaturated and no deeper class is needed.** The fourth content move is
refused by the harness, and the prompt states the cap.

*Read with three caveats.* (i) **The proxy is not the agent**: 7.3's agents
saturated where scripted searchers did not, so the arm's realized saturation is
reported as a descriptive readout beside check 4. (ii) **Even the uncapped proxy
saturates only 0.40–0.50 here**, so the replay-gate arm may itself be unsaturated on
this panel; check 4 is then read on both arms, the capped one being the arm whose
non-saturation is designed rather than hoped for. (iii) The preflight ran at β = 1.0
and 1.5 because nearest-the-bar is not yet known. **It is re-run at nearest-the-bar on
the design block after the scripted half**; if the capped proxy's saturation there
exceeds **0.50**, the deeper class (signed depth 4) is preflighted the same way
before any agent run, and its outcome is recorded by a dated commit.

**Recorded beside it, because it changes rule 3:** the realized class argmax is the
planted member on only **2/20 (β = 1.0) and 3/20 (β = 1.5)** panels. A correlated
neighbour of `m*`, with a luckier residual draw, usually tops the class: class
maximum 1.21 against `m*`'s realized 0.93 at β = 1.0. **Even an exhaustive search
recovers `m*` exactly on about one panel in eight.**

**The tier rule applies.** The class is enumerable, so **the declared-class tier
certifies**; the replay tier's p, the bracket and the commitment result are
reported beside it as audit (ROADMAP, 2026-09-30 amendment), with no fall-through
(`prereg/bracketed-verdicts.md` amendment 1).

**The nulls, fixed now.** Both tiers at **B = 1,000** replicates (the agent cells'
B = 200 asked only whether a null was computable; here the p-value is the readout),
the stationary bootstrap with the certifying null's block length chosen on the
panel's demeaned base columns, replicate RNG seeded by the panel seed, so the two
tiers of one run price on identical resamples. The class null is the class maximum
of the demeaned net Sharpe over all 82,240 members, **streamed chunk by chunk from
the panel without materialising a table** (`ClassTable.null_max`'s count-matrix
device applied per chunk), so no worker holds the 2 GB a table would need.

**Seeds are shared across arms by index**, as in 7.3, so arm contrasts are paired
on the same panel.

### Registered in advance: the prior-weighted arm's definitions

Registered now so that if the arm is built, its readouts cannot be defined after the
data. **It runs in 7.5 only if `short_list` and its pricing are built and tested
before the live commit**; otherwise the live commit records it deferred.

- **`short_list`**: up to **5** specifications, each a class member, declared in one
  call **before the first `evaluate`**; a late or second declaration is refused and
  logged. The list is fixed for the session.
- **Pricing**: the short list is tested by **White's Reality Check over its own
  members** at **α_prior = 0.04**, on the gate's stationary bootstrap with the
  certifying null's block length and seed; the search is tested against the class
  at **α_search = 0.01**. A run certifies if either test rejects; total size ≤ 0.05
  by Bonferroni. The class test is the class tier, unchanged.
- **Readouts**: whether the short list contains `m*` (exact) or overlaps it; the
  share of certificates from each route; false certification per route at β = 0.

### Registered in advance: the four reader definitions

From cell 3's read (`prereg/agent-cell.md`), where they were fixed at read time.
Registered here before any data:

1. **Evaluated.** A feature is evaluated when it appears in a support the search
   scored — any logged `support_after`. Candidates scored inside one move are not
   counted.
2. **Stated confidence.** The stated sd of `predict`; lower is more confident. The
   stated mean is reported beside it and is not the confidence measure.
3. **Net of priming.** A difference in differences of means: (arm − comparator) on
   the panel minus (arm − comparator) on its placebo, descriptive, with a bootstrap
   interval over runs (B = 10,000, percentile).
4. **Confidence rising.** Stated sd lower in an arm than its comparator at a
   two-sided Mann-Whitney U p < 0.05. Without that, confidence is "not shown to
   rise", which is not "unchanged".

## Decision rules

Each rule states both branches and what it can detect at its n. **"Detectable"**
means 80% power at a two-sided 0.05 test unless stated.

**(1) False certification at β = 0. One-sided, on the lower Wilson end. Expected
at or below nominal.** A certificate is false when its submission has in-sample
`SR_pop ≤ 0` (Design, "Is β = 0 a global null?"). The rule fails high **iff the
lower end of the Wilson 95% interval of the false-certification rate exceeds α**, at
α = 0.05 and 0.01, per arm, scripted and agent.
- *At or below nominal:* the gate holds on real features in agent hands; reported
  with the upper end as the largest liberality not ruled out.
- *Fails high:* **one-shot replication** on the replication block, same arm, same n,
  identical settings. Fails again: the gate is liberal on this panel, the arm's
  certificates carry no claim, and the liberality is investigated (leak first, then
  the null's construction) before anything else is read. Replication holds: reported
  as one failure of two, which is what a family of rules produces at this rate.
- *Expected direction, and why:* at β = 0 (`c = 0`) every member has negative
  population net Sharpe, since its gross edge is zero and its cost is not, and P2
  makes a sub-maximal search conservative; the rate is predicted **below** nominal.

| n | α | fires at | passes if exactly valid | with replication | 80% detects a true rate of |
|---|---|---|---|---|---|
| 2,000 scripted | 0.05 | k ≥ 120 | 0.9749 | — | 0.0644 |
| 2,000 scripted | 0.01 | k ≥ 29 | 0.9664 | — | 0.0167 |
| 20 agent | 0.05 | k ≥ 3 | 0.9245 | 0.9943 | 0.202 |
| 20 agent | 0.01 | k ≥ 2 | 0.9831 | 0.9997 | 0.143 |
| 14 reasoned pick at β = 0 | 0.05 | computed at the live commit from the realized n | | | |

**Family.** Six scripted searchers × two α at n = 2,000: **0.7206** if every one is
exactly valid and independent, **0.9893** with the replication branch. Agent arms at
β = 0 (replay 20, reasoned pick 14, unsaturable 20) × two α: **0.72–0.77**,
**0.96–0.98** with replication. **At n = 20 the agent rule sees gross leakage and
nothing finer** — a true rate below 0.20 at α = 0.05 is invisible.

**(2) Power by level, scripted and agent, reported against the curve.** Certification
rate per level and arm, with Wilson intervals; agent rates read **against the
scripted curve at the same level**, by exact binomial test of the agent count
against the scripted rate (known to ±0.011 at n = 2,000).
- *Predicted:* non-decreasing in β for every arm. If the true powers were near
  (0.02, 0.06, 0.57, 0.97), observed rates at n = 20 come out non-decreasing in
  **0.879** of experiments; a reversal at that n is read as noise unless it repeats
  across arms.
- *Agent at or near the curve:* the agent searches as well as the registered
  scripted policies at that level. *Above:* it finds the edge more often than they
  do. *Below:* it misses an edge they find — reported with where its submissions
  went.
- *Detectable at n = 20:* against a scripted power of 0.5, an agent rate below
  **0.20** or above **0.80**; against 0.9, below **0.685**; against 0.05, above
  **0.26**. Between arms, Fisher at 20 against 20: 0.05 against **0.45**, 0.20
  against **0.70**.

**(3) Planted-member recovery.** Per run, two outcomes: the submission **equals**
`m*` (canonical support), and the submission **contains** `m*` — read, since both are
depth ≤ 3, as **sharing at least two of `m*`'s three signed features**. Rates per
level and arm, Wilson intervals, each beside its **exhaustive-search base rate**:
the share of panels whose realized class argmax equals or contains `m*`, measured
on the scripted half's draws. The preflight puts "equals" at **2–3 of 20** for the
class argmax itself, so "equals" is reported but **"contains" is the readout**.
- *Predicted:* "contains" rising in β, near zero at β = 0, and at or below the
  exhaustive base rate.
- *Recovery near the base rate:* the agent finds what the class's own maximum would.
  *Well below it:* the agent misses the edge's neighbourhood. *Recovery low where
  certification is high:* the gate certifies neighbours of the edge, a finding about
  what "certified" means here, read with rule 5.
- *Detectable at n = 20:* the interval at 10/20 is [0.30, 0.70]; only a difference of
  about 0.4 between an arm and its base rate is visible.

**(4) Deflation gap against planted truth.** Per run: **stated mean minus the
submission's in-sample `SR_pop`** — the agent's belief about its submission against
that submission's true value. Mean and median per level and arm, one-sample t and
Wilcoxon against zero, both reported.
- *Predicted:* positive at every level (6.5 measured +0.53 against a deflated
  figure, in both arms alike).
- *Positive and shrinking with β:* overstatement is a search effect. *Positive and
  flat:* the agent states roughly the same number whatever is there. *Negative:*
  understatement, reported as such.
- *Detectable at n = 20:* with 6.5's sd of stated means, 0.035, a mean gap of
  **0.023**. If stated means here are as tight, any overstatement of practical size
  is visible; if they spread, the detectable gap scales with their sd, reported.

**(5) Out-of-sample: certified against uncertified, at α. PRIMARY: population.** For
every run, the submission's **holdout `SR_pop`** — its exact population Sharpe on
2018–2022 under the planted process. **No sampling noise per run.** Compared,
certified against uncertified at α = 0.05, **within level** (certification is
concentrated at high β, so a pooled comparison would read β, not the gate), combined
across levels by the paired difference of means.
- *Predicted:* certified > uncertified at every level with certificates.
- *Certified ≤ uncertified:* certification selects for in-sample luck, not edge —
  the gate's central claim fails here, and that is the result.
- *Detectable:* the per-run outcome is exact, so the comparison's noise is only the
  spread of truths across submissions within a level, **which the scripted half
  measures** and which sets this rule's detectable difference at the live commit.
- **SECONDARY: the sealed-holdout realization**, the submission's realized net
  Sharpe on its panel's sealed 2018–2022 returns. Kept because it is what a
  deployment would see. Per-run SE over 5 years: **0.447** at Sharpe 0, **0.548**
  at 1.0, **0.652** at 1.5. Certified against uncertified at 10 and 10 runs: SE
  0.200, detectable **0.56**; at 30 and 30, **0.32**.

**(6) Check 2: fidelity, per `prereg/agent-cell.md` amendment 7 as settled**
(`experiments/fidelity.py`): the information set is the prompt plus `shown[0..k−1]`;
the resampling recomputes candidate statistics on a stationary block bootstrap
replicate; presentations are stateless; about **20 presentations per decision**;
tolerance **0.80**. **Pick subsample: every accepted pick** (amendment 11); meta
moves: the first 10 runs per level. A kind below 10 decisions is **unmeasured with
its count**.
- *A kind at or above 0.80:* not priced locally. *Below 0.80:* priced locally from
  then on, and a liberal local price drops the run to the class tier.
- *Detectable:* at 10 decisions the Wilson interval on a rate of 0.8 is [0.49,
  0.94], so only a rate far below tolerance is seen.

**(7) Check 4: tier power at matched actual size, on the unsaturable arm.** The
replay tier's CERTIFIED rate against the class tier's, at nearest-the-bar, at
thresholds matched on the same arm's β = 0 runs. **At n = 20 the attainable actual
sizes are multiples of 0.05**, so 0.05 is one rejection of 20; reported as such.

**Descriptive, gating nothing:** `p_class − p_trigger` per run; the bracket rate;
trigger changes; and the behavioural readouts (moves to submit, `pick_prior`, near-
duplicate pairs evaluated, accepted picks) under definitions 1–4 above.

### The standing check

Before the agent half is read, **every rule above is run on the scripted half's
draws with the scripted searchers in place of the agent**, and the rate at which a
correct procedure passes each rule is written into this file beside the rule. The
numbers above for rules 1 and 2 are the binomial bounds; the scripted half replaces
them with measured rates on this panel.

## Cost

- **Scripted half, box.** 6 searchers × 4 levels × 2,000 panels, each priced at the
  class tier over 82,240 members on T = 3,019. The class maximum is the cost:
  **150 s of CPU per panel** measured alone, **250 s** median with 7 workers on an
  8-core laptop (the preflight). Planted panels at
  different levels share the residual draw but not the streams, so 8,000 class
  passes ≈ **333 CPU-hours**; on the c7a.8xlarge (32 cores) about **10–12 hours**,
  about **$15–20**. The searchers' own scoring is small against that.
- **Agent half, seat.** 60 + 42–60 + 60 = **162–180 runs**, at 6.5's measured
  $0.075–0.123 per run: **$12–22**. Check 2's re-presentations: about 10 picks
  and 30–40 meta decisions × 20 presentations ≈ **800–1,000 model calls**,
  separately costed at the live commit.
- **Pricing, box.** Each agent run's class table is built for its own planted
  panel (82,240 × 3,019, about 2 GB), used, and deleted: about 3 min to build plus
  0.5–2 min to price, so **about 15 CPU-hours** for 180 runs.

**Cost threshold and lever order, registered before the curve.** If the scripted
half's measured cost on a 200-panel scaling curve (smoke block) exceeds **$40**, the
levers are taken in this order, each only as far as needed: (1) draws per level
2,000 → 1,000, with rule 1's detectability restated at 1,000; (2) the two searchers
whose continuation duplicates another's (`LookaheadStopWhenCleared`,
`RandomExtendWhileImproving`) dropped, with the reason recorded; (3) level 0.5
dropped from the scripted half, if nearest-the-bar is already decided without it.
The class, B and the levels used by the agent half are never levers.

## Standing items

- **Smoke and scaling block: 980000–980999**, dedicated and cost-only: wall time,
  memory and guard counts, **no rule quantity printed** (`prereg/README.md`).
- **Seed blocks**, checked 2026-10-01 against **every** pre-registration in `prereg/`
  and the ten removed ones in history (34 files, 74 explicit ranges, master seeds
  20260916, 20260924, 20260925, 20260929, 20260930, 20261001 expanded to 5,000 draws
  each): **no collision.**

  | block | use |
  |---|---|
  | 600000–601999 | scripted half, panel seeds, shared across levels |
  | 610000–611999 | scripted replication (rule 1's one-shot branch) |
  | master 20261010 | agent panel seeds, shared across arms by index |
  | master 20261015 | agent replication (rule 1's one-shot branch) |
  | 640000–640999 | design (the preflight below used 640000–640019) |
  | 980000–980999 | smoke and scaling, cost only |

  Reproducible: `python -m experiments.seed_block_check --exclude prereg/planted-edge.md
  --ranges 600000-601999,610000-611999,640000-640999,980000-980999 --masters
  20261010,20261015` prints NO COLLISION. The two new masters' draws also miss the
  new ranges, and each other.
- **Replication branch on a registered fresh block for the first failure of any
  validity rule** — 610000–611999 scripted, master 20261015 agent; once, at
  identical settings.
- **No SPY reference arm.** 6.5 is the liquid real-data anchor, graded at 6.9.

## Build items, before the live commit

1. `environments/planted_panel.py`: the registered generator, reproducing
   `experiments/planted_edge_preflight.py`'s planted scale and `SR_pop` on the
   design seeds to 1e-12.
2. The sealed holdout generator and archive, with its SHA-256 in this file.
3. Feature-name masking in the agent-facing view, with a test that no real name
   crosses.
4. `price_runs` for planted panels: per-run class table built on the box, the
   class tier and the population truths written into the run file.
5. `fidelity.py --live`, for check 2.
6. If it is to run: `short_list` and the prior-weighted pricing.
7. The unsaturable arm's cap in the harness, with a refusal test.
