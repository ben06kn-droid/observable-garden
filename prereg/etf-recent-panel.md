# ETF recent panel: Sancho on liquid ETFs with a recent holdout, a registration

**Status: LIVE, 2026-10-11 (America/Chicago).**
- The author confirmed points 1–11 (answers at `bc547b6`, with the no-data rule fixed at
  `66559aa`). This status is set in a commit touching only this file.
- The fetch script, the cut, the runner and the reader are written after this commit. Each
  refuses to run unless it is an ancestor of HEAD.
- **Nothing has been fetched.** Nothing has run on the holdout host or the box.
- The only run was the laptop design script of section h, outcome-free, on the already-read
  pool: script `bf90274`, output `717e1a9`.
- Amendments are append-only and dated. The [AUTHOR] points are listed at the end.

## a. Disclosures: what was seen before, and what each does and does not weaken

1. **2005–2022 on this list was read before** (`prereg/agent-on-real-data.md`).
   - **What was read:** 4,531 sessions in-sample.
     - The class tier: 82,240 members, p = 1.0000 on all 80 runs.
     - 80 agent sessions (claude-sonnet-5, four arms of 20).
     - Two extra looks: `ret1_z` at Sharpe −2.077, and a best-case short list at p = 0.0580.
   - **It weakens:**
     - This panel's in-sample (2005–2024) re-uses those 18 years. It is not independent of
       what the author has seen.
     - The decision to run this panel was made after those results. That is a forking path
       at the level of panels. No test here corrects for it.
   - **It does not weaken:**
     - The registered tests' size, given the procedure. Sancho's code, the features, the
       split and the levels are fixed before this fetch.
     - **Sancho has never been run on real ETF returns:** no record in `runs/`, and
       `prereg/ml-v2-confirmation.md` says "No holdout row is involved".
2. **The sealed 2023–2025 holdout was opened once,** for the 6.5 grading
   (`prereg/holdout-grading.md`). It was graded 2026-10-06 at `55a39f6`, live `3a5483e`, read
   at `0426352`.
   - **2023–2024 move into this in-sample.** That is a re-use of opened data as in-sample. It
     weakens nothing about the in-sample test beyond item 1.
   - **2025 sits in this holdout,** but it was inside an opened window. The 80 submissions'
     realised returns over 2023–2025 were read. That told the author how ETF-feature
     strategies did in 2025.
     - **It weakens:** 2025 as an unseen period, for the author's choices (including the
       choice to run this panel now).
     - **It does not weaken:** the graded number's mechanics. Sancho never ran on 2025; its
       code and settings are fixed before the fetch; the graded quantity is fixed here.
   - **Only 2026 is untouched:** about 194 sessions to 2026-10-09 (0.77 years; SE about 1.14).
     That is too short to grade alone. **A 2026-only realised value is printed beside,
     descriptive, never deciding** (the author, 2026-10-11).
3. **Sancho was confirmed on planted panels built on these ETF features** (`97d2519`,
   `prereg/ml-v2-confirmation.md`).
   - **The confirmation panels:**
     - X is the real pinned ETF X (2005–2022).
     - The X and V blocks come from the real ETF data.
     - Returns were planted, not real.
   - **It weakens:** generalisation. A certificate here is on the features Sancho's
     configuration was chosen on. It says little about other universes.
   - **It does not weaken:**
     - the test's size, which comes from the bootstrap null on this panel's returns;
     - Sancho's selection, which never saw real ETF returns.
4. **The candidate list itself was named in 2026** (`prereg/etf-universe.md`), from
   well-known ETFs that all traded through 2025.
   - The new rule (section b) stops conditioning on survival. **It does not undo the list.** A
     2005 investor would have had other candidates, some of which later closed.
   - **It weakens:** any claim about a 2005-formed universe.
   - **It does not weaken:** the test, given the list.
5. **The holdout's length** (section g): about 1.76 years at the fetch.
   - The grading can tell little apart. P(held) is about 0.66 if the true Sharpe is at the
     bar, and about 0.36–0.46 if it is 0, for a stream certified at the bar.
   - This is stated before any number exists. That grading is labelled "weak: 1.76 years",
     and a second grading is fixed for 2028 (section g).

## b. Universe: inclusion with no conditioning on survival

