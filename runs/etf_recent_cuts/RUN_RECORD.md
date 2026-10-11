# ETF recent panel: the host fetch and cut (HOST-1 steps 2–10), run record, 2026-10-11

**The registration:** `prereg/etf-recent-panel.md`, live at `310225c`, with amendment 1
(`80ec191`).
**The sheet:** `docs/etf_recent_operator_sheets.md`, HOST-1, at G =
`04eecfc97d82d2ab2b5f8042d416a686e0c2090d`.
**The host:** `og-holdout` (`i-0886a189b85d4d051`), IP 13.58.172.90. The author reported it up at
about 11:46 CDT.
**Run by the author,** in his own terminal. The agent ran nothing on the host.

## Steps 2–8, on the host

- The author's outputs for steps 2–8 were not pasted to the agent. What the committed record
  shows about them:
  - the cut record's `registration` is `310225cd4932bc18e1c8e2e248cbbb133124a004`;
  - the fetch started at **2026-10-11T16:48:46Z**;
  - the last fetched session is **2026-10-09**;
  - `refused` is null.
- **The raw responses and `fetch.json` stay on the host.** The record carries `fetch.json`'s
  SHA-256.

## Step 9, the copy to the laptop (the author)

`scp -r og-holdout:etf_recent/insample og-holdout:etf_recent/insample.cut.json
runs/etf_recent_cuts/` copied 38 CSVs and the record.

## Step 10, the check (the agent, on the laptop)

- **Every CSV's SHA-256 equals the record's (38 of 38).** The combined SHA-256 equals the
  record's: `c79312e73bf193133660b4199840ec4cea833701b3273932a10e8c9a923fe61a`.
- The CSVs are gitignored (`runs/etf_recent_cuts/insample/`, `af7f46e`) and are not committed.
  **Only `insample.cut.json` is committed.**
- **Included: 38 of 40.** SPY, the declared market, is included (amendment 1).
  - Every included ETF has 5,033 rows (2005-01-03..2024-12-31), 0 missing sessions in
    2005–2014 and 2015–2024, and 0 null volumes in 2005–2014.
  - The lowest 2005–2014 median among those included is TIP, at 583,000.
- **Excluded by rule 2** (median share volume over 2005–2014 below 500,000), with 0 missing
  sessions:
  - **EWU**, median 438,250;
  - **IEF**, median 480,600.

  Neither lies in the narrow band where the true median and `fetch_etf.py`'s upper-middle
  element could disagree (amendment 1, b).
- **No candidate returned no data,** and none failed rule 1. Item 3 is not verified (section b).
- **Holdout rows, counted from their dates only:** 444 for every ticker (2025-01-02..2026-10-09).
  That matches the design's expected holdout length.

## The author's note on holdout fields (2026-10-11)

**Holdout fields are tokenised as text, hashed and written, and never parsed to numbers on any
machine but the host's grader.**
- The fetch writes the raw responses as received and hashes them.
- The cut tokenises each response whole, keeping numbers as their source text. It converts to
  numbers only rows dated before 2025-01-01, and counts later rows from their timestamps alone.
- No holdout field has reached the laptop. The record holds date counts only for those rows.
