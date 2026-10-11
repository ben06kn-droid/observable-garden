# French long history: operator sheets

The registration is `prereg/french-long-history.md`. These sheets name every step, in order:
- **[H]** steps run on the holdout host, by the author;
- **[L]** steps run on the laptop;
- **[BOX]** steps run on the compute box.

Each needs its own go. Commands are one line each. On the host, packages are installed with
`uv`, never `pip`.

Placeholders, each filled in the go message for its step:
- `LIVE`: the live commit (`756af89`);
- `G1`, `G2`: the commits the host checks out (H1 ran at G1 = `b541ddf`);
- `EXPECT`: the commit the box checks out for BOX-B1 (the tip when its go is given);
- `HOST`, `BOX`: the IPs;
- `D`: the date.

**Stopping (the author's rule, 2026-10-11; it replaces that morning's "console only" wording).**
- The agent stops the holdout host (`og-holdout`) and the compute box (`og-48`) itself, from the
  laptop, with exactly this command and nothing else: `ssh <alias> 'sudo shutdown -h now'`.
- **On the holdout host, that is the only command the agent ever runs.** Every other host step
  is run by the author, in his own terminal.
- **When:** only after the author says the host work is done, or, on the box, after the outputs
  are fetched and verified.
- **Never terminate an instance, and never start one.** The author confirmed in the console
  that both instances' shutdown behaviour is "Stop".
- **Afterwards:** confirm that ssh no longer answers, and record the stop time.

`W` is `lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl` throughout.

## H1. The host cut for B1 (the author; about 10 minutes)

1. [author] Start the holdout host (`i-0886a189b85d4d051`) and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G1 && git rev-parse HEAD`
3. [H] `git merge-base --is-ancestor LIVE HEAD && echo ancestor-ok`
4. [H] `echo "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de  $HOME/french_holdout/49_Industry_Portfolios_daily_CSV.zip" | sha256sum -c`
5. [H] `mkdir -p ~/french_long`
6. [H] `.venv-grading/bin/python -m data.french_long_split --cut b1 --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b1_insample.csv`
7. [L] `mkdir -p runs/french_long_cuts && scp HOST:french_long/b1_insample.csv HOST:french_long/b1_insample.cut.json runs/french_long_cuts/`
8. [L] `shasum -a 256 runs/french_long_cuts/b1_insample.csv` (it must equal the record's `csv_sha256`)
9. [L] Commit the cut record (the JSON: counts, entry dates, hashes; no value). The CSV stays
   gitignored.
10. [L] Once the author says the host work is done: `ssh og-holdout 'sudo shutdown -h now'`. Then
    confirm ssh no longer answers, and record the stop time.

## BOX-B1. The B1 in-sample read (one box session; stop and ask at 2 box-hours)

The box checks out EXPECT exactly: the tip after H1's record, the seed and consistency
amendments and these corrections. EXPECT holds the committed cut record, and step 4a
compares the box's copy with it. Before pricing, the runner writes `pins.json` and refuses
on a cut-hash mismatch.

1. [author] Start the compute box and send its IP. [L] Set `HostName` of `og-48` to it.
2. [L] `ssh og-48 'mkdir -p ~/french_long' && scp runs/french_long_cuts/b1_insample.csv runs/french_long_cuts/b1_insample.cut.json og-48:french_long/`
3. [BOX] `cd ~/observable-garden && git fetch origin && git checkout EXPECT && git rev-parse HEAD` (must equal EXPECT; if the checkout is blocked by untracked files that match committed blobs, move them aside and record them)
4. [BOX] `git status --porcelain --untracked-files=no | wc -l` (must be 0)
4a. [BOX] `cmp ~/french_long/b1_insample.cut.json runs/french_long_cuts/b1_insample.cut.json && echo record-identical`
    (the box's copy against the committed record; **any difference: stop, nothing runs**)
4b. [BOX] `nproc --all` (record it. The run uses 4 workers × `THREADS=32`; if 128 exceeds it,
    **stop and ask. Do not change THREADS or `--workers`.**)
5. [BOX] `echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$W" | sha256sum -c`
6. [BOX] `OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_french_long_panel.py tests/test_french_long_read.py tests/test_read_french_long.py tests/test_recency.py`
7. [BOX] `THREADS=32 cloud/run.sh fl_b1 python -m experiments.french_long_read --read b1 --cuts ~/french_long/b1_insample.cut.json --out runs/french_long_b1/D --expect-head EXPECT --wheel ~/$W --workers 4`
8. [L] `rsync -av og-48:observable-garden/runs/french_long_b1/ runs/french_long_b1/; echo "exit=$?"`
9. [L] `rsync -av og-48:observable-garden/logs/fl_b1.log runs/french_long_b1/D/; echo "exit=$?"`
10. [L] After steps 8–9 exit 0 and the hashes match: `ssh og-48 'sudo shutdown -h now'`. Then
    confirm ssh no longer answers, and record the stop time.
