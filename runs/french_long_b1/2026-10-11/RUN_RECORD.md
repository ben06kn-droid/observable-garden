# French long history, BOX-B1: the B1 in-sample read, run record, 2026-10-11

**The registration:** `prereg/french-long-history.md`, live at `756af89`, with amendments 1
(`1fcbfc2`) and 2 (`27e8a10`).
**The sheet:** `docs/french_long_operator_sheets.md`, BOX-B1, as written at EXPECT.
**The go:** the author's, for this run only. EXPECT = `ca4b68616124f37f8df60f2279d2edcb1afb6df4`.
**The box:** `og-48` (`i-0e0c1484de3c755ad`), IP 3.139.101.168. Started by the author at 07:58
CDT (12:58 UTC). The stop-and-ask time was 09:58 CDT.

## Steps

1. `og-48`'s HostName was set to 3.139.101.168, and ssh connected. `origin/main` was already at
   EXPECT, so there was nothing to push.
2. Both cut files were copied to `~/french_long/`. `sha256sum` of the CSV on the box gave
   `c380c3eaa578734a4de8c019220b5babce9c2e6adc3f7a6175a68999d4910693`.
3. **The checkout was blocked** by five untracked files.
   - Each one's `git hash-object` equalled its blob at EXPECT:

     | file | blob |
     |---|---|
     | `runs/recency_planted_2/2026-10-11/provenance.json` | `33ab24bf55e5b56fd6786b2d0c153706a532dc96` |
     | `runs/recency_planted_2/2026-10-11/results.jsonl` | `d1c2b93e2691feb793c49b85645c6af23d74036f` |
     | `runs/recency_planted_2_dry/2026-10-11/dry_check.txt` | `cf804b9558a9c4bb7d8869a480270c961168aa5a` |
     | `runs/recency_planted_2_dry/2026-10-11/provenance.json` | `ab779a4ecaaa60fe08f757feb8973bcfaa0986d4` |
     | `runs/recency_planted_2_dry/2026-10-11/results.jsonl` | `64551b5e6d3fa1b3bf8d0e960132a2349011f888` |

   - The author moved them to `~/moved_aside/2026-10-11-boxb1/` ("moved-identical"). His
     command re-checked each blob before each move. Claude Code's permission classifier had
     blocked the same move from the agent's session.
   - Then `git checkout`: HEAD = `ca4b68616124f37f8df60f2279d2edcb1afb6df4`.
4. `git status --porcelain --untracked-files=no | wc -l`: 0.
   - 4a. `cmp` of the box's cut record against the committed
     `runs/french_long_cuts/b1_insample.cut.json`: `record-identical`.
   - 4b. `nproc --all`: **192**. That is at least 4 × 32 = 128, so the run went ahead with
     `THREADS=32 --workers 4` unchanged.
5. The wheel: `sha256sum -c` OK.
6. The tests: **20 passed** (2 warnings, 41.8 s).
   - Section g of the registration counts 19 (2 + 3 + 2 + 12).
   - The 20th is the pins test, added to `tests/test_french_long_read.py` at `b541ddf`, now 4
     tests.
7. **Launched** 13:03:39 UTC (08:03 CDT) as tmux `fl_b1`:
   `THREADS=32 cloud/run.sh fl_b1 python -m experiments.french_long_read --read b1 --cuts ~/french_long/b1_insample.cut.json --out runs/french_long_b1/2026-10-11 --expect-head ca4b68616124f37f8df60f2279d2edcb1afb6df4 --wheel ~/lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl --workers 4`
   - No refusal. `pins.json` was written at 13:05 UTC, before any fit.
   - **Finished** at about 13:58 UTC: `results written …; no outcome printed`, `[exit 0]`.
     Total 3,169 s (52.8 min). No "stopped" key.
   - Peak load about 122 during the fits. Disk 35 GB used of 48 GB at the end.
   - The class table is cached on the box in `data/planted_cache/`. The log holds only
     RuntimeWarnings (an empty slice, degrees of freedom ≤ 0, from rows before an industry
     enters) and the two closing lines.
8. `rsync` of `runs/french_long_b1/`: exit 0.
9. `rsync` of `logs/fl_b1.log`: exit 0. The SHA-256 of each file is identical on the box and
   the laptop:
   - `results.json` `5cc4c857ddf743b1b5fb3b49ce0fb388fec4877810894520d81797eccb38717e`;
   - `pins.json` `add9b6e07cdc28ea095fb36b50d9b7a2dc3563e66b33fe8a8f650c1841eff6a9`;
   - `fl_b1.log` `22583923d201a852fe3ea68a74ad0d8ef211af340288a20833914a013006fb70`.

   After the run the box's HEAD was still EXPECT, with 0 tracked changes.
10. **The stop.**
    - `aws ec2 stop-instances` from the agent's shell failed: no region was set, and then
      there were no credentials.
    - **The box was stopped by the author**, with his own credentials. He reported it
      "stopped" at 10:42 CDT (15:42 UTC); he did not give the exact stop time. At 10:42 CDT
      ssh to 3.139.101.168 timed out.
    - It was not stopped with `shutdown -h`.
    - **Box time:** from 07:58 CDT to the stop, at most about 2.7 box-hours. The run took 0.9
      of them (08:03 to 08:58 CDT). The box sat idle from 08:58 CDT, after the fetch, until the
      stop, because the agent's shell had no AWS credentials. **So the 2-box-hour mark
      (09:58 CDT) passed while the box was idle. No computation ran past it.**

## Process fields from `results.json` (no statistic read)

- registration `756af89…`; git_head `ca4b686…`; platform Linux x86_64.
- inputs: `b1_insample.csv` `c380c3ea…0693`. 17,084 rows, 1926-07-01 .. 1989-12-29.
- **The repeat: bit-identical** at d = 1 and at d = 0.
- **Seconds per fit:**
  - d = 1: rolling 606, expanding 1,445;
  - d = 0: rolling 598, expanding 1,405.

  That is about 3.3× the laptop smoke's 623 s per fit (108 rolling, 489 expanding, at 16,000
  rows). Section g's estimate for the four fits, about 18 min, was low. They took about 34 min.
  The whole session stayed well under the 2-hour cap.

## Notes

- **The runner's docstring** shows `--workers 6`. The sheet and this run use 4. The runner is
  pinned by the registration, so it was not edited.
- **Entry dates (a check, not a rule):** the cut record's `entry_rule_ii` matches `pins.json`'s
  entry dates for all 49 industries, at d = 1 and at d = 0. Differences: 0.
- **X shapes from `pins.json`:** d = 1 (16,829, 49, 40); d = 0 (16,830, 49, 40).
- **The row count** (17,084 against "about 16,000") is noted in the H1 run record
  (`209f6a4`).
