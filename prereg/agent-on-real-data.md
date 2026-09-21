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

**One fetch, on the holdout host, for the whole span.** The full 2005-01-01 to
2025-12-31 adjusted series is fetched **once**, on the holdout host, and hashed
there. **The holdout host is the EC2 c7a.48xlarge `i-0e0c1484de3c755ad`** (ssh
alias `og-c7a`), which is never the agent's machine. From that single fetch:

- the **in-sample rows (2005-01-01 to 2022-12-31)** are exported to the agent's
  machine as derived files, each with its own hash and the hash of the fetch it
  came from;
- the **holdout rows (2023-01-01 to 2025-12-31)** stay on the holdout host and are
  never copied to the agent's machine.

**Why once.** Back-adjusted closes are rewritten at every later dividend and
split, and the vendor revises and rounds them, so two fetches on different dates
are not one series and do not hash the same. A single fetch is the only way for
in-sample and holdout to be one hashed series, with every derived file traceable
to it.

**Before any bar is opened**, a manifest (`data/etf_manifest.json`, the ADR
pattern) records: the universe commit, the holdout host, source, endpoint,
request parameters, download date, adjustment method, tzdata and calendar
versions, and a hash, row count and first/last date for the fetch and for each
derived file. Raw series stay out of git.

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

*Confirmed 2026-09-21.* Three years rather than two because the per-run Sharpe standard error is 0.58 rather
than 0.71 (below). Whole calendar years because the brief asks for it. The slice
from 2026-01-01 to the search date is **in neither**: it keeps 6.5's holdout to
whole years, and keeps 6.9's sealed forward window strictly after the search
date, where it has to be.

**The holdout is never on the machine the agent runs on.**
- Nothing is fetched on the agent's machine. It receives only the exported
  in-sample rows from the holdout host's single fetch.
- The in-sample loader refuses any date on or after 2023-01-01. This is a hard
  check, not a filter.
- Submissions are graded only on the holdout host, `i-0e0c1484de3c755ad`, after
  every submission is committed.

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

### Features and class

As ROADMAP 6.5: **K = 40** price-based, dollar-neutral cross-sectional signals
with strict one-day lag, committed in their own feature-list commit before any
run. All are dollar-neutral, so the zero-return null is the right null and no
benchmark subtraction is needed. **Class: signed subsets of size ≤ 3 (82,240
members)**, admissible by preflight at this length: bar 1.14, power **0.27** at
reference Sharpe 1.0, above the 20% floor. It would fall back to unsigned
depth-3 (power 0.43) or signed depth-2 (0.53) only if this were inadmissible,
and it is not.

### Arms, matching Phase 7 as amended

claude-sonnet-5, one fixed in-sample panel, **40 runs per arm**:

| arm | certification route |
|---|---|
| **control** | none; the agent searches and submits |
| **declared-class gate** | full-class null over the signed depth-3 class, α = 0.05 |
| **prior-weighted α** (item 2, `prereg/prior-weighted-alpha.md`) | a short list of up to 5 specifications declared before the first `evaluate`, and refused if late, tested by Reality Check at **α_prior = 0.04**; the search tested against the class at **α_search = 0.01** |
| **replay gate** | the process null of 7.2 part two, **conditional**: it runs only if 7.2 part two is built when 6.5 goes live. It is not stubbed. If absent, the arm is recorded as deferred and 6.5 runs with three arms. |

Reported beside every verdict, per the Phase 7 amendment: item 1's bracket where
a decision was not replayable, and item 6's bits of selection. Twin calibration
(item 5) is not run here. Its per-dataset twins are reserved for 7.4, where the
dataset is the question.

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

**Labels, fixed.** The point is **"expected out-of-sample Sharpe under a
search-only decay model"**. The interval is **"predictive interval for the
realized out-of-sample Sharpe under the same model"**: it includes the holdout's
own sampling error, so it is wider than an interval for the expectation.
**Reported, never a decision input.** No verdict, tier or threshold reads either.

**What the model assumes, and how far it is off where measured.** All decay is
selection: the null-max is how far search alone lifts the maximum. The point is
exactly `estimator.bootstrap.deflate`'s `sr_deflated = sr_sel − mean(M_b)`, whose
bias SCOPE measures ("Effective breadth"; "The headline cell"), with an oracle
ceiling of 1.0, so with a real edge present. Predicted decay minus realized
decay is **+0.017** at the headline cell (rho = 0, N = 1,000) and between
**−0.031 and +0.029** across rho 0–0.9 and N 10–1,000. **Near-unbiased there**, in
either direction. Two things are not covered by that measurement and are
stated rather than assumed:
- **those searches were oblivious menus**, not an adaptive agent;
- **the declared-class gate's `M_b` is the class maximum.** For a searcher that
  does not reach the class maximum, P2 makes the class null-max larger than what
  its own search lifted, so the point **over-deflates** by the searcher's
  shortfall. The size of that shortfall on real data is unmeasured.

Costs and regime change are outside the model entirely.

### Checks on `sr_deflated`

1. **Coverage on synthetic data, one-sided.** No proposition predicts nominal
   coverage for `SR_obs − M_b + SE·Z`, and with an exhaustive searcher under s0
   over-coverage is expected. So the check is **one-sided**: under-coverage is
   the failure, and over-coverage is reported as the conservatism it is. On s3
   the per-side miss rates are reported, gating nothing.
   **Prospective only.** Stored runs kept the gate's critical value and null
   quantiles, not the draws `M_b`, so the check runs on synthetic runs made
   after this goes live, with `M_b` stored.
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
2. **`sr_deflated` synthetic coverage (one-sided).** On s0, prospective runs:
   fails **iff the upper end of the Wilson 95% interval of the coverage is below
   0.95**, meaning under-coverage is demonstrated. No exactness is claimed.
   - *Holds:* reported on the ETF holdout with the synthetic coverage beside it.
   - *Fails (under-covers):* too narrow even where its model holds. Reported on
     the ETF holdout labelled "uncalibrated, too narrow".
   - *Coverage above nominal:* the expected direction, reported as
     conservatism, with its size.
3. **The pooled PASS-versus-FAIL readout is descriptive.** No threshold. If PASS
   does not predict holdout, that is the result (ROADMAP 6.5).

## Cost

Seat: 160 runs (four arms of 40) at the measured $0.268 mean per run, **about
$43**, or about $32 if the replay arm is deferred. Local: feature building and
the gates. Holdout host: the single fetch, the export, and grading, minutes of
instance time. The synthetic coverage check runs prospectively on new runs with
`M_b` stored.

## Open, to fix before live

- The universe rule's volume threshold and the exact ETF list: their own commit.
- The feature list: its own commit.
- **Checked:** stored runs kept only the critical value (`runs.csv` has
  `critical_value`, and no null draws), so the coverage check is prospective.
- **Whether 7.2 part two exists** when this goes live decides whether the replay
  arm runs.
