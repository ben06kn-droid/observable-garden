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

**ARM's history.** ARM listed 2023-09; the free-tier window opens ~2024-09, so
ARM should cover it fully. **Confirm at download and record actual first and
last bar per name** — this is an assumption until the manifest says otherwise.

## Sessions

**US regular session only, 09:30–16:00 ET.** VWAP is computed from
regular-session bars only. The volume feature takes a **20-trading-day warm-up**,
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

The auction-end sensitivity readout takes the end of each name's last
`TRANSITION` bar as its boundary.

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
**XAMS, XPAR, XETR, XHEL, XSTO, XSWX** and XNYS/XNAS. tz database **2026.4**.
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
