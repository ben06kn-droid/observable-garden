# ETF recent panel, BOX-ETF: the in-sample read, run record, 2026-10-11

**The registration:** `prereg/etf-recent-panel.md`, live at `310225c`, with amendments 1
(`80ec191`), 2 (`850d59d`; design numbers `d56d39e`) and 3 (`d72ae30`).
**The sheet:** `docs/etf_recent_operator_sheets.md`, BOX-ETF, as written at EXPECT.
**The go:** the author's, for this run only:
- EXPECT = `47e63cacec9f1c818e50bf3beafc4441b1090443`;
- IP <ip>;
- D = 2026-10-11;
- box started at 6:18, taken as 18:18 CDT. `uptime -s` gives 23:17:57 UTC, which is 18:17:57
  CDT. **The 1-box-hour cap was 19:18 CDT.**
- The first go message still contained "REPLACE", so nothing ran until the author gave the start
  time.

## Steps

- **1.** `<compute-box>`'s HostName set to <ip>. It is the same instance (`<compute-box>`).
- **0a.** 48 GB disk, 35 GB used, 13 GB free. In `data/planted_cache/`:
  - `fast_7c02af63f340181d`, 21 GB;
  - `fast_64b2439bdc05fe7f`, 3.7 GB;
  - `fast_a8c4ecf1ed1b6262`, 3.7 GB;
  - `recency_pool`, 1.9 GB;
  - `invariants_784a0d478f13f5f9.npz`, 1.9 MB.
- **0b.** `fast_7c02af63f340181d/manifest.json`: class `french-long-b1-signed-3`, N 82,240,
  T 16,829, the expected key. **It matches exactly.**
  - The two other fast caches were identified from their manifests and left untouched, neither
    deleted nor moved:
    - `recency-pool-gross` (N 82,240, T 3,019);
    - `planted-signed-3` (N 82,240, T 3,019).
- **0c.** `rm -r` of B1's cache and its lock. Disk afterwards: **14 GB used, 34 GB free** (at least
  15 needed).
- **2.** The 38 CSVs and `insample.cut.json` copied to `~/etf_recent/`.
- **3.** The checkout was blocked by BOX-B1's untracked `runs/french_long_b1/2026-10-11/pins.json`
  and `results.json`.
  - Each one's `git hash-object` equalled its blob at EXPECT:
    - `pins.json` `9dba775797e3c2e00aef81bf82c652ec67fc0ff8`;
    - `results.json` `3adc4ca6e49e5dd1581856586994e4935886a5c3`.
  - Re-checked immediately before each move, then moved to `~/moved_aside/2026-10-11-boxetf/`.
  - HEAD = EXPECT.
- **4.** 0 tracked changes.
  - **4a.** `cmp` of the box's record against the committed one: `record-identical`.
  - **4b.** `nproc --all` = 192.
- **5.** The wheel: OK.
- **6. Deviation, the author's option 1.**
  - The sheet's step 6 failed while collecting: `tests/test_etf_recent_integration.py` imports
    the host cut script, which needs `exchange_calendars`, and that is not in the box's `.venv`.
    No test ran.
  - **The run stopped and the author was asked.** He chose option 1: step 6 without the
    integration test.
  - `tests/test_etf_recent_read.py`, `tests/test_read_etf_recent.py` and `tests/test_recency.py`:
    **22 passed.**
  - The integration test had passed on the laptop. The box's environment was not changed.
- **7.** Launched at **18:22:49 CDT**: `THREADS=32 cloud/run.sh etf_r … --expect-head EXPECT
  --workers 4`.
  - No refusal. `pins.json` was written before any fit.
  - Finished by **18:31 CDT**: `results written …; no outcome printed`, `[exit 0]`. Total 452 s.
  - The log holds only RuntimeWarnings from rows before entry or warm-up, and the two closing
    lines.
- **8, 9.** Both `rsync`s exited 0. SHA-256s are identical on the box and the laptop:
  - `results.json` `e7460ccb1fec0f3066c0755ade77513ba287e0e193cc271a476bef6b3d07138e`;
  - `pins.json` `6c36ec544561c6915c268e69d6040814c7149791bf5edbbd6abfcefd8761e4a8`;
  - `etf_r.log` `691df31f6a8cfcac283d2a01836e0a26760053f003414e4672d620363136d874`;
  - `precompute/manifest.json` `78583e9b2fdadad7ef64bb6cd1b08b0a0ca9879a15ea84f165a20d2e705b0ae2`.

  **Every precompute file's SHA-256 equals its manifest's** (`sancho_d1.npz`,
  `class_scored.npy` at 1,655,326,848 bytes, `class_stats.npz`, `base_columns.npy`). The
  manifest's own SHA-256 equals `results.json`'s `precompute` entry.
  After the run the box was still at EXPECT, with 0 tracked changes.
- **10.** `ssh <compute-box> 'sudo shutdown -h now'` at **18:34:01 CDT** (exit 0). By 18:34:56 CDT ssh
  timed out. The box was up about 16 minutes, well inside the cap.

## Process fields from results.json and pins.json (no statistic read)

- registration `310225c…`; git_head = EXPECT; Linux x86_64.
- **Amendment 2:**
  - rows used 2010-01-04..2024-12-31, 3,774;
  - **1,259 rows dropped before 2010-01-04**, by date;
  - X at d = 1 is (3,519, 38, 40);
  - the scored rows are feature rows 1,003–3,518 at d = 1: **2,516, earned
    2015-01-02..2024-12-31.**
- The cut: 38 included, combined `c79312e7…fe61a`, last fetched session 2026-10-09.
- **The repeat: bit-identical** at d = 1 and at d = 0.
- **Seconds per fit:**
  - d = 1: rolling 104, expanding 126;
  - d = 0: rolling 95, expanding 118.
- **The tests:**

  | test | rows | earned | first scored row | block length (last n_eff) | B | seed |
  |---|---|---|---|---|---|---|
  | 1 | 2,516 | 2015-01-02..2024-12-31 | 763 | 15 (14) | 5,000 | 721000 |
  | 2 | 2,516 | same | 762 | 14 (17) | 5,000 | 721001 |
  | 3 | 2,516 | same | — | 15 | 5,000 | 721002 |

  Test 3 covers 82,240 members.

## Committed with this record

- `results.json`, `pins.json`, `etf_r.log`;
- the precompute's `manifest.json`, `sancho_d1.npz`, `class_stats.npz`, `base_columns.npy`.

`class_scored.npy` (1.66 GB) is gitignored. It stays on the laptop, pinned by the manifest.
