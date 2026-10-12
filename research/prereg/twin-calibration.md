# twin-calibration (item 5): the agent as its own null

**DRAFT — committed but not live, EXCEPT the score-rank cell, LIVE from 2026-10-02**
(the section "Score-rank cell — LIVE" at the end). Everything else here authorises
nothing. A new Phase 7 item.
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

## Amendment — 2026-10-02, not live. Both twin cells run on the pinned X

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

**Both cells read X through `environments/planted_panel.load_base`, which now loads the
pinned file** (SHA-256 `4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`)
and refuses anything else, with no rebuild. The laptop smoke on 985000–985013 ran on the
laptop's own build, which is byte-identical to the pinned file, so its cost stands. A
box run copies the pinned file with the ETF data; every record carries its platform.
The score-rank cell's live patch names the code commit that includes this.

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

## Score-rank cell — LIVE, 2026-10-02

**Only the score-rank cell goes live** (the amendments and addenda of 2026-10-02 above).
The p-rank cell and everything else in this file stay drafts. From this commit, a change
to anything this cell reads is a dated amendment, appended, never an edit.

**This cell tests the twin constructions, not the registered p-rank statistic.** Under
exchangeability the rank of any statistic computed the same way on the real panel and
its twins is exact, so T1 asks whether `joint_time_permutation` and `block_permutation`
produce twins exchangeable with the real panel on real features. The p-rank statistic —
the gate's own p-value ranked among twins — is a later cell in this draft.

**What runs.** On each panel, at **levels 0 and 1.0**, the real panel and **K = 19 twins
under each of `joint_time_permutation` and `block_permutation`** (block 21; twin children
[3] and [4] of `SeedSequence(seed)`, shared by both levels), and the **six registered
scripted searchers** (`registered_71`), class-capped to signed depth 3. **Statistic:
each searcher's submitted realized net Sharpe**; **p** is its rank among the 19 twins,
`(1 + #{twins scoring ≥ the real run}) / 20`, ties counted against the real run. An
empty real submission ranks at p = 1, and an empty twin submission never counts against
the real run (both tested). **X is the pinned file**, SHA-256
`4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba`, refused on mismatch
with no rebuild; returns and costs come from the 40 in-sample CSVs, combined SHA-256
`ce4bc21e64b47d09714308560fa25f39540714dcfba6fb89ab3ee2d34e69df2a`.

**Registered now:**

