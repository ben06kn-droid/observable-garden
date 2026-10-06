# 7.5 planted-edge: a known edge, on real features, in agent hands

**STAGE 1 (the scripted half) LIVE from 2026-10-02 (America/Chicago), read and CLOSED
2026-10-04. STAGE 2 (the agent half) LIVE from 2026-10-05 (America/Chicago).** It
replaces 7.4, withdrawn 2026-10-01 (`ROADMAP.md`, "7.4 withdrawn, 7.5 registered").
- A change to anything either stage reads is a dated amendment, appended, never an
  edit.
- Stage 2's terms are its live section at the end of this file ("Stage 2 — LIVE"),
  together with the stage-2 records it names.

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
2026-10-01). The same L is used for the holdout.

**Stated, and checked in code: the generator resamples return blocks independently
of X, and X stays in its original calendar order.** It does **not** resample joint
(X, r) rows. Row t of the panel pairs the real features `X_t` with the residual row
`E[idx_t]` from some other day, so the residual is independent of X by construction,
no real feature–return relation survives into the panel, and the only feature–return
relation present is the planted one. `tests/test_planted_panel.py` asserts the panel's
features are byte-identical to X's rows in order, whatever the seed.

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

**β is set ex ante, as a population net Sharpe.** The population Sharpe of a
specification is **the ratio of the expectation of its per-period net return to its
standard deviation under the planted DGP** — t uniform over the segment's rows, the
residual row drawn from the pool — **computed analytically for any specification**,
not estimated. It is not the expectation of a realized Sharpe ratio. Because the
stationary bootstrap's marginal draw is uniform over the pool (uniform block starts,
circular wrap) and E is demeaned, `E[⟨w_m,t, e⟩] = 0` and
`Var[⟨w_m,t, e⟩] = w_m,t' Σ w_m,t` exactly, with **`Σ = E'E / T`, the pool's own
covariance at ddof = 0**. With the registered cost model (ETF one-way cost and borrow,
as 6.5):

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

