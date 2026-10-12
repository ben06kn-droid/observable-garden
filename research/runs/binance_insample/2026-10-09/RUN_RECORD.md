# Binance in-sample read: run record, 2026-10-09

- Registration: `prereg/binance-panel.md`, live at ecc07f0e6117e92db9ac03be462f418e3b0ac246 (amendment 1 at 79c3dfa).
- The author's go, typed: "Go for the Binance in-sample read, this run only, on the laptop.
  Run it as written with EXPECT 1374236077c2a234beaeae95ab2991edd8c1b054."
- Platform: the laptop, Darwin arm64; LightGBM macOS pin.
- Before the run, HEAD was 1374236077c2a234beaeae95ab2991edd8c1b054 with 0 tracked changes, and the runner's
  start-up refusals passed (the runner checks them itself).
- Command:
  `OMP_NUM_THREADS=1 .venv/bin/python -m experiments.binance_insample_read --out runs/binance_insample/2026-10-09
  --wheel ~/og-wheels/lightgbm-4.7.0-py3-none-macosx_12_0_arm64.whl --expect-head 1374236077c2a234beaeae95ab2991edd8c1b054`
- Started 2026-10-09 20:43:06 UTC; ended 21:18:39 UTC; exit 0. The runner's own timer recorded
  2,114 s.
- It printed only: "results written to runs/binance_insample/2026-10-09/results.json; no outcome printed."
- Bit-for-bit repeat: d = 0 identical, d = 1 identical.
- `results.json`: SHA-256 fd2e646b624f400f427a8ee9e610acdf253b6ec9090e53b041b9a038e7bd5e79. It is committed with this record
  before the read.
- No holdout data was touched, and no box was used.
