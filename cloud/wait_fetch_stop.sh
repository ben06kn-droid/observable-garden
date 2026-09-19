#!/usr/bin/env bash
# Wait for a detached run to finish, fetch its results, then stop the instance.
# Run this from the repository root ON YOUR MAC, not on the instance.
#
#   cloud/wait_fetch_stop.sh ~/path/to/key.pem 18.217.175.127 armB
#
# Quote the key path if it contains spaces; it is passed to rsync's -e, which
# word-splits, so it is re-quoted with printf %q below rather than interpolated.
#
# NAME is the tmux session name given to cloud/run.sh. That script appends
# "[exit N]" to logs/NAME.log when the command returns, which is the completion
# marker polled for here.
#
# Order matters and is the whole point of this script: a stopped instance cannot
# be rsynced from, so results are pulled BEFORE the stop. Stopping before
# fetching would strand them on the volume and cost a restart to recover.
#
# `sudo shutdown -h now` STOPS an EBS-backed instance whose
# instance-initiated-shutdown-behavior is the default. A stopped instance still
# bills for its EBS volume: terminate it in the console when the work is done,
# not merely finished for the day. This script deliberately stops rather than
# terminates, so a failed run can be resumed from its checkpoints.
set -uo pipefail

if [ $# -lt 3 ]; then
  echo "usage: cloud/wait_fetch_stop.sh KEY.pem PUBLIC_IP NAME [POLL_SECONDS]" >&2
  exit 2
fi
KEY="$1"; IP="$2"; NAME="$3"; POLL="${4:-60}"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "ubuntu@$IP")
LOG="observable-garden/logs/$NAME.log"

echo "waiting for '$NAME' on $IP (polling every ${POLL}s; Ctrl-C is safe, the run continues)"
while true; do
  line=$("${SSH[@]}" "grep -m1 '^\[exit ' $LOG 2>/dev/null" || true)
  if [ -n "$line" ]; then
    echo "run finished: $line"
    break
  fi
  if ! "${SSH[@]}" "tmux has-session -t $NAME 2>/dev/null"; then
    echo "WARNING: no tmux session '$NAME' and no exit marker." >&2
    echo "The run may have died before writing one. Not stopping the instance." >&2
    "${SSH[@]}" "tail -20 $LOG 2>/dev/null" || true
    exit 1
  fi
  sleep "$POLL"
done

echo "fetching figures/ and logs/"
# %q so a key path containing spaces survives rsync splitting -e on whitespace.
printf -v RSH 'ssh -i %q -o StrictHostKeyChecking=accept-new' "$KEY"
rsync -avz -e "$RSH" "ubuntu@$IP:observable-garden/figures/" figures/ || {
  echo "rsync failed; NOT stopping the instance" >&2; exit 1; }
rsync -avz -e "$RSH" "ubuntu@$IP:observable-garden/logs/" logs/ || true

code="${line#*[exit }"; code="${code%]*}"
if [ "$code" != "0" ]; then
  echo "run exited $code; results fetched, NOT stopping the instance so it can be inspected" >&2
  exit "$code"
fi

echo "stopping the instance"
"${SSH[@]}" "sudo shutdown -h now" || true   # the connection drops as it goes down
echo "stop issued. The EBS volume still bills while stopped; terminate in the"
echo "console when the work is finished, not just paused."
