# Recency planted validation: run record, 2026-10-09

- Plan: `prereg/recency-weight-planted.md` (07fa892; amendments e48113e, a2fc19f, 5bf5b43).
- **The author's go, typed:** "GO for the recency planted validation on the compute box, this
  run only." EXPECT = AMEND.
- **The go's conditions, checked before any box command:**
  - AMEND = 5bf5b43da97293e6a7ad06b70932e79ebd2370ee is the tip of main, local and on
    origin;
  - its parent is 18392d5af8571055c06f85e7c29ef508873bfacf;
  - its diff touches only `prereg/recency-weight-planted.md` (12 lines added).
  - The amendment commit was created and pushed by a tool call the session reported as
    rejected. It was found already committed and pushed, checked to appear once, and not
    repeated.
- **Box:** og-48 (c7a.48xlarge, 192 vCPU, 369 GB), IP 18.223.134.213. Up since 23:24:54 UTC;
  stopped with `sudo shutdown -h now` at 00:33:53 UTC (stop, not terminate). About 69 box
  minutes.

## Steps
1. **The three v2c logs, fetched first:** rsync exit 0 each. Their hashes and content checks
   are recorded in the confirmation's run record (commit 9ece901).
2. **Setup:**
   - The pull was blocked by 7 untracked files from the confirmation session. Each matched
     its committed blob, and each was moved to `~/moved_aside_2026-10-09_rp/` on the box:
     - `runs/ml_v2_confirm/2026-10-09/{provenance.json, results.jsonl}`;
     - `runs/ml_v2_confirm_dry/2026-10-09/{dry_check.txt, provenance.json, results.jsonl}`;
     - `runs/ml_v2_smoke_box3/2026-10-09/{smoke.json, smoke.txt}`.
   - Then HEAD = EXPECT, with 0 tracked changes.
   - The ETF X pin printed OK, and the three plan commits are ancestors.
3. **The pool, built on the box:** exit 0. Manifest in `pool_manifest.json`; the hashes are the
   box's own (Linux x86_64), with the laptop's pool kept apart.
4. **The dry run alongside the tests:**
   - pytest (test_recency, test_recency_planted, test_read_recency_planted): 19 passed;
   - the dry run: 10/10 tasks, 12 s, exit 0;
   - `check_recency_planted_dry`: DRY RUN CHECK PASS (all 7 arms, fields and finiteness).
5. **The run:** launched at about 23:31:30 UTC on 180 workers.
   - 5,200 of 5,200 tasks; wall 3,713 s; exit 0; "no rate printed".
   - The log has 0 lines matching traceback or error. The runner has no retry path, and no
     task failed or was retried.
   - Provenance written past the refusals.
   - The class arms ran about 3× slower per task than the laptop smoke under 180-way load:
     every worker read the 2 GB pool at once. The session still stayed under 2 box-hours.
6. **Fetched one rsync call each, every exit status 0:**
   - the run directory, the dry directory, the pool manifest, and the three logs;
   - results.jsonl: 5,200 rows, SHA-256
     f8c10960530ade38804e84c665542d177f328cc6bf5eec01ed223d3f278652e7.

Committed with the outputs before the read.

## Note, 2026-10-09 (after the read)

The reader's header printed "plan 07fa892; amendments e48113e, a2fc19f". It omitted
amendment 3 (`5bf5b43`: NA40's scaled form kept, and the reader's seed 705999 registered).
The reader already used both: the runner's NA40 form, and `default_rng(705999)`. The read's
output (`read.txt`) is left unedited.
