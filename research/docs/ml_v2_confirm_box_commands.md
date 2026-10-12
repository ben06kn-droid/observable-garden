# Version-2 confirmation: box commands (QUEUED; not run)

The registration is `prereg/ml-v2-confirmation.md`, live at `083c734`, with amendment 1 at
`0b0b358`. The runner is `experiments/ml_v2_confirm_2026_10_09.py`. The reader is
`experiments/read_ml_v2_confirm_2026_10_09.py`. **Nothing here runs without the author's
go and the box IP.**

`EXPECT` is the full hash of the commit to run, given in the report. The runner refuses
to start unless all of these hold:
- HEAD equals `EXPECT`, and the tree is clean;
- the registration `083c734` is an ancestor of HEAD;
- version 2's blobs (learn2, the v2 inputs, the planted rules) and version 1's blobs are
  the pinned ones;
- the Linux LightGBM wheel and library hashes match, and the v2 inputs pin has its hash;
- the platform is Linux x86_64.

```
WHEEL=lightgbm-4.7.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl
EXPECT=<full hash given in the report>
D=$(date -u +%F)
```

## 1. Setup on the box

Point `og-48` at the box IP. Stop on any mismatch. If the pull is blocked by untracked
files that match committed blobs, move them aside and record that.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD      # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                 # must be 0
git merge-base --is-ancestor 083c734724340b0d1ae7f6bfd98b0a61e23fe84c HEAD && echo ancestor-ok
echo "d23e922acd891e77212e4d0fbcee9ba973c96dee479491341d05ba595357ebb7  $HOME/$WHEEL" | sha256sum -c
echo "3ff15481cc4a81b62ee09e49610b5b776d9eb2f989b7a2fca53bb241a1696700  data/pinned/etf_v2_inputs_r2.npz" | sha256sum -c
echo "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba  data/pinned/etf_features_X.npy" | sha256sum -c
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_learn2.py tests/test_learn.py tests/test_planted_rules_v2.py \
    tests/test_read_ml_v2_confirm.py tests/test_ml_v2_confirm.py -k "not laptop_is_refused"
```

`test_the_pinned_blobs_match_this_checkout_and_the_laptop_is_refused` assumes the Mac.
It would fail on Linux, as the first pilot's did, so it is not run here. The runner's own
start-up refusals cover the same pins on the box.

## 2. Box smoke, then the run, with the dry run on 699900–699909 alongside

```
cloud/run.sh v2c_smoke python -m experiments.ml_v2_smoke_2026_10_08 --out runs/ml_v2_smoke_box3/$D --workers 64
# after the smoke passes (leak tests PASS, repeats True):
cloud/run.sh v2c_run python -m experiments.ml_v2_confirm_2026_10_09 --out runs/ml_v2_confirm/2026-10-09 \
    --workers 180 --wheel ~/$WHEEL --expect-head $EXPECT
cloud/run.sh v2c_dry python -m experiments.ml_v2_confirm_2026_10_09 --out runs/ml_v2_confirm_dry/2026-10-09 \
    --dry --workers 2 --wheel ~/$WHEEL --expect-head $EXPECT
# when the dry run exits:
.venv/bin/python -m experiments.check_ml_v2_confirm_dry --dir runs/ml_v2_confirm_dry/2026-10-09
```

**Stop and report** if any start-up refusal, leak test, repeat or the checker fails.

## 3. Fetch, then stop the box

```
# from the Mac
rsync -avz og-48:observable-garden/runs/ml_v2_confirm/ runs/ml_v2_confirm/
rsync -avz og-48:observable-garden/runs/ml_v2_confirm_dry/ runs/ml_v2_confirm_dry/
rsync -avz og-48:observable-garden/runs/ml_v2_smoke_box3/ runs/ml_v2_smoke_box3/
ssh og-48 "sudo shutdown -h now"        # stop, not terminate
```

## 4. On the Mac

1. Commit the raw outputs and the run record before the read.
2. Read once:

   ```
   .venv/bin/python -m experiments.read_ml_v2_confirm_2026_10_09 --dir runs/ml_v2_confirm/2026-10-09
   ```

   It prints level first, then claims H and R with their 97.5% intervals and the joint
   outcome, then the secondaries.
3. Commit the read's output unedited, and push.