| item | value |
|---|---|
| panel seeds | **650000–650999, n = 1,000**, both levels paired on each seed |
| replication | **660000–660999**, n = 1,000, one shot, for the **first** failure among the twelve T1 rules |
| smoke | 985000–985999, cost only (used: 985000–985013 on the laptop, 985000–985190 on the box) |
| levels | **0** (unplanted; every member's population Sharpe negative) and **1.0** (the planted member's population net Sharpe) |
| K | **19 per construction**; α = 0.05 the only attainable level |
| code | `experiments/planted_twins.py --cell score` and `environments/planted_panel.py` at **`a3ac38b`** (the score cell's code is unchanged since `c5e3860`; the box smoke ran at `a3ac38b`) |
| platform | **x86_64, EC2 c7a.48xlarge** (instance `i-0e0c1484de3c755ad`), Ubuntu 26.04, Python 3.14.7, numpy 2.5.3; every record carries its platform, and the launch writes the checked-out commit hash to the log |
| workers | **191**, under `cloud/run.sh` (one BLAS thread per process) |

**Measured cost on this box** (smoke on 985000–985190, 191 panels, 191 workers;
`runs/_smoke/planted_twins_score_box/`, commit `f840875`): per panel, both levels, 39
return matrices each, **wall median 338 s** (range 210–428), **CPU median 338 s**,
**wall/CPU 1.00**; peak memory **441 MB per worker** (about 84 GB of 369); throughput
**1,587 panels per hour**. **For n = 1,000: six rounds, about 40–45 minutes, about 94
CPU-hours, about $7 at $9.85/h** (about $9 with the self-stop's 10-minute fetch
window). No seat cost.

**Before the read: the results are fetched and committed, and only then opened.**
`runs/planted_twins_score/draws.jsonl` and the run's log are copied from the box,
checked for exactly 1,000 complete lines and no truncated line, and committed **without
opening or summarising any rule quantity**. **The read cites that commit's hash**, so
the data it reports on is fixed in history before any number in it is seen.

**The read, once, after all 1,000 panels, in this order:**
1. **T1 per searcher and construction — 6 × 2 = 12 rules.** Score-rank rejections at
   α = 0.05 (`p ≤ 1/20`) at **level 0** over all 1,000 panels; every one is a false
   certification, since every member's population Sharpe is negative there. **Fails
   high iff the lower end of the Wilson 95% interval exceeds 0.05 — at n = 1,000, iff
   k ≥ 64 of 1,000.** An exactly valid rule passes 0.9716; 80% detects a true rate of
   0.0705. The family pass rate — 0.69–0.71 for twelve independent valid rules, 0.99
   with the replication branch — is reported beside the twelve.
   - *At or below nominal:* the construction is exchangeable with the real panel on real
     features, to this resolution; the upper end is reported as the largest liberality
     not ruled out.
   - *Fails high:* the **one-shot replication on 660000–660999** runs before anything
     else is read. Fails again: the construction is not exchangeable on real features,
     and twin certification is not used on real-feature panels until it is explained.
     Replication holds: reported as one failure of two.
   - *The predicted direction is read against* `median_lag1_autocorr_signed_singles`,
     recorded per panel and level: **the median, over the real panel's 80 signed depth-1
     members (every feature at +1 and at −1), of each net stream's demeaned lag-1
     autocorrelation**, Σ_{t≥2} x̃_t x̃_{t−1} / Σ_t x̃_t². Its median across the level-0
     panels gives the sign: positive predicts a departure above 1/20 (liberal), negative
     below (conservative), small either way and smaller under block permutation. **This
     is not the p-rank cell's figure** (the median over the first class-pass chunk's 512
     members); this cell reads only its own.
2. **Level 1.0, descriptively:** correct score-rank rejections (submission population
   Sharpe > 0) per searcher and construction, with Wilson intervals. No class tier is
   beside them in this cell, and no rule reads them.

**No interim read.** The run's log prints only the commit hash and per-seed wall time
and peak memory. **Resume is by seed**: a relaunch skips every seed on record and redoes
the rest from scratch, deterministically; a truncated last line from an interrupted
write is dropped and its seed redone (`load_done`, tested).

## Score-rank cell — Read, 2026-10-02. CLOSED

**Read once**, by the reader committed before it opened the results (`26e3a0e`), on
the results committed before any read (`1affdd1`); the output is `1fc432a`
(`runs/planted_twins_score/read.txt`). 1,000 panels on 650000–650999, run at the live
commit `f43c812`. Nothing below goes beyond that file.

**T1 at level 0 — all twelve PASS.** k score-rank rejections at α = 0.05 of 1,000
level-0 panels; the rule fires at k ≥ 64.

| searcher | joint-time permutation | block permutation |
|---|---|---|
| stop-when-cleared | 32 (0.0320) [0.0228, 0.0448] | 39 (0.0390) [0.0287, 0.0529] |
| extend-while-improving | 32 (0.0320) [0.0228, 0.0448] | 39 (0.0390) [0.0287, 0.0529] |
| cleared-restart | 32 (0.0320) [0.0228, 0.0448] | 39 (0.0390) [0.0287, 0.0529] |
| lookahead-stop-when-cleared | 33 (0.0330) [0.0236, 0.0460] | 39 (0.0390) [0.0287, 0.0529] |
| random-extend-while-improving | 25 (0.0250) [0.0170, 0.0366] | 48 (0.0480) [0.0364, 0.0631] |
| second-best-while-improving | 32 (0.0320) [0.0228, 0.0448] | 45 (0.0450) [0.0338, 0.0597] |

