# Binance USDT-margined perpetuals, 4h, formation 2021-01: a registration DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE (rewritten 2026-10-09, America/Chicago; revised the same day with
the author's decisions on timing (d = 0), the class tier, the split and the pre-live
records).** It is committed for the author's reading. Nothing in it binds until a separate, dated commit makes it live.
- No agent session has run on this panel, and no box has been used for it.
- **No outcome has been read:** no realised mean, Sharpe, p-value or certification.
- **No holdout row (2025-04-01 onward) has been downloaded or parsed.**
- Every number below is an outcome-free design quantity.
- The windows follow `prereg/new-panels-audit-2026-10-06.md`. That audit fixed the
  holdout at 2025-04-01 before any price was read.
- The earlier draft text (4h formation 2021-10, version 1's ridge_stack, flat 10 bps) is
  kept below as an appendix. **Where it differs from this body, this body governs.**

## a. Data

- **Source:** data.binance.vision, `futures/um` (USDT-margined perpetuals): monthly
  `klines/<SYM>/4h/` and `fundingRate/<SYM>/`, and daily `klines/<SYM>/4h/` for the gap
  fill. Every zip is verified against its published `.CHECKSUM` (SHA-256) before use. A
  mismatch refuses.
- **Fetches, each with its code committed first and a manifest of every file's hash:**

  | what | code | when (UTC) | manifest |
  |---|---|---|---|
  | formation-month 1d klines (the universe rule) and the daily funding files | `data/fetch_binance_daily.py` | 2026-10-08 | `data/binance_daily_manifest.json` |
  | monthly 4h klines, 2021-02 to 2025-03, for the 50 contracts | `data/fetch_binance_4h_formations.py` (`65661c4`) | 2026-10-09 | `data/binance_4h_formations_manifest.json` (`6f08d30`) |
  | daily 4h klines filling two archive holes (decision B2) | `data/fetch_binance_fill_formation.py` (`816073f`) | 2026-10-09 | `data/binance_4h_2021-01_fill_manifest.json` (`2ab1df1`) |

  - **The 4h fetch:** 2,465 monthly zips verified. 2,069 were reused from the quarantine,
    each only on a match with the published CHECKSUM; 396 were downloaded.
  - **Funding** is copied from the daily formation's funding CSVs. Those come from the
    same verified funding zips; funding does not depend on the bar size.
- **The taker-buy columns** were dropped in error by the original parser. They were
  restored from the quarantined zips, each at its recorded hash, with every rebuilt row
  checked equal to the derived CSV (correction of 2026-10-09 in the appendix; `704ea5b`).
- **Where the files are:**
  - the raw zips: `~/Desktop/og-quarantine/binance/`, refused by every loader;
  - the derived CSVs: `data/raw/binance_4h_2021-01/` (gitignored).
- **The definition of the data is the pinned arrays** (section h). The derived CSVs are
  hashed as well:
  - every one of the 190 files in `data/raw/binance_4h_2021-01/` (50 contracts × kline,
    taker and funding, and 20 × fill and fill taker), with its SHA-256 and row count, in
    `data/binance_4h_2021-01_derived_manifest.json` (`ebf6b1a`; code
    `data/fetch_binance_holdout_checksums.py`);
  - **combined SHA-256 `5ae9a12fa37c73b34bbf862029665f2ba1ce0fbac2c0acfbd348e6f60ba31cb8`**:
    the SHA-256 of the lines "<file name> <file SHA-256>", sorted by name;
  - that entry goes into the dataset ledger (section q).

## b. Windows

- **Bars:** 4h, by open time (UTC), 6 a day, so 2,190 a year.
- **The grid:** 2021-02-01 00:00 to 2025-03-31 20:00, 9,120 bars. It starts the month
  after formation.
- **Warm-up:** the first 253 bars, 2021-02-01 00:00 to 2021-03-15 00:00. They feed features
  and blocks only.
- **Feature rows: 8,866,** the first at 2021-03-15 04:00 and the last at 2025-03-31 16:00.
  - **At d = 0 (section i), feature row t earns bar t + 1.** The earned bars run from
    2021-03-15 08:00 to 2025-03-31 20:00: 4.05 years.
  - **The class tier scores all 8,866 rows.**
- **Version 2's stream scores from feature row 762** (first scored row 756 + embargo
  h 5 + 1 + d 0). Its earned bars run from 2021-07-20 08:00 to 2025-03-31 20:00: **8,104
  rows, 3.70 years**.
- The descriptive d = 1 stream (section k) has 8,865 feature rows and scores 8,102, from
  2021-07-20 16:00.
- **Holdout: 2025-04-01 00:00 to 2026-09-30 20:00** (decision B4: the last complete month
  in the monthly archive). That is 18 months, 3,288 bars, 1.50 years.

## c. Universe, point in time

**The rule** (`data/fetch_binance.py`; applied to formation month January 2021 by
`data/fetch_binance_daily.py`):
1. **Candidates:** every USDT-quoted perpetual in the `futures/um` klines listing, excluding
   stablecoin bases and composite index contracts. 85 had a January 2021 1d file.
2. **Qualify:** a 1d kline with trades on **every one of the 31 days** of January 2021.
   **79 qualify.**
3. **Rank** by January 2021 summed quote volume. Take the **top 50, held fixed.**
   - Number 50, ZENUSDT, traded 1.002 bn USDT; number 51, KAVAUSDT, 0.841 bn.
4. **No contract enters later.** A contract stays until its death (section d).

**Deaths in-sample: 4 of 50,** together 0.59% of the 50's formation volume:

| contract | dead from (bar open, UTC) |
|---|---|
| YFIIUSDT | 2022-04-12 12:00 |
| WAVESUSDT | 2024-06-11 12:00 |
| FTMUSDT | 2025-01-06 12:00 |
| OMGUSDT | 2025-01-31 12:00 |

- **A death is detected from the rows** (decision B3): dead from the bar after the last bar
  with trades, if it never trades again in-sample or only after a silence of 180 or more
  bars. There is no re-entry.

**Why this variant (author, 2026-10-09).** It was chosen from outcome-free design
quantities alone (`5941c66`):
- the universe rule is intact at 50: 79 qualify;
- it scores 3.70 years;
- its floor is within a few hundredths of the 2020-09 variant's: gross needed 1.996
  against 1.963.

No return, Sharpe or p-value on any variant had been computed. The alternatives not taken
are formation 2020-09 (44 qualify, so the rule's top 50 is not reached) and 2021-10 (2.90
scored years).

## d. Dead contracts

- **Decision B1 (d3):** there is no mask. From its death bar a contract's features are all
  0, its earned returns are 0, its funding is 0, and its trades cost 0.
- **Adopted 2026-10-09 (proposal (b)): the closure rule for version 2's stream.**
  - Applied after the model; learn2 is untouched.
  - The position in a contract is zero on every row whose earned bar is dead. At d = 0 the
    exit then trades at the close of the last live bar, the last price at which the
    contract traded, which the death bar carries.
  - That trade is costed by the cost rule (section f).
  - **The freed gross is NOT redeployed.**
  - **Effect on the design numbers at d = 0:** the dead-contract gross share falls from
    0.015 to 0; turnover per unit gross rises from 0.0943 to 0.0946; cost per year, drag
    and the bars are unchanged to the digits shown (section l).
- **The class tier (accepted by the author, 2026-10-09):** its members also place small
  weights on dead contracts, which earn and cost nothing. The fast kernel takes no mask,
  and the closure is not applied to the class.

**Death in the holdout: the general rule (author, 2026-10-09).**
- **A contract is dead from the EARLIER of:**
  - (i) the registered death rule: dead from the bar after its last bar with trades, or
    from the start of a silence of 30 days (180 bars) or more; and
  - (ii) the first bar for which the archive has no kline row.
