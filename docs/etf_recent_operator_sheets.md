# Operator sheets: one host session (the ETF fetch and cut, then the B1 grading), and BOX-ETF

**The registrations:**
- `prereg/etf-recent-panel.md`, live at `310225cd4932bc18e1c8e2e248cbbb133124a004`;
- `prereg/french-long-b1-grading.md`, live at `00417de103785335f2b3a4b6860b7e81a1b33135`. Its
  parent `prereg/french-long-history.md` is live at `756af89`.

**Who runs what:**
- **[H]** steps run on the holdout host (`og-holdout`, `i-0886a189b85d4d051`), **by the author,
  in his own terminal.**
- **[A-L]** steps run on the laptop by the author: copies from the host.
- **[L]** steps run on the laptop by the agent: checks and commits.
- **[BOX]** steps run on the compute box (`og-48`, `i-0e0c1484de3c755ad`).

Each session needs the author's own go. Commands are one line each. Packages are installed with
`uv`, never `pip`.

**Stopping (the author's rule, 2026-10-11).**
- The agent stops either machine with exactly `ssh <alias> 'sudo shutdown -h now'`, and nothing
  else.
- **On the holdout host, that is the only command the agent ever runs.**
- It runs only after the author says the host work is done, or, on the box, after the outputs
  are fetched and verified.
- Never terminate, never start. Both instances' shutdown behaviour is "Stop", confirmed by the
  author in the console.
- Afterwards the agent confirms ssh no longer answers and records the stop time.

**Placeholders, filled in the go message:**
- `G`: the commit the host checks out;
- `EXPECT`: the commit the box checks out;
- `D`: the date;
- `HOST`: the IP.

`W` is `lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`.

## HOST-1. One holdout-host session: the ETF fetch and cut, then the B1 holdout cut and grading

**The cap:** the B1 grading stops and asks at 3.5 host-hours (its registration). The ETF part
takes minutes. Each step gives the command, then **→** the expected output, then **writes:**
what it writes.

**Setup**

1. [author] Start the host and send its IP. [L] Set `HostName` of `og-holdout` to it.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G && git rev-parse HEAD`
   - → G.
   - If the checkout is blocked by untracked files identical to committed blobs, move them to
     `~/moved_aside/D/` and record them.
3. [H] `git status --porcelain --untracked-files=no | wc -l`
   - → `0`.
4. [H] `git merge-base --is-ancestor 310225cd4932bc18e1c8e2e248cbbb133124a004 HEAD && git merge-base --is-ancestor 00417de103785335f2b3a4b6860b7e81a1b33135 HEAD && echo ancestors-ok`
   - → `ancestors-ok`.

**The ETF fetch and cut** (a venv of their own, so `.venv-grading` is not changed)

5. [H] `uv venv ~/venv-fetch --python 3.14 && uv pip install --python ~/venv-fetch/bin/python exchange_calendars==4.13.2 tzdata==2026.4`
   - → uv's "Installed …" lines.
   - **writes:** `~/venv-fetch`.
6. [H] `~/venv-fetch/bin/python -c "import importlib.metadata as m; print(m.version('exchange_calendars'), m.version('tzdata'))"`
   - → `4.13.2 2026.4`.
7. [H] `~/venv-fetch/bin/python -m data.fetch_etf_recent --out ~/etf_recent/raw`
   - → 40 lines `  TICKER: HTTP 200, n bars, 2005-01-03 .. <last day>`, then
     `FETCH DONE: 40 of 40 HTTP 200; record …/fetch.json; no value printed`.
   - **writes:** `~/etf_recent/raw/<TICKER>.json`, the 40 raw responses as received, and
     `fetch.json` (URLs, HTTP codes, SHA-256s). **Both stay on the host.**
8. [H] `~/venv-fetch/bin/python -m data.etf_recent_cut --raw ~/etf_recent/raw --out ~/etf_recent/insample`
   - → `cut: N of 40 included (…); last fetched session YYYY-MM-DD; combined SHA-256 …; record insample.cut.json; no value printed`.
   - **writes:**
     - `~/etf_recent/insample/<TICKER>.csv`, 2005-01-03..2024-12-31;
     - `~/etf_recent/insample.cut.json`: counts, dates, 2005–2014 volume medians and hashes; no
       price.

**If step 7 shows any ticker other than HTTP 200, or step 8 prints REFUSED:**
- Stop the ETF part, and send the output to the agent.
- Possible reasons: a no-data ticker, fewer than 30 included, or a 2015–2024 gap.
- Nothing more runs for the ETF panel. The record is still written, and its counts may be sent.
- The B1 part may continue.

**Rows from 2025-01-01 never leave the host.** They are only in the raw responses.

9. [A-L] `cd ~/observable-garden && mkdir -p runs/etf_recent_cuts && scp -r og-holdout:etf_recent/insample og-holdout:etf_recent/insample.cut.json runs/etf_recent_cuts/`
   - → scp's file lines.
   - **writes, on the laptop:** `runs/etf_recent_cuts/insample/*.csv` (gitignored) and
     `runs/etf_recent_cuts/insample.cut.json`.
10. [L] The agent:
    - checks each CSV's SHA-256 and the combined SHA-256 against the record;
    - confirms the CSVs are gitignored;
    - commits **only the record**, with a run record.

**The B1 holdout cut and grading**

11. [H] `echo "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de  $HOME/french_holdout/49_Industry_Portfolios_daily_CSV.zip" | sha256sum -c`
    - → `…zip: OK`.
12. [H] `.venv-grading/bin/python -m data.french_long_split --cut b1-holdout --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip --out ~/french_long/b1_holdout.csv`
    - → `b1-holdout: <about 1517> rows 19900102 .. 19951229; SHA-256 …; record b1_holdout.cut.json; no value printed`.
    - **writes:** `~/french_long/b1_holdout.csv` (**stays on the host**) and
      `~/french_long/b1_holdout.cut.json`.
13. [H] `sha256sum ~/french_long/b1_insample.csv`
    - → `c380c3eaa578734a4de8c019220b5babce9c2e6adc3f7a6175a68999d4910693` (H1's cut, still on
      the host).
14. [H] `.venv-grading/bin/python -c "import lightgbm, hashlib, pathlib; p = pathlib.Path(lightgbm.__file__).parent / 'lib' / 'lib_lightgbm.so'; print(lightgbm.__version__, hashlib.sha256(p.read_bytes()).hexdigest())"`
    - → `4.7.0 573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a`.
    - If not: `uv pip install --python .venv-grading/bin/python --no-deps ~/lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`,
      then repeat this step.
15. [H] `mkdir -p logs && tmux new -d -s b1g 'OMP_NUM_THREADS=32 OPENBLAS_NUM_THREADS=32 MKL_NUM_THREADS=32 .venv-grading/bin/python -m experiments.french_long_grade --read b1 --insample-cut ~/french_long/b1_insample.cut.json --holdout-cut ~/french_long/b1_holdout.cut.json --out runs/french_long_b1_grade/D --expect-head G --workers 4 > logs/b1g.log 2>&1; echo "[exit $?]" >> logs/b1g.log'`
    - → nothing; the session starts.
    - **writes:** `runs/french_long_b1_grade/D/grades.json` and `logs/b1g.log`.
    - It runs four Sancho fits. Estimate: 45–75 minutes.
16. [H] `tail -n 30 logs/b1g.log` (repeat as needed)
    - → one `check …: pass` line per check (b1–c4), then `grades written to …; no value printed`
      and `[exit 0]`.
    - **Any `FAIL` or `REFUSED`: nothing is graded.** Send the log; the host stays up.
    - **The cap:** at 3.5 host-hours from the start of the host, stop and ask, whatever the log
      shows.
17. [A-L] `cd ~/observable-garden && rsync -av og-holdout:observable-garden/runs/french_long_b1_grade/ runs/french_long_b1_grade/ && scp og-holdout:observable-garden/logs/b1g.log og-holdout:french_long/b1_holdout.cut.json runs/french_long_b1_grade/D/; echo "exit=$?"`
    - → `exit=0`.
    - **writes, on the laptop:** `grades.json`, `b1g.log`, and `b1_holdout.cut.json` (counts and
      dates, no value).
18. [author] Says "host work done".
19. [L] `ssh og-holdout 'sudo shutdown -h now'`
    - Then `ssh -o ConnectTimeout=10 og-holdout true` must time out.
    - The stop time goes in the run record.
20. [L] Commit `grades.json`, the log, the holdout cut record and the run record before the read.
    Then read once:
    `.venv/bin/python -m experiments.read_french_long_grade --dir runs/french_long_b1_grade/D`.
    Commit its output unedited, and push.

**What comes back to the laptop:**
- the ETF in-sample CSVs (gitignored) and their cut record;
- B1's `grades.json`, the grading log and the `b1-holdout` cut record.

**What stays on the host:** the raw ETF responses and `fetch.json`, every row from 2025 on,
the `b1-holdout` CSV, the zip, and the 2020+ French holdout.

## BOX-ETF. The ETF in-sample read (one box session; stop and ask at 1 box-hour)

The box checks out EXPECT exactly. EXPECT holds the committed ETF cut record.

**Step 0: free the disk first.** At B1's end the box had 35 GB used of 48 GB.
- B1's class cache is `data/planted_cache/fast_7c02af63f340181d/`, about 22 GB. Its key was
  seen during the run as `.fast_7c02af63f340181d.4577.tmp`.
- The run record is `runs/french_long_b1/2026-10-11/RUN_RECORD.md`. X at d = 1 is (16,829, 49, 40).
- The ETF read needs about 6.3 GB for its cache: 82,240 × 4,778 × 8 bytes × 2 arrays (g and k).

0a. [BOX] `cd ~/observable-garden && df -h ~ | tail -1 && du -sh data/planted_cache/* data/class_tables/* 2>/dev/null`
    - → the usage, and the cache directories with their sizes.
0b. [BOX] `cat data/planted_cache/fast_7c02af63f340181d/manifest.json`
    - → `"class": "french-long-b1-signed-3"`, `"N": 82240`, `"T": 16829`.
0c. [BOX] Only if 0b matches exactly: `rm -r data/planted_cache/fast_7c02af63f340181d data/planted_cache/fast_7c02af63f340181d.lock && df -h ~ | tail -1`
    - → about 22 GB more free. At least 15 GB free is needed.
    - **If 0b differs, or 0a lists anything not identified by a run record:** do not delete it.
      Move it aside to `~/moved_aside/D/`, which frees no space on this disk; record it; stop
      and ask.
    - If the agent's session is blocked from deleting, the author runs 0c himself.

**The run**

1. [author] Start the box and send its IP. [L] Set `HostName` of `og-48` to it.
2. [L] `ssh og-48 'mkdir -p ~/etf_recent' && scp -r runs/etf_recent_cuts/insample runs/etf_recent_cuts/insample.cut.json og-48:etf_recent/`
3. [BOX] `cd ~/observable-garden && git fetch origin && git checkout EXPECT && git rev-parse HEAD`
   - → EXPECT. Identical untracked files are moved aside and recorded.
4. [BOX] `git status --porcelain --untracked-files=no | wc -l`
   - → `0`.
   - 4a. [BOX] `cmp ~/etf_recent/insample.cut.json runs/etf_recent_cuts/insample.cut.json && echo record-identical`
     - → `record-identical`. **Any difference: stop, nothing runs.**
   - 4b. [BOX] `nproc --all`
     - → at least 128; record it.
     - If it is less, stop and ask. Do not change THREADS or `--workers`.
5. [BOX] `echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$W" | sha256sum -c`
   - → `…whl: OK`.
6. [BOX] `OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_etf_recent_read.py tests/test_read_etf_recent.py tests/test_etf_recent_integration.py tests/test_recency.py`
   - → all passed.
7. [BOX] `THREADS=32 cloud/run.sh etf_r python -m experiments.etf_recent_read --cut ~/etf_recent/insample.cut.json --out runs/etf_recent/D --expect-head EXPECT --wheel ~/$W --workers 4`
   - → `started 'etf_r' in tmux`.
   - Then `pins.json` appears, and finally `results written …; no outcome printed` and
     `[exit 0]`.
   - Any REFUSED: stop.
8. [L] `rsync -av og-48:observable-garden/runs/etf_recent/ runs/etf_recent/; echo "exit=$?"`
   - → `exit=0`.
9. [L] `rsync -av og-48:observable-garden/logs/etf_r.log runs/etf_recent/D/; echo "exit=$?"`
   - → `exit=0`, and the SHA-256s are equal on both sides.
10. [L] `ssh og-48 'sudo shutdown -h now'`
    - Then `ssh -o ConnectTimeout=10 og-48 true` must time out.
    - The stop time is recorded.
11. [L] Commit `results.json`, `pins.json`, the log and the run record. Then read once:
    `.venv/bin/python -m experiments.read_etf_recent --dir runs/etf_recent/D`.
    Commit the output unedited, and push.

**The cap:** at 1 box-hour from the box's start, stop and ask, whatever the projection.

**Estimate, from the smoke** (`runs/etf_recent_smoke/2026-10-11/`; laptop, synthetic 40 × 5,033):
- **Sancho:** one fit took 88 s on the laptop (27 s rolling, 56 s expanding). On the box, fits
  ran about 3.3× slower each in BOX-B1, so the four fits in parallel take about 5 minutes.
- **The class:** the table about 5 minutes, the W2 null about 3 and the unweighted null about
  the same again. The cache (g and k) is 6.29 GB.
- **In all:** about 20–30 minutes, with setup.
