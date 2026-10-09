# French 49-industry panel: holdout grading, a registration, 2026-10-09 (America/Chicago)

**Status: LIVE, 2026-10-09 (America/Chicago).**
- The author accepted the draft at `d54f553`, and this text is committed alone.
- At this commit no holdout row has been parsed, the zip has not been moved, and nothing
  has been run on the holdout host.
- The split script, the grader and the reader are written after this commit. Each refuses
  to run unless this commit is an ancestor of HEAD.
- Amendments are append-only and dated.

**Parent registration:** `prereg/french-panel.md` (live at `de9da1b`), section k. The
in-sample read is at `31622d6` (raw) and `fc92cdb` (read).

## 1. What is graded

The objects were fixed by the in-sample read at `31622d6`. **Both were refused in-sample,
and both are graded.**

| | object | in-sample net Sharpe | in-sample p | in-sample 90% lower bound |
|---|---|---|---|---|
| (a) | the ridge_stack stream: code at `fce5627`, the four pinned `learn/` blobs, `ridge_stack.run(panel, "ridge_stack")` | 0.547 | 0.0738 (refused at p < 0.04) | **+0.065** |
| (b) | class member 2937: **+ma_spread_z, −ma_spread_rank** (supports [[28, +1], [29, −1]]) | 0.679 | 0.9626 (refused at p < 0.01) | **−0.518** |

**Nothing else is graded.** There are no other members, no re-selection on holdout data,
and no other predictor.

## 2. The holdout window

- **2020-01-01 to the last row of the pinned zip** (SHA-256
  `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de`).
- **1,674 rows**, about **6.64 years** at 252 a year. The fetch counted the rows from their
  date field; their values were never parsed.
  - **The holdout ends at the zip's last row** (author, 2026-10-09). Its date is not read
    now. The grader records it at the split on the host and writes it into the grades
    file.
- **Graded periods:** the 1,674 periods whose earned return is dated in the window.
  - The first is the return dated 2020-01-02, earned by the position formed at the close of
    2019-12-30.
  - The last is the final row of the zip.
- **There is no fallback window.**

## 3. Continuation across the boundary

**One panel spans in-sample and holdout.** The grader builds a single panel over
2008-12-29 to the last holdout row, by `environments.french_panel`'s computation. In that
panel, feature rows 0–2515 are the in-sample rows. Every quantity is computed on it
causally.

- **Features:**
  - The 252-row (and shorter) lookbacks run over the in-sample tail into the holdout.
  - Nothing is restarted at 2020-01-01.
  - The declared market (the equal-weighted average) and average ranks are as registered.
  - The two rows 2019-12-30 and 2019-12-31 become feature rows in the spanning panel. Their
    features use in-sample data only; the returns they earn are dated in 2020.
- **ridge_stack:**
  - The walk-forward continues on the same 252-row year chunks, counted from feature row 0.
  - It keeps the same annual refit, with trees refit every second year as in the code, the
    same 2-row embargo and the same 64-row warm-up drop.
  - Each refit trains on all rows realised before it.
  - The market states and sigma are computed over the spanning panel with no reset. Their
    expanding standardisations continue from the in-sample history.
  - The chunk containing the boundary is fitted where its year starts (feature row 2268),
    exactly as in-sample.
- **The book:**
  - The net stream of each object is computed over all its rows, from its first scored
    in-sample row, with one continuous book. The holdout periods are then sliced out.
  - So the position held at the close of 2019-12-27 carries over, and the first holdout
    trade is costed from it.
  - `learn.inputs.net_stream` restarts the book from zero at its first row, so it is
    called on the full row range, never on the holdout slice alone.