- **Its position is closed at the last available bar's price.** The exit is costed, and the
  position stays zero after.
- **Funding listed after death is ignored.**
- **Where it is applied:** on the holdout host at grading, from the rows there. (ii) is
  decided from the archive's listing.
- **The in-sample read is unaffected.** No in-sample contract is missing a kline row for
  any bar it is live; (ii) adds nothing before 2025-04-01.

**Listing facts found on 2026-10-09.** These come from file listings and checksum files
only; **no holdout row was read.** The 140 absent holdout contract-month files
(`data/binance_4h_2021-01_holdout_checksums.json`) belong to nine contracts. For each,
the absence runs without a break to 2026-09 for that file type.

| contract | in-sample death | absent (holdout months) | kline file sizes in the listing |
|---|---|---|---|
| YFIIUSDT | 2022-04-12 | klines and funding, 2025-04 – 2026-09 | none listed |
| WAVESUSDT | 2024-06-11 | funding from 2025-07 | about 1.5 KB every month: the filler size |
| FTMUSDT | 2025-01-06 | funding from 2025-07 | the same |
| OMGUSDT | 2025-01-31 | funding from 2025-07 | the same |
| MKRUSDT | none | funding from 2025-10 | about 9 KB to 2025-08, 3.6 KB in 2025-09, then 1.5 KB |
| ALPHAUSDT | none | funding from 2025-10 | about 9 KB to 2025-08, 7.0 KB in 2025-09, then 1.5 KB |
| SXPUSDT | none | funding from 2026-01; klines from 2026-06 | about 8.6 KB to 2025-11, 2.8 KB in 2025-12, 1.5 KB to 2026-05, then none |
| LRCUSDT | none | funding from 2026-04 | about 8.8 KB to 2026-02, 7.1 KB in 2026-03, then 1.5 KB |
| **EOSUSDT** | none | **klines from 2025-06** | 8.7 KB in 2025-04, 6.1 KB in 2025-05, then **none**; **funding files continue (about 0.7 KB) through 2026-09** |

- **The filler pattern:** after a delisting, the archive keeps a kline file of about 1.5 KB
  each month (zero-trade rows at a constant price). The funding files stop a few months
  later. The three contracts that die in-sample follow it.
- **The pattern suggests delistings within the holdout for MKR, ALPHA, SXP and LRC.** Rule
  (i) decides each one at grading, from the rows.
- **EOSUSDT's kline files stop after 2025-05, while its funding files continue. Rule (ii)
  covers it:** it is dead from the first bar with no kline row, and its later funding is
  ignored.

## e. Returns and funding

- **Return:** r_t = close_t / close_{t−1} − 1 − F_t. F_t is the sum of the funding rates
  with open_t < calc_time ≤ open_t + 4h, under Binance's sign convention: longs pay a
  positive rate.
- **Gaps (decision B2):** 20 of the 50 contracts had no 4h rows for
  2022-02-26 00:00 to 02-28 20:00 and 2022-04-01 00:00 to 04-02 20:00, 30 bars each.
  - **All 600 bars were filled** from the archive's daily 4h files. Each hole's 12 overlap
    bars matched the monthly rows exactly (maximum relative difference 0). None was
    carried.
  - Any other bar with no row, or with zero trades, while a contract is live carries its
    close: return 0 apart from funding, still tradable and costed.

## f. Costs (adopted 2026-10-09)

**Cost per unit of turnover = 5 bps fee + max(half-spread estimate, 1 bp).**
`environments/binance_costs.py` (`02c7ba4`).
- **The fee, 5 bps, is an assumption.** Its source is Binance's futures fee FAQ
  (`binance.com/en/support/faq/360033544231`, last updated 2026-05-01): "a Regular User's
  taker fee is 0.05%". The FAQ labels this as a calculation with hypothetical rates, and
  the fee-rate table showed no rates without a login (appendix, section f). Every trade is
  costed as a taker trade.
- **The half-spread** for contract i in month m is half of the **EDGE** spread estimate
  (Ardia, Guidotti and Kroencke 2024, doi:10.1016/j.jfineco.2024.103916).
  - It uses contract i's 4h bars **opening in the 30 days before month m starts**, so every
    bar used has closed before the month begins. There is no look-ahead.
  - It is re-estimated monthly and applied to every trade executed in month m.
  - With fewer than 90 traded bars there is no estimate. The month then takes that month's
    cross-sectional median: 97 of 2,500 contract-months. 50 are February 2021, which has
    no prior bars and lies inside the warm-up. 47 are months whose 30-day window falls after a
    contract's death; dead contracts cost nothing in any case.
- **The floor:** 1 bp on the half-spread, so no trade costs less than 6 bps.
- **A trade is costed at its execution bar,** in that bar's month: at d = 0, the bar t at
  whose close it fills, iff bar t is live (section i).
- **Dead contracts cost nothing** after their exit.
- **No borrow:** shorts pay or receive funding, which is in the return.
- **The rates are pinned** (section h). The same rates price the class tier's members and
  the base columns behind the block length.

**The book-ticker check** (`experiments/binance_spread_check.py`, `02c7ba4`; output
`660bdf5`):
- **What was compared:** the quoted half-spread from Binance's book-ticker files, against
  the rule's monthly EDGE estimate.
  - Three contracts of different liquidity (BTCUSDT, VETUSDT, ZENUSDT); four in-sample
    days each, from 2023-06-14 to 2024-03-13.
  - The quoted half-spread is time-weighted over 0.3 to 28 million updates a day.
  - Only those twelve daily files were downloaded, each verified and quarantined.
- **The test, committed before any file was read:** EDGE is clearly biased iff, for at
  least two of the three contracts, the medians of the floored estimate and the floored
  quote differ by more than 1 bp with a ratio outside [0.5, 2].
- **Result:**

  | contract | quoted half-spread, bps (4 days) | EDGE half-spread, bps | floored medians, EDGE vs quoted |
  |---|---|---|---|
  | BTCUSDT | 0.007–0.020 | 0.18–1.09 | 1.00 vs 1.00 |
  | VETUSDT | 1.02–3.14 | 2.65–6.26 | 3.67 vs 2.37 (ratio 1.55) |
  | ZENUSDT | 0.78–1.00 | 0.52–4.57 | 2.87 vs 1.00 (ratio 2.87, fails) |

  - One contract fails, so **EDGE is not clearly biased by the registered test, and is
    used.** Spearman over the 12 contract-days is 0.68.
  - **Where it errs, it overstates the spread** (VET, ZEN): costs are biased up, so the
    drag below is conservative.
  - **Abdi–Ranaldo**, the named fallback, did worse: 0 on 7 of 12 days and 14–19 bps on
    VET. It is not used.
- **Limit:** the check covers 12 contract-days in 2023–2024. Book-ticker files do not
  exist for 2021–2022 or after 2024-04.

## g. Market series

The equal-weighted average of the **live** contracts' price returns, each bar
(decision B6).

## h. Features and blocks, pinned

- **P: the registered 40,** the 20 base signals as cross-sectional z-scores and average
  ranks. **Price-only** (decision B7). Lookbacks are in rows, so on 4h bars they are
  shorter horizons: for example `mom21` is 3.5 days and `mom252` 42 days (appendix,
  section h).
- **Version 2's blocks** (`learn2.blocks`), built on the full grid from data known at each
  bar's close, then cut to the feature rows exactly as P is:
  - **X** (10 columns): from price-only bar returns and the live-average market;
  - **V** (5 columns): logvol_ratio, taker_last, taker_mean21, count_ratio, amihud21;
  - **F** (3 columns): the funding paid in each bar (clarification of 2026-10-09);
  - **the neutrality groups:** from the trailing 252-row market-residual correlation.
