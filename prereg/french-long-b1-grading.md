# French long history, B1: holdout grading, a registration

**Status: DRAFT, NOT LIVE (2026-10-11, America/Chicago).** For the author's review.
- **Nothing has run for it.** No `b1-holdout` cut has been made. No row dated 1990 or later has
  been parsed by this project.
- The grader and its reader are written **after** this registration goes live. Each refuses to
  run unless the live commit is an ancestor of HEAD.
- Amendments are append-only and dated.

**Parent registration:** `prereg/french-long-history.md`, live at `756af89`, with amendments 1
(`1fcbfc2`) and 2 (`27e8a10`).
- Its section j, item 3, fixes the graded quantity and the rule. **This registration may add
  checks. It may not change that quantity or that rule.**
- The B1 in-sample read: raw outputs at `314beda`, the reader's output at `ff04846`.

## 1. What is graded

**Three objects,** fixed by the in-sample read at `314beda`. **All three are graded,** the
refused one too (parent, section j, item 4).

| | object | in-sample verdict (96% / 90%) | weighted (W2) net Sharpe | **weighted L90 (the bound)** | unweighted net Sharpe, beside |
|---|---|---|---|---|---|
| (1) | the Sancho stream, d = 1 | certified / certified | 1.084 | **+0.674** | 0.774 |
| (2) | the Sancho stream, d = 0, **NOT IMPLEMENTABLE** | certified / certified | 1.307 | **+0.889** | 1.699 |
| (3) | the class's best member under the weights, d = 1: index 54952, **+mom252_rank, +volmom252_rank, +ma50_rank** | refused / refused | 0.798 | **−0.324** | — |

- **Sancho** is version 2 as confirmed at `97d2519`, run by `experiments/french_long_read.py` at
  `ca4b686`:
  - the base view, h 5, M2 (rolling 756 and expanding), G3, L {1, 3, 10, 30};
  - positions are zero on every row whose earned day is not eligible.
- **The member graded for (3) is the weighted best member,** the object the certificate was
  computed on.
  - The unweighted best member is recorded in `results.json`, but the reader did not print it
    (section 9, item 1).
  - **It is not graded.** [AUTHOR] confirms.
- **Nothing else is graded.** There is no other member, no re-selection on holdout data, and no
  other predictor.

## 2. The holdout window

- **1990-01-01 to 1995-12-31**: the `b1-holdout` cut of the registered zip (SHA-256
  `8f394fe3…40de`), made on the holdout host by `data/french_long_split.py`.
- **About 1,517 rows** (about 6.02 years at 252 a year). The exact count is recorded at the cut,
  from the date field. No row is parsed before then.
- **Graded periods:** the periods whose earned return is dated in the window. The first is the
  return dated on the first session of 1990, earned by the position the registered timing forms
  from in-sample data.
- **There is no fallback window.**
- **The holdout CSV never leaves the host.** Only `grades.json`, the run record and the cut
  record leave it. The cut record holds counts and dates, no value (section 8).

## 3. Continuation across the boundary

**One panel spans in-sample and holdout:** 1926-07-01 to 1995-12-31. It is built by
`environments.french_long_panel.long_panel` from the `b1` cut followed by the `b1-holdout` cut.
Every quantity on it is causal.

- **Features, the market series, eligibility and costs:**
  - These are computed over the spanning panel with no reset at 1990-01-01.
  - The 253-row warm-ups and lookbacks run over the in-sample tail into the holdout.
- **Entry by rule (ii) on the spanning panel:**
  - Every industry entered by 1971-03-12 (the `b1` record).
  - So, if no holdout value is missing, the spanning panel's entry dates equal the cut record's.
  - **A missing holdout value refuses the grading:** it would move an entry date and change
    in-sample positions.
- **Sancho:**
  - The walk-forward keeps its fixed schedule: the first scored row, then a refit every 252
    rows (`learn2/learner.py`, `REFIT = 252`), counted from the start.
  - The chunk containing 1990-01-01 is fitted where its chunk starts, as in-sample.
  - Each later refit trains on the rows realised before it.
- **The class member:** computed by the same kernel as the read (`environments.planted_fast`).
- **The book:**
  - Each stream is computed over all its rows, from its first scored in-sample row, with one
    continuous book.
  - The first scored rows are 1929-12-09 for d = 1 and 1929-12-06 for d = 0. The class runs from
    row 0.
  - The graded periods are then sliced out.
  - So the first holdout trade is costed from the position carried out of 1989.

## 4. Checks before any holdout value is computed (the grader refuses on any failure)