**How the grader proves no restart happened.** Each check runs before any holdout value is
computed, and the grader refuses if any fails.
1. **Positions, same platform:** the grader runs each object twice on the host.
   - Once on the spanning panel, and once on the in-sample-only panel.
   - Positions on feature rows 0–2515 must be **bit-identical** between the two runs.
   - The positions are causal (ridge_stack's leak test passes on this panel), so this holds
     iff nothing in the spanning run depends on its length.
   - This is the same comparison the leak test makes, applied to a series that grows
     rather than one that is perturbed.
2. **Features:** the spanning panel's features on rows 0–2515 must be bit-identical to the
   host's own in-sample-only build.
3. **The book:** the spanning stream's cost on the first holdout period must equal
   |p_t − p_{t−1}| · cost_rate + max(−p_t, 0) · borrow_rate, summed over industries, to
   1e-15.
   - t is the feature row 2019-12-30 and t−1 is the feature row 2019-12-27.
   - A restarted book, with p_{t−1} = 0, would give a different cost, so this check fails
     on a restart.

## 4. Platform: the proposal

**The problem.** The holdout host (`i-0886a189b85d4d051`) is Linux x86_64. The French X
pin and the in-sample read are Darwin arm64, with the macOS LightGBM pin. The registration
expects a Linux rebuild not to match the pin bit for bit. ridge_stack also has discrete
steps: the penalty argmax over 192 grid points, the leave-one-year-out choice, and the
non-negative stack. So a last-digit difference can occasionally change a choice, not just a
digit.

**Proposed, in order:**

**Step 0: a feasibility check, outcome-free for the holdout.** Its design was approved on
2026-10-07, but it is **not run now**. It is queued for the next box session and needs
the author's go then.
- **Where:** on the compute box (c7a, Linux x86_64; not the holdout host). The in-sample
  CSV only is copied there, with its hash checked. That copy is a stated departure, as the
  ETF in-sample copy was.
- **What it does:** builds the in-sample X with the registered code, and computes, against
  the pinned arm64 X:
  - the maximum absolute difference over the 20 z-features;
  - the number of rank entries that differ, over the 20 rank features.
- **Then the two in-sample objects,** whose values are already read and committed at
  `fc92cdb`:
  - member 2937's in-sample net Sharpe;
  - ridge_stack's in-sample net Sharpe, with the Linux LightGBM pin;
  - the maximum absolute difference in member 2937's positions;
  - the share of ridge_stack's refits whose chosen penalties or stack weights differ from
    the laptop's.
- **No holdout row is involved.**
- **Cost:** under 10 box minutes, under $2.

**Option A, the Linux holdout host with stated tolerances.** Proposed if step 0 meets
these tolerances:

| check, on the host, before any holdout value | tolerance |
|---|---|
| z-features, rows 0–2515, against the pinned X | max absolute difference ≤ 1e-9 |
| rank features, rows 0–2515, against the pinned X | at most 1 differing entry in 10,000 (≤ 246 of 2,465,680) |
| member 2937, in-sample net Sharpe | equals 0.679 to 3 decimals |
| ridge_stack, in-sample net Sharpe | equals 0.547 to 3 decimals |
| no-restart checks (section 3) | bit-identical, on the host's own runs |

The grader refuses on any failure. Holdout values then come from the host's own spanning
build. **Cost:** the host's normal use; the grading itself takes minutes.

**Option A2, a possibility that needs the author's decision. No numbers are fixed here.**
- **When it applies:** step 0 misses the 3-decimal match on ridge_stack's in-sample net
  Sharpe ONLY because some refits choose different penalties or stack weights on Linux.
  The z-feature, rank and member-2937 tolerances must all be met.
- **Then a looser tolerance may be fixed,** from step 0's numbers alone and before any
  holdout value is computed. It has two parts:
  - ridge_stack's in-sample net Sharpe within a stated band of 0.547;
  - the correlation of its in-sample positions with the laptop's above a stated value.
- **Both numbers, and the decision to use A2 at all, are the author's.** They are recorded
  in a dated amendment before the grader runs. If the author declines, Option B applies.

**Option B, if a tolerance cannot be met (and A2 is not taken): an arm64 macOS holdout
host.**
- **What:** an EC2 Mac instance (mac2 family, Apple silicon), not the agent machine. It
  runs the same Python 3.14.2, numpy 2.5.3 and scipy 1.18.1, and the macOS LightGBM pin.
- **Requirement:** **bit-identity** with the pinned X on rows 0–2515, and the in-sample
  Sharpes reproduced exactly (to the stored digits) before any holdout value.
- **Fallback:** if even that fails, nothing is graded and the author is asked.
- **Cost:** an EC2 Mac needs a dedicated host with a 24-hour minimum allocation, roughly
  $16–$22 at about $0.65–$0.88 an hour (not checked today), plus setup time.
- **Seal:** the zip moves to this host instead, and the Linux host is not used for this
  panel.

**Not proposed:** grading on the laptop. It would put holdout rows on the agent machine,
which the parent registration's seal rules out (section f).

### Step 0's result, and the platform decision (2026-10-09)

Step 0 ran on 2026-10-09: the laptop reference, then the comparison on the compute box
(c7a.48xlarge, Linux x86_64, the Linux LightGBM pin). Outputs are in
`runs/french_step0/2026-10-09/`, committed at `4a0e621`. **It is in-sample only, and no
holdout row was read.** It printed:

| Option A check | result | tolerance | verdict |
|---|---|---|---|
| z-features, largest difference against the pinned arm64 X | 6.223e-14 | ≤ 1e-9 | PASS |
| rank entries differing | 2 of 2,465,680 | ≤ 246 | PASS |
| member 2937, in-sample net Sharpe | 0.679 | 0.679 to 3 decimals | PASS |
| ridge_stack, in-sample net Sharpe | 0.547 | 0.547 to 3 decimals | PASS |

ridge_stack had 7 refits. Its penalties differed on 0 of them; its stack weights differed
by more than 1e-9 on all 7. Its positions correlate with the laptop's at 1.000000 over the
scored rows.

**Decision:**
- **Option A is adopted.** The grading platform is the Linux holdout host: the 6.5 holdout
  host, `i-0886a189b85d4d051` (c7a.8xlarge). **The compute box is not used for grading.**
- **Options A2 and B are not needed,** and are kept above as the record of what was
  considered.

The no-restart checks of section 3 run on the host's own builds, as before.

## 5. Quantities, descriptive

There are two objects (n = 2). **No pooled test.**

**For each object:**
- **The realised holdout net Sharpe** over the 1,674 graded periods.
  - **Interval:** a stationary block bootstrap 95% interval (percentile).
  - **Replicates:** B = 10,000; one resample of holdout period indices is shared by both
    objects.
  - **Block length:** by the class rule, the median Politis–White length over the
    holdout's demeaned base feature columns (`estimator.bootstrap.select_block_length`).
  - **Seed:** `default_rng(694000)`, from the block 694000–694999 (`seed_block_check`: NO
    COLLISION, 2026-10-07).
- **Realised minus the in-sample 90% lower bound:** realised − 0.065 for the stream, and
  realised − (−0.518) for the member. The interval is the same bootstrap interval, shifted
  by that constant.
- **Where the realised value falls on the object's in-sample confidence curve.**
  - The stored curve C(s) is on the grid s = −1.00, −0.95, …, 3.00 (81 points); it is in
    `results.json` at `31622d6`.
  - The grader reports C at the realised Sharpe, by linear interpolation on that grid.
    Below −1.00 or above 3.00 it reports the end value and says so.

**What size of difference is visible.** The standard error of an annualised Sharpe over
6.64 years is about sqrt((1 + SR² / (2 · 252)) / 6.64), by Lo's iid formula with ppy 252.
(Corrected on 2026-10-08: the earlier table used (1 + SR²/2) and overstated it.)

| at SR | standard error |
|---|---|
| 0 | 0.388 |
| 0.547 | 0.388 |
| 0.679 | 0.388 |
| 1.0 | 0.388 |

A difference between realised and in-sample Sharpe smaller than about **0.8** (two
standard errors) will usually not be distinguishable from noise.

## 6. Both branches, for each object

Judged on the point estimate: the realised holdout net Sharpe against the in-sample 90%
lower bound.
- **Held** (realised ≥ the in-sample 90% lower bound): "**<object>: the in-sample 90%
  lower bound held on the holdout (realised <x> ≥ bound <L>).**"
- **Not held** (realised < the in-sample 90% lower bound): "**<object>: the in-sample 90%
  lower bound did not hold on the holdout (realised <x> < bound <L>).**"
- **Always stated, in both branches:** "**Both graded objects were refused in-sample.
  This grading cannot test whether a pass holds.**"

## 7. Going live, and the operator checklist (Option A, the 6.5 holdout host)

**Going live.**
- **This registration goes live as its own dated commit** (call it LIVE).
- The grader and its reader are written **after** LIVE. **Each refuses to run unless LIVE
  is an ancestor of HEAD.**
- The reader is tested on made-up rows before the grading runs.
- The grader commit that runs on the host (call it G) is named in the author's go.
- **Script names below are those to be written after LIVE:**
  - `experiments/french_holdout_split.py`;
  - `experiments/french_holdout_grade.py`;
  - `experiments/read_french_holdout.py`.

**The checklist, in order.** [L] runs on the laptop and [H] on the holdout host.
**Nothing runs without the author's go.**

1. **[L] Push G,** and record LIVE and G in the run record.
2. **[author] Start the holdout host,** `i-0886a189b85d4d051`, and send its IP. On the
   laptop, set `HOST` to that address (ssh user `ubuntu`, the project key).
3. **[L] Copy the zip to the host:**

   ```
   ssh HOST 'mkdir -p ~/french_holdout'
   scp ~/Desktop/og-quarantine/french/49_Industry_Portfolios_daily_CSV.zip HOST:~/french_holdout/
   ```

4. **[H] Check the zip's hash on the host:**

   ```
   echo "8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de  $HOME/french_holdout/49_Industry_Portfolios_daily_CSV.zip" | sha256sum -c
   ```

   It must print `OK`. **On anything else, stop:** the laptop copy is kept, and nothing
   further runs.
5. **ZIP-DELETE: the named operator step,** run only on the author's explicit go, given
   after step 4 prints OK.
   - **Its confirmation line, written by the author:** "ZIP-DELETE confirmed: host
     SHA-256 OK for 8f394fe3…40de at <UTC time>; delete the laptop copy."
   - **[L] Then:**

     ```
     rm ~/Desktop/og-quarantine/french/49_Industry_Portfolios_daily_CSV.zip
     ls ~/Desktop/og-quarantine/french/      # must no longer list the zip
     ```

   - The deletion, its time and the confirmation line go into the run record.
6. **[L] Copy the grading inputs:** the in-sample CSV, the pinned X and the Linux
   LightGBM wheel.

   ```
   scp data/raw/french_insample/french49_vw_daily.csv HOST:observable-garden/data/raw/french_insample/
   scp data/pinned/french49_X.npy HOST:observable-garden/data/pinned/
   scp ~/og-wheels/lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl HOST:~
   ```

7. **[H] Repository at G, clean, with LIVE as an ancestor:**

   ```
   cd ~/observable-garden && git fetch origin && git checkout G && git rev-parse HEAD   # must equal G
   git status --porcelain --untracked-files=no | wc -l                                  # must be 0
   git merge-base --is-ancestor LIVE HEAD && echo ancestor-ok
   ```

8. **[H] Check the hashes, and set up the grading environment:**

   ```
   W=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
   echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$W" | sha256sum -c
   echo "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e  data/raw/french_insample/french49_vw_daily.csv" | sha256sum -c
   echo "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc  data/pinned/french49_X.npy" | sha256sum -c
   .venv-grading/bin/pip install --no-deps ~/$W
   .venv-grading/bin/python -c "import lightgbm, hashlib, pathlib; p = pathlib.Path(lightgbm.__file__).parent / 'lib' / 'lib_lightgbm.so'; print(lightgbm.__version__, hashlib.sha256(p.read_bytes()).hexdigest())"
   # must print 4.7.0 573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a
   ```

9. **[H] The split** (section 2):

   ```
   .venv-grading/bin/python -m experiments.french_holdout_split --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip \
       --out ~/french_holdout/holdout.csv
   ```

   - It records the holdout CSV's SHA-256, its row count (which must be 1,674) and its
     last date.
   - **The holdout CSV never leaves the host.**
10. **[H] Grade:**

    ```
    .venv-grading/bin/python -m experiments.french_holdout_grade --holdout ~/french_holdout/holdout.csv \
        --out runs/french_holdout/<date> --expect-head G
    ```

    It runs, in order, refusing on any failure before any holdout value is computed:
    - the start-up refusals (the pins, the clean tree, HEAD = G, LIVE an ancestor);
    - section 4's Option A tolerances, on the host's own build;
    - section 3's no-restart checks.

    It then computes section 5's quantities and writes `grades.json`, with the holdout's
    last date, printing no value.
11. **[L] Fetch only the grades and the run record:**

    ```
    rsync -avz HOST:observable-garden/runs/french_holdout/ runs/french_holdout/
    ```

    **Commit `grades.json` and the run record before the read.**
12. **[L] Read once,** then commit its output unedited and push:

    ```
    .venv/bin/python -m experiments.read_french_holdout --dir runs/french_holdout/<date>
    ```

13. **[L] Stop the host** (stop, not terminate), and record its state:

    ```
    ssh HOST 'sudo shutdown -h now'
    ```

## 8. Known items

- **The state-gated rule's holdout gate restart** (`f41583b`) concerns planted rules on
  the planted panel, not this panel. It is listed so the grader's no-restart check is seen
  to cover the analogous risk here (section 3).
- **Recall:** 2020 onward lies inside the agent model's training data. No agent is
  involved in this grading.
