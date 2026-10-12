# Run directories

Every directory under `runs/`, what wrote it, and the commit that recorded it. Each
agent run is one JSON file. Each scripted run is one `draws.jsonl`, one line per seed,
and is written resumably (`experiments/_resume.load_done`). A run's registration is in
`prereg/`, or in the removed table of `EXPERIMENTS.md` once it has closed.

**Results are committed before anything reads them.** A `read.txt` beside a results
file is the registered reader's output, committed separately and citing both commits.

## Scripted cells

| directory | what | registration | committed |
|---|---|---|---|
| `planted_edge_scripted/` | 7.5 stage 1, the scripted curve: seeds 600000–601999, four levels, six searchers, B = 1,000. **Running; fetched and committed unread when it ends** | `prereg/planted-edge.md` | — |
| `planted_edge_scripted_replication/` | only if a rule-1 rule fails high: 610000–611999 (`planted_edge --replication`). Does not exist | `prereg/planted-edge.md` | — |
| `planted_edge_preflight.{json,txt}`, `planted_edge_null_check.json`, `planted_edge_population_levels.json` | 7.5 design-block checks, seeds 640000–640020 | `prereg/planted-edge.md` | `0cbb6d1`, `fc6aa7c` |
| `planted_twins_score/` | twin calibration, score-rank cell: 1,000 panels, `draws.jsonl`, the run log and `read.txt`. Closed | `prereg/twin-calibration.md` | results `1affdd1`, read `1fc432a` |

## Smoke runs (`_smoke/`): cost only, never read for a rule

| directory | what |
|---|---|
| `_smoke/planted_edge/` | 7.5 laptop smokes (980000–980007) |
| `_smoke/planted_edge_box/` | 7.5 box smoke, 980000–980190 at 191 workers; the sizing measurement (`58167e8`) |
| `_smoke/planted_twins/` | empty and untracked (git keeps no empty directory) |
| `_smoke/planted_twins_score/` | score-rank laptop smoke (`c831f1a`) |
| `_smoke/planted_twins_score_box/` | score-rank box smoke, 985000–985190 (`f840875`) |

## Agent runs on real ETF data (6.5)

`etf_control/`, `etf_declared_class/` (`3f6c189`), `etf_replay/`, `etf_orientation/`
(logs `62644b8`, priced `43cd139`): 20 runs per arm, 80 in all, against a registered
120; the deviation is in `prereg/agent-on-real-data.md`. These 80 are the submissions
the 6.9 grading (`prereg/holdout-grading.md`, draft) seals and grades.
`agent_cell_read_cells12_checks34.txt` and `agent_cell_read_cell3.txt` are its reads
(cell 3: `7cdc469`). `shakeout_etf_orientation/` is the harness shakeout before the
cell, not part of it.

## The agent cell (7.3) and its pilots

| directory | what |
|---|---|
| `agent_cell_s0_{control,replay,orientation,reasoned}/`, `agent_cell_s3_{replay,orientation,reasoned}/` | the 7.3 agent cell (`prereg/agent-cell.md`); `regrade_*.json` files are dated regrades, beside the originals |
| `reanchor_s0_replay/`, `reanchor_s3_replay/` | amendment 13's re-anchoring runs (read `8e47868`) |
| `shakeout_s0_*`, `shakeout2_s0_*` | harness shakeouts before the cell |
| `agent_pilot/`, `agent_pilot_seat/`, `agent_pilot_seat2/`, `agent_pilot_etf_seat/` | the pilots (`prereg/agent-pilot.md`) |
| `self_enforcement_exploratory.txt` | headed EXPLORATORY (`aa428d2`); no rule reads it |

## The agent arm's batches

`b1-baseline/` to `b5-opus/`, `cells-pooled.csv`, `_aborted/`, `_excluded/`,
`EXCLUSIONS.md` and `s0_control_000_T500/` (the first single run): the section below.

## Not in git

`.gitignore` keeps these out:

- `logs/`, `runs/_logs/` and `runs/_logs_batch2/`, the runner logs. A registered run's
  own log is copied into its results directory and committed there.
- `data/class_tables/`, the enumerated class matrices, 0.27–3.6 GB each and rebuilt
  from code.
