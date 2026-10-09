# French 49 industries, the long history: DRAFT, NOT LIVE

**Status: DRAFT, NOT LIVE (2026-10-09, America/Chicago).** It is committed for the author's
reading, and nothing in it binds.
- **No value before 2008-12-29 has been read.** The rows before 2008-12-29 in the registered
  file (`prereg/french-panel.md`, section a) were counted from their date field only.
- No box, host or agent has been used for it.
- It uses the **recency-weighted certificate**
  (`prereg/recency-weight-exploratory-2026-10-09.md`, amendment 1 at `190d75e`). That
  statistic is still under validation (`prereg/recency-weight-planted.md`, not run).
  **This draft cannot go live before that validation is read.**

Points needing the author are marked [AUTHOR].

## a. Data, and the missing-value counts

- **The same source file as `prereg/french-panel.md`:** the zip with SHA-256
  `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de`, the value-weighted
  daily block. Its rows run from 1926-07-01.
- **The zip is on the holdout host only.** It was moved there and deleted from the laptop
  for the French holdout grading (ZIP-DELETE, `a415bde`). So the counts below need a step
  on the host.
- **Item a, before any value is read: COUNTS ONLY.** `data/count_french_missing.py`
  (`f58a97a`, tested on synthetic text) produces:
  - the number of missing-value flags (−99.99 or −999) per industry per year, for the rows
    before 2008-12-29;
  - the first date on which all 49 industries are present;
  - for each industry, the first date after which it has no gap.

  It compares each cell with the two codes and nothing else. Rows from 2008-12-29 are
  skipped by their date field before any value is parsed.
- **[AUTHOR] Where the count runs.** Proposed: on the holdout host, by the author, on the
  author's go. Only the JSON of counts comes back to the laptop. The commands:

  ```
  # [H] on the holdout host, at the repository
  .venv-grading/bin/python -m data.count_french_missing --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip \
      --out ~/french_missing_counts.json
  # [L] on the laptop
  scp HOST:~/french_missing_counts.json runs/french_long_counts/
  ```

  The alternative is a fresh fetch on the laptop. That would be a different, revised file,
  and it would put the 1990–1995 and 2020+ rows on the laptop, which custody (section e)
  forbids.
- **The start date and the rule for late industries: proposed only after the counts.**
  [AUTHOR] The two candidates to decide between:
  - **(i)** start on the first date all 49 are present. The panel is balanced, but it
    starts later.
  - **(ii)** start 1926-07-01, with each industry entering on the first date after which
    it has no gap. Its features are NaN, which maps to 0 as for a dead Binance contract,
    until it has a full 253-row warm-up. It is never in a book before then.
- The design numbers (section f) barely depend on this choice under the weights (section f).

## b. The two reads

- **B1, first:**
  - in-sample: the start date to 1989-12-31;
  - graded on 1990-01-01 to 1995-12-31 (6 years).
- **B2, second, and only after B1 is graded and its grading committed:**
  - in-sample: the start date to 2019-12-31;
  - graded on the existing holdout, 2020-01-01 to the last row of the registered zip.
  - **Disclosed in B2:** the 2020+ window was opened once before, to grade ridge_stack and
    class member 2937 (`a415bde`). Its realised returns for those two objects are known. B2's
    grading is therefore not blind to that window's general behaviour.
- The 2009–2019 rows were read for `prereg/french-panel.md`. B1 does not include them.
  B2 does, and says so.

## c. What each read tests

**Each read, the same structure:**
1. **Sancho** (version 2, as confirmed at `97d2519`: base view, M2, G3, L {1, 3, 10, 30})
   as one supplied stream, at **d = 1**: the French panel's registered timing (signal at the
   close of t, held from the close of t+1 to the close of t+2).
2. **The class tier:** `SubsetClass`, max_size 3, signed, 82,240 members.
3. **A second stream: Sancho at d = 0, labelled NOT IMPLEMENTABLE.** Signal at the close
   of t, earning t to t+1, filled at that close. Industry portfolios cannot be traded at
   their own closing price, so it can never be acted on. It shows how much of the result
   depends on immediacy. It has its own share of the level, and is never reported without
   its label.

