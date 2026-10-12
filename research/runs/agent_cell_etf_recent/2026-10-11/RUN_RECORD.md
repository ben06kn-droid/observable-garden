# Agent cell on the ETF recent panel: the 240 sessions, run record, 2026-10-11

**The registration:** `prereg/agent-cell-etf-recent.md`, live at `00c7af1`, with amendment 1
(`ecaa516`: retries that run out stop the launcher) and amendment 2 (`c569873`: 120 sessions per
arm, 240 in all).
**The prompts:** `prereg/agent-cell-etf-recent-prompts.md`, live with it.
**The precompute:** BOX-ETF's (`05642cf`), manifest SHA-256 `78583e9b…0ae2`, pinned in the
launcher and checked at start.
**Run by the author, on the seat,** from his own terminal. The agent launched nothing.

## The smoke (cost only; never collected, priced or read)

- 5 sessions on the dedicated seeds (master 723100), 4 workers, at code `5b4153e`.
- Output in `runs/agent_cell_etf_recent_smoke/2026-10-11-smoke/`. It is not committed.
- **The folder-name refusal:** the smoke command the agent first printed named the folder
  `…/agent_cell_etf_recent_smoke/2026-10-11`. That folder's own name does not contain "smoke",
  so the launcher refuses it.
  - The author ran the smoke into `…/2026-10-11-smoke`.
  - The operator note and the launcher's message were then corrected (`ae246d7`).
- **Cost (the `usd` fields only):** $0.110, $0.125, $0.131, $0.110, $0.130; **$0.606 in all.**
- Its sessions have not been opened for anything else.

## The cell

- **The command:** `--arm both --runs 120 --credential seat --workers 4 --out
  runs/agent_cell_etf_recent/2026-10-11`, at code `ae246d7` (`run_config.json`'s `code_state`).
- **Start:** `0 complete skipped; 0 partial deleted and redone; 240 to run`.
  - The first session started at **19:53:40 CDT** and the last ended at **21:17:42 CDT**, 84
    minutes.
  - The launcher printed nothing more until the end. With `--workers 4` it printed every "done"
    line only after all sessions finished (fixed afterwards, in its own commit).
  - The author's terminal looked idle. The agent counted session files and processes (no
    content) at 20:27 (96 written) and 20:57 (186).
- **240 session files**, 120 per arm, matching `run_config.json`'s schedule of 240.
  - Every file ends with its `end` event.
  - **No session has an error or a `retried_attempts` event,** and no retry sidecar was ever
    written. So there were no rate-limit or service-error retries.
- **Served model:** `claude-sonnet-5` in all 240 (each run's `models_seen`). `run_config.json`
  also records the model, 60 max turns, 4 workers, `smoke: false`, the registration and the
  precompute manifest.
- **Cost (the `usd` fields): $37.90 for 240, a mean of $0.158.** That is below the
  registration's projection of $55–115, which used 6.5's figures.
- **Not read:** every field above is a process field. No move, candidate, Sharpe, prediction or
  submission was opened for this record. `no_submit` sessions are counted by the collector at
  pricing.

## Committed with this record

All 240 `cellE_*.json` session logs and `run_config.json`, as raw outputs, before any collection,
pricing or read.
