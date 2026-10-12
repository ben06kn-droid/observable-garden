# ETF recent panel: holdout grading of the panel's three objects and the cell's 240 submissions, a registration

**Status: DRAFT, NOT LIVE (2026-10-11, America/Chicago).** For the author's review.
- **Nothing has run for it.** No holdout value of this panel has been computed for any purpose.
  The holdout rows sit in the raw fetch on the holdout host only.
- The grader (`experiments/etf_recent_grade.py`, written and tested at `0870dca` → `ae246d7`)
  refuses until this registration is live: its `GRADING` constant is set by the commit after
  the live one.
- Amendments are append-only and dated. The [AUTHOR] points are listed at the end.

**Parent registrations:**
- `prereg/etf-recent-panel.md`, live at `310225c`, with amendments 1 (`80ec191`), 2 (`850d59d`)
  and 3 (`d72ae30`). Its section g and amendment 2 fix **the graded quantity and rule for the three
  objects.** Amendment 2, item 7, fixes **when:** one host session, after the cell's sessions are
  complete and committed.
- `prereg/agent-cell-etf-recent.md`, live at `00c7af1`, with amendments 1 (`ecaa516`) and 2
  (`c569873`). Its sections 0, 6, 7 and 9 fix **the submissions' graded quantity, their L90 and
  the joint bootstrap.**
- **This registration may add checks. It may not change those quantities or rules.**

## 1. What is graded