**The statistic:** the recency-weighted Sharpe, h = 1,260 rows, the fixed centring.
Reported for each test:
- p, at both levels;
- L90 (weighted);
- the performance line: the unweighted net Sharpe over the last 252 and 756 rows, with 90%
  intervals; descriptive only.

**The split (proposed; [AUTHOR]):**

| test | 96% level | 90% level |
|---|---|---|
| Sancho stream, d = 1 | p < 0.03 | p < 0.06 |
| Sancho stream, d = 0, NOT IMPLEMENTABLE | p < 0.01 | p < 0.02 |
| class tier | p < 0.01 | p < 0.02 |
| family-wise | ≤ 5% | ≤ 10% |

**Why this split:**
- The class keeps its French weight.
- The d = 0 stream's share comes out of the stream's 0.04. Its certificate could not be
  acted on, so it gets the smaller share.
- The cost to the d = 1 stream, from 0.04 to 0.03: its weighted net floor at 80% power
  rises from 0.67 to 0.71 at 64 years, and from 0.69 to 0.72 at 94 (section f).

## d. Costs

- **As the French panel:** 5 bps one-way per unit of turnover, and 50 bps a year borrow on
  shorts. **An assumption.**
- **Limit, repeated:** industry portfolios are not tradable instruments. On pre-1990 data,
  5 bps is a paper assumption. Actual costs were far higher for most of that history, and
  are not modelled. No claim about implementable returns rests on these costs.

## e. Custody

**[AUTHOR] Proposed, for B1:**
- **Before B1's in-sample read is committed, no row after 1989-12-31 reaches the laptop.**
  - On the holdout host, a split script cuts the B1 in-sample CSV (the start date to
    1989-12-31) from the registered zip. It refuses any row after 1989-12-31, and records
    the CSV's SHA-256 and row count.
  - Only that CSV is copied to the laptop.
- **The B1 grading (1990–1995) runs on the holdout host,** by the author, after B1's
  in-sample read is committed, with no-restart checks as in the French grading (`4f11f95`).
- **For B2:** after B1's grading is committed, the host cuts the 1990-01-01 to 2008-12-26
  rows, with the same refusal past 2019-12-31. The 2009–2019 rows are already on the
  laptop. The 2020+ rows stay on the host, and B2 is graded there.
