# Recency validation, round 2: box commands (QUEUED; not run)

- **Plan:** `prereg/recency-weight-planted-2.md` (`46b589e`; amendments `86277fc` and
  `8a23368`: the Bonferroni-adjusted rule, and NA40 at n = 2,000).
- **Runner:** `experiments/recency_planted_2.py`. **Reader:**
  `experiments/read_recency_planted_2.py`.
- **Nothing here runs without the author's typed go and the box IP.**

The runner refuses to start unless:
- the platform is Linux x86_64;
- HEAD equals `EXPECT`, and the tree is clean;
- the plan and both its amendments are ancestors of HEAD;
- the pool files on the box match their manifest. The pool is round 1's, built on the box on
  2026-10-09 and kept on its disk; it is not rebuilt.

```
EXPECT=<the full hash in the go message>
D=$(date -u +%F)
```

## 1. On the Mac

Set `HostName` of `Host og-48` in `~/.ssh/config` to the IP in the go message.

## 2. Setup on the box

Stop on any mismatch. Round 1's run outputs are untracked on the box and now committed. If
the pull is blocked by untracked files, each is compared with its committed blob. Those that
match are moved to `~/moved_aside_<date>_rp2/` and recorded. A file that does not match stops
the session.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD      # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                 # must be 0
echo "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba  data/pinned/etf_features_X.npy" | sha256sum -c
cat data/planted_cache/recency_pool/manifest.json                                   # built_on Linux x86_64
```

## 3. The dry run alongside the tests

```
cloud/run.sh rp2_dry python -m experiments.recency_planted_2 --dry --out runs/recency_planted_2_dry/$D --workers 4
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_recency.py tests/test_recency_planted_2.py tests/test_read_recency_planted_2.py
# when rp2_dry exits:
.venv/bin/python -m experiments.check_recency_planted_2_dry --dir runs/recency_planted_2_dry/$D
```

**Stop and report** if any test or the dry checker fails.

## 4. The run

```
cloud/run.sh rp2_run python -m experiments.recency_planted_2 --out runs/recency_planted_2/$D \
    --workers 180 --expect-head $EXPECT
```

- 6,200 tasks (NA40 at 2,000). About 50 minutes, smoke-scaled; about 70 box-minutes with setup.
- **If the session projects above 2 box-hours, stop and ask.**

## 5. Fetch, one rsync call each, every exit status reported; then stop the box

```
rsync -av og-48:observable-garden/runs/recency_planted_2/ runs/recency_planted_2/; echo "exit=$?"
rsync -av og-48:observable-garden/runs/recency_planted_2_dry/ runs/recency_planted_2_dry/; echo "exit=$?"
rsync -av og-48:observable-garden/logs/rp2_run.log runs/recency_planted_2/$D/; echo "exit=$?"
rsync -av og-48:observable-garden/logs/rp2_dry.log runs/recency_planted_2_dry/$D/; echo "exit=$?"
ssh og-48 "sudo shutdown -h now"        # stop, not terminate
```

## 6. On the Mac

1. Commit the raw outputs, the dry check and the run record before the read.
2. Read once:

   ```
   .venv/bin/python -m experiments.read_recency_planted_2 --dir runs/recency_planted_2/$D
   ```

3. Commit the read's output unedited, and push.