**The panel's three objects.** The in-sample read is at `05642cf` / `3552158`. **All three were
refused, and all three are graded** (the parent's section g).

| object | in-sample W2 net Sharpe | **W2 L90 (the bound, as registered)** | unweighted, beside |
|---|---|---|---|
| (1) Sancho stream, d = 1 | 0.246 | **−0.123** | 0.183 (L90 −0.179) |
| (2) Sancho stream, d = 0, NOT IMPLEMENTABLE | 0.243 | **−0.139** | 0.180 (L90 −0.186) |
| (3) the class's best member under the weights: +vol252_z, −vol252_rank, −idvol63_rank | 0.659 | **−0.530** | — |

**The cell's 240 submissions.**
- The submission list is `runs/agent_cell_etf_recent_priced/2026-10-11/submissions.json`
  (SHA-256 `45cedcab7dff8d426ca8c649808c5df67bb9bef6f2b11e7085f561b1bce4066c`). It holds 240
  submissions and 0 `no_submit`, collected from the committed logs (`870e07c`).
- They were priced from those logs on the pinned precompute (on the compute box, 96 workers, a
  byte-identical-to-one-worker pool):
  - `runs/agent_cell_etf_recent_priced/2026-10-11/priced.json`, SHA-256
    **`388cc6f2636fcbab6a007335e76b6cc2b3dd5f529c82edf0f1c410f5aedf37c7`**;
  - committed at `0d6f55d` before anything read it;
  - pinned on the grader's command line.
  - Its integrity fields: the replay is computed for all 240, the log consistency holds in all
    240, and all 240 are rules.
- Each submission's bound is **its own UNWEIGHTED L90**, as the cell's section 0 fixes. Its W2 L90
  is beside, labelled "recency-weighted, descriptive".

**Also computed, descriptive, never deciding:**
- the equal-weight books of all submissions and of each arm (for the cell's R4);
- the 2026-only realised Sharpe of every item.

## 2. The graded window

- **2025-01-02 to 2026-10-09:** the last fetched session, recorded in the cut record (`ad233e7`).
- **444 sessions,** counted from their dates for every one of the 38 ETFs. About 1.76 years.
- **Graded periods:** the periods whose earned return is dated in the window.
- **There is no fallback window.**
- **The 2026-only part,** 2026-01-02..2026-10-09 (194 rows), is printed beside, descriptive.
- **Every printed grading line carries "weak: 1.76 years"** (the parent's section g).

## 3. Continuation across the boundary

**One spanning panel:** 2010-01-04 to 2026-10-09, built by the runner's own construction
(`experiments.etf_recent_read.etf_panel`; rows before 2010-01-04 dropped by date, amendment 2).
- **The holdout rows** are parsed on the host only, from the raw responses of the single fetch
  (`~/etf_recent/raw`).
  - There is one fetch, so no join is needed. The second grading's join (2028) is its own
    registration's.
  - **A check:** each ETF's 2024-12-31 adjusted close in the raw response equals the cut CSV's,
    compared as text.
- **Features, the market series and costs** run over the in-sample tail into the holdout, with
  no reset.
- **Sancho:** the walk-forward keeps its fixed schedule (first scored row, then a refit every 252
  rows, counted from the start). Later refits train on rows realised before them.
- **Rules and the class member:** computed by the same kernel as the precompute, on the
  spanning panel.
- **Every book is continuous** from its first in-sample row, and the graded periods are sliced
  out. So the first holdout trade is costed from the position carried out of 2024.

## 4. The death rule on the holdout

**The parent's rule** (section b, item 4; amendment 1, a):
- an ETF is dead from the session after its last bar, if it has no later bar or a silence of 10
  or more sessions;
- its position is closed at its last bar's adjusted close, the exit is costed, and its position
  is zero after;
- there is no re-entry;
- the 2026-09-22 fetch may supply a last bar, used only to close a position;
- if SPY dies, nothing runs, and the author is asked.

**What the records show:** the cut record counts 444 holdout dates for every one of the 38 ETFs,
so **no death and no gap is expected in the window.**

**The grader refuses on any missing or null holdout value.** If that happens, nothing is graded.
The death rule's implementation is then added, and tested, by a dated amendment and its code
commit, before any holdout value is computed.

## 5. Checks before any holdout value (the grader refuses on any failure)

Each check prints one pass/FAIL line and no value.

**a. Start-up:**
- this registration, the panel's and the cell's are all ancestors of HEAD; HEAD equals
  `--expect-head`; no tracked changes;
- Linux x86_64; LightGBM 4.7.0 with the Linux library's SHA-256; the `learn2/` blobs are the
  confirmation's;
- the cut's CSV hashes and combined hash; every holdout session present for every ETF, with no
  missing value (section 4); the 2024-12-31 closes equal as text;
- `submissions.json` and `priced.json` equal their SHA-256s given on the command line, and
  `priced.json` names the pinned precompute manifest `78583e9b…0ae2`.

**b. Reproduction of the in-sample numbers on the host.** The read and the precompute ran on the
compute box.
1. X (both timings) and Sancho's inputs (P, the X and V blocks, the groups), built from the cut
   alone with rows from 2010-01-04: their SHA-256 must equal `pins.json` (`05642cf`). **Exactness
   is predicted:** the same code, input and platform.
2. **To 3 decimals:**
   - each object's in-sample W2 net Sharpe on the scored window (0.246, 0.243, 0.659);
   - the two streams' unweighted net Sharpes (0.183, 0.180);
   - each rule submission's in-sample unweighted and W2 Sharpes (`S`, `S_w` in `priced.json`).

   **Exactness is not predicted here:** the box ran 32 BLAS threads per worker on 192 vCPU, and the
   host runs 8 per worker on 32. As in the B1 grading (its amendment 1), **on a miss nothing is
   graded, and the registered fallback is `--workers 1` with `THREADS=32`**, which needs the
   author's go.

**c. No restart:**
1. The features on the in-sample rows are bit-identical between the spanning build and the
   in-sample-only build.
2. Every object's and every rule submission's positions are bit-identical on the in-sample rows.
3. The first holdout trade is costed from the carried position, to 1e-13.
4. No unwarmed all-zero feature row appears in the first 253 holdout rows, and Sancho holds a
   nonzero position at the first holdout row.

## 6. The graded quantity and the rule (fixed by the parents; restated)

**For each item, realised** is the UNWEIGHTED net Sharpe over the graded periods, with the
compounded net return beside.
- **The three objects:** held iff realised ≥ the parent's **W2 L90** (section 1). They are graded
  although all three were refused. The sentences are the parent's (section i):
  - "refused; consistent with the registered detection floor. Graded: realised x [≥ / <] its
    weighted lower bound L";
  - (2) carries NOT IMPLEMENTABLE;
  - every line carries "weak: 1.76 years".
- **Each submission:** held iff realised ≥ **its UNWEIGHTED L90** from `priced.json` (the cell's
  section 0). The W2 version is beside, labelled "recency-weighted, descriptive".

**The bootstrap: one stationary bootstrap over holdout days, applied jointly to every item**
(the three objects, the 240 submissions and the three books), with sessions held fixed.
- B = 10,000.
- The block length is the class rule on the holdout's demeaned base feature columns.
- **The seed is 723000,** as the cell's section 9 registered it (`seed_block_check`: NO
  COLLISION).
- `grades.json` carries the replicate matrices (B × items, float32), so the cell's readers can
  compute every joint interval without the holdout.

**Nothing is read here.**
- The objects' reader (`experiments/read_etf_recent_grade.py`) prints the three objects' branches
  once, after the grades are committed.
- The cell's R1–R4 are read once, in order, by the cell's reader, under the cell's registration.

## 7. What 444 rows can tell (detectability, restated)

The SE of one realised Sharpe is about **0.753** at Sharpe 0 (Lo's iid, ppy 252, 1.76 years).
The 2026-only part's SE is about 1.14.

P(held) by the iid normal approximation:

| item | bound | true Sharpe = its in-sample W2 value | true Sharpe = 0 |
|---|---|---|---|
| (1) d = 1 | −0.123 | 0.69 | 0.57 |
| (2) d = 0, NOT IMPLEMENTABLE | −0.139 | 0.69 | 0.57 |
| (3) class member | −0.530 | 0.94 | 0.76 |
| the best rule submission possible (unweighted L90 −0.558) | −0.558 | — | 0.77 |
| a model-stream submission (unweighted L90 −0.179) | −0.179 | — | 0.59 |

- **Every bound is negative.** A true Sharpe of 0 is "held" more often than not, so "held" says
  little, as the cell registered in its section 0a.
- "Did not hold" needs a realised Sharpe well below 0.
- **All items share one window.** Their outcomes move together, and the joint bootstrap reports
  that. The direction of error and the type-M note are as in the parent's section g.

## 8. Threads and runtime (the B1 lesson)

**Threads: `--workers 4` with `OMP/OPENBLAS/MKL_NUM_THREADS=8`,** so workers × threads = 32 ≤
the host's 32 vCPU. No oversubscription. This is fixed here.
- **The lesson** (`prereg/french-long-b1-grading.md`, amendment 1, `2ddf0fa`):
  - with 4 workers × 32 BLAS threads on the same host, the B1 grading ran 5 h 30 min without
    finishing a fit;
  - with 4 × 8, the relaunch finished in about 31 minutes, all checks passing.

**Expected runtime, about 20–40 minutes:**
- **The four Sancho fits** (d = 1 and d = 0, each on the in-sample-only and the spanning panel)
  run in parallel.
  - BOX-ETF's fits took 95–126 s per part.
  - On the host, B1's in-sample fits ran at about 0.6 of the box's time per fit. So expect about
    3–6 minutes.
- **The 240 submissions' books,** in-sample-only and spanning, plus the reproduction checks:
  about 5–15 minutes.
- **The joint bootstrap,** 10,000 × 246 items × 444 rows: a few minutes.
- **The cap:** stop and ask at **2 host-hours** from the grader's start.

**The host environment.** The grader lists the holdout sessions with `exchange_calendars`, which
is not in `.venv-grading`.
- It is installed there with `uv … --no-deps` at the fetch's pins: `exchange_calendars` 4.13.2
  and tzdata 2026.4, plus its pure-Python dependencies.
- Then numpy 2.5.3, scipy 1.18.1, LightGBM 4.7.0 and Python 3.14.2 are checked unchanged before
  the grader runs (the operator sheet).

## 9. Custody

- The holdout rows are parsed only by the grader, on the host.
- **Only `grades.json`, the grading log and the run record leave the host.** No holdout row,
  position or price does.
- The host is stopped by the agent with `ssh og-holdout 'sudo shutdown -h now'`, only after the
  author says the host work is done (the author's rule, 2026-10-11).

## 10. Disclosures

- **The parent's scripted read refused all three objects,** and the cell's agents were told none
  of it (the cell's section 0a).
- **2025 lies inside a window opened once** for other strategies (the 6.5 grading). Only 2026 is
  untouched.
- The second grading (2028-01-03) is its own registration's.
- **The pricing is committed before this registration goes live.** The registration does not
  depend on any priced value beyond restating that the bounds are negative. That was known from
  the precompute before any session.

## [AUTHOR] points

1. **Seeds.** Your brief asked for a fresh, checked block. But the cell's live registration
   (section 9) already fixes 723000 for the joint holdout bootstrap, and the grader uses it. A
   fresh block would need an amendment to the cell.
   - Proposed: keep 723000.
   - Record that the panel's reserved 721010–721019 ("the grading", its section i) are unused.
2. The thread setting: 4 × 8 (section 8).
3. The 2-host-hour cap.
4. Installing `exchange_calendars` into `.venv-grading` with `--no-deps`, and checking the pinned
   versions unchanged (section 8). Or keep it out of `.venv-grading` by having the cut-side session
   list written by `~/venv-fetch` first. That would need a small grader change.
5. The death rule (section 4): refuse and amend if it is ever needed, rather than implement it
   now. The records show no gap.
6. Whether the objects' reader runs right after the grades are committed, before the cell's
   R1–R4, or together with them.
