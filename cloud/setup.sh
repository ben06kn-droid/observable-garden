#!/usr/bin/env bash
# Provision an Ubuntu 24.04 EC2 instance (sized for c7a.8xlarge) to run observable-garden experiments.
#
# From your Mac, once the instance is running:
#   scp -i KEY.pem cloud/setup.sh ubuntu@PUBLIC_IP:~
#   ssh -i KEY.pem ubuntu@PUBLIC_IP 'bash ~/setup.sh'
#
# It installs system packages and uv, clones (or updates) the repository, builds a Python
# environment matching the local one, and runs the test suite. Safe to rerun. Only code that has
# been committed and pushed reaches the instance.
#
# Settings (environment variables): REPO_URL, BRANCH (main), PYTHON_VERSION (3.14),
# DEST (~/observable-garden), RUN_TESTS (1).
#
# Afterwards:
#   start runs detached:  cd ~/observable-garden && cloud/run.sh NAME python -m experiments.MODULE
#   fetch results:        rsync -avz -e "ssh -i KEY.pem" ubuntu@PUBLIC_IP:observable-garden/figures/ figures/
#   when finished:        terminate the instance in the EC2 console (a stopped instance still bills storage)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/ben06kn-droid/observable-garden.git}"
BRANCH="${BRANCH:-main}"
PYTHON_VERSION="${PYTHON_VERSION:-3.14}"
DEST="${DEST:-$HOME/observable-garden}"
RUN_TESTS="${RUN_TESTS:-1}"

log() { printf '\n==> %s\n' "$*"; }

log "System packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git tmux build-essential htop

log "uv"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

log "Repository ($BRANCH)"
if [ -d "$DEST/.git" ]; then
  git -C "$DEST" fetch --quiet origin "$BRANCH"
  git -C "$DEST" checkout --quiet "$BRANCH"
  git -C "$DEST" pull --quiet --ff-only origin "$BRANCH"
elif ! git clone --quiet --branch "$BRANCH" "$REPO_URL" "$DEST"; then
  echo "Clone failed. For a private repository, connect with 'ssh -A' (forwards your GitHub key)" >&2
  echo "and rerun with REPO_URL=git@github.com:ben06kn-droid/observable-garden.git" >&2
  exit 1
fi
cd "$DEST"
echo "at $(git rev-parse --short HEAD): $(git log -1 --format=%s)"

log "Python $PYTHON_VERSION environment"
uv python install "$PYTHON_VERSION"
if [ ! -x .venv/bin/python ]; then
  uv venv --python "$PYTHON_VERSION" .venv
fi
uv pip install --python .venv/bin/python -e ".[dev]"

if [ "$RUN_TESTS" = "1" ]; then
  log "Test suite"
  .venv/bin/pytest -q
fi

log "Ready: $(nproc) cores, $(free -g | awk '/^Mem:/{print $2}') GB RAM, $(.venv/bin/python --version)"
echo "Start runs with: cd $DEST && cloud/run.sh NAME python -m experiments.MODULE"