- `data/pinned/`, the pinned feature matrix X, 52 MB. Its SHA-256 is registered and
  `pinned_features` refuses a mismatch.
- `data/planted_cache/`, `data/raw/`, and any sealed-holdout copy (`*.enc`, `*.gpg`,
  `*.asc`, `Desktop/`).

The largest tracked files under `runs/` are `planted_twins_score/draws.jsonl` (about
4 MB) and the batch archives (`raw.tar.gz`, up to about 2.7 MB). Scaling the box smoke's
180 KB for 191 seeds, the curve's `draws.jsonl` should be about 2 MB. Outside `runs/`,
four tracked `figures/*_data.pkl` files are 9.6–18 MB each.

---

# The agent arm's runs (batch detail)

662 run directories holding 4,627 files, reduced to five batch folders. The raw
logs are archived here byte-identically; nothing was thrown away.

## Why this shape

Nothing read the directories one at a time. Every regressor the analysis uses
is a per-run scalar, and the 61,123 logged `evaluate` calls are consumed only
as a count. Of the 48 MB on disk, 18 MB was `assistant_usage_raw` — a field no
analysis has ever read — and about a third of each transcript was redundant:
`tool_result.args` repeating the preceding `tool_use.input`, and
`tool_result.text` rendering `sr_is` and `n_evaluated` from the same record
through one of three fixed templates.

A **batch** is the real unit. Each is a pre-registered amendment with its own
schedule file under `experiments/` and its own model and arm allocation. Cells
cross batches — `s0 control sonnet` is 40 runs in b1, 30 in b2 and 30 in b3 —
and the analysis already compares both within and across them. Making the batch
the folder makes that visible, and leaves pooling as one deliberate step in
`cells-pooled.csv`.

| folder | seeds | runs | cells | allocation |
|---|---|---|---|---|
| `b1-baseline/` | 0–79 | 80 | 2 | the original s0 control/gate arm, Sonnet, before the model tag existed |
| `b2-arms/` | 80–319, 500 | 241 | 8 | amendment 4: the count and budget arms, and the first s3 cells at σ=1 |
| `b3-models/` | 320–499 | 180 | 6 | amendment 7: the pushed arm, Sonnet against Fable |
| `b4-s3-recal/` | 501–580 | 80 | 2 | amendment 9: s3 at the recalibrated σ=194.407, Sonnet |
| `b5-opus/` | 581–660 | 80 | 2 | amendments 11 and 12: s3 at the recalibrated σ, Opus |

## What is in a batch folder

| file | what it is |
|---|---|
| `BATCH.md` | what ran and what it showed. The part written for a person. |
| `cells.csv` | one row per cell: medians, IQRs, verdict counts, cost. |
| `runs.csv` | one row per run, `load_run()`'s fields exactly. Machine input. |
| `raw.tar.gz` | the run directories, byte-identical. |
| `SHA256SUMS` | a checksum per archived file. |

Every CSV cell is JSON-encoded, so the tables round-trip `load_run()`'s types
exactly — `str`, `float`, `bool`, `None`, and the three list-valued fields
alike. That costs a little readability in a spreadsheet and buys exactness,
which is the property that matters: `runs.csv` is what makes the paired and
unpaired comparisons reproducible, not something to read.

## Regenerating

```
python -m experiments.build_manifest --verify     # rebuild the tables, check round-trip
python -m experiments.analyze_agent               # reads the manifest by default
```

`analyze_agent` reads `runs.csv` unless given `--from-dirs`, which walks raw run
directories instead and needs them unpacked from `raw.tar.gz` first. The two
paths produce byte-identical output; that equality is what licensed removing the
directories, and it is worth re-checking after any change to `load_run()`.

`build_manifest` never overwrites a `BATCH.md`. The tables regenerate, the prose
does not.

## Recovering a run

```
tar xzf runs/b2-arms/raw.tar.gz s0_T5000_sonnet_count_314/
shasum -c runs/b2-arms/SHA256SUMS      # from a directory holding the unpacked runs
```

Exclusions, aborted runs and the three irregular runs the analysis retains are
in `EXCLUSIONS.md`.
