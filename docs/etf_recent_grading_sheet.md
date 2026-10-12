# Operator sheet HOST-2: the ETF recent holdout grading (one holdout-host session)

**The registration:** `prereg/etf-recent-grading.md`. **The grader refuses unless it is live:**
its `GRADING` constant is set in the commit after the live one. Its parents are the panel
(`310225c`) and the cell (`00c7af1`).

**Who runs what:**
- **[H]** steps run on the holdout host (`og-holdout`, `i-0886a189b85d4d051`), **by the author, in
  his own terminal.**
- **[A-L]** steps are the author's, on the laptop.
- **[L]** steps are the agent's, on the laptop.

On the host the agent runs only the final `ssh og-holdout 'sudo shutdown -h now'`, plus any
read-only log `tail` the author explicitly allows for this session. Packages are installed with
`uv`, never `pip`.

**Placeholders, filled in the go message:**
- `G`: the commit to check out, the tip after the grading registration's constant commit;
- `LIVE`: the grading registration's live commit;
- `PRICED_SHA`: the SHA-256 of the committed `priced.json`, which is
  `388cc6f2636fcbab6a007335e76b6cc2b3dd5f529c82edf0f1c410f5aedf37c7` (`0d6f55d`);
- `D`: the date;
- `HOST`: the IP.

**The cap:** stop and ask at 2 host-hours from the grader's start. Expected runtime: 20–40 minutes.

## Steps

1. [author] Start the host and send its IP. [L] Set `HostName` of `og-holdout` to it.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout G && git rev-parse HEAD`
   - → G.
   - If the checkout is blocked by untracked files identical to committed blobs, move them to
     `~/moved_aside/D/` and record them.
3. [H] `git status --porcelain --untracked-files=no | wc -l`
   - → `0`.
4. [H] `git merge-base --is-ancestor 310225cd4932bc18e1c8e2e248cbbb133124a004 HEAD && git merge-base --is-ancestor 00c7af167f8ddb9a4874cc29b438926112360fb9 HEAD && git merge-base --is-ancestor LIVE HEAD && echo ancestors-ok`
   - → `ancestors-ok`.
5. [H] `ls ~/etf_recent/raw | wc -l; cmp ~/etf_recent/insample.cut.json runs/etf_recent_cuts/insample.cut.json && echo record-identical`
   - → `41` (40 raw responses and `fetch.json`), then `record-identical`.
6. [H] `uv pip install --python .venv-grading/bin/python --no-deps exchange_calendars==4.13.2 tzdata==2026.4 pyluach toolz korean_lunar_calendar`
   - → uv's "Installed …" lines.
   - `--no-deps`, so numpy, scipy, pandas and LightGBM are not touched.
7. [H] `.venv-grading/bin/python -c "import sys, numpy, scipy, lightgbm, exchange_calendars, hashlib, pathlib; p = pathlib.Path(lightgbm.__file__).parent / 'lib' / 'lib_lightgbm.so'; print(sys.version.split()[0], numpy.__version__, scipy.__version__, lightgbm.__version__, exchange_calendars.__version__, hashlib.sha256(p.read_bytes()).hexdigest()[:8])"`
   - → `3.14.2 2.5.3 1.18.1 4.7.0 4.13.2 573d57e8`.
   - **Anything else: stop, nothing runs.**
8. [H] `mkdir -p logs && date -u && tmux new -d -s etfg 'OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 .venv-grading/bin/python -m experiments.etf_recent_grade --cut ~/etf_recent/insample.cut.json --raw ~/etf_recent/raw --read-dir runs/etf_recent/2026-10-11 --submissions runs/agent_cell_etf_recent_priced/2026-10-11/submissions.json --submissions-sha 45cedcab7dff8d426ca8c649808c5df67bb9bef6f2b11e7085f561b1bce4066c --priced runs/agent_cell_etf_recent_priced/2026-10-11/priced.json --priced-sha 388cc6f2636fcbab6a007335e76b6cc2b3dd5f529c82edf0f1c410f5aedf37c7 --out runs/etf_recent_grade/D --expect-head G --workers 4 > logs/etfg.log 2>&1; echo "[exit $?]" >> logs/etfg.log'`
   - → the UTC start time (for the run record), then nothing: the session starts.
   - Workers × threads = 4 × 8 = 32 on 32 vCPU, as the registration's section 8 fixes.
   - **Do not change it.**
9. [H] `tail -n 30 ~/observable-garden/logs/etfg.log` (repeat as needed)
   - → `check a …: pass` lines within minutes. Then the b1 pins, the b2 lines (objects and rule
     submissions, 3 decimals), b3, and c1–c4, every one `pass`. Then
     `grades written to runs/etf_recent_grade/D/grades.json; no value printed` and `[exit 0]`.
   - **Any `FAIL` or `REFUSED`:** nothing is graded. Send the log, and the host stays up.
     - A b2 miss: the registered fallback is `--workers 1` with `THREADS=32`, only on the author's
       go.
     - A missing holdout value: the death rule is added by amendment first (registration
       section 4).
10. [A-L] `cd ~/observable-garden && rsync -av og-holdout:observable-garden/runs/etf_recent_grade/ runs/etf_recent_grade/ && scp og-holdout:observable-garden/logs/etfg.log runs/etf_recent_grade/D/; echo "exit=$?"`
    - → `exit=0`.
    - **What comes back:** `grades.json` and `etfg.log`.
11. [author] Says "host work done".
12. [L] `ssh og-holdout 'sudo shutdown -h now'`
    - Then `ssh -o ConnectTimeout=10 og-holdout true` must time out.
    - The stop time goes in the run record.
13. [L] Commit `grades.json`, the log and the run record before any read. Then the reads, once, in
    the order the author fixes (registration [AUTHOR] point 6):
    - the objects:
      `.venv/bin/python -m experiments.read_etf_recent_grade --dir runs/etf_recent_grade/D`;
    - the cell's R1–R4:
      `.venv/bin/python -m experiments.read_agent_cell_etf_recent --priced runs/agent_cell_etf_recent_priced/2026-10-11/priced.json --grades runs/etf_recent_grade/D/grades.json --out runs/agent_cell_etf_recent_read/D`.

    Commit each output unedited, and push.

## What stays on the host

- the raw fetch (`~/etf_recent/raw`, every 2025+ row) and `fetch.json`;
- the in-sample CSVs;
- the zip;
- the 2020+ French holdout;
- anything the grader builds in memory: spanning panels, positions, holdout prices and returns.

## What comes back

`grades.json` (per item: realised, net return, 90% intervals, held/not, the bound and its
statistic, the joint replicate matrices) and the grading log. Nothing else.
