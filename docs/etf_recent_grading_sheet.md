# Operator sheet HOST-2: the ETF recent holdout grading (one holdout-host session)

**The registration:** `prereg/etf-recent-grading.md`, **live at `2fd0346cde8903ea431acc2186e7bd5264f2d16a`**. The grader's
`GRADING` constant is set at `3df6bbe`. **The grader refuses unless the registration is live,**
and its parents too: the panel (`310225c`) and the cell (`00c7af1`).

**Filled in:**
- **G** = `31b3b2c09cfe094e5e39efe46fd834a22ef06fd2`. The host checks it out. It holds the live registration, the constant, the
  session-list script (`31b3b2c`), and the committed `submissions.json` and `priced.json`.
- **LIVE** = `2fd0346cde8903ea431acc2186e7bd5264f2d16a`.
- **D** = `2026-10-11`.

**Who runs what:**
- **[H]** steps run on the holdout host (`og-holdout`, `i-0886a189b85d4d051`), **by the author, in
  his own terminal.**
- **[A-L]** steps are the author's, on the laptop.
- **[L]** steps are the agent's, on the laptop.

On the host the agent runs only the final `ssh og-holdout 'sudo shutdown -h now'`, plus any
read-only `tail` of the grading log the author explicitly allows for this session.

**No package is installed into `.venv-grading`.** The holdout session list comes from
`~/venv-fetch`.

**The threads are fixed:** 4 workers × 8 threads = 32 on 32 vCPU. **The cap:** stop and ask at 2
host-hours from the grader's start. Expected runtime: 20–40 minutes.

## Steps

1. [author] Start the host and send its IP. [L] Set `HostName` of `og-holdout` to it.
2. [H] `cd ~/observable-garden && git fetch origin && git checkout 31b3b2c09cfe094e5e39efe46fd834a22ef06fd2 && git rev-parse HEAD`
   - → `31b3b2c09cfe094e5e39efe46fd834a22ef06fd2`.
   - If the checkout is blocked by untracked files identical to committed blobs, move them to
     `~/moved_aside/2026-10-11/` and record them.
3. [H] `git status --porcelain --untracked-files=no | wc -l`
   - → `0`.
4. [H] `git merge-base --is-ancestor 310225cd4932bc18e1c8e2e248cbbb133124a004 HEAD && git merge-base --is-ancestor 00c7af167f8ddb9a4874cc29b438926112360fb9 HEAD && git merge-base --is-ancestor 2fd0346cde8903ea431acc2186e7bd5264f2d16a HEAD && echo ancestors-ok`
   - → `ancestors-ok`.
5. [H] `ls ~/etf_recent/raw | wc -l; cmp ~/etf_recent/insample.cut.json runs/etf_recent_cuts/insample.cut.json && echo record-identical`
   - → `41`, then `record-identical`.
6. [H] `~/venv-fetch/bin/python -m data.etf_recent_sessions --cut ~/etf_recent/insample.cut.json --out ~/etf_recent/holdout_sessions.json`
   - → `holdout sessions: 444, 2025-01-02 .. 2026-10-09 (exchange_calendars 4.13.2, tzdata 2026.4); SHA-256 <64 hex>; written /home/ubuntu/etf_recent/holdout_sessions.json; no value printed`.
   - Calendar dates only. It stays on the host, and its hash goes into `grades.json`.
7. [H] `.venv-grading/bin/python -c "import sys, importlib.util, numpy, scipy, lightgbm, hashlib, pathlib; p = pathlib.Path(lightgbm.__file__).parent / 'lib' / 'lib_lightgbm.so'; print(sys.version.split()[0], numpy.__version__, scipy.__version__, lightgbm.__version__, hashlib.sha256(p.read_bytes()).hexdigest()[:8], importlib.util.find_spec('exchange_calendars') is None)"`
   - → `3.14.2 2.5.3 1.18.1 4.7.0 573d57e8 True`.
   - That is the grading environment untouched, with no exchange_calendars in it.
   - **Anything else: stop, nothing runs.**
