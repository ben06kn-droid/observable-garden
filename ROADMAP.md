# Roadmap

**Phase 6** tests the gate where it has not been tested. **Phase 7** builds the
replay gate — a process null over an agent's typed, harness-executed moves —
with a holdout tier beneath it, and an intraday testbed for both. The last
section decides what runs on this laptop and what needs EC2.

Every cell gets its own `prereg/<name>.md`, committed before it runs and removed
once it has reported, with the commit recorded in `EXPERIMENTS.md`. What the gate
does, and what it has been shown to do, is in `SCOPE.md`.

---

# Phase 6 — testing the gate where it hasn't been tested

## Context

**What the gate is.** Given a logged search, `garden audit` returns whether
the submitted result can be believed, given the search that produced it.
The verdict engine is White's (2000) Reality Check: demean every candidate,
resample the time index jointly, take the maximum, read off a p-value.
The project's additions: a characterization of when a transcript licenses
that correction (only for data-oblivious candidate sets), the sign and size
of the error when it doesn't (liberal under winner-chasing), a record
hierarchy that restores validity (the declared-class tier), and two verdicts
no existing tool returns — INADMISSIBLE (the search is too wide for the
sample to certify anything) and UNDECIDABLE (the log cannot license a
correction).

**What has been shown.** Under the declared-class tier the gate is valid
however adaptively the search chose what to evaluate. On 421 pure-noise
searches run by LLM agents (419 graded) it passed 15 times, 3.6% against a
nominal 5% — Sonnet 12/329, Fable 3/90. On a Sharpe-1.0
edge with 20 years of daily data it passed 60–70% of agent searches, above
the single-strategy power of 46% because a searcher that can find the edge
picks the best of its neighborhood. The agents themselves state a belief
that is a fixed function of the in-sample number they found — roughly a
model-specific prior plus half the in-sample Sharpe — with no dependence on
how many things they tried, even when the count is assigned. Telling them
the count does nothing; showing them the bar changes how much they search,
in a model-specific direction, and barely what they believe. On real data
(SPY, 1993–2026, 44 moving-average rules), the verdict depends on the null:
PASS against zero return, FAIL against buy-and-hold, PASS for the 22
long-short rules alone.

**What has not been tested.** Everything below. Each item bounds where the
results apply; none is expected to overturn them. Ordered so that the free
and local work lands first and the seat is spent last, on the one test
that matters most to a practitioner.

Rules carried over: every cell pre-registered in `prereg/` before it runs, and
removed once it has reported, its commit recorded in `EXPERIMENTS.md`;
fingerprint recorded per run; runners launched only from the seat terminal;
`experiments/` frozen during any batch. Seat cost for the whole phase is
roughly 160 runs, under $60 at list.

---

## Repository status, 2026-09-19

The repo was restructured on this date; several items below are cheaper or
differently addressed as a result.

- **Experiments are named, not numbered.** `EXPERIMENTS.md` is the registry and
  carries the old `e<n>`/`E<n>` id for every one. Names used here follow it.
- **`runs/` is five per-batch folders**, not 662 run directories. Each holds
  `runs.csv` (one row per run, ~40 columns), `cells.csv`, `raw.tar.gz` with the
  transcripts byte-identical, and `SHA256SUMS`. `runs/cells-pooled.csv` is the
  only place cells are pooled across batches. This is what makes 6.1's and
  6.2's free work a table read.
- **Pre-registrations are removed once their experiment reports.** The nine
  already-run ones are in git at the commits `EXPERIMENTS.md` lists, each of
  which precedes its run. `prereg/` now holds only `AGENT_PROMPTS.md` — still
  live, since its Fable arm is deferred to 2026-09-30 and it pins 6.5–6.7 —
  and the history-rewrite record.
- **`GARDEN_WATCH_PLAN.md` and `estimator_build_spec.md` were deleted**, at
  `1fb464f`. The watch plan also served as the pre-registration for
  `watch-validation`, so 6.4 extends `watch` against that commit.
- **`SCOPE.md` is ~3,100 words in named sections**, cited by name rather than
  number throughout the code and the gate's own verdict strings.

---

## 6.1 Calibration at 1% (free, then local)

**Why.** 5.0% at α=0.05 is one point on the p-value distribution. A gate
used for allocation decisions will be run at 1%, where the empirical check
has 5× fewer events and the bootstrap tail matters more.

**Free part — re-score what exists. Counts done 2026-09-19; KS still to run.**
Every graded s0 run carries its p-value as a column in `runs/<batch>/runs.csv`,
so this is a table read, not a walk over run directories. Over all 419 graded
s0 runs (331 Sonnet, 90 Fable):

| α | rejections | rate |
|---|---|---|
| 0.10 | 29 | 6.9% |
| 0.05 | 15 | 3.6% |
| 0.01 | 3 | 0.72% |

The plan expected about 4 of 380 at 1%; observed 3 of 419. Nothing is liberal
at any of the three levels. Still to do, and what 6.1 is actually for: Wilson
intervals per model, and the KS test of the pooled p-values against U(0,1),
which is the stronger statement and covers every α at once. Note that agents in
the gate and pushed arms saw a 5% bar, which affects behavior, not the validity
of the p-value.

**Local part — scripted, high count.** 5,000 draws of s0 with Greedy and
Adaptive scripted searchers under the full-class null (the declared class
the agents used), rejections at 1% and 5%, KS on the p-values. At 5,000
draws the 1% interval is ±0.3 points. Also 500 draws at B=50,000 to check
the bootstrap tail resolution at 1% against B=10,000.

**Gate — calibration only.** Rejection at 1% within its interval of nominal,
and KS not rejecting, for every searcher. If the 1% rate is high while 5% is
fine, the bootstrap approximation is failing in the tail, and the things to
examine are finite T, the block length, and the studentization — **not B**. The
`(1 + #)/(B + 1)` p-value is valid at every B: the rank is uniform under the
null, so the rejection rate is `floor(α(B+1))/(B+1) ≤ α` whatever B is.
Raising B cannot move a rate that is already correct.

