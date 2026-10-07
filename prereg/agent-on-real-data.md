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
there. **The holdout host is the EC2 c7a.8xlarge `i-0886a189b85d4d051`** (ssh
alias `og-32`), which is never the agent's machine. (Changed on 2026-09-22,
before the fetch, from the c7a.48xlarge `i-0e0c1484de3c755ad` named when this was
first drafted. The session moved to this box; no data had been fetched on
either.) **The agent harness never
runs on this host.** From that single fetch:

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

### The holdout's two copies, and how it is opened

**Primary copy: the holdout host's volume**, `/home/ubuntu/etf/data/raw/etf/holdout`
on the c7a.8xlarge `i-0886a189b85d4d051`. 40 CSVs, one per panel ticker,
2023-01-01 to 2025-12-31, `date,adjclose,volume`. Its content hashes, which any
restored copy must reproduce:

- sorted file list: `385a11f0f29371de85f552350b4277498a48e39bbeff27440fa92b9cbf46e28d`
- contents (SHA-256 over the sorted per-file SHA-256 lines):
  **`8d92a7b2f527dd619a3944fb248bccc769e26ad99b38d1336fef34dffab031c8`**

Reproduce it with `cd <dir> && sha256sum $(ls -1 | sort) | sha256sum`.

**Second copy: a symmetric-encrypted archive on the agent machine**,
`~/Desktop/etf_holdout_2023_2025.tar.gz.enc`, 398,896 bytes, SHA-256
**`4fcaf8cbad3e003c4a82b98eaca005b41333e3e455ffea9490858f3a86093494`**. Made with
`openssl enc -aes-256-cbc -pbkdf2`. **Its passphrase is held by the author alone.
It is not on this machine, not in this repository, and not available to any agent
session.** The plaintext was never written to the instance: the archive was piped
over ssh and encrypted locally.

Decryption, for the record and not to be run by any agent session:

    openssl enc -d -aes-256-cbc -pbkdf2 -in etf_holdout_2023_2025.tar.gz.enc | tar xzf -

**How the holdout is opened, at 6.9 and nowhere earlier.** Decrypt to a temporary
directory **on a machine where no agent session is running**, grade the sealed
submissions there, and delete the plaintext when grading ends. The encrypted
archive and the host's copy are what persist.

**Enforced, not merely stated** (`data/etf_loader.py`, tests in
`tests/test_etf_loader.py`): the loader refuses any path whose suffix is `.enc`,
`.gpg` or `.asc`, refuses any path under `~/Desktop`, and refuses outright — not
filters — any file containing a row on or after 2023-01-01. `.gitignore` also
refuses those suffixes and a `Desktop/` path, so a sealed copy cannot be staged.

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
- Submissions are graded only on the holdout host, `i-0886a189b85d4d051`, after
  every submission is committed.

**Ancestor-commit guard, as for 7.4.** Feature building refuses unless the
universe commit, the feature-list commit and this pre-registration's live
commit are ancestors of HEAD and unmodified in the working tree. Holdout grading
refuses unless, in addition, a **sealed-submissions commit**, holding every
run's submission and verdict, is an ancestor.

### One feature is contaminated for human declarations

**Recorded 2026-09-24.** While the panel builder was being written, the
researcher observed the in-sample statistics of the single-feature
specification **`ret1_z`**: mean −8.01e-04 a day, annualised Sharpe −2.077, net
of the registered costs. It is recorded as a look in `data/etf_manifest.json`.

**Consequence.** A **human-declared** specification involving `ret1` in either
form (`ret1_z`, `ret1_rank`) or its sign is **not oblivious** and is
**inadmissible for the prior-weighted short list**, whose whole claim is that
the list preceded the data. Any other human declaration touching that feature
carries the same disclosure.

**The agent's declarations are unaffected.** The agent never saw that number: it
was printed in a build transcript the agent has no access to, and the agent's
short list is declared inside its own session before its first `evaluate`. An
agent that declares `ret1` on its own is oblivious in the sense the
pre-registration means.

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

## The replay arm is conditional on the class table, not deferred

**Recorded 2026-09-24.** The Arms table calls the replay arm "conditional: it
runs only if 7.2 part two is built when 6.5 goes live. It is not stubbed. If
absent, the arm is recorded as deferred." 7.2 part two **is** built, so on the
original reading the arm simply runs.

