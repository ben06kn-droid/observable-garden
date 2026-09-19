#!/usr/bin/env bash
# Start a command detached in tmux, logged to logs/NAME.log, so it survives disconnecting.
# Run from the repository root on the instance.
#
#   cloud/run.sh e12 python -m experiments.type_m_by_power
#   THREADS=32 cloud/run.sh big python -m experiments.some_single_process_job
#
#   tail -f logs/e12.log     follow the output
#   tmux attach -t e12       watch it live (detach with Ctrl-b d)
#   tmux ls                  list running sessions
#
# THREADS is the numpy/BLAS thread count per process: 1 by default, right when many worker
# processes share the cores; raise it for a single process that should use all of them.
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: cloud/run.sh NAME COMMAND [ARGS...]" >&2
  exit 2
fi
name="$1"
shift
if tmux has-session -t "$name" 2>/dev/null; then
  echo "tmux session '$name' already exists" >&2
  exit 1
fi

mkdir -p logs
threads="${THREADS:-1}"
printf -v cmd '%q ' "$@"
tmux new-session -d -s "$name" bash -c "
  export OMP_NUM_THREADS=$threads OPENBLAS_NUM_THREADS=$threads MKL_NUM_THREADS=$threads
  source .venv/bin/activate
  $cmd 2>&1 | tee logs/$name.log
  echo \"[exit \${PIPESTATUS[0]}]\" | tee -a logs/$name.log
"
echo "started '$name' in tmux; log: logs/$name.log"
