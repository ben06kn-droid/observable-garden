#!/usr/bin/env bash
# Pilot runner for the agent arms: seeds 2-79, arms alternating by parity.
#
#   experiments/run_arms.sh          # start at seed index 2
#   experiments/run_arms.sh 34       # resume at seed index 34
#
# Seed indices 0 and 1 are spent: 0 on the superseded T=500 pilot and on the
# T=5000 control run that replaced it. prereg/AGENT_PROMPTS.md section 4 fixes
# the seed sequence and requires arms to alternate within every session, so
# parity assigns them: even index -> control, odd -> gate. Nothing here chooses
# a seed or an arm; both follow from the index.
#
# Commits after every run, so an interrupted session leaves the completed runs
# in history rather than in a dirty tree. Stops on the first non-zero exit and
# prints the failing index, because a seat that is rate limited stays rate
# limited and a retry loop would burn the window.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

START=${1:-2}
LAST=79
CONFIG=s0

# Read T from the config rather than hardcoding it: run_id embeds T, the config
# has already moved once (500 -> 5000, amendment 1), and a stale literal here
# would commit the wrong path or warn that a run it just made is missing.
T=$(.venv/bin/python -c "from experiments.e_agent import CONFIGS; print(CONFIGS['$CONFIG']['T'])") || {
  echo "could not read T from CONFIGS['$CONFIG']" >&2; exit 70; }

if ! [[ "$START" =~ ^[0-9]+$ ]] || [ "$START" -lt 0 ] || [ "$START" -gt "$LAST" ]; then
  echo "usage: $0 [start-index]   (0..$LAST, default 2)" >&2
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

  if [ -d "runs/$RUN_ID" ]; then
    git add "runs/$RUN_ID"
    git commit -q -m "pilot run $RUN_ID

Seed index $i, arm $ARM, config $CONFIG (T=5000, T_oos=1000) per
prereg/AGENT_PROMPTS.md sections 3 and 4 as amended by amendment 1."
    echo "committed runs/$RUN_ID"
  else
    echo "WARNING: runs/$RUN_ID missing after a zero exit; nothing committed" >&2
  fi
done

echo
echo "done: seed indices $START..$LAST complete"