8. [H] `cd ~/observable-garden && mkdir -p logs && date -u && S=$(sha256sum ~/etf_recent/holdout_sessions.json | cut -c1-64) && echo "sessions sha $S" && tmux new -d -s etfg "OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 .venv-grading/bin/python -m experiments.etf_recent_grade --cut ~/etf_recent/insample.cut.json --raw ~/etf_recent/raw --sessions ~/etf_recent/holdout_sessions.json --sessions-sha $S --read-dir runs/etf_recent/2026-10-11 --submissions runs/agent_cell_etf_recent_priced/2026-10-11/submissions.json --submissions-sha 45cedcab7dff8d426ca8c649808c5df67bb9bef6f2b11e7085f561b1bce4066c --priced runs/agent_cell_etf_recent_priced/2026-10-11/priced.json --priced-sha 388cc6f2636fcbab6a007335e76b6cc2b3dd5f529c82edf0f1c410f5aedf37c7 --out runs/etf_recent_grade/2026-10-11 --expect-head 31b3b2c09cfe094e5e39efe46fd834a22ef06fd2 --workers 4 > logs/etfg.log 2>&1; echo [exit \$?] >> logs/etfg.log"`
   - → the UTC start time, then `sessions sha <the same 64 hex as step 6>`, then nothing: the
     session starts.
   - **Do not change the threads or `--workers`.**
9. [H] `tail -n 30 ~/observable-garden/logs/etfg.log` (repeat as needed)
   - → `check a …: pass` lines within minutes, including "a holdout session list pinned and
     matching the cut record" and "a holdout sessions complete, none missing; boundary close
     matches".
   - Then b1 (pins), b2 (3 decimals, for the objects and every rule submission), b3, and c1–c4,
     every one `pass`.
   - Then `grades written to runs/etf_recent_grade/2026-10-11/grades.json; no value printed` and `[exit 0]`.
   - **Any `FAIL` or `REFUSED`:** nothing is graded. Send the log, and the host stays up.
     - A b2 miss: the registered fallback is `--workers 1` with `THREADS=32`, only on the author's
       go.
     - A missing or extra holdout date: the death rule is added by amendment first.
10. [A-L] `cd ~/observable-garden && rsync -av og-holdout:observable-garden/runs/etf_recent_grade/ runs/etf_recent_grade/ && scp og-holdout:observable-garden/logs/etfg.log runs/etf_recent_grade/2026-10-11/; echo "exit=$?"`
    - → `exit=0`.
    - **What comes back:** `grades.json` and `etfg.log`. Nothing else.
11. [author] Says "host work done".
12. [L] `ssh og-holdout 'sudo shutdown -h now'`
    - Then `ssh -o ConnectTimeout=10 og-holdout true` must time out.
    - The stop time goes in the run record.
13. [L] Commit `grades.json`, the log and the run record before any read. Then **the reads, in
    one sitting, each once, each committed unedited:**
    1. the panel's three objects:
       `.venv/bin/python -m experiments.read_etf_recent_grade --dir runs/etf_recent_grade/2026-10-11`;
    2. the cell's R1–R4, in order:
       `.venv/bin/python -m experiments.read_agent_cell_etf_recent --priced runs/agent_cell_etf_recent_priced/2026-10-11/priced.json --grades runs/etf_recent_grade/2026-10-11/grades.json --out runs/agent_cell_etf_recent_read/2026-10-11`.

    Then push.

## What stays on the host

- the raw fetch (`~/etf_recent/raw`, every 2025+ row) and `fetch.json`;
- `holdout_sessions.json`, whose hash is recorded in `grades.json`;
- the in-sample CSVs;
- the zip;
- the 2020+ French holdout;
- everything the grader builds in memory: spanning panels, positions, holdout prices and
  returns.

## What comes back

`grades.json` (per item: realised, net return, 90% intervals, held/not, the bound and its
statistic, the joint replicate matrices, the session list's hash) and the grading log.
