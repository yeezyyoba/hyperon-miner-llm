#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# reproduce_issues.sh — re-creates the evidence in docs/01-problem.md
#
#   Issue 1  upstream run_miner.metta does not run
#   Issue 2  upstream CI depends on PeTTa HEAD (pinned: 8/8 pass, HEAD: fewer)
#   Issue 3  conjunction expansion cost grows fast with depth   (make profile)
#
# Needs: ./setup.sh done. Issue 2 also clones PeTTa HEAD into .cache/petta-head.
# -----------------------------------------------------------------------------
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MINER="$ROOT/external/hyperon-miner"
OUT="$ROOT/runs/issues"; mkdir -p "$OUT"
export LANG=C.UTF-8 LC_ALL=C.UTF-8
strip() { sed 's/\x1b\[[0-9;]*m//g'; }
hr() { printf '\n\033[36m== %s ==\033[0m\n' "$*"; }

# --- Issue 1 ------------------------------------------------------------------
hr "Issue 1: upstream run_miner.metta on pinned PeTTa"
(cd "$MINER" && bash "$ROOT/.petta/run.sh" run_miner.metta) 2>&1 | strip > "$OUT/issue1-upstream-run.log"
if grep -q '^(supportOf\|^(surprisingnessOf' "$OUT/issue1-upstream-run.log"; then
  echo "upstream entry point produced results (issue not reproduced)"
else
  echo "upstream entry point produced NO results. Final output line:"
  grep -v '^[[:space:]]*$' "$OUT/issue1-upstream-run.log" | tail -1
  echo "(a 'partial' result means PeTTa received the wrong number of arguments)"
fi
hr "Issue 1: fixed run_miner.metta (this repo)"
(cd "$ROOT" && bash .petta/run.sh run_miner.metta) 2>&1 | strip > "$OUT/issue1-fixed-run.log"
echo "fixed entry point: $(grep -c '^(surprisingnessOf' "$OUT/issue1-fixed-run.log") scored patterns"

# --- Issue 2 ------------------------------------------------------------------
run_suite() {  # $1 = PeTTa dir, $2 = label
  local dir="$1" label="$2"
  grep -q '^#!' "$dir/run.sh" || { printf '#!/bin/bash\n' | cat - "$dir/run.sh" > "$dir/run.sh.tmp" && mv "$dir/run.sh.tmp" "$dir/run.sh"; }
  chmod +x "$dir/run.sh"
  (cd "$MINER" && PATH="$dir:$PATH" python3 scripts/run-tests.py) 2>&1 | strip > "$OUT/issue2-$label.log"
  local pass fail
  pass=$(grep -c '^PASSED' "$OUT/issue2-$label.log"); fail=$(grep -c '^FAILED' "$OUT/issue2-$label.log")
  echo "$label ($(git -C "$dir" log -1 --format='%h %cs')): $pass passed, $fail failed"
}
hr "Issue 2: upstream test suite, pinned vs latest PeTTa"
run_suite "$ROOT/.petta" pinned
if [ "${SKIP_HEAD:-0}" != "1" ]; then
  HEAD_DIR="$ROOT/.cache/petta-head"
  [ -d "$HEAD_DIR/.git" ] || git clone --quiet https://github.com/patham9/PeTTa "$HEAD_DIR"
  git -C "$HEAD_DIR" pull --quiet --ff-only || true
  run_suite "$HEAD_DIR" head
fi

hr "Logs written to runs/issues/"
