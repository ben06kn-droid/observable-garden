# French 49-industry in-sample read: run record, 2026-10-07 (America/Chicago; UTC 2026-10-08)

**Registration:** `prereg/french-panel.md`, section k, live at
`de9da1b914bcd2522ef95ddc4be4231eb47b1af0`. `results.json` is committed before the read.

## Pre-run checks

- **HEAD** `1a248db4fd93dd313322cb46b07a8984c9142e26`, as authorised. No tracked changes.
- **Power:** the laptop was on mains. `/usr/bin/pmset -g batt` read "Now drawing from 'AC
  Power'", battery 14% and charging.

## The run

- **Command:**

  ```
  python -m experiments.french_insample_read --out runs/french_insample/2026-10-07 \
      --wheel ~/og-wheels/lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl \
      --expect-head 1a248db4fd93dd313322cb46b07a8984c9142e26
  ```

- **Timing:** started 04:39:04 UTC, ended 04:40:40 UTC. Wall 1 min 37 s. Exit 0.
- **Platform:** Darwin arm64. **No start-up refusal.**
- **Pins:**
  - installed `lib_lightgbm.dylib` SHA-256
    `bc392db609d97730a9ed2acec7a56529b356c03dfad39bebf689523fed7dff18`;
  - macOS wheel SHA-256 `129535462686f274df179133643118c5c5c5667167fe6c3a28d955f0b3c8e868`;
  - pinned X SHA-256 `07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc`.
- **The bit-for-bit repeat** (two ridge_stack fits, positions) **passed.**
- **Both tests were priced, in order:** (i) the stream, seed 693000; (ii) the class, seed
  693001; B = 5,000 each.
- **Output:** `results.json`, SHA-256
  `2c3e0a4430d530f024277f8883d8344fc38cd37887519d7adea3f28dd732ebf3`.
- **The runner printed no outcome.** Before the read, only the repeat flag and the
  presence of both test records were checked.

## Not done

No holdout row was parsed, the zip was not moved, and the holdout grading registration
was not started.

## Deviations

None.
