# French long history: operator sheets (DRAFT; nothing runs before the registration is live)

The registration is `prereg/french-long-history.md`. These sheets name every step, in order:
- **[H]** steps run on the holdout host, by the author;
- **[L]** steps run on the laptop;
- **[BOX]** steps run on the compute box.

Each needs its own go. Commands are one line each. On the host, packages are installed with
`uv`, never `pip`.

Placeholders, each filled in the go message for its step:
- `LIVE`: the live commit;
- `G1`, `G2`: the commits to check out for each session;
- `HOST`, `BOX`: the IPs;
- `D`: the date.

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
10. [author] Stop the host: `ssh HOST 'sudo shutdown -h now'`

## BOX-B1. The B1 in-sample read (one box session)

1. [author] Start the compute box and send its IP. [L] Set `HostName` of `og-48` to it.
2. [L] `ssh og-48 'mkdir -p ~/french_long' && scp runs/french_long_cuts/b1_insample.csv runs/french_long_cuts/b1_insample.cut.json og-48:french_long/`
3. [BOX] `cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD` (must equal G1; move aside and record any untracked files that match committed blobs)
4. [BOX] `git status --porcelain --untracked-files=no | wc -l` (must be 0)
5. [BOX] `echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$W" | sha256sum -c`
6. [BOX] `OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_french_long_panel.py tests/test_french_long_read.py tests/test_read_french_long.py tests/test_recency.py`
7. [BOX] `THREADS=32 cloud/run.sh fl_b1 python -m experiments.french_long_read --read b1 --cuts ~/french_long/b1_insample.cut.json --out runs/french_long_b1/D --expect-head G1 --wheel ~/$W --workers 4`
8. [L] `rsync -av og-48:observable-garden/runs/french_long_b1/ runs/french_long_b1/; echo "exit=$?"`
9. [L] `rsync -av og-48:observable-garden/logs/fl_b1.log runs/french_long_b1/D/; echo "exit=$?"`
10. [L] `ssh og-48 'sudo shutdown -h now'`
11. [L] Commit `results.json` and the run record. Then read once:
    `.venv/bin/python -m experiments.read_french_long --dir runs/french_long_b1/D`. Commit the
    output unedited and push.

## H2. The B1 grading (the author; on the host)

The grader (`experiments/french_long_grade.py`) is written after B1's in-sample read is
committed, under its own grading registration, as on French.
1. [author] Start the host and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G2 && git rev-parse HEAD`
3. [H] `.venv-grading/bin/python -m data.french_long_split --cut b1-holdout --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b1_holdout.csv`
4. [H] `.venv-grading/bin/python -m experiments.french_long_grade --read b1 --insample ~/french_long/b1_insample.cut.json --holdout ~/french_long/b1_holdout.cut.json --out runs/french_long_b1_grade/D --expect-head G2`
5. [L] `rsync -av HOST:observable-garden/runs/french_long_b1_grade/ runs/french_long_b1_grade/; echo "exit=$?"`
6. [L] Commit, then read once. [author] Stop the host.

## H3. The host cut for B2 (only after B1's grading is committed)

1. [author] Start the host and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G2 && git rev-parse HEAD`
3. [H] `.venv-grading/bin/python -m data.french_long_split --cut b2-extra --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b2_extra.csv`
4. [L] `scp HOST:french_long/b2_extra.csv HOST:french_long/b2_extra.cut.json runs/french_long_cuts/`
5. [L] Commit the cut record. [author] Stop the host.

## BOX-B2. The B2 in-sample read (one box session)

As BOX-B1, with these two commands in place of steps 2 and 7:

2. [L] `scp runs/french_long_cuts/b1_insample.csv runs/french_long_cuts/b1_insample.cut.json runs/french_long_cuts/b2_extra.csv runs/french_long_cuts/b2_extra.cut.json og-48:french_long/ && scp data/raw/french_insample/french49_vw_daily.csv og-48:observable-garden/data/raw/french_insample/`
7. [BOX] `THREADS=32 cloud/run.sh fl_b2 python -m experiments.french_long_read --read b2 --cuts ~/french_long/b1_insample.cut.json ~/french_long/b2_extra.cut.json --insample data/raw/french_insample/french49_vw_daily.csv --out runs/french_long_b2/D --expect-head G2 --wheel ~/$W --workers 4`

## H4. The B2 grading (the author; on the host, on the existing 2020+ holdout CSV)

The grader for B2 is written after B2's in-sample read is committed.
1. [author] Start the host and send its IP.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G2 && git rev-parse HEAD`
3. [H] `.venv-grading/bin/python -m experiments.french_long_grade --read b2 --holdout ~/french_holdout/holdout.csv --out runs/french_long_b2_grade/D --expect-head G2`
4. [L] Fetch, commit, read once. [author] Stop the host.

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