- **Pinned** (`environments/binance_pins.py`), built once on the laptop (arm64, Python 3.14,
  numpy 2.5.3) and served only at these hashes, with no rebuild on a mismatch.
  **The registered stream and the class tier use the d = 0 pins** (`ef8f0a7`); the
  descriptive d = 1 stream (section k) uses the d = 1 pins (`086f6ad`).

  | file (`data/pinned/`, gitignored) | contents | SHA-256 |
  |---|---|---|
  | `binance_4h_2021-01_d0_X.npy` | P at d = 0, (8866, 50, 40) | `da66f540df2102eed75c9ca2580eb44ccc733835e9cbac0f2bb04a73cf12eafa` |
  | `binance_4h_2021-01_d0_v2.npz` | X, V, F, groups at d = 0 | `602325699910ebf3adc4326aaa8c150c993a1e1711a732f5a429a07d5f644164` |
  | `binance_4h_2021-01_d0_costs.npz` | cost rates at d = 0, (8866, 50); the monthly EDGE table | `9fe8813e06cdd7dc8dd3ac70b5b0d34bd4dd3e7ba0f5d59a2798ae5c482acecf` |
  | `binance_4h_2021-01_X.npy` | P at d = 1, (8865, 50, 40) | `e6ff168cc06dbe795b90d73edfeafad332f886417331f2e921404ad677e8e257` |
  | `binance_4h_2021-01_v2.npz` | X, V, F, groups at d = 1 | `47c688ee76ba8e9f5070a31e4ff155a0d702e6e7a72bc99aee5c4e224206e6c5` |
  | `binance_4h_2021-01_costs.npz` | cost rates at d = 1 | `74be4b19b9fad50cc878aae82d4b616b1ec93f12026aedf8aa51a45033399789` |

- **What the change of timing changed in the pins:**
  - **P and the v2 blocks:** a new file each, because d = 0 has one more feature row (the
    last bar's features now earn the window's last bar). Every shared row is bit-identical
    to the d = 1 pin: features and blocks use data up to each bar's close, not the earned
    return.
  - **The cost rates:** the monthly EDGE table is identical. The per-row rates differ on
    52 rows, where the execution bar moves across a month edge or a death.
  - **Not pinned, because they are built from the pins and the panel:** the earned
    returns, the market states learn2 computes from them, and the class tier's fast
    tables. The tables were rebuilt for d = 0, in 1,936 s on the laptop (section l).
  - The builder change (`0869120`) leaves d = 1 as it was: the three d = 1 pins rebuild
    bit-identically after it.

- **Platform: the laptop only** (Darwin arm64), as on French. A Linux rebuild is not
  expected to match the hashes bit for bit.
  - LightGBM is the macOS pin: 4.7.0, wheel SHA-256 `129535462686f274…e868`, dylib
    `bc392db6…ff18`.
  - **The learn2 blobs are the confirmation's** (`083c734`; `experiments/ml_v2_confirm_2026_10_09.py`,
    `PINNED_V2`), unchanged at HEAD.

## i. Timing (decided by the author, 2026-10-09: d = 0)

- **The signal is formed at the close of bar t, and the trade fills at that close.** In a
  continuous market that is the same instant as the next bar's open. **The position earns
  bar t+1,** from the close of t to the close of t+1. In learn2's terms d = 0, and the
  embargo is h + 1 + d = 6 rows, as coded.
- **The trade is costed iff bar t is live,** at the cost rule's rate for bar t's month.
- **The assumption, stated plainly:**
  - every trade fills at the bar's closing price;
  - the half-spread and the fee are the whole allowance for slippage;
  - **this is optimistic** by the seconds it takes to compute the signal and send the
    order after the close. The price can move in that time, and nothing here charges for
    it.
- **How much depends on immediacy is shown, not tested:** the same stream at d = 1, with a
  one-bar delay, is reported beside the d = 0 result (sections k and m).
- **The builder:** `environments.binance_panel.panel_from_arrays(..., lag=1)` (`0869120`).
  It sets `meta["delay"] = 0`, which learn2 reads. Tested: at lag 1 each row earns the
  next bar; a trade on a contract's death bar costs nothing, and the bar before it is
  costed.

## j. Sealing

- **No holdout month is ever downloaded to the laptop.** The loader refuses any row with
  open time or calc time on or after 2025-04-01, and any quarantined or sealed path.
- **At grading, the holdout months (2025-04 to 2026-09) are fetched directly on the
  holdout host** from data.binance.vision, each file verified against its published
  CHECKSUM there.
- **The holdout's identity is fixed now.** The published CHECKSUM text of every
  holdout-month 4h kline and funding file for the 50 contracts is recorded in
  `data/binance_4h_2021-01_holdout_checksums.json` (`ebf6b1a`; code
  `data/fetch_binance_holdout_checksums.py`, committed before its run).
  - **Only CHECKSUM files were fetched,** each a line of text with a hash. No holdout data
    zip was downloaded, and the code refuses any other URL.
  - **Recorded:** 1,660 files present. 140 contract-month files are absent from the
    listing.
  - **At grading,** each holdout file fetched on the holdout host must match its recorded
    hash, or the grading refuses.
- **The data is public, so the seal is procedural.** It stops this pipeline from reading
  the holdout. It does not stop anyone from fetching it.
- **Limit, recall:** 2025–2026 may lie inside the agent model's training data. No agent is
  involved in this registration. For agents later, contracts are `C00`–`C49` and rows are
  indexed.

## k. What may be tried, declared up front

Exactly two things may certify:
1. **Version 2's base view as one declared stream, at d = 0:**
   - all four blocks (P X V F); horizon 5; market neutrality; regime always;
   - memories M2 (rolling 756, expanding); rate grid G3 (0.3, 0.1, 0.03); L grid
     {1, 3, 10, 30};
   - the closure rule (section d) after the model;
   - priced through the supplied-streams tier over its 8,104 scored rows.
2. **The class tier:** `SubsetClass`, max_size 3, signed (82,240 members), fast kernel,
   over all 8,866 rows, at d = 0.

**And one thing is looked at but cannot certify:**
3. **The same stream at d = 1** (the one-bar delay), on the d = 1 pins, with everything
   else as in item 1.
   - Its observed net Sharpe and its 95% interval are reported beside the d = 0 result.
   - **No p-value, no certificate, no claim.** It is a second stream, looked at to show
     how much of the result depends on immediacy. It does not enter the 5%.

**Block length, both tiers (adopted 2026-10-09, proposal (a)):** the median of the base
columns' Politis–White lengths over the whole in-sample window after warm-up (8,866 rows).
- For the class tier, that is its own window, so the class rule is unchanged.
- For the stream, it replaces the scored-window median. The stream's tier
  (`learn/stream_tier.py`) is not changed. The read script computes the block length and
  draws the bootstrap rows itself.
- On this panel the whole-window median is 1.91 at d = 0, so L = 2.

**The split of the 5% (confirmed by the author, 2026-10-09):**
- **The stream certifies iff its p < 0.04.**
- **The class tier certifies iff its p < 0.01.**
- The family-wise error over the two is at most 5% (Bonferroni).

**Why:** the class tier's 80%-power net Sharpe is 2.46 even at its 95% point (section l,
d = 0). An edge it could certify must be very large at any weight.
- Against an even split (2.5% each), the class's net floor rises from 2.562 to 2.670
  (+0.11).
- The stream's gross floor falls from 2.173 to 2.067 (−0.11).

This is the French split, chosen for the same reason. **It was set from the design
numbers alone,** before any outcome was computed.

## l. Outcome-free design quantities

**Sources:**
- d = 0: `experiments/binance_design_d0.py`, committed before its run at `ef8f0a7`; output
  `runs/binance_design_d0/2026-10-09` (`fda86df`); seeds 695058 (stream), 695059 (class),
  695060 and 695061 (leak tests).