**a. Start-up:**
- the live commit is an ancestor of HEAD; HEAD equals `--expect-head`; no tracked changes;
- Linux x86_64; LightGBM 4.7.0 with the Linux library's SHA-256; the `learn2/` blobs are the
  confirmation's;
- the `b1` CSV's SHA-256 is `c380c3ea…0693`; the `b1-holdout` CSV's SHA-256 is its cut
  record's;
- every holdout row is dated 1990-01-01 to 1995-12-31, and none is missing.

**b. Reproduction of the in-sample read on the host.** The read ran on the compute box; the
grading runs on the holdout host.
1. X (both timings), version 2's X block and the groups, built from the `b1` cut alone: their
   SHA-256 must equal `pins.json` (`314beda`). **Exactness is predicted here:** the same code,
   input and platform, and element-wise arithmetic.
2. The in-sample weighted net Sharpe of each object, recomputed on the host:
   - **proposed: equal to the read to 3 decimals** (1.084, 1.307, 0.798);
   - and the unweighted net Sharpe of (1) and (2) to 3 decimals (0.774, 1.699).

   **Exactness is not predicted here:**
   - the box ran with 32 BLAS threads per process, and the host's thread count differs;
   - Sancho has discrete choices that a last-digit difference can flip.

   This is the same tolerance the French grading set (its section 4, Option A), and
   [AUTHOR] confirms it.
   - **On a miss: nothing is graded, and the author is asked.** Any looser tolerance is fixed
     by a dated amendment before any holdout value is computed.
3. The spanning panel's entry dates equal `pins.json`'s.

**c. No restart:**
1. The spanning panel's features on the in-sample rows are **bit-identical** to the in-sample-only
   build's (host against host).
2. Each object's positions on the in-sample rows are **bit-identical** between the spanning run
   and the in-sample-only run (host against host).
3. Each object's net return on its first holdout period equals its gross return minus the cost of
   trading from the carried position, to 1e-13. A restarted book, starting from zero, fails this.
4. No restart signature: no unwarmed all-zero feature row in the first 253 holdout rows, and a
   nonzero Sancho position at the first holdout row.

The checks print a line each, passed or not.

## 5. The graded quantity and the rule (fixed by the parent; restated)

For each object:
- **realised:** the UNWEIGHTED net Sharpe over the graded periods, with its stationary-bootstrap
  **90%** interval (percentile);
- **held iff realised ≥ the object's in-sample weighted L90** (section 1's bound column).

**Bootstrap:**
- B = 10,000. One resample of the holdout period indices is shared by the three objects.
- Block length by the class rule: the median Politis–White length over the holdout's demeaned
  base feature columns (`estimator.bootstrap.select_block_length`).
- Seed `default_rng(719000)`, from the block 719000–719099. Checked 2026-10-11 with
  `seed_block_check`: NO COLLISION. A scan of every tracked file found no use.

**Added, descriptive, never deciding:**
- realised − L90, and the interval shifted by L90;
- where the realised value falls on the object's in-sample weighted confidence curve (stored in
  `results.json`), by linear interpolation; at the grid's ends the end value, so labelled;
- beside it, realised against the in-sample UNWEIGHTED L90 for (1) and (2) (+0.594, +1.517),
  labelled "unweighted, descriptive, not the rule".

## 6. What a 6-year window can tell

The standard error of an annualised Sharpe over about 6.02 years, by Lo's iid formula with
ppy 252, is sqrt((1 + SR²/504) / 6.02).
- That is **0.408 at every Sharpe from 0 to 1.3.** The 90% interval is about ±0.67.
- **A correction to the parent's section j, item 3:** it used (1 + SR²/2) and gave 0.46 at
  SR 0.7. The French grading corrected the same formula on 2026-10-08 (`b45f111`). The value at
  SR 0, 0.41, is unchanged.
- The bootstrap interval, not this formula, is what is reported.

**P(held) under the iid normal approximation:**

| object | bound | true Sharpe = in-sample weighted value | true Sharpe = 0 |
|---|---|---|---|
| (1) d = 1 | +0.674 | 0.84 | 0.05 |
| (2) d = 0, NOT IMPLEMENTABLE | +0.889 | 0.85 | 0.015 |
| (3) class member | −0.324 | 0.997 | 0.79 |

- **Direction of error:**
  - the in-sample values are selected (the class maximum) or estimated with error, so the
    "in-sample value" column is **optimistic** (type-M);
  - if the true Sharpe equals the bound, P(held) is 0.5.
