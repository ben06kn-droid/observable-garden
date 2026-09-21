# 7.4 ADR testbed — universe, benchmarks, sessions and boundary convention

**Committed before any bar is opened.** This file fixes what will be downloaded
and how sessions are defined. It does **not** fix the feature list, which is a
separate commit and a separate approval; `data/` code refuses to build features
until that commit is an ancestor of HEAD. Until then: row counts and date ranges
only.

No novelty is claimed for anything here.

## Universe

Nine names. Six with a real home market, three without — the three are a
**separate placebo control panel**, never searched by the agent, graded offline.

| ticker | company | home market | MIC | US listing | benchmark ETF | panel |
|---|---|---|---|---|---|---|
| ASML | ASML Holding | Euronext Amsterdam | XAMS | Nasdaq | SOXX | treated |
| SAP | SAP SE | Xetra | XETR | NYSE | XLK | treated |
| STM | STMicroelectronics | Euronext Paris | XPAR | NYSE | SOXX | treated |
| NOK | Nokia | Nasdaq Helsinki | XHEL | NYSE | XLK | treated |
| ERIC | Ericsson | Nasdaq Stockholm | XSTO | Nasdaq | XLK | treated |
| LOGI | Logitech | SIX Swiss | XSWX | Nasdaq | XLK | treated |
| ARM | Arm Holdings | none | — | Nasdaq | SOXX | **control** |
| NXPI | NXP Semiconductors | none | — | Nasdaq | SOXX | **control** |
| SPOT | Spotify | none | — | NYSE | **XLC** | **control** |

**Benchmark mapping**, to be checked at the feature commit: `SOXX` for
semiconductor exposure, `XLK` for broad technology. **`SPOT` is the awkward
one** — it is classified Communication Services, not Technology, so `XLK` does
not hold it and `XLC` is the honest match. That makes three benchmark series
rather than two. Flagged rather than smoothed over; overridable before the
feature commit.

**SOXX self-weight (recorded 2026-09-21).** SOXX holds **ASML at 2.33%** and
**NXPI at 3.15%**, as of 2026-09-17. **Read-level: secondary**
(stockanalysis.com, data from Finnhub), because iShares' own holdings file is
not served to scripted requests. STM and ARM are not among the 25 listed of 34
holdings, so each is at most 1.00% if held at all. "Own return minus SOXX" for
ASML and NXPI therefore carries a small self-weight, and possibly STM and ARM
too. **Recorded, not corrected.**

**Download list:** the nine names above plus `SOXX`, `XLK`, `XLC`.

### Amendment, 2026-09-21: the registered fallback is invoked

Decided before any bar is opened, on power rather than on data: six names make a
noisy dollar-neutral book. ROADMAP 7.4's registered widening is invoked. **The
treated panel is now the six tech names plus the twelve EU large caps (18
names)**, with the six tech names kept as a **sub-panel**, reported as a readout
and never separately certified. **The control panel is unchanged** (ARM, NXPI,
SPOT).

| ticker | company | home market | MIC | benchmark ETF | sub-panel |
|---|---|---|---|---|---|
| NVS | Novartis | SIX Swiss | XSWX | XLV | large-cap |
| AZN | AstraZeneca | London | XLON | XLV | large-cap |
| SNY | Sanofi | Euronext Paris | XPAR | XLV | large-cap |
| NVO | Novo Nordisk | Nasdaq Copenhagen | XCSE | XLV | large-cap |
| HSBC | HSBC Holdings | London | XLON | XLF | large-cap |
| BCS | Barclays | London | XLON | XLF | large-cap |
| UL | Unilever | London | XLON | XLP | large-cap |
| DEO | Diageo | London | XLON | XLP | large-cap |
| TTE | TotalEnergies | Euronext Paris | XPAR | XLE | large-cap |
| SHEL | Shell | London | XLON | XLE | large-cap |
| BP | BP | London | XLON | XLE | large-cap |
| RIO | Rio Tinto | London | XLON | XLB | large-cap |

**Home market is the venue open during US hours.** HSBC's Hong Kong line and
RIO's Sydney line are closed throughout the US session; AZN's Stockholm, and
UL's and SHEL's Amsterdam, lines are secondary. **Benchmark** is the Select Sector
SPDR for each name's sector (XLV, XLF, XLP, XLE, XLB), downloaded 2026-09-21 into
`data/adr_fallback_manifest.json` beside the twelve names.

**To verify before features are built, not assumed:** whether any of the
eighteen changed its US listing structure or ADR ratio inside the window. AZN
and TTE are the names to check first; each depositary's notices and the vendor's
splits endpoint are the sources. A ratio change that `adjusted=true` does not
absorb is a price-level break, and would be handled as a registered exclusion,
not smoothed.

