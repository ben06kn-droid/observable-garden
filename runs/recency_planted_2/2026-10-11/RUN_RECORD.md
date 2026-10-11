# Recency validation, round 2: run record, 2026-10-11 (UTC)

- Plan: `prereg/recency-weight-planted-2.md` (46b589e; amendments 86277fc, 8a23368).
- **The author's go, typed:** "GO for the recency validation round 2 on the compute box,
  this run only." EXPECT = d36d1e773043be5a3932c27d145b5969f58a8019.
- **EXPECT was checked before anything started on the box:** it is the tip of main, locally
  and on origin, with a clean tree.
- **Box IP 77.113.76.110.** The agent queried it as not looking like an AWS address. The
  author confirmed it was the box's public IP. Checked on connect: the repository was at
  round 1's EXPECT (5bf5b43), and the pool manifest carried round 1's box hashes (G
  541a1842...). Linux x86_64, 192 vCPU.
- **Box:** og-48, up since 2026-10-11 01:07:27 UTC; stopped with `sudo shutdown -h now` at
  02:36:31 UTC (stop, not terminate). About 89 box minutes.

## Steps
1. **Setup:**
   - The pull was blocked by 5 untracked round-1 files. Each matched its committed blob, and
     each was moved to `~/moved_aside_2026-10-11_rp2/`:
     - `runs/recency_planted/2026-10-09/{provenance.json, results.jsonl}`;
     - `runs/recency_planted_dry/2026-10-09/{dry_check.txt, provenance.json, results.jsonl}`.
   - HEAD = EXPECT; 0 tracked changes.
   - The ETF X pin OK; the pool built on Linux x86_64 (round 1's, not rebuilt); the plan and
     both amendments ancestors.
2. **The dry run alongside the tests:**
   - pytest (test_recency, test_recency_planted_2, test_read_recency_planted_2): 21 passed;
   - the dry run: 10/10 tasks, 19 s, exit 0;
   - `check_recency_planted_2_dry`: PASS (all 7 arms; fields and finiteness).
3. **The run:** launched at about 01:10:20 UTC on 180 workers.
   - 6,200 of 6,200 tasks; wall 5,151 s; exit 0; "no rate printed".
   - 0 log lines match traceback or error. No task failed or was retried.
   - The projection stayed under 2 box-hours throughout. The class arms ran about 0.6–1.0
     tasks a second, slower than the smoke-scaled estimate (50 minutes of run against 86).
4. **Fetched one rsync call each, every exit status 0:** the run directory, the dry directory,
   and both logs. results.jsonl: 6,200 rows, SHA-256
   a98f048869a23ab3aac58aee40312de412cdfdb839731592c4c2758e9221fc9c.

Committed with the outputs before the read.