- d = 1: `experiments/binance_design_chosen.py` (`086f6ad`); output
  `runs/binance_design_chosen/2026-10-09` (`7f0e2c9`); seeds 695056 and 695057.
- Both: pinned inputs; the laptop; the cost rule; the closure; the whole-window block
  length; B = 5,000.
- **Not computed:** no observed score, realised mean, Sharpe or p-value.
- **Power:** Lo's iid formula with ppy 2,190: the certified SR solves
  SR − 0.8416 · sqrt((1 + SR²/4,380) / T_years) = bar.
- **Gross needed** = net at 80% power + cost drag. The cost drag is cost per year divided by
  the stream's annualised volatility.

**The stream, d = 0 (registered) beside d = 1 (descriptive):**

| timing | rows | years | L | bar 95% → net / gross | bar 96% → net / gross | drag | turnover per unit gross | cost per year | dead share | ann. vol | mean gross |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **d = 0** | 8,104 | 3.70 | 2 | 0.839 → 1.277 / 1.992 | 0.914 → **1.351 / 2.067** | **0.715** | **0.0946** | 0.1142 | 0 | 0.160 | 0.664 |
| d = 1 | 8,102 | 3.70 | 2 | 0.837 → 1.275 / 1.864 | 0.896 → 1.334 / 1.923 | 0.589 | 0.0797 | 0.0987 | 0 | 0.168 | 0.685 |

- At d = 0 the stream's bars at 97.5% and 99% are 1.020 → 1.458 / 2.173 and
  1.178 → 1.616 / 2.331.
- **d = 0 trades more:** turnover per unit gross is 19% higher, and the cost drag 0.13
  higher. So at d = 0 the gross Sharpe needed rises by 0.14, although the bar barely
  moves.
  - The fit at d = 0 predicts the returns of bars t+1 to t+5 rather than t+2 to t+6, with
    the most recent bar's information one bar fresher. That its targets change faster is
    a plausible reading, not a measured one.
- **Per-row cost under the rule, d = 1** (live rows of the scored window): median 7.63 bps;
  5% 6.00, 25% 6.59, 75% 9.04, 95% 11.85; mean 8.15; 12.3% of rows at the 6 bps
  minimum.
  - Per contract (median): BTC, ETH and BNB 6.0 bps; most between 6.3 and 9.0; the highest
    EOS 10.4, YFII 10.8 and CRV 12.2.
  - At d = 0 the rates are the same apart from 52 rows (section h).
- **At flat 10 bps (d = 1, for reference):** drag 0.713, gross needed 1.988 at 95% and
  2.047 at 96%.
- **Seconds per fit at d = 0:** 121 (rolling 756) and 1,144 (expanding). The run shared the
  laptop's cores with two other jobs. At d = 1, run alone, they were 65 and 206.

**The class tier (block length 2):**

| timing | rows | 95% | 96% | 97.5% | 99% |
|---|---|---|---|---|---|
| **d = 0** | 8,866 (4.05 years) | 2.037 → 2.456 | 2.076 → 2.495 | 2.144 → 2.562 | 2.251 → **2.670** |
| d = 1 | 8,865 | 2.019 → 2.438 | 2.059 → 2.478 | 2.128 → 2.547 | 2.245 → 2.664 |

- The class's cost drag is not computed. Its bar is on demeaned streams, so a gross figure
  would need each member's drag.
- **The fast kernel's tables were rebuilt for d = 0:** 1,936 s, against 778 s for d = 1,
  with three jobs sharing the cores. The null pass took 127 s.

**Checks at d = 0 on this panel** (`fda86df`):
- **Leak tests:** all pass. The learner's book is bit-identical up to t = 4,814 when every
  input after it is replaced, and the change is visible after it. Each block builder
  passes the same test: X (on returns), V (on volume, taker volume and trade count),
  F (on funding), and the groups.
  - The block builders do not depend on d. X's test on the market series also passed on
    the same builder at d = 1 (`d4d2824`, `4102600`).
- **Bit-for-bit repeat:** two fits in separate processes give identical positions.

## m. The in-sample read (scripted, no agents)

**Two tests only, run once, in this order:**
1. **Version 2's stream at d = 0 through the supplied-streams tier.**
   - Window: its 8,104 scored rows.
   - Block length by section k's rule; B = 5,000; `default_rng(701000)`.
   - **Certified iff p < 0.04.**
2. **The class maximum against the class null.**
   - Window: all 8,866 rows at d = 0; 82,240 members; the fast kernel.
   - Block length by the class rule; B = 5,000; `default_rng(701001)`.
   - **Certified iff p < 0.01.**

**Then, descriptive only: the d = 1 stream** (section k, item 3).
- Its observed net Sharpe over its 8,102 scored rows.
- Its 95% interval: the 2.5% and 97.5% points of the Sharpe over B = 5,000 stationary
  bootstrap resamples of the stream, with the block length by section k's rule,
  `default_rng(701002)`.
- It is printed after both tests' verdicts, under the line "descriptive, not a test:
  the same stream with a one-bar delay". **It carries no p-value and no verdict.**

**Seeds:** block 701000–701999 (`experiments.seed_block_check`: NO COLLISION, 2026-10-09).
Only 701000, 701001 and 701002 are used.

**Before pricing:** two version 2 fits at d = 0 must give bit-identical positions, and so
must two at d = 1. If either pair differs, nothing is priced and the read stops.

**The runner's start-up refusals:**
- Darwin arm64, and the macOS LightGBM pin;
- the six pins at their hashes (three at d = 0, three at d = 1);
- the learn2 blobs equal the confirmation's;
- no tracked changes;
- this registration's live commit is an ancestor of HEAD;
- HEAD equals the commit named on the command line.

**Recorded for each test, whatever the verdict:** the observed net Sharpe; p; the 90%
lower bound; the confidence curve; and, for the class, the best member's features and
signs.

**Both branches for each test:**
- **Certified:** "certified in-sample at the registered weight; whether it holds is the
  holdout grading's question."
- **Refused:** "refused; consistent with the registered detection floor; no further
  reading."

## n. Registered expectations, stated in advance

| tier | certifies iff | bar | true net Sharpe certified with 80% power | gross Sharpe needed |
|---|---|---|---|---|
| version 2 stream, d = 0 | p < 0.04 | 0.914 | **1.351** | **2.067** |
| class tier, d = 0 | p < 0.01 | 2.251 | **2.670** | not computed |

- **A refusal is the more likely outcome.**
  - The stream must earn a net Sharpe above about 1.35, a gross above about 2.07, to be
    certified with 80% power.
  - Most cross-sectional rules on liquid crypto contracts are not expected to clear that
    after costs.
- **A refusal is not evidence of no edge.** It is consistent with the detection floor of
  3.7 years of 4h data at these error rates.

## o. The holdout: 2025-04 to 2026-09, and what it can show

- **Graded in both branches,** as on French: a separate grading registration, written
  after the in-sample read and before any holdout row is parsed.
  - The walk-forward and the blocks continue across 2025-04-01 without restarting state.
  - The grading's no-restart checks are as at `4f11f95`.
- **What it can show:**
  - 1.50 years: the standard error of an annualised Sharpe is about
    sqrt(1 / 1.5) ≈ 0.82;
  - so a 95% interval is about ±1.6 wide each side.
  - It can reveal a gross failure, a large negative realised Sharpe against a certified
    lower bound.
- **What it cannot show:**
  - it cannot confirm a modest edge: a true Sharpe of 1 is not distinguishable from 0;
  - it cannot separate a decayed edge from noise.
- **The holdout is the archive's last complete month at going live** (B4). It is not
  extended later.
