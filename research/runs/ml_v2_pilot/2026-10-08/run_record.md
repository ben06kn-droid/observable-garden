# ML version-2 pilot: run record, 2026-10-08 (America/Chicago; box clock UTC 2026-10-09)

**The pilot section:** `prereg/ml-v2-exploratory-2026-10-08.md` (`817f8d2`). EXPLORATORY.
These raw outputs are committed before any read.

## The run

- **Box:** c7a.48xlarge (og-48, 3.18.104.157), 192 vCPU, 369 GB. It came up at about
  00:12 UTC.
- **Code:** HEAD `bbbeed5a3fd62ce3acb27b7785de9e222b5b4296`, equal to EXPECT, checked after
  the pull. No tracked changes.
- **Hashes checked on the box with `sha256sum -c`, all OK:**
  - the Linux LightGBM wheel (`d23e922a…ebb7`);
  - the v2 inputs pin `etf_v2_inputs_r2.npz` (`3ff15481…6700`), copied from the laptop;
  - the ETF P pin (`4b461070…b7ba`).
- **LightGBM:** 4.7.0.
- **Tests on the box:** 54 passed, 1 failed (see deviation 2).

## Sequence (UTC)

1. **00:13:45, box smoke** (`runs/ml_v2_smoke_box/2026-10-08`).
   - All 252 fit cells ran in 74 s on 64 workers.
   - **The leak tests PASSED** for every block (X, V, groups, F on synthetic funding) and
     for 3 views.
   - **The bit-for-bit repeat** held for both cells.
   - Wall 537 s.
2. **00:23:00, the pilot and the dry run started together.**
   - The pilot ran 730 tasks on 180 workers.
   - The dry run (`runs/ml_v2_pilot_dry/2026-10-08`) ran 3 tasks on 3 workers. It took
     2,753 s.
   - **The dry checker PASSED:** 3 of 3 tasks, 7 of 7 rows, every field finite or a
     declared null.
3. **About 00:39, the 15-minute check:** no pilot task had finished yet (the heavy tasks
   ran first). The dry run's seed task took 869 s, against 513 s on the laptop. The
   projection was about 2.5 box-hours, under the 4-hour limit.
4. **01:09:** 180 of 730 tasks done (the first wave of heavy tasks, about 41 minutes
   each).
5. **About 02:26, the pilot finished:** **730 of 730 tasks, no failure, no retry, no
   traceback.**
   - 1,880 rows: 1,400 seed, 280 menu, 200 level-0.
   - Wall 7,369 s. Exit 0.
   - `results.jsonl` SHA-256
     `ad6405397d5f6a3e9b22d2639414b382d7b42e7bfd6f221372e5e07c31cdd086`.
6. **About 02:26, fetched, then stop issued** (`cloud/wait_fetch_stop.sh`). The box
   reset the ssh connection at 02:26. Its EC2 state was not read from here (no AWS
   credentials).

**Box time:** about 2 h 15 min (00:12–02:27).

## Deviations

1. **Six untracked files were moved aside before the pull.** `git pull --ff-only`
   aborted on six untracked files: the ridge_stack confirmation's box outputs, later
   committed from the laptop. Each box copy's `git hash-object` equals its blob at
   `bbbeed5`:

   | file | blob |
   |---|---|
   | `runs/ml_confirm/ridge_stack/provenance.json` | `f461c58d69f45ee3bcbc306044ddb8519df30949` |
   | `runs/ml_confirm/ridge_stack/results.jsonl` | `a173001810a0599bdc5339e091f44ee9599bf6d5` |
   | `runs/ml_confirm_dry/ridge_stack/dry_check.txt` | `a8bd03bd346b354ab9b85ac44309ad8805748c7d` |
   | `runs/ml_confirm_dry/ridge_stack/provenance.json` | `b7c1dd5b05a410fd44dacc9bcc64fc589db4bfa7` |
   | `runs/ml_confirm_dry/ridge_stack/results.jsonl` | `688da79a8558b2fdd01e5c1bfa289dd8fb28b1e1` |
   | `runs/ml_confirm_smoke/ridge_stack/smoke.txt` | `1082b2315d656d127c53f98560348cc8dc50fc77` |

   They were moved, not deleted, to `~/box_untracked_2026-10-09/` on the box. The pull
   then completed, and HEAD equalled EXPECT.
2. **One test failed on the box:** `tests/test_ml_v2_pilot.py::test_the_runner_refuses_on_the_laptop`.
   - The test assumes it runs on the Mac: it asserts that a "platform" refusal is
     present, and on Linux that refusal correctly does not appear.
   - It is a test that is wrong off the laptop, not a runner defect. The runner's
     start-up refusals ran on the box and refused nothing.
   - It was not fixed, since a fix would have changed the commit to run.
3. **The order of the dry run was changed, on the author's instruction.**
   - The dry run was not run before the pilot. Its checker cannot read partial pilot
     output without a code change, so the dry run ran **concurrently** with the pilot, and
     its checker was applied when it finished (PASS).
   - **The reason** (the author's): the cores were otherwise idle, and the dry path had
     already passed on the laptop.
