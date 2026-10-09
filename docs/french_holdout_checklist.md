# French holdout grading: the final operator checklist (QUEUED; not run)

The registration is `prereg/french-holdout-grading.md`, live at LIVE. This is its section
7 checklist with the real script names and G filled in. **Nothing here runs, no zip is
moved and no holdout row is parsed without the author's go.** ZIP-DELETE needs its own
confirmation line.

```
LIVE=4f11f952092831d77c4d8287f083bda12b425f22
G=0259c126de737226a9e294b0f60dd848426e7784
W=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
D=$(date -u +%F)
```

- **The scripts at G:**
  - `experiments/french_holdout_split.py` (step 9);
  - `experiments/french_holdout_grade.py` (step 10);
  - `experiments/read_french_holdout.py` (step 12).
- **Their tests:** `tests/test_french_holdout.py`, 10 tests on synthetic panels with a fake
  holdout segment. They include restarted book, state, feature and position cases, and
  the reader on made-up grades.
- **Two additions to the registered steps; neither changes a step.**
  - Step 6 creates the target directories before copying.
  - Step 8 creates `.venv-grading` if the host has none.
  - Both are marked "(added)".

1. **[L] Push G,** and record LIVE and G in the run record (`runs/french_holdout/$D/RUN_RECORD.md`).
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
5. **ZIP-DELETE**, run only on the author's explicit go, given after step 4 prints OK.
   - **The author's confirmation line:** "ZIP-DELETE confirmed: host SHA-256 OK for
     8f394fe3…40de at <UTC time>; delete the laptop copy."
   - **[L] Then:**

     ```
     rm ~/Desktop/og-quarantine/french/49_Industry_Portfolios_daily_CSV.zip
     ls ~/Desktop/og-quarantine/french/      # must no longer list the zip
     ```

   - The deletion, its time and the confirmation line go into the run record.
6. **[L] Copy the grading inputs** (in-sample CSV, pinned X, Linux wheel):

   ```
   ssh HOST 'mkdir -p observable-garden/data/raw/french_insample observable-garden/data/pinned'   # (added)
   scp data/raw/french_insample/french49_vw_daily.csv HOST:observable-garden/data/raw/french_insample/
   scp data/pinned/french49_X.npy HOST:observable-garden/data/pinned/
   scp ~/og-wheels/$W HOST:~
   ```

7. **[H] Repository at G, clean, with LIVE as an ancestor:**

   ```
   cd ~/observable-garden && git fetch origin && git checkout $G && git rev-parse HEAD   # must equal G
   git status --porcelain --untracked-files=no | wc -l                                  # must be 0
   git merge-base --is-ancestor $LIVE HEAD && echo ancestor-ok
   ```

8. **[H] Check the hashes, and set up the grading environment:**

   ```
   echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$W" | sha256sum -c
   echo "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e  data/raw/french_insample/french49_vw_daily.csv" | sha256sum -c
   echo "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc  data/pinned/french49_X.npy" | sha256sum -c
   test -d .venv-grading || (python3 -m venv .venv-grading && .venv-grading/bin/pip install -e .)   # (added)
   .venv-grading/bin/pip install --no-deps ~/$W
   .venv-grading/bin/python -c "import lightgbm, hashlib, pathlib; p = pathlib.Path(lightgbm.__file__).parent / 'lib' / 'lib_lightgbm.so'; print(lightgbm.__version__, hashlib.sha256(p.read_bytes()).hexdigest())"
   # must print 4.7.0 573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a
   ```

9. **[H] The split** (section 2). It refuses unless LIVE is an ancestor, the zip has its
   SHA-256 and the output does not exist. It writes `holdout.csv` and
   `holdout.split.json` (SHA-256, rows, which must be 1,674, and the last date), and
   prints no return value.

   ```
   .venv-grading/bin/python -m experiments.french_holdout_split --zip ~/french_holdout/49_Industry_Portfolios_daily_CSV.zip \
       --out ~/french_holdout/holdout.csv
   ```

   **The holdout CSV never leaves the host.**
10. **[H] Grade:**

    ```
    OMP_NUM_THREADS=1 .venv-grading/bin/python -m experiments.french_holdout_grade --holdout ~/french_holdout/holdout.csv \
        --out runs/french_holdout/$D --expect-head $G
    ```

    It runs in order, refusing on any failure before any holdout value is computed:
    - the start-up refusals: LIVE an ancestor, HEAD = G, clean tree, Linux x86_64, the
      LightGBM .so pin, the X pin and the in-sample CSV pin;
    - section 4's Option A tolerances, on the host's own build;
    - section 3's no-restart checks.

    Then section 5's quantities go to `grades.json`, with the last date. No value is
    printed.
11. **[L] Fetch only the grades:**

    ```
    rsync -avz HOST:observable-garden/runs/french_holdout/ runs/french_holdout/
    ```

    **Commit `grades.json` and the run record before the read.**
12. **[L] Read once,** then commit its output unedited and push:

    ```
    .venv/bin/python -m experiments.read_french_holdout --dir runs/french_holdout/$D
    ```

13. **[L] Stop the host** (stop, not terminate), and record its state:

    ```
    ssh HOST 'sudo shutdown -h now'
    ```
