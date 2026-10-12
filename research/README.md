# research/: the record behind the note

This folder is the research record of the Observable Garden project. It holds every
pre-registration and amendment, every raw output, read and figure, and the code that made them.
**Nothing here is needed to use the gate or Sancho**; the top-level `README.md` covers that.

| folder or file | what it holds |
|---|---|
| `prereg/` | every pre-registration and its amendments (append-only, dated); `DATASET_LEDGER.md`, `README.md` |
| `runs/` | raw outputs, run records and reads, one folder per run; `EXCLUSIONS.md` |
| `figures/` | figure data (`*_data.pkl`), rendered figures and their text |
| `experiments/` | the code of every experiment, runner, pricing script and reader |
| `data/` | fetch, cut and loader scripts, and committed manifests (never data values) |
| `learn/` | model version 1 (ridge_stack); `learn2/` is an alias of `sancho/` (version 2) |
| `tests/` | the tests of this record |
| `docs/` | the related-work notes and the operator sheets still cited by a registration |
| `cloud/`, `notebooks/`, `scratch/`, `ckpt_h63C/` | box scripts, notebooks, scratch work, checkpoints |
| `THEORY.md`, `SCOPE.md`, `ROADMAP.md`, `OPEN_QUESTIONS.md`, `EXPERIMENTS.md` | the long-form docs |
| `DELETED.md` | every path the cleanup deleted, with its size and reason |
| `NOTE_MAP.md` | the map from each claim in the note (distributed separately) to its registration, result and read |
| `CITATIONS.md` | what each cited source was checked for, and against which copy |

## Finding a registration or a result from the note

1. Find the claim in `research/NOTE_MAP.md`. Each row gives the experiment, its registration file
   and commit, its result commit and its read commit.
2. **A registration that is still open** is in `research/prereg/`. **One that has closed** has
   left that folder. Recover it with `git show <registration commit>:prereg/<file>`, using the
   pre-cleanup path, as `EXPERIMENTS.md` explains.
3. **The result** is in `research/runs/<name>/` or `research/figures/<name>_data.pkl`. Its run
   record is beside it.

## The old paths: the tag `pre-cleanup-2026-10-12`

The 2026-10 cleanup moved:
- this record from the repository root into `research/`;
- the engine (`estimator`, `environments`, `searchers`, `garden`) into `quixote/engine/`;
- `learn2/` to `sancho/`.

**The tag `pre-cleanup-2026-10-12` (commit `a7de2a45f538b2cafe80c84a233a63673cce86d4`) has
every path as the note, the registrations and the run records cite it.**
- `git show pre-cleanup-2026-10-12:<old path>` prints any file as it was.
- `git checkout pre-cleanup-2026-10-12` gives the whole old layout.

**What the cleanup changed in code: where files live, not what they compute.**
`research/tests/test_pins_after_cleanup.py` checks two things:
- every blob a registered runner pins still holds at the tag;
- the moved engine and Sancho differ from the tag only in import lines and data-path lines.

**Registered runners refuse to run at the new layout.** They check `learn2/...`, `learn/...` and
`environments/...` blobs at HEAD. Reproduce a registered run from its pinned commit, or from the
tag.

## Running research code in the new layout

```
pip install -e .                 # from the repository root
cd research                      # the research code runs from here, as it always ran from the folder holding prereg/
python -m experiments.<name> ...
```

- **Machine-local data** (raw downloads, pinned feature arrays, class tables, planted caches)
  is never committed. It lives at `<repo>/data/`, where it always did. Set `OG_LOCAL_DATA` to
  move it.
- **The batch runner** `experiments/run_arms.sh` expects the pre-cleanup layout. Run it from a
  checkout of the tag.
- **The tests:** run `pytest research/tests` from the repository root. They switch to
  `research/` themselves.

## The second ETF grading, fixed for 2028-01-03

`prereg/etf-recent-panel.md` (section g; amendment 2) fixes a second grading of the ETF recent
panel, from a new fetch, on 2028-01-03.
- **Its graded quantity and rule are unchanged:** the unweighted holdout net Sharpe against the
  in-sample L90.