`prereg/agent-pilot.md` shows that reading is incomplete. On a **net-of-cost**
panel — which this one is — the replay priced a statistic that was not the one
the search optimised, and the identity-replicate guard refused all three
replay-arm pilot runs with score gaps around 7.4. Process replay was *present*
and *unable to certify*.

**So the condition is restated, before 6.5 runs:** the replay arm runs **iff the
declared class is tabulated for this panel** (`environments/class_table.py`), so
that `evaluate` and every replicate read the same stored net streams. The ETF
panel's table at depth 3 is 82,240 members and 2.81 GB, built once and chunked;
building it is a prerequisite of the arm, not an optimisation of it.

- *Table built:* the arm runs, and its verdicts price the net statistic.
- *Table not built:* the arm is recorded as **deferred for a stated reason** —
  the null cannot price this panel's statistic without it — and **not** as
  deferred for absence of 7.2, which would be false.

This changes no rule and no threshold. It names the thing the arm was always
conditional on, which the pilot made visible.

## Amendment — 2026-09-25, committed not live. A fourth arm: orientation

Registered in full in `prereg/agent-cell.md`; what this file fixes is its place
in 6.5 and what is read from it here.

**The arm.** The replay-gate arm, plus one paragraph delivering a summary of the
**feature panel's structure and nothing about returns**
(`prereg/AGENT_PROMPTS_REAL.md` amendment 6). The table is a function of the
feature matrix alone, so a menu chosen from it is data-oblivious in `SCOPE.md`'s
sense and every null this file uses stays valid; the argument and its enforcement
are in `agent-cell.md`.

**Orientation costs no evaluation budget and is not a trial.** It changes what
the agent is told before it starts, not what it may do: the tool list is the
replay-gate arm's, unchanged.

**Readouts for this arm**, beside the existing ones. Predicted directions, each
with its opposite:

| readout | predicted | if it goes the other way |
|---|---|---|
| z/rank near-duplicate pairs evaluated (both members hit) | **fewer** | orientation did not help the agent see the duplicates, and the table's clearest content went unused |
| moves to `submit` | **fewer** | the table lengthened the search rather than focusing it |
| `pick_prior` use | **more** | structure alone does not support a prior, which `agent-cell.md`'s masking note already allows for |
| trigger changes | **fewer** | the agent's stopping rule is no better chosen for knowing the map |
| accepted picks | **more** | the agent still names choices its own rule does not make |

**The registered failure mode.** Stated confidence rises with **no change in the
deflation gap** — the agent feels it understands the data. That is orientation
making the agent *worse calibrated while looking better behaved*, and it is named
here in advance so it cannot be written up as a success.

**The haircut regression is reported for this arm beside the others.**

**Nothing runs on this amendment.** The arm is committed-not-live with the rest
of `agent-cell.md`, and 6.5's own launch decision is unchanged by it.

## Open, to fix before live

- The universe rule's volume threshold and the exact ETF list: their own commit.
- The feature list: its own commit.
- **Checked:** stored runs kept only the critical value (`runs.csv` has
  `critical_value`, and no null draws), so the coverage check is prospective.
- **Whether 7.2 part two exists** when this goes live decides whether the replay
  arm runs.

## The prior-weighted arm is DEFERRED to the next agent cell, unbuilt — 2026-10-01

**Recorded after the replay-gate and orientation arms were read and before any further
arm runs.** 6.5 runs **three of its four registered arms**: control, declared-class
gate and replay gate, with orientation as the amendment's fourth. The prior-weighted
α arm is not run on this panel and is not built.

**What it would need, both new:**
- **a grammar element**: a `short_list` tool, declaring up to 5 specifications before
  the first `evaluate` and refused if late. It is listed in
  `experiments/real_prompts.TOOLS_FOR` and nothing builds it;
- **a pricing path**: the short list tested by Reality Check at α_prior = 0.04 and the
  search tested against the class at α_search = 0.01. Neither `price_runs` nor
  `certify` computes it.

**The reason it is deferred rather than built now: on this panel no verdict can
differ.** Both of the arm's tests are bounded by measurements already made.
- **The search test** is against the class at α_search = 0.01. The class maximum is
  **0.3159** and the declared-class null maximum averages **0.64–0.68**: all 40 priced
  runs have p = 1.0000 at the class tier. Nothing can reject at 0.01.