No ties and no empty submissions on any rule. **The replication branch was not
triggered.** Each upper Wilson end is the largest liberality the data do not rule out:
at most 0.0448–0.0460 under joint-time permutation (0.0366 for
random-extend-while-improving) and 0.0529–0.0631 under block permutation.

**The autocorrelation sign, and the prediction: it held.** The median across the 1,000
level-0 panels of `median_lag1_autocorr_signed_singles` is **−0.063514**, negative on
998 panels and positive on 2. Registered, that predicts a departure **below** 1/20,
small, and smaller under block permutation. All twelve rates are below 0.05, and every
block-permutation rate (0.0390–0.0480) is nearer 0.05 than the same searcher's
joint-time rate (0.0250–0.0330).

**Level 1.0, descriptive; no rule reads it.** Correct rejections, those with submission
population Sharpe > 0, are **450–463 of 1,000 under joint-time permutation and 499–509
under block permutation**, Wilson intervals in `read.txt`. **29 rejections were of
submissions with population Sharpe ≤ 0**, every one negative (−0.047 to −0.443), on
seeds 650086, 650686, 650706, 650789 and 650839, listed in full in `read.txt`.

**The limits, stated with the result:**
- **Twelve dependent rules.** Six searchers on the same 1,000 panels, several submitting
  the same specification, are not twelve independent tests. Four searchers give
  identical counts under both constructions. The family figures registered beside them
  assumed independence.
- **Score-rank, not p-rank.** This tests whether the two twin constructions are
  exchangeable with the real panel on real features, for the submitted-score statistic.
  It does **not** test the registered p-rank statistic, the gate's own p-value ranked
  among twins. That cell remains a draft.
- **Scripted searchers only.** No agent ran. Whether an agent's search keeps twins
  exchangeable is untested.
- **Synthetic returns on real features.** The panels are the planted generator's:
  real X (pinned, `4b461070…b7ba`) with a resampled real residual, independent of X by
  construction. A real return series, with real feature-return dependence, is not tested
  here.

**Cost, from the run's log:** 1,000 panels in **34 min 01 s wall** (2026-10-03,
00:06:58–00:40:59 UTC); per panel, wall median 349 s (178–555); peak 444 MB per worker;
about 97 CPU-hours. **About $5.58 for the run** at $9.85/h, **about $7.22 with the
self-stop's 10-minute fetch window**, against the $7–9 projected from the box smoke.
No seat cost.

**The score-rank cell is closed.**

*Correction to the Read section above, 2026-10-02:* "Four searchers give identical
counts under both constructions" is wrong. **Three do** — stop-when-cleared,
extend-while-improving and cleared-restart, 32 and 39 — and lookahead-stop-when-cleared
matches them under block permutation only (39), not under joint-time permutation (33
against 32). The limit it illustrates, that the twelve rules are dependent, stands.

## Citation note — 2026-10-02 (America/Chicago). Phipson & Smyth, read against the claim

The Design section above says the twin rank p-value "controls type-I at any K" because
the K + 1 runs are exchangeable, and cites Phipson & Smyth (2010) for the construction.
Read against the text (arXiv:1603.05766v1; `docs/CITATIONS.md`): the paper calls
`(b + 1)/(m + 1)` **exact** for independent null datasets with a continuous statistic
(§4, p. 6). It calls it **valid but conservative** for permutations drawn with
replacement (§6.1–6.2, pp. 7–8). It does not treat exchangeable replicates in general.
Validity at any K under exchangeability stands, but **on the standard rank argument,
not on that paper**. Counting ties by `<=`, as the score-rank cell does, makes the test
conservative. **No verdict changes:** the score-rank cell's rule is a validity rule
(rate ≤ α), and its twelve rates were all below 0.05, the direction this predicts.
Besag & Clifford (1991) is cited here only for sequential stopping, which is not
registered; its text could not be accessed.

