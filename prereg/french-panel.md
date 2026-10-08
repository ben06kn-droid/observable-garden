# French 49-industry panel: DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE.** It is committed so the author can read the full text. It is
not a registration, and nothing in it binds until a separate, dated commit makes it live.
- The author's decisions of 2026-10-07 are folded in.
- No agent session has run and no box has been used.
- No outcome on this data has been read: no realised Sharpe, p-value or certification.
- The windows were fixed before any price was read, in `prereg/new-panels-audit-2026-10-06.md`.
- What has been done so far:
  - one fetch (section a);
  - the in-sample CSV written;
  - outcome-free design quantities, run twice (section i). The second run supersedes the
    first.

## a. Data

- **Source:** Kenneth R. French Data Library, *49 Industry Portfolios, daily*, the
  value-weighted block ("Average Value Weighted Returns -- Daily"). Values are percent
  returns, divided by 100 on load.
  - `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/49_Industry_Portfolios_daily_CSV.zip`
- **The one fetch:**
  - **When:** 2026-10-08 04:04:13 UTC (2026-10-07 America/Chicago).
  - **The zip:** 4,173,817 bytes, SHA-256
    `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de`. It has one member,
    `49_Industry_Portfolios_Daily.csv`.
  - **No `Last-Modified` header** was returned by the server, so none is recorded.
  - **The hash is the definition of the data.** The library revises and extends the file,
    so no later re-fetch replaces it.
  - **Code:** `data/fetch_french.py`, committed before the fetch at `85e428f`. The
    manifest is `data/french_manifest.json`.
- **The in-sample CSV:** `data/raw/french_insample/french49_vw_daily.csv` (gitignored),
  2,771 rows, SHA-256 `1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e`.
- **Missing-value codes:** the library marks a missing value as −99.99 or −999.
  - The fetch counts both, per industry, in every row it writes, and **refuses to write**
    the CSV if any is present. The loader refuses again: any NaN, or any return at or below
    −99.99%.
  - **Result: none,** in all 2,771 rows and all 49 industries. No gap is filled,
    interpolated or zeroed.
- **Holdout rows:** 1,674 lines dated on or after 2020-01-01 were **counted from their
  date field only**. Their values were never parsed, printed or stored.
- **Unused:** 21,872 rows before 2008-12-29.

## b. Windows

- **Scored in-sample: earned-return dates 2010-01-04 to 2019-12-31** (2,516 days). Feature
  row t earns the return dated t + 2, so:
  - the first feature row is 2009-12-30;
  - the last feature row is 2019-12-27.
- **Warm-up: 253 rows, 2008-12-29 to 2009-12-29.** This is the ETF builder's 252 + 1. They
  feed features only, and no return in them is scored.
  - **Three of them are from December 2008** (12-29, 12-30, 12-31), because 2009 has 252
    trading days.
  - **The author's explicit YES, 2026-10-07:** 253 warm-up rows, 3 of them from December
    2008, for features only.
  - This departs from the audit's "rows before 2010-01-01 are simply unused". The
    departure is accepted and recorded here.
- **Holdout: 2020-01-01 onward.** Its end is the last row of the 2026-10-08 fetch. **There
  is no fallback window.**
- **ridge_stack scores later.** It needs its first three 252-row years for training, so it
  scores feature rows 756 to 2,515: earned dates from 2013-01-04 to 2019-12-31, 1,760 rows
  (section i). The class tier scores all 2,516 rows.

## c. Market series

- **The declared market series is the equal-weighted average of the 49 industry returns,**
  each day. `beta252` and `idvol63` regress on it.
- `_etf_base_signals` now takes a declared market series, with no first-asset fallback
  (`9e7871d`). The ETF path declares SPY and rebuilds the pinned X bit-identically.

## d. Features

- **The registered 40:** the 20 base signals of `prereg/etf-features.md`, each as a
  cross-sectional z-score and a rank.
- **This panel's rank definition: exact ties take their AVERAGE rank**
  (`environments.french_panel.rank_average`), mapped to [−1, 1] as `_rank` maps ranks.
  - This is part of this panel's feature definition.
  - The data is quantised to 0.01%, so exact ties are common. The ETF builder's `_rank`
    breaks a tie by sort order, which is platform-dependent. An average rank does not
    depend on order.
  - **The ETF path is unchanged.** Its pin test still passes: the rebuilt ETF X hashes to
    `4b461070…b7ba`.
- **Same timing as the ETF panel:** signal at the close of t, held from the close of t+1 to
  the close of t+2.
- **The price path** for `ma50`, `ma200`, `ma_spread` and `drawdown` is the compounded
  return index, log p_t = Σ log(1 + r) through t. The momentum signals sum simple returns,
  as on the ETF panel.