- **Deaths in the holdout** follow the general rule in section d: dead from the earlier of
  the registered death rule and the first bar with no kline row. They are decided on the
  holdout host at grading. The listing already points to five holdout deaths (EOS, MKR,
  ALPHA, SXP, LRC; section d).

## p. Stated limits

- **A delisted contract is settled by the venue at a final price,** which may differ from
  its last bar's close. Closing at the last bar's price ignores that difference. Up to five
  of the 50 contracts are affected in the holdout.
- **Fills at the close (d = 0) are optimistic** by the seconds between the close and an
  order (section i). The d = 1 stream shows how much depends on that.
- **A US resident cannot trade this venue.** Binance's USDT-margined perpetuals are not
  offered to US persons. The results are about the method on this data, not an
  implementable strategy for the author.
- The fee is an assumption, and the spread estimate is checked on only 12 contract-days.
- The funding, gaps and deaths are as the archive records them. The archive's own errors
  are not checked beyond the CHECKSUMs and the fill's overlap test.

## q. Dataset ledger entry (before any run)

**`prereg/DATASET_LEDGER.md` gets this entry in the same commit that makes this
registration live.**

| field | value |
|---|---|
| dataset | Binance USDT-margined perpetuals, 4h, formation 2021-01, top 50 |
| fetched | 2026-10-08 (formation, funding) and 2026-10-09 (4h klines, fill), laptop; manifests in section a |
| derived CSVs | `data/raw/binance_4h_2021-01/`, 190 files; combined SHA-256 `5ae9a12fa37c73b34bbf862029665f2ba1ce0fbac2c0acfbd348e6f60ba31cb8` (`data/binance_4h_2021-01_derived_manifest.json`) |
| grid | 2021-02-01 00:00 – 2025-03-31 20:00 UTC, 9,120 bars |
| scored in-sample | d = 0: earned bars 2021-03-15 08:00 – 2025-03-31 20:00 (8,866; class), stream from 2021-07-20 08:00 (8,104) |
| holdout | 2025-04-01 00:00 – 2026-09-30 20:00; never downloaded to the laptop; 1,660 published CHECKSUMs recorded (`data/binance_4h_2021-01_holdout_checksums.json`) |
| raw zips | `~/Desktop/og-quarantine/binance/` (in-sample only) |
| pinned | d = 0: X `da66f540df2102eed75c9ca2580eb44ccc733835e9cbac0f2bb04a73cf12eafa`, v2 `602325699910ebf3adc4326aaa8c150c993a1e1711a732f5a429a07d5f644164`, costs `9fe8813e06cdd7dc8dd3ac70b5b0d34bd4dd3e7ba0f5d59a2798ae5c482acecf`; d = 1: X `e6ff168cc06dbe795b90d73edfeafad332f886417331f2e921404ad677e8e257`, v2 `47c688ee76ba8e9f5070a31e4ff155a0d702e6e7a72bc99aee5c4e224206e6c5`, costs `74be4b19b9fad50cc878aae82d4b616b1ec93f12026aedf8aa51a45033399789` (arm64) |
| pricing platform | laptop (arm64) only |
| reads so far | outcome-free design quantities, and the book-ticker spread check |
| outcome reads | none |

---

## Appendix: the draft's history (2026-10-08 to 2026-10-09)

Kept as written. Its headings are demoted by one level. Where it differs from the body
above, the body governs.

### The earlier header

#### Binance USDT-margined perpetuals, 4h: DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE.** It is committed for the author's review. It is not a
registration, and nothing in it binds until a separate, dated commit makes it live.
- No agent session has run and no box has been used.
- **No outcome has been read:** no realised Sharpe, p-value or certification.
- **No holdout row (2025-04-01 onward) has been downloaded or parsed.** Holdout files were
  listed, with names, sizes and their published CHECKSUM text, and counted.
- The windows follow `prereg/new-panels-audit-2026-10-06.md`. That audit fixed the
  holdout at 2025-04-01 before any price was read.
- **Code:** the fetch, loader and builder are at `4e18a87`, committed before the fetch.
  The design script is at `d0667f0`, committed before its run; its output is at `6537bd3`.

Each choice is stated **with the alternative not taken**. Choices the author must make are
collected in **"Open choices"** at the end.

### a. Source

- **data.binance.vision, `futures/um` (USDT-margined).** The fetch uses monthly files only:
  - `klines/<SYM>/4h/` for bars;
  - `fundingRate/<SYM>/` for funding.
- **Every zip is verified** against its published `.CHECKSUM` (SHA-256) before use. A
  mismatch refuses the fetch.
- **The one fetch:** 2026-10-08 04:53:32 UTC, on the laptop.
  - 3,926 in-sample zips (klines and funding) were downloaded and verified. 174
    contract-months had no file, all after delistings.
  - Their hashes, and every formation file's hash, are in `data/binance_manifest.json`.
- **Where the files are:**
  - The raw zips are quarantined under `~/Desktop/og-quarantine/binance/`. That is outside
    the repository and refused by every loader.
  - The derived in-sample CSVs are in `data/raw/binance_insample/` (gitignored).
- **Alternatives not taken:**
  - the daily-file series: it is redundant with the monthly files for the in-sample
    window;
  - the REST API: it is not archived and not checksummed.

### b. Bars and windows

- **Bars:** 4h, indexed by open time (UTC). There are 6 a day, every day, so 2,190 a year.
- **Scored in-sample:** the bars whose earned return opens from 2022-01-01 00:00 to
  2025-03-31 20:00. That is **7,116 bars, 3.25 years**.
  - Feature row t earns bar t + 2, as on the daily panels: signal at the close of bar t,
    held from the close of t+1 to the close of t+2.
- **Warm-up:** 253 bars before the first feature row (2021-12-31 16:00). They run from
  2021-11-19 12:00 and feed features only.
  - **Data needed and available:** all 50 contracts have 4h rows from 2021-11 onward. This
    is guaranteed by the universe rule: every member traded on every day of October 2021.
- **Holdout:** 2025-04-01 00:00 onward.
  - The monthly archive runs to **2026-09**. For the 50 contracts it lists 1,664 holdout
    files (klines and funding); these were counted only.
  - **Decided (B4, 2026-10-08): the holdout ends at 2026-09-30,** with the last bar
    opening 20:00. That is the last complete month in the monthly archive.

### c. Universe, point in time

**The rule** (`data/fetch_binance.py`):
1. **Candidates:** every symbol in the `futures/um` klines listing that is a USDT-quoted
   perpetual (no `_YYMMDD` delivery suffix), excluding:
   - stablecoin bases (USDC, BUSD, TUSD, USDP, DAI, FDUSD, PAX, UST, USTC, SUSD);
   - composite index contracts (DEFI, BTCDOM, FOOTBALL, BLUEBIRD).
2. **Formation month: October 2021**, entirely before the warm-up starts. A candidate
   qualifies only with a 1d kline showing trades on **every one of the 31 days**: 126 did.
3. **Rank** by the month's summed quote volume (USDT). Take the **top 50, held fixed.**
   - Number 50 traded 4.28 bn; number 51 traded 4.06 bn.
   - The universe is listed in the manifest.
4. **Delisted contracts stay in until their delisting.** No contract enters later.

**How survivorship is avoided:**
- Membership uses October 2021 data only. No later information, including whether a
  contract survives, enters the choice.
- **7 of the 50 die in-sample:**

  | contract | dead from |
  |---|---|
  | KEEPUSDT | 2022-02-15 |
  | LUNAUSDT | 2022-05-12 |
  | TLMUSDT | 2022-06-09 |
  | ICPUSDT | 2022-06-10 |
  | MATICUSDT | 2024-09-04 |
  | FTMUSDT | 2025-01-06 |
  | OMGUSDT | 2025-01-31 |

  They are kept to their death, so their crashes and migrations are in the data. Together
  they are 6.98% of the universe's formation volume.

