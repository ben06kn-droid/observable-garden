#!/usr/bin/env bash
# Batch runner for the agent arms.
#
#   experiments/run_arms.sh                                  # legacy: seeds 2-79 by parity
#   experiments/run_arms.sh 34                               # resume that at index 34
#   experiments/run_arms.sh --schedule experiments/schedule_240.txt
#   experiments/run_arms.sh --schedule experiments/schedule_240.txt --start 112
#   experiments/run_arms.sh --schedule F --start 11 --workers 4
#   experiments/run_arms.sh --schedule F --start 11 --workers 4 --only-worker 2
#
# Schedule format: one run per line, `#` comments ignored.
#
#   seed  config  arm      budget   model
#                                   e.g.  81  s0  budget  20  claude-sonnet-5
#                                         84  s3  control  -  claude-sonnet-5
#
# Nothing here chooses a seed, an arm or a dose; all of them come from the file,
# which experiments/make_schedule.py generates from the amendments and verifies
# against them. Regenerate rather than edit by hand.
#
# --workers N (amendment 6) runs N workers in parallel within one usage window.
# Rows are dealt round-robin *within each block* by experiments/worker_rows.py,
# so every worker rotates across all eight cells; striding the flat row order
# would have left workers at N=4 with a single budget dose. Workers never touch
# git: one commit loop commits completed runs every two minutes under an
# mkdir-based lock (macOS has no flock). A worker that hits a non-zero exit
# stops itself, writes runs/_logs/stopped_k, and leaves the others running.
#
# --workers 1, the default, is the original path unchanged: sequential, with a
# commit after every run, stopping the batch on the first non-zero exit. A seat
# that is rate limited stays rate limited, and a retry loop would burn the window.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

SCHEDULE=""
START=""
ALLOW_CODE_CHANGE=0
WORKERS=1
ONLY_WORKER=""
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --schedule)          SCHEDULE="${2:-}";    shift 2 ;;
    --start)             START="${2:-}";       shift 2 ;;
    --workers)           WORKERS="${2:-}";     shift 2 ;;
    --only-worker)       ONLY_WORKER="${2:-}"; shift 2 ;;
    --allow-code-change) ALLOW_CODE_CHANGE=1;  shift ;;
    -h|--help)           sed -n '2,31p' "$0";  exit 0 ;;
    *)                   POSITIONAL+=("$1");   shift ;;
  esac
done

LOGS=runs/_logs
LOCK="$LOGS/.commit.lock"

t_for() {  # T for a config name, read rather than hardcoded
  .venv/bin/python -c "from experiments.e_agent import CONFIGS; print(CONFIGS['$1']['T'])"
}

commit_run() {  # $1 run_id, $2 description
  if [ -d "runs/$1" ]; then
    git add "runs/$1"
    git commit -q -m "run $1

$2 per prereg/AGENT_PROMPTS.md §§3-4 as amended."
    echo "committed runs/$1"
  else
    echo "WARNING: runs/$1 missing after a zero exit; nothing committed" >&2
  fi
}

# Reads SEED CONFIG ARM BUDGET MODEL; sets T MTAG RUN_ID LABEL. Shared by both
# paths so the sequential one keeps producing exactly the ids it always has.
prepare_row() {
  T=$(t_for "$CONFIG") || { echo "could not read T for $CONFIG" >&2; return 70; }
  # Batch 3 added a model column. Schedules written before it default to sonnet.
  MODEL=${MODEL:-claude-sonnet-5}
  case "$MODEL" in
    claude-sonnet-5)  MTAG=sonnet ;;
    claude-fable-5-1) MTAG=fable ;;
    *) echo "unknown model: $MODEL" >&2; return 64 ;;
  esac
  # No array for the optional flag: bash 3.2 under `set -u` treats an empty
  # array as unset, so "${BUDGET_ARG[@]}" aborts on every non-budget line --
  # which is the first scheduled run. bash -n cannot see it; only running does.
  if [ "$BUDGET" = "-" ] || [ -z "$BUDGET" ]; then
    RUN_ID="${CONFIG}_T${T}_${MTAG}_${ARM}_$(printf '%03d' "$SEED")"
    LABEL="arm $ARM, config $CONFIG, model $MODEL"
  else
    RUN_ID="${CONFIG}_T${T}_${MTAG}_${ARM}${BUDGET}_$(printf '%03d' "$SEED")"
    LABEL="arm $ARM (B=$BUDGET), config $CONFIG, model $MODEL"
  fi
  return 0
}