**The candidates:** the 40 of `prereg/etf-universe.md`.
- **Equity, US:** SPY QQQ DIA IWM MDY IWD IWF IWN IWO IJH IJR.
- **US sectors:** XLB XLE XLF XLI XLK XLP XLU XLV XLY.
- **International:** EFA EWJ EWG EWU EWC EWA EWH EEM EWZ EWT EWY.
- **Bonds:** SHY IEF TLT LQD TIP AGG.
- **Other:** GLD IYR VNQ.

**The rule** (formation window 2005-01-03 to 2014-12-31):
1. **A bar on every NYSE session from 2005-01-03 to 2014-12-31** (XNYS, exchange_calendars
   4.13.2, as `data/fetch_etf.py`).
   - No gap is allowed: a missing session fails. The old rule allowed a single missing
     session. The author confirmed the stricter rule on 2026-10-11.
2. **Liquidity: median daily share volume over 2005-01-03 to 2014-12-31 of at least 500,000**
   (confirmed by the author, 2026-10-11).
   - It is the old threshold, on the formation window only.
   - Nothing argues for a different number. Share volume is what the old rule used
     (`etf-universe.md`), and Yahoo's volume is split-adjusted.
3. **Ticker, merger or structure changes: NOT verified from any committed record.** No
   claim is made.
   - The old rule 3 was recorded only as checked "separately". No committed record of that
     check was found.
   - Nothing is applied for it. It is listed under the limits (section k).
   - A ticker that stops trading under its symbol goes to the death rule (item 4).