- **For (3), "held" is likely even at a true Sharpe of 0.** Its bound is negative, so a
  realised value of zero holds it. Grading (3) mainly checks that a refused object's bound was
  not too high. It cannot show that the member has an edge.
- **For (1) and (2), "held" against "did not hold"** is decided mostly by realised values more
  than about 0.4 from the bound.

## 7. Both branches, for each object

Wording from the parent's section i:
- **Certified, and the bound held:** "<object>: certified in-sample under the recency weights
  (W2) at the registered weight [96% level]; its weighted lower bound held on 1990-01-01 to
  1995-12-31 (realised <x> ≥ bound <L>)."
- **Certified, and the bound did not hold:** "<object>: certified in-sample …; its weighted
  lower bound did not hold on 1990-01-01 to 1995-12-31 (realised <x> < bound <L>)."
- **Refused, either way:** "<object>: refused in-sample; consistent with the registered
  detection floor. Graded: realised <x> [≥ / <] its weighted lower bound <L>."
- **(2) carries "NOT IMPLEMENTABLE"** in every branch.
- **Always stated:**
  - the validation's limits (parent, section c);
  - "a 6-year window: the standard error is about 0.41; values within about 0.4 of the bound
    are not distinguished from it."

## 8. Host, runtime and operator steps

**Platform:** the holdout host (`i-0886a189b85d4d051`, c7a.8xlarge, 32 vCPU, Linux x86_64).
The compute box is not used for grading.

**Runtime, estimated from BOX-B1** (fits of about 2,000–2,050 s each at 17,084 rows):
- four Sancho fits in parallel: d = 1 and d = 0, each on the in-sample-only panel and on the
  spanning panel (about 18,600 rows; the expanding fit grows faster than n);
- **estimate:** about 45–75 minutes, on 32 vCPU rather than the box's 192. The member and the
  bootstrap take minutes.
- **The cap:** stop and ask at 2 host-hours.
- `THREADS=32` as on the box ([AUTHOR]: the thread count can matter for check b.2).

**The H2 sheet** (`docs/french_long_operator_sheets.md`) is revised when the grader exists:
- the host checks out the grader commit G2;
- the Linux LightGBM wheel is installed into `.venv-grading` with `uv pip install --python
  .venv-grading`, and its library hash is checked;
- the `b1-holdout` cut is made, then the grade;
- `grades.json`, the run record and the `b1-holdout` cut record are fetched (counts, dates, no
  value; [AUTHOR]);
- the host is stopped by the author from the console or with `aws ec2 stop-instances`;
- raw outputs and the run record are committed before the read, then read once, committed
  unedited.

**Files to be written after this goes live:**
- `experiments/french_long_grade.py`, the grader, tested on synthetic panels;
- `experiments/read_french_long_grade.py`, the reader, tested on made-up grades.

## 9. Known items and disclosures

1. **The reader omitted an item the parent registers.** Section c: "for the class, the best
   member under the weights, and the unweighted best member beside it." `read.txt` at
   `ff04846` prints only the weighted one. The unweighted one is in `results.json` and has not
   been printed. Proposed: record it by a dated amendment to the parent before this goes live
   ([AUTHOR]).
2. **Some p-values are at their resolution floor.** p = 0.0002 is 1/(B + 1) at B = 5,000: test
   2's weighted p, and the unweighted p for tests 1 and 2. Each is "at most 0.0002".
3. **What is already known about the holdout period.** 1990–1995 has not been read by this
   project. But momentum-type signals on US equities after 1990 are the subject of published
   work, and the author knows that literature. Sancho's features include 252-day momentum
   ranks, and so does member (3).
   - This does not touch the graded numbers, which are fixed by code at `ca4b686`.
   - It does mean the window is not unknown to the person who chose it.
   - No citation is given here. One goes in only after the project's citation check
     ([AUTHOR]).
4. **No agent is involved** in this grading.
5. **The parent's box estimate for BOX-B2.** Sancho fits took about 34 minutes against the
   estimated 18. That bears on B2's 2.5-hour cap, not on this grading.

## [AUTHOR] points

1. Grade the weighted best member only, for (3) (section 1).
2. The box-to-host tolerance, 3 decimals on the in-sample Sharpes, and "on a miss, ask"
   (section 4b.2).
3. `THREADS=32` on the host (section 8).
4. Fetch the `b1-holdout` cut record (counts and dates, no value) with the grades (section 8).
5. The amendment recording the reader's omission (section 9, item 1).
6. A citation for item 3, or leave it uncited (section 9).
7. The descriptive additions of section 5: keep, trim or drop.