run_row() {  # $1 worker index, or "" when sequential (then no --worker is passed)
  local w="${1:-}"
  if [ "$BUDGET" = "-" ] || [ -z "$BUDGET" ]; then
    .venv/bin/python -m experiments.e_agent \
        --arm "$ARM" --config "$CONFIG" --runs 1 --seed-index "$SEED" \
        --model "$MODEL" ${w:+--worker "$w"}
  else
    .venv/bin/python -m experiments.e_agent \
        --arm "$ARM" --config "$CONFIG" --runs 1 --seed-index "$SEED" \
        --budget "$BUDGET" --model "$MODEL" ${w:+--worker "$w"}
  fi
}

FP() { .venv/bin/python -m experiments.code_state --field "$1"; }

# Compares against the batch's baseline. The commit loop moves HEAD constantly,
# which is exactly why code_state fingerprints the code paths and ignores runs/.
check_fingerprint() {  # $1 context for the message; 0 = proceed, 65 = refuse
  NOW_FP=$(FP fingerprint)
  [ "$NOW_FP" = "$BATCH_FP" ] && return 0
  NOW_HEAD=$(FP head)
  if [ "$ALLOW_CODE_CHANGE" -eq 1 ]; then
    echo "code changed mid-batch; continuing because --allow-code-change was passed:"
    echo "  batch started: fingerprint $BATCH_FP at HEAD $BATCH_HEAD"
    echo "  now:           fingerprint $NOW_FP at HEAD $NOW_HEAD"
    BATCH_FP="$NOW_FP"; BATCH_HEAD="$NOW_HEAD"
    return 0
  fi
  echo "REFUSING $1: the code changed mid-batch." >&2
  echo "  batch started: fingerprint $BATCH_FP at HEAD $BATCH_HEAD" >&2
  echo "  now:           fingerprint $NOW_FP at HEAD $NOW_HEAD" >&2
  echo "Runs produced before and after a code change are not comparable." >&2
  return 65
}

# -- the commit loop, and its lock -------------------------------------------
# mkdir is the atomic primitive here: macOS has no flock. The pid inside lets a
# lock left behind by a killed loop be reclaimed instead of wedging the batch.
lock_acquire() {
  if mkdir "$LOCK" 2>/dev/null; then echo $$ >"$LOCK/pid"; return 0; fi
  local pid; pid=$(cat "$LOCK/pid" 2>/dev/null || true)
  if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
    echo "reclaiming a stale commit lock from dead pid $pid" >&2
    rm -rf "$LOCK"
    if mkdir "$LOCK" 2>/dev/null; then echo $$ >"$LOCK/pid"; return 0; fi
  fi
  return 1
}
lock_release() { rm -rf "$LOCK"; }

quiet_for() {  # $1 dir, $2 seconds -- nothing written there recently
  local newest now
  newest=$(find "$1" -type f -print0 2>/dev/null \
           | xargs -0 stat -f '%m' 2>/dev/null | sort -n | tail -1)
  [ -n "$newest" ] || return 1
  now=$(date +%s)
  [ $((now - newest)) -ge "$2" ]
}