- **Code:** `environments/french_panel.py`.
- **X is pinned:** `data/pinned/french49_X.npy` (gitignored), shape (2516, 49, 40),
  float64.
  - **File SHA-256 `07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc`.**
  - **Built on:** arm64 (Apple M3), Python 3.14.2, numpy 2.5.3, scipy 1.18.1. Written
    once, at `4a03f82`.
  - `build_french_panel` serves the pinned X. It refuses on a hash or shape mismatch, and
    there is no rebuild fallback.
  - The cache manifest's `panel_x_sha256` is the hash of the raw array bytes
    (`4543987c…a754`). It differs from the file hash because the file has an `.npy`
    header.
- **Will a rebuild on Linux x86 match the hash? Not expected.** Average ranks remove
  exact-tie ordering. They do not remove last-bit differences in the floating-point
  arithmetic behind the features:
  - summation order in the rolling means and standard deviations;
  - the BLAS dot products in `beta252` and `idvol63`.

  Those last-bit differences change z-scores, and can flip ranks between values that are
  nearly tied. It was not tested, because no box was used. **So all French pricing runs
  on the laptop** (arm64), on the pinned X.
- **One consequence, for the author's decision:** on the laptop, ridge_stack runs with the
  macOS LightGBM pin, not the confirmation's Linux pin.
  - The macOS pin is LightGBM 4.7.0, wheel
    `lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl`, SHA-256
    `129535462686f274df179133643118c5c5c5667167fe6c3a28d955f0b3c8e868`.
  - The code and settings are those of `fce5627`. Only the platform's LightGBM build
    differs.

## e. Costs

- **5 bps one-way per unit of turnover, and 50 bps/yr borrow on shorts,** as on the ETF
  panel. **This is an assumption.**
- **Limit:** industry portfolios are not directly tradable instruments. The costs stand in
  for trading a replicating basket and are not measured. No claim about implementable
  returns rests on them.

## f. Sealing

- **The loader** (`data/french_loader.py`):
  - refuses any row dated on or after 2020-01-01 in any file it opens;
  - refuses sealed (`.enc`, `.gpg`, `.asc`) and quarantined (`~/Desktop`) paths;
  - reads the holdout only behind a grading flag, which is not built yet. Building it is
    part of the grading registration.
- **Split and hash:**
  - The in-sample CSV is written and hashed (section a).
  - The holdout CSV is cut from the quarantined zip at grading, on the holdout host, and
    hashed there. The zip's hash is checked first.
- **The zip, now:** it sits unopened at `~/Desktop/og-quarantine/french/`. That is
  outside the repository and under a path the loaders refuse.
- **Before any agent session runs on this panel,** the zip is moved to the holdout host
  and deleted from the laptop. Its SHA-256 is checked on arrival.
- **The data is public, so the seal is procedural.** It stops this pipeline and its
  agents from reading the holdout rows. It does not stop anyone fetching the file.
- **Limit, recall:** 2020 onward lies inside the agent model's training data. For agents,
  industry names and calendar dates are masked: assets are `I00`–`I48`, and rows are
  indexed, not dated. Whether recall leaks through anyway is a limit stated here, not
  measured.

## g. What may be tried, declared up front

Exactly two things, each declared before any outcome is read:
1. **The class tier:** `SubsetClass`, max_size 3, signed, over the 40 features (82,240
   members). The class maximum is priced against the class null over the 2,516 scored
   rows.
2. **ridge_stack as one declared stream:** pinned as in the confirmation (`77f3ee1`):
   - code at `fce5627`, with the four `learn/` blob hashes;
   - the start-up refusals.

   It runs on the laptop, so with the macOS LightGBM pin (section d). It is priced through
   the supplied-streams tier over its scored window.

**The 5% is split by weight, fixed now from null-only quantities:**
- **The ridge_stack stream certifies iff its p < 0.04.**
- **The class tier certifies iff its p < 0.01.**
- The family-wise error over the two is at most 5% (Bonferroni).

**Why these weights:** on this window the class tier's 80%-power Sharpe is about 1.7, even
at an even split (1.721 at its 96% point). An edge the class tier could certify would
have to be very large. So most of the 5% goes to the stream, whose bar is lower.

**The weights were set before any outcome was read.** They were set from the null maxima
and bars in section i alone. No observed score, realised mean, Sharpe or p-value on this
panel had been computed.

**Joint pricing: the alternative not taken.**
- **What it is:** price the ridge_stack stream together with the class as one menu,
  82,241 streams, at 5%. The null is the maximum over all of them under joint resampling.
- **Its cost: a common window is needed.** Either:
  - the class is restricted to ridge_stack's window (1,760 rows, losing 3 years), or
  - ridge_stack's stream is zero over its training years (2,516 rows, diluting its
    Sharpe).

  And the stream would face the class's maximum-over-82,240 bar rather than its own.

## h. Dataset ledger entry (before any run)

No ledger file exists yet. **`prereg/DATASET_LEDGER.md` is created with this entry in
the same commit that makes this registration live.** It is not created before then.