**Separately — reproducibility, which is what B does control.** An individual
p-value has Monte Carlo standard deviation `sqrt(p(1-p)/B)`, so at p = 0.01 a
re-run with a different bootstrap seed moves it by about 1% of the threshold at
B = 10,000. That is a question about whether a near-threshold verdict is stable,
not about whether the rate is right, and it averages out across draws. The
B = 50,000 subsample measures it as a **verdict flip rate**; it does not gate,
and it is the only result that could implicate B — and then only if the paired
shift is signed rather than noise. See `prereg/calibration-at-1pct.md`
amendment 4.

## 6.2 Costs and regime change (free, synthetic)

**Why.** The gate corrects for search breadth only. A practitioner's
question is whether PASS survives the things it ignores.

**Costs — re-grade the s3 runs.** Positions are recoverable from each
submitted specification and the DGP seed, so turnover is computable
offline; `submitted`, `seed_index`, `sigma` and `oos` are all columns of
`runs/<batch>/runs.csv`, and the 240 s3 runs sit in `b2-arms` (σ=1, not to be
pooled), `b4-s3-recal` and `b5-opus`. Re-grade realized OOS net of a simple linear cost at 5, 10 and 20
bps per unit turnover for all 160 s3 runs at σ=194.407 (Sonnet and Opus).
Report: OOS gross vs net by verdict; the fraction of PASS runs whose net OOS
Sharpe stays above 0 and above 0.5 at each cost; the same for FAIL runs.
No model calls.

**Regime change — re-grade under a shifted OOS.** For the same 160 runs,
regenerate the OOS panel with (a) one true β halved, (b) one true β
sign-flipped, (c) σ doubled. Report OOS by verdict under each. The gate's
PASS is expected to remain a valid in-sample statement and to lose
predictive value in proportion to the shift — the point is to put numbers
on "necessary, not sufficient."

**Output.** One table for the paper's limitations section, replacing the
sentence "trading costs and regime change are not checked" with what they
cost.

## 6.3 Heterogeneous correlation and fat tails under the full-class null (local)

**Why.** Null calibration of the full-class tier was established under
equicorrelated Gaussian features. Real features are neither.

**Design.** Scripted searchers only. Two DGP variants: unequal-correlation's one-factor
loading structure (correlations λᵢλⱼ, loadings spread 0.2–0.8), and
Student-t innovations at ν=4 with a GARCH(1,1)-style volatility path
(stationary block bootstrap already chosen for this). 2,000 draws each of
s0, Greedy and Adaptive, full-class null, rejection at 5% and 1%, KS.

**Gate.** Both hold at both α. If the t/GARCH cell is liberal at 1%, the
block-length selector is the first suspect; report the block lengths chosen.

## 6.4 Explicit classes in `watch` (code, no runs)

**Why.** `watch` refuses ExplicitClass. An agent whose tool grammar emits
rules rather than feature subsets — which is most agents anyone would
build — can't be watched. The audit already handles explicit classes
(Reality Check on the supplied streams); watch needs the same path.

**Build.** At open: take the class as a matrix of return streams, price the
bar with the ordinary Reality Check bootstrap once, membership by spec id.
Everything else unchanged. Tests: bar equals audit's explicit-class null on
the same inputs; membership refusal by id; bar does not move. Enables 6.5's
rule-grammar arm.

## 6.5 An agent on real data (seat, ~80 runs) — the headline

**Why.** Everything the agents have done, they have done on a synthetic
panel with a known oracle. The claim a practitioner will act on is what
the gate does when an agent searches data with real structure.

**Panel.** A fixed universe of ~40 liquid US ETFs with 20+ years of daily
history (sector, factor, size, international, bond, commodity), adjusted
closes from Yahoo, committed to `data/` with a README. No survivorship
issue: the universe is defined as "ETFs with continuous history from 2005,"
chosen before any search, and the choice is recorded.

**Split.** In-sample 2005–2021 (~4,250 days), holdout 2022–2026 (~1,100
days). The holdout is never on the machine the agent runs on; the harness
grades from a separate file after submit.

**Features.** K=40 price-based signals per asset, computed with strict
one-day lag, defined and committed before any run: momentum at 5/21/63/126/
252 days, short-term reversal, realized volatility at three horizons,
volatility-scaled momentum, distance from moving averages, drawdown,
cross-sectional rank versions of each. All dollar-neutral cross-sectional
constructions, so the zero-excess-return null is the right null and no
benchmark subtraction is needed; say so in the pre-registration.

**Class and admissibility.** Run `preflight` first. Signed subsets of ≤3
over K=40 at T≈4,250 is near the 20% power floor (interpolating the T
table: roughly 0.25–0.30 at reference Sharpe 1.0). If INADMISSIBLE, drop to
unsigned d=3 or signed d=2 — decided by preflight before any run, recorded.

**Arms.** control and gate, 40 runs each, claude-sonnet-5. Every run sees
the same in-sample panel; runs differ only in the agent's own search, so
this is a study of what the agent does with fixed real data, not a
sampling experiment.

**Readouts, all pre-registered.**
1. Verdict distribution. With no oracle, the expected PASS rate is unknown;
   report it with its interval.
2. The gate's practical test: holdout Sharpe of PASS submissions vs FAIL
   submissions, gross and net of 10 bps costs. If PASS doesn't predict
   holdout, that is the result.
3. The haircut regression: stated mean on submitted in-sample Sharpe and
   log(count). The equation's coefficients on real data, next to the
   synthetic ones.
4. Which features the agents converge on, and whether PASS submissions
   cluster on a few — a real-data version of "abandoning the truth."
5. Evaluation counts and status calls by arm, as before.

**Secondary arm (after 6.4).** 20 runs with a rule-grammar tool — the agent
composes moving-average and breakout rules per asset from a fixed menu —
watched under an explicit class. The first watched agent whose actions
aren't feature subsets.

