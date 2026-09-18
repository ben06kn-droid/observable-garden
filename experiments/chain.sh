#!/usr/bin/env bash
# Chained launch: finish batch 2, then run batch 3.
#
#   experiments/chain.sh
#
# Batch 2 stopped against the five-hour cap with two rows unrun -- schedule
# lines 233 (seed 313, s3 gate) and 234 (seed 314, s0 count), both worker 0's
# under the --start 44 --workers 4 assignment. Seed 313's rate-limited attempt
# is parked in runs/_aborted/, so the row is free to run again. Leg 1 re-walks
# worker 0's 53 rows and skips the 51 that already carry a verdict, a void or a
# no_submit, so it runs exactly those two.
#
# Leg 2 is batch 3: 180 rows, {control, gate, pushed} x {sonnet, fable} on s0,
# seeds 320-499, registered by prereg/AGENT_PROMPTS.md §6 amendment 7.
#
# Both legs pass --auto-resume, which is the point of running this now: the seat
# is capped until 03:50 and the cap is a wait, not a failure. A rate-limited
# worker parks its unfinished run, sleeps until the reset the error reports, and
# runs the same row again, without bound. Leg 1 is therefore expected to sleep
# before it completes anything.
#
# Leg 1 passes --allow-code-change deliberately: batch 3's merge moved the code
# fingerprint away from what batch 2's earlier rows were produced under. Each run
# records its own fingerprint in config.json, so the boundary stays recoverable.
# Leg 2 needs no such flag -- it takes its own baseline at start.
#
# Batch 3 starts only if leg 1 exits 0. Anything that is not a rate limit --
# auth, a harness defect, a void run -- stops that worker and fails the leg, and
# the chain stops rather than opening a 180-run batch against a broken seat.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

log() { echo "[chain $(date '+%Y-%m-%d %H:%M:%S')] $*"; }

log "leg 1: batch 2 remainder, schedule lines 233-234 (worker 0)"
experiments/run_arms.sh --schedule experiments/schedule_240.txt \
    --start 44 --workers 4 --only-worker 0 --auto-resume --allow-code-change
CODE=$?
if [ "$CODE" -ne 0 ]; then
  log "leg 1 exited $CODE; NOT starting batch 3"
  exit "$CODE"
fi
log "leg 1 complete: batch 2 is finished"

log "leg 2: batch 3, 180 rows across 4 workers"
experiments/run_arms.sh --schedule experiments/schedule_180.txt \
    --workers 4 --auto-resume
CODE=$?
log "leg 2 exited $CODE"
exit "$CODE"
