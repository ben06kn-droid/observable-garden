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

## Draft: how each pull would split and seal its holdout, following 6.5 (item 5). Not live

**Common to both.**
- **One fetch, on a holdout host.** The host is an EC2 instance with no agent session,
  following 6.5's single-fetch design. Every downloaded file is hashed there, and a
  manifest records the source URL, size, and SHA-256 or published CHECKSUM of each one.
- **The split happens on the host**, at the cut.
  - The in-sample part is copied to the agent machine.
  - The holdout part stays on the host's volume, with an encrypted second copy made by
    the operator.
- **What an agent session can reach:** only the in-sample panel, through a loader that
  refuses any row on or after the cut, and any sealed or quarantined path, as
  `data/etf_loader.py` does for 6.5.
- **What it cannot reach:** the holdout host, the holdout files, the encrypted copy and
  its passphrase. A new loader per source is needed; the ETF loader's 2023-01-01 cut is
  hard-coded.
- **Recall, which the seal does not cover.** Both holdouts (2020 onward, and 2025-04
  onward) are in the past, and likely inside the agent model's training data. The seal
  stops the agent reading the rows; it does not stop the agent *recalling* the period.
  Asset identities and calendar dates should therefore be masked from the agent, as
  7.5 masks its labels. Whether recall still leaks through is a limit to state.

**Ken French, 49 industries, daily.**
- **What is fetched:** the zip `49_Industry_Portfolios_daily_CSV.zip`, once, on the
  host. Its SHA-256 and `Last-Modified` header go in the manifest.
- **The split:** the value-weighted block's rows 2010-01-01 to 2019-12-31 are written to
  an in-sample CSV, hashed and copied. Rows from 2020-01-01 to the last row in the file
  go to a holdout CSV, hashed and kept on the host.
  - **The holdout's end is fixed by the fetch date.** The file grows each month.
  - The other blocks (equal-weighted, sizes, firm counts) are not split out. They stay
    inside the archived zip on the host.
- **Revisions:** the library revises historical returns from time to time. The single
  fetch's hash is therefore the definition of the data, and no later re-fetch replaces
  it.
- **Market series:** `beta252` and `idvol63` need one. The Fama-French daily factors
  file (Mkt-RF plus RF) would be fetched and split in the same way.

**Binance USD-M, klines.**
- **What is fetched:** the monthly zips of the chosen universe and bar, together with
  their `.CHECKSUM` files and the funding-rate months, once, on the host. Each zip is
  verified against its CHECKSUM, and the manifest records the key, size, ETag and
  checksum.
- **The split is by month file.** Months up to 2025-03 are in-sample and are copied to
  the agent machine. Months from 2025-04 stay on the host.
  - The loader refuses any open time on or after 2025-04-01 00:00 UTC, in
    milliseconds, as the audit found.
- **The universe is chosen from in-sample months only**, and committed before any
  holdout month is fetched.
- **Delistings:** they are dated from zero-volume filler, not from the archive's last
  month, because the archive pads stopped contracts.
- **Holdout delistings** are handled in grading by a tradable mask. Grading runs on the
  slow path, which the fast kernel refuses.
