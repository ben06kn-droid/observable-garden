# French holdout grading, step 0: commands (QUEUED; not run)

The draft is `prereg/french-holdout-grading.md`, section 4, step 0. Its design was approved
on 2026-10-07; it is queued for the next box session and needs the author's go.

**Where these commands should live.** They belong in that draft's operator section. They
are here instead because the author's instruction of 2026-10-08 forbade editing any
prereg file while the version-2 pilot runs. They can be moved into the draft with the
author's go.

The script is `experiments/french_step0.py`. Its helpers are tested on synthetic arrays
in `tests/test_french_step0.py`.

## 1. Laptop: the reference (Darwin arm64, macOS LightGBM pin)

```
cd ~/observable-garden && .venv/bin/python -m experiments.french_step0 reference --out runs/french_step0/<date>
```

## 2. Copy to the compute box (not the holdout host) and check every hash on arrival

This is a stated departure, as the ETF in-sample copy was: only the in-sample CSV and the
pinned X are copied. No holdout row exists in either.

```
scp data/raw/french_insample/french49_vw_daily.csv og-48:observable-garden/data/raw/french_insample/
scp data/pinned/french49_X.npy og-48:observable-garden/data/pinned/
scp -r runs/french_step0/<date> og-48:observable-garden/runs/french_step0/
ssh og-48 'cd ~/observable-garden && \
  echo "1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e  data/raw/french_insample/french49_vw_daily.csv" | sha256sum -c && \
  echo "07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc  data/pinned/french49_X.npy" | sha256sum -c'
```

## 3. Box: the comparison (Linux LightGBM pin)

```
ssh og-48 'cd ~/observable-garden && OMP_NUM_THREADS=1 .venv/bin/python -m experiments.french_step0 compare \
    --out runs/french_step0/<date> --reference runs/french_step0/<date>/reference.json'
rsync -avz og-48:observable-garden/runs/french_step0/ runs/french_step0/
```

It prints PASS or FAIL against the draft's Option A tolerances, and the refit and
position-correlation counts that decide between Option A2 and Option B. It reads no
holdout row: the loader refuses any row dated 2020 or later, and the script refuses a
panel that reaches 2020.