## Amendment — 2026-10-05 (America/Chicago), not live. The p-rank cell, set up for the box

**The planted level is 1.5.** The cell's planted level was registered as "7.5 stage 1's
nearest-the-bar", fixed by dated commit. Stage 1's read returned **1.5** (`8660508`;
pooled power at α = 0.05 of 0.4391, against 0.2035 at 1.0 and 0.0484 at 0.5). That
choice was made by the stage-1 read alone, before this cell has any data. The cell's
levels are therefore **0 and 1.5**.

**On the box.** The cell runs on the c7a.48xlarge (`i-0e0c1484de3c755ad`, x86_64,
shutdown behaviour Stop) at **191 workers**. At about 1.5 GB per worker (39 streams of
a chunk, plus 39 count matrices) that is about 290 GB of 369. The box smoke records the
real peak.

**The cost threshold replaces the lever.** The lever registered above ("if the box
smoke projects more than $30, n drops to 500") is withdrawn before any smoke has run,
so the change depends on no data. **The threshold is $30 on the mean-throughput
projection.** The projection is 1,000 panels × mean seconds per panel ÷ 191 workers,
at $9.85/h. The upper bound (full rounds × the slowest panel) is reported beside it and
decides nothing. **If the mean projection exceeds $30, the cell does not launch.** It
stops and is reported, and no lever (n, B, K, constructions, searchers) is applied
automatically.

**Expected, from the laptop component estimate (labelled as one):** about 820 s per
panel uncontended. That is about **1.2 h and $12** at mean throughput, and about
**$16** at the upper bound (6 rounds of about 1,000 s). The box smoke replaces it.

**The smoke:** 191 panels on the smoke block, at levels 0 and 1.5, B = 1,000, cost
only. The driver starts its smoke at 985000, so it reuses 985000–985190, which the
score-rank box smoke also used. Smoke seeds are never read, so that is cost-only
reuse. It writes to `runs/_smoke/planted_twins/`, separately from the score-rank smoke.

**Still to build before the live commit:** the p-rank reader. `experiments/
planted_twins_read.py` reads the score-rank cell only. The p-rank reader is to be
committed, and tested on synthetic files, before the cell's results exist. It is pinned
by hash in the live commit.

## P-rank cell — stopped at its box smoke, 2026-10-05 (America/Chicago). Not run; the p-rank statistic is unmeasured

The registered box smoke ran on 2026-10-05, 22:34–23:37 UTC: 191 panels on
985000–985190, levels 0 and 1.5, B = 1,000, 191 workers on the c7a.48xlarge, at
`3737147`. The records are cost only (`517f027`).
- Each panel took a wall mean of **3,633 s** (max 3,789; wall/CPU 1.05). The class pass
  over the 39 matrices took 1,813 s per level (median). Peak memory was **2,281 MB per
  worker**.
- The **mean-throughput projection for 1,000 panels was 5.28 h, $52.04**, against the
  **$30 threshold** (amendment of 2026-10-05). The upper bound was 6.32 h, $62.20.
- **Over the threshold, the cell stopped as registered.** There was no live commit and
  no registered run, and **no lever was applied**: not n, B, K, the constructions, the
  searchers or the workers.
- **The p-rank statistic is unmeasured.** Twin certification as registered (the gate's
  own p ranked among twins) has no result on real-feature panels. The score-rank cell's
  T1 passes (closed 2026-10-02) test the twin constructions with the submitted-score
  statistic. They do not license the p-rank statistic.

**Why the estimate missed, recorded for any later registration:**
- The laptop component estimate was about 820 s per panel, single process and
  uncontended. With 191 workers on the box, a panel took about 4.4 times that, and the
  class pass is nearly all of it.
- Memory per worker was 2.3 GB, not the estimated 1.5 GB, which left only 10–20 GB of
  the box's 369 free.

Running the cell would need a new, dated registration of its size or its threshold,
made before any p-rank data exists. None is made here.