**Found 2026-09-21 from the vendor's splits endpoint** (metadata only, in the
manifests): **AZN, 2026-02-02, split 2 → 1**, which is consistent with the ADR
(one ADR = half a share) becoming an ordinary-share line; **UL, 2025-12-09,
9 → 8**. None for the other sixteen, TTE included. Whether `adjusted=true`
absorbs both events cleanly, and whether TTE had an unrecorded change, is
checked by hand against the depositary notices when the features are built.

**AZN and TTE, verified 2026-09-21 from the companies' own announcements** (still
before any bar is opened):

- **AZN: depositary receipt to direct listing, inside the window.** The Nasdaq
  ADSs represented ordinary shares "on a two-for-one basis" and ceased trading
  30 January 2026. Ordinary shares began trading on the NYSE on Monday 2 February
  2026, same ticker (AstraZeneca press release, "AstraZeneca to complete direct
  listing of ordinary shares … on the New York Stock Exchange"). **The vendor
  covers the price step:** its split record, 2026-02-02 at 2 → 1, matches the
  ratio and the date, and `adjusted=true` applies split records. Whether the
  vendor also adjusts **volume** is not documented. So **AZN's relative-volume
  feature is registered as missing for the 20 sessions from 2026-02-02** (its
  look-back crosses the change), unless the build-time check shows volume is
  adjusted. The venue also changed from Nasdaq to NYSE, which the consolidated
  aggregates do not separate.
- **TTE: depositary receipt to ordinary share, inside the window, at one for
  one.** The ADR program terminated and every ADR was converted into one
  NYSE-listed ordinary share on 8 December 2025, same ticker (TotalEnergies
  press release of that date). A one-for-one conversion creates no price-level
  step, which is consistent with the vendor recording no split. **No adjustment
  is needed.** One cost consequence is recorded rather than resolved:
  TotalEnergies' ADR-holder FAQ states that its NYSE-traded shares are within
  the French financial transaction tax. The flat-overnight book holds no
  end-of-day position; whether that takes it outside the tax is **not verified**,
  and the cost model does not charge it.
- **UL's 2025-12-09 record (9 → 8) is the 8-for-9 share consolidation**, which
  followed the Magnum Ice Cream demerger of 8 December 2025. Verified and handled
  in `prereg/adr-features.md` amendment 1, A4.

**Placebo limitation.** All three controls are technology names (two
semiconductors and SPOT), while twelve of the eighteen treated names are not
tech. So the placebo panel matches the **tech sub-panel** in sector, not the
treated panel as a whole. A home-close "effect" found on the large caps and
absent on the controls cannot separate the mechanism from sector. **The
like-for-like placebo comparison is tech sub-panel against controls.** The large
caps have **no placebo of their own**; for them the within-name falsification
readouts (clock-mismatch weeks, home holidays, home early closes) are the only
check. Three control names also make a very noisy dollar-neutral book, so a null
placebo result is weak evidence either way.

**ARM's history.** ARM listed 2023-09; the free-tier window opens ~2024-09, so
ARM should cover it fully. **Confirm at download and record actual first and
last bar per name** — this is an assumption until the manifest says otherwise.

## Sessions

**US regular session, 09:35–15:55 ET traded; first and last bars dropped**
(amended 2026-09-21 from 09:30–16:00, to match ROADMAP 7.4; decided before any
bar is opened). The 09:30 and 15:55 bars are not traded and carry no return, but
their prices and volumes enter the features: VWAP and the volume profile use
every regular-session bar from 09:30. **Flat overnight**, and the first traded
bar's return is measured from its own open; see `prereg/adr-features.md`. The volume feature takes a **20-trading-day warm-up**,
so the first 20 sessions of the window carry no volume feature and are excluded
from scoring rather than filled.

**Everything is computed in UTC** from `zoneinfo`, never from an assumed ET or
CET offset. DST rules are not hand-verified; they come from the tz database, and
its version is pinned in the download manifest. Verified empirically: Euronext
Amsterdam's continuous end is 17:30 local, which is 16:30 UTC in winter and 15:30
UTC in summer, and so 11:30 ET in winter, 11:30 ET in summer, and **12:30 ET during the weeks when US and EU clocks
disagree**.

## The home-open boundary

**The indicator is per name and switches at the END OF CONTINUOUS TRADING**,
because live arbitrage against the home book is the mechanism, and that stops
when continuous trading stops rather than when the auction prints.

**End of closing auction is a registered sensitivity readout**, not the primary.

**Bars between a name's continuous end and its auction end are flagged
`TRANSITION` and are not traded** — in real data and in twins alike. **Where the
auction end is randomised past a bar boundary (XAMS, XPAR, XETR), the following
bar is `TRANSITION` too**, so the uncross can never land in a traded bar.

### Per-name boundary constants

| MIC | end of continuous | end of closing auction | read-level |
|---|---|---|---|
| XSWX | **17:20 CET** | **17:30 CET** | **primary** — six-group.com trading-hours page, fetched |
| XSTO | **17:25 CET** | **17:30 CET**, uncross random in the last 30 s | **primary** — Nasdaq European Markets trading-hours page, Main Market *Equities* row (09:00–17:30) and its note: last five minutes no matching, final uncross random in the last 30 s |
| XHEL | **18:25 EET** (= 17:25 CET) | **18:30 EET**, as XSTO | **primary** — same Nasdaq page, Helsinki Equities row (10:00–18:30) |
| XAMS | **17:30 CET** | **17:35 CET, random end**; Trading-at-Last 17:35–17:40 | **primary** — Euronext *Appendix to Trading Manual 4-01* (xlsx, euronext.com/en/media/1927/download), group J0 "Equities AEX": continuous 09:00–17:30, CA 17:35 random, TAL 17:35–17:40 |
| XPAR | **17:30 CET** | **17:35 CET, random end**; TAL 17:35–17:40 | **primary** — same appendix, groups F1/F2 "Equities CAC40": identical times |
| XETR | **17:30 CET** | **17:35 CET earliest, random end** (plus any volatility interruption); Trade-at-Close to 17:40 | **primary** — Deutsche Börse cash-market trading-hours page ("Trading on Xetra takes place … from 9 until 17:30 CET"); Xetra Trade-at-Close factsheet, data as of July 2026 (closing auction ends 17:35 CET, randomized) |
| XLON | **16:30 UK** | **16:35 UK at the earliest, random end**; price-monitoring extensions can run to 16:49 at the latest; then the Closing Price Crossing session at the auction price | **primary** — LSE, *Exchange Traded Funds: Introducing and Operating ETFs in the UK* (Feb 2024): the order book is continuous "until the start of the closing auction at 16:30", which "runs from 16:30 until at least 16:35", with the uncross "dependent on random end times and price monitoring periods" and "the latest possible time of uncrossing is 16:49". The guide's subject is ETFs on the order book; the same timings are in LSE's *Market Close ceremony* note (2019: auction launched at 16:30, trades executed at 16:35), and the mechanism is in *MIT201* 15.8 (random period before the uncross, CPX after). The Business Parameters workbook itself was not obtained |
| XCSE | **16:55 CET** | **17:00 CET**, uncross random in the last 30 s | **primary** — Nasdaq European Markets page, Copenhagen Equities row (09:00–17:00) and the same last-five-minutes note as XSTO |

In US time, from `zoneinfo` at tz 2026.4 (continuous / auction end, ET): XSWX
11:20 / 11:30; XSTO and XHEL 11:25 / 11:30; XAMS, XPAR, XETR 11:30 / 11:35 —
each one hour later during the clock-mismatch weeks.

**`TRANSITION` bars at 5 minutes, per name:**

| name | MIC | `TRANSITION` (ET) | mismatch weeks (ET) | bars | why |
|---|---|---|---|---|---|
| LOGI | XSWX | 11:20–11:30 | 12:20–12:30 | 2 | continuous end to auction end |
| ERIC | XSTO | 11:25–11:30 | 12:25–12:30 | 1 | uncross is random within the final 30 s *before* 11:30, so it stays inside the bar |
| NOK | XHEL | 11:25–11:30 | 12:25–12:30 | 1 | as XSTO |
| ASML | XAMS | 11:30–11:40 | 12:30–12:40 | 2 | auction end randomised past 11:35, so the 11:35–11:40 bar is flagged too |
| STM | XPAR | 11:30–11:40 | 12:30–12:40 | 2 | as XAMS |
| SAP | XETR | 11:30–11:40 | 12:30–12:40 | 2 | 11:35 is the *earliest* auction end, plus any volatility interruption |
| NVS | XSWX | 11:20–11:30 | 12:20–12:30 | 2 | as LOGI |
| SNY, TTE | XPAR | 11:30–11:40 | 12:30–12:40 | 2 | as STM |
| AZN, HSBC, BCS, UL, DEO, SHEL, BP, RIO | XLON | 11:30–11:40 | 12:30–12:40 | 2 | the auction runs until *at least* 16:35 with a random end, so the next bar is flagged too |
| NVO | XCSE | 10:55–11:00 | 11:55–12:00 | 1 | uncross in the final 30 s before 17:00, as XSTO |

The auction-end sensitivity readout takes the end of each name's last
`TRANSITION` bar as its boundary.

**Known residue.** A price-monitoring extension (London, up to 16:49) or a
volatility interruption (Xetra) can push an uncross past the second
`TRANSITION` bar. This is rare, is not flagged per day, and the two-bar rule
stands.

**Post-auction phases are not price discovery.** Euronext's Trading-at-Last
(17:35–17:40 CET) and Xetra's Trade-at-Close (to 17:40 CET) match only at the
closing-auction price. They are recorded as post-auction phases: the home book
is closed for price discovery once the auction has printed, and neither phase
moves either boundary.

**`exchange_calendars` 4.13.2 reports one close for all six: 17:30 CET/CEST
(16:30 UTC in winter, 15:30 UTC in summer; an earlier draft wrongly said 16:30 UTC
year-round).**
That is **not** one kind of close: it is the *auction end* for XSWX, XSTO and
XHEL, and the *continuous end* for XAMS, XPAR and XETR, whose auctions run to
17:35 CET. (The earlier draft of this file called it the official close for all
six; the primary documents above contradict that for the three Euronext/Xetra
names.) Either way the six do not share one continuous end, so **per-name
constants are required and a panel-wide 11:30 ET is wrong**.

**The constants are assumed fixed across the window.** `exchange_calendars`
4.13.2 encodes one close time for each of the six, with no change inside
2024-09-23 to 2026-09-18, and no dated primary source for the continuous or
auction ends was found. Every source above is a current document, so today's
constants apply throughout by assumption, not by verification.

## Calendars

`exchange_calendars` 4.13.2, pinned in the manifest. Coverage confirmed for
**XAMS, XPAR, XETR, XHEL, XSTO, XSWX, XLON, XCSE** and XNYS/XNAS. tz database **2026.4**.
Holiday and early-close handling comes from that library, spot-checked against
primary sources with the read-level recorded.

**Early closes in the window, 2024-09-23 to 2026-09-18, per exchange:**

| MIC | from `exchange_calendars` | primary spot-check | read-level |
|---|---|---|---|
| XAMS, XPAR | 14:05 CET on 24 and 31 Dec 2024 and 2025 (4 days each) | Euronext trading-hours page: cash markets "close by 14:05 CET" on half days (wording from its 2021 year-end notice); 24 and 31 Dec 2026 listed as half days | primary, but the 2024–25 year-end appendices were not fetched |
| XETR | shut 24 and 31 Dec; **14:00 CET on 30 Dec 2024 and 2025** | Deutsche Börse's non-trading-day list confirms 24 and 31 Dec closed; for 30 Dec it says only that deviating hours may apply, set by circular | closures primary; **30 Dec time unverified** |
| XSTO | 13:00 CET half days, 9 in the window (2024-11-01, 2025-04-17, 2025-04-30, 2025-05-28, 2025-10-31, 2026-01-05, 2026-04-02, 2026-04-30, 2026-05-13) | Nasdaq's page lists 2026 half days Jan 5, Apr 2, Apr 30, May 13 — matches; half-day equities 09:00–13:00 | dates primary for 2026; **continuous end on half days (presumably 12:55) unverified** |
| XHEL | none | Nasdaq's page lists no Helsinki half days | primary |
| XSWX | none; shut 24 and 31 Dec | not spot-checked against SIX | library only |
| XLON | 12:30 UK on 24 and 31 Dec 2024 and 2025 (4 days) | not spot-checked | library only |
| XCSE | none | Nasdaq's 2026 Copenhagen closure list matches the library's closed days | primary for 2026 |

## Secondary falsification readouts — counted, not estimated

Measured on XAMS against XNYS over 2024-09-01 to 2026-09-01, 495 common
sessions:

| readout | sessions | prediction |
|---|---|---|
| **clock-mismatch** (home close at 12:30 ET) | **40** | a home-close effect moves with the true close; a US time-of-day effect does not |
| **home holidays** (US open, home market shut) | **6** | the ADR behaves as home-closed for the whole session |
| **home early closes** (24 and 31 Dec, close 08:05 ET) | **4** | the boundary moves to the early close |

**All three have low power** and are registered as secondary. 40 sessions is the
largest and is the only one with any real chance of separating the mechanism
from a US time-of-day effect; 6 and 4 are close to anecdote and are reported as
such.

## Independent units

The six continuous ends fall at 17:20, 17:25 and 17:30 CET and the auction ends
at 17:30 and 17:35 CET, so neither set coincides, and per-name boundaries carry a
small amount of extra identification. **The
independent unit is therefore no longer strictly the day**, though it is much
closer to the day (~500 in the window) than to the bar. Twin construction
respects each name's own boundary and drops `TRANSITION` bars.

## Deviation: where the correcting commit's content landed

The correction of 2ea8574's close times was meant to be one commit on its own.
Most of it landed inside **2dd4473** ("add an optional class cap to MetaAdaptive,
…"), an unrelated commit that swept up the uncommitted edit to this file. That
part covers the primary-source close times, the per-name exchange_calendars
reading and the 17:30-local correction. **0a5a15a** carries the rest: two
`TRANSITION` bars for XAMS, XPAR and XETR, and the post-auction phases. The
pushed history was not rewritten; the download manifest records all three
hashes.
