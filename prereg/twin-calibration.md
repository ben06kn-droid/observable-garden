# twin-calibration (item 5): the agent as its own null

**DRAFT — committed but not live.** Authorises nothing. A new Phase 7 item.
**This one changes what certifies.** Literature search 2026-09-30 (`docs/RELATED_WORK_2026.md`) found no prior
replay of an adaptive search's logged decisions inside a data-snooping null,
and no mixed replay/max-over-alternatives pricing. Not a proof of absence. The note below stands.

## Question

Every certifier built so far prices the search the *log* records. Anything the
grammar missed — unfaithful reasons, fill errors, search the agent never logged —
is invisible to it. Re-running the same agent on data where the null holds by
construction prices whatever it actually did, logged or not. Does that work, and
what does it cost?

## Design

Run the **same agent** — same prompt, same model, separate sessions — on **K
placebo twins** of the dataset, in which the null holds by construction. Compute
the gate's own p-value on the real run and on each twin. The reported p-value is
the real run's rank among them:

    p = (1 + #{twins with p_k <= p_real}) / (K + 1)

Under the twin null the K+1 runs are **exchangeable**, so this controls type-I at
any K. The construction is the permutation-test logic of Phipson & Smyth,
*Permutation p-values should never be zero*, Statistical Applications in Genetics
and Molecular Biology 9(1):Article 39, 2010 (arXiv:1603.05766). **Read-level: opened
in full.** Its argument is directly the one this item needs — that a permutation
or Monte Carlo procedure should be read as **generating an exact discrete null
distribution**, not as estimating a tail probability, and that the naive
`#/K` form understates the p-value by about `1/K`. The `(1 + #)/(K + 1)` form
above is the correction, and it is the same form the gate already uses for its
bootstrap p-values.

**The replay null becomes the test statistic, not the certifier.** Replay, the
class gate and item 1's bracket explain *why* a run ranks where it does; the twin
rank is what certifies.

### Twin construction — this IS the null hypothesis

What a twin destroys is what the test can detect. State it per testbed.

- **Synthetic:** a fresh s0 draw, or a joint time-permutation of returns against
  features.
- **ADR (7.4):** re-pair mornings with afternoons from different days, using the
  **same permutation across names** so cross-sectional structure survives.
- **Any return-derived feature is recomputed from the permuted returns**, so a
  twin is not detectable by internal inconsistency.

**Limits, stated in advance:** day permutation destroys volatility clustering;
block permutation is approximate; circular shifts leave a seam. A twin that an
agent could identify is not a twin, and each of these gives it a way to try.

### Masking

Tickers and calendar dates are masked, so memorised price history cannot break
exchangeability. **This is in tension with 7.4's theory-driven picks**, which
need to know what a name *is*. Resolution: expose **structural metadata without
identity** — whether a name has a home market, that market's close time, sector,
liquidity band — so a theory-driven pick remains possible while the specific
security does not. **7.4's pre-registration must state how it resolved this**;
this file records the constraint, not the resolution.

### K, and sequential stopping

**K = 19 for α = 0.05; K = 99 for α = 0.01.** These give attainable levels of
exactly 1/20 = 0.05 and 1/100 = 0.01, verified.

**Sequential stopping is NOT registered here.** Stopping early once a clear
failure is evident would save most of the cost, and the sequential Monte Carlo
construction that keeps it exactly valid is Besag & Clifford (1991), already
logged in `OPEN_QUESTIONS.md`. That entry records two unresolved checks — the
validity argument is for i.i.d. replicates, and the stopping rule interacts with
the full-class maximum in a way not yet checked. **Until those are resolved,
every certification runs the full K.** Registering early stopping without the
check is exactly the kind of shortcut this repository exists to refuse.

### Interaction with item 2

If prior-weighted α is active, the twin statistic is the **weighted min-p**:
`min(p_prior / α_prior, p_search / α_search)`.

### Readouts

- **The gap** between the log-based p-value and the twin-calibrated p-value, per
  run. This is the measured size of **latent forking** — what the log missed.
- Reported per run and pooled.

## Free check, done now, exploratory

**The stored s0 agent runs are twins of one another.** Computed on 419 graded s0
runs, rerunning nothing:

| quantity | value |
|---|---|
| KS against U(0,1) | D = 0.0991, **p = 4.9e-04 — rejects** |
| rejection rate at 0.10 | 6.92% (4.86–9.76) |
| rejection rate at 0.05 | 3.58% (2.18–5.82) |
| rejection rate at 0.01 | 0.72% (0.24–2.08) |
| mean p-value | 0.5683 |
| median p-value | 0.5791 |
| **5th percentile** | **0.0661** (95% bootstrap 0.0488–0.1159) |

So the class gate's p-values on these runs are **not uniform** but are **shifted
conservative** (mean 0.57 against 0.50), and a threshold of **0.066** would give a
true 5% rate. The bootstrap interval on that percentile includes 0.05, so the
departure at the 5% point is not itself established.

**This holds only for a fixed agent and configuration.** It is exploratory, not
pre-registered, and is not evidence about any other agent, model or dataset.

**The 0.0661 threshold is used nowhere.** It is not a calibration, not a
recommended cut-off, and enters no rule in this or any other file. It is reported
because it is the natural summary of what a twin pool says about a gate's
realized size, and for no other reason. Any later use of it would require its own
pre-registration.

## Decision rules

1. **Scripted twins hit nominal on s0 (primary).** Scripted searchers with twins:
   the rejection rate at the attainable levels — exactly 1/(K+1) and its
   multiples — with the Wilson interval containing nominal. *Passes 0.9548 at
   α = 0.05 for a correct procedure.* The attainable grid is stated with the
   result so a rate "below nominal" is not read as conservatism when it is
   discreteness.
   - *Holds:* exchangeability is implemented correctly.
   - *Fails high:* the twins are not exchangeable with the real run — the
     construction is detectable, or masking leaked. Halt.
   - *Fails low beyond discreteness:* over-conservative, reported with its size.
2. **Twins correct what the log-based null misses (primary).** Add an
   **unfaithful searcher** — one whose logged moves do not match what it did. Its
   log-based p-value should be liberal; its twin-calibrated p-value should not.
   - *Twin-calibrated rate at nominal while log-based exceeds it:* the case for
     the whole item.
   - *Both liberal:* the twins are not catching it, and the item does not do what
     it claims. Reported plainly.
3. **The latent-forking gap, reported not gated.** Distribution of
   `p_twin − p_log` across runs.

## Cost — the binding constraint

Sized from the 661 stored agent runs: **mean $0.268 per run** (median $0.220,
90th percentile $0.473), mean wall time 160 s.

| | runs per certification | seat cost | serial seat-hours |
|---|---|---|---|
| K = 19 (α = 0.05) | 20 | **$5.35** | 0.9 |
| K = 99 (α = 0.01) | 100 | **$26.77** | 4.5 |

**Proposed design, given that cost.**

- **Synthetic cells: a shared pool of population-level twins.** 419 graded s0
  runs from the same agent and config already exist. For a fixed agent and
  config, twins of the *process* need not be twins of the *dataset*, so one pool
  serves many certifications at zero marginal cost. The free check above is that
  pool used exactly this way. **The limitation is registered: a shared pool tests
  the agent-and-config, not the dataset**, so it cannot detect a dataset-specific
  failure.
- **Per-dataset twins are reserved for a small number of 7.4 certifications**,
  where the dataset is the thing in question and a shared pool would not answer
  it. At K = 19 that is $5.35 each; **five such certifications is $27 and about
  4.5 seat-hours**, which is affordable and is the registered budget.
- K = 99 is **not** budgeted for routine use. It is reserved for a single
  headline certification if one is wanted at α = 0.01.

## Amendment — 2026-10-02, still not live. A scripted twin cell on planted panels

**Not live; nothing runs on it.** It adds a scripted cell on **real features**, where
rule 1 above ("scripted twins hit nominal") has so far only an s0 statement. It goes
live by a dated commit, which needs one input this file cannot supply: the planted
level, below.

### Panels

`environments/planted_panel.py` (7.5's generator, `prereg/planted-edge.md`): the real
ETF feature matrix X, 2006-01-04 to 2017-12-29, and a resampled real residual with one
depth-3 member planted. **Two levels per panel, paired on one seed**: **level 0**, the
unplanted panel (`c = 0`), where every member's population Sharpe is negative; and
**one planted level, fixed as 7.5 stage 1's nearest-the-bar** by the dated commit that
makes this cell live. That level is not chosen here and cannot be chosen after this
cell's data. **Panel seeds 650000–650999**, replication 660000–660999, smoke and
scaling 985000–985999 (cost only). All three were checked on 2026-10-02 against every
pre-registration, live and removed, `planted-edge.md`'s blocks included
(`python -m experiments.seed_block_check --exclude prereg/twin-calibration.md --ranges
650000-650999,660000-660999,985000-985999`: **NO COLLISION**, 34 files, 100 ranges, 8
masters).

### Per panel

The real panel and **K = 19 twins under each of `joint_time_permutation` and
`block_permutation`** (`quixote/twins.py`, block 21), seeded by `SeedSequence(seed)`'s
children [3] and [4]. Children [0]–[2] are the panel's own, and the same permutations
serve both levels. **Each of the six registered scripted searchers**
(`registered_71`, class-capped to signed depth 3) runs on the real panel and on all
38 twins. **The statistic is the class tier's p** (the certifying tier, ROADMAP
2026-09-30), at **B = 1,000**. **p is the registered rank**,
`(1 + #{twins with p_k ≤ p_real}) / (K + 1)`, with ties counted against the real run
as registered; tie counts are reported. Only α = 0.05 is attainable at K = 19.
Driver: `experiments/planted_twins.py`, with `tests/test_planted_twins.py`.

**What a twin is on this panel.** A twin permutes the **rows of the panel's return
matrix against X**, which stays in calendar order. Positions are a function of X
alone, so **every member's cost and borrow path is identical in the real panel and
in every twin**, and only the gross return differs (tested). The rule above that
"any return-derived feature is recomputed from the permuted returns" is **vacuous
here**: X comes from real prices, not from the panel's returns, in the real panel as
much as in a twin. **Each matrix is priced by one procedure**: its own null block
length from its own depth-1 (+) streams, and its own B replicates from
`default_rng(panel seed)`. The real panel's statistic is not computed differently from
a twin's, which exchangeability needs.

### What each construction destroys on this panel, and the predicted direction

| | destroys | keeps |
|---|---|---|
| `joint_time_permutation` | the alignment of `X_t` with `r_t` (the null under test, including the planted signal's timing); **all serial structure of the returns** — the residual's autocorrelation and volatility clustering, which the stationary bootstrap carries within its blocks (mean 7 days) | each day's cross-section; every member's cost path exactly; the time-mean return vector — at a planted level, the static part of the planted signal |
| `block_permutation` (21-day blocks) | the alignment, across about 144 block seams; serial structure only at the seams | within-block serial structure (blocks three times the bootstrap's mean block length); the cross-section; costs; the time mean |

**Predicted, at level 0.** The real panel and its twins differ only in serial
structure, since the alignment they also differ in is null there. **The direction of
any departure from 1/20 follows the sign of the real streams' short-lag
autocorrelation.** Positive autocorrelation makes the real panel's Sharpes more
dispersed than its joint-time twins', so the real run ranks extreme too often:
**liberal**. Negative makes it **conservative**. The sign is recorded per panel (the
median lag-1 autocorrelation of the real panel's member streams in the first chunk) and
read with the rule. It is not chosen after it: the prediction is the mechanism, and the
read says which sign the panel had. **Predicted small either way**, and **closer to
1/20 under `block_permutation`** than under `joint_time_permutation`, because blocks
keep the serial structure the mechanism runs through.

**Predicted, at the planted level: twin power below the class tier's on the same
panels.** Both constructions keep the time-mean return vector, so the **static
part** of the planted signal survives into every twin: a member whose positions hold
a persistent average aligned with the planted member's average earns in the twins too,
and the real run's statistic stands out only by the time-varying part. The gap is
predicted larger for planted members built on slow features (252-day horizons), and
similar under the two constructions, since both shuffle offsets far longer than those
features' persistence.

### Rules

**(T1) False certification at level 0. One-sided, on the lower Wilson end.** Per
searcher and construction: twin rejections at α = 0.05 (`p_twin ≤ 1/20`), over **all**
panels. At level 0 every member's population Sharpe is negative, so every rejection is
false. **Fails high iff the lower end of the Wilson 95% interval exceeds 0.05.**
- *At or below nominal:* twins are exchangeable with the real panel on real features,
  to this rule's resolution. Reported with the upper end as the largest liberality
  not ruled out, and with the attainable grid (multiples of 1/20; counted ties make it
  conservative) so that "below" is not read as conservatism when it is discreteness.
- *Fails high:* **one-shot replication** on 660000–660999, same n and settings, for
  the **first** failure among the twelve rules. Fails again: the twins are not
  exchangeable with the real panel on real features — the serial-structure mechanism
  is checked first, against the recorded autocorrelation sign — and **twin
  certification is not used on real-feature panels** until it is explained.
  Replication holds: reported as one failure of two.
- *Detectable at n:*

  | n panels | fires at | passes if exactly 1/20 | 80% detects a true rate of |
  |---|---|---|---|
  | 500 | k ≥ 35 (0.070) | 0.9697 | 0.0795 |
  | **1,000** | **k ≥ 64 (0.064)** | **0.9716** | **0.0705** |

- *Family:* 6 searchers × 2 constructions = 12 rules on the same panels. If every one
  is exactly valid and they were independent, all pass **0.69–0.71** of the time,
  **0.99** with the replication branch; they are positively correlated, so the true
  family pass rate is higher.

**(T2) Power at the planted level, reported beside the class tier's on the same
panels. Descriptive; no rule.** Per searcher and construction: **correct** twin
rejections — those whose submission has population Sharpe > 0, following
`planted-edge.md`'s definition — over all panels, beside the class tier's correct
certifications over the **same** panels, with the paired discordance (twin rejects
and class does not, and the reverse). *Predicted:* twin below class, for the
static-part reason above.

### Cost, and the proposed n

**Measured on this laptop, as a component estimate, labelled as one** (2026-10-02): one
512-member chunk of the class pass for all 39 matrices takes **2.3 s** (1.2 s for
positions and streams, 1.1 s for the nulls), and building the 39 count matrices takes
**42 s** per level. So about **410 s per level, about 820 s per panel**, single process
and uncontended. **The end-to-end smoke did not complete**: it was stopped at 10 minutes
of 13, with the laptop on battery at 11%, and its partial record was discarded. Peak
memory per worker is about **1.5 GB** (39 streams of the chunk, 0.48 GB; 39 count
matrices, 0.94 GB). **The box smoke on 985000–985999, at the registered worker count,
is the sizing measurement** (`prereg/README.md`), and it must complete before the live
commit.

**Proposed n: 1,000 panels, the whole registered block.** Under contention at about
1.4× the uncontended figure, that is roughly **320 CPU-hours, about 10 h on 31 workers,
about $17**, and it brings T1's detectable liberality down to **0.0705**. At 31 workers
the memory is about 47 GB of 64. **Lever, registered now:** if the box smoke projects
more than **$30**, n drops to **500** (detectable 0.0795), with the reason recorded.
B, K, the constructions and the searchers are never levers.

## Amendment — 2026-10-02, still not live. A score-rank cell, which runs first

**Not live; nothing runs on it.** It adds a cell **ahead of** the p-rank cell above and
changes nothing in that one.

**The statistic: the searcher's submitted realized net Sharpe**, ranked among its
K = 19 twins in the registered form with **ties counted against the real run**:

    p = (1 + #{twins whose submitted score >= the real run's}) / (K + 1)

A higher score is the more extreme, which is the only change of orientation from the
p-rank form. **No class pass and no bootstrap**: each searcher scores only the supports
it visits, on the real panel and on each twin.

**Levels 0 and 1.0, fixed now**, independent of 7.5's curve. This cell therefore needs
nothing from 7.5 stage 1 and can go live without it. **Same seeds** (panels
650000–650999, replication 660000–660999, smoke 985000–985999), the **same two
constructions** at K = 19 each with the same twin children, the **same rule T1** —
false certification at level 0, one-sided on the lower Wilson end, both branches, the
detectability table above — and the **same replication branch**. At level 1.0, correct
score-rank rejections (submission population Sharpe > 0) are reported per searcher and
construction, descriptively. There is no class tier beside them in this cell, because it
runs no class pass.

**What this cell tests, stated so it is not over-read: the twin constructions, not the
registered p-rank statistic.** Under exchangeability the rank of any statistic computed
the same way on the real panel and its twins is exact, so T1 here asks whether
`joint_time_permutation` and `block_permutation` produce twins exchangeable with the
real panel on real features. The predicted directions are the ones above: at level 0
the departure follows the sign of the real streams' short-lag autocorrelation, is small,
and is smaller under block permutation; at 1.0 the twins keep the planted signal's
static part. **It does not test the statistic the item registers**, the gate's own
p-value ranked among twins. **That p-rank cell stays in this draft as a later cell**,
on the same panels so the two are paired, and goes live by its own dated commit after
7.5 stage 1 fixes its planted level.

**Cost and n** are measured by the laptop smoke on 985000–985999, run to completion,
and recorded by a dated addendum. The proposed n stays **1,000** unless that
measurement says otherwise.

### Addendum, 2026-10-02 — the score-rank cell's cost, measured

**Laptop smoke on 985000–985013, run to completion, cost only** (Apple M3, 8 cores, 7
workers; `runs/_smoke/planted_twins_score/smoke_cost.txt`). **Mains power and Low Power
Mode off at both start and end**, recorded by the smoke; run under `caffeinate`.
Per panel, both levels, 39 return matrices each: **wall median 486 s (mean 448, max 548),
CPU median 416 s (mean 388, max 500)**; the largest wall/CPU ratio is 1.31, which is
contention on 7 workers over 4 performance and 4 efficiency cores, not sleep. **Peak
memory 295 MB per worker.** Throughput: 14 panels in 1,015 s, **about 50 panels an
hour**.

Two earlier attempts are not counted, and are recorded so their absence is not
mistaken for a clean first run: one ran without `caffeinate`, and the laptop
idle-slept mid-run; one was stopped at launch because the machine had gone to
battery with Low Power Mode on. Neither produced a cost line.

**At the proposed n = 1,000:** about **20 hours** wall on this laptop at 7 workers, or
about 108 CPU-hours, **about 3.5 h on the box at 31 workers and about $6**, if a box
core matches a laptop core; the box smoke would settle that. **n stays 1,000**: well
under the $30 lever, and it gives T1 its registered detectability, a true rate of
0.0705 at 80%.
