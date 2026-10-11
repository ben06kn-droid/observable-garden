# French 49 industries, the long history: a registration

**Status: LIVE, 2026-10-11 (America/Chicago).**
- The author read the draft at `653a400` and confirmed its answers. The additions of section j
  were made at `aaa0864`.
- This status was then set in a commit touching only this file.
- Amendments are append-only and dated.
- **Not yet set:** `REGISTRATION` in `data/french_long_split.py` and
  `experiments/french_long_read.py`. It is set to this commit by the following commit, and
  both scripts refuse to run until it is.
- **No value before 2008-12-29 has been read.** Rows before 2008-12-29 in the registered file
  were counted from their date field only.
- **Nothing has run on the box or the host for it.**
- **Recorded:** the recency validation, round 2, read at `4fb8b73`: "W2 is ADOPTED for
  weighted reads". The first draft's point 7 (that this draft could not go live before that
  validation was read) is satisfied.

The points that remained for the author are listed at the end, with how each was settled.

## a. Data, start date, entry

- **The same registered file as `prereg/french-panel.md`:** the zip with SHA-256
  `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de`, the value-weighted daily
  block. It is on the holdout host only.
- **The start: 1926-07-01, with rule (ii)** (author's answer 1):
  - each industry enters on the first date after which it has no missing value within the
    read's window;
  - from then on it feeds the market series and its own signals;
  - **it is in no book until its 253-row warm-up is complete.** Until then its features are
    0, its earned return is 0 and trading it costs nothing, so a weight a demeaned book
    places on it earns and costs nothing (`environments/french_long_panel.py`, `805f72a`).
  - **The market series** is the equal-weighted average of the industries that have entered.
- **The missing-value count is no longer a step before going live** (author's answer 1). The
  host cut computes and reports it with each cut: counts only, as JSON, with each industry's
  entry date (section e).

## b. The two reads

- **B1, first:**
  - in-sample: 1926-07-01 to 1989-12-31, about 63.5 years and 16,000 rows;
  - graded on 1990-01-01 to 1995-12-31.
- **B2, second, and only after B1 is graded and its grading committed:**
  - in-sample: 1926-07-01 to 2019-12-31, about 93.5 years and 23,560 rows;
  - graded on the existing 2020+ holdout.
  - **Disclosed in B2:** the 2020+ window was opened once before, to grade ridge_stack and
    class member 2937 (`a415bde`).
- The 2009–2019 rows were read for `prereg/french-panel.md`. B2 includes them and says so.

## c. What each read tests, and the certificate

**The certificate is on the WEIGHTED statistic under W2** (author's answer 4), h = 1,260 rows:
- block starts are drawn with probability ∝ w²;
- the first start is drawn from q, the exact stationary marginal;
- each stream is centred by its q-weighted mean;
- weights attach to position.

The definitions are `prereg/recency-weight-exploratory-2026-10-09.md`,
`prereg/recency-weight-planted-2.md` and `estimator/recency.py`.

**Three tests per read:**

| test | 96% level | 90% level |
|---|---|---|
| 1. Sancho (version 2, as confirmed at `97d2519`), one supplied stream, **d = 1** (the French timing) | p < 0.03 | p < 0.06 |
| 2. Sancho, **d = 0, NOT IMPLEMENTABLE** | p < 0.01 | p < 0.02 |
| 3. the class tier, 82,240 members, at d = 1 | p < 0.01 | p < 0.02 |
| family-wise | ≤ 5% | ≤ 10% |

The split was confirmed by the author (answer 2).

**Sancho on this panel:**
- the base view (P and X; this panel has no volume or funding), h 5, market neutrality,
  regime always;
- M2 (rolling 756 and expanding), G3, L {1, 3, 10, 30};
- positions zero on every row whose earned day is not eligible, applied after the model;
  learn2 is untouched.

**Printed for each test:**
- the weighted net Sharpe, p, and both levels' verdicts;
- the weighted L90, from the W2 null;
- **beside it:** the UNWEIGHTED statistic, its p and its L90, labelled "unweighted,
  descriptive, not the certificate". No level is spent on it.
- **for the streams, the performance line:** the unweighted net Sharpe over the last 252
  and 756 scored rows, with 90% intervals. Descriptive; it never gates.
- **block length:** the registered rule (the class rule on the base columns over the whole
  in-sample window), with the Politis–White median on the last n_eff rows recorded beside it.
- **for the class,** the best member under the weights, and the unweighted best member
  beside it.

**The validation's limits, stated beside the certificate wording** (and printed by the reader):
- W2's size is checked by simulation, on four null shapes (stationary, a volatility shift,
  and dependence added to the recent or to the old rows), **not proved**;
- **overshoots of about 10% are not reliably detected** (amendment `8a23368`'s tables: a
  stream rate of 0.05 against the 4% level is caught with probability 0.35 at n = 2,000 and
  0.17 at n = 1,000);
- **the class checks are weak** against small inflations (0.38 at 1.5× the level, n = 2,000).

## d. Costs

- **As the French panel:** 5 bps one-way per unit of turnover, and 50 bps a year borrow on
  shorts. Charged only on eligible industries. **An assumption.**
- **Limit, repeated:** industry portfolios are not tradable instruments. On pre-1990 data,
  5 bps is a paper assumption. Actual costs were far higher for most of that history, and are
  not modelled. No claim about implementable returns rests on them.

## e. Custody (author's answer 3)

- **Every cut is made on the holdout host,** by the author, from the registered zip.
  - `data/french_long_split.py` (tested on synthetic text) refuses to run until this
    registration is live, and refuses a zip with any other SHA-256.
  - It never writes a row outside its window: rows past the window are skipped by their date
    field before any value is parsed.
  - It writes, with each cut, a record: the CSV's SHA-256, row count and first and last
    dates, the missing-value counts per industry per year, the first date all 49 are
    present, and each industry's entry date by rule (ii). No value is printed.
- **The cuts:**
  - `b1`: 1926-07-01 to 1989-12-31. Copied to the laptop and the box for B1.
  - `b1-holdout`: 1990-01-01 to 1995-12-31. Stays on the host; B1 is graded there.
  - `b2-extra`: 1990-01-01 to 2008-12-26. Cut and copied **only after B1's grading is
    committed**.
- **B2's graded window** is the existing 2020+ holdout CSV on the host, and B2 is graded there.
- **Each grading** runs on the host, by the author, under a grading registration written after
  its in-sample read is committed, with no-restart checks as in the French grading (`4f11f95`).

## f. Design numbers by simulation, under W2

**Source:** `experiments/french_long_design_w2.py`, committed before its run at `1a0d712`;
output `runs/french_long_design_w2/2026-10-11` (`a2720e9`).
- **Method:** the already-read 2009–2019 French pool supplies only its dependence. Gross
  streams, demeaned so that every null is exact, are row-resampled to B1's and B2's lengths.
- **Replicates:** B 2,000; seeds 716000–716999.
- **Stream bars:** the mean of 5 panels. **Class bars:** the mean of 3.
- **Power:** net Sharpe at 80% power by Lo's iid formula, over the weighted effective years
  (14.4).
- **Not computed:** no realised mean, Sharpe or p-value.

| test, level (alpha) | B1, 16,000 rows: W2 bar → net 80% | B2, 23,560 rows: W2 bar → net 80% |
|---|---|---|
| stream d = 1, 96% (0.03) | 0.493 → **0.715** | 0.502 → **0.724** |
| stream d = 1, 90% (0.06) | 0.405 → 0.626 | 0.416 → 0.638 |
| stream d = 0 NOT IMPLEMENTABLE, 96% (0.01) | 0.611 → 0.833 | 0.626 → 0.848 |
| stream d = 0 NOT IMPLEMENTABLE, 90% (0.02) | 0.540 → 0.761 | 0.551 → 0.772 |
| class, 96% (0.01) | 1.179 → **1.402** | 1.188 → **1.410** |
| class, 90% (0.02) | 1.130 → 1.352 | 1.134 → 1.356 |

- **The floor does not move between B1 and B2.** The effective length is 14.4 years for
  both.
- **The unweighted statistic** (printed beside, never certifying) would need much less: about
  0.34 at 64 years and 0.28 at 94, for the d = 1 stream at its 96% level (the superseded table
  below). **That is the weights' stated cost.**

**Superseded, kept beside: the first draft's table**, under the round-1 fixed centring
(`f58a97a`, output `6549253`). Its weighted bars agree with W2's within about 0.01.

| length | test, alpha | weighted (fixed centring) bar → net 80% | unweighted bar → net 80% |
|---|---|---|---|
| 64 y | stream d = 1, 0.03 | 0.490 → 0.711 | 0.236 → 0.341 |
| | stream d = 0, 0.01 | 0.604 → 0.826 | 0.293 → 0.398 |
| | class, 0.01 | 1.176 → 1.398 | — |
| 94 y | stream d = 1, 0.03 | 0.503 → 0.724 | 0.191 → 0.278 |
| | stream d = 0, 0.01 | 0.615 → 0.837 | 0.236 → 0.322 |
| | class, 0.01 | 1.197 → 1.419 | — |

## g. Code, tests, smoke and runtime

**All code is written against synthetic data only:**

| file | what | tests |
|---|---|---|
| `environments/french_long_panel.py` | the long panel: rule (ii), eligibility, both timings, costs | `tests/test_french_long_panel.py`, 2 |
| `data/french_long_split.py` | the host cuts with their counts (refuses until live) | `tests/test_french_long_split.py`, 3 |
| `estimator/recency.py` | W2, and the class under W2 on a real panel | `tests/test_recency.py`, 12 |
| `experiments/french_long_read.py` | the B1 and B2 runner (box only; refuses until live) | `tests/test_french_long_read.py`, 3, the whole read end to end on a synthetic panel |
| `experiments/read_french_long.py` | the reader | `tests/test_read_french_long.py`, 2, made-up results |

- **Seeds** (block 718000–718099; checked 2026-10-11: NO COLLISION):
  - B1: 718000 (d = 1 stream), 718001 (d = 0 stream), 718002 (class), 718003 (the
    performance line);
  - B2: 718010–718013, in the same order.
- **The smoke** (`experiments/french_long_smoke.py`, `d8b6f9b`; output `aee0f4a`): cost only, on
  a synthetic panel of B1's length (16,000 rows, 49 industries, staggered entries; seeds
  717000–717009), on the laptop, one thread:
  - one Sancho fit at d = 1: **623 s** (108 rolling, 489 expanding);
  - the W2 stream test at B 5,000: 7 s; the unweighted one: 74 s;
  - the class, extrapolated linearly from 1,024 members to 82,240: the fast kernel's table
    about 46 minutes, the W2 null about 12 minutes; the unweighted null about the same again.

**Box time and cost, estimated from the smoke.** The box runs 1.7× slower per core than the
laptop under load. The four Sancho fits run in parallel, and the class's matrix products on
32 threads (speedup assumed 4×, not measured). [AUTHOR]: these estimates are uncertain.

| session | Sancho (4 fits in parallel) | class (table and two nulls) | with setup | box-hours | cost |
|---|---|---|---|---|---|
| BOX-B1 | about 18 min | about 30 min | about 60–75 min | about 1.0–1.3 | about $11–15 |
| BOX-B2 | about 34 min (expanding about 2.2× B1's) | about 45 min | about 95–110 min | about 1.6–1.9 | about $18–21 |

- **BOX-B2 is close to the 2-hour limit.** It stops and asks if its projection passes 2 hours.
- **Disk:** the class table is about 21 GB for B1 and about 31 GB for B2, on the box's disk.

**The laptop runs nothing for these reads** except tests and the reader (author's answer 5).

## h. Operator sheets

`docs/french_long_operator_sheets.md`:
- **(H1)** the host cut for B1;
- **(BOX-B1)** the B1 in-sample run;
- **(H2)** the B1 grading;
- **(H3)** the host cut for B2;
- **(BOX-B2)** the B2 run;
- **(H4)** the B2 grading.

Commands are one line each, and on the host `uv` is used, never `pip`.

**For the author, in all:** 4 host starts, 12 host commands to paste, and 2 box sessions. Each
needs its own go.

## i. Both branches, for each read and each test

- **Certified, and the weighted bound held on the graded window:** "certified in-sample under
  the recency weights (W2) at the registered weight [96% level, or 90% level, so labelled];
  its weighted lower bound held on [the graded window]."
- **Certified, and the bound did not hold:** "certified in-sample …; its weighted lower bound
  did not hold on [the graded window] (realised … < bound …)."
- **Refused:** "refused; consistent with the registered detection floor." It is still graded,
  as on French.
- **The d = 0 stream,** in every branch, carries "NOT IMPLEMENTABLE".
- **The validation's limits** (section c) are printed beside every certificate.

## j. Added before going live (the author, 2026-10-11)

The author confirmed the six answers as written at `653a400`, including the certificate on
the W2-weighted statistic for both reads.

1. **Pinning, as proposed.**
   - The runner writes, to the run's directory and **before any pricing call**, the SHA-256
     of each cut CSV, of X (both timings) and of Sancho's inputs (version 2's X block and the
     groups, both timings).
   - **It refuses to price if a cut CSV's SHA-256 differs from the one H1 recorded** in the
     cut's record.
2. **Box caps:** BOX-B1 stops and asks at 2 box-hours; BOX-B2 at 2.5 box-hours.
3. **The graded quantity, fixed now for both reads.**
   - **What is graded:** the UNWEIGHTED net Sharpe over the graded window, with its
     stationary-bootstrap 90% interval, compared with the test's in-sample WEIGHTED L90.
   - **"Held" iff the realised value ≥ the weighted L90.**
   - **Why this quantity:** the weighted statistic estimates the recent Sharpe. The graded
     window is short and wholly recent, so its plain Sharpe is the matching realised quantity.
   - **How little a short window can distinguish.** The standard error of an annualised Sharpe
     is about sqrt((1 + SR²/2) / years):
     - over 6 years (B1, 1990–1995): **0.41** at SR 0 (0.46 at SR 0.7). The 90% interval is
       about ±0.67;
     - over 6.6 years (B2, 1,674 graded rows): 0.39 at SR 0 (0.43 at SR 0.7). The 90% interval
       is about ±0.64.

     So "held" and "did not hold" differ only for realised values well away from the bound. A
     bound near the realised value is not distinguished from it.
   - **The grader registrations may add checks. They may not change this quantity or this
     rule.**
4. **A refused test is still graded,** as on French.

## Remaining [AUTHOR] points

1. ~~Confirm or override the six answers~~: confirmed by the author (section j).
2. ~~The pin of X~~: accepted as proposed (section j, item 1).
3. **The box estimates are uncertain,** especially the class's threading. The caps are in
   section j, item 2.
4. **The graders** (H2, H4) are written after each in-sample read, under their own grading
   registrations, as on French.
5. **The registration is not live.** Going live sets `REGISTRATION` in
   `data/french_long_split.py` and `experiments/french_long_read.py` by a following commit.

## Amendment 1, 2026-10-11 (America/Chicago): the seed block 718000–718099, re-checked

Section g records the block as "checked 2026-10-11: NO COLLISION". That check is now recorded,
with the registration's own mentions excluded, over prereg, code and runs. Run on the laptop at
`209f6a4`.
- **Prereg:** `python -m experiments.seed_block_check --exclude prereg/french-long-history.md
  --ranges 718000-718099` scanned 52 files: every live and removed pre-registration,
  `EXPERIMENTS.md` and `ROADMAP.md`. It found 295 explicit ranges and 8 master seeds at 5,000
  draws each, the masters held in code included. Result: **NO COLLISION**. Without the
  exclusion it reports only this file's own blocks (718000–718099, 718010–718013) and its own
  integers.
- **Code and runs:** the checker does not scan them. So every tracked file (1,684) was
  searched for an integer from 718000 to 718099 that is not part of a longer number or a
  decimal. Outside this file there are two hits, both this registration's own:
  - `experiments/french_long_read.py:53`, `SEEDS = {"b1": 718000, "b2": 718010}`;
  - `tests/test_read_french_long.py:10`, `"seed": 718000` in a made-up result for the
    reader's test. It is a label; nothing is drawn from it.
- **Ranges built in code:** none reaches the block. The nearest are 716000–716999
  (`french_long_design_w2.py`), 717000–717009 (`french_long_smoke.py`) and 715000–715999
  (`recency_planted_2.py`).

**H1 ran at `b541ddf`,** before this amendment. This amendment does not touch
`data/french_long_split.py`, its inputs (the registered zip) or the cut it wrote. Nothing else
changes.

## Amendment 2, 2026-10-11 (America/Chicago): status lines overtaken by `756af89` and `dab1ac0`

Four statements were true when written and have since been overtaken. They stay as written,
since amendments are append-only. Read them as follows:
- **Lines 8–10** ("Not yet set: `REGISTRATION` …"): overtaken by `dab1ac0`. It sets
  `REGISTRATION = "756af89c0b7c7663bac184364b722cdb16a73807"` in `data/french_long_split.py`
  and `experiments/french_long_read.py`.
- **Line 13** ("Nothing has run on the box or the host for it"): true when this file went
  live at `756af89`. Since then:
  - H1, the `b1` cut, ran on the holdout host at `b541ddf`; its record and run record are at
    `209f6a4`;
  - nothing has run on the box.
- **Line 268** (point 5, "The registration is not live"): overtaken by `756af89`, which made
  it live, and `dab1ac0`, which set `REGISTRATION`.
- **The operator sheets' title**, "DRAFT; nothing runs before the registration is live", in
  `docs/french_long_operator_sheets.md`: overtaken by the same two commits. The sheets are
  corrected in a commit of their own.

This amendment does not touch `data/french_long_split.py`, its inputs or the `b1` cut. No rule
changes.
