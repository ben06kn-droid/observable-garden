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
Amsterdam's close lands at 16:30 UTC year-round, which is 11:30 ET in winter,
11:30 ET in summer, and **12:30 ET during the weeks when US and EU clocks
disagree**.

## The home-open boundary

**The indicator is per name and switches at the END OF CONTINUOUS TRADING**,
because live arbitrage against the home book is the mechanism, and that stops
when continuous trading stops rather than when the auction prints.

**End of closing auction is a registered sensitivity readout**, not the primary.

**Bars between a name's continuous end and its auction end are flagged
`TRANSITION` and are not traded** — in real data and in twins alike.

### Per-name boundary constants

| MIC | end of continuous | end of closing auction | read-level |
|---|---|---|---|
| XSWX | **17:20 CET** | **17:30 CET** | **primary** — six-group.com trading-hours page, fetched |
| XSTO | 17:25 local | ~17:27 local | **primary-adjacent** — Nasdaq's own Appendix 4 gives 09:00–17:25 for Swedish stock-related *derivatives*; cash equities not separately confirmed |
| XHEL | 18:25 local (= 17:25 CET) | ~18:27 local | **secondary** — aggregator |
| XAMS | 17:30 CET | 17:30 CET (auction at close) | **secondary** — Euronext's own pages link to downloadable PDFs and do not state hours inline; two fetch attempts failed |
| XPAR | 17:30 CET | 17:30 CET | **secondary**, as XAMS |
| XETR | **not verified** | **not verified** | — |

**`exchange_calendars` 4.13.2 reports a single close of 16:30 UTC for all six**,
which is the *official close* (auction end). That reconciles two apparently
conflicting facts: the six do share one official close, and they do **not** share
one continuous end. The convention above selects the boundary on which they
differ, so **per-name constants are required and a panel-wide 11:30 ET is wrong**.

Unverified cells must be resolved from primary documents **before the feature
commit**, since the indicator depends on them. Whether either constant changed
inside the two-year window is also unresolved.

## Calendars

`exchange_calendars` 4.13.2, pinned in the manifest. Coverage confirmed for
**XAMS, XPAR, XETR, XHEL, XSTO, XSWX** and XNYS/XNAS. tz database **2026.4**.
Holiday and early-close handling comes from that library, to be spot-checked
against primary sources for a sample of dates with the read-level recorded.

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

All six official closes coincide at 16:30 UTC, but the **continuous** ends do
not, so per-name boundaries carry a small amount of extra identification. **The
independent unit is therefore no longer strictly the day**, though it is much
closer to the day (~500 in the window) than to the bar. Twin construction
respects each name's own boundary and drops `TRANSITION` bars.