- **The short-list test** is a Reality Check at α_prior = 0.04 over at most five
  pre-declared members. Its most favourable case is a list of **one**, the class
  maximum itself, declared in advance. That single test was computed on 2026-10-01
  from the class table, with the gate's own stationary bootstrap, block length 9,
  B = 5,000 and seed 20261001: **p = 0.0580**, above 0.04. A longer list can only enlarge
  the null maximum, and no member scores above 0.3159. The margin is not wide
  (0.058 against 0.04), so this is stated as a measurement of the best case and not as
  a theorem for every list.

Building a new grammar element and a new pricing path to produce a verdict fixed in
advance would spend seat runs and code on a known answer.

**What this does not settle.** Whether a pre-declared short list buys power is the
arm's question, and it stays open. It needs a panel where the class maximum clears the
null, and the next agent cell is where the arm is built, tested and run, under a
registration written before it.

**Recorded with it: a routing defect fixed before the declared-class gate arm ran.**
`experiments/agent_cell.py` chose an arm's tools by `arm == "control"`, so the
declared-class gate arm, registered for `evaluate` and `submit` exactly as control is,
would have received the replay grammar under a prompt describing `evaluate` and
`submit`. Tools are now chosen from the registered table and checked against it on
every build, and an arm whose tools are not built is refused before anything is
created (`tests/test_agent_cell.py`). No run was made under the defect.

## 6.5 in-sample CLOSED — 2026-10-01

**What ran.** Four arms of 20 runs, all on the in-sample panel (2005-01-01 to
2022-12-31), claude-sonnet-5, seat, deferred pricing:
`runs/etf_control`, `runs/etf_declared_class`, `runs/etf_replay` and the
orientation amendment's `runs/etf_orientation`. **Integrity clean on all 80**: every
run complete and submitted, zero errors, zero unregistered refusals, the pinned model
on every run, and every score any agent was shown equal to the verified class table.

**Deviations, all recorded where they arose:**
1. **The prior-weighted α arm did not run: deferred to the next agent cell, unbuilt**
   (this file, 2026-10-01). On this panel no verdict could differ: the class tier is
   p = 1.0000 on every priced run, and the best possible short list, the class maximum
   declared alone, prices at p = 0.0580 against α_prior = 0.04. **6.5 therefore ran
   three of its four registered arms, plus the orientation amendment's fourth.**
2. **Replay runs 0–5 were voided and redone** at their indices, after a class-table
   cache defect truncated the shared table under concurrent workers
   (`prereg/agent-cell.md`, disposition by timestamp).
3. **The control and declared-class logs were priced before they were committed**, so
   unlike the other two arms they are not fixed in history ahead of their verdicts.
   Pricing inserts only `class_p` and `priced_from_log`; the sessions are unaffected.
