# agent-on-real-data (6.5): what the gate does when an agent searches real data

**DRAFT — committed but not live.** It authorises nothing; no bar is downloaded,
opened or summarised, and no run starts, until it has been read and its open
choices are fixed. ROADMAP 6.5 is the design this refines.

## Question

Everything the agents have done so far, they have done on a synthetic panel with
a known oracle. On a fixed panel of liquid US ETFs with real structure, what does
the gate certify, and do its verdicts predict what happens out of sample?

## Design

### Data, and why not the ADR vendor

**The vendor's free tier refuses daily bars too.** Probed 2026-09-21, status
codes only: SPY daily for 2005-01-03..07 and for 2023-01-03..06 both returned
**HTTP 403 `NOT_AUTHORIZED`** ("Your plan doesn't include this data timeframe").
The two-year window applies at every frequency, so it cannot supply 2005–2025.

**Source: Yahoo Finance's chart endpoint** (`query1.finance.yahoo.com/v8/finance/chart`),
the source of `data/SPY_daily.csv` and the one ROADMAP 6.5 names. Reachable on
2026-09-21 (HTTP 200, body discarded). Adjusted close is **split- and
dividend-adjusted**, so returns from it are total returns. For a short position
that is the right sign, because the short pays the dividend.

**Before any bar is opened**, a manifest (`data/etf_manifest.json`, the ADR
pattern) records: the universe commit, source, endpoint, request parameters,
download date, adjustment method, tzdata and calendar versions, and a hash, row
count and first/last date per file. Raw series stay out of git.

**Survivorship, noted.** The universe is "ETFs with continuous daily history
from 2005-01-01 through the end of the holdout", fixed by a rule and committed
in its own commit before any download (ROADMAP 6.5). That conditions on survival
**through the holdout**. Funds that closed are absent, and so are their holdout
returns. For a dollar-neutral cross-sectional book this biases *which* assets
are compared, not the level of returns, but it is a bias, and it is stated
rather than assumed away. Survivorship-free ETF history would need a paid source.

### Split: explore and no-touch

**Holdout: 3 years, 2023-01-01 to 2025-12-31, daily.** In-sample: 2005-01-01 to
2022-12-31, which is 4,531 NYSE sessions.

*These two choices are proposed here and are the author's to confirm.* Three
years rather than two because the per-run Sharpe standard error is 0.58 rather
than 0.71 (below). Whole calendar years because the brief asks for it. The slice
from 2026-01-01 to the search date is **in neither**: it keeps 6.5's holdout to
whole years, and keeps 6.9's sealed forward window strictly after the search
date, where it has to be.

**The holdout is never on the machine the agent runs on.**
- The in-sample download requests end at 2022-12-31. No holdout date is ever
  requested on the agent's machine.
- The in-sample loader refuses any date on or after 2023-01-01. This is a hard
  check, not a filter.
