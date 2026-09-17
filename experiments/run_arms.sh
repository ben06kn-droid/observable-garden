#!/usr/bin/env bash
# Batch runner for the agent arms.
#
#   experiments/run_arms.sh                                  # legacy: seeds 2-79 by parity
#   experiments/run_arms.sh 34                               # resume that at index 34
#   experiments/run_arms.sh --schedule experiments/schedule_240.txt
#   experiments/run_arms.sh --schedule experiments/schedule_240.txt --start 112
#
# Schedule format: one run per line, `#` comments ignored.
#
#   seed  config  arm      budget      e.g.  81  s0  budget  20
#                                            84  s3  control  -
#
# Nothing here chooses a seed, an arm or a dose; all three come from the file,
# which experiments/make_schedule.py generates from amendment 4's quotas and
# verifies against them. Regenerate rather than edit by hand.
#
# Commits after every run, so an interrupted session leaves completed runs in
# history rather than a dirty tree. Stops on the first non-zero exit and prints
# the failing seed: a seat that is rate limited stays rate limited, and a retry
# loop would burn the window.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

SCHEDULE=""
START=""
ALLOW_CODE_CHANGE=0
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --schedule) SCHEDULE="${2:-}"; shift 2 ;;
    --start)    START="${2:-}";    shift 2 ;;
    --allow-code-change) ALLOW_CODE_CHANGE=1; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *)          POSITIONAL+=("$1"); shift ;;
  esac
done

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

# ---------------------------------------------------------------- schedule mode
if [ -n "$SCHEDULE" ]; then
  [ -f "$SCHEDULE" ] || { echo "no such schedule: $SCHEDULE" >&2; exit 66; }
  START=${START:-0}
  if ! [[ "$START" =~ ^[0-9]+$ ]]; then
    echo "--start must be a non-negative integer" >&2; exit 64
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

  # The code state this batch runs under. Deliberately not HEAD: this script
  # commits after every run, so HEAD moves constantly while the code does not,
  # and a guard on HEAD would fire on the second run of every batch and mean
  # nothing. experiments/code_state.py fingerprints the paths that determine how
  # a run behaves (prereg included) and ignores runs/.
  FP() { .venv/bin/python -m experiments.code_state --field "$1"; }
  BATCH_FP=$(FP fingerprint) || { echo "could not read the code fingerprint" >&2; exit 70; }
  BATCH_HEAD=$(FP head)
  echo "code: fingerprint $BATCH_FP at HEAD $BATCH_HEAD"

  for ((n = START; n < TOTAL; n++)); do
    read -r SEED CONFIG ARM BUDGET MODEL <<<"${LINES[$n]}"

    NOW_FP=$(FP fingerprint)
    if [ "$NOW_FP" != "$BATCH_FP" ]; then
      NOW_HEAD=$(FP head)
      if [ "$ALLOW_CODE_CHANGE" -eq 1 ]; then
        echo "code changed mid-batch; continuing because --allow-code-change was passed:"
        echo "  batch started: fingerprint $BATCH_FP at HEAD $BATCH_HEAD"
        echo "  now:           fingerprint $NOW_FP at HEAD $NOW_HEAD"
        BATCH_FP="$NOW_FP"; BATCH_HEAD="$NOW_HEAD"
      else
        echo >&2
        echo "REFUSING to start seed $SEED at schedule line $n: the code changed mid-batch." >&2
        echo "  batch started: fingerprint $BATCH_FP at HEAD $BATCH_HEAD" >&2
        echo "  now:           fingerprint $NOW_FP at HEAD $NOW_HEAD" >&2
        echo "Runs produced before and after a code change are not comparable." >&2
        echo "To continue deliberately:" >&2
        echo "  $0 --schedule $SCHEDULE --start $n --allow-code-change" >&2
        exit 65
      fi
    fi

    T=$(t_for "$CONFIG") || { echo "could not read T for $CONFIG" >&2; exit 70; }
    # Batch 3 added a model column. Schedules written before it default to sonnet.
    MODEL=${MODEL:-claude-sonnet-5}
    case "$MODEL" in
      claude-sonnet-5) MTAG=sonnet ;;
      claude-fable-5-1) MTAG=fable ;;
      *) echo "unknown model on schedule line $n: $MODEL" >&2; exit 64 ;;
    esac

    # No array for the optional flag: bash 3.2 under `set -u` treats an empty
    # array as unset, so "${BUDGET_ARG[@]}" aborts on every non-budget line --
    # which is the first scheduled run. bash -n cannot see it; only running the
    # loop body does.
    if [ "$BUDGET" = "-" ] || [ -z "$BUDGET" ]; then
      RUN_ID="${CONFIG}_T${T}_${MTAG}_${ARM}_$(printf '%03d' "$SEED")"
      LABEL="arm $ARM, config $CONFIG, model $MODEL"
    else
      RUN_ID="${CONFIG}_T${T}_${MTAG}_${ARM}${BUDGET}_$(printf '%03d' "$SEED")"
      LABEL="arm $ARM (B=$BUDGET), config $CONFIG, model $MODEL"
    fi

    echo
    echo "=== [$((n + 1))/$TOTAL] seed $SEED  $LABEL  run_id=$RUN_ID ==="

    if [ "$BUDGET" = "-" ] || [ -z "$BUDGET" ]; then
      .venv/bin/python -m experiments.e_agent \
          --arm "$ARM" --config "$CONFIG" --runs 1 --seed-index "$SEED" --model "$MODEL"
    else
      .venv/bin/python -m experiments.e_agent \
          --arm "$ARM" --config "$CONFIG" --runs 1 --seed-index "$SEED" \
          --budget "$BUDGET" --model "$MODEL"
    fi
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
  echo "   or: $0 --schedule FILE [--start N]" >&2
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