**How a delisting is detected: from the rows, not from file sizes.** A contract is dead from
the bar after its last bar with trades (`count > 0` and `volume > 0`) if either:
- it never trades again in-sample (the archive's filler rows have zero trades and a
  constant price, and later months may be absent); or
- its next trade comes only after a silence of 180 or more bars (30 days). That is treated
  as a new contract, which is not entered. **Decided (B3): dead from the silence, no
  re-entry** (this applies to ICPUSDT and TLMUSDT).

The audit's file-size heuristic is not used.

**Alternatives not taken:**
- a rolling universe (re-formed periodically): this adds entries and needs a mask;
- a formation by market capitalisation: that is not in the archive;
- a top 100: more contracts with thin early trading.

### d. The tradable mask: options and costs

The fast kernel refuses masks. **Decided (B1, 2026-10-08): d3, no mask; a dead contract
becomes idle capital.**
- **Its returns.** The last traded bar's return is earned in full by any position held
  over it. Every later bar earns 0, with funding 0 and cost 0.
  - The death bar is the first bar after the last trade.
  - A trade decided at the close of bar t executes at the close of t+1, so it is costed iff
    bar t+1 is live.
- **Its features are finite and deterministic.** From the death bar on, every one of its
  20 base signals is set to NaN *before* the cross-sectional transforms. Any ±inf (a zero
  volatility in a ratio) is set to NaN first.
  - So it drops out of that row's z-score mean and standard deviation, and out of its rank
    count.
  - Both transforms map a missing value to 0, so **all 40 of its features are exactly 0.**
  - Zero volatility therefore never produces a NaN, or a divide-by-zero, in X.
  - Tested in `tests/test_binance_panel.py`: all-zero features after death, a finite X,
    and live ranks still spanning [−1, 1].
- **The weight a strategy can place on it is not zero.** A class member and ridge_stack
  both demean their scores across all 50 contracts.
  - So a dead contract (score 0) receives **minus the row's mean score, divided by the
    row's gross score.**
  - A class member is a signed sum of up to three features, so its mean score is the mean
    of those features over the 50, and the dead weight is −mean/gross.
  - ridge_stack's basis portfolios are each demeaned the same way, so its dead weight is the
    combination of those.
  - That weight earns nothing and costs nothing. Its size is measured in item C (the share
    of gross held in dead contracts).
- Positions remain a function of X alone, so the fast kernel and the pinned ridge_stack
  both run unchanged.
- **The distortion:** books may hold dead contracts, which dilutes them. There is no
  look-ahead: a death is seen in the features only after it happens.

| option | how | cost |
|---|---|---|
| **d1** slow path with a mask | `streams_for` with `tradable` False after a death | Class pass: about 6 min per pass over the 82,240 members (measured on 128). A null pass needs the streams again, chunked, or 4.7 GB in memory, which does not fit the laptop. So roughly 10–15 min per class pricing call, against 90 s on the fast kernel. **And ridge_stack's pinned code (`learn/`, `fce5627`) has no mask:** it would trade dead contracts. A mask means changing `learn/` and breaking the pin. |
| **d2** survivors only | the contracts live through the whole window: 43 of the 50 | **Survivorship:** the 7 dead contracts (6.98% of formation volume) are removed, among them LUNA's collapse. **Bound:** at most 7 of 50 contracts, and at most 14% of the equal-weight cross-section, is affected. The bias is towards survivors' returns, with no estimate of its sign for a long-short book. |
| **d3** (decided) idle after death | as above | No code change; fast kernel. Weights on dead contracts dilute books. |

### e. Returns and funding

- **Return:** r_t = close_t / close_{t−1} − 1 − F_t.
  - F_t is the sum of funding rates with open_t < calc_time ≤ open_t + 4h.
  - So a funding event at a bar boundary falls in the bar that **ends** there. The position
    held over that bar is the one held at the funding time; the rebalance at that close
    comes after.
- **Sign convention: Binance's.** A positive rate is paid by longs and received by shorts.
  A long earns −F_t and a short earns +F_t, through the same w · r.
  - Tested in `tests/test_binance_panel.py`: with a flat price and a +0.1% funding event,
    a long's return is −0.1% and a short's is +0.1%.
- **Funding intervals:** most are 8h. Two contracts move to shorter intervals in-sample:
  SOLUSDT to 2h and 4h, OMGUSDT to 2h. Every event inside the bar is summed.
- **Gaps:** a bar with no row, or with zero trades, while a contract is live is a gap. Its
  close is carried forward, and it stays tradable and costed.
  - **An archive hole:** 15 of the 50 contracts have no 4h rows for **2022-02-26 00:00 –
    02-28 20:00** and **2022-04-01 00:00 – 04-02 20:00**, 30 bars in all. Carrying the
    close puts the whole move across each hole into one bar.
  - **Decided (B2): fill them from the archive's daily 4h files,** only if those agree with
    the monthly file on the overlapping bars. Otherwise the close is carried and the bars
    flagged.
    - **The tolerance:** a relative difference of at most 1e-9 on open, high, low, close,
      volume and quote volume, and an equal trade count, on every bar of the days just
      before and just after each hole.
    - **The result:** all 15 contracts were **filled**, 30 bars each. Each hole had 12
      overlap bars, and the maximum relative difference was **0**: the files are
      identical where they overlap.
    - The daily files were verified against their CHECKSUM and quarantined.
    - Code: `data/fetch_binance_fill.py` (`a9d8801`). Manifest:
      `data/binance_fill_manifest.json` (`96b683e`).
    - **A fill never overrides a monthly row.**
  - The same check also filled ICPUSDT's and TLMUSDT's missing months during their
    silences. Both remain dead from the silence (B3).
- **Decided (B7): signals are price-only. Funding enters the earned return only.** The
  signals use close-to-close price returns, and so does the market series they use. The
  alternative not taken is total-return signals.

### f. Costs

- **Decided (B5): 10 bps one-way per unit of turnover,** charged on live contracts. **It is
  an assumption.** It is made of a taker fee of 5 bps and slippage of 5 bps. There is **no
  borrow term:** shorts pay or receive funding instead.
- **The taker fee, re-checked on 2026-10-08: not confirmed from the published schedule.**
  - Binance's USDⓈ-M fee-rate table (`binance.com/en/fee/futureFee`) showed no rates
    without a login ("No records found").
  - Binance's futures fee FAQ (`binance.com/en/support/faq/360033544231`, last updated
    2026-05-01) states "a Regular User's maker fee is 0.02% and a Regular User's taker fee
    is 0.05%". It labels this as a calculation with **hypothetical** fee rates.
  - A search summary reported 0.04% taker at Level 0. That could not be traced to a page
    and is not relied on.
  - **So the 5 bps taker half is the FAQ's illustrative regular-user rate,** not a
    confirmed schedule figure. It is stated as such.
- **The slippage half (5 bps) is unmeasured,** and is said to be. It is plausible for the
  most liquid contracts and optimistic for the thinner ones in the top 50.
- **Alternatives:**
  - a per-contract slippage from formation-month volume;
  - a sensitivity read at 5 and 20 bps.

### g. Market series

**Decided (B6):** the equal-weighted average of the **live** contracts' price returns,
each bar. The alternative not taken is to average all 50, with dead contracts at 0.

### h. Features: the same code, different horizons

- **The registered 40,** with lookbacks **in rows, as coded.** Exact ties take average
  ranks, as on French. **X is pinned** once the data choices are settled.
  - The design numbers below are on the unpinned build, and are **provisional**.
- **On 4h bars these are different horizons from the daily panels:**
  - `mom5` is 20 hours;
  - `mom21` is 3.5 days;
  - `mom63` and `vol63` are 10.5 days;
  - `mom252`, `vol252`, `beta252` and `drawdown` are 42 days;
  - `ma50` is 8.3 days and `ma200` is 33.3 days;
  - `mom12_1` is bars t−251 to t−21: 42 days skipping the last 3.5.
