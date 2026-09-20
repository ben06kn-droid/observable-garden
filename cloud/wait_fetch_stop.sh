#!/usr/bin/env bash
# Wait for a detached run to finish, fetch its results, then stop the instance.
# Run this from the repository root ON YOUR MAC, not on the instance.
#
#   cloud/wait_fetch_stop.sh og calib
#
# HOST is an alias from ~/.ssh/config carrying HostName, User and IdentityFile:
#
#   Host og
#       HostName 18.217.175.127
#       User ubuntu
#       IdentityFile "/path/to/key.pem"
#
# An alias rather than -i KEY because rsync splits -e on whitespace, so a key
# path containing a space cannot be passed through it -- not with quoting, and
# not with printf %q, both of which were tried. The alias keeps the path out of
# the command line altogether, and has the side benefit that replacing the
# instance means editing one HostName rather than every invocation.
#
# NAME is the tmux session name given to cloud/run.sh. That script appends
# "[exit N]" to logs/NAME.log when the command returns, which is the completion
# marker polled for here.
#
# Order matters and is the whole point of this script: a stopped instance cannot
# be rsynced from, so results are pulled BEFORE the stop. Stopping first would
# strand them on the volume and cost a restart to recover.
#
# `sudo shutdown -h now` STOPS an EBS-backed instance whose
# instance-initiated-shutdown-behavior is the default. A stopped instance still
# bills for its EBS volume: terminate it in the console when the work is done,
# not merely finished for the day. This script deliberately stops rather than
# terminates, so a failed run can be resumed from its checkpoints.
set -uo pipefail

if [ $# -lt 2 ]; then
  echo "usage: cloud/wait_fetch_stop.sh HOST NAME [POLL_SECONDS]" >&2
  echo "  HOST is an ~/.ssh/config alias, e.g. og" >&2
  exit 2
fi
HOST="$1"; NAME="$2"; POLL="${3:-60}"
LOG="observable-garden/logs/$NAME.log"

if ! ssh -o ConnectTimeout=20 "$HOST" true 2>/dev/null; then
  echo "cannot reach '$HOST'. Is it in ~/.ssh/config, and is the instance running?" >&2
  exit 1
fi

echo "waiting for '$NAME' on $HOST (polling every ${POLL}s; Ctrl-C is safe, the run continues)"
while true; do
  line=$(ssh "$HOST" "grep -m1 '^\[exit ' $LOG 2>/dev/null" || true)
  if [ -n "$line" ]; then
    echo "run finished: $line"
    break
  fi
  if ! ssh "$HOST" "tmux has-session -t $NAME 2>/dev/null"; then
    echo "WARNING: no tmux session '$NAME' and no exit marker." >&2
    echo "The run may have died before writing one. Not stopping the instance." >&2
    ssh "$HOST" "tail -20 $LOG 2>/dev/null" || true
    exit 1
  fi
  sleep "$POLL"
done

echo "fetching figures/ and logs/"
rsync -avz "$HOST:observable-garden/figures/" figures/ || {
  echo "rsync failed; NOT stopping the instance" >&2; exit 1; }
rsync -avz "$HOST:observable-garden/logs/" logs/ || true

code="${line#*[exit }"; code="${code%]*}"
if [ "$code" != "0" ]; then
  echo "run exited $code; results fetched, NOT stopping the instance so it can be inspected" >&2
  exit "$code"
fi

echo "stopping the instance"
ssh "$HOST" "sudo shutdown -h now" || true   # the connection drops as it goes down
echo "stop issued. The EBS volume still bills while stopped; terminate in the"
echo "console when the work is finished, not just paused."
