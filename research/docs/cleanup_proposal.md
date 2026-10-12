# Cleanup inventory, 2026-10-08: proposals for the author's review

**This is an inventory only. Nothing has been moved or deleted.** Every action below is a
proposal. Statuses come from each file's own status lines, checked against the sessions
that wrote them; check before acting.

## 1. prereg/

| file | status | proposed action |
|---|---|---|
| `AGENT_PROMPTS.md` | superseded by `AGENT_PROMPTS_REAL.md` (its own first status line) | keep; add a one-line pointer to the live file if one is missing |
| `AGENT_PROMPTS_REAL.md` | live (the prompts used on real data) | keep |
| `COMMIT_MAP.md` | reference table (commit map) | keep |
| `DATASET_LEDGER.md` | live (created with the French registration, `de9da1b`) | keep; add the ETF and ADR datasets so it is complete |
| `README.md` | index of the pre-registrations | update the index with every file below added since its last edit (`d3dc733`) |
| `adr-features.md`, `adr-universe.md` | closed | keep |
| `agent-cell.md` | live sections, with a draft status line at the top | check whether the top line is stale; if so, state the live state |
| `agent-on-real-data.md` | first status word DRAFT; its 6.5 holdout was graded under `holdout-grading.md` | add a closing line pointing to `0426352` |
| `agent-pilot.md` | live, closed | keep |
| `binance-panel.md` | DRAFT, NOT LIVE; held unread (`4f5fdd8`) | keep as draft |
| `bits-of-selection.md`, `bracketed-verdicts.md`, `living-verdict.md`, `pivotal-interrogation.md`, `prior-weighted-alpha.md`, `stability-statistic.md` | DRAFT (never run) | mark them "parked" with a date, or move them to a `prereg/drafts/` folder |
| `confidence-output.md` | DRAFT status line, but its fields are used in live reads (`quixote.confidence`) | check whether it went live elsewhere; state that in the file |
| `diagnostics-2026-10-06.md`, `estimators-exploratory-2026-10-06.md` | exploratory, closed (`6808704`) | keep |
| `etf-features.md`, `etf-universe.md` | DRAFT status line, but in use as the registered feature definition and universe (pinned X) | replace the stale DRAFT line with the commit that made them binding |
| `french-holdout-grading.md` | DRAFT, NOT LIVE; step 0 queued | keep; move the step-0 commands in from `docs/french_step0_box_commands.md` when allowed |
| `french-panel.md` | live; in-sample closed (`fc92cdb`); amendment 1 (`e1cda69`) | keep |
| `holdout-grading.md` | live, closed (`0426352`) | keep |
| `ml-pipeline-exploratory-2026-10-07.md` | exploratory, closed (`85f293a`) | keep |
| `ml-ridge-stack-confirmation.md` | live, closed (`d746a78`) | keep |
| `ml-v2-exploratory-2026-10-08.md` | exploratory; the version-2 pilot running (`817f8d2`) | keep |
| `new-panels-audit-2026-10-06.md` | audit, closed | keep |
| `planted-edge.md` | live (stage 1); stage 2 drafted | keep |
| `point-estimate.md` | DRAFT, NOT LIVE | park with a date, or decide |
| `twin-calibration.md` | DRAFT status line with live parts | check and state |

## 2. runs/: the largest directories, and whether a ledger entry cites them

