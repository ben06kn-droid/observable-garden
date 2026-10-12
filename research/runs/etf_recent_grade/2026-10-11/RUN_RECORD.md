# ETF recent panel: the holdout grading (HOST-2), run record, 2026-10-11

**The registration:** `prereg/etf-recent-grading.md`, live at `2fd0346`. The grader's constant
is set at `3df6bbe`, and the session-list change is at `31b3b2c`.
**Its parents:** the panel (`310225c`) and the cell (`00c7af1`). `grades.json` records all three.
**The sheet:** `docs/etf_recent_grading_sheet.md` (HOST-2), G = `31b3b2c`.
**The host:** `og-holdout` (`i-0886a189b85d4d051`), IP 18.226.60.15, up at about 22:47 CDT (the
author's message).
**Every host command was run by the author, in his own terminal.** The agent ran only the
shutdown. It had no permission to `tail` for this session and did not.

## Steps

- **The checkout** of G was blocked by B1's untracked
  `runs/french_long_b1_grade/2026-10-11-r2/grades.json`.
  - Its `git hash-object` was `4d287343a3e1cd86e07ab5565d53050c09e40536`, equal to the committed
    blob.
  - It was moved to `~/moved_aside/2026-10-11-host2/` ("moved-identical").
  - Then HEAD was `31b3b2c09cfe094e5e39efe46fd834a22ef06fd2`.
- **Steps 2–7** (the status count, the ancestor checks, the inputs, the session list, the version
  line and the launch) **were run by the author. Their printed outputs were not pasted to the
  agent.** What the committed outputs show:
  - `grades.json` records git head `31b3b2c…` and all three registrations;
  - versions Python 3.14.2, numpy 2.5.3, scipy 1.18.1, LightGBM 4.7.0, Linux x86_64. These are
    the grading environment's pins, with nothing installed into it;
  - the holdout session list's SHA-256 is
    `7ed52a668b23f44f09cce15785555be0a90b60c2cc54831034b9875540797a1a`;
  - the submission list is `45cedcab…066c`, the priced file `388cc6f2…37c7`, and the cut's combined
    hash `c79312e7…fe61a`.
- **The grader's log** (`etfg.log`, here) has **526 `check …: pass` lines and no FAIL:**
  - **a:** start-up; the cut CSVs; submissions and pricing pinned; the holdout session list
    pinned and matching the cut record; the holdout sessions complete, none missing, the boundary
    close matching;
  - **b1:** 16 pins equal `pins.json`, including the first row used and the 1,259 rows dropped
    before 2010;
  - **b2:** to 3 decimals, for the two streams (weighted and unweighted), the class member
    (weighted), and every one of the 240 submissions (weighted and unweighted);
  - **c:** features identical and warm at both timings; positions identical, the book carried
    and a position at the boundary for both streams; the class member; and each distinct rule.
  - Then `grades written to runs/etf_recent_grade/2026-10-11/grades.json; no value printed`,
    `[exit 0]`.
- **Run time:** 190 s for the grading proper, at 4 workers × 8 threads.
  - Fit seconds (rolling, expanding):

    | fit | rolling | expanding |
    |---|---|---|
    | in-sample d = 1 | 36 | 56 |
    | in-sample d = 0 | 37 | 55 |
    | spanning d = 1 | 43 | 70 |
    | spanning d = 0 | 43 | 71 |

  - Well inside the 2-host-hour cap.
- **The process fields of grades.json** (no graded value read here):
  - 444 graded periods, 2025-01-02..2026-10-09;
  - label "weak: 1.76 years";
  - block length 4, B 10,000, seed 723000;
  - **246 items:** the 3 objects, the 240 submissions and the 3 books. The bootstrap matrices
    are 10,000 × 246.
- **A fact from the check lines** (in-sample, not a read): the no-restart checks list **3 distinct
  rules** among the 240 submissions:
  - +33 −35;
  - +32 −35;
  - +16 −17 −35.

## The fetch and the stop

- **The author copied the outputs:** `rsync` of `runs/etf_recent_grade/` and `scp` of
  `logs/etfg.log`, `exit=0`.
- **The SHA-256s on the laptop** (the agent's host commands do not include reading the host's):
  - `grades.json` `06a953f8d876cf59649de31927d27f1f35ee35d14da3679b2a4c7ff3f274264c`, 26,441,619
    bytes;
  - `etfg.log` `1884d34c6218663a062bfcf3bd3ea61029d8702e00ae693a34dc71246c2b7259`.
- **The stop:** the author said "host work done". The agent ran
  `ssh og-holdout 'sudo shutdown -h now'` at **22:57:23 CDT**. By 22:58:18 CDT ssh timed out.
- **Stayed on the host:** the raw fetch, every 2025+ row, `holdout_sessions.json`, the cut CSVs,
  the zip and the 2020+ French holdout.

## Next

These files are committed before any read. Then, in one sitting, each once, each committed
unedited (the registration, decision 5):
1. the panel's three objects;
2. the cell's R1–R4, in order.