**What this cannot show.** Whether any PASS is a real edge. Twenty runs on
one holdout is one draw of the future. The output is the gate's behavior
on real structure and the agent's behavior on real data, not an alpha.

## 6.6 T sweep for agents (seat, ~40 runs)

**Why.** Agents have only ever run at T=5,000, where the pinned class is
admissible. At realistic sample lengths the gate says INADMISSIBLE at
open, and no run has shown what an agent does when told that.

**Design.** s0, T ∈ {1,000, 2,500}, control and gate, 10 runs per cell,
Sonnet. Gate agents receive INADMISSIBLE at open through `status`.
Readouts: evaluation count, stated mean, and whether any agent's behavior
changes when the gate has said in advance that nothing can be certified.
Hypothesis, from everything so far: none of it changes.

## 6.7 Fat tails for agents (seat, ~40 runs, conditional on 6.3)

Only if 6.3 holds. s0 with t(4)+GARCH innovations, control and gate, 20
each, Sonnet. Readout: PASS rate at 5% and 1% on the agent's own searches,
and whether the haircut equation holds under fat tails (it should; the
agent sees Sharpe ratios either way).

---

## Sequence and gates

| step | work | where | gate |
|---|---|---|---|
| 1 | 6.1 free re-score; 6.2 re-grades | local, minutes | — |
| 2 | 6.1 scripted; 6.3 | local, hours | 1% within interval, KS holds, in every cell; else examine T, block length and studentization — not B — before anything else |
| 3 | 6.4 explicit-class watch | code | bar equals audit; tests green |
| 4 | 6.5 panel, features, preflight, pre-registration | local | preflight OK at some class; class recorded |
| 5 | 6.5 main arms | seat, one window | — |
| 6 | 6.6, 6.7 | seat, one window | — |
| 7 | 6.5 rule-grammar arm | seat | — |

Steps 1–2 produce the limitations table and the 1% number and cost
nothing. Step 5 is the one that matters. If time runs short, cut 7, then
6.7, then 6.6; never 6.5.

## What goes where

- **Note to López de Prado:** nothing from this phase. It's finished as
  scoped.
- **Paper:** 6.1 (calibration at 1%, KS), 6.2 (the limitations table with
  numbers), 6.3 (robustness of the full-class null), 6.5 (the real-data
  section).
- **README:** the 6.5 verdict table beside the SPY three-null table.
- **Amendments:** one per cell, before it runs, as before.

---

## 6.8 Cheap extensions — answerable with what exists

Each is local work or one seat window. None changes the results above; each
closes a question a reader will ask.

| question | how | cost |
|---|---|---|
| Calibration at 1%, fat tails, heterogeneous correlation | 6.1, 6.3 | local |
| What costs and regime shifts do to PASS's predictive value (synthetic) | 6.2 re-grades | free |
| Does the haircut equation hold on real data and across models | 6.5, plus one Sonnet/Opus/Fable cell each | one window |
| What an agent does when told INADMISSIBLE at open | 6.6 | one window |
| Does the gate's feedback improve outcomes, not just beliefs | two more model cells on s3 (it didn't for Sonnet) | one window |
| Can an agent deflate if told *how* | one prompt arm that hands it the DSR formula and the count; separates "can't" from "wasn't asked" | 40 runs |
| Watching rule-grammar agents | 6.4 | code |
| The effective-N note | two-hour literature check, write-up | a day |
| The Thresholdout hybrid | explore on a noisy holdout, certify a declared class on fresh data | a week of code, no new theory |

Answerable only weakly from any experiment: whether PASS predicts real
out-of-sample performance (6.9 below), and whether real edges live inside
classes narrow enough to certify — a question about the world that only
live tracking answers.

Not answerable without a large amount of new work, and out of scope:
interior-rank sign in closed form; bootstrap consistency under partial
separation; large-K asymptotics for studentized maxima; the recursive tier
for LLM agents; training agents to be calibrated; the matched human
baseline; non-Sharpe settings such as prediction markets.

---

## 6.9 Does PASS predict out-of-sample performance? — the forward test

**The problem.** One holdout is one draw of the future. Daily data over
twenty years gives four or five independent multi-year windows, so a
rolling-origin design yields a direction with a wide interval, never a
rate. Two things widen the sample: making the holdout the actual future,
so no look-ahead of any kind is possible; and going intraday, where a few
years contain many independent windows.

**Design A — sealed forward test.** Pull data up to a pre-registered cutoff
(the date the search runs), run the agent search and the gate on it, and
commit every submission and verdict before any later data exist. The
holdout is then calendar time. Nothing can leak because nothing exists
yet. Results arrive on their own schedule — the first reading at six
months, a defensible one at eighteen — and the readout is the same
asymmetric test as everywhere else: holdout Sharpe of PASS submissions
against FAIL submissions, gross and net of costs. The gate's claim is on
the FAIL side (nothing it refused should have been believed); PASS is a
weaker claim, and the test should say so.

Run it on the daily ETF panel from 6.5 at the same time as 6.5's own
holdout analysis: the 2005–2021 / 2022–2026 split gives the weak answer
now, and sealing 2026-09 as the cutoff gives the strong one later. Same
runs, same submissions, two holdouts.

**Design B — intraday alpha search on 1–5 minute OHLCV bars.** Five-minute
bars give ~78 per session, ~20,000 a year; three years of one liquid
instrument is ~60,000 bars, and a rolling-origin design over it yields
dozens of holdout windows of a month each rather than four of four years.
That is the only way to turn "does PASS predict OOS" into a rate within
months instead of years.

What changes at this frequency, each of which must be decided and
recorded before any search:

- *The effective sample is smaller than the bar count.* Intraday returns
  have short-lag autocorrelation, intraday seasonality, overnight gaps, and
  strong volatility clustering. The stationary block bootstrap handles the
  dependence; the block-length selector should be run and reported per
  instrument, and preflight's power must be computed on the bar series
  itself, not from T alone. Expect the admissible class to be narrower than
  the bar count suggests.
