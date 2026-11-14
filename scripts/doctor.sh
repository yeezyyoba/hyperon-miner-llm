#!/usr/bin/env bash
# doctor.sh — check that the local toolchain can run the miner and the LLM layer.
set -u
ok()   { printf '  \033[92m✔\033[0m %s\n' "$*"; }
bad()  { printf '  \033[91m✘\033[0m %s\n' "$*"; FAIL=1; }
FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "hyperon-miner-llm doctor"

command -v swipl >/dev/null && ok "swipl: $(swipl --version | head -1)" || bad "swipl not found (macOS: brew install swi-prolog)"
# Ask janus for its Python version. </dev/null: if a goal fails, swipl must not sit at its prompt.
JANUS_PY=$(swipl -g "use_module(library(janus)),py_call(sys:version,S),split_string(S,' ','',[V|_]),write(V),halt" -t "halt(1)" </dev/null 2>/dev/null | cut -d. -f1,2)
if [ -n "$JANUS_PY" ]; then
  ok "janus (Python bridge) uses Python $JANUS_PY"
else
  bad "SWI-Prolog has no working janus"
  if [ "$(uname)" = "Darwin" ] && swipl -g "use_module(library(janus))" -t halt </dev/null 2>&1 | grep -q "Python3.framework"; then
    echo "     Homebrew's janus.so looks for Apple's Python3.framework in Xcode. Fix (see README, macOS):"
    echo "       J=\$(find \$(brew --prefix swi-prolog)/ -name janus.so | head -1)"
    echo "       chmod +w \"\$J\" && install_name_tool -add_rpath /Library/Developer/CommandLineTools/Library/Frameworks \"\$J\""
    echo "       chmod -w \"\$J\" && codesign -f -s - \"\$J\""
  fi
fi
VENV_PY=$(python3 -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
if [ "$JANUS_PY" = "$VENV_PY" ]; then ok "python3 is $VENV_PY (matches janus)"
else bad "python3 is $VENV_PY but janus uses $JANUS_PY: create the venv with python$JANUS_PY (see README)"; fi
[ -f "$ROOT/.petta/run.sh" ] && ok "PeTTa installed at $(git -C "$ROOT/.petta" log -1 --format='%h')" || bad "PeTTa missing: run ./setup.sh"
[ -f "$ROOT/external/hyperon-miner/run_miner.metta" ] && ok "submodule present" || bad "submodule missing: git submodule update --init"
python3 -c "import scipy, requests, yaml, dotenv, minerllm" 2>/dev/null && ok "Python packages importable" || bad "missing Python packages: ./setup.sh"
PYTHONPATH="$(python3 -c 'from minerllm.petta import python_path; print(python_path())' 2>/dev/null)" \
  swipl -g "use_module(library(janus)),py_call(importlib:import_module(scipy),_),py_call(importlib:import_module(requests),_),halt" -t "halt(1)" </dev/null >/dev/null 2>&1 \
  && ok "janus can import scipy + requests from the venv" || bad "janus cannot import the venv packages (Python version mismatch?)"
if [ -f "$ROOT/.env" ]; then
  for k in GEMINI_API_KEY GROQ_API_KEY NVIDIA_API_KEY; do
    grep -qE "^$k=.+" "$ROOT/.env" && ok "$k set" || printf '  \033[93m•\033[0m %s not set (provider will be skipped)\n' "$k"
  done
else
  printf '  \033[93m•\033[0m no .env yet (only needed for real LLM runs: cp .env.example .env)\n'
fi
git -C "$ROOT" check-ignore -q .env && ok ".env is git-ignored" || bad ".env is NOT ignored"
exit $FAIL