**The truth for every specification, and the noise.** `SR_pop` is defined for
**any** member, so every submission has an exact population Sharpe on each segment:
no sampling noise, computed from X, Σ, c and the cost model. That is the outcome
readouts 4 and 5 use. **A member's realized Sharpe on one panel is `SR_pop` plus the
noise of that panel's residual draw — and that noise is exactly what the gate
prices.** Every figure below is labelled population (analytic, no draw) or realized
(one panel's draw).

**Is β = 0 a global null? Measured, not assumed.** Planting `c_0 > 0` gives every
member overlapping `m*` a gross edge, and a member with lower turnover than `m*`
could net positive. **It does, in population.** On 7 design panels (640000–640006,
2026-10-01, `runs/planted_edge_null_check.json`), with `c_0` set so that
`SR_pop(m*) = 0`, the largest **population** net Sharpe in the class is **+0.03 to
+0.91**, and **62 to 23,022 members** are positive. **These are population figures,
computed analytically with no residual draw** (`null_check` never samples), not
realized ones: the positive members are a property of the DGP at that `c_0`, not
noise. A high-turnover `m*` needs a large `c_0` to cover its
own cost, and lower-turnover neighbours collect that gross edge more cheaply.
**"β = 0" defined as `SR_pop(m*) = 0` is not a null.**

**So the β = 0 level is the unplanted panel, `c = 0`** — the residual alone, where
every member has zero gross edge and positive cost, hence `SR_pop < 0` for every
member: **a null for every member**, by construction. Realized member Sharpes on a
β = 0 panel are pure noise around those negative population values, which is what the
gate must refuse to certify. The planted levels 0.5, 1.0 and 1.5 keep the
population-Sharpe definition. **This departs from setting every level by `SR_pop(m*)`,
and is recorded as the reason.** Rule 1's definition of false certification is
nonetheless per specification, so it stays correct if any level's null is partial: **a certificate is false when the certified
submission's in-sample `SR_pop ≤ 0`**, whatever the level.

### The holdout, generated and sealed at registration

The planted process continues into 2018–2022: the same `m*` and `c_β`, the holdout
segment's own residual pool `E_holdout` (demeaned over 2018–2022), resampled with
child [2]. **The seal covers the agent seeds only.** Every
agent panel's holdout returns are generated at the live commit of the agent half,
before any agent run, for every seed and level, written to an archive that is
encrypted and moved off the machine as 6.5's holdout was, with its SHA-256 recorded
in this file, and opened once, after every agent run is priced.

**The scripted half computes its holdout inline**: each scripted panel's holdout
returns are generated from child [2] inside the draw that prices it, used for the
secondary readout, and not stored. Nothing is sealed for it because nothing needs to
be: a scripted searcher is code with no path to the holdout, and its submission is
fixed before the holdout is generated in the same process.

### Masking

Instruments are opaque labels and dates are period indices, per
`prereg/AGENT_PROMPTS_REAL.md` §4. **Feature names are masked too, which departs
from §4** ("Feature names are not masked"). The reason is particular to this panel:
the returns are synthetic, so a real name (`mom252_z`) carries real-world
associations — momentum works, low volatility works — that the planted process does
not honour, and an agent following them would be measured on its priors about
markets rather than on its search. Labels are `F00`–`F39` by a seeded permutation
per panel (child [1]'s stream, after the member draw).

**The confound this removes, and the readout that measures it.** In 6.5, with real
names, agents converged on one feature: **`beta252_z+` in 47 of 80 submissions**, and
`vol252_rank−` in 40, across arms whose prompts differed. Real names, real in-sample
returns and the panel's structure are confounded there. Here returns carry no real
relation and names are masked, so **convergence on a fixed feature is measured, as a
descriptive readout**: per arm and level, the share of submissions containing
`beta252_z` (true index 32, either sign) **on panels whose `m*` does not contain it**,
against its base rate (a uniformly random depth-3 member contains a given feature with
probability 3/40 = 0.075) and against 6.5's 47/80 = 0.59.
- *Near the base rate:* 6.5's convergence was names or real returns, not the features'
  structure. *Well above it:* something in X's structure (its correlations, turnover,
  autocorrelation) draws agents to that feature regardless of name — reported as a
  property of X.

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
and 1.5 because nearest-the-bar is not yet known; it is re-run at nearest-the-bar on
the design block after the scripted half, as information.

**The fallback, registered: the cap is read on the agent, not the proxy.** If the
unsaturable arm's **agent** saturation — submissions equal to the realized class
argmax — **exceeds one half at cap 3** at nearest-the-bar, **check 4 is read as
uninformative** on this arm (both tiers would again be pricing one statistic), and the
next step is registered now: **a signed depth-4 class priced by the moment engine**
(`garden/_full_class_engine.py`). Recorded with it, so the step is not taken blind:
the moment engine prices **linear base columns**, and on a net-of-cost panel the base
basis is diagnostic — positions are normalised and costs are not linear in the weights
— so a depth-4 extension needs its own registration of what statistic it prices
before it runs.

**Recorded beside it, because it changes rule 3. All preflight figures are
REALIZED** — one residual draw per panel — except the planted scale and `SR_pop(m*)`,
which are population. The **realized** class argmax is the planted member on only
**2/20 (β = 1.0) and 3/20 (β = 1.5)** panels: a correlated neighbour of `m*`, with a
luckier residual draw, usually tops the class — **realized** class maximum 1.21
against `m*`'s **realized** 0.93 at β = 1.0 (population 1.00). **Even an exhaustive search
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
the panel without materialising a table of streams** (`ClassTable.null_max`'s
count-matrix device applied per chunk), so no worker holds the 2 GB a table would
need. **In the scripted half** the pass keeps what it computes per member — the
realized Sharpe and the Sharpe on each of the B replicates, an 82,240 × 1,000 matrix
(about 660 MB) — and the searchers, realized and under trigger replay, score by lookup
into those same arrays (`experiments/planted_edge.py`). A searcher's score is then that
member's value in the class pass exactly, and both tiers price one replicate with one
number.

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
on the scripted half's draws. **Both are registered readouts**, each with both
branches below. The preflight puts "equals" at **2–3 of 20** (realized) for the class
argmax itself, so "equals" is expected to be small for every searcher, and its
detectability is stated accordingly.
- *Predicted:* both rising in β, near zero at β = 0, and at or below the exhaustive
  base rate. "Equals" at n = 20 can only show a rate near zero against one well above
  it: at 0/20 the upper Wilson end is 0.161.
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

- **Scripted half, box. Measured, not projected from components:** the smoke on
  980000–980007 (8 panels × 4 levels, B = 1,000, 4 workers on an 8-core laptop,
  2026-10-01, `runs/_smoke/planted_edge/smoke_cost.txt`, cost only) took **808 s per
  seed** for all four levels: class pass 164 s and trigger nulls 39 s per level, the
  rest negligible; peak RSS **846 MB per worker**. For 2,000 seeds that is **449
  CPU-hours** at the laptop's contended per-core speed — about **14.5 h on 31 workers,
  about $24** on the c7a.8xlarge (memory ≈ 26 GB of 64). **Below the $40 threshold,
  so no lever is taken.** The README's sizing rule still applies: it is re-measured on
  the box, at 31 workers, on the same smoke block, before the registered launch.
- **Re-measured 2026-10-02**, after every member's `SR_pop` moved into the run
  (invariants once per run, 87 s, cached; overlap moments once per seed in the first
  level's class pass; every level in closed form). Same block, same 8 panels, same 4
  workers: **1,170 s per seed**, peak RSS 866 MB, projecting 650 CPU-hours and about
  **$34** on the box (`runs/_smoke/planted_edge/smoke_cost.txt`). **That run was
  confounded: the laptop was in Low Power Mode** (on battery charge 21%). Every stage
  slowed by the same factor — generation 1.44×, trigger nulls 1.41× (code unchanged),
  class pass 1.43× (the stage that changed) — so the code itself costs about 1–2 % more
  per seed at equal machine speed, roughly 820–830 s, not 1,170. Both figures are under
  the $40 threshold; the box's own smoke decides.
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

1. **BUILT 2026-10-01.** `environments/planted_panel.py`, the registered generator,
   with `tests/test_planted_panel.py`: X unchanged and in order whatever the seed;
   levels paired; level 0 the residual alone; the scale solving its target; the
   analytic moments matching 4,000-draw Monte Carlo; level 0 a null for every member;
   and, on the ETF data, the preflight's planted member exactly and its scale to within
   the ddof difference (2/T relative).
1b. **BUILT 2026-10-01.** `experiments/planted_edge.py`, the scripted driver, with
   `tests/test_planted_edge_driver.py`; `--smoke` on 980000–980999, cost only.
2. The sealed holdout generator and archive for the **agent** seeds, with its SHA-256
   in this file.
3. Feature-name masking in the agent-facing view, with a test that no real name
   crosses.
4. `price_runs` for planted panels: per-run class table built on the box, the
   class tier and the population truths written into the run file.
5. `fidelity.py --live`, for check 2.
6. If it is to run: `short_list` and the prior-weighted pricing.
7. The unsaturable arm's cap in the harness, with a refusal test.

## Draft revisions

**2026-10-01, four, before anything registered runs.** (1) Population Sharpe defined
as the ratio of the expectation to the standard deviation of the per-period net
return under the planted DGP, analytic for any specification, with the pool's ddof = 0
covariance — the preflight's prototype used ddof = 1, a relative difference of 1/3,019
in the variance term; the β = 0 panel (`c = 0`) is a null for every member; realized
member Sharpes are the noise the gate prices; the generator resamples return blocks
independently of X in original order, not joint (X, r) rows, stated and tested;
preflight figures labelled realized, and the null check's labelled population, which
is what it computed. (2) Recovery: exact match and two-of-three signed overlap both
registered. (3) Masking stands; the departure from §4, its reason, and 6.5's
convergence on `beta252_z+` (47/80) as a readout. (4) Cap 3 by rule, with the fallback
read on the agent: saturation above one half reads check 4 as uninformative and
registers a depth-4 class via the moment engine as the next step.

## Amendment — 2026-10-01, the draft not live. False certification at every level; the population-best member; what the grid is denominated in

**1. False certification is defined at every level as certifying a specification
whose population Sharpe is ≤ 0** — in-sample `SR_pop` of the certified submission, as
defined in Design — **not as certifying a non-planted member.** A non-planted member
with `SR_pop > 0` is a true edge on this DGP, and certifying it is a correct
certificate. Rule 1 is read with this definition at **every level**:
- at β = 0 (`c = 0`) every member has `SR_pop < 0`, so every certificate is false, as
  before;
- at the planted levels the false members are those with `SR_pop ≤ 0`, which on the
  design panels is **51,520–77,402 of 82,240** (table below), so the rule has content
  there too. It is read per level with the same one-sided lower-Wilson rule, the same
  replication branch, and the same detectability at its n.
- **The false-certification rate is per run**: false certificates over **all runs at
  the level, per arm** — a run that issued no certificate counts in the denominator as
  a non-rejection (as `prereg/agent-cell.md` amendment 11 has it), and the scripted
  half reads it per searcher in place of per arm.
- **Power counts correct certificates**: certificates whose submission has
  `SR_pop > 0`, over all runs at the level, per arm (per searcher, scripted). A false
  certificate at a planted level is never counted as power, so rules 1 and 2 partition
  the certificates at every level.
- *Predicted at or below nominal at every level.* The class tier's null is the class
  maximum with **every** member demeaned, which stochastically dominates the maximum
  over the members whose null is true; so a certificate on any `SR_pop ≤ 0` member has
  probability at most α whichever members carry an edge. That is control over the
  false members themselves, not only under the global null, and it is what rule 1 now
  tests.

**2. Is `m*` the population-best member at each level? No, and it is not
guaranteed.** β calibrates `m*`'s own population Sharpe. Every other member loads on the
planted signal through the overlap of its weights with `w*`, and one that overlaps
heavily at lower turnover or lower residual variance carries the same edge more
efficiently. Measured, analytically (no residual draw), on design panels 640000–640006
(`runs/planted_edge_population_levels.json`):

| level | `m*` is population-best | `m*`'s rank, median (range) | population-best shares 2 of 3 with `m*` |
|---|---|---|---|
| 0 | 0/7 | 60,109 | 0/7 (the best is one fixed member, `SR_pop` −0.028) |
| 0.5 | **0/7** | 3,646 (3 – 13,529) | 4/7 |
| 1.0 | **1/7** | 1,086 (1 – 7,744) | 4/7 |
| 1.5 | **1/7** | 216 (1 – 4,268) | 4/7 |

**So recovery is registered against the population-best member as well**, alongside
the two existing rates. With `m⁺` the argmax of `SR_pop` over the class at the panel's
level, per run: the submission **equals `m⁺`**, and the submission **shares at least
two of `m⁺`'s three signed features** (or all of a smaller `m⁺`'s). Rates per level
and arm, Wilson intervals, each beside its exhaustive base rate from the scripted half
(how often the realized class argmax equals or overlaps `m⁺`), with both branches as
rule 3: *near the base rate*, the agent finds what the class's own maximum would;
*well below it*, it misses the edge's best carrier. **Read at the planted levels only**:
at β = 0 `m⁺` is one fixed member with negative `SR_pop`, and recovering it means
nothing. Rule 5's comparison is unchanged, since it already scores each submission by
its own `SR_pop`.

*Build item this adds, recorded so it is not hidden in cost:* `m⁺` needs every member's
`SR_pop` at every panel and level. **Built 2026-10-02**: the panel-invariant moments
(`E[k]`, `E[k²]`, `E[w'Σw]`) are computed **once per run** and cached
(`planted_panel.invariants_for`, 87 s on the laptop); the overlap moments (`E[a]`,
`E[a²]`, `E[ak]`, with `a = ⟨w, w*⟩`) are accumulated **inside the class pass's own
position loop** (`streams_with_overlap`, whose streams are `streams_for`'s bit for
bit); and every level's `SR_pop` follows **in closed form**
(`population_from_moments`), equal to the direct per-level pass to 1e-9
(`tests/test_planted_panel.py`) and reproducing
`runs/planted_edge_population_levels.json` exactly on seeds 640004 and 640001. The
re-measured smoke is under Cost.

**3. What the grid is denominated in.** **β is the planted member `m*`'s in-sample
population net Sharpe**: annualised by √252, net of the registered ETF cost and
borrow, on 2006-01-04 to 2017-12-29, under the planted DGP. **Level 0 is `c = 0`**, the
unplanted panel. **β is not the class's best population Sharpe, and it is not a realized
Sharpe.** Per level, on the 7 design panels:

| level | class maximum `SR_pop`, min / median / max | members with `SR_pop` > 0, min / median / max |
|---|---|---|
| 0 | −0.028 / −0.028 / −0.028 | 0 / 0 / 0 |
| 0.5 | +0.508 / +0.754 / +1.324 | 4,838 / 20,370 / 26,402 |
| 1.0 | +1.000 / +1.207 / +1.759 | 11,541 / 24,874 / 28,867 |
| 1.5 | +1.500 / +1.679 / +2.194 | 16,455 / 27,592 / 30,720 |

**What this means for the curve, recorded and not acted on.** At a given β the best
edge actually available varies across panels — at β = 0.5 from 0.51 to 1.32 — so power
"at β" averages over panels whose strongest member differs by up to 0.8. Rule 2 is read
by β as registered, and nearest-the-bar is still chosen by β. **Added as a descriptive
readout**: power reported again against each panel's class-maximum `SR_pop`, binned,
so the curve can be read in the units of the edge the class actually holds. No rule
reads it.

## Adopted: a two-stage live commit — proposed and adopted 2026-10-02

**Adopted as the plan for going live, by draft revision. Adopting it makes nothing
live: stage 1 goes live only by its own dated commit, after the box smoke, and stage 2
by a second one.** Until stage 1's commit, the whole file remains a draft.

- **Stage 1, the scripted half, live now-ish.** Its build items are done — **1** (the
  generator) and **1b** (the scripted driver), both tested, with the smoke measured.
  A dated commit makes the scripted half live: the design as it stands, the scripted
  rules (1, 2, 3, 5 per searcher, and the standing check), seeds 600000–601999 and
  replication 610000–611999, B = 1,000. The curve then runs on the box.
- **Stage 2, the agent half, by a second dated commit after the scripted read** and
  after build items **2–7** exist and pass their tests. It fixes what only the
  scripted half can supply — nearest-the-bar, the measured standing check, rule 5's
  detectable difference, the exhaustive base rates for recovery — and the sealed
  holdout archive for the agent seeds with its SHA-256.

**Why split.** The agent half's design inputs are outputs of the scripted half, so a
single live commit would either fix them before they exist or leave them to be chosen
after data. Two commits let each half go live with everything it reads already on
record. **What stage 1 must not do:** change anything the agent half registers; a
change found necessary there is a stage-2 amendment, dated, before the agent seeds
are generated.

## Amendment — 2026-10-02, the draft not live. The feature matrix is a pinned file

**The finding.** `environments/real_panel._rank` ranks each period's cross-section with
`np.argsort(np.argsort(row))`, numpy's default **unstable** sort. Where values tie
exactly, the order it assigns depends on the sort implementation, and numpy's x86 and
arm64 builds differ. Found 2026-10-02, when the planted generator's real-data test failed
on a c7a.48xlarge (x86_64, Python 3.14.7, numpy 2.5.3) against the laptop (arm64, Python
3.14.2, numpy 2.5.3). The two builds of the ETF feature matrix from **byte-identical
input data** (combined SHA-256 of the 40 in-sample CSVs `ce4bc21e…`) differ materially in
**two features**:

| feature | segment | cells differing | days differing | largest difference |
|---|---|---|---|---|
| `ret1_rank` (1) | whole panel, 2006-01-04 – 2022-12-28 | **512** of 171,040 | **237** of 4,276 | 0.154 |
| | 2006–2017 | 421 | 196 of 3,019 | 0.154 |
| | 2018–2022 | 91 | 41 of 1,257 | 0.154 |
| `drawdown_rank` (31) | whole panel | **12,022** of 171,040 | **1,823** of 4,276 | 1.231 |
| | 2006–2017 | 9,033 | 1,330 of 3,019 | 1.179 |
| | 2018–2022 | 2,989 | 493 of 1,257 | 1.231 |

Both are ties in the underlying signal: `drawdown` is exactly 0 for every name at its
252-day high, and `ret1` exactly 0 on unchanged prices; on every day checked where
`drawdown_rank` differs, `drawdown` has exact ties. Seven z-score features also differ,
by at most **8.1e-14** (floating-point reduction order), which moves no rank and no
decision. A rebuild on the laptop is byte-identical to the pinned file, so each platform
is deterministic; they disagree with each other.

**Checked, between the features and a member's net stream, for any other sort or rank:**
`real_panel` (`_etf_base_signals`, `_zscore`, `_roll`, `weights_from`, `net_stream`),
`class_table.streams_for`, `planted_panel` (residual, weights, population moments,
planted scale) and `estimator/bootstrap.py`. **`_rank` is the only order statistic over
values.** The other sorts order strings or distinct integers — tickers, dates, a
support's feature indices — and cannot tie. Rolling `max` (drawdown, maxret21) is exact
in any reduction order. `select_block_length` takes a median of per-column block lengths
and rounds it, which a 1e-14 difference could flip only at an exact .5. Downstream of the
streams, the searchers' anchor ranking (`argsort` of single-feature Sharpes) is a sort,
but over computed Sharpes, which do not tie exactly in practice.

**So X is pinned.** The generator (`environments/planted_panel.load_base`) loads
`data/pinned/etf_features_X.npy` — the laptop's build, the X the preflight, the design
analysis and every smoke used — and **refuses on a missing file or a hash mismatch, with
no rebuild fallback**: a rebuild on another platform is a different panel that would
pass every other check. Returns, costs and dates still come from the build: element-wise
arithmetic on the same prices, with no sort.

| | |
|---|---|
| file | `data/pinned/etf_features_X.npy` (gitignored; copied to any box with the ETF data) |
| **SHA-256** | **`4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`** |
| shape | (4276, 40, 40), float64, rows 2006-01-04 – 2022-12-28 |
| built on | arm64 (Apple M3), Python 3.14.2, numpy 2.5.3 |

Tested both ways (`tests/test_planted_panel.py`): a matching hash loads and is what
`load_base` serves; a mismatch, a missing file and a wrong shape are each refused.
**Every run record now carries its platform** (`experiments.code_state.platform_info`),
so a run on another machine says so. Stage 1's live patch names the code commit that
includes this.

### Stated departure, 2026-10-02: the raw in-sample ETF data was copied to a compute box

**What.** `data/raw/etf_insample` — **40 CSV files**, combined SHA-256
**`ce4bc21e64b47d09714308560fa25f39540714dcfba6fb89ab3ee2d34e69df2a`** (the SHA-256 of
`sha256sum *.csv`'s output, one `hash  filename` line per file in name order),
identical on both machines — was copied by `rsync` from the laptop to an EC2
c7a.48xlarge (x86_64, instance `i-0e0c1484de3c755ad`) on 2026-10-02, together with
`data/pinned/etf_features_X.npy`, whose SHA-256 the box computed as
`4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`, the registered value.

**Why it is a departure.** The ETF data protocol (`prereg/etf-universe.md`,
`prereg/agent-on-real-data.md`) has one fetch, on the holdout host, and exports the
in-sample rows to the agent's machine only. A copy to a third machine is not in that
protocol. **No holdout row moved**: these files end on 2022-12-31,
`data/etf_loader.py` refuses any row on or after 2023-01-01, and no agent session runs
on the box.

**Why it was needed.** The planted generator builds returns, costs and dates from these
files, and loads the pinned X beside them. The box's real-data tests pass on them
(`test_the_registered_generator_reproduces_the_preflights_scale`,
`test_load_base_uses_the_pinned_matrix_not_the_build`), so a box run and a laptop run are
the same panel.

## Stage 1 — LIVE, 2026-10-02 (America/Chicago)

**Only the scripted half goes live.** Stage 2, the agent half, stays a draft — its arms and
sizing, the sealed agent holdout, masking, rules 4, 6 and 7, the four reader definitions,
the prior-weighted arm and build items 2–7 — until its own dated commit after the
scripted read.

**What goes live:**
- **Design.** Features are the pinned X (SHA-256
  `4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`, refused on
  mismatch with no rebuild); returns and costs come from the 40 in-sample CSVs (combined
  SHA-256 `ce4bc21e64b47d09714308560fa25f39540714dcfba6fb89ab3ee2d34e69df2a`). The
  residual is resampled in joint-time blocks, independently of X, at block length 7.
- **Levels: 0, 0.5, 1.0 and 1.5.** Level 0 is the unplanted panel (`c = 0`), where every
  member's population Sharpe is negative. At 0.5, 1.0 and 1.5 the planted scale is set so
  that the planted member's population net Sharpe equals the level. The four levels of
  one seed share its residual draw and its planted member, and every member's population
  Sharpe is computed in closed form.
- **Searchers.** The six registered scripted searchers (`registered_71`), class-capped to
  `SubsetClass(max_size=3, signed=True)`, 82,240 members.
- **Nulls.** **Class tier (certifying**, by the tier rule) **and trigger replay
  (audit)**, both at **B = 1,000**, on **identical replicates**: one set of B stationary
  bootstrap index sequences per panel and level, shared by the two tiers.
- **Rules, per searcher and level:**
  - **Rule 1:** false certification, per run: certifying a submission whose in-sample
    population Sharpe is ≤ 0. Fails high iff the lower end of the Wilson 95% interval
    exceeds α, at every level.
    - **The family: 6 searchers × 4 levels × 2 α = 48 tests.** At n = 2,000 a rule
      fires at k ≥ 120 (α = 0.05) and k ≥ 29 (α = 0.01); an exactly valid rule passes
      0.9749 and 0.9664 respectively. **If all 48 were exactly valid and independent,
      all 48 would pass 0.2393 of the time; with the replication branch, 0.9587.** They
      are neither: **predicted conservative** (at level 0 every member's population
      Sharpe is negative, and a sub-maximal search is conservative by P2), and
      **correlated** (the same panels, the same replicates, and searchers that often
      submit the same specification), so the true family pass rate is higher.
    - **A rule-1 failure triggers the one-shot replication before anything else is
      read: the whole block 610000–611999 is rerun at identical settings** — all 2,000
      seeds, all four levels, all six searchers, B = 1,000 — **and every rule that
      failed high is re-read on it.** A rule that fails again is a liberal gate on this
      design; one that holds is reported as one failure of two.
  - **Rule 2:** power, counting correct certificates only.
  - **Rule 3:** recovery of `m*` and of the population-best member `m⁺`, exact and
    two-of-three, beside the exhaustive base rates from the realized class argmax.
  - **Rule 5:** holdout population Sharpe, certified against uncertified within each
    level; secondary, the holdout realization computed inline.
  - Descriptive: power against the panel's class-maximum population Sharpe.
  - **The standing check.**
- **Nearest-the-bar:** the level among {0.5, 1.0, 1.5} whose pooled scripted power at
  α = 0.05 is nearest 50%, ties to the lower.

**Registered now:**

| item | value |
|---|---|
| panel seeds | **600000–601999** (2,000 panels, each at all four levels) |
| replication | **610000–611999**, one shot, for the first failure of any validity rule |
| smoke | 980000–980999, cost only (used: 980000–980007 on the laptop, 980000–980190 on the box) |
| design | 640000–640999. **On record:** 640000–640019 (the budget-cap preflight), 640000–640006 (the β = 0 null check and the population analysis), 640001 and 640004 (the closed form's check against that analysis). **Also used, unrecorded until now:** 640020, for the driver's correctness and timing checks on 2026-10-01 and 2026-10-02 |
| B | **1,000**, both tiers, identical replicates per panel |
| α | 0.05 and 0.01 |
| code | `environments/planted_panel.py`, `experiments/planted_edge.py` at **`6fdd1ba`**; the launch uses `cloud/run.sh` at **`8e923c5`** or later (exact-match tmux targets, so the self-stop can fire) |
| platform | x86_64, EC2 c7a.48xlarge (instance `i-0e0c1484de3c755ad`), shutdown behaviour **Stop** (confirmed in the console); every record carries its platform, and the launch writes the commit hash to the log |
| workers | **191** |

**Box smoke, the sizing measurement** (`runs/_smoke/planted_edge_box/`, commit `58167e8`; run at `6fdd1ba` on 2026-10-03, 01:10:44 UTC, exit 0):

| item | value |
|---|---|
| panels | **191** (980000–980190), all four levels each, B = 1,000 |
| per seed, all four levels | wall median **1,188 s** (mean 1,186, max 1,208); CPU median **1,188 s**; wall/CPU **1.00** (median and max). Per level: class pass 243 s, trigger nulls 50 s |
| peak RSS per worker | **1,035 MB** (about 198 GB of 369 at 191 workers); the invariant population moments, once per run, 167 s |
| projected for 2,000 seeds, **mean throughput** | **3.45 h** wall, **$34** at $9.85/h (plus 167 s for the invariants) |
| projected for 2,000 seeds, **upper bound** (full rounds × the slowest seed) | **3.69 h** wall (11 rounds × 1,208 s), **$36** at $9.85/h |
| against the $40 threshold | **under: $34 against $40, so no lever is taken** (the upper bound, $36, is under too) |

**The $40 threshold reads the mean-throughput projection;** the upper bound is reported
beside it and decides nothing. Fixed here before the smoke ran.

**Before the read:** the results and the run's log are fetched and committed, checked for
exactly 2,000 complete lines and no truncated line, without opening or summarising any
rule quantity. **The reader is committed, and tested on synthetic files in the results'
format, before it opens the results.** The read cites both commits.

**The read, once, after all 2,000 seeds, in this order:** rule 1 per searcher and level
(and, if any rule fails high, the replication on 610000–611999 before anything else);
then rules 2, 3 and 5; then the standing check. Nearest-the-bar, the measured standing
check, rule 5's detectable difference and the recovery base rates are then written into
this file by a dated commit, as stage 2's inputs.

## Amendment — 2026-10-02 (America/Chicago), stage-2 material, not live. The masking rationale corrected; the convergence readout restated

**Stage 1 is untouched.** This changes only text that stage 2's live commit adopts.

**The correction.** "Masking" above says that in 6.5, "with real names, agents
converged on one feature". **6.5's agents never saw a feature name.** The tools take
and return feature **numbers**, 0–39, in one fixed order on every panel: `evaluate`
and `submit` take `features: list[int]`, a support is shown as `[32+, 19-]`, and the
system prompt says only "{K} candidate features". A search on 2026-10-02 found none of
the 40 feature names (`ret1_z` … `maxret21_rank`) anywhere in the **87 ETF run files**
(`runs/etf_*`, `runs/shakeout_etf_orientation`, `runs/agent_pilot_etf_seat`): not in a
system prompt, a tool call, a tool result or the agent's own text. What did cross was
a **stable numbering**: feature 32 was `beta252_z` on every panel and in every run. So
6.5's "beta252_z+ in 47 of 80 submissions" is **convergence on number 32**. Three
things are confounded in it: the fixed numbering, the real in-sample returns, and the
structure of feature 32 in X. Real-world associations of the *name* are not among
them. `prereg/agent-on-real-data.md` carries the matching note.

**What masking does here, restated.** `environments/planted_view.py` (build item 3,
`e558236`) permutes the feature **axis** per panel by `masking_permutation`. Masked
number `j` is true feature `perm[j]`, labelled `F{j:02d}`. The numbering an agent
sees therefore carries no identity from panel to panel, and the returns carry no real
relation to X. **The reason for masking is the numbering, not the names:** a fixed
numbering would let a habit learned on one panel (feature 32) carry to every other.
Names are masked as well, because nothing is lost by it.

**The convergence readout, restated (descriptive).** Per arm and level: the share of
submissions containing **true feature 32** (either sign), counted **only on panels
whose `m*` does not contain feature 32**, under the per-panel shuffled numbering.
- **Base rate:** a submission of depth `d` contains a given feature with probability
  `d/40`, which is 3/40 = 0.075 at depth 3. The base rate for an arm is the mean of
  `d/40` over its counted submissions. 6.5's 47/80 = 0.59 is reported beside it.
- **Near the base rate**, defined as the Wilson 95% interval containing it: feature 32's
  structure in X does not draw the search. 6.5's convergence then came from the fixed
  numbering, the real returns, or both. This readout does not separate those two.
- **Well above the base rate**, defined as the lower Wilson 95% end above it:
  something in X's own structure (its correlations, turnover or autocorrelation) draws
  agents to feature 32 whatever number it carries. That is reported as a property of X,
  and on these panels it is not an edge, since the planted returns ignore it.
- **Below** (the upper end under the base rate) is reported as observed, with no reading
  registered.
- *Beside it, descriptive and proposed for stage 2 to accept or drop:* the same share
  for **masked number 32**, whatever true feature it is. A rate above base there is an
  effect of position in the numbering, which the shuffle separates from X.

## Recorded for stage 2 — 2026-10-02 (America/Chicago), draft, not live. The cap inside the replay null; the instrument labels' stream

1. **The unsaturable arm's cap is enforced inside the replay null, not only in the
   live harness.** The harness refuses the fourth content move (`ToolSession`'s
   `content_cap`, build item 7, `ad825d4`), and the cap is written on the session log.
   Trigger replay as it stands (`quixote/replay.py`) bounds a replicate by the
   declared budget, which is the turn limit (60). A replicate whose triggers never fire
   could therefore make more content moves than the capped agent could, so it would
   price a deeper search than the one that ran. **Registered for stage 2: on a capped
   run, every replicate stops content moves at the same cap and counts them as the
   harness does.** Each of `init`, `extend_best`, `swap_worst`, `flip`, `refine`, `pick`
   and the fill's content step counts one when evaluated; `restart` and `stop` do not.
   After the cap, a replicate ends as the harness would end the live search. It must
   be built and tested (on a replicate equal to the realized data, the capped replay
   reproduces the capped search) before the stage-2 live commit. Until then the
   unsaturable arm's replay tier is not computable as registered.
2. **The instrument labels come from the same stream as the feature shuffle.** The
   feature permutation is child [1]'s stream after the member draw
   (`masking_permutation`). The instrument-label permutation is the next draw from
   that same stream (`environments/planted_view.asset_permutation`, which asserts that
   its feature permutation equals `masking_permutation`). Rows are not reordered.
   Every per-panel random choice stays on one registered stream.

## Stage 1 — paused, 2026-10-02 (America/Chicago), 21:54 CDT (02:54 UTC on 2026-10-03)

**The registered curve was paused at the author's request, partway through. Nothing
was opened.** The run started at 01:52:36 UTC (launch commit `6f55a07`, code at
`6fdd1ba`, 191 workers on the c7a.48xlarge). It was stopped at 02:54 UTC, just after
its third wave of 191 seeds was written.
- **On disk:** `runs/planted_edge_scripted/draws.jsonl`, **573 complete lines**,
  seeds **600000–600572** contiguous, none unparseable (checked by seed count only),
  SHA-256 `9adf6ebfb3c1bb212298f820251675dfba61988c4fbb25592fd157b313945ad4`. It is on
  the instance's volume (shutdown behaviour Stop, so the volume persists) and in a
  copy on the author's laptop outside the repository. **Not committed:** results are
  committed when all 2,000 seeds are complete.
- **Lost:** the fourth wave's seeds had just started and are rerun from scratch.
  Resume is by seed (`experiments/_resume.load_done`): the relaunch runs the 1,427
  missing seeds at identical settings, and a seed's record does not depend on which
  run computed it.
- **The resume uses the same code.** The instance's checkout is not pulled before the
  relaunch, so `planted_panel.py` and `planted_edge.py` stay at `6fdd1ba`, and the
  log's commit line for the resumed run must read `6f55a07`. A different instance type
  or platform is a deviation and is recorded as one.

## Stage 1 — Read, 2026-10-04 (America/Chicago). CLOSED

**Read once**, by the reader committed before the results existed locally (`6236b18`,
`experiments/planted_edge_read.py`, unchanged), on the results committed before any
read (`30ee870`, `runs/planted_edge_scripted/draws.jsonl`, 2,000 complete lines on
600000–601999, SHA-256 `cd7e9f8f…259ce1`). The output is `8660508`
(`runs/planted_edge_scripted/read.txt`). Run at the live commit `bb0dcc4`, code
`6fdd1ba`, launch commit `6f55a07`, paused and resumed by seed (`74fc761`). Nothing
below goes beyond that file.

**Rule 1: all 48 PASS.** No searcher certified a submission with population Sharpe
≤ 0 at any level or either α: k = 0 of 2,000 on every one of the 48 tests (Wilson upper
end 0.0019). **The replication branch was not triggered.** At level 0 no run certified
at all (rule 2, level 0: 0 of 2,000 for every searcher).

**Rule 2, power at α = 0.05 (class tier), per searcher:**

| level | range over the six searchers | pooled |
|---|---|---|
| 0.5 | 0.0400–0.0610 | 0.0484 |
| 1.0 | 0.1665–0.2390 | 0.2035 |
| 1.5 | 0.4100–0.4760 | 0.4391 |

At α = 0.01 the range is 0.0235–0.0350, 0.1050–0.1610 and 0.3180–0.3965. The
trigger-replay tier (audit) is in `read.txt`.

**Rule 3, recovery.** Exact recovery of `m*` by a searcher ranges from 0 to 10 of 2,000
at every planted level. Two-of-three recovery of `m*` ranges from 0.0005 to 0.0835.
Per-searcher figures, and recovery of `m⁺`, are in `read.txt`.

**Rule 5, out of sample.** Certified minus uncertified holdout population Sharpe,
within level and combined over the planted levels, is **+0.8375 to +0.9021** across the
six searchers (secondary, realized: +0.8415 to +0.9056). The per-level SEs are
0.019–0.030 (primary). No run certified at level 0, so that level is n/a.

**The standing check:** with k = 0 at n = 2,000, a procedure with this curve's
false-certification rate passes rule 1 at the agent half's n = 20 with probability
1.000, at every searcher, level and α.

### Stage 2's inputs, written here as registered

- **Nearest-the-bar: level 1.5** (pooled power at α = 0.05 is 0.4391; 0.5 is 0.0484 and
  1.0 is 0.2035).
- **The measured standing check:** 1.000 throughout, as above.
- **Rule 5's detectable difference** at 20 runs per level (10 certified against 10
  uncertified, 80%, two-sided 0.05): **0.4951 at 0.5, 0.6685 at 1.0, 0.8413 at 1.5**.
  The holdout population Sharpe's sd is 0.3954, 0.5339 and 0.6718.
- **Recovery base rates, from the realized class argmax:**

  | level | = m* | 2 of 3 m* | = m⁺ | 2 of 3 m⁺ |
  |---|---|---|---|---|
  | 0.5 | 0.0110 | 0.1355 | 0.0535 | 0.2330 |
  | 1.0 | 0.0450 | 0.2765 | 0.1160 | 0.3610 |
  | 1.5 | 0.1215 | 0.4370 | 0.2230 | 0.5135 |

**Open for the stage-2 live commit, recorded and not resolved here:** the agent half is
registered at "β = 0, nearest-the-bar, 1.5". Nearest-the-bar is 1.5, so as written the
three agent levels are two. Stage 2 must decide how to treat that before it goes live.

**The limits, stated with the result:**
- **48 dependent rules.** Six searchers on the same 2,000 panels and the same
  replicates, several often submitting the same specification. Rule 1's family figures
  assumed independence. Three searchers (stop-when-cleared, cleared-restart,
  lookahead-stop-when-cleared) have near-identical rows throughout.
- **Rule 1 here is a test of a conservative regime.** Level 0's planted panel has every
  member's population Sharpe negative, so k = 0 is what P2 predicts. It shows the gate
  is not liberal on this design. It does not measure how close to nominal it runs.
- **Scripted searchers only.** No agent ran; that is stage 2.
- **Synthetic returns on real features.** These are the planted generator's panels: the
  pinned real X with a resampled, demeaned real residual, independent of X by
  construction, plus one planted member. Real feature-return dependence is not tested.
- **The holdout is the planted process continued** into 2018–2022, with the same
  member and scale. It is not a regime change.
- **How often the class maximum itself clears the bar.** The read reports the
  searchers' power, not the exhaustive search's. Recorded afterwards:

  **Descriptive, outside the registered read, on data already read** (2026-10-04,
  America/Chicago). One pass over `30ee870`'s file (SHA-256 `cd7e9f8f…`) counted the
  panels whose realized class maximum exceeds the stored null quantiles `null_max_q`.

  **This approximates the certificate rule; it is not that rule.** A certificate is
  `p_class = (1 + #{M_b ≥ S})/(B + 1) < α`. The replicates `M_b` were not stored, only
  their 0.95 and 0.99 quantiles, so "class max > q_{1−α}" stands in for it. The two can
  differ only on panels where the class maximum falls within a replicate or two of the
  quantile.

  The ratio column gives each searcher's realized score as a share of its panel's
  realized class maximum, pooled over the six searchers (n = 12,000 per level). The class
  maximum is positive on every panel, so the share is well defined.

  | level | class max > q_0.95 | class max > q_0.99 | median searcher score / class max [q25, q75] |
  |---|---|---|---|
  | 0 | 1 / 2,000 = 0.0005 | 0 / 2,000 = 0.0000 | 0.5049 [0.1635, 0.7490] |
  | 0.5 | 412 / 2,000 = 0.2060 | 268 / 2,000 = 0.1340 | 0.5770 [0.2003, 0.8183] |
  | 1.0 | **1,400 / 2,000 = 0.7000** | 1,039 / 2,000 = 0.5195 | 0.6107 [0.2188, 0.8288] |
  | 1.5 | 1,973 / 2,000 = 0.9865 | 1,909 / 2,000 = 0.9545 | 0.6110 [0.2380, 0.8109] |

**Cost, from the logs.** Two segments at 191 workers on a c7a.48xlarge:
- 573 seeds, 2026-10-03 01:52:36 to 02:54 UTC;
- 1,427 seeds, 2026-10-04 05:07:14 to about 07:42 UTC, exit 0.

That is **about 3 h 37 min of run wall, about $36** at $9.85/h, against the $34
projected from mean throughput and the $36 upper bound. The fourth wave's seeds, just
started at the pause, were rerun. Seconds per seed were 1,184–1,248, as in the smoke.
No seat cost.

**7.5 stage 1 is closed.** Stage 2 stays a draft until its own dated live commit.

## Recorded for stage 2 — 2026-10-04 (America/Chicago), draft, not live. The agent levels, and the unsaturable arm's prompt sentence

**The agent levels are 0, 1.0 and 1.5.** The agent half is registered at "β = 0,
nearest-the-bar, 1.5". The stage-1 read (`8660508`) returned **nearest-the-bar =
1.5**, with pooled power at α = 0.05 of 0.4391, against 0.0484 at 0.5 and 0.2035 at
1.0. As written, the three agent levels would therefore be two. **1.0 fills the third
slot.**

**The reason:** at 1.0 the realized class maximum clears the class tier's 0.05 bar
on **1,400 of 2,000 panels (0.7000)**, and its 0.01 bar on 1,039 (0.5195). The
searchers clear it far less often, with pooled power 0.2035. **Checked
2026-10-04**: the author first stated the figure as about 70%, and the check confirms
it. The check was descriptive, outside the registered read, on data already read,
and it approximates the certificate rule (see stage 1's Limits). At 1.0, then, an
exhaustive search usually certifies and the registered searchers usually do not.
That gap is what the agent half measures. At 1.5 both certify often, and at 0.5 the
class maximum clears the bar on only 0.2060 of panels.

**Descriptive, outside the registered read, on data already read** (2026-10-04,
America/Chicago). One pass over `30ee870`'s file (SHA-256 `cd7e9f8f…`) counted the
panels whose realized class maximum exceeds the stored null quantiles `null_max_q`.

**This approximates the certificate rule; it is not that rule.** A certificate is
`p_class = (1 + #{M_b ≥ S})/(B + 1) < α`. The replicates `M_b` were not stored, only
their 0.95 and 0.99 quantiles, so "class max > q_{1−α}" stands in for it. The two can
differ only on panels where the class maximum falls within a replicate or two of the
quantile.

The ratio column gives each searcher's realized score as a share of its panel's
realized class maximum, pooled over the six searchers (n = 12,000 per level). The class
maximum is positive on every panel, so the share is well defined.

| level | class max > q_0.95 | class max > q_0.99 | median searcher score / class max [q25, q75] |
|---|---|---|---|
| 0 | 1 / 2,000 = 0.0005 | 0 / 2,000 = 0.0000 | 0.5049 [0.1635, 0.7490] |
| 0.5 | 412 / 2,000 = 0.2060 | 268 / 2,000 = 0.1340 | 0.5770 [0.2003, 0.8183] |
| 1.0 | **1,400 / 2,000 = 0.7000** | 1,039 / 2,000 = 0.5195 | 0.6107 [0.2188, 0.8288] |
| 1.5 | 1,973 / 2,000 = 0.9865 | 1,909 / 2,000 = 0.9545 | 0.6110 [0.2380, 0.8109] |

**The runner** is `experiments/planted_agent.py`. Every agent panel is shown through
the masked view (`environments/planted_view.py`) and searched on the fly (no class
table). The unsaturable arm runs with `ToolSession(content_cap=3)`, and the cap is
enforced in the replay null (`3e7a803`). The runner refuses everything but a dry run
on design seeds until this stage's live commit fixes the agent seed block.

### The unsaturable arm's prompt sentence

Appended to the replay-gate prompt for the unsaturable arm only, and to no other arm.
The runner reads it from here and nowhere else:

```
You may make at most 3 content moves in this session. Each call to init, extend_best, swap_worst, flip, refine or pick counts as one, whether you keep its result or discard it. A fourth content move is refused. Declaring triggers, changing a trigger, stop, restart, pick_prior, predict and submit do not count.
```

## Recorded for stage 2 — 2026-10-05 (America/Chicago), draft, not live. The prior-weighted arm is built

The registration says this arm "runs in 7.5 only if `short_list` and its pricing are
built and tested before the live commit". They now are:
- **The tool surface** (`experiments/agent_backend.prior_weighted_tools`).
  `short_list` may be called once, before any `evaluate`, even a refused one. It
  takes up to 5 class members. A late, second, over-cap or out-of-class list is
  refused and logged.
- **The pricing** (`experiments/price_runs.prior_weighted`). It uses the class tier's
  own replicate rows.
- **The planted runner's `prior-weighted` arm**, with the registered prompt.

**The routes, confirmed 2026-10-05 (America/Chicago).**
- **The list route applies only when the submission is on the list.** It compares the
  submission's Sharpe with the maximum over the list of the demeaned replicate Sharpe,
  at α_prior = 0.04.
- **The class tier at α_search = 0.01 applies either way**, on or off the list.
- The run certifies if either route rejects, and the route is recorded (`list`,
  `search`, `both`). False certification per route at β = 0 is read on the submission.

**The size argument.** At β = 0 every member's population Sharpe is negative, so any
certificate is false, and P(certify) ≤ P(list route rejects) + P(search route rejects)
≤ 0.04 + 0.01 = **0.05**. That is the union bound, and it holds **under any dependence**
between the routes. Each term is valid on its own:
- **The list route is a fixed menu.** The list is declared before the agent has seen
  any data. The harness refuses every data-access tool until `short_list` has been
  called, and the prompt carries no data. The list is therefore independent of the
  returns, and Reality Check over a fixed menu of at most 5 members is valid at its
  level (P1).
- Comparing the **submission's** Sharpe rather than the list's maximum can only raise
  the p-value, since the submission is on the list and so its Sharpe is at most the
  list's maximum. That only makes the route more conservative (P2).
- **The search route is the class tier**, valid at 0.01 however the search ran (P3).

Rule 1, on this arm at β = 0, measures the result. The prediction is at or below 0.05,
and conservative, since the union bound is not tight.

**The list comes first, enforced (2026-10-05).** `evaluate` is refused until
`short_list` has been called. An empty list (`supports: []`) is an explicit decline: it
is logged, and the arm then runs with the search route alone. The refusal message
says so. This makes the declaration a required step. The registered prompt says the
agent "may" call it once, so the refusal message is what tells it the call comes first.

**On masked synthetic panels the list is blind.** The features are shuffled per panel
and anonymised, and the returns are synthetic and unrelated to any real-world fact. An
agent therefore has no information from which a prior could point at the planted
member: its list is, in effect, chosen blind. **On this panel the arm is a validity
check of the pricing and makes no power claim.** It measures:
- the size of the two-route procedure at β = 0;
- the share of certificates by route;
- at 1.5, whether a blind list ever certifies.

It does not measure whether a prior that is right pays.

**Still unregistered:** the arm's size per level. The agent table lists it as
"definitions registered below; not run unless built and tested before live", and the
live commit must give its run count.

## Stage 2 — LIVE, 2026-10-05 (America/Chicago)

**The agent half goes live**, as amended by the stage-2 records of 2026-10-02,
2026-10-04 and 2026-10-05. This commit is pre-registration only, apart from the
seed constants it sets:
- `AGENT_SEEDS = range(630000, 630020)` in `experiments/planted_agent.py` and
  `experiments/planted_holdout.py`;
- the replication block, `range(631000, 631020)`.

The shake-out block (`SHAKEOUT = range(632000, 632010)`, model-backed runs into
`runs/_shakeout/` only) is already in the runner (`ad26545`).

**What goes live:**
- **Panels.** `environments/planted_panel.py` on the pinned X (SHA-256
  `4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`), at **levels 0,
  1.0 and 1.5**.
  - Nearest-the-bar returned 1.5 (`8660508`), so **1.0 fills the third slot**. There
    the realized class maximum clears the 0.05 bar on 1,400 of 2,000 panels
    (descriptive, `e317d56`).
  - Agents see the **masked view** (`environments/planted_view.py`) and evaluate on the
    fly. Model `claude-sonnet-5`, thinking disabled, `max_turns = 60`.
- **Arms and sizes.** A run's seed is set by its index: index i is seed 630000 + i,
  in every arm and at every level. Arms are therefore paired on the same panel, and
  levels on the same residual draw.

  | arm | runs | seeds (index) |
  |---|---|---|
  | replay gate | **20 per level, 60** | 630000–630019 |
  | unsaturable, `content_cap = 3`, the cap enforced in the replay null | **20 per level, 60** | 630000–630019 |
  | replay gate (reasoned pick) | **14 per level to start, 42**; then +2 per level (6 runs) until **10 accepted picks** are on record, pooled over the three levels; capped at **20 per level, 60** | 630000–630013, extending in order to 630019 |
  | prior-weighted | **20 at level 0 and 20 at level 1.5, 40** | 630000–630019 |

  - The reasoned-pick stopping rule reads **only the count of accepted picks**, a
    harness fact.
  - At the cap with fewer than 10 accepted picks, check 2 is **unmeasured, with its
    count**.
  - Total: **202 to 220 runs**.
- **The prior-weighted arm** has two routes: the list route at 0.04 (Reality Check over
  the short list, when the submission is on it), and the class tier at 0.01 either
  way. Total size is at most 0.05 by the union bound. `evaluate` is refused until
  `short_list` is called, and an empty list declines. **On these panels the list is
  blind. This arm is a validity check of the pricing and makes no power claim.**
- **Rule 1 is read per arm at every level** (0, 1.0 and 1.5, and 0 and 1.5 for
  prior-weighted), at α = 0.05 and 0.01.
  - A **false certificate** is a run certified by the class tier (`p_class < α`)
    whose submission has in-sample population Sharpe ≤ 0. At level 0 every certificate
    is false; at a planted level only those on a non-positive member are.
  - It fails high iff the lower Wilson 95% end exceeds α.
  - **The prior-weighted arm is read per route:** the list route against 0.04, the
    search route against 0.01, and the run's combined certificate against 0.05.
- **Rules:** (1)–(7) as registered in "Decision rules", with the standing check's
  measured rates (1.000 throughout) and the inputs written at stage 1's close:
  - nearest-the-bar 1.5;
  - rule 5's detectable differences 0.4951, 0.6685 and 0.8413;
  - the recovery base rates.

  Rule 7 (check 4, tier power at matched size) is read on the unsaturable arm at 1.5.
- **Registered descriptive readouts** (no rule reads them), per arm and level, on both
  tiers (the class tier, and the replay tier as audit):
  - **coverage of `L_g`** for g = 0.90, 0.95 and 0.99: the share of runs whose
    submission's in-sample population Sharpe is ≥ `L_g`;
  - **tightness**: the median and quartiles of `SR_pop − L_g`;
  - **`P_5` against the sealed holdout**: the mean stated `P_5`, the observed share of
    runs with realized holdout Sharpe > 0, and the Brier score. These are given for all
    runs and **for certified runs separately, on both tiers**, each by its own
    certificate (the class tier `p_class < 0.05`, the replay tier its verdict's status).
    V3 found `P_5` a floor only where there is an edge (`afdcb53`, `de348ea`), and
    `P_H` is shown only beside a certified verdict (`0290ec5`);
  - **the agent's stated distribution beside the gate's confidence curve**: the
    agent's `predict` (mean μ, sd σ), read as the stated `P(SR > 0) = Φ(μ/σ)`,
    against `C0`; and μ against the gate's median, the smallest grid `s` with
    `C(s) ≤ 0.5`.

**Seed blocks**, checked 2026-10-05 against every pre-registration, live and removed
(`experiments.seed_block_check --exclude prereg/planted-edge.md --ranges
630000-630999,631000-631999,632000-632999`: **NO COLLISION**):

| block | use |
|---|---|
| **630000–630019** (block 630000–630999) | the agent runs |
| **631000–631019** (block 631000–631999) | the one-shot replication for the first rule-1 failure: same arm, same n, identical settings |
| **632000–632009** (block 632000–632999) | the shake-out, never read for any rule |

**The sealed holdout for the agent seeds**, generated in this commit before any agent
run:
- `python -m experiments.planted_holdout --seeds 630000-630019 --levels 0 1.0 1.5
  --out <outside the repository>`;
- 60 panels; **archive SHA-256
  `132eb820f8165111645743b2f5d3c575b8824002a3a36b9aceb2067cefa0ad47`**
  (`planted_stage2_holdout.tar.gz`, 22,551,053 bytes, generated 2026-10-05 on the
  laptop outside the repository). The per-file hashes are in its `manifest.json`. The
  manifest's code state is this live commit's working tree; the returns depend only on
  `environments/planted_panel.py` (`c5e3860`) and the pinned X.
- The operator encrypts it with `openssl enc -aes-256-cbc -pbkdf2`, as for 6.5, and
  moves it off the machine. The plaintext is deleted.
- **It is opened once, after every agent run is priced and the priced files are
  committed**, by `open_sealed` against this SHA-256, for rule 5's secondary readout.
- The replication block's holdout is generated and sealed the same way, in the commit
  that launches the replication, if that is ever needed.

**Shake-out first. Never read; its runs are excluded from every rule.**
- **Which runs:** four model-backed runs, one per arm, on 632000–632003. The replay
  gate, unsaturable and reasoned-pick arms run at level 1.0; prior-weighted runs at
  1.5. Pricing is deferred, and the four files are then priced on the box with
  `price_runs` at B = 1,000. `fidelity.py --dry-run` runs on the reasoned-pick file.
- **What it checks.** Every item must hold:
  1. every file is complete (`end` and `self_check` events), and the grammar arms'
     self-checks are replayable;
  2. **masking:** none of the 40 real feature names, no ticker and no calendar date
     appears anywhere in any file (the search that was run on 6.5's 87 files);
  3. **unsaturable:** at most 3 content moves were made, and any fourth was refused
     with the cap message;
  4. **prior-weighted:** no `evaluate` was accepted before `short_list`;
  5. the served model is the pinned one (`endpoint.agrees_with_prereg`);
  6. `price_runs` computes, for every file:
     - the verdict, with replay integrity PASS on the per-run table;
     - `class_p` with both tiers' confidence fields;
     - `planted_truth`;
     - for the unsaturable file, the cap restored;
     - for the prior-weighted file, both routes;
  7. the cost record: turns, tool calls and wall minutes per run, and pricing seconds
     and peak memory per run on the box.
- **The commands** (seat for the four runs; the box for pricing):

  ```
  for spec in "replay gate|1.0|632000" "unsaturable|1.0|632001" \
              "replay gate (reasoned pick)|1.0|632002" "prior-weighted|1.5|632003"; do
    IFS='|' read arm level seed <<< "$spec"
    python -m experiments.planted_agent --arm "$arm" --level "$level" --runs 1 \
        --seed0 "$seed" --out runs/_shakeout/planted_agent
  done
  git add runs/_shakeout/planted_agent && git commit -m "7.5 stage 2 shake-out: four run files, unpriced" && git push
  ssh og-48 'cd ~/observable-garden && git pull --ff-only && python -m experiments.price_runs --dir runs/_shakeout/planted_agent --workers 4 --B 1000'
  python -m experiments.fidelity --dir _shakeout/planted_agent --panel planted --dry-run
  ```

- **What stops the launch:** any failure of items 1–6; a **projected wall time above
  120 hours for the 202–220 runs, at the concurrency measured in the shake-out**; or a
  pricing projection above **$25** at mean throughput. A stop is reported. **No lever** (arms, n, B, levels, cap) is applied
  automatically.

**Pricing from committed logs.** The run files are committed as they finish, unpriced
(`pricing_deferred`).
- They are priced on the box by `experiments/price_runs.py` at **B = 1,000**, both
  tiers. Each run rebuilds its panel and mask from its seed and level on the pinned X,
  and its class table in memory.
- `price_runs` writes the verdict, `class_p` (with confidence fields and, on that arm,
  `prior_weighted`) and `planted_truth` into each file, before its `end`.
- The priced files are committed **before any reader opens them**.
- The readout `price_runs` prints for a planted directory is counts only.

**Readers committed before the results.**
- **The stage-2 reader is pinned: `experiments/planted_agent_read.py` at `4a8dbae`**
  (re-pinned in this live commit from `7ddc547`, for the certified-separately `P_5`
  readout).
  It was committed, and tested on synthetic priced files and on an end-to-end set of
  priced dry runs, before any result exists.
- **Check 2's rule reader is pinned: `experiments/fidelity_read.py` at `f948ead`.** It
  recomputes agreement from the live presentation log.
- Each runs only if the working copy is byte-identical to its pinned commit
  (`git diff --quiet <hash> -- <file>`). If a reader changes before the live commit,
  its pin is updated in the live commit itself, and never afterwards.
- The sealed holdout is opened only by the reader, after the priced files are
  committed.

**The read, once, after all runs are priced, in this order:**
1. **Rule 1** per arm and level, with the prior-weighted arm per route. **If any rule
   fails high, the replication on 631000–631019 for that arm runs before anything else
   is read.**
2. **Rule 2** (power against the scripted curve), **rule 3** (recovery against the
   base rates), **rule 4** (deflation gap) and **rule 5**: holdout population Sharpe as
   primary, then the sealed holdout opened for the secondary.
3. **Rule 6** (check 2: fidelity, from the `--live` presentations, at the 0.80
   tolerance).
4. **Rule 7** (check 4, the unsaturable arm at 1.5).
5. The prior-weighted readouts: route shares, the list containing or overlapping `m*`,
   and size per route at 0.
6. The registered descriptive readouts above, then the behavioural ones.

**Cost.** Corrected 2026-10-05 from measurements. The earlier 31–57-minute "per run"
figures were not session time: they ran to timestamps of pricing written into 6.5's
files afterwards.

| item | estimate | basis |
|---|---|---|
| **seat, agent sessions** | **about 3 hours of sessions, run one after another** (202–220 runs). That is 162–180 grammar-arm runs at about 0.65 min each and 40 prior-weighted runs at about 1.5 min each. Upper bound, every run at the slowest observed: 220 × 2.4 min = 8.8 h. Far under the 120-hour stop | 6.5's sessions, system prompt to last tool call: replay-gate median 0.63 min (max 1.78), orientation 0.70 (max 2.36), control 1.58 (max 2.29), declared-class 1.44 (max 2.02). Model latency is about all of it: 1.7 s median between grammar calls, 0.5 s between `evaluate` calls, against 0.01 s of harness per call |
| seat, check 2 | on the order of 1,000 short, stateless calls, each about one model latency | `fidelity.py --live` prints the exact count and needs `--yes` |
| **pricing, box** | **about 282 s per run with the current code**, measured. 220 runs is about 17 CPU-hours. At about 140 workers (2.5 GB each), that is 2 waves of about 5 minutes. **About $2–4 with boot, against the $25 threshold** | one planted dry-run file (4 logged moves; 6.5's replay logs have a median of 5), design seed 640063, B = 1,000, on the laptop on battery in Low Power Mode: class table 176 s (63%), replay verdict 86 s (31%), class tier 17 s, truths 2 s |
| holdout generation | 60 panels, minutes, on the laptop | `planted_holdout` |

### Stage 2 — the sealed holdout encrypted and moved off the machine, 2026-10-05 (America/Chicago)

Reported by the author and recorded here:
- The archive (`planted_stage2_holdout.tar.gz`, SHA-256 `132eb820…cefa0ad47`) was
  encrypted with `openssl enc -aes-256-cbc -pbkdf2 -salt`. The round trip (decrypt,
  then SHA-256) matched the registered hash.
- **The encrypted archive's SHA-256 is
  `c64eb3ca32a2c1d2b4b80cbe9707ed081da979a2023309b75e119441949d16cd`.** It was copied
  to a flash drive and verified identical on both copies.
- The plaintext archive, the plaintext directory and the laptop's `.enc` were deleted.
  `~/og_sealed/` was checked empty on 2026-10-05.

The holdout is opened once, after every agent run is priced and the priced files are
committed: decrypted against this `.enc` hash, then opened by `open_sealed` against
the registered plaintext hash.