- *Costs are first-order, not a footnote.* At a five-minute horizon a
  spread crossing per trade is comparable to the expected move. The gate's
  null is zero mean return; on intraday data the only honest null is zero
  return *net of a stated cost model* — use `--benchmark` with the cost
  series subtracted, and pre-register the cost assumption (half-spread plus
  a fixed per-share fee, from the instrument's own quoted spreads).
- *Sessions are not one series.* Overnight gaps are removed or modeled;
  the first and last bars of each session are excluded or flagged;
  annualization uses bars-per-year for the instrument, stated once.
- *Features and class.* Price/volume constructions at bar lags 1–60:
  returns, ranges, volume ratios, VWAP distance, order-flow proxies from
  OHLCV. Fixed and committed before the search. Same declared-class tier;
  preflight decides d and signs.
- *Data.* A vendor with several years of clean 1-minute bars for a few
  liquid instruments (index futures or the largest ETFs). Free sources
  rarely go back far enough at this frequency; budget for it and record
  the source, the download date, and the adjustment method.
- *Decay is fast, which is the point.* Intraday edges that exist tend to
  disappear within quarters. A rolling-origin readout will show PASS
  submissions decaying; the question is whether they decay to zero faster
  or slower than FAIL submissions, and whether the gate's FAIL side holds.

**Readouts for B, pre-registered.**
1. Per rolling window: verdict, holdout Sharpe gross and net, block length,
   admissible class at open.
2. Pooled: holdout Sharpe of PASS vs FAIL submissions, with the between-
   window dependence acknowledged (windows overlap in features even when
   holdouts don't).
3. Calibration in the wild: the fraction of FAIL submissions with positive
   net holdout Sharpe — the gate's false-negative rate on real data, the
   number nobody has.
4. The haircut regression on intraday data, one more row in the table.

**Order.** A costs nothing beyond 6.5 and should be sealed the day 6.5
runs. B is a separate project — data acquisition, a session-aware
sandbox, a cost model — of two to four weeks before the first search, and
it belongs after the note and the paper's first version are out. It is
also the one experiment on this list that could produce a result a trading
desk would care about, which is a reason to do it and a reason to do it
carefully.

---

# Phase 7 — the replay gate, and an EU-tech ADR testbed

Built after Phase 6's free items (6.1–6.3) and before 6.5, so that 6.5
runs on the new gate as well as the old.

**Design principle.** An agent's decisions are captured as rules the
harness can re-execute, and every ambiguity resolves in the conservative
direction: a decision the gate cannot replay is priced by the maximum over
its alternatives, never ignored. Residual ambiguity in how an agent decides
then costs power, not validity — and whatever still leaks is measured on
s0 (7.3) rather than assumed away.

**Prior art, to be read in full before any novelty claim.**
- POPPER (Huang et al., ICML 2025): agentic sequential falsification,
  e-values, Type-I control. Closest on the statistics. Validates a given
  hypothesis; no search pricing, no replay.
- Huang, Fan, Hu & Ye (2026, arXiv 2604.26747): constrained agents for
  crypto factor discovery — restricted DSL, append-only trace, falsifiable
  hypotheses, fixed splits. Closest on the surface. Gates are fixed
  training-window IC thresholds; no multiple-testing control. **The
  earlier attribution to "Chen et al. (2025)" was wrong**: inside that
  paper Chen (2025) is a different JPM article.
- Nakkiran & Błasiok (2018, arXiv 1809.05596), "The Generic Holdout":
  exploration set plus holdout with binary feedback. This *is* the
  holdout tier's mechanism; cite it, claim nothing.
- Fithian, Sun & Taylor (2014): holdout-only inference is dominated by
  carving. The reason the holdout is a fallback, not the certifier.
- Kinlay (blog, 2026-09-02): pre-registered, trial count as a log file for
  an agentic pipeline; leg count as an unlogged selection axis. Overlaps
  the observability thesis, not this gate. Our declared class bounds legs
  at d; say so where cited.

What is grammar, ledger, or falsifiable-hypothesis framing is not new.
The candidate contribution is the process null over typed moves with its
size measured, and the fidelity measurement in 7.3.

## 7.0 gate-comparison — which test should certify? (EC2, first)

Unregistered scouting (2026-09-19, scripted greedy, K=40, d=3 signed,
T=5,000, oracle 1.0, n=120–300, bar priced once per configuration; null
rates came in at 4–9%, so direction only):

| design | one fixed strategy | winner-chasing search |
|---|---|---|
| declared class, full sample | 0.43 | 0.66–0.73 |
| holdout 70/30, one test at α | 0.79 | 0.40–0.48 |
| α-spending over 10 predictions | 0.45 | — |
| Fisher: class p (exploration) × holdout p | 0.71 | 0.63 |

The ranking reverses at search level: selection inflates the submitted
Sharpe, the class bar prices that legitimately, and the holdout sees only
the unbiased Sharpe of a partly right spec on 30% of the sample. Class
width is cheap (bar ~ √(2 ln N)); splitting is not (SE × 1.8).

Pre-register and run properly: Greedy and Adaptive on s0 and s3, 2,000
draws, three certifiers — declared class on the full sample, holdout
70/30 and 50/50, process replay on the full sample. Type-I at 5% and 1%,
PASS rate on s3, holdout Sharpe of passes. Add one 6.2-style regime-shift
cell using **β sign-flipped on S[0]** — the same shift 6.2 ran, so the two
are directly comparable. Motivated by 6.2: under that shift the class gate's
PASS advantage erodes from +0.46 to +0.08 in median gross OOS Sharpe, about
80%, without inverting. 7.0 asks whether a later-in-time holdout tier
degrades differently under the same shift, the case where it might win.

Gate: decides tier order in 7.2. Expected order — replay, class, holdout.
If replay does not beat the class gate's PASS rate on s3 at matched
type-I, Phase 7 reduces to the holdout fallback plus the measurements, and
says so.

**From 6.1's arm B (added 2026-09-20).**

- *The class gate's actual size is far below nominal, so power must be compared
  at matched actual type-I, not at matched nominal α.* Measured at α = 0.05:
  scripted Adaptive **1.0%**, agents **3.6%** (arm A), against a nominal 5%.
  That slack is exactly what process replay is meant to recover, and comparing
  PASS rates at nominal α would credit replay with power that is really just the
  class gate's unused size.
- *The exhaustive searcher joins 7.0 as the calibration anchor.* `ExhaustiveClass`
  submits the argmax over the declared class, so P2's conservatism vanishes and
  P1 predicts exactness; it is the only searcher whose size measures the
  bootstrap rather than its own position in the class. 7.0 therefore reports
  each certifier's **actual size per searcher** alongside its PASS rate.
- *Why agents sit closer to nominal than scripted Adaptive.* Not P5. Checked
  against the arm A transcripts: 95.9% of agent submissions are depth 3, so it
  is not depth, and **83.8% carry at least one short leg**. `Greedy` and
  `Adaptive` build weights with `_one_hot_sum`, which is unsigned, so they are
  confined to the 10,700-member unsigned sublattice — 13% of the 82,240-member
  signed class they are priced against. The agents search the signed class and
  get nearer its maximum. P5 concerns greedy reaching the *lattice* optimum,
  which would put Adaptive near nominal if the lattice were the bar; the bar is
  eight times larger than the lattice it can reach.
- *7.0's scripted arms must use a class matched to each searcher's reach* —
  either signed searcher variants against the signed class, or the existing
  unsigned searchers against an unsigned class. Pricing an unsigned searcher
  against a signed bar is what made arm B unreadable, and 7.0 compares
  certifiers, so a mismatch would be attributed to the certifier rather than to
  the searcher's confinement. `ExhaustiveClass` is the exception and is run
  against whichever class is being priced, since it reaches all of it by
  construction.

## 7.1 fixed-sequence-replay — what does freezing a decision cost? (EC2)

The replay gate re-executes an agent's typed moves on each bootstrap
resample. Content choices (which feature gets extended) are rules and are
replayed exactly. Meta-choices (when to stop, when to restart, which move
next) were made after seeing results; by P4, freezing them is the
realized-menu error one level up, and stop-when-cleared is the
winner-anchored case. Measure it, then measure the fix.

Scripted meta-adaptive searchers on s0: stop-when-cleared,
restart-after-k-failures, extend-while-improving, each with its move
sequence and its triggers recorded. Four nulls per draw:

1. fixed-sequence replay — move types frozen at the realized sequence;
2. **trigger replay** — each meta-move carries its predicate; the
   predicate is re-evaluated on the replicate. A replicate that stops
   earlier takes its value there. One that would continue past the
   realized sequence is filled with greedy extension to the budget;
3. full policy replay — exact, since the policy is code;
4. declared-class bound.

2,000 draws. Type-I at 5% and 1% for each; Kolmogorov distance of (1) and
(2) from (3) per searcher.

Gate: trigger replay must be at or below nominal for all three searchers
— conservative is acceptable, liberal is not. If it holds, in-the-loop
agents are certifiable with triggers declared. If only full policy replay
holds, the agent writes a policy instead of searching in the loop. The
fixed-sequence number is reported either way as the size of the error
that declaring triggers removes.

## 7.2 The replay gate — build

**Tiers.** The gate uses the strongest valid test the record supports,
and reports the others beside it:

| record kept | certifier | validity |
|---|---|---|
| typed moves, triggers, fidelity passed | process replay, full sample | asymptotic; size from 7.1 and 7.3 |
| declared class only | full-class null, full sample (exists) | finite-sample, conservative |
| neither — free-form search | holdout, binary feedback | exact under slice independence |

**Grammar, harness-executed.** The agent names a move; the harness
computes it and builds the specification, so the log cannot disagree with
what ran. Content moves: `init(spec)`, `extend_best(k, by=stat)`,
`swap_worst(by=stat)`, `flip(feature)`, `refine(stat)`. Two pick moves
replace free-form judgment:
- `pick(by=stat, among=set, else=stat2)` — a data-driven reason stated as
  a rule. `stat` comes from a fixed, committed library (exploration
  Sharpe, autocorrelation at named lags, volatility, correlation with the
  current best, IC). Replayed like any content move. `else` is what the
  rule does when its premise fails on a replicate; without one the harness
  fills with the best of `among`.
- `pick_prior(feature, reason)` — a reason from outside this data.
  Oblivious, free, and admissible only while the harness can show by
  timestamp that no `evaluate` result touching `feature` or its family
  has been returned. After that point it is refused; use `pick`.

Meta moves: `restart(trigger)`, `stop(trigger)`. A trigger is a predicate
over the agent's information set (best so far, moves since improvement,
bar cleared, budget left), stamped before the move executes.

**Information set.** The harness logs exactly what each `evaluate`
returned and when. Tags come from timestamps, never from the agent's own
description.

**Consistency check, free.** For every `pick`, the harness confirms the
agent's choice is what the declared rule selects on the realized data. A
pick that contradicts its rule is rejected as declared and priced
locally.

**Local pricing.** A rejected pick, or any step the agent cannot state as
a rule, is replaced in each replicate by the best of its admissible
alternatives at that step; the rest of the sequence replays normally.
This is P3 applied to one move rather than the whole class. Conjecture
from P4: anchoring later moves on a local maximum is conservative.
Verified in 7.3 before it is relied on. A move outside the grammar
entirely drops the run to the declared-class tier.

**Process null.** The move sequence with triggers, replayed on
full-sample resamples by the recursive bootstrap. This certifies; it is
also the standing bar during search. `by=stat` must be computable from
base columns alone, which the `Replayable` contract already requires.

**Holdout tier.** Only for runs with no replayable record and no
declarable class. Exploration/validation split fixed in the
pre-registration (70/30, contiguous, validation later, embargo of max
lookback plus block length at the boundary). Binary feedback; failures
are visible; the run halts at the first confirmation (Nakkiran &
Błasiok). Levels by α-spending, Σα_j ≤ α, valid under arbitrary
dependence including sign-flipped pairs. No earn-back: Foster–Stine needs
each test valid given earlier outcomes, which a shared slice breaks. One
certifying prediction keeps the whole α; ten cost about 34 points of
power in scouting.

**Prediction slot.** Every `evaluate` may carry a falsifiable claim,
stamped before the result returns; trivial or underpowered claims are
rejected at entry. Under the replay and class tiers it is a measurement
— does the agent commit before it looks — and carries no α. Under the
holdout tier one prediction is the certificate.

**Verdict.** CERTIFIED (replay) / PASS (class) / CONFIRMED (holdout), each
labelled with its tier; FAIL; INADMISSIBLE if preflight fails for the
tier in use; UNDECIDABLE only if no tier applies. Reported beside the
verdict: the other tiers' p-values, the fraction of moves replayed exactly
/ priced locally / filled, and the run's fidelity rate if sampled.

**Surface.** Move sequence with triggers, information-set log,
consistency results, prediction log with timestamps. A reviewer reads a
ledger of decisions, not a transcript.

**Tests.** The process null reproduces pointwise-dominance's recursive
p-values when the grammar is the two-step anchored search; harness
execution makes log and specification identical; `pick_prior` is refused
after the timestamp; a contradicted `pick` is priced locally; a trigger
that fires earlier on a replicate truncates there; the grammar is closed;
the prediction slot cannot be written after the result exists.

## 7.3 Does the gate account for the agent? (EC2, then seat)

**Scripted, on s0 and s3, 2,000 draws.** Faithful searchers using every
move type, then three unfaithful ones, because the gate's validity
depends on the rule the searcher used, not the one it declared:
- declares `pick by=autocorr`, actually picks by best Sharpe seen;
- declares `pick_prior`, actually peeked;
- omits the trigger on a stop-when-cleared.

Required: faithful searchers at or below nominal at 5% and 1%; the
consistency check or the timestamp catches each unfaithful one, and local
pricing returns it to nominal. Report the liberal size when the checks
are switched off — that is the cost of trusting a stated reason. The
local-pricing conjecture is tested here: if it is liberal anywhere,
rejected picks drop the run to the class tier instead.

**Agent cell.** Sonnet. Control 40, replay arm 80 on s0 and 40 on s3.

1. *Calibration.* Each s0 run's submitted Sharpe is placed within its own
   replay null. If the gate reproduces what the agent does on noise, those
   positions are uniform — e1, applied to agent plus gate. KS against
   U(0,1) and type-I at 5%. At n=80 this detects a true rate near 13% or
   worse; it rules out gross leakage and no more, and the scripted runs
   carry the calibration claim. Skew toward small p means a decision kind
   is leaking; the per-kind fractions say which.
2. *Fidelity.* For a pre-registered subsample (10 runs per config, every
   `pick` and meta-move), re-present the single decision to the agent ~20
   times with resampled numbers in context and record how often the
   declared rule predicts the choice. Report the rate by move type.
   Pre-registered tolerance: moves whose type falls below it are priced
   locally in the certifying null from then on. Search for prior work on
   this measurement before claiming it; Turpin et al. (2023) and the
   chain-of-thought faithfulness literature are the neighbours, to be
   verified before citing.
3. *Behaviour.* Share of moves by kind; how often `pick_prior` is used and
   refused; how often triggers are declared versus filled; predictions
   made before the first look.
4. *Power.* CERTIFIED rate on s3 against the class gate's PASS rate on the
   same runs.

Known residue, stated in the write-up: the agent's choice of *which*
statistic to look at is itself data-informed. The fixed library bounds
that fork and the local-pricing fallback prices it when the consistency
check fails; it is not eliminated, and check 1 is what measures it.

Gate: Phase 7 enters the paper as a section if the scripted runs
calibrate and check 1 shows no skew; otherwise as a measured failure,
with the leaking decision kind named.

## 7.4 EU-tech ADR testbed at 5-minute bars

**Why ADRs.** The ADR trades in US hours while its home market is open
until ~11:30 ET and closed after. Information arrives on a schedule and
pulls in known directions — home index, sector ETF, FX, the ADR–ordinary
parity (Gagnon & Karolyi 2010) — so an agent can state theory-driven picks
before seeing results — `pick_prior` with the home-close mechanism as its
reason — which the replay gate prices at zero and the timestamp rule can
verify. Whether any of it survives at five minutes net of ADR spreads is
the open question.

**Universe — decided before any data is looked at, and recorded.** EU
technology and semiconductor names with liquid US listings:

| ticker | company | home | listing | note |
|---|---|---|---|---|
| ASML | ASML | Euronext AMS | Nasdaq | most liquid |
| SAP | SAP | Xetra | NYSE | |
| STM | STMicroelectronics | Euronext PAR | NYSE | |
| NOK | Nokia | Helsinki | NYSE | |
| ERIC | Ericsson | Stockholm | Nasdaq | |
| ARM | Arm Holdings | none (US-only) | Nasdaq | from 2023-09; no home market |
| LOGI | Logitech | SIX | Nasdaq | ordinary, dual-listed |
| NXPI | NXP | none | Nasdaq | EU-domiciled, US-only listing |
| SPOT | Spotify | none | NYSE | EU-domiciled, US-only listing |

EU tech is thin: five or six names with a real home-market close, and
three EU-domiciled names without one. Keep the latter in the panel as a
built-in control — every home-close prediction should fail on them — and
say so in the pre-registration. If preflight on this panel is INADMISSIBLE
at any admissible class, widen to EU large-caps across sectors (NVS, AZN,
SNY, NVO, HSBC, BCS, UL, DEO, TTE, SHEL, BP, RIO) and keep the tech names as
a sub-panel. Exclude OTC-only listings (IFNNY, CGEMY, DASTY); their
intraday prints are too sparse.

**Data, and whether it's free.** Two years is free; more is not.
- Polygon.io free tier: 5 calls a minute, historical window of roughly the
  last two years; aggregates return up to 50,000 bars per call, so two
  years of 5-minute bars for a name is one or two calls. The whole panel
  downloads in an afternoon at no cost. US-listed ADRs are US equities to
  Polygon, so they're covered.
- Alpha Vantage's intraday endpoint advertises 25+ years of history, but
  the free tier is 25 requests a day with compact output; multi-year
  intraday needs a premium key (~$50/month, cancel after one month).
- Yahoo: 60 days of 5-minute bars. Not usable.
- Databento / Kibot: pay-as-you-go, cheap for a 12-name panel, and the
  cleanest corporate-action handling.

Start free. Two years of 5-minute bars is ~40,000 bars per name; with
the panel it is enough for preflight to have something to say, and for a
rolling-origin design with ~20 monthly holdouts. If the first pass shows
power is the constraint, the extra years are one month of Alpha Vantage
premium. Record source, download date, session filter, and adjustment
method in `data/README.md`; ADR ratio changes must be checked by hand
against each depositary's notices.

**Sessions and null.** US regular session only, 9:35–15:55 ET, first and
last bars dropped. Home-close at 11:30 ET is a boundary the sandbox knows:
every feature carries a home-open/home-closed indicator, and the block
bootstrap treats it as a break. Null: zero return net of a pre-registered
cost model — half of each name's median quoted spread per trade plus a
per-share fee. Costs depend on each specification's turnover, so they are
not one benchmark series: the sandbox returns net-of-cost streams per
specification, and the class is priced as an explicit class of net
streams. This depends on 6.4; `audit` refuses `--benchmark` on classes
enumerated from base returns, and `watch` has no benchmark path.
Annualization by the panel's own bars per year.

**Features, fixed and committed first.** Cross-sectional within the panel,
dollar-neutral: own return at lags 1, 3, 6, 12 bars; return relative to a
US semiconductor/tech ETF over the same lags; overnight gap; distance from
session VWAP; volume versus 20-day average at that time of day; minutes to
and from home-close; each of these interacted with the home-open
indicator. K ≈ 40, as before.

**Class.** Signed subsets ≤ 3 by default; preflight on the exploration
slice at the panel's bar count decides d and signs, recorded.

Sharpe's standard error is set by years, not bars: two years gives
SE ≈ 0.71 annualized on the full sample and ≈ 1.3 on a 30% slice.
Preflight with a reference Sharpe chosen and recorded before any data is
seen; the holdout tier is expected to be INADMISSIBLE at Sharpe 1.0 here.

**Arms.** control, class gate, replay gate — 30 runs each, Sonnet; then a
rolling-origin pass with the replay arm only, ~20 origins. The holdout
tier is computed for every run as a reported number, not an arm.

**Readouts, pre-registered.**
1. Verdict distributions per arm; certification rate for the replay gate.
2. Holdout Sharpe, gross and net, of CERTIFIED vs PASS vs FAIL
   submissions; the false-negative side (FAIL submissions with positive net
   holdout) is the number nobody has.
3. The home-close control: prediction confirmation rate on names with a
   home market vs without.
4. The haircut regression on intraday data.
5. Decision behaviour: share of `pick_prior` versus `pick`, fraction of
   prior picks naming the home-close mechanism, triggers declared versus
   filled, fraction of moves priced locally.
6. Fidelity rate by move type on a 10-run subsample, as in 7.3.

**What it cannot show.** That any certified edge is tradeable at size, or
that it persists — two years of history and twenty monthly holdouts give
a direction and a bounded false-negative rate, not an alpha. Seal the
last month as a forward holdout regardless, per 6.9.

## Sequence

| step | work | where |
|---|---|---|
| 1 | 6.1–6.3 | local / EC2 |
| 2 | 7.0 gate-comparison; 7.1 fixed-sequence and trigger replay | EC2, one instance |
| 3 | 6.4 explicit classes in `watch` (now blocks 7.4's null) | local |
| 4 | 7.2 build; 7.3 scripted, faithful and unfaithful | local, then EC2 |
| 5 | Polygon download, panel README, features, preflight, pre-registration | local |
| 6 | 7.3 agent cell, calibration and fidelity checks | seat, one window |
| 7 | 7.4 fixed-split arms | seat, one window |
| 8 | 6.5 daily ETF panel on all three gates | seat, one window |
| 9 | 7.4 rolling-origin pass | seat |
| 10 | 6.6, 6.7 | seat |

The note to López de Prado is unaffected. Phase 7 goes in the paper as
its own section only if 7.3 calibrates; otherwise it goes in as a
measured failure, which is also a section.

---

# Compute — what runs on the laptop and what needs EC2

The machine is a MacBook Air, M3, 8 GB. Two things decide placement: total
bootstrap work, and peak memory. Rules of thumb from what has already run
here — oblivious-calibration (640 cells × 1,500 replicates) took 7.7 hours on a
32-core instance; the T=2000 validation (96 cells) took 1.5–3 hours; a single
agent run's two bootstraps take seconds.

**Never EC2:** anything that calls the model. Agent runs are latency-bound
and the seat is logged in on the laptop. All of 7.3's agent cell, 7.4's
arms, 6.5, 6.6, 6.7 run locally regardless of scale. 7.3's fidelity check
is short single-decision calls, roughly 20 per sampled decision on 10 runs
per config — a few thousand calls, inside one window.

**Running an agent batch.** Agent runs go through the enterprise seat on this
laptop, never EC2. Confirm which seat is active before spending a window: the
harness pins the model and records it per run, but nothing records which seat
paid for it.

    echo $CLAUDE_CONFIG_DIR
    .venv/bin/python -m experiments.check_model --model claude-sonnet-5

`check_model` costs a few thousand tokens rather than a run, and settles the two
things that void an entire cell if they are wrong: whether the seat serves the
model at all, and whether it reports back the exact string the run config pins.
`prereg/AGENT_PROMPTS.md` §3 excludes any run whose reported string differs.

Then launch under `caffeinate`, so the machine cannot sleep mid-window:

    caffeinate -i bash experiments/run_arms.sh \
        --schedule experiments/<schedule>.txt --start 0 --workers 4 --auto-resume

`--only-worker K` runs one worker's rows and is what a stopped worker's resume
line prints. `--allow-code-change` is only for deliberately continuing a batch
across a fingerprint change; without it the runner refuses, which is the
intended default. `--auto-resume` treats a rate limit as a wait rather than a
failure, and retries the same row after the reset.

The seat's configuration cannot reach the agent: `searchers/llm_agent.py` passes
`setting_sources=[]`, so neither `~/.claude` nor project settings are read, and
the byte-identical-prompt guarantee of `prereg/AGENT_PROMPTS.md` §2 holds
whichever seat is authenticated. `CLAUDE_CONFIG_DIR` decides who pays, not what
the agent sees.

**Always local:** re-scoring existing verdicts (6.1 free part), OOS
re-grades (6.2), the notebook, the replay gate build and its unit tests,
feature construction on the ADR panel (12 names × 40k bars × 40 features
is ~150 MB), and any single audit or preflight, including on the intraday
panel — the moment-based class null is O(K²) per replicate and does not
hold a B × T index matrix.

**EC2, because of total work:** any sweep with more than ~500 draws of the
full-class null, and any sweep that replays a search inside the bootstrap.
That is: 6.1's scripted 5,000-draw calibration and its B=50,000 tail
check; 6.3 (8,000 draws across two DGP variants); 7.0 gate-comparison
(2,000 draws × 3 certifiers); 7.1 fixed-sequence-replay (2,000 draws ×
four nulls, not three, one of which replays the policy per replicate — the
most expensive thing in the plan); 7.3's scripted runs (2,000 draws, and
three unfaithful searchers with the checks on and off). Each is hours to a day on
16–32 vCPUs and minutes of setup; on the Air each would be days and would
compete with everything else. Use a compute-optimized spot instance
(c7g or c6i, 16–32 vCPU), sync the repo, run the experiment script with
its own `--workers`, pull back the `.pkl` and figures, commit. A few
dollars per sweep.

**Memory hazards on the Air, and how to avoid them.** The recursive and
explicit-class bootstraps materialize resampled index arrays of size
B × T. At B=10,000 and T=5,000 that's 50 M entries — fine. At the intraday
panel's T≈40,000 it's 400 M, or 3.2 GB in int64, which will swap or die on
8 GB with anything else open. Any bootstrap on the intraday panel must
chunk B (500 replicates at a time is plenty) or use int32 indices; the
moment engine already avoids the matrix and is the default for the
declared-class bar. The same applies to fixed-sequence-replay and the replay
gate's process replay at intraday length — those go to EC2 for memory as
much as time.

**Practical rule.** If a script's expected runtime is over two hours or
its B × T exceeds 10⁸, it goes to EC2. Everything else, including every
run that talks to the seat, stays on the laptop.

**Measured, 2026-09-20, on c7a-class 32 physical cores (AMD EPYC 9R14, no SMT),
the full-class null at K=40, d=3 signed, T=5,000, B=10,000.** The 32-worker row
is `calibration-at-1pct` arm B's own 5,000-draw run, not a smoke.

| workers | s/draw | wall s/draw | draws/hour | $/draw at $1.64/h | parallel efficiency |
|---|---|---|---|---|---|
| 1 | 38.77 | 38.77 | 93 | $0.0177 | 100% |
| 4 | 41.31 | 10.33 | 349 | $0.0047 | 94% |
| 16 | 76.85 | 4.80 | 750 | $0.0022 | 50% |
| 32 | 159.73 | 4.99 | 721 | $0.0023 | 24% |

**This workload saturates at about 16 workers, and 32 is worse than 16 on both
axes** — 4% slower in wall-clock and marginally dearer per draw. Single-core on
the instance is 38.8 s against 34 s on the laptop, so per-core speed is within
12% and the remaining 4.1× is contention, not hardware. The inner loop streams
the (T, K) demeaned array roughly ten thousand times per draw; past sixteen
concurrent workers the memory system, not the cores, sets the rate.

Confirmed independently by `calibration-at-1pct` arm D's 48-draw sizing smoke:
**75.03 s/draw at 16 workers** (median 74.43, max 132.32), within 2.4% of the
16-worker row above. Two measurements on different code paths agreeing to that
tolerance is what the row rests on.

**Standing configuration: 16 workers on this 32-core instance**, for arm D, 7.0
and 7.1 alike. Not `nproc --all`, which costs 4% wall-clock and gains nothing.
The smaller-instance question — whether 16 workers on a 16-vCPU box would contend
as much as 32 do here, since bandwidth scales with instance size in this family —
is **not being tested**; the saving would be marginal and a second instance shape
is another thing to get wrong. Decided 2026-09-20.

**Standing step before any EC2 sweep.** Measure per-draw cost end to end at the
worker count the sweep will actually use, with every worker busy — never from a
component sum, a low-worker run, or a handful of draws. Skipping it cost a 4.7×
miss on arm B (34 s predicted from two laptop workers, 159.7 s observed at 32).
A four-point scaling curve at 1 / 4 / 16 / 32, two draws per worker, costs about
fifteen minutes and gives the right worker count as well as the cost, which a
single full-worker smoke does not.

Two further traps, both hit on this workload. `nproc` honours `OMP_NUM_THREADS`,
which `cloud/run.sh` exports as 1, so `--workers $(nproc)` silently launches one
worker — use `nproc --all`. And a projection must divide by the worker count the
smoke actually used: `calibration_at_1pct` divided by a hardcoded 32 regardless,
which understated arm D's main pass by exactly 2× until it was fixed.