4. **The death rule:** an ETF is dead from the session after its last bar if either:
   - it has no bar on any later fetched session; or
   - it has a silence of 10 or more consecutive sessions.

   Then:
   - its position is closed at its last bar's adjusted close;
   - the exit is costed, and its position is zero after;
   - there is no re-entry;
   - it is never dropped retroactively.

   This is adapted from `prereg/binance-panel.md` (lines 91–93 and 124–133: "dead from the bar
   after its last bar with trades … Its position is closed at the last available bar's price.
   The exit is costed, and the position stays zero after.").
   - **A fetch that returns no data at all** for a candidate (Yahoo can drop delisted
     tickers) is **not a drop.** The ETF is dead from the session after its last bar in the
     last record that holds it.
   - For these 40, that record is the 2026-09-22 fetch on the host, through 2025-12-31.
   - **That older fetch may supply a last bar, used only to close the position** (the author,
     2026-10-11). No other value is taken from it.
   - **A candidate with no data in this fetch cannot be checked against items 1–2,** and the
     old fetch is not used to check it. The cut records it, **nothing runs, and the author is
     asked.** Excluding it silently would condition on survival to the fetch date.
5. **Minimum panel: 30 ETFs** (confirmed). **With fewer than 30, nothing runs and the author is
   asked.**

**How many of the 40 pass, from committed records only:**
- **Item 1: all 40, per the records.** `data/etf_manifest.json` records, for every ticker,
  first date 2005-01-03, 0 missing sessions and no consecutive gap over 2005-01-03 to
  2025-12-31. That window covers 2005–2014.
  - The first date is truncated by the request's start, 2005-01-01. Earlier inception is not
    recorded and not needed.
- **Item 2: not determinable from records for any of the 40.**
  - Medians are recorded only over 2005-01-03 to 2022-12-31 (`fetch_etf.py:130-132`).
  - The lowest there are TIP 815,700, IWO 1,005,800, EWU 1,031,200, SHY 1,075,600, IEF
    1,098,200, IWN 1,305,500 and AGG 1,305,800.
  - A 2005–2022 median above 500,000 does not bound the 2005–2014 median. Volumes in 2005–2008
    were lower for several of these funds.
  - **So between 0 and 40 could fail item 2. Records cannot say more.**
  - **No new look is taken** (the author, 2026-10-11). The host cut decides.
- **Item 3:** not verified from any record (item 3 above; section k).
- **Item 4:** all 40 had bars through 2025-12-31 (the old fetch's 752 holdout rows each). No
  death before 2026 is possible among them.

## c. Windows

- **The fetch:** 2005-01-03 to the last complete NYSE session before the fetch date.
- **In-sample:** rows to 2024-12-31, 5,033 sessions, giving 4,778 feature rows (warm-up 253,
  then the d = 1 lag).
  - **Choice A (adopted by the author, 2026-10-11):**
    - Sancho's walk-forward starts as early as its warm-up and training allow: the first
      scored feature row is 763 (756 plus the d = 1 embargo, as B1), about early 2009.
    - Its whole scored stream to 2024-12-31 is tested: about 4,015 rows.
    - The class runs on all 4,778 feature rows.
  - **Choice B (considered, not adopted; its design numbers are kept in section h):** score
    2015-01-02 to 2024-12-31 only (2,516 sessions), for every test.
    - Sancho still trains from the start.
    - The rows of the formation window, 2005–2014, are never scored.
- **Holdout:** 2025-01-01 to the last fetched session. At a fetch on 2026-10-12, that is
  2025-01-02 to 2026-10-09: **444 rows, 1.76 years.** There is no fallback window.

## d. Tests, the split and the certificate (as `prereg/french-long-history.md`)

| test | 96% level | 90% level |
|---|---|---|
| 1. Sancho, one supplied stream, **d = 1** (the ETF timing) | p < 0.03 | p < 0.06 |
| 2. Sancho, **d = 0, NOT IMPLEMENTABLE** | p < 0.01 | p < 0.02 |
| 3. the class tier, 82,240 members (signed subsets of size ≤ 3 of K = 40), at d = 1 | p < 0.01 | p < 0.02 |
| family-wise | ≤ 5% | ≤ 10% |

- **Sancho:** version 2 as confirmed at `97d2519`.
  - Version 2's base view as configured there: blocks P, X and V; h 5; market-neutral;
    regime always.
  - M2 (rolling 756 and expanding), G3, L {1, 3, 10, 30}.
  - Positions are zero on any ETF after its death, applied after the model.
- **Timing:**
  - d = 1: the signal uses data through the close of t, and the position is held from the
    close of t+1 to the close of t+2 (`prereg/etf-features.md`).
  - d = 0 is held from the close of t to the close of t+1. NOT IMPLEMENTABLE.
- **The certificate is on the WEIGHTED statistic under W2,** h = 1,260: block starts
  ∝ w², the first start from q, q-centring.
- **Printed for each test:**
  - the weighted net Sharpe, p, both verdicts and the weighted L90;
  - beside it, the UNWEIGHTED statistic, its p and L90, labelled "unweighted, descriptive,
    not the certificate";
  - for the streams, the performance line (last 252 and 756 scored rows, 90% intervals);
  - the block length by the registered rule, with the Politis–White median on the last n_eff
    rows beside;
  - for the class, the weighted best member **and the unweighted best member beside** (the
    B1 reader left the latter out; this reader must print it).
- **The validation's limits are printed beside every certificate:**
  - W2's size is checked by simulation, not proved;
  - overshoots of about 10% are not reliably detected;
  - the class checks are weak.

## e. Costs (as the ETF registrations; an assumption)

- 5 bps one-way per unit of turnover, with 10 bps reported beside.
- Borrow at 50 bps a year on short notional, charged daily at 50/252 bps.
- $1M gross notional and zero impact (`prereg/agent-on-real-data.md:145-152`,
  `environments/real_panel.py`).
- Prices are Yahoo adjusted closes.
- **This is an assumption.** It is not a measured cost for any period.

## f. Custody

1. **One fetch, on the holdout host, by the author** (`i-0886a189b85d4d051`).
   - **The source is that of the old fetch:** Yahoo's chart endpoint
     `query1.finance.yahoo.com/v8/finance/chart`, by `curl`, with interval 1d, events div and
     split, and adjusted close (`data/fetch_etf.py:76-82`). **Not yfinance.**
   - A new script, `data/fetch_etf_recent.py`, adapted from `fetch_etf.py`, is written after
     this goes live and refuses until it is live.
   - **The host needs:** `curl`, already there, and in `.venv-grading` (uv, never pip)
     exchange_calendars 4.13.2 and tzdata 2026.4, as pinned in `data/etf_manifest.json`.
2. **Pinning:**
   - the SHA-256 of each raw response, as received, recorded at the fetch;
   - the fetch's UTC time and the last session it holds.
3. **The cut, on the host:**
   - the in-sample file runs to 2024-12-31;
   - its record gives the SHA-256, row counts, entry and death dates, and the volume medians
     of item b2. These are counts and medians of volume, not returns (confirmed by the
     author).
   - **Only that file and its record reach the laptop.**
   - **Rows from 2025-01-01 stay on the host,** with the raw responses. Grading is on the
     host.
4. **The adjusted-price caveat:** a back-adjusted close is rewritten at each later dividend
   and split. So this fetch's 2005–2022 prices differ from the 2026-09-22 fetch's, and a later
   fetch can differ again.
   - Daily returns are nearly unchanged under a proportional back-adjustment.
   - **The pinned file is the object of record,** not "Yahoo's series".
   - The new and the old in-sample files are not compared value by value, because that
     comparison would be a look.

## g. The graded quantity (as fixed for the French long history)

- **Realised:** the UNWEIGHTED net Sharpe over the holdout, with its stationary-bootstrap 90%
  interval.
- **Held iff realised ≥ the test's in-sample WEIGHTED L90.** Refused tests are graded too.
- One spanning panel, the no-restart checks and continuation are as in
  `prereg/french-long-b1-grading.md`, section 3–4. A grading registration is written after
  the in-sample read and may add checks. It may not change this quantity or this rule.
- **Both branches,** with wording as in `prereg/french-long-history.md` section i:
  - certified and held;
  - certified and not held (realised < bound);
  - refused, and graded either way.

  The d = 0 stream carries NOT IMPLEMENTABLE in every branch.

**The first grading: at the fetch, labelled "weak: 1.76 years".**

**What 444 rows can tell:** the SE of the realised Sharpe is **0.753** at Sharpe 0 (Lo's iid,
ppy 252). P(held) is computed for an object certified exactly at the bar, under the iid
normal approximation, with L90 = S − g:

| test, level | choice A: P(held), true = bar / true = 0 | choice B: P(held), true = bar / true = 0 |
|---|---|---|
| stream d = 1, 96% | 0.66 / 0.42 | 0.70 / 0.40 |
| stream d = 1, 90% | 0.66 / 0.46 | 0.70 / 0.46 |
| stream d = 0, 96%, NOT IMPLEMENTABLE | 0.66 / 0.36 | 0.70 / 0.33 |
| stream d = 0, 90%, NOT IMPLEMENTABLE | 0.66 / 0.40 | 0.70 / 0.37 |
| class, 96% | 0.91 / 0.39 | 0.94 / 0.37 |
| class, 90% | 0.91 / 0.42 | 0.94 / 0.41 |

- **"Held" and "did not hold" are weak evidence either way.** For a certified stream, a true
  Sharpe at the bar gives about 2 in 3, and a true Sharpe of 0 gives about 2 in 5.
- **Direction of error:** objects certified above the bar have higher bounds, so P(held) at a
  true 0 is lower for them. Selection makes in-sample values optimistic (type-M).

**The second grading: fixed now for the first NYSE session of 2028, 2028-01-03.**
- **Holdout rows:** from a **new fetch** made then, covering 2025-01-01 to the last complete
  session before that fetch. Through 2027-12-31 that is 752 rows, about 2.98 years, with an SE
  of about 0.58 at Sharpe 0.
- **This registration fixes only:**
  - that the second grading happens;
  - its date;
  - that **the graded quantity and the rule are unchanged:** unweighted holdout net Sharpe
    against the same in-sample weighted L90, held iff realised ≥ L90, refused tests graded.
- **Everything else is written then,** in its own grading registration, before the new fetch.
  The objects, the in-sample read and its L90s are those of this registration's single
  in-sample read. There is no re-read and no refit of the in-sample.
- **How the two fetches are joined, without a value-by-value comparison:**
  - The in-sample stays this fetch's pinned file, to 2024-12-31.
  - The holdout enters as **daily returns** computed within the new fetch alone. The new fetch
    also holds the 2024-12-31 bar, so the return dated 2025-01-02 comes from the new fetch's
    own closes.
  - Prices past 2024-12-31 are rebuilt by chaining those returns onto this fetch's 2024-12-31
    adjusted close.
  - A proportional back-adjustment between the fetches leaves the returns unchanged, so the
    join needs no comparison of the two fetches' prices.
  - **Open for the later registration:** volume, which is split-adjusted and so rescaled by any
    split after this fetch, feeds Sancho's V block. Whether to rescale the new fetch's
    volumes by the split events it records, and the death rule's use of the two fetches, are
    fixed then.

## h. Design numbers by simulation (outcome-free)

**The source:** `experiments/etf_recent_design_w2.py`, committed before its run at `bf90274`;
output `runs/etf_recent_design_w2/2026-10-11` at `717e1a9`; laptop, 111 s.
- **The dependence comes only from the already-read ETF recency pool:** 3,019 rows of
  2006–2017, gross member streams demeaned, SHA-256s checked against its manifest.
- Rows are resampled to each length.
- **Replicates:** B 2,000. **Seeds:** 720000–720999 (`seed_block_check`: NO COLLISION).
- Streams use 5 panels and the class 3.
- **Power:** net Sharpe at 80% power by Lo's iid formula over the weighted effective years.
- No realised mean, Sharpe or p-value is computed.

| test, level (alpha) | choice A: W2 bar → net 80% | choice B: W2 bar → net 80% |
|---|---|---|
| stream d = 1, 96% (0.03) | 0.462 → **0.709** | 0.574 → **0.860** |
| stream d = 1, 90% (0.06) | 0.380 → 0.627 | 0.465 → 0.751 |
| stream d = 0 NOT IMPLEMENTABLE, 96% (0.01) | 0.577 → 0.825 | 0.718 → 1.005 |
| stream d = 0 NOT IMPLEMENTABLE, 90% (0.02) | 0.506 → 0.754 | 0.642 → 0.929 |
| class, 96% (0.01) | 1.205 → **1.444** | 1.412 → **1.699** |
| class, 90% (0.02) | 1.153 → 1.392 | 1.342 → 1.629 |

**Lengths:**
- Choice A: the stream has 4,015 rows (weighted effective 11.6 years) and the class 4,778
  (12.5 years).
- Choice B: 2,516 rows each (8.6 years).
- The L90 gap g:

  | | stream | class |
  |---|---|---|
  | choice A | 0.312 | 0.998 |
  | choice B | 0.386 | 1.169 |

**Choice B costs about 0.15 of net Sharpe on the d = 1 stream and about 0.25 on the class.** In
return, no scored row lies in the formation window.

**Limit:** the pool's dependence is 2006–2017 only. The 2018–2024 rows of the real panel may
differ, for example in 2020's volatility.

## i. Seeds

- **The read:** block 721000–721099.
  - 721000: the d = 1 stream;
  - 721001: the d = 0 stream;
  - 721002: the class;
  - 721003: the performance line.
- **The grading:** 721010–721019.
- **The smoke:** 721100–721199.
- **Checked 2026-10-11:** `seed_block_check --ranges 721000-721099,721100-721199` gives NO
  COLLISION. A scan of tracked files found only `range(720000, 721000)`'s exclusive end.

## j. Cost and platform

- **Sancho:** four fits (the bit-for-bit repeat at d = 1 and d = 0) on about 4,778 rows × 40
  ETFs.
  - From the ML v2 design (base view, about 73 s of fits per 4,276-row ETF panel) and B1's box
    times scaled by rows and assets: **about 2–5 minutes per fit.**
- **The class:** the table is 82,240 × 4,778 × 8 bytes = **about 3.1 GB**. The old 4,276-row
  table was 2.81 GB.
  - The W2 null and the unweighted null take minutes (about 0.6 minutes per W2 panel on the
    pool).
- **Where: the compute box** (the author), Linux x86_64, about 0.5 box-hours.
  - It is the grading host's platform, so the reproduction check at grading is box against
    host, as B1.
  - The laptop could run it, but the grading would then need cross-platform tolerances (the
    French Option A).
  - **Stop and ask at 1 box-hour** (the author, 2026-10-11).
- **The host:** the fetch (minutes), the cut, then the grading later.

## k. Limits

- **Item 3 of section b (ticker, merger or structure changes) is NOT verified** from any
  committed record, and no claim is made about it.
- The list of 40 was named in 2026 from ETFs that survived (section a, item 4).
- The design numbers' dependence comes from 2006–2017 only (section h).
- The costs are an assumption (section e).
- The first grading is weak (section g).

## The author's answers (2026-10-11)

1. The liquidity threshold, 500,000 median share volume over 2005–2014: **yes.**
2. No missing session in 2005–2014: **yes.**
3. Item 3: stated as **NOT verified** from any committed record, not claimed, and listed under
   the limits (section k).
4. The death rule: **10 sessions.** The 2026-09-22 host fetch may supply a last bar, used only
   to close the position.
5. The minimum panel of 30: **yes.**
6. **Choice A.**
7. The 2026-only realised value: **yes,** descriptive.
8. The cut record carries the 2005–2014 volume medians: **yes.**
9. **The box,** with a cap of 1 box-hour.
10. **No new look.** The host cut decides. With fewer than 30 ETFs, nothing runs and the author
    is asked.
11. **Go ahead.**
    - The grading at the fetch is labelled "weak: 1.76 years".
    - A second grading is fixed for 2028-01-03, from a new fetch, with the quantity and rule
      unchanged (section g).

## Amendment 1, 2026-10-11 (America/Chicago): SPY as the declared market, and the liquidity median

Made before HOST-1. Nothing has been fetched and nothing has run on the host or the box.

**(a) SPY is the declared market series.**
- SPY is the market for X, the groups and the features (`declared_market`; no fallback in
  the code).
- **If SPY fails inclusion (section b) or dies, nothing runs and the author is asked.** There is
  no fallback series.
- The runner refuses if SPY is not included (`experiments/etf_recent_read.py`, `d141b5d`).
- The cut refuses any 2015–2024 gap, so SPY cannot die in-sample without a refusal. A death in
  the holdout is handled under the grading registration, by this rule: nothing is graded, and
  the author is asked.

**(b) The liquidity median** (section b, item 2) is the **true median** of daily share volume
over the sessions of 2005-01-03 to 2014-12-31 that have a non-null volume.
- Null volumes are left out of the median. Their count is recorded per ticker
  (`volume_nulls_2005_2014` in the cut record).
- A session with a bar but a null volume is not a missing session for item 1.
- **This differs from `data/fetch_etf.py`,** which took the upper-middle element of the sorted
  volumes.
  - With an odd count, the two are equal.
  - With an even count, the true median is the mean of the two middle values, and the old one is
    the larger of them.
  - **So the verdicts differ only when the threshold lies between the true median and the upper
    middle value.** For example, middle values of 497,000 and 501,000 give a true median of
    499,000, which fails, where the old rule gives 501,000, which passes.
  - That is a narrow band around the threshold, not only the value 500,000 exactly. The author's
    brief said "only at exactly 500,000"; this states the condition exactly.
  - The old 2005–2022 medians of these funds are all at least 815,700. That does not bound the
    2005–2014 medians.

Nothing else changes.

## Amendment 2 (2026-10-11, America/Chicago): rows from 2010 only; every
## test scored on 2015-2024

Made before any in-sample value of this panel has been read by the runner.
The cut (ad233e7) is unchanged.

1. Rows used. No row dated before 2010-01-04 enters any feature, market
   series, warm-up, training set, test or bootstrap. The cut files still hold
   2005-2009; the runner drops those rows by date before any computation and
   records how many it dropped.
2. Section c is replaced. The 253-row warm-up starts at 2010-01-04. Sancho's
   walk-forward starts at its usual first scored feature row, counted from
   the first feature row (about early 2014); its rows before 2015-01-02 are
   computed and not scored. The scored window for all three tests is earned
   dates 2015-01-02 to 2024-12-31. Choice A is withdrawn. This is choice B
   with the training start moved from 2005 to 2010.
3. The class tier runs on the scored window only.
4. Unchanged: the universe and its formation (section b), applied at the cut
   before this amendment; the three tests and the split; the W2 certificate
   at h = 1,260, with the 90% level always labelled; costs; custody; the
   holdout, 2025-01-01 to the last fetched session (2026-10-09); the graded
   quantity and rule; the second grading on 2028-01-03; amendment 1.
5. Disclosed: the universe was formed on 2005-2014 volume and completeness.
   That is the only use of pre-2010 rows, and it was made at the cut.
6. Design numbers are recomputed, outcome-free, under these windows and
   appended before the run. The earlier table is kept beside, labelled
   superseded.
7. When the holdout is graded. Not before the sessions of
   prereg/agent-cell-etf-recent.md are complete and committed. One host
   session then grades this panel's three objects and every agent submission.
   Until then no 2025+ value is computed for any purpose.
8. Reason and cost. The author's decision of 2026-10-11: no work from here
   on uses data before 2010, and strategies are developed on 2015-2024. The
   scored window is shorter and Sancho has less training data, so power is
   lower. That cost is accepted.