| field | value |
|---|---|
| dataset | French 49 industries, daily, value-weighted |
| fetched | 2026-10-08 04:04:13 UTC, laptop, once |
| zip SHA-256 | `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de` (4,173,817 bytes) |
| in-sample CSV SHA-256 | `1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e` (2,771 rows, 2008-12-29 – 2019-12-31) |
| scored in-sample | earned dates 2010-01-04 – 2019-12-31 (2,516) |
| holdout | 2020-01-01 – last row of the fetch; 1,674 lines, counted only |
| zip location | `~/Desktop/og-quarantine/french/`; moves to the holdout host before any agent session |
| pinned X | `data/pinned/french49_X.npy`, SHA-256 `07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc` (arm64) |
| pricing platform | laptop (arm64) only |
| reads so far | outcome-free design quantities only (section i) |
| outcome reads | none |

## i. Outcome-free design quantities

**Source:** `experiments/french_design_quantities.py`.
- **Not computed, in either run:** no observed score, realised mean, Sharpe or p-value.
- **Laptop numbers:** Darwin arm64, the macOS LightGBM pin.

**Power:** the certified Sharpe solves SR − 0.8416 · sqrt((1 + SR²/2) / T_years) = bar.
This is a normal approximation with iid returns. It ignores selection: for the class it is
the Sharpe of a single member that is also the class's best.

**Current run.** The script was committed before the run at `2d277ca`; the output is in
`runs/french_design/2026-10-07-weighted` (`e099d46`).
- **Panel:** the pinned X, with average ranks.
- **Replicates:** B = 5,000 for the 96% and 99% points.
- **Seeds:** 692003 (class null), 692004 (ridge null), 692005 (leak test).

| tier | window | block length | bar 96% | certified at 80% power | bar 99% | certified at 80% power | seconds per pricing call |
|---|---|---|---|---|---|---|---|
| class (82,240 members, fast kernel) | 2,516 rows, 9.98 years | 2 | 1.302 | 1.721 | 1.412 | 1.850 | 35.5 at B 5,000 (cache built once in 98 s) |
| ridge_stack, one stream | rows 756–2515, 1,760 rows, 6.98 years (earned dates 2013-01-04 – 2019-12-31) | 1 | 0.666 | 1.065 | 0.877 | 1.311 | 19.4 for the predictor, 0.1 for the tier |

- **The fast kernel accepts this panel.** Its streams match the registered `streams_for`
  on 256 members to a relative 8.5e-16.
- **ridge_stack's leak test passes on this panel,** at rows 1000, 1700 and 2300, on
  positions only.

**Superseded first run.** It was committed at `fd82d57`, with output at `522151f`.
- It ran before average ranks and the pin, at B = 1,000, with seeds 692000–692002.
- **Class:** 1.279 / 1.361 at 95% / 97.5%.
- **ridge_stack:** 0.611 / 0.716 at 95% / 97.5%.
- It is kept for the record and enters nothing.

## j. Registered expectations, stated in advance

**The ceiling at the chosen weights:**

| tier | certifies iff | bar | true net Sharpe certified with 80% power |
|---|---|---|---|
| ridge_stack, one stream | p < 0.04 | 0.666 (96% point of its demeaned-stream null) | **1.065** |
| class tier | p < 0.01 | 1.412 (99% point of the class null maximum) | **1.850** |

- **An edge whose true net Sharpe is below 1.065 will usually be refused** by the stream
  tier. Below 1.850, it will usually be refused by the class tier. **This is the detection
  floor of this window, not a defect.** Ten years of daily data cannot certify a smaller
  edge at these error rates.
- **ridge_stack yields exactly one stream on this panel.** So the ML tier contributes at
  most one certificate, whatever the number of agent sessions.

**The holdout, 2020-01-01 onward, both branches:**
- **If anything certifies:** it and every refusal are graded together on 2020 onward,
  against their lower bounds.
- **If nothing certifies:** the refusals are still graded, against their lower bounds.
  The registration then says that this panel could not test whether a pass holds.

## What does not fit the ETF builder's assumptions

- **No price series.** The file gives returns. The price path is the compounded return
  index (section d).
  - Every row has a return, including the first, which the ETF build left NaN.
  - The warm-up is the same 253 rows either way.
- **Resolution: returns are quantised to 0.01% (1 bp).**
  - Each industry has 4–19 days of exactly 0.00 in the 2,771 rows.
  - Three industries (Smoke, LabEq, Trans) have one run of two zero days.
  - No row is all zeros, and no row has 10 or more zeros.
  - So cross-sectional ties, in `ret1` especially, are far more common than on the ETF
    panel. Section d therefore uses average ranks and pins X.
- **Missing days:** none. The 2,771 dates equal SPY's trading days over 2008-12-29 –
  2019-12-31 exactly.
  - The only calendar gap longer than 4 days is 2012-10-26 → 2012-10-31, the Hurricane
    Sandy closure, which SPY shares.
- **Missing-value codes:** none (section a).
- **Industries with gaps:** none. All 49 have a value on every in-sample day.
- **Not a tradable instrument** (section e).
