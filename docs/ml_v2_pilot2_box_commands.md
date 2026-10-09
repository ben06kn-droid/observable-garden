# Second version-2 pilot, with French step 0: box commands

The second pilot's section is in `prereg/ml-v2-exploratory-2026-10-08.md`, at `4688d5e`.
French step 0 is `experiments/french_step0.py` (`2c0f25b`). **Nothing here runs without
the author's go and the box IP.**

`EXPECT` is the full hash of the commit to run, given in the report. The runner refuses
to start unless all of these hold:
- HEAD equals `EXPECT`, and the tree is clean;
- both pilot sections are ancestors of HEAD;
- version 1's blobs are the pinned ones;
- the Linux LightGBM wheel and library hashes match;
- the v2 inputs pin has its registered hash;
- the platform is Linux x86_64.

```
WHEEL=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
EXPECT=<full hash given in the report>
D=$(date -u +%F)
```

## 0. Laptop, before the session: French step 0's reference

This is in-sample only, and reads no holdout row.

```
cd ~/observable-garden && .venv/bin/python -m experiments.french_step0 reference --out runs/french_step0/$D
```

## 1. On the Mac

Point `og-48` at the box IP. Then copy French step 0's inputs (in-sample only):

```
ssh og-48 'mkdir -p observable-garden/data/raw/french_insample observable-garden/runs/french_step0'
scp data/raw/french_insample/french49_vw_daily.csv og-48:observable-garden/data/raw/french_insample/
scp data/pinned/french49_X.npy og-48:observable-garden/data/pinned/
scp -r runs/french_step0/$D og-48:observable-garden/runs/french_step0/
```

## 2. Setup on the box

Stop on any mismatch. If the pull is blocked by untracked files that match committed
blobs, move them aside and record that.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD      # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                 # must be 0
echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$WHEEL" | sha256sum -c
echo "3ff15481cc4a81b62ee09e49610b5b776d9eb2f989b7a2fca53bb241a1696700  data/pinned/etf_v2_inputs_r2.npz" | sha256sum -c
echo "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba  data/pinned/etf_features_X.npy" | sha256sum -c
echo "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e  data/raw/french_insample/french49_vw_daily.csv" | sha256sum -c
echo "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc  data/pinned/french49_X.npy" | sha256sum -c
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_learn2.py tests/test_ml_v2_pilot2.py tests/test_read_ml_v2_pilot2.py \
    tests/test_french_step0.py tests/test_learn.py tests/test_planted_rules_v2.py
```

`tests/test_ml_v2_pilot.py::test_the_runner_refuses_on_the_laptop` assumes the Mac and
fails on Linux, as recorded in the first pilot's run record. It is not run here.

## 3. Box smoke, then the pilot, with the dry run alongside

```
cloud/run.sh v2b_smoke python -m experiments.ml_v2_smoke_2026_10_08 --out runs/ml_v2_smoke_box2/$D --workers 64
# after the smoke passes (leak tests PASS, repeats True):
cloud/run.sh v2b_pilot python -m experiments.ml_v2_pilot2_2026_10_09 --out runs/ml_v2_pilot2/2026-10-09 \
    --workers 180 --wheel ~/$WHEEL --expect-head $EXPECT
cloud/run.sh v2b_dry python -m experiments.ml_v2_pilot2_2026_10_09 --out runs/ml_v2_pilot2_dry/2026-10-09 \
    --dry --workers 2 --wheel ~/$WHEEL --expect-head $EXPECT
# when the dry run exits:
.venv/bin/python -m experiments.check_ml_v2_pilot2_dry --dir runs/ml_v2_pilot2_dry/2026-10-09
```

**Stop and report** if any start-up refusal, leak test, repeat or the checker fails.

## 4. After the pilot is fetched, before the box stops: French step 0 on the box

```
# from the Mac: fetch the pilot WITHOUT stopping the box
rsync -avz og-48:observable-garden/runs/ml_v2_pilot2/ runs/ml_v2_pilot2/
rsync -avz og-48:observable-garden/runs/ml_v2_pilot2_dry/ runs/ml_v2_pilot2_dry/
rsync -avz og-48:observable-garden/runs/ml_v2_smoke_box2/ runs/ml_v2_smoke_box2/
ssh og-48 "cd ~/observable-garden && OMP_NUM_THREADS=1 .venv/bin/python -m experiments.french_step0 compare \
    --out runs/french_step0/$D --reference runs/french_step0/$D/reference.json"
rsync -avz og-48:observable-garden/runs/french_step0/ runs/french_step0/
ssh og-48 "sudo shutdown -h now"        # stop, not terminate
```

## 5. On the Mac

1. Commit the raw outputs and the run records: the pilot's, and French step 0's.
2. Read the pilot once:

   ```
   .venv/bin/python -m experiments.read_ml_v2_pilot2_2026_10_09 --dir runs/ml_v2_pilot2/2026-10-09
   ```

3. Commit the read's output unedited.
4. French step 0's output decides between options A, A2 and B under the grading draft. It
   is reported, and nothing is graded.
