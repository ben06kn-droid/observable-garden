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

## Finding a registration or a result from the note

1. Find the claim in `paper/NOTE_MAP.md`. Each row gives the experiment, its registration file
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
