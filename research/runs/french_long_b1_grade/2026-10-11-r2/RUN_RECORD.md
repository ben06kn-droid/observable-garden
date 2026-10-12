# French long history, B1: the holdout grading, run record, 2026-10-11

**The registration:** `prereg/french-long-b1-grading.md`, live at `00417de`, with amendment 1
(`2ddf0fa`). The parent is `prereg/french-long-history.md` (live `756af89`; amendments 1–4).
**The sheet:** `docs/etf_recent_operator_sheets.md`, HOST-1, steps 11–20.
**The host:** `<holdout-host>` (`<holdout-host>`, c7a.8xlarge, 32 vCPU), IP <ip>. Up
at about 11:46 CDT (16:46 UTC, from the author's message; `uptime` gives 5:40 at 22:26 UTC).
**Every host command was run by the author, in his own terminal.** The agent ran only:
- the read-only log `tail`, under the author's rule extension below;
- the final shutdown.

## Steps 11–14 (the author)

- The zip check, the `b1-holdout` cut, the `b1_insample.csv` hash and the LightGBM library hash
  were run at G = `04eecfc`.
- **Their printed outputs were not pasted to the agent.** What the committed records show:
  - **The holdout cut record** (`b1_holdout.cut.json`, here): cut `b1-holdout`, window
    1990-01-01..1995-12-31, **1,517 rows**, 1990-01-02..1995-12-29. CSV SHA-256
    `87110c71ce7e7334bac91a5fb34e21270ffed0102e38842935f44a41fffefc21`. Every industry present
    from the first row.
  - The grader's start-up checks passed. These cover the LightGBM 4.7.0 library hash, the
    `learn2/` blobs, Linux, HEAD, a clean tree and both registrations as ancestors. They also
    cover the `b1` CSV's hash `c380c3ea…0693` and the holdout CSV against its record.
- **There is no wheel file on the host** (the author, 2026-10-11). The grader's wheel check is
  dropped. Standing in for it:
  - LightGBM 4.7.0 with `lib_lightgbm.so` SHA-256 `573d57e8…616a`;
  - the `learn2/` blobs equal to the confirmation's;
  - Linux x86_64;
  - HEAD equal to `--expect-head`, with a clean tracked tree;
  - `756af89` and `00417de` both ancestors of HEAD.
- **Versions** (grades.json): Python 3.14.2, numpy 2.5.3, scipy 1.18.1, LightGBM 4.7.0, Linux
  x86_64.

## The first launch (stopped; nothing graded)

- **Launched at about 16:50:58 UTC** (11:50 CDT; tmux `b1g`), at G = `04eecfc`, with
  `THREADS=32 --workers 4`, as section 8 then said. Its log is kept as `b1g_run1.log`, here.
- It printed check a (start-up, cut hashes, holdout rows complete) and the nine b1 pin checks,
  all passing. Nothing after them.
- **The 3.5-host-hour cap** passed at about 15:15 CDT. At 15:28 CDT the agent asked, and the
  author said "do not stop, just continue running". The stop-and-ask mark was then set at 21:00
  CDT.
- **The rule extension (the author, about 15:30 CDT):**
  - "You may run ssh <holdout-host> 'tail -n 30 ~/observable-garden/logs/b1g.log', read-only, to watch
    the B1 grading, and nothing else on the host besides the shutdown."
  - It later covered the relaunch log `logs/b1g2.log` the same way (the author's brief for
    amendment 1).
  - The agent watched by monitor, every 5 minutes.
- **The author's check at 22:26 UTC:**
  - tmux `b1g` alive;
  - load average 109 on 32 vCPU;
  - four forkserver workers at about 800% CPU each, elapsed 5 h 30 min;
  - the log at 44 lines, unchanged over 60 s;
  - no grades file.

  **The cause:** 4 workers × 32 BLAS threads on 32 cores. The 32-thread setting was the
  reviewer's.
- **Amendment 1** (`2ddf0fa`) set `THREADS=8 --workers 4`. **The author stopped the first launch**
  (`tmux kill-session -t b1g`) before any fit finished.
  - It wrote no grades, and nothing from it was seen beyond the start-up and pin checks.
  - The grader creates its output directory only when it writes `grades.json`, so the first
    launch left none.

## The relaunch (graded)

- **At G2 = `2ddf0fada54aeacea363e758cebb7d6f0326911a`** (tmux `b1g2`), with
  `OMP/OPENBLAS/MKL_NUM_THREADS=8 --workers 4`, a fresh output `2026-10-11-r2` and a fresh log
  `b1g2.log`.
- **Times:** the log was first seen at 17:36 CDT. The pin checks passed by 17:41.
- **It finished by 18:07 CDT: `grades written to …/grades.json; no value printed`, `[exit 0]`.**
  Total 1,728 s.
- **Fit seconds:**

  | fit | rolling | expanding |
  |---|---|---|
  | in-sample d = 1 | 226 | 990 |
  | in-sample d = 0 | 228 | 978 |
  | spanning d = 1 | 249 | 1,151 |
  | spanning d = 0 | 250 | 1,139 |

- **All 34 checks printed `pass`:**
  - a: start-up, cut CSVs, holdout rows complete;
  - b1: 9 pins;
  - b2: the in-sample Sharpes to 3 decimals, for the d = 1 and d = 0 streams (weighted and
    unweighted) and the class member (weighted). **This also covers the thread change.**
  - b3: entry dates at both timings;
  - c1–c4: features and positions identical on the in-sample rows, the books carried, the
    holdout features warm, a position at the boundary.
- **From grades.json (process fields only):** 1,517 graded periods, 1990-01-02..1995-12-29;
  bootstrap B 10,000, seed 719000, block length 4.

## The fetch and the stop

- **The author copied the outputs to the laptop:** `rsync` of
  `runs/french_long_b1_grade/`, and `scp` of `b1g2.log`, `b1g_run1.log` and `b1_holdout.cut.json`.
  The local `b1g2.log` ends with the exit line.
- **The SHA-256s on the laptop** could not be compared with the host's, because the agent's host
  commands are limited to the log `tail` and the shutdown:

  | file | SHA-256 |
  |---|---|
  | `grades.json` | `952d1e1f60f4f7bb0cd064f682f0823abb2b6aab91cd0255abfbe15395d4f19e` |
  | `b1g2.log` | `d50951edf00accba2f25dd1d70e93f9aca1492d481646b25c2009442da88c3f8` |
  | `b1g_run1.log` | `5d648e94a4d94a1e246b5a148d1e2808eeec710f290a2c5cc3d7029c954e6419` |
  | `b1_holdout.cut.json` | `491f2b77e18c1dd160aa088679a40cb7291d79fe3c2464aeffc98f8b6b965ba8` |

- **The stop:** the author said "host work done". The agent ran
  `ssh <holdout-host> 'sudo shutdown -h now'` at **18:11:54 CDT** (exit 0). By 18:12:49 CDT,
  `ssh <holdout-host>` timed out.
  - The instance's shutdown behaviour is "Stop", as the author confirmed in the console.
  - The host was up about 6 h 26 min in all.
- **No holdout row or value left the host.** Only `grades.json`, the logs and the holdout cut
  record came back. The cut record holds counts and dates, no value.