commit_completed() {  # $1 seconds a directory must have been quiet (default 30)
  local d id quiet="${1:-30}"
  for d in runs/*/; do
    id=$(basename "$d")
    case "$id" in _*) continue ;; esac                  # _logs, _excluded
    # A terminal artifact means the harness finished with it, one way or another.
    if [ ! -f "$d/verdict.json" ] && [ ! -f "$d/void.json" ] && \
       [ ! -f "$d/no_submit.json" ] && [ ! -f "$d/error.json" ]; then
      continue
    fi
    git ls-files --error-unmatch "$d" >/dev/null 2>&1 && continue   # already committed
    # Written to just now: let it settle, so a run mid-write is never committed.
    [ "$quiet" -eq 0 ] || quiet_for "$d" "$quiet" || continue
    git add "$d"
    git commit -q -F - <<MSG
run $id

Committed by the parallel commit loop (prereg/AGENT_PROMPTS.md §6, amendment
6). Workers never touch git; this loop holds the only lock.
MSG
    echo "committed runs/$id"
  done
}

commit_loop() {
  local waited=0
  while [ ! -f "$LOGS/.stop" ]; do
    sleep 5
    waited=$((waited + 5))
    if [ "$waited" -ge 120 ]; then
      waited=0
      if lock_acquire; then commit_completed; lock_release; fi
    fi
  done
  # Final pass with no quiet window: every worker has exited, so nothing can be
  # mid-write, and keeping the window would strand whatever finished last.
  if lock_acquire; then commit_completed 0; lock_release; fi
}

# -- a worker ----------------------------------------------------------------
record_stop() {  # $1 worker, $2 line index, $3 label, $4 exit code
  {
    echo "worker $1 stopped at schedule line $2 (seed $SEED, $3): exit $4"
    echo "$0 --schedule $SCHEDULE --start $START --workers $WORKERS --only-worker $1 --allow-code-change"
  } >"$LOGS/stopped_$1"
  echo "worker $1 STOPPED at schedule line $2 (seed $SEED): exit $4" >&2
}

run_worker() {
  # Split deliberately: in bash 3.2 a name declared by a `local` is not visible
  # to a later assignment in that same statement, so `local k="$1" log="..$k.."`
  # reads an unset k and, under `set -u`, aborts the function. The parallel path
  # hid it because the caller's loop variable is also named k; --only-worker,
  # which has no such caller, died on it. tests/test_run_arms_sh.py guards this.
  local k="$1"
  local log="$LOGS/worker_$k.log"
  local n idxs CODE
  idxs=$(.venv/bin/python -m experiments.worker_rows \
           --schedule "$SCHEDULE" --start "$START" --workers "$WORKERS" --worker "$k") \
    || { echo "worker $k: could not compute its rows" >&2; return 1; }
  {
    echo "worker $k of $WORKERS: schedule $SCHEDULE from line $START"
    echo "rows: $(echo $idxs | tr '\n' ' ')"
  } >"$log"

  for n in $idxs; do
    read -r SEED CONFIG ARM BUDGET MODEL <<<"${LINES[$n]}"
    prepare_row >>"$log" 2>&1 || { record_stop "$k" "$n" "malformed row" 64; return 0; }

    # A resumed worker skips what it already finished. RunPaths would refuse the
    # directory anyway; skipping makes the resume line simply re-runnable.
    if [ -f "runs/$RUN_ID/verdict.json" ] || [ -f "runs/$RUN_ID/void.json" ] || \
       [ -f "runs/$RUN_ID/no_submit.json" ]; then
      echo "=== [worker $k, line $n] $RUN_ID already complete; skipping ===" >>"$log"
      continue
    fi

    check_fingerprint "worker $k at schedule line $n" >>"$log" 2>&1 \
      || { record_stop "$k" "$n" "code changed mid-batch" 65; return 0; }

    echo >>"$log"
    echo "=== [worker $k, line $n] seed $SEED  $LABEL  run_id=$RUN_ID ===" >>"$log"
    run_row "$k" >>"$log" 2>&1
    CODE=$?
    if [ "$CODE" -ne 0 ]; then
      record_stop "$k" "$n" "$LABEL" "$CODE"
      return 0
    fi
  done
  echo "worker $k: done" >>"$log"
}

# ---------------------------------------------------------------- schedule mode
if [ -n "$SCHEDULE" ]; then
  [ -f "$SCHEDULE" ] || { echo "no such schedule: $SCHEDULE" >&2; exit 66; }
  START=${START:-0}
  if ! [[ "$START" =~ ^[0-9]+$ ]]; then
    echo "--start must be a non-negative integer" >&2; exit 64
  fi
  if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || [ "$WORKERS" -lt 1 ]; then
    echo "--workers must be a positive integer" >&2; exit 64
  fi
  if [ -n "$ONLY_WORKER" ]; then
    if ! [[ "$ONLY_WORKER" =~ ^[0-9]+$ ]] || [ "$ONLY_WORKER" -ge "$WORKERS" ]; then
      echo "--only-worker must be in 0..$((WORKERS - 1))" >&2; exit 64
    fi
  fi

  # Not mapfile: it is a bash 4+ builtin and /usr/bin/env bash is 3.2 on macOS,
  # so the schedule loop would die on its first line. This is 3.2-compatible.
  LINES=()
  while IFS= read -r line; do
    LINES+=("$line")
  done < <(grep -vE '^[[:space:]]*(#|$)' "$SCHEDULE")
  TOTAL=${#LINES[@]}
  if [ "$TOTAL" -eq 0 ]; then
    echo "schedule $SCHEDULE has no runnable lines" >&2; exit 66
  fi
  if [ "$START" -ge "$TOTAL" ]; then
    echo "--start $START is past the end of the schedule ($TOTAL runs)" >&2; exit 64
  fi
  echo "schedule: $SCHEDULE, $TOTAL runs, starting at line index $START"

  BATCH_FP=$(FP fingerprint) || { echo "could not read the code fingerprint" >&2; exit 70; }
  BATCH_HEAD=$(FP head)
  echo "code: fingerprint $BATCH_FP at HEAD $BATCH_HEAD"

  # -- parallel ---------------------------------------------------------------
  if [ "$WORKERS" -gt 1 ] || [ -n "$ONLY_WORKER" ]; then
    mkdir -p "$LOGS"
    rm -f "$LOGS"/stopped_* "$LOGS/.stop"
    rm -rf "$LOCK"
    echo "workers: $WORKERS${ONLY_WORKER:+ (running only worker $ONLY_WORKER)}, logs in $LOGS/"

    commit_loop & CL_PID=$!
    WPIDS=()
    if [ -n "$ONLY_WORKER" ]; then
      run_worker "$ONLY_WORKER" & WPIDS+=($!)
    else
      for ((k = 0; k < WORKERS; k++)); do run_worker "$k" & WPIDS+=($!); done
    fi
    # A worker returns 0 both when it finishes and when it records a stop, so a
    # non-zero status here means it died unexpectedly. That must not be reported
    # as success: an earlier version ignored wait's status and printed "every
    # worker finished" over a worker that had aborted before its first run.
    FAILED=0
    for p in "${WPIDS[@]}"; do wait "$p" || FAILED=$((FAILED + 1)); done

    touch "$LOGS/.stop"; wait "$CL_PID"; rm -f "$LOGS/.stop"

    echo
    STOPPED=0
    for f in "$LOGS"/stopped_*; do
      [ -e "$f" ] || continue
      STOPPED=$((STOPPED + 1))
      sed -n '1p' "$f"
      echo "  resume: $(sed -n '2p' "$f")"
    done
    if [ "$STOPPED" -eq 0 ] && [ "$FAILED" -eq 0 ]; then
      echo "done: every worker finished the schedule from line $START"
      exit 0
    fi
    if [ "$FAILED" -gt 0 ]; then
      echo "$FAILED worker(s) exited abnormally without recording a stop." >&2
      echo "Their rows did not run. Logs: $LOGS/worker_*.log" >&2
    fi
    if [ "$STOPPED" -gt 0 ]; then
      echo "$STOPPED worker(s) stopped; the rest ran to completion. Logs: $LOGS/worker_*.log"
    fi
    exit 1
  fi

  # -- sequential (the original path, unchanged) ------------------------------
  for ((n = START; n < TOTAL; n++)); do
    read -r SEED CONFIG ARM BUDGET MODEL <<<"${LINES[$n]}"

    check_fingerprint "to start seed $SEED at schedule line $n" || {
      echo "To continue deliberately:" >&2
      echo "  $0 --schedule $SCHEDULE --start $n --allow-code-change" >&2
      exit 65
    }

    prepare_row || exit $?

    echo
    echo "=== [$((n + 1))/$TOTAL] seed $SEED  $LABEL  run_id=$RUN_ID ==="

    run_row ""
    CODE=$?

    if [ "$CODE" -ne 0 ]; then
      echo
      echo "STOPPED at schedule line $n (seed $SEED, $LABEL, run_id $RUN_ID): exit $CODE" >&2
      echo "Resume with: $0 --schedule $SCHEDULE --start $n" >&2
      exit "$CODE"
    fi
    commit_run "$RUN_ID" "Seed index $SEED, $LABEL"
  done

  echo
  echo "done: schedule $SCHEDULE complete from line $START"
  exit 0
fi

# ---------------------------------------------------------------- legacy mode
START=${POSITIONAL[0]:-2}
LAST=79
CONFIG=s0
T=$(t_for "$CONFIG") || { echo "could not read T from CONFIGS['$CONFIG']" >&2; exit 70; }

if ! [[ "$START" =~ ^[0-9]+$ ]] || [ "$START" -lt 0 ] || [ "$START" -gt "$LAST" ]; then
  echo "usage: $0 [start-index]   (0..$LAST, default 2)" >&2
  echo "   or: $0 --schedule FILE [--start N] [--workers N]" >&2
  exit 64
fi

echo "pilot: seed indices $START..$LAST, config $CONFIG, arms alternating by parity"

for ((i = START; i <= LAST; i++)); do
  if (( i % 2 == 0 )); then ARM=control; else ARM=gate; fi
  RUN_ID="${CONFIG}_T${T}_${ARM}_$(printf '%03d' "$i")"

  echo
  echo "=== [$i/$LAST] arm=$ARM run_id=$RUN_ID ==="

  .venv/bin/python -m experiments.e_agent \
      --arm "$ARM" --config "$CONFIG" --runs 1 --seed-index "$i"
  CODE=$?

  if [ "$CODE" -ne 0 ]; then
    echo
    echo "STOPPED at seed index $i (arm $ARM, run_id $RUN_ID): exit $CODE" >&2
    echo "Resume with: $0 $i" >&2
    exit "$CODE"
  fi
  commit_run "$RUN_ID" "Seed index $i, arm $ARM, config $CONFIG"
done

echo
echo "done: seed indices $START..$LAST complete"
