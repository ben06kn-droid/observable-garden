# Binance USDT-margined perpetuals, 4h: DRAFT, NOT LIVE

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

## a. Source

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

## b. Bars and windows

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
  - **Open:** the holdout end. Either 2026-09-30 20:00 (the last complete month in the
    monthly archive), or the fetch date, which needs the daily files for 2026-10-01 to
    10-07.

## c. Universe, point in time

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
  as a new contract, which is not entered.

The audit's file-size heuristic is not used.

**Alternatives not taken:**
- a rolling universe (re-formed periodically): this adds entries and needs a mask;
- a formation by market capitalisation: that is not in the archive;
- a top 100: more contracts with thin early trading.

## d. The tradable mask: options and costs

The fast kernel refuses masks. **Proposed: d3, no mask; a dead contract becomes idle
capital.**
- After its death a contract has return 0, funding 0 and cost 0.
- It stays in the cross-section, and its features follow its flat price.
- Any weight on it earns nothing and costs nothing to change. That is the settled position
  after a delisting.
- Positions remain a function of X alone, so the fast kernel and the pinned ridge_stack
  both run unchanged.
- **The distortion:** books may hold dead contracts, which dilutes them. There is no
  look-ahead: a death is seen in the features only after it happens.

| option | how | cost |
|---|---|---|
| **d1** slow path with a mask | `streams_for` with `tradable` False after a death | Class pass: about 6 min per pass over the 82,240 members (measured on 128). A null pass needs the streams again, chunked, or 4.7 GB in memory, which does not fit the laptop. So roughly 10–15 min per class pricing call, against 90 s on the fast kernel. **And ridge_stack's pinned code (`learn/`, `fce5627`) has no mask:** it would trade dead contracts. A mask means changing `learn/` and breaking the pin. |
| **d2** survivors only | the contracts live through the whole window: 43 of the 50 | **Survivorship:** the 7 dead contracts (6.98% of formation volume) are removed, among them LUNA's collapse. **Bound:** at most 7 of 50 contracts, and at most 14% of the equal-weight cross-section, is affected. The bias is towards survivors' returns, with no estimate of its sign for a long-short book. |
| **d3** (proposed) idle after death | as above | No code change; fast kernel. Weights on dead contracts dilute books. |

## e. Returns and funding

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
  - **Open:** fill those bars from another archive file (the daily 4h files, or 1h
    monthly files aggregated), or carry the close as now.
- **Signals use the same total return,** price change plus funding. The alternative not
  taken is price-only signals with funding in the earned return only.

## f. Costs

- **Proposed: 10 bps one-way per unit of turnover,** charged on live contracts. It is
  **taker fee 5 bps + slippage 5 bps.** There is **no borrow term:** shorts pay or receive
  funding instead.
- **Sources, as stated assumptions:**
  - **The taker fee** is Binance's published USDⓈ-M fee schedule at the regular (VIP 0)
    tier: 0.05% taker, and it was 0.04% earlier in the window. **Not re-checked today.**
  - **The slippage** is an assumption with no measured source here. It is plausible for
    the most liquid contracts and optimistic for the thinner ones in the top 50.
- **Alternatives:**
  - a per-contract slippage from formation-month volume;
  - a sensitivity read at 5 and 20 bps.

## g. Market series

The equal-weighted average of the **live** contracts' returns, each bar. The alternative
not taken is to average all 50, with dead contracts at 0.

## h. Features: the same code, different horizons

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

## i. What may be tried

1. **The class tier:** `SubsetClass`, max_size 3, signed (82,240 members), over the 7,116
   scored rows.
2. **One ridge_stack stream:** pinned as in the confirmation, the code at `fce5627` and the
   four `learn/` blob hashes. It is priced through the supplied-streams tier on its 6,360
   scored rows.
- **The split of the 5% is left open** for the author, now that the design numbers exist
  (section k).

## j. Sealing and its limits

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

## k. Outcome-free design quantities (PROVISIONAL: unpinned build)

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

## Open choices (for the author)

1. **The mask: d3** (proposed: idle after death, fast kernel, pinned code), **d1** (slow
   path; breaks the `learn/` pin), or **d2** (survivors only, 43 contracts).
2. **The archive hole** (15 contracts; 2022-02-26 to 02-28 and 2022-04-01 to 04-02): fill
   it from another archive file, or carry the close.
3. **Relisting:** ICPUSDT (silent 108 days from 2022-06-10) and TLMUSDT (silent 294 days
   from 2022-06-09) resumed trading.
   - Proposed: dead from the silence, no re-entry.
   - Alternative: re-enter at relisting. This is observable when it happens, so there is no
     look-ahead, but it is a mask-like entry.
4. **The holdout end:** 2026-09-30 (the last monthly file), or the fetch date (daily
   files).
5. **Costs:** 10 bps one-way (taker 5 + slippage 5), or another figure, or a sensitivity
   read.
6. **The market series:** the live-contract average, or all 50.
7. **Signals:** on total return (proposed), or on price return only.
8. **The split of the 5%** between the class tier and the stream. The class tier's
   80%-power Sharpe is above 3 at every weight on this 3.25-year window (section k).
9. **The universe parameters:** top 50, October 2021 formation, full-month trading, and
   the stablecoin and index exclusions.