- The holdout is downloaded, and submissions graded, only on the grading host
  (the EC2 instance, or another machine that is never the agent's), after every
  submission is committed.

**Ancestor-commit guard, as for 7.4.** Feature building refuses unless the
universe commit, the feature-list commit and this pre-registration's live
commit are ancestors of HEAD and unmodified in the working tree. Holdout grading
refuses unless, in addition, a **sealed-submissions commit**, holding every
run's submission and verdict, is an ancestor.

### Execution, registered: identical in-sample and out, and across arms

| assumption | value |
|---|---|
| timing | signal computed at the **close of day t** from data through t; position held from the **close of t+1 to the close of t+2**. One full day of implementation lag. |
| cost | **5 bps one-way per unit of turnover** (sum of absolute weight changes) |
| cost sensitivity | **2× (10 bps)**, reported beside every net figure; matches ROADMAP 6.5's 10 bps readout |
| borrow | **50 bps a year on short notional**, charged daily at 50/252 bps |
| notional | **$1 million gross**, about $25,000 per ETF at 40 names, stated to be small enough for zero market impact in these ETFs; the universe rule also requires a median daily dollar volume that keeps every position under 0.1% of it |
| prices | adjusted closes, as above |

**Why 5 bps is generous.** Quoted spreads on the most liquid ETFs are well under a
basis point. The universe includes bond, commodity and international funds whose
spreads are wider, so 5 bps one-way per unit turnover sits above typical
half-spread plus commission for all of them, and 10 bps sits above it by a
margin. Both are **assumptions, not measurements**, and labelled so.

### Features, class, arms

As ROADMAP 6.5: **K = 40** price-based, dollar-neutral cross-sectional signals
with strict one-day lag, committed in their own feature-list commit before any
run. All are dollar-neutral, so the zero-return null is the right null and no
benchmark subtraction is needed. **Class: signed subsets of size ≤ 3 (82,240
members)**, admissible by preflight at this length: bar 1.14, power **0.27** at
reference Sharpe 1.0, above the 20% floor. It would fall back to unsigned
depth-3 (power 0.43) or signed depth-2 (0.53) only if this were inadmissible,
and it is not. **Arms:** control and gate, 40 runs each, claude-sonnet-5, one
fixed in-sample panel.

### Out-of-sample readouts

**Per-run Sharpe SE at the holdout length** (Lo 2002, iid returns): **0.58** at
a true Sharpe of 0 and **0.71** at 1.0 over 3 years (0.71 and 0.87 over 2). **A
single run's holdout Sharpe cannot tell 0 from 1.** So:

- **Primary, pooled, as 6.2:** the **median holdout Sharpe of PASS submissions
  against FAIL submissions**, across runs, gross and net at 5 and 10 bps, with a
  bootstrap interval over runs. That interval reflects run-to-run variation on
  **one** future. All runs share the same holdout, so it is not an interval over
  futures, and the report says so (ROADMAP 6.5, "What this cannot show").
- **Secondary, per run:** whether each run's realized holdout Sharpe falls
  inside its `sr_deflated` interval (next section), with coverage pooled across
  runs.

### Verdict addition, all gates: `sr_deflated`

For every gate that prices a null-max distribution — the declared-class gate
(full-class null) and the replay gate (process null) — the verdict reports
`sr_deflated`. The holdout tier prices none and reports "n/a".

**Definition.** With the submission's in-sample Sharpe `SR_obs`, the gate's
null-max draws `M_1..M_B`, and the holdout Sharpe standard error `SE_oos`, the
predictive distribution is the Monte Carlo sample

  F_b = SR_obs − M_b + SE_oos · Z_b,  Z_b ~ N(0, 1), b = 1..B,

with point `sr_deflated = SR_obs − mean(M)` and the **95% interval** its 2.5 and
97.5 percentiles. `SE_oos = sqrt((1 + sr_deflated²/2) / years_oos)`.

**Label, fixed:** "expected out-of-sample Sharpe under a search-only decay
model". **Reported, never a decision input.** No verdict, tier or threshold
reads it.

**What the model assumes, and which way it errs.** All decay is selection:
the null-max is how far search alone lifts the maximum. When a real edge
exists, selection lifts the observed Sharpe *less* than the null-max, so the
model **over-deflates**, and the forecast is biased low. Costs and regime
change are outside it entirely.

### Checks on `sr_deflated`

1. **Coverage at nominal on synthetic data.** On s0 draws, where the model's
   assumption holds, the 95% interval should cover the realized OOS Sharpe at
   about 95%. This is predicted by the construction under the null, to a normal
   approximation. On s3 draws, where a real edge exists, the predicted
   direction is realizations **above** the interval more often than 2.5%
   (over-deflation), reported rather than gated.
2. **On the ETF holdout: under-coverage is expected**, with realizations
   **below** the interval, attributed to costs (net figures) and regime change.
   Reported with its direction. The gross-versus-net gap says how much of it is
   costs.
3. **CRPS of the agent's stated distribution.** The agent's `predict` slot gives
   a mean and a standard deviation. Its CRPS against the realized holdout Sharpe
   is reported beside the CRPS of `sr_deflated`'s predictive distribution
   against the same number. Lower is better. This asks whether the agent's
   stated belief about its own submission beats the search-only deflation. A
   zero standard deviation is scored as a point forecast (absolute error).

## Decision rules

Per `prereg/README.md`.

1. **Admissibility, fixed now.** Signed depth-3 at power 0.27 ≥ 0.20: admissible.
   The class does not change after any bar is opened.
2. **`sr_deflated` synthetic coverage (rule, two-sided).** On s0, the Wilson 95%
   interval of the interval's coverage contains 0.95. Exactness is licensed by
   the construction under the null, to a normal approximation, and that
   proposition is named here.
   - *Holds:* `sr_deflated` is reported on the ETF holdout as calibrated under
     its own assumption.
   - *Fails low (coverage under 95%):* the interval is too narrow even where its
     model holds. It is reported on the ETF holdout with an "uncalibrated,
     too narrow" label.
   - *Fails high:* too wide, reported as conservative.
3. **The pooled PASS-versus-FAIL readout is descriptive.** No threshold. If PASS
   does not predict holdout, that is the result (ROADMAP 6.5).

## Cost

Seat: 80 runs at the measured $0.268 mean per run, **about $21**. Local: feature
building, both gates, grading and `sr_deflated` on stored null-max draws. The
synthetic coverage check reuses stored s0 and s3 runs where the null-max draws
were kept, and recomputes them locally where they were not. No EC2 except as
the grading host.

## Open, to fix before live

- **The holdout length and start (3 years from 2023-01-01) are proposals** pending
  confirmation.
- The universe rule's volume threshold and the exact ETF list: their own commit.
- The feature list: its own commit.
- **The synthetic coverage check needs `M_b` stored per run.** Whether the
  existing runs kept it is to be checked before this goes live.
