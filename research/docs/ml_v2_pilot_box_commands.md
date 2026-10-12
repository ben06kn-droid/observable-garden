# ML version-2 pilot: box commands

The pilot section is in `prereg/ml-v2-exploratory-2026-10-08.md`, at `817f8d2`. **Nothing
here runs without the author's go and the box IP.**

`EXPECT` is the full hash of the commit to run, given in the report. The runner refuses
to start unless all of these hold:
- HEAD equals `EXPECT`, and the tree is clean;
- the pilot section is an ancestor of HEAD;
- version 1's four `learn/` blobs are the pinned ones;
- LightGBM is 4.7.0, with the Linux wheel's and library's hashes;
- the v2 inputs pin has its registered hash;
- the platform is Linux x86_64.

```
WHEEL=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
EXPECT=<full hash given in the report>
```

## 0. On the Mac

Point `og-48`'s HostName in `~/.ssh/config` at the box IP. Then copy the new v2 inputs
pin. The ETF P pin, the wheel and the ETF in-sample data are already on the box from
earlier runs; their hashes are checked in step 1.

```
scp data/pinned/etf_v2_inputs_r2.npz og-48:observable-garden/data/pinned/
scp ~/og-wheels/$WHEEL og-48:~                  # only if ~/$WHEEL is missing on the box
```

## 1. Setup on the box

Stop on any mismatch. If the pull is blocked by untracked files that match committed
blobs, move them aside and record that, as before.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD      # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                 # must be 0
echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$WHEEL" | sha256sum -c
echo "3ff15481cc4a81b62ee09e49610b5b776d9eb2f989b7a2fca53bb241a1696700  data/pinned/etf_v2_inputs_r2.npz" | sha256sum -c
echo "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba  data/pinned/etf_features_X.npy" | sha256sum -c
.venv/bin/python -c "import lightgbm; print(lightgbm.__version__)"                  # 4.7.0
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_learn2.py tests/test_planted_rules_v2.py \
    tests/test_ml_v2_pilot.py tests/test_read_ml_v2_pilot.py tests/test_learn.py tests/test_planted_rules.py
```

## 2. The v2 smoke on the box

Cost only, on 696000–696001. It covers the leak tests for every block and three views,
and the bit-for-bit repeat. It prints no outcome.

```
cloud/run.sh v2_smoke python -m experiments.ml_v2_smoke_2026_10_08 --out runs/ml_v2_smoke_box/2026-10-08 --workers 64
```

## 3. The dry run on the smoke block

One task of each kind: seed 696500, lead-lag; menu 696501, volume-conditioned, level 1.0;
level-0 696502. Then the checker. The menu and level-0 tasks fit all 126 cells, so this
takes about an hour of wall time.

```
cloud/run.sh v2_dry python -m experiments.ml_v2_pilot_2026_10_08 --out runs/ml_v2_pilot_dry/2026-10-08 \
    --dry --workers 3 --wheel ~/$WHEEL --expect-head $EXPECT
.venv/bin/python -m experiments.check_ml_v2_dry --dir runs/ml_v2_pilot_dry/2026-10-08
```

**Stop and report** if any start-up refusal, leak test, repeat or the checker fails.

## 4. The pilot

730 tasks on 180 workers; the longest tasks (menus and level 0) are started first.

```
cloud/run.sh v2_pilot python -m experiments.ml_v2_pilot_2026_10_08 --out runs/ml_v2_pilot/2026-10-08 \
    --workers 180 --wheel ~/$WHEEL --expect-head $EXPECT
```

## 5. From the Mac: fetch the smoke and dry run, then wait, fetch and stop

The last command waits for the pilot, fetches its results first, then stops the box (stop,
not terminate).

```
rsync -avz og-48:observable-garden/runs/ml_v2_smoke_box/ runs/ml_v2_smoke_box/
rsync -avz og-48:observable-garden/runs/ml_v2_pilot_dry/ runs/ml_v2_pilot_dry/
cloud/wait_fetch_stop.sh og-48 v2_pilot 120 runs/ml_v2_pilot/2026-10-08
```

## 6. On the Mac

1. Commit the raw outputs and the run record before any read.
2. Read once:

   ```
   .venv/bin/python -m experiments.read_ml_v2_pilot_2026_10_08 --dir runs/ml_v2_pilot/2026-10-08
   ```

3. Commit the read's output unedited.
