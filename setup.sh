#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# setup.sh — reproducible toolchain for hyperon-miner-llm
#
# Why this exists: upstream setup.sh always checks out PeTTa's *latest* commit.
# PeTTa changes quickly, so the miner's own CI breaks whenever PeTTa moves
# (see docs/01-problem.md, Issue 2). Here we pin the PeTTa commit the miner was
# last known to work with.
#
# Usage:  ./setup.sh            # install PeTTa into .petta/ and check deps
#         PETTA_COMMIT=<sha> ./setup.sh   # try another PeTTa version
# -----------------------------------------------------------------------------
set -euo pipefail

PETTA_REPO="https://github.com/patham9/PeTTa"
# Last PeTTa commit on or before the miner's last petta-main commit (2026-09-27).
PETTA_COMMIT="${PETTA_COMMIT:-9e5929ad577121bfcf6287d4de6d7649f1d98b91}"
MIN_SWIPL="9.1.22"  # first release with janus, the Python bridge used by py-call

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PETTA_DIR="$ROOT/.petta"

say()  { printf '\033[36m[setup]\033[0m %s\n' "$*"; }
fail() { printf '\033[31m[setup] %s\033[0m\n' "$*" >&2; exit 1; }

# 1. submodule ---------------------------------------------------------------
if [ ! -f "$ROOT/external/hyperon-miner/run_miner.metta" ]; then
  say "Fetching the hyperon-miner submodule"
  git -C "$ROOT" submodule update --init --recursive
fi

# 2. SWI-Prolog ----------------------------------------------------------------
command -v swipl >/dev/null 2>&1 || fail "swipl not found.
  macOS:  brew install swi-prolog
  Ubuntu: sudo apt-add-repository ppa:swi-prolog/stable && sudo apt install swi-prolog"

SWIPL_VERSION="$(swipl --dump-runtime-variables | sed -n 's/^PLVERSION="\([0-9]*\)";/\1/p')"
# PLVERSION is e.g. 90334 for 9.3.34
want=$(echo "$MIN_SWIPL" | awk -F. '{printf "%d%02d%02d", $1, $2, $3}')
[ "$SWIPL_VERSION" -ge "$want" ] || fail "SWI-Prolog >= $MIN_SWIPL required (found PLVERSION=$SWIPL_VERSION)."
swipl -g "use_module(library(janus)),halt" -t "halt(1)" </dev/null >/dev/null 2>&1 \
  || fail "SWI-Prolog was built without janus (the Python bridge). Reinstall it with Python support."
say "SWI-Prolog OK (PLVERSION=$SWIPL_VERSION, janus available)"

# 3. PeTTa at a pinned commit -------------------------------------------------
if [ ! -d "$PETTA_DIR/.git" ]; then
  say "Cloning PeTTa"
  git clone --quiet "$PETTA_REPO" "$PETTA_DIR"
fi
git -C "$PETTA_DIR" fetch --quiet origin
git -C "$PETTA_DIR" checkout --quiet "$PETTA_COMMIT"
say "PeTTa pinned at $(git -C "$PETTA_DIR" log -1 --format='%h (%cs)')"

# 4. Python deps ----------------------------------------------------------------
if [ "${SKIP_PIP:-0}" != "1" ]; then
  say "Installing Python dependencies"
  python3 -m pip install --quiet -r "$ROOT/requirements.txt" ${PIP_EXTRA_ARGS:-}
  python3 -m pip install --quiet -e "$ROOT" ${PIP_EXTRA_ARGS:-}
fi

say "Done. Try:  make run"