- **ridge_stack's "years" are 252-row blocks, which is 42 days.**
  - It refits every 252 rows, with trees every second block.
  - It trains on 3 blocks (126 days) before scoring.
  - Over the window there are about 28 blocks: 6,360 scored rows from 2022-05-07.
- **What in `learn/` assumes daily data.** These are horizons, not errors:
  - `YEAR = 252` and `FIRST_TEST_YEAR = 3`: refit cadence and initial training, as above;
  - `STATE_MIN_HISTORY = 252`: states start after 42 days;
  - `sigma`'s 63-row window: 10.5 days;
  - the 5-row trailing mean of positions: 20 hours;
  - `GAP = 2` rows: an 8-hour embargo;
  - the 64-row warm-up drop: 10.7 days.

  **None is wrong in arithmetic.** Each is a different horizon on 4h bars.
- **Sharpe annualisation is correct.** `learn.inputs.sharpe`, the supplied-streams tier,
  the class tier, `quixote.confidence` (P_H) and `RealSandbox` all take
  `panel.periods_per_year`, which is 2,190. No `252` is hard-coded as an annualisation
  anywhere on the pricing path. (`quixote.confidence`'s default `ppy = 252.0` is always
  overridden by its callers here.)

### i. What may be tried

1. **The class tier:** `SubsetClass`, max_size 3, signed (82,240 members), over the 7,116
   scored rows.
2. **One ridge_stack stream:** pinned as in the confirmation, the code at `fce5627` and the
   four `learn/` blob hashes. It is priced through the supplied-streams tier on its 6,360
   scored rows.
- **The split of the 5% is left open** for the author, now that the design numbers exist
  (section k).

### j. Sealing and its limits

- **No holdout zip has been downloaded.** The holdout's identity is fixed now, without
  reading it: the published SHA-256 of each holdout month file is recorded in the manifest.
  At grading, each downloaded file must match.
- **The loader** (`environments.binance_panel.load_symbol`) refuses:
  - any row with open time or calc time on or after 2025-04-01;
  - any sealed (`.enc`, `.gpg`, `.asc`) or quarantined (`~/Desktop`) path.
- **The data is public, so the seal is procedural.**
- **Limit, recall:** 2025 onward may lie inside the agent model's training data. For
  agents, contract names and dates are masked: assets are `C00`–`C49`, and rows are
  indexed. Whether recall leaks through anyway is stated as a limit, not measured.

### k. Outcome-free design quantities (PROVISIONAL: unpinned build, before B1–B7)

These figures predate decisions B1–B7: total-return signals, unfilled holes, and dead
contracts' features following their flat price. Item C recomputes the stream's figures on
the decided build.

**Source:** `experiments/binance_design_quantities.py` (`d0667f0`); output in
`runs/binance_design/2026-10-08` (`6537bd3`).
- **Platform:** the laptop, Darwin arm64.
- **Replicates:** B = 5,000.
- **Seeds:** 695000–695002.
- **Not computed:** no observed score, realised mean, Sharpe or p-value.

**Power, Lo's iid formula, annualised correctly:** the certified SR solves
SR − 0.8416 · sqrt((1 + SR² / (2 · 2,190)) / T_years) = bar.

| tier | window | block length | 95% → certified at 80% power | 96% | 97.5% | 99% | seconds per pricing call |
|---|---|---|---|---|---|---|---|
| class (fast kernel) | 7,116 rows, 3.25 years | 3 | 2.573 → **3.040** | 2.657 → 3.125 | 2.806 → 3.273 | 3.049 → 3.517 | 90 at B 5,000 (cache built once in 560 s) |
| ridge_stack stream | 6,360 rows, 2.90 years (2022-05-07 – 2025-03-31) | 3 | 0.960 → **1.454** | 1.012 → 1.506 | 1.136 → 1.630 | 1.311 → 1.805 | 328 for the predictor + 21 for the tier |

- **The fast kernel accepts the panel.** Its streams match the registered `streams_for` to
  5.9e-16.
- **ridge_stack on this panel:**
  - the bit-for-bit repeat of positions: **True**;
  - the leak test at rows 1256, 3558 and 6816: **PASS**.

### l. Item C: bar size, cost drag and the floor (outcome-free; PROVISIONAL unpinned builds)

**Source:** `experiments/binance_design_c.py`, committed before its run at `6ca2e0a`; output
in `runs/binance_design_c/2026-10-08`.
- **Builds:** the decided ones (B1–B7), on the laptop.
- **Replicates:** B = 5,000, with stream seeds 695010–695013 and class seeds
  695020–695023.
- **Not computed:** no mean return, Sharpe or p-value.

**The daily variants.**
- UTC daily bars, ppy 365, the same row-based code.
- The data starts in the month after formation and runs to 2025-03-31. **The 253-row
  warm-up lies inside that span,** because no earlier data exists for the 2020-09 formation
  (the archive starts in 2020-01).
- ridge_stack then needs 3 × 252 rows of training. That is why its scored windows are
  short.

**ridge_stack's stream:**

| variant | qualifying / universe / dead in-sample | scored rows (years) | turnover per row (per year) | cost per year | annualised vol | cost drag (Sharpe) | dead share of gross | bar 95% → net / gross at 80% power | bar 96% → net / gross |
|---|---|---|---|---|---|---|---|---|---|
| 4h (2021-10) | 126 / 50 / 7 | 6,360 (2.90) | 0.156 (341.5) | 0.322 | 0.253 | **1.273** | 0.045 | 1.039 → **1.533 / 2.806** | 1.103 → 1.597 / 2.871 |
| daily 2020-09 | 44 / 44 / 3 | 632 (1.73) | 0.152 (55.3) | 0.055 | 0.214 | 0.256 | 0.011 | 1.238 → **1.879 / 2.135** | 1.305 → 1.946 / 2.202 |
| daily 2021-01 | 79 / 50 / 4 | 509 (1.39) | 0.131 (47.8) | 0.048 | 0.212 | 0.224 | 0.003 | 1.428 → **2.143 / 2.366** | 1.519 → 2.234 / 2.458 |
| daily 2021-10 | 126 / 50 / 7 | 236 (0.65) | 0.106 (38.5) | 0.038 | 0.217 | 0.177 | 0.001 | 2.022 → **3.076 / 3.253** | 2.165 → 3.219 / 3.396 |

**The class tier, daily variants** (bar → net Sharpe at 80% power; the class's
gross-versus-net is not computed):

| variant | rows (years) | 95% | 96% |
|---|---|---|---|
| daily 2020-09 | 1,388 (3.80) | 2.101 → 2.535 | 2.133 → 2.567 |
| daily 2021-01 | 1,265 (3.47) | 2.170 → 2.625 | 2.211 → 2.666 |
| daily 2021-10 | 992 (2.72) | 2.460 → 2.973 | 2.499 → 3.012 |

The 4h class tier, on the earlier build (section k), was 2.573 → 3.040 at 95%.

**Gross floor** = the net floor plus the cost drag at 10 bps. The cost drag is cost per
year divided by the stream's annualised volatility.

### Open choices (for the author)

Decided on 2026-10-08 and written in above:
- B1: d3, idle after death;
- B2: holes filled (all 15, an exact match on the overlaps);
- B3: no re-entry after a silence;
- B4: the holdout ends at 2026-09-30;
- B5: 10 bps, an assumption;
- B6: the live-contract market;
- B7: price-only signals.

**Still open:**
1. **The split of the 5%** between the class tier and the stream. It is left open until
   item C (bar size) is done.
2. **The universe parameters:** top 50, the formation month, full-month trading, and the
   stablecoin and index exclusions. Also left open until item C.
