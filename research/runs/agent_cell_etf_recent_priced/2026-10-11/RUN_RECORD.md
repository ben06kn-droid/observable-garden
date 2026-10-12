# Agent cell on the ETF recent panel: collection and pricing, run record, 2026-10-11

**The registration:** `prereg/agent-cell-etf-recent.md`, live at `00c7af1` (amendments 1 and 2).
Its section 6 fixes the pricing.
**The inputs:**
- the 240 committed session logs (`870e07c`);
- the pinned precompute (manifest `78583e9b…0ae2`, BOX-ETF `05642cf`).

## Collection (laptop)

- `python -m experiments.agent_cell_etf_recent_collect --logs runs/agent_cell_etf_recent/2026-10-11
  --out runs/agent_cell_etf_recent_priced/2026-10-11/submissions.json`
- → "collected 240 sessions: 240 submissions, 0 no_submit".
- **`submissions.json`:** SHA-256 `45cedcab7dff8d426ca8c649808c5df67bb9bef6f2b11e7085f561b1bce4066c`,
  committed before pricing (`162e657`'s parent).
- All 240 submissions are rules. No session submitted the model stream.

## Pricing

**A first attempt on the laptop (one process) was stopped by the agent.**
- It had written nothing (`priced.json` is written only at the end), and its log was empty and
  was deleted.
- Timing on 3 rule sessions showed each takes more than about 200 s (the replay tier: B 1,000,
  three replays of the logged search per replicate). That is at least 13 hours for 240 in one
  process.
- The author chose option 2: the compute box, with a typed go and the box's IP.

**A pricing change, before the box run (`162e657`): `--workers`.**
- It is a process pool over sessions; each worker loads the pinned precompute once.
- Sessions are independent: each replay draws from its own session seed.
- **A test shows 1 and 3 workers give a byte-identical priced record, replay tier included.** It
  changes wall time only.

**The box run** (`og-48`, `i-0e0c1484de3c755ad`, IP 18.218.8.60):
- **Booted** 02:50:20 UTC (21:50:20 CDT). The 1-box-hour stop-and-ask mark was 22:50 CDT.
- **The checkout of `162e657`** was blocked by BOX-ETF's own outputs, left untracked on the box:
  - `pins.json` `76b49b4e…`;
  - `results.json` `4bc8ad99…`;
  - `precompute/manifest.json` `147961c8…`;
  - `precompute/sancho_d1.npz` `d0f3d0a5…`;
  - `precompute/class_stats.npz` `ff126725…`;
  - `precompute/base_columns.npy` `8e958305…`.

  Each equalled its committed blob, and all were moved to `~/moved_aside/2026-10-11-pricing/`.
  Then HEAD was `162e657`, with 0 tracked changes.
- **The box's precompute:** the manifest's SHA-256 is `78583e9b…0ae2`, the pinned one, and every
  file matches it, including `class_scored.npy` (kept on the box since BOX-ETF).
- **Launched at 21:54:31 CDT** in tmux `price`: `OMP/OPENBLAS/MKL_NUM_THREADS=1`, `--workers 96`.
  - Load was about 96, and memory about 23 GB of 369.
- **Finished by 22:07 CDT:** `priced 240 submissions (0 no_submit) -> …/priced.json; SHA-256
  388cc6f2…`, `[exit 0]`. About 13 minutes.
- **The fetch:** both `rsync`s exited 0. SHA-256s are identical on the box and the laptop:
  - `priced.json` `388cc6f2636fcbab6a007335e76b6cc2b3dd5f529c82edf0f1c410f5aedf37c7`;
  - `price.log` `1623c72037f025da298ad472702b3f3fd0ebbc3e2d02a4e56c9cf2a08de7133a`.
- **The stop:** `ssh og-48 'sudo shutdown -h now'` at **22:07:18 CDT**. By 22:08:13 CDT ssh timed
  out. The box was up about 17 minutes.

## Integrity fields of priced.json (no priced value read)

- 240 rows, 120 per arm. It names the pinned precompute manifest.
- **The replay tier is computed for all 240.**
- **The logs' consistency with the pricing holds in all 240:** the candidate's Sharpe values
  logged in the session (S, S_w) and arm B's shown L90 each match the pricing's to 5e-4. No arm-A
  session was shown an L90.
- **Flags:** every one of the 240 rule submissions carries "a non-grammar look (the model stream)
  was taken". Every session called `baseline_model()` before submitting a rule. That is
  recorded here as a count. Its bearing on the replay verdicts is as the registration's
  section 6 states.

## Committed with this record

`priced.json` and `price.log`, before anything reads them. No reader has run.
