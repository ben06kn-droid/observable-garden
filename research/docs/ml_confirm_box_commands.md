# ridge_stack confirmation: box commands

The registration is `prereg/ml-ridge-stack-confirmation.md`, live at
`77f3ee19469f500d5c3959c9612a04d250856b02`. **Nothing here runs without the author's go.**

`EXPECT` is the commit to run, and the author is given its full hash. It is the commit
that adds this file, so the file cannot name it. The runner refuses to start unless HEAD
equals `EXPECT`, the tree is clean and the registration is an ancestor of HEAD.

```
WHEEL=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
EXPECT=<full hash given in the report>
```

## 0. On the Mac

Point `og-48`'s HostName in `~/.ssh/config` at the box IP. The wheel should still be in
the box's home directory from the pilot; if it is not, copy it again:

```
scp ~/og-wheels/$WHEEL og-48:~
```

## 1. Setup on the box

Stop on any mismatch.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD     # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                # must be 0
echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$WHEEL" | sha256sum -c
uv pip install --python .venv/bin/python --no-deps ~/$WHEEL                        # no-op if installed
.venv/bin/python -c "import lightgbm; print(lightgbm.__version__)"                 # 4.7.0
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_learn.py tests/test_ml_pilot.py \
    tests/test_ml_confirm_ridge_stack.py tests/test_read_ml_confirm_ridge_stack.py \
    tests/test_check_ml_pilot_dry.py tests/test_planted_fast.py tests/test_planted_rules.py \
    tests/test_planted_truth_rules.py
```

## 2. Box smoke on 689902–689903

ridge_stack and the control only. It prints the leak test, the bit-for-bit repeat and
seconds per panel, and no outcome.

```
cloud/run.sh confirm_smoke python -m experiments.ml_smoke_2026_10_07 \
    --out runs/ml_confirm_smoke/ridge_stack --seeds 689902 689903 --predictors ridge_stack control
```

## 3. Dry run on 689900–689901

```
cloud/run.sh confirm_dry python -m experiments.ml_confirm_ridge_stack \
    --out runs/ml_confirm_dry/ridge_stack --dry-seeds 689900 689901 --workers 2 \
    --wheel ~/$WHEEL --expect-head $EXPECT
# when it has exited, check it: tasks, rows, field names and finiteness only
.venv/bin/python -m experiments.check_ml_pilot_dry --dir runs/ml_confirm_dry/ridge_stack \
    --file results.jsonl | grep -v '^   '
```

**Stop and report** if the leak test or the repeat fails for either predictor, or if the
checker does not print PASS.

## 4. The run

800 tasks on 150 workers.

```
cloud/run.sh confirm python -m experiments.ml_confirm_ridge_stack \
    --out runs/ml_confirm/ridge_stack --workers 150 --wheel ~/$WHEEL --expect-head $EXPECT
```

## 5. From the Mac: fetch, then stop

This waits for the run to finish, fetches the results first, then stops the box (stop,
not terminate).

```
rsync -avz og-48:observable-garden/runs/ml_confirm_smoke/ runs/ml_confirm_smoke/
rsync -avz og-48:observable-garden/runs/ml_confirm_dry/ runs/ml_confirm_dry/
cloud/wait_fetch_stop.sh og-48 confirm 60 runs/ml_confirm/ridge_stack
```

## 6. On the Mac, in order

1. Commit the raw outputs and the run record before any read.
2. Read once:

   ```
   .venv/bin/python -m experiments.read_ml_confirm_ridge_stack --dir runs/ml_confirm/ridge_stack
   ```

3. Commit the read's output unedited.