- **Its own registration is written then,** before the new fetch.
- **It must not be built on a layout that might move again.** Branch it from the tag, which holds
  the code, registrations and inputs the first grading used.

**On the laptop, to start the 2028 work:**

```
git clone https://github.com/ben06kn-droid/observable-garden.git og-grading-2028
cd og-grading-2028
git checkout -b grading-2028 pre-cleanup-2026-10-12
# write prereg/etf-recent-grading-2028.md here, commit it alone, then make it live in a commit of its own
```

**What the first grading ran, for reference** (all reachable from the tag):
- **the grading registration:** `prereg/etf-recent-grading.md`, live at
  `2fd0346cde8903ea431acc2186e7bd5264f2d16a`;
- **the commit the holdout host checked out (G):** `31b3b2c09cfe094e5e39efe46fd834a22ef06fd2`;
- **its one-session host sheet, with every command:**
  `git show e6fba092ac9a031dfde027176ae3732020a180cf:docs/etf_recent_grading_sheet.md`;
- **its outputs and run record:** `runs/etf_recent_grade/2026-10-11/` at
  `ccfb184a8b5b459dcd580ea116af22cf43dc88a3`.

**On the holdout host, the second grading checks out the commit its own registration names.** That
commit descends from the tag on the `grading-2028` branch, so the host runs the same old-layout
commands as the first grading:

```
cd ~/observable-garden && git fetch origin --tags && git checkout <G of the 2028 registration> && git rev-parse HEAD
git merge-base --is-ancestor 2fd0346cde8903ea431acc2186e7bd5264f2d16a HEAD && echo ancestors-ok
```

- The grader is `python -m experiments.etf_recent_grade …`. Its arguments are in the first
  grading's sheet above, and the 2028 registration says how the two fetches join (the panel's
  section g leaves the volume join open).
- Nothing in `main`'s layout is needed, and the cleanup cannot break this path.

## 2026-10-12: hosts, addresses and local paths replaced by placeholders

On the branch `cleanup-2026-10`, 59 files had IP addresses, EC2 instance IDs, ssh host aliases
and local home paths replaced by fixed placeholders. **Nothing else in them changed.** Several of
these files are reads, or run records, that were committed unedited; they were changed only in
these tokens, and this section puts that edit on the record. **The originals are at the tag
`pre-cleanup-2026-10-12`** (`git show pre-cleanup-2026-10-12:<path without research/>`). History
was not rewritten.

| placeholder | replaces |
|---|---|
| `<holdout-host>` | the holdout host's instance ID and its ssh alias |
| `<compute-box>` | the compute box's instance ID, its ssh aliases and its EC2 host name |
| `<ip>` | any IP address |
| `<repo>` | the repository root on the laptop or a host |
| `<home>` | anything else under a home directory |

