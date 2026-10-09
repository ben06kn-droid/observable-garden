# Version-2 confirmation: run record, 2026-10-09

- Registration: 083c734724340b0d1ae7f6bfd98b0a61e23fe84c (amendment 1 at 0b0b358).
- EXPECT: 3cfaa28b60abba12a2249a09adea73007da1bc6c. The box was at this HEAD with a clean tree
  and the registration as an ancestor.
- Author's go: given 2026-10-09 in session, option (a): the agent runs the box commands
  over ssh, for this session only.
- Box: og-48 (c7a.48xlarge, 192 vCPU), IP 3.144.69.189. Up since 05:45:26 UTC (`uptime -s`).
  Stopped with `sudo shutdown -h now` at 06:35:20 UTC (stop, not terminate). About 50 box
  minutes.

## Setup (`docs/ml_v2_confirm_box_commands.md` section 1)
- The pull was blocked by 11 untracked files. Each matched its committed blob at EXPECT
  (`git hash-object` = `git rev-parse origin/main:<path>`). They were moved to
  `~/moved_aside_2026-10-09_v2c/` on the box:
  - runs/french_step0/2026-10-09/{ref_positions.npy, reference.json, step0.json, step0.txt};
  - runs/ml_v2_pilot2/2026-10-09/{provenance.json, results.jsonl};
  - runs/ml_v2_pilot2_dry/2026-10-09/{dry_check.txt, provenance.json, results.jsonl};
  - runs/ml_v2_smoke_box2/2026-10-09/{smoke.json, smoke.txt}.
- After the pull: HEAD = EXPECT; 0 tracked changes; ancestor-ok. The wheel, the v2 inputs
  r2 pin and the ETF X pin each printed OK.
- pytest on the box (OMP_NUM_THREADS=1): 44 passed, 1 deselected
  (`test_the_pinned_blobs_match_this_checkout_and_the_laptop_is_refused`, Mac-only, as the
  commands state), 8 warnings, 70.9 s.

## Smoke, run, dry run
- Smoke (`runs/ml_v2_smoke_box3/2026-10-09`): every leak test PASS (blocks X, V, groups,
  F; three views); both bit-for-bit repeats True; wall 537 s; exit 0.
- Run and dry run were launched at 06:00:21 UTC. Both passed the start-up refusals:
  provenance was written, and it is written only after them.
- Dry run (699900 volcond, level-0 699901): exit 0. `check_ml_v2_confirm_dry`: 2 of 2
  tasks, 3 rows (expected 3), every field finite or a declared null, DRY RUN CHECK: PASS.
- Run: 960/960 tasks, wall 2059 s, exit 0, "no outcome printed". The log had 0 lines
  matching traceback or error. The runner has no retry path, and no task failed or was
  retried. results.jsonl: 1,520 rows (1,120 seed rows over 560 tasks, 400 level-0),
  960 distinct tasks. Provenance: HEAD = EXPECT, Linux x86_64, dry_run false, 960 tasks.
- SHA-256 on the laptop after the fetch:
  - results.jsonl e3191c0cf10c4d22140dc578ce1420dcb968b88517f8edc30f11a37d136e8402;
  - provenance.json e069cb42aca8998ba0c87a5fed3b5333978819f101e0c7596d59bc0f81699936.

## Deviation
- **Logs not fetched.** The agent's rsync of the three logs (v2c_smoke, v2c_run, v2c_dry)
  used several remote sources in one call. The laptop's rsync 2.6.9 rejects that, so the
  fetch failed and the box was stopped anyway. The logs remain on the stopped box under
  `~/observable-garden/logs/`. Their content quoted above was read over ssh before the stop.
  The outputs (results, provenance, the dry run with its check, the smoke) were fetched.
