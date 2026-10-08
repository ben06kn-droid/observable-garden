# ridge_stack confirmation: run record, 2026-10-07 (America/Chicago; box clock UTC 2026-10-08)

**Registration:** `prereg/ml-ridge-stack-confirmation.md`, live at
`77f3ee19469f500d5c3959c9612a04d250856b02`. These raw outputs are committed before any
read.

## The run

- **Box:** c7a.48xlarge (ssh alias og-48, 18.225.7.169), 192 vCPU.
- **Code:** HEAD `9f3ba9edbad088a053a3ef09390bf9ee9ba94efd`, equal to EXPECT, checked on the
  box after the pull. The tree was clean and the registration is an ancestor of HEAD.
- **Environment:** Python 3.14.7, numpy 2.5.3.
- **LightGBM:** 4.7.0.
  - Wheel SHA-256 `d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7`,
    verified with `sha256sum -c`.
  - Installed `lib_lightgbm.so` SHA-256
    `573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a`.
- **The pinned `learn/` blobs** at HEAD equal the registered ones. The runner checks
  this at start-up and recorded them in `provenance.json`.
- **Tests on the box:** 62 passed.

## Sequence (UTC)

1. **About 02:50, box up.** `uptime` read 0 min at 02:51:02.
2. **02:52:13, box smoke.** Panels 689902–689903, ridge_stack and the control. Output in
   `runs/ml_confirm_smoke/ridge_stack`.
   - **The leak test PASSED, and the positions repeated bit for bit, for both.**
   - ridge_stack took 37.4 s per panel; the control took 0.6 s.
   - Wall 375 s.
3. **02:58:53, dry run.** Seeds 689900 (state-gated, levels 1.0/1.5/2.5) and 689901
   (level 0, at cost and zero cost), 2 workers. Output in `runs/ml_confirm_dry/ridge_stack`.
   - **No start-up refusal.**
   - **The checker PASSED:** 2 of 2 tasks, 5 of 5 rows, every field finite or a declared
     null.
   - Wall 231 s.
4. **03:03:10, the run.** 800 tasks on 689000–689799, 150 workers.
   - **All 800 tasks completed. No task failed and none was retried.**
   - 1,600 rows: 800 planted panels, 400 level-0 panels at cost and 400 at zero cost.
   - Wall 1,116 s. Exit 0.
   - `results.jsonl` SHA-256
     `562b9e366985114ed42dd0beb1c24c38ed8246ba87f17768ce0fd281374fdf66`.
5. **About 03:22, results fetched, then stop issued** (`cloud/wait_fetch_stop.sh`).
   - The box reset the ssh connection at 03:22:53 and timed out shortly after.
   - Its EC2 state was not read from here, because no AWS credentials are configured.

## Deviation: seven untracked files moved aside on the box before the pull

- **What happened:** `git pull --ff-only` aborted. Seven untracked files would have been
  overwritten by the merge.
- **Why they were there:** they are the pilot's box outputs, written on the box on
  2026-10-08 UTC and later committed from the laptop (`302c447`).
- **The check:** each box copy's `git hash-object` equals its blob at `9f3ba9e`:

  | file | blob |
  |---|---|
  | `runs/ml_pilot/2026-10-07/pilot.jsonl` | `6c1dc1523f1e9de45539f559c528ad1763598263` |
  | `runs/ml_pilot/2026-10-07/provenance.json` | `694ee38537cc1ad3a1cc02bd227ab3d54c55b7ab` |
  | `runs/ml_pilot_dry/2026-10-07/dry_check.txt` | `eee28b1ef7062defb0402480a50114460c1f9598` |
  | `runs/ml_pilot_dry/2026-10-07/pilot.jsonl` | `43215455b712451cec63afb1a141d1b799f10f3f` |
  | `runs/ml_pilot_dry/2026-10-07/provenance.json` | `2c76ec467447aeb0b0dd80861e858defca2d75dc` |
  | `runs/ml_smoke_box/2026-10-07/effective_parameters.json` | `6af400999ce9c5c4dc9b21cab2940d04b6053d37` |
  | `runs/ml_smoke_box/2026-10-07/smoke.txt` | `1032e3af07ca598f33b788c3fe30aa1a5dee2f8e` |

- **The action:** all seven were moved, not deleted, to `~/box_untracked_2026-10-08/` on
  the box, under the same relative paths. The author's go for this run allowed moved
  files, to be recorded here.
- **Then:** the pull completed, and HEAD was checked equal to EXPECT.
