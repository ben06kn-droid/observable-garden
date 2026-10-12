# Recency planted validation: box commands (QUEUED; not run)

The plan is `prereg/recency-weight-planted.md` (`07fa892`; amendments `e48113e`, `a2fc19f`).
The runner is `experiments/recency_planted.py`; the reader is
`experiments/read_recency_planted.py`. **Nothing here runs without the author's own typed
go and the box IP.**

`EXPECT` is the full hash given in the go message. The runner refuses to start unless:
- the platform is Linux x86_64;
- HEAD equals `EXPECT`, and the tree is clean;
- the plan and both its amendments are ancestors of HEAD;
- the pool files match the pool's manifest.

```
EXPECT=<the full hash in the go message>
D=$(date -u +%F)
```

## 1. On the Mac: point `og-48` at the box IP

Set `HostName` of `Host og-48` in `~/.ssh/config` to the IP in the go message.

## 2. First: the three version-2 confirmation logs (one file per rsync call)

These were left on the box's disk on 2026-10-09. The confirmation's run record (`1ba8df7`)
recorded their content, not their hashes.

```
mkdir -p runs/ml_v2_confirm/2026-10-09/logs
rsync -av og-48:observable-garden/logs/v2c_smoke.log runs/ml_v2_confirm/2026-10-09/logs/; echo "rsync v2c_smoke exit=$?"
rsync -av og-48:observable-garden/logs/v2c_run.log   runs/ml_v2_confirm/2026-10-09/logs/; echo "rsync v2c_run exit=$?"
rsync -av og-48:observable-garden/logs/v2c_dry.log   runs/ml_v2_confirm/2026-10-09/logs/; echo "rsync v2c_dry exit=$?"
shasum -a 256 runs/ml_v2_confirm/2026-10-09/logs/*.log
```

**Checked against the run record's quoted content.** Each grep must find its line:

```
L=runs/ml_v2_confirm/2026-10-09/logs
grep -c "PASS" $L/v2c_smoke.log; grep -q "wall 537 s" $L/v2c_smoke.log && echo smoke-wall-ok; grep -q "\[exit 0\]" $L/v2c_smoke.log && echo smoke-exit-ok
grep -q "960/960 tasks" $L/v2c_run.log && echo run-tasks-ok; grep -q "wall 2059 s; 960 tasks; no outcome printed" $L/v2c_run.log && echo run-wall-ok; grep -q "\[exit 0\]" $L/v2c_run.log && echo run-exit-ok
grep -q "2/2 tasks" $L/v2c_dry.log && echo dry-tasks-ok; grep -q "\[exit 0\]" $L/v2c_dry.log && echo dry-exit-ok
```

- The rsync exit statuses, the three SHA-256 values and the grep results are reported, and
  written into the confirmation's run record, which is append-only.
- **If an rsync exit status is not 0, or a grep finds nothing, stop and report.** The box
  stays up.

## 3. Setup on the box

Stop on any mismatch. If the pull is blocked by untracked files that match committed blobs,
move them aside and record that.

```
ssh og-48
cd ~/observable-garden && git pull --ff-only origin main && git rev-parse HEAD      # must equal $EXPECT
git status --porcelain --untracked-files=no | wc -l                                 # must be 0
echo "4b4610704db0042c514c8ee4f230b239942d4b15be87d07188be3f0e7600b7ba  data/pinned/etf_features_X.npy" | sha256sum -c
```

## 4. The pool, then the dry run alongside the tests

The pool is built on the box. Its hashes are the box's own, written to its manifest.

```
cloud/run.sh rp_pool python -m experiments.recency_planted --build-pool
# when rp_pool exits:
cloud/run.sh rp_dry python -m experiments.recency_planted --dry --out runs/recency_planted_dry/$D --workers 4
OMP_NUM_THREADS=1 .venv/bin/pytest -q tests/test_recency.py tests/test_recency_planted.py tests/test_read_recency_planted.py
# when rp_dry exits:
.venv/bin/python -m experiments.check_recency_planted_dry --dir runs/recency_planted_dry/$D
```

**Stop and report** if the pool build, any test or the dry checker fails.

## 5. The run

```
cloud/run.sh rp_run python -m experiments.recency_planted --out runs/recency_planted/$D \
    --workers 180 --expect-head $EXPECT
```

- 5,200 tasks.
- The smoke measured about 60 core-hours on the laptop. On 180 workers at the measured
  1.7× slowdown, that is about 35 minutes.
- **If the session projects above 2 box-hours, stop and ask.**

## 6. Fetch, then stop the box

```
# from the Mac, one call per directory
rsync -av og-48:observable-garden/runs/recency_planted/ runs/recency_planted/; echo "exit=$?"
rsync -av og-48:observable-garden/runs/recency_planted_dry/ runs/recency_planted_dry/; echo "exit=$?"
rsync -av og-48:observable-garden/data/planted_cache/recency_pool/manifest.json runs/recency_planted/$D/pool_manifest.json; echo "exit=$?"
ssh og-48 "sudo shutdown -h now"        # stop, not terminate
```

## 7. On the Mac

1. Commit the raw outputs, the dry check and the run record before the read.
2. Read once:

   ```
   .venv/bin/python -m experiments.read_recency_planted --dir runs/recency_planted/$D
   ```

3. Commit the read's output unedited, and push.
