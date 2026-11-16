#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# demo.sh — a 5-minute live demo for the presentation  (make demo)
#
#   1. the problem:   upstream's entry point vs ours; the duplicate + scoring bugs
#   2. equivalence:   guided miner at 100 % == upstream, every support re-counted
#   3. the LLM:       30 % budget with the real chain (Groq -> NVIDIA -> Gemini)
#   4. failure path:  garbage answer -> next provider; total outage -> still completes
#   5. evidence:      the generated results table and verdicts
#
# Steps that need API keys are skipped (with a note) when .env has none.
# DEMO_PAUSE=0 runs straight through; otherwise it waits for Enter between steps.
# -----------------------------------------------------------------------------
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export LANG=C.UTF-8 LC_ALL=C.UTF-8
PY="${PYTHON:-python3}"
OUT="runs/demo"
mkdir -p "$OUT"

step() { printf '\n\033[1;36m━━ %s ━━\033[0m\n' "$*"; }
note() { printf '\033[2m%s\033[0m\n' "$*"; }
pause() { [ "${DEMO_PAUSE:-1}" = "0" ] || read -r -p $'\033[2m[Enter] next step\033[0m ' _; }
has_keys() { [ -f .env ] && grep -qE '^(GROQ|NVIDIA|GEMINI)_API_KEY=.+' .env; }

step "1/5  The problem: the documented entry point does not run (Issue 1)"
note "upstream run_miner.metta passes 8 arguments to a 9-argument function:"
(cd external/hyperon-miner && bash "$ROOT/.petta/run.sh" run_miner.metta 2>&1) \
  | sed 's/\x1b\[[0-9;]*m//g' | grep -v '^[[:space:]]*$' | tail -1
note "ours (run_miner.metta) imports the generic miner and passes all 9:"
bash .petta/run.sh run_miner.metta 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -c '^(surprisingnessOf' \
  | xargs printf '  %s scored patterns\n'
pause

step "2/5  Equivalence: guided miner, exhaustive, 100 % budget == upstream output"
note "same data, same minsup, 3 conjuncts; every support re-counted by the Python oracle"
$PY -m minerllm mine --dataset external/hyperon-miner/experiments/data/ugly_man_sodaDrinker \
    --minsup 10 --depth 1 --surp none --top 0 --out "$OUT/upstream" | tail -1
$PY -m minerllm guided --config configs/sample.yaml --depth 1 --strategy exhaustive \
    --budget 1.0 --top 0 --out "$OUT/exhaustive" 2>/dev/null | tail -1
pause

step "3/5  The LLM ranks schema joins; the miner verifies only 30 % of candidates"
if has_keys; then
  $PY -m minerllm guided --config configs/university.yaml --strategy llm --budget 0.3 \
      --top 5 --out "$OUT/llm"
  note "top joins the LLM scored (from the execution trace):"
  $PY - "$OUT/llm" <<'EOF'
import json, sys, glob
for f in glob.glob(sys.argv[1] + "/*.trace.jsonl"):
    for line in open(f):
        e = json.loads(line)
        if e.get("top_joins"):
            for j, s in e["top_joins"][:6]:
                print(f"  {s:4.0f}  {j}")
EOF
else
  note "(no API keys in .env: skipped. The offline mock shows the same flow:)"
  $PY -m minerllm guided --config configs/university.yaml --strategy llm --budget 0.3 \
      --providers mock --no-cache --top 3 --out "$OUT/llm-mock"
fi
pause

step "4/5  Failure path: a provider talks nonsense, then every provider is down"
note "first provider returns garbage -> validator rejects it -> next provider answers:"
$PY -m minerllm guided --config configs/university.yaml --strategy llm --budget 0.3 \
    --providers mock:garbage,mock --no-cache --top 0 --out "$OUT/garbage" 2>&1 | tail -1
note "every provider fails -> cardinality fallback -> mining still completes, all logged:"
$PY -m minerllm guided --config configs/university.yaml --strategy llm --budget 0.3 \
    --providers mock:error,mock:fatal --no-cache --top 0 --out "$OUT/outage" 2>&1 | tail -1
pause

step "5/5  Evidence: generated results and pre-registered verdicts"
if [ -f results/results.md ]; then
  sed -n '/^### university$/,/^### university-anon/p' results/results.md | grep -E '^\| (method|cardinality|random|llm)' | grep -E '30 %|method' | head -12
  echo
  sed -n '/^\*\*H1\*\*/,$p' results/results.md | head -20
else
  note "(no results yet: make eval-baselines && make eval-llm && make report)"
fi
printf '\n\033[1;32mDone.\033[0m Artefacts in %s/ (scripts, traces, oracle checks).\n' "$OUT"
