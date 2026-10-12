# ML pilot run record, 2026-10-07 (America/Chicago; box clock UTC 2026-10-08)

**Exploratory** (`prereg/ml-pipeline-exploratory-2026-10-07.md`, the pilot section and later
appends). These raw outputs are committed before any read.

## The run

- **Box:** c7a.48xlarge (ssh alias og-48, 18.224.252.87): 192 vCPU, 369 GB.
- **Code:** HEAD `fce5627fb53e5551aa8768a770aba3ce73ef8fb7`, checked on the box after the
  pull. No tracked changes.
- **Environment:** Python 3.14.7, numpy 2.5.3.
- **LightGBM:** 4.7.0, installed from
  `lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`.
  - Wheel SHA-256 `d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7`,
    verified with `sha256sum -c` before install.
  - Installed `lib_lightgbm.so` SHA-256
    `573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a`.
- **Tests on the box:** 58 passed (learn, the ML pilot runner, reader and checker,
  planted_fast, planted_rules, the planted-truth rule branch).

## Sequence (UTC)

1. **01:19:01, box smoke.** Panels 686002–686003, cost only. Output in
   `runs/ml_smoke_box/2026-10-07`.
   - The leak test PASSED and the positions repeated bit for bit for all four settings.
   - Wall 510 s.
2. **01:27:53, dry run.** Seeds 686004 (state-gated, levels 1.0/1.5/2.5) and 686005
   (level 0, at cost and zero cost), 2 workers. Output in `runs/ml_pilot_dry/2026-10-07`.
   - The checker PASSED: 2 of 2 tasks, 5 of 5 rows, every field finite or a declared null.
   - Wall 299 s.
3. **01:33:18, pilot.** 300 tasks on 687000–687299, 150 workers.
   - All 300 tasks completed. **No task failed and none was retried.**
   - 800 rows: 600 planted, 100 level-0 at cost, 100 level-0 at zero cost.
   - Wall 819 s. Exit 0.
   - `pilot.jsonl` SHA-256
     `859023ffca056da2831658da8053509d7f12ced0643251ee8f0f23461ea39bb0`.
4. **About 01:47, results fetched, then stop issued** (`cloud/wait_fetch_stop.sh`,
   `sudo shutdown -h now`). The box stopped answering ssh at 01:48. Its EC2 state was not
   read from here, because no AWS credentials are configured.

## Deviation: two untracked files moved aside on the box before the pull

- **What happened:** `git pull --ff-only` on the box aborted. Two untracked files would
  have been overwritten by the merge:
  - `runs/diagnostics/estimators_2026-10-06_diffs.npz`
  - `runs/diagnostics/estimators_2026-10-06_rows_v2.jsonl`
- **Why they were there:** they are the 2026-10-06 diagnostic outputs. They were written
  on the box and later committed from the laptop.
- **The check:** each box copy's `git hash-object` equals its blob at `fce5627`:

  | file | blob |
  |---|---|
  | `estimators_2026-10-06_diffs.npz` | `ae81943e84bf6afa20bb78f1b88afeb8b09e15ad` |
  | `estimators_2026-10-06_rows_v2.jsonl` | `f3ac13873603337252bf0f5bfba314215fa273e9` |

- **The action:** with the author's go, both were moved, not deleted, to
  `~/box_untracked_2026-10-07/runs/diagnostics/` on the box.
- **Then:** the pull completed, and HEAD was checked against
  `fce5627fb53e5551aa8768a770aba3ce73ef8fb7`. The untracked checkpoint folders
  (`ckpt_g70_*`, `ckpt_h63*`) were left alone.

## Note

- **Invariants cache:** the box's cache key is `784a0d478f13f5f9`; the laptop's is
  `b0a5c0dc50a031f2`. The key hashes the in-sample panel and Sigma, so the two platforms
  differ at the bit level.
- **No mixing:** per the note, no laptop number appears beside a box number.
