# New panels: an audit of two candidate data sources, 2026-10-06 (America/Chicago). AUDIT

**Why.** The 6.5 holdout read (`0426352`) found nothing that passed: no 6.5 submission was
certified. So the gate has not yet been tested on real data where a signal clears the
bar. This audit asks whether two further real sources could supply such a test. It
reads metadata and in-sample rows only.

## The two sources, and their windows, fixed before any price is read

The windows below were fixed in this file **before any price from either source was
read**. **There is no fallback window.** If nothing certifies on these windows, that is
the result.

| source | in-sample | holdout |
|---|---|---|
| **Ken French, 49 Industry Portfolios, daily, value-weighted** (Dartmouth data library) | 2010-01-01 to 2019-12-31 | 2020-01-01 onward |
| **Binance USD-M perpetual futures**, klines (`data.binance.vision`, `futures/um`) | the start of the archive to 2025-03-31 | 2025-04-01 00:00 UTC onward |

## What this audit may read, and what it may not

**May read:**
- bucket and file listings, file names, sizes and checksum-file names;
- file headers and column layouts;
- dates and timestamps, as needed to place a row against a cut;
- **rows inside the in-sample windows**: French rows dated 2010-01-01 to 2019-12-31, and
  Binance months up to and including 2025-03.

**May not read:**
- **any row on or after a cut**: French on or after 2020-01-01, Binance on or after
  2025-04-01 00:00 UTC.
- No such row's value is printed, stored or summarised. French rows on or after the cut
  are counted only, never parsed into values.
- French rows before 2010-01-01 are simply unused.
- No Binance price file for a month on or after 2025-04 is downloaded. Listings may show
  that such files exist; their contents are not fetched.

**Also out of scope here:** no box, no agent sessions, nothing on the 6.5 holdout host.

## Exploratory: how the bar falls with class depth (item 4)

This part reads **the class null only**: the replicate maxima of the demeaned streams
on the pinned planted panel's in-sample window. No observed score is computed or
compared. It reports the 95th percentile of the null maximum for the classes of size at
most 1, at most 2 and at most 3. It is exploratory and gates nothing.