| directory | size | cited in `EXPERIMENTS.md` | proposed action |
|---|---|---|---|
| `ml_pilot` | 55 MB (`pilot.jsonl` 57 MB, over GitHub's 50 MB warning) | yes (version-1 pilot) | keep; consider Git LFS or a compressed copy for new large outputs |
| `confidence_cell` | 39 MB | check | keep if cited; otherwise archive |
| `planted_edge_scripted` | 26 MB | yes (planted edge) | keep |
| `planted_agent` | 10 MB | check | keep if cited |
| `diagnostics` | 6.2 MB | yes (estimators) | keep |
| `holdout_grading` | 4.9 MB | yes (6.5) | keep |
| `planted_twins_score` | 4.0 MB | check | keep if cited |
| `ml_confirm` | 3.2 MB | yes | keep |
| `b1-baseline` … `b5-opus`, `agent_cell_*`, `etf_*`, `reanchor_s0_replay` | 0.8–2.9 MB each | the agent-arm rows cite `runs/` generally | add a per-directory line to the agent-arm entry, or archive |
| `_aborted`, `_excluded`, `_shakeout`, `_smoke` | small | `runs/EXCLUSIONS.md` covers them | keep, as the exclusion record |
| `ml_v2_smoke_box`, `ml_v2_pilot_dry` | small | not yet (untracked; fetched during the version-2 pilot) | commit with the version-2 pilot's raw outputs |

## 3. Leftovers on the laptop (untracked or gitignored)

| path | size | what it is | proposed action |
|---|---|---|---|
| `data/planted_cache/fast_1fc6c2b25e7bf95e` | 8.7 GB | Binance 4h class cache (decided build) | delete while Binance is held; rebuildable in about 9 min |
| `data/planted_cache/fast_a8c4ecf1ed1b6262` | 3.7 GB | the planted ETF panel's class cache (in use) | keep |
| `data/planted_cache/fast_912cbdc906e0a1a0` | 3.1 GB | the French class cache (pinned X) | keep until the French grading is done |
| `data/planted_cache/fast_fc1fdcfb3aa6e9cd`, `fast_72e004d48c8ed1ba`, `fast_cad54f093d46d55f` | 1.7, 1.5, 1.2 GB | Binance daily-variant class caches (exploratory) | delete; rebuildable in under a minute each |
| `data/class_tables/` | 6.5 GB (ETF K40 2.6 GB, ADR K22 3.6 GB and 0.27 GB) | full class tables | keep the ETF table; archive the ADR tables if 7.4 is closed |
| `data/raw/` | 100 MB | ETF, ADR, French and Binance in-sample derived files | keep |
| `data/pinned/` | 124 MB | the pins (ETF X, French X, v2 inputs, both v2 input files) | keep; the superseded `etf_v2_inputs.npz` (`50dec727…`) can go once the version-2 pilot is read |
| `~/Desktop/og-quarantine/{french,binance}` | — | quarantined raw zips | keep until each moves to the holdout host (French: before any grading) |
| `~/og-wheels/` | — | both LightGBM wheels | keep |
| `ckpt_h63C/` (repo root) | 384 KB | tracked checkpoint pickles at the root | move under `runs/` or remove from git, if nothing cites them |
| `logs/`, `.cache/`, `__pycache__/`, `observable_garden.egg-info/` | 11 MB, 8 MB | build and run logs | keep `logs/` (gitignored); the rest are disposable |
| `scratch/ml_stress_test.py`, `scratch/README.md` | — | non-evidence (stated in `scratch/README.md`) | keep as is, or delete when the ML arm closes |

## 4. Scripts with no caller

`experiments/unfaithful_searchers_read.py` is the only module under `experiments/` whose
name appears nowhere else in the repository (excluding `runs/`). Every other script is
named in a pre-registration, a doc, a test or another script.
- **Proposed action:** check whether its read is recorded under another name. If so, add
  a pointer; if not, it is dead code.

## 5. README sections that no longer match the findings

- **"What it has measured"** lists only the simulation results. It does not mention any
  of these:
  - the 6.5 real-data holdout read: "PASS against FAIL: no PASS (the registered B = 200
    results); 80 FAIL";
  - the agent arm (661 runs);
  - the ML results: the ridge_stack confirmation HOLDS on planted rule shapes, and the
    French in-sample read refused both tests.
  - **Proposed:** add one line each, quoted as printed.
- **"Next: a gate for agents that think"** says "In build … Nothing in this section is a
  result yet". The agent arm and the 6.5 holdout have since produced results.
  - **Proposed:** retitle it, or move the results above.
- **The adaptive rate** (from the author's standing note): at note-v1, README's 13.6%
  (the e4 configuration) is to be replaced with E21's figure, or kept with its label.
  - **Proposed:** decide at note-v1.