- **The default the author named** (a fetch script that refuses any row after 1989-12-31
  until B1's commit exists) is this, applied to the registered zip on the host rather than
  to a new fetch. A new fetch would be a revised file with a different hash.

## f. Design numbers by simulation

**Source:** `experiments/french_long_design.py`, committed before its run at `f58a97a`;
output `runs/french_long_design/2026-10-09` (`6549253`).
- **Method:** the French 2009–2019 in-sample panel (read already) supplies only its
  dependence. Gross streams, demeaned so that every null is exact, are row-resampled to each
  candidate length.
- **Replicates:** B = 2,000, seeds 708000–708999.
- **Stream bars:** the mean over 5 panels (a pool base column as the stream), with iid
  normal beside.
- **Class bars:** the mean over 3 panels of the weighted class maximum's null.
- **Power:** net Sharpe at 80% power by Lo's iid formula, over the weighted effective years
  (weighted) or the window's years (unweighted).
- **Not computed:** no realised mean, Sharpe or p-value.

**B1 is about 64 years if it starts 1926-07; B2 about 94.**

| length (weighted effective years) | test, alpha | weighted bar → net 80% | unweighted bar → net 80% |
|---|---|---|---|
| 64 y (14.4) | stream d = 1, 0.03 | 0.490 → **0.711** | 0.236 → 0.341 |
| | stream d = 1, 0.06 (90%) | 0.401 → 0.623 | 0.197 → 0.303 |
| | stream d = 0, 0.01 | 0.604 → 0.826 | 0.293 → 0.398 |
| | stream d = 0, 0.02 (90%) | 0.536 → 0.757 | 0.258 → 0.363 |
| | class, 0.01 | 1.176 → **1.398** | — |
| | class, 0.02 (90%) | 1.118 → 1.340 | — |
| 94 y (14.4) | stream d = 1, 0.03 | 0.503 → **0.724** | 0.191 → 0.278 |
| | stream d = 1, 0.06 (90%) | 0.423 → 0.645 | 0.159 → 0.246 |
| | stream d = 0, 0.01 | 0.615 → 0.837 | 0.236 → 0.322 |
| | stream d = 0, 0.02 (90%) | 0.547 → 0.768 | 0.207 → 0.294 |
| | class, 0.01 | 1.197 → **1.419** | — |
| | class, 0.02 (90%) | 1.130 → 1.352 | — |

The 20- and 40-year rows (for a later start) are in the output. Weighted, the d = 1
stream's net floor is 0.75 at 20 years and 0.72 at 40.

**What these numbers say:**
- **The weighted floor stops falling after about 40 years.** The effective length saturates
  at 14.4 years, so a 94-year history certifies no smaller an edge than a 40-year one.
- **Against the unweighted statistic, the weights roughly double the floor on long
  histories:** 0.72 against 0.34 at 64 years, and 0.72 against 0.28 at 94. **This is the
  weights' stated cost**, measured here. It is much larger than at French's 10 years.
  - [AUTHOR] Whether the weighted statistic is still wanted for these reads, given that.
    Both statistics could be reported, with the certificate on one, registered in advance.
- **The class floor is about 1.40 at 96%.** That is lower than French 2009–2019's 1.85
  (unweighted, 10 years) and roughly flat across lengths.
- **Bars from the pool's dependence and from iid returns agree** within about 0.03.

**Sancho's runtime on the long panel** (an estimate, scaled from the measured Binance fits;
not measured on this panel):
- One fit (two memories), 49 industries:
  - B1, about 64 years: rolling 756 about 2 min, expanding about 14 min, **about 16 min**;
  - B2, about 94 years: about 3 and 29 min, **about 32 min**.
- The expanding memory's cost grows with the square of the length. Each refit trains on
  all rows so far.
- **A read** is the repeat (two fits) at d = 1 and at d = 0, so four fits:
  - laptop: about 1.1 h for B1 and 2.2 h for B2, one fit at a time. About 2 GB per fit, so
    two at once at most on 8 GB;
  - box: the four fits in parallel, each about 1.7× slower per core: about 27 min for B1
    and 55 min for B2 of run. No gain beyond 4 workers.
- **The class tier:** about 30 s per weighted null at these lengths (measured above, B 2,000),
  plus building the fast kernel's tables for the long panel.
  - [AUTHOR] At 94 years that table is 82,240 × 23,688 × 2 × 8 bytes = 31 GB. It does not fit
    the laptop; it fits the box's disk. The planted runner's aggregation to pool rows does
    not apply to a real panel, whose rows are not drawn from a pool. So the class tier on
    B2 is a box job, or needs a streaming variant of the kernel.

## g. Both branches, for each read and each test

- **Certified, and the bound held on the graded window:** "certified in-sample under the
  recency weights at the registered weight (96% level, or 90% level, so labelled); its
  weighted lower bound held on [the graded window]."
- **Certified, and the bound did not hold:** "certified in-sample …; its weighted lower bound
  did not hold on [the graded window] (realised … < bound …)."
- **Refused:** "refused; consistent with the registered detection floor." The grading still
  grades it, as on French.
- **The d = 0 stream,** in every branch, carries "NOT IMPLEMENTABLE".

## [AUTHOR] points

1. **Where the missing-value count runs** (proposed: the holdout host, by the author).
2. **The start date and the rule for late industries,** after the counts.
3. **The three-way split** of the 5% and of the 10%.
4. **Custody:** the host-side split for B1, and the order for B2.
5. **Whether the weighted statistic is still wanted for these reads,** given its cost on long
   histories (section f), or both statistics with the certificate on one.
6. **The class tier on B2:** the box, or a streaming kernel.
7. **This draft cannot go live before the recency planted validation is read.**
