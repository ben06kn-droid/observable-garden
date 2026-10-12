# Second version-2 pilot, and French step 0: run record, 2026-10-09 (UTC)

**The pilot section:** `prereg/ml-v2-exploratory-2026-10-08.md` (`4688d5e`). EXPLORATORY.
French step 0 is `experiments/french_step0.py` (`2c0f25b`) under the French grading draft
(DRAFT, NOT LIVE). These raw outputs are committed before the pilot's read.

## Setup

- **Box:** c7a.48xlarge (og-48, 3.18.223.195). It came up at about 04:28 UTC.
- **French step 0's laptop reference** was made before the session (in-sample only):
  `runs/french_step0/2026-10-09/reference.json` and `ref_positions.npy`.
- **Copied to the box:** the French in-sample CSV, the pinned French X and the reference.
- **Code:** HEAD `704241a9311bb0cc703b0bd64eea7f9612777bfe`, equal to EXPECT, checked after
  the pull. No tracked changes.
- **Hashes checked on the box with `sha256sum -c`, all OK:**
  - the Linux LightGBM wheel (`d23e922a…ebb7`);
  - the v2 inputs pin (`3ff15481…6700`);
  - the ETF P pin (`4b461070…b7ba`);
  - the French in-sample CSV (`1547da6f…c04e`);
  - the French X pin (`07488718…d3fc`).
- **LightGBM:** 4.7.0.
- **Tests on the box:** 47 passed.

## Sequence (UTC)

1. **04:30:33, box smoke** (`runs/ml_v2_smoke_box2/2026-10-09`).
   - **The leak tests PASSED** for every block (X, V, groups, F on synthetic funding) and
     for 3 views.
   - **The bit-for-bit repeat** held for both cells.
   - Wall 536 s.
2. **04:39:58, the pilot (450 tasks, 180 workers) and the dry run (2 tasks, 2 workers)
   started together**, as the box commands set out.
   - **The dry checker PASSED:** 2 of 2 tasks, 3 of 3 rows, every field finite or a
     declared null.
   - Dry wall 370 s.
3. **About 04:56, the pilot finished:** **450 of 450 tasks, no failure, no retry, no
   traceback.**
   - 800 rows: 700 seed (350 seeds × 2 levels), 100 level-0.
   - Wall 958 s. Exit 0.
   - `results.jsonl` SHA-256
     `ae1314ce7b8fbba511242a38c2191f8faacfa45a076530b4ccf1ecca50bcf144`.
4. **The pilot, the dry run and the smoke were fetched without stopping the box.**
5. **French step 0, compare on the box** (`runs/french_step0/2026-10-09`). It is
   in-sample only, and no holdout row was read: the loader refuses any row dated 2020 or
   later, and the script refuses a panel that reaches 2020.
   - It printed PASS on all four Option A tolerances.
   - `step0.json` SHA-256
     `dbd6d3fdb9692aa57a2e9231314c59c2ef1af101afad3b47595f2ca586c0a7e3`.
   - It was fetched.
6. **04:57:04, the stop was issued** (`sudo shutdown -h now`). The box stopped answering
   ssh by 04:57:34. Its EC2 state was not read from here (no AWS credentials).

**Box time:** about 29 minutes (04:28–04:57).

## Deviation

**Seven untracked files were moved aside before the pull.** `git pull --ff-only` aborted on
seven untracked files: the first version-2 pilot's box outputs, later committed from the
laptop. Each box copy's `git hash-object` equals its blob at `704241a`:

| file | blob |
|---|---|
| `runs/ml_v2_pilot/2026-10-08/provenance.json` | `b699635f639c433651e7bd5e198047df6621381d` |
| `runs/ml_v2_pilot/2026-10-08/results.jsonl` | `5f4e12a33706ca791af7f41703f68b7cfd34ee32` |
| `runs/ml_v2_pilot_dry/2026-10-08/dry_check.txt` | `8cc464791063a28fd0a0ae27e10d393e53653370` |
| `runs/ml_v2_pilot_dry/2026-10-08/provenance.json` | `5717b900866907c98c26a75de7ed7114f5c638fc` |
| `runs/ml_v2_pilot_dry/2026-10-08/results.jsonl` | `481f66d1bf3e2ac5cdb75391cc804131d3e0c7d8` |
| `runs/ml_v2_smoke_box/2026-10-08/smoke.json` | `525b9ed5a1c02c189a1225e0192d63d3e497c9d0` |
| `runs/ml_v2_smoke_box/2026-10-08/smoke.txt` | `b7f0526c6704f18731e448ab56fe926f7d0ee2bf` |

They were moved, not deleted, to `~/box_untracked_2026-10-09b/` on the box. The pull then
completed, and HEAD equalled EXPECT.