**Edited** (paths under `research/`):
- `cloud/`: `wait_fetch_stop.sh`
- `data/`: `fetch_etf.py`
- `docs/`: `french_holdout_checklist.md`, `french_long_operator_sheets.md`, `french_step0_box_commands.md`
- `experiments/`: `grade_real.py`, `planted_edge_read.py`, `planted_twins_prank_read.py`
- `prereg/`: `agent-on-real-data.md`, `confidence-output.md`, `etf-recent-grading.md`, `etf-recent-panel.md`, `french-holdout-grading.md`, `french-long-b1-grading.md`, `holdout-grading.md`, `planted-edge.md`, `twin-calibration.md`
- `runs/_smoke/confidence_cell/`: `draws.jsonl`
- `runs/_smoke/planted_edge_box/`: `draws.jsonl`
- `runs/_smoke/planted_twins/`: `draws.jsonl`
- `runs/_smoke/planted_twins_score_box/`: `draws.jsonl`
- `runs/agent_cell_etf_recent_priced/2026-10-11/`: `RUN_RECORD.md`
- `runs/agent_pilot/`: 5 files (`pilot_index_adr_dry.json`, `pilot_index_dry.json`, ...)
- `runs/agent_pilot_etf_seat/`: `pilot_index_etf_replay.json`
- `runs/agent_pilot_seat/`: `pilot_index_adr.json`, `pilot_index_adr_dry.json`
- `runs/agent_pilot_seat2/`: `pilot_index_adr_replay.json`
- `runs/etf_recent/2026-10-11/`: `RUN_RECORD.md`
- `runs/etf_recent_cuts/`: `RUN_RECORD.md`
- `runs/etf_recent_grade/2026-10-11/`: `RUN_RECORD.md`
- `runs/etf_repriced_b1000/control/`: `reprice_readout.txt`
- `runs/etf_repriced_b1000/declared_class/`: `reprice_readout.txt`
- `runs/etf_repriced_b1000/orientation/`: `reprice_readout.txt`
- `runs/etf_repriced_b1000/replay/`: `reprice_readout.txt`
- `runs/french_design/2026-10-07-weighted/`: `design.txt`
- `runs/french_design/2026-10-07/`: `design.txt`
- `runs/french_holdout/2026-10-09/`: `RUN_RECORD.md`
- `runs/french_long_b1/2026-10-11/`: `RUN_RECORD.md`
- `runs/french_long_b1_grade/2026-10-11-r2/`: `RUN_RECORD.md`
- `runs/french_long_cuts/`: `b1_h1_run_record.md`
- `runs/ml_confirm/ridge_stack/`: `run_record.md`
- `runs/ml_pilot/2026-10-07/`: `run_record.md`
- `runs/ml_v2_confirm/2026-10-09/`: `RUN_RECORD.md`
- `runs/ml_v2_pilot/2026-10-08/`: `run.log`, `run_record.md`
- `runs/ml_v2_pilot2/2026-10-09/`: `run.log`, `run_record.md`
- `runs/ml_v2_pilot2_dry/2026-10-09/`: `run.log`
- `runs/ml_v2_pilot_dry/2026-10-08/`: `run.log`
- `runs/ml_v2_smoke_box/2026-10-08/`: `run.log`
- `runs/ml_v2_smoke_box2/2026-10-09/`: `run.log`
- `runs/planted_agent_fidelity/`: `run_console.log`
- `runs/planted_twins_score/`: `draws.jsonl`
- `runs/recency_planted/2026-10-09/`: `RUN_RECORD.md`
- `runs/recency_planted_2/2026-10-11/`: `RUN_RECORD.md`

**Not edited, because a SHA-256 or git blob of the file is pinned** (by a registration, a run record,
a manifest, a test, a reader, or the pricing step), so one changed character would break the check:
- **pinned by hash in a run record or a reader** (11): `runs/confidence_cell/draws.jsonl`, `runs/etf_recent/2026-10-11/etf_r.log`, `runs/etf_recent_grade/2026-10-11/etfg.log`, `runs/french_long_b1/2026-10-11/fl_b1.log`, `runs/french_long_b1_grade/2026-10-11-r2/b1_holdout.cut.json`, `runs/french_long_b1_grade/2026-10-11-r2/b1g2.log`, `runs/french_long_b1_grade/2026-10-11-r2/b1g_run1.log`, `runs/ml_v2_confirm/2026-10-09/logs/v2c_dry.log`, `runs/ml_v2_confirm/2026-10-09/logs/v2c_run.log`, `runs/ml_v2_confirm/2026-10-09/logs/v2c_smoke.log`, `runs/planted_edge_scripted/draws.jsonl`;
- **manifests** (3) and **the cut record** (1): `data/binance_manifest.json`, `data/etf_manifest.json`, `data/french_manifest.json`, `runs/french_long_cuts/b1_insample.cut.json`;
- **priced records** (286): session records, whose SHA-256 the pricing step writes into each
  priced output (`experiments/price_runs.py`), and the repriced cells, which are priced outputs
  themselves. In `runs/_shakeout/planted_agent/` (4), `runs/etf_repriced_b1000/control/` (20), `runs/etf_repriced_b1000/declared_class/` (20), `runs/etf_repriced_b1000/orientation/` (20), `runs/etf_repriced_b1000/replay/` (20), `runs/planted_agent/` (202).

Some of these still carry a host name, address or local path.