4. **The class p is at B = 200** (the certifying null's B), so its resolution is 1/201.
   Immaterial here: every p is 1.0000.

**Readouts, as registered:**
1. **Verdict distribution.** The certifying tier is the declared class (ROADMAP,
   2026-09-30): **CERTIFIED 0/80** across all four arms, **0/20** in the declared-class
   gate arm itself, Wilson [0, 0.161] per arm. The class maximum is **0.3159**
   (`[vol252_z+, vol252_rank−]`) against a mean null maximum of 0.64–0.68.
2. **Holdout Sharpe, PASS against FAIL:** **no PASS submission exists**, so the
   comparison has no PASS group. At 6.9 it is reported as "no PASS", and the FAIL
   side — whether anything the gate refused would have earned out of sample — is
   graded on its own.
3. **The haircut regression:** reported in `runs/agent_cell_read_cell3.txt`, and **not
   interpretable** on this panel: each arm submits 3 to 7 distinct members, so the
   in-sample Sharpe barely varies.
4. **Feature convergence.** The agents converge on a beta/volatility family:
   `beta252_z+` appears in **47 of 80** submissions and `vol252_rank−` in **40**; the
   commonest submission is `[vol252_rank−, beta252_z+]` (25 runs), then `[beta252_z+]`
   (18) and `[vol252_z+, vol252_rank−]` (9). There are no PASS submissions to compare.

**`sr_deflated`, reported and never a decision input:** −0.36 to −0.54 by arm mean.

**The headline behavioural result, ranked above the FAIL verdicts: the deflation gap
is +0.53 in every arm, the control included** (medians 0.522–0.539). Agents state
about +0.06 to +0.17 for submissions whose search-only expectation is −0.36 to −0.54.
The gate's presence does not change it, and neither does an orientation table.

**What remains of 6.5: the holdout, at 6.9.** 2023-01-01 to 2025-12-31, sealed, opened
once, grading all 80 submissions gross and net. Nothing else in 6.5 runs.

## Recorded 2026-10-02: rank ties are platform-dependent, and what that means for 6.9

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

**Where 6.5 ran.** Every 6.5 agent session ran on the laptop (arm64), and **all four arms
were priced on the laptop** by `experiments/price_runs.py` (`--workers 2`, from this
machine's shell history), against the ETF class table built on the laptop
(`data/class_tables/`, 2026-10-01). The re-grades ran there too. **6.5's in-sample record
is therefore one platform's throughout**, and its verdicts stand as recorded.

**Submissions and logs touching the two features.**
- **One submission uses either: control run 8**, `[ret1_rank −, mom5_rank +]` (`mom5_rank` itself matches across platforms). Control has
  no session log, so there is no log re-execution to pass or fail. What exists was
  checked: all of its `evaluate` results, and its submitted score, equal the laptop's
  class table exactly. That is part of the 4,567 evaluations checked on 2026-10-01 with
  no mismatch.
- **All 40 runs of the two evaluate/submit arms** (control, declared-class) evaluated
  some specification containing feature 1 or 31; all equal the laptop's table.
- **The grammar arms** (replay, orientation) hold neither feature in any logged support.
  Their `extend_best` and `swap_worst` moves score every extension, so both features were
  scored as candidates. **Log re-execution passed on all 40** (integrity PASS,
  `regrade_2026-09-28.json`), on the laptop.

**6.9 grading must build in-sample and holdout features on one pinned platform.** The
holdout is opened only on a machine where no agent session is running, and it is never
on the agent's machine (above), so grading runs on the x86 holdout host. There it
rebuilds the features for the whole span, in-sample lookback and holdout together, on one
platform, records that platform and the matrix's SHA-256 beside the grades, and grades
every submission against that one build. **What this changes, stated before the
holdout opens:** on the holdout host `ret1_rank` and `drawdown_rank` break ties
differently from the in-sample features the agents searched, so a submission containing
either is graded on a feature that differs, on tie days, from the one it was chosen on.
**That is control run 8 alone**, and its grade is reported with this note. No other
submission contains either feature.

## Deviation, recorded 2026-10-02: three arms registered at 40 ran at 20

**What.** "Arms, matching Phase 7 as amended" registers **40 runs per arm**. Control,
declared-class gate and replay gate each ran **20** (`runs/etf_control`,
`runs/etf_declared_class`, `runs/etf_replay`). The orientation arm's 20 is its own
registration (`prereg/agent-cell.md`, twenty per cell). **6.5 therefore holds 80 runs**,
not the 120 registered for the three original arms, and 6.9 grades 80 submissions.

**Why.** `experiments/agent_cell.py` defaults to `--runs 20`, and the launch lines given
for these arms — `--runs <N>` for replay and orientation, filled with 20; `--runs 20`
written out for control and declared-class — were not checked against this file's 40.
The close-out of 2026-10-01 then recorded "four arms of 20" without flagging it. **An
error in the run lines, not a decision**, and it was not recorded when it happened.

**The stop was not data-dependent.** Each arm's count was fixed on its command line
before its first run, and each ran to exactly that count: `run_config.json` shows
`runs: 20` and 20 indices run in each directory, with no early stop and no extension.
The replay arm's 20 was set at its first launch, before any 6.5 verdict existed, and
kept when the voided runs were redone. The orientation, control and declared-class arms
were launched later — after the six voided replay runs had been priced in-line, and
control and declared-class after the replay and orientation arms had been priced — so
verdicts existed when their 20 was typed. Their 20 copies the replay arm's and the
runner's default; no rule, script or command read a result to set it, and no arm's
count differs from another's. No run was dropped, and none was added after a look.

**What it costs: detectability at n = 20 against the registered n = 40.**

| readout | at n = 20 per arm (as run) | at n = 40 (as registered) |
|---|---|---|
| verdict distribution: upper Wilson end when 0 of n certify | 0.161 | 0.088 |
| smallest true certification rate giving at least one certificate with 80% probability | 0.077 | 0.039 |
| width of the Wilson interval at a 50% rate | 0.40 | 0.30 |
| deflation gap, one-sample, detectable mean (sd 0.035, as measured) | 0.023 | 0.016 |
| arm against arm (Mann-Whitney, two-sided 0.05, 80%), detectable effect in sd | 0.91 | 0.64 |
| orientation (20, as registered) against an arm at n, detectable effect in sd | 0.91 | 0.79 |
| PASS against FAIL holdout mean, standard error over runs (one future; per-run SE 0.58) | 0.130 | 0.092 |

**What it does not change.** No verdict differs because of it: every one of the 80
runs is p = 1.0000 at the class tier, against a class maximum at half the null level,
and no run count reaches a certificate on this panel. The deflation gap's headline
(+0.53 in every arm) sits far above the 0.023 detectable at n = 20. **What it does
change is resolution**: every interval in the 6.5 read is wider than registered, by the
factors above, and the arm comparisons see only effects about 1.4 times larger than
the registration sized for. Whether to run the missing 60 runs is a separate decision,
and this note does not make it.

## Recorded 2026-10-02: registered as "feature names are not masked"; in fact agents were shown numbers only

`prereg/AGENT_PROMPTS_REAL.md` §4 registers that "Feature names are not masked", on the
grounds that the names describe arithmetic. **No 6.5 agent was shown a feature name.**
Every tool takes and returns feature numbers 0–39, in one fixed order on every panel,
and the system prompt says only how many features there are. A search of all **87 ETF
run files** (`runs/etf_*`, `runs/shakeout_etf_orientation`, `runs/agent_pilot_etf_seat`)
found none of the 40 names in any prompt, tool call, tool result or assistant text.
What the agents saw was the numbering, the same on every run: number 32 was `beta252_z`
and number 31 was `drawdown_rank`.

**No verdict changes.** The registration said names *could* be shown; it did not
require them to be. Every tool, the class, the class tier and the replay tier work on
the numbers, and the runs are priced on what was actually shown. What changes is how
readouts that mention names should be read. "Agents converged on `beta252_z+`" means
they converged on **number 32**, and a reading that appeals to the name (momentum, low
volatility) is not available. Control run 8's `[ret1_rank −, mom5_rank +]` was, as the
agent saw it, `[1−, 3+]`. The rank-tie note above is unaffected: it concerns the values
behind the numbers.

7.5's masking rationale is corrected for the same reason (`prereg/planted-edge.md`,
amendment of 2026-10-02).

## Deviation, recorded 2026-10-06 (America/Chicago): the second holdout copy cannot be opened

**The author can no longer recall the passphrase for the second copy**,
`~/Desktop/etf_holdout_2023_2025.tar.gz.enc` (registered above as the symmetric-encrypted
archive).
- **The file is intact and unmodified.** Its SHA-256 was verified on 2026-10-06 as the
  registered `4fcaf8cbad3e003c4a82b98eaca005b41333e3e455ffea9490858f3a86093494`
  (398,896 bytes). Only the encrypted file was hashed.
- **It cannot be opened**, so it is no longer a usable source.
- **The primary copy on the holdout host** (`/home/ubuntu/etf/data/raw/etf/holdout` on
  `i-0886a189b85d4d051`) **is the sole usable source.** Its registered content hash,
  `8d92a7b2f527dd619a3944fb248bccc769e26ad99b38d1336fef34dffab031c8`, is checked on the
  host as the first operator step of the grading (`prereg/holdout-grading.md`). If it
  does not match, there is no second copy to fall back on, and nothing is graded.
- **No holdout data was read in establishing this.**

**Withdrawal, 2026-10-06 (America/Chicago), of the deviation above (`3b049b6`).** The
author has recalled the passphrase for the second copy. It was verified on 2026-10-06 by
piping the decrypted stream into `gzip -t`, which printed OK; no output was written or
displayed, and no holdout data was read. **The second copy is usable, the deviation is
withdrawn, and both copies stand as registered.** 6.5 holdout grading
(`prereg/holdout-grading.md`) still grades from the primary copy on the holdout host, and
checks its content hash `8d92a7b2…` first.