3. **The bar size:** 4h, or one of the daily variants (item C).

### Note, 2026-10-08 (America/Chicago): held unread; not registered with ridge_stack version 1

The author read item C's comparison (`28194a4`) and decided:
- **Every variant needs a gross Sharpe above 2.1.** At 80% power the stream's gross floor
  is 2.135–3.396 across the four variants (section l). That holds at 95% and 96%, and on
  4h bars as on daily.
- **This panel is not registered, and not read, with ridge_stack version 1.**
- **It is held unread** until a version-2 predictor has been confirmed on planted panels.
- **The bar size, the split of the 5% and the universe settings stay open.** They will be
  chosen from version 2's own design numbers, not from section k or section l.
- **The taker fee stays unverified** (section f). The author will supply it from the
  author's own fee table.
- **Nothing more is fetched, run or read on this panel until then.** The data already
  fetched stays as it is: the in-sample CSVs, the quarantined raw zips, the manifests and
  the recorded holdout checksums.

### Scoping note, 2026-10-08 (America/Chicago): a spread estimate for version 2's cost model

**Status:** a scoping note only, in a draft that stays DRAFT, NOT LIVE.
- No estimate has been computed and no panel outcome has been read.
- Nothing was downloaded beyond directory listings.
- The panel stays held unread (note of 2026-10-08 above).

**1. Book-ticker (best bid and ask) files on data.binance.vision, `futures/um`.**
- **Present:** `bookTicker` exists under both `monthly/` and `daily/`, for 315 symbols. 48
  of this draft's 50 universe contracts have it. LUNAUSDT does not.
- **But the dates are short:** for the contracts checked (BTC, ETH, SOL, AXS, SUSHI), the
  monthly files cover only **2023-05 to 2024-04** (12 months, each with a CHECKSUM file).
  BTCUSDT's daily files cover 2023-05-16 to 2024-03-30 (320 days).
- **And the files are very large** (zipped, per contract-month, minimum / median /
  maximum):

  | contract | per month |
  |---|---|
  | BTCUSDT | 38 MB / 4.4 GB / 8.3 GB |
  | ETHUSDT | 31 MB / 3.3 GB / 8.4 GB |
  | SOLUSDT | 24 MB / 1.6 GB / 4.0 GB |
  | AXSUSDT | 5 MB / 374 MB / 812 MB |
  | SUSHIUSDT | 5 MB / 281 MB / 783 MB |

  A BTCUSDT daily file has a median of 146 MB.
- **So book-ticker data does not cover 2022–2025.** It covers about a year in the middle,
  and the universe for that year would be some hundreds of GB. It can serve only as a
  **check** on a bar-based estimator, over 2023-05 to 2024-04, on a few contracts.

**2. Estimators from bar data.** The references were checked against Crossref on
2026-10-08. The biases listed are those that follow from each construction; they were not
re-verified from the papers' text.

| estimator | reference |
|---|---|
| Roll | Roll, R. (1984), "A Simple Implicit Measure of the Effective Bid-Ask Spread in an Efficient Market", *Journal of Finance* 39(4), 1127–1139. doi:10.1111/j.1540-6261.1984.tb03897.x |
| Corwin–Schultz high–low | Corwin, S. A., and Schultz, P. (2012), "A Simple Way to Estimate Bid-Ask Spreads from Daily High and Low Prices", *Journal of Finance* 67(2), 719–760. doi:10.1111/j.1540-6261.2012.01729.x |
| Abdi–Ranaldo close–high–low | Abdi, F., and Ranaldo, A. (2017), "A Simple Estimation of Bid-Ask Spreads from Daily Close, High, and Low Prices", *Review of Financial Studies* 30(12), 4437–4480. doi:10.1093/rfs/hhx084 |
| EDGE (open, high, low, close) | Ardia, D., Guidotti, E., and Kroencke, T. A. (2024), "Efficient estimation of bid–ask spreads from open, high, low, and close prices", *Journal of Financial Economics* 161, 103916. doi:10.1016/j.jfineco.2024.103916 |

- **Roll (serial covariance of price changes).** It is undefined whenever the covariance is
  positive, and it is noisy. In a trending or momentum period it is often undefined.
- **Corwin–Schultz.** It separates volatility from spread by comparing one- and two-period
  high–low ranges. Its period estimates are often negative, and the usual zero floor then
  biases it upward. Volatility not captured by the two-period assumption also leaks in.
  There is no overnight gap on a 24/7 venue, which removes one of its known adjustments.
- **Abdi–Ranaldo.** It uses the close and the high–low midpoint. Like Corwin–Schultz it
  depends on how volatility scales within the bar, and averaging over a window is needed.
- **EDGE.** It combines all four prices. By its own account it is unbiased and has the
  least variance among such estimators under its assumptions. Its sensitivity to bar
  frequency and to trade discreteness on crypto contracts is not known here.

**3. A proposed per-contract cost rule** (for the author's decision; nothing is
computed):
- **cost_rate_i(t) = 5 bps (the fee, an assumption) + ŝ_i(m) / 2,** the estimated
  half-spread.
- **The estimate ŝ_i(m)** is EDGE's spread for contract i from the 1h bars of the 30 days
  **before** month m begins. It is re-estimated once a month, applied to every bar of
  month m, and floored at 0.
- **No look-ahead:** each month's cost uses only bars that closed before that month
  started. A dead contract's cost stays 0 (decision B1).
- **A check before use** (outcome-free; it reads only quotes and prices):
  - over 2023-05 to 2024-04, compare ŝ with the book-ticker time-weighted quoted spread for
    two or three contracts (BTC, a mid-cap such as AXS, a thin one such as SUSHI);
  - download only those contract-months, each verified against its CHECKSUM;
  - report bias and rank correlation.
- **The alternative,** if the check shows EDGE biased on these bars: Abdi–Ranaldo on the
  same window, with the same check.

**Recommendation:**
- EDGE on trailing-30-day 1h bars, re-estimated monthly;
- the book-ticker check on 2–3 contracts first;
- a fixed 5 bps fee on top.

### Clarification, 2026-10-09 (America/Chicago): B7 and version 2's funding block

The author's clarification, recorded so that two decisions of 2026-10-08 do not read as a
conflict:
- **B7 ("signals are price-only") applies to version 1's registered 40 features (P).**
- **Version 2's design adds an F block (funding), approved the same day.** On Binance, F
  stays in version 2's base view: the funding paid in each bar, whose calc time is at or
  before that bar's close.
- **P, X and the neutrality groups stay price-only.** X and the groups are built from
  price-only bar returns and the live-average market of price-only returns.
- Funding still enters the earned return as in section e.

### Correction, 2026-10-09 (America/Chicago): the builder dropped the taker-buy columns

- **What was wrong.** `data/fetch_binance.py`'s `parse_klines` kept eight of the archive's
  twelve kline columns. It dropped `taker_buy_volume` and `taker_buy_quote_volume` in
  error when the in-sample CSVs were written (4h, the 4h fills, and the three daily
  formations).
- **What was done** (`data/rebuild_binance_taker.py`, `1cb047c`, fix `27ffc6a`; manifest
  `data/binance_taker_manifest.json`):
  - no download;
  - each quarantined zip was re-read at the SHA-256 recorded when it was fetched;
  - the rebuilt rows' first eight fields were checked equal to the existing derived CSVs;
  - `{SYM}_{bar}_taker.csv` files were written beside them. The existing CSVs are
    unchanged.
- **When.** Restored before any outcome was read on this panel, and before its X is
  pinned (`PINNED_X_SHA256` is still empty).
- **Effect.** Version 2's V block on Binance has all five columns: logvol_ratio,
  taker_last, taker_mean21, count_ratio, amihud21. Version 1's 40 features never used
  volume and are unaffected.