11. [L] Commit `results.json`, `pins.json` and the run record. The run record also holds:
    `nproc --all`; the note that the runner's docstring says `--workers 6` while the run uses 4;
    and the check (not a rule) of the cut record's `entry_rule_ii` against `pins.json`'s
    entry dates. Then read once:
    `.venv/bin/python -m experiments.read_french_long --dir runs/french_long_b1/D`. Commit the
    output unedited and push.

## H2. The B1 grading (the author; on the host)

**Superseded by `docs/etf_recent_operator_sheets.md`, HOST-1, steps 11–20.** That one host
session makes the ETF fetch and cut first, then the `b1-holdout` cut and the grading.
- **The grader:** `experiments/french_long_grade.py`, under `prereg/french-long-b1-grading.md`
  (live at `00417de`).
- **The command:** `--insample-cut` and `--holdout-cut`, with `OMP_NUM_THREADS=32`, in tmux.
- **The cap:** 3.5 host-hours.
- **The stop:** the agent runs `ssh og-holdout 'sudo shutdown -h now'` after the author says the
  host work is done.

## H3. The host cut for B2 (only after B1's grading is committed)

**WITHDRAWN** (`prereg/french-long-history.md`, amendment 4, 2026-10-11): read B2 is withdrawn, so this step will not run.

1. [author] Start the host and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G2 && git rev-parse HEAD`
3. [H] `.venv-grading/bin/python -m data.french_long_split --cut b2-extra --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b2_extra.csv`
4. [L] `scp HOST:french_long/b2_extra.csv HOST:french_long/b2_extra.cut.json runs/french_long_cuts/`
5. [L] Commit the cut record. [L] Stop the host as in H1 step 10, once the author says the host work is done.

## BOX-B2. The B2 in-sample read (one box session; stop and ask at 2.5 box-hours)

**WITHDRAWN** (`prereg/french-long-history.md`, amendment 4, 2026-10-11): read B2 is withdrawn, so this step will not run.

As BOX-B1, with these two commands in place of steps 2 and 7:

2. [L] `scp runs/french_long_cuts/b1_insample.csv runs/french_long_cuts/b1_insample.cut.json runs/french_long_cuts/b2_extra.csv runs/french_long_cuts/b2_extra.cut.json og-48:french_long/ && scp data/raw/french_insample/french49_vw_daily.csv og-48:observable-garden/data/raw/french_insample/`
7. [BOX] `THREADS=32 cloud/run.sh fl_b2 python -m experiments.french_long_read --read b2 --cuts ~/french_long/b1_insample.cut.json ~/french_long/b2_extra.cut.json --insample data/raw/french_insample/french49_vw_daily.csv --out runs/french_long_b2/D --expect-head G2 --wheel ~/$W --workers 4`

## H4. The B2 grading (the author; on the host, on the existing 2020+ holdout CSV)

**WITHDRAWN** (`prereg/french-long-history.md`, amendment 4, 2026-10-11): read B2 is withdrawn, so this step will not run.

The grader for B2 is written after B2's in-sample read is committed.
1. [author] Start the host and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G2 && git rev-parse HEAD`
3. [H] `.venv-grading/bin/python -m experiments.french_long_grade --read b2 --holdout ~/french_holdout/holdout.csv --out runs/french_long_b2_grade/D --expect-head G2`
4. [L] Fetch, commit, read once. [L] Stop the host as in H1 step 10, once the author says the host work is done.

## Totals for the author

| session | host starts | host commands to paste | box session |
|---|---|---|---|
| H1 | 1 | 5 | — |
| BOX-B1 | — | — | 1 |
| H2 | 1 | 3 | — |
| H3 | 1 | 2 | — |
| BOX-B2 | — | — | 1 |
| H4 | 1 | 2 | — |
| **total** | **4** | **12** | **2** |
