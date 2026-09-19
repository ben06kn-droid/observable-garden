# The agent arm's runs

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
